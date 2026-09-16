# =============================================================================
# 모듈 설명: emails 도메인의 서비스/셀렉터/뷰 동작을 검증합니다.
# - 주요 범위: 소속 판별, 이동/삭제, Outbox 처리, API 엔드포인트
# - 불변 조건: 테스트는 DB 트랜잭션을 사용하며 시간은 timezone-aware입니다.
# =============================================================================

from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone as dt_timezone
from email.message import EmailMessage
from io import BytesIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

import api.account.services as account_services
from api.common.services import UNASSIGNED_USER_SDWT_PROD
from api.emails.models import Email, EmailAsset, EmailOutbox
from api.emails.permissions import resolve_access_control
from api.emails.selectors import (
    get_filtered_emails,
    resolve_assistant_email_scope,
    resolve_email_affiliation,
)
from api.emails.serializers import (
    EmailBulkDeleteInputSerializer,
    EmailMoveInputSerializer,
)
from api.emails.services import (
    _parse_message_to_fields,
    claim_unassigned_emails_for_user,
    delete_single_email,
    enqueue_rag_index_for_emails,
    enqueue_rag_index,
    ingest_pop3_mailbox,
    move_emails_to_user_sdwt_prod,
    move_sender_emails_after,
    parse_datetime_value,
    process_email_outbox_batch,
    run_pop3_ingest_from_settings,
    store_email_html_and_assets,
)
from api.emails.services.ingest import (
    _LongLinePOP3,
    _compile_excluded_subject_patterns,
    _is_excluded_subject,
    _iter_pop3_messages,
)
from api.rag.services import RAG_INDEX_EMAILS, resolve_rag_index_name

UTC = getattr(timezone, "utc", dt_timezone.utc)


class EmailWriteInputSerializerTests(SimpleTestCase):
    """메일 삭제·이동 입력 serializer의 canonical 계약을 검증합니다."""

    def test_bulk_delete_accepts_camel_case_ids_and_normalizes_numbers(self) -> None:
        """camelCase ID 목록의 숫자 문자열을 정수로 변환합니다."""

        serializer = EmailBulkDeleteInputSerializer(
            data={"emailIds": ["1", 2]},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["normalized_email_ids"], [1, 2])

    def test_move_accepts_canonical_target_without_changing_service_input(self) -> None:
        """camelCase 대상 메일함 값을 service 입력용 원문으로 보존합니다."""

        serializer = EmailMoveInputSerializer(
            data={
                "emailIds": [3],
                "toUserSdwtProd": " group-b ",
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["normalized_email_ids"], [3])
        self.assertEqual(
            serializer.validated_data["normalized_to_user_sdwt_prod"],
            " group-b ",
        )

    def test_move_rejects_snake_case_aliases(self) -> None:
        """제거된 snake_case alias를 명시적인 입력 오류로 거부합니다."""

        serializer = EmailMoveInputSerializer(
            data={"email_ids": [3], "to_user_sdwt_prod": "group-b"},
        )

        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            str(serializer.errors["non_field_errors"][0]),
            "unsupported fields: email_ids, to_user_sdwt_prod",
        )

    def test_move_reuses_existing_required_field_errors(self) -> None:
        """빈 ID 목록과 누락 대상이 기존 API 오류 문구를 유지하는지 확인합니다."""

        missing_ids = EmailMoveInputSerializer(
            data={"toUserSdwtProd": "group-b"},
        )
        missing_target = EmailMoveInputSerializer(
            data={"emailIds": [1]},
        )

        self.assertFalse(missing_ids.is_valid())
        self.assertEqual(
            str(missing_ids.errors["non_field_errors"][0]),
            "emailIds must be a non-empty list",
        )
        self.assertFalse(missing_target.is_valid())
        self.assertEqual(
            str(missing_target.errors["non_field_errors"][0]),
            "toUserSdwtProd is required",
        )


def _set_current_affiliation(user, *, user_sdwt_prod: str) -> None:
    """테스트 사용자의 현재 앱 소속을 설정합니다."""

    account_services.set_current_affiliation_for_user(
        user=user,
        department="Dept",
        line="Line",
        user_sdwt_prod=user_sdwt_prod,
    )


def _allow_test_scope_access(test_case: TestCase) -> None:
    """도메인 endpoint 테스트에서 공통 portal/app 권한 경계를 격리합니다."""

    for target in (
        "api.account.services.get_access_payload",
        "api.account.services.data_scope.get_access_payload",
    ):
        patcher = patch(target, return_value={"allowed": True})
        patcher.start()
        test_case.addCleanup(patcher.stop)


def _grant_emails_affiliation_data(
    *,
    user,
    user_sdwt_prods: tuple[str, ...],
    actor=None,
) -> None:
    """테스트 사용자에게 Emails 앱의 추가 소속 데이터 범위를 부여합니다."""

    if actor is None:
        User = get_user_model()
        actor = User.objects.create_superuser(
            sabun=f"SCOPE-{user.id}",
            password="test-password",
        )
    affiliations = [
        account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod=user_sdwt_prod,
        )
        for user_sdwt_prod in user_sdwt_prods
    ]
    payload, status_code = account_services.update_user_scope_affiliation_data(
        actor=actor,
        user_id=user.id,
        scope_key="emails",
        data_scope_mode="default",
        affiliation_ids=[affiliation.id for affiliation in affiliations],
        reason="Emails 테스트 소속 데이터 범위",
    )
    if status_code != 200:
        raise AssertionError(f"테스트 소속 데이터 범위 부여 실패: {payload}")


def _grant_emails_admin(*, user, actor) -> None:
    """테스트 사용자에게 Portal 접근과 Emails 관리자 역할을 부여합니다."""

    for scope_key, role in (("portal", "user"), ("emails", "admin")):
        _payload, status_code = account_services.decide_user_access(
            actor=actor,
            user_id=user.id,
            scope_key=scope_key,
            action="grant",
            role=role,
            reason="Emails 관리자 테스트 권한 부여",
        )
        if status_code != 200:
            raise AssertionError(f"테스트 권한 부여 실패: {scope_key}={status_code}")

    payload, status_code = account_services.update_user_scope_affiliation_data(
        actor=actor,
        user_id=user.id,
        scope_key="emails",
        data_scope_mode="all",
        affiliation_ids=[],
        reason="Emails 관리자 테스트 전체 범위",
    )
    if status_code != 200:
        raise AssertionError(f"테스트 전체 데이터 범위 부여 실패: {payload}")


class EmailPop3SettingsTests(SimpleTestCase):
    """POP3 실행이 canonical Django settings만 소비하는지 검증합니다."""

    @override_settings(
        EMAIL_POP3_HOST="pop3.example.test",
        EMAIL_POP3_PORT=1110,
        EMAIL_POP3_USERNAME="user",
        EMAIL_POP3_PASSWORD="secret",
        EMAIL_POP3_USE_SSL=False,
        EMAIL_POP3_TIMEOUT=7,
    )
    @patch("api.emails.services.ingest.run_pop3_ingest")
    def test_run_pop3_ingest_uses_canonical_settings(self, mock_run: Mock) -> None:
        """legacy runtime env fallback 없이 설정 값을 그대로 전달합니다."""

        mock_run.return_value = {"deleted": 0, "reindexed": 0}

        result = run_pop3_ingest_from_settings()

        self.assertEqual(result, {"deleted": 0, "reindexed": 0})
        mock_run.assert_called_once_with(
            host="pop3.example.test",
            port=1110,
            username="user",
            password="secret",
            use_ssl=False,
            timeout=7,
        )


class EmailExcludedSubjectPatternTests(SimpleTestCase):
    """메일 제목 제외 pattern의 wildcard와 literal 규칙을 검증합니다."""

    def _is_excluded(self, subject: str, patterns: tuple[str, ...]) -> bool:
        """지정한 pattern만 적용해 제목 제외 여부를 검사합니다."""

        matchers = _compile_excluded_subject_patterns(patterns)
        with patch(
            "api.emails.services.ingest.EXCLUDED_SUBJECT_PATTERNS",
            matchers,
        ):
            return _is_excluded_subject(subject)

    def test_wildcard_matches_zero_or_more_characters(self) -> None:
        """`*`가 닫는 대괄호 전의 0글자 이상 문자열과 일치합니다."""

        patterns = ("[drone_sop*]", "[test]")

        self.assertTrue(self._is_excluded("[drone_sop] 알림", patterns))
        self.assertTrue(self._is_excluded("[drone_sop_v1] 알림", patterns))
        self.assertTrue(self._is_excluded("[drone_sop_v2] 알림", patterns))

    def test_match_is_case_insensitive_and_anchored_at_subject_start(self) -> None:
        """대소문자와 앞 공백은 정규화하고 제목 중간 일치는 허용하지 않습니다."""

        patterns = ("[drone_sop*]",)

        self.assertTrue(self._is_excluded("  [DRONE_SOP_V2] 알림", patterns))
        self.assertFalse(self._is_excluded("안내 [drone_sop_v2] 알림", patterns))

    def test_literal_prefix_keeps_existing_behavior(self) -> None:
        """wildcard가 없는 값은 기존 literal prefix 규칙을 유지합니다."""

        patterns = ("[test]",)

        self.assertTrue(self._is_excluded("[test] 알림", patterns))
        self.assertFalse(self._is_excluded("[testing] 알림", patterns))

    def test_regex_metacharacters_other_than_wildcard_are_literal(self) -> None:
        """점과 대괄호가 정규식 문법으로 해석되지 않는지 확인합니다."""

        patterns = ("[drone.sop*]",)

        self.assertTrue(self._is_excluded("[drone.sop_v1] 알림", patterns))
        self.assertFalse(self._is_excluded("[droneXsop_v1] 알림", patterns))


@override_settings(TIME_ZONE="Asia/Seoul")
class EmailQueryFilterTests(SimpleTestCase):
    """emails.services.query_filters의 날짜 파싱을 검증합니다."""

    def test_parse_datetime_value_naive_is_utc(self) -> None:
        """타임존 없는 문자열이 KST로 해석되어 UTC로 변환되는지 확인합니다."""

        parsed = parse_datetime_value("2025-01-01T10:00:00")

        self.assertIsNotNone(parsed)
        self.assertTrue(timezone.is_aware(parsed))
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.hour, 1)

    def test_parse_datetime_value_with_offset_converts_to_utc(self) -> None:
        """오프셋이 포함된 입력이 UTC 기준으로 변환되는지 확인합니다."""

        parsed = parse_datetime_value("2025-01-01T10:00:00+09:00")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.hour, 1)

    def test_parse_datetime_value_date_only_returns_midnight_utc(self) -> None:
        """날짜만 입력된 경우 KST 자정을 UTC로 변환하는지 확인합니다."""

        parsed = parse_datetime_value("2025-01-01")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 12)
        self.assertEqual(parsed.day, 31)
        self.assertEqual(parsed.hour, 15)
        self.assertEqual(parsed.minute, 0)

    def test_parse_datetime_value_accepts_datetime(self) -> None:
        """datetime 입력이 UTC timezone-aware로 변환되는지 확인합니다."""

        parsed = parse_datetime_value(datetime(2025, 1, 1, 10, 0, 0))

        self.assertIsNotNone(parsed)
        self.assertTrue(timezone.is_aware(parsed))
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.hour, 1)

    def test_parse_datetime_value_accepts_date(self) -> None:
        """date 입력이 UTC 자정으로 변환되는지 확인합니다."""

        parsed = parse_datetime_value(date(2025, 1, 1))

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 12)
        self.assertEqual(parsed.day, 31)
        self.assertEqual(parsed.hour, 15)
        self.assertEqual(parsed.minute, 0)

    def test_parse_datetime_value_date_only_end_boundary(self) -> None:
        """종료일 경계가 KST 기준 하루 끝으로 변환되는지 확인합니다."""

        parsed = parse_datetime_value("2025-01-01", boundary="end")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.tzinfo, UTC)
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        self.assertEqual(parsed.year, 2025)
        self.assertEqual(parsed.month, 1)
        self.assertEqual(parsed.day, 1)
        self.assertEqual(parsed.hour, 14)
        self.assertEqual(parsed.minute, 59)
        self.assertEqual(parsed.second, 59)
        self.assertEqual(parsed.microsecond, 999999)


class EmailAffiliationTests(TestCase):
    """emails.selectors / emails.services의 소속 판별/재분류 동작을 검증합니다."""

    def test_resolve_email_affiliation_uses_user_knox_id(self) -> None:
        """사용자 knox_id 기반 소속 판별이 우선 적용되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/소속 데이터 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S12345", password="test-password")
        user.knox_id = "loginid1"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        affiliation = resolve_email_affiliation(sender_id="loginid1", received_at=timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], "group-a")

    def test_resolve_email_affiliation_unknown_sender_defaults_to_unassigned(self) -> None:
        """미확인 발신자는 UNASSIGNED로 분류되는지 확인합니다.

        입력:
            없음.
        반환:
            없음.
        부작용:
            없음.
        오류:
            조건 불일치 시 assertion 실패.
        """

        affiliation = resolve_email_affiliation(sender_id="unknown-sender", received_at=timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], UNASSIGNED_USER_SDWT_PROD)

    def test_resolve_email_affiliation_uses_external_prediction(self) -> None:
        """외부 예측 소속이 있는 경우 해당 값을 사용하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 예측 스냅샷 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        account_services.sync_external_affiliations(
            records=[
                {
                    "knox_id": "loginid-ext",
                    "department": "Dept",
                    "user_sdwt_prod": "group-pred",
                    "source_updated_at": timezone.now(),
                }
            ]
        )

        affiliation = resolve_email_affiliation(sender_id="loginid-ext", received_at=timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], "group-pred")

    def test_resolve_email_affiliation_uses_current_user_sdwt_prod(self) -> None:
        """현재 user_sdwt_prod가 최우선으로 유지되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/변경 이력 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S77777", password="test-password")
        user.knox_id = "loginid3"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-old")

        # -------------------------------------------------------------------------
        # 1) 소속 옵션 및 변경 요청 준비
        # -------------------------------------------------------------------------
        effective_from = timezone.now()
        option = account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="group-new",
        )
        approver = User.objects.create_user(sabun="S77778", password="test-password")
        _set_current_affiliation(approver, user_sdwt_prod="group-new")
        account_services.ensure_self_access(approver, role="manager")
        payload, status_code = account_services.request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=effective_from,
            timezone_name="Asia/Seoul",
        )
        self.assertEqual(status_code, 202)

        # -------------------------------------------------------------------------
        # 2) 승인 권한 보장 및 승인 처리
        # -------------------------------------------------------------------------
        approve_payload, approve_status = account_services.approve_affiliation_change(
            approver=approver,
            change_id=payload["changeId"],
        )
        self.assertEqual(approve_status, 200)
        self.assertEqual(approve_payload.get("status"), "approved")

        before = resolve_email_affiliation(sender_id="loginid3", received_at=effective_from - timedelta(hours=1))
        self.assertEqual(before["user_sdwt_prod"], "group-new")

        after = resolve_email_affiliation(sender_id="loginid3", received_at=effective_from + timedelta(hours=1))
        self.assertEqual(after["user_sdwt_prod"], "group-new")


class EmailMoveServiceTests(TestCase):
    """emails.services 이동/삭제 관련 동작을 검증합니다."""

    def setUp(self) -> None:
        """메일 이동 대상에 사용할 활성 정규 소속을 준비합니다."""

        for user_sdwt_prod in ("group-a", "group-b", "group-new"):
            account_services.ensure_affiliation_option(
                department="Dept",
                line="Line",
                user_sdwt_prod=user_sdwt_prod,
            )

    @patch("api.emails.services.insert_email_to_rag")
    def test_enqueue_rag_index_for_emails_reports_missing_ids(self, _mock_insert: Mock) -> None:
        """존재하지 않는 id가 ragMissing으로 집계되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="rag-missing-msg",
            received_at=timezone.now(),
            subject="Missing",
            sender="missing@example.com",
            sender_id="loginid-missing",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
            body_text="Body",
        )

        result = enqueue_rag_index_for_emails(
            email_ids=[email.id, 999999],
            target_user_sdwt_prod="group-a",
            previous_user_sdwt_prod_by_email_id=None,
        )

        self.assertEqual(result["ragRegistered"], 1)
        self.assertEqual(result["ragMissing"], 1)
        self.assertEqual(result["ragFailed"], 0)
        self.assertEqual(EmailOutbox.objects.count(), 0)

    @patch("api.emails.services.insert_email_to_rag")
    def test_move_emails_to_user_sdwt_prod_updates_rows(self, _mock_insert: Mock) -> None:
        """메일함 이동 시 user_sdwt_prod가 갱신되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성/수정.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email_a = Email.objects.create(
            message_id="move-msg-a",
            received_at=timezone.now(),
            subject="A",
            sender="a@example.com",
            sender_id="loginid-move",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body A",
        )
        email_b = Email.objects.create(
            message_id="move-msg-b",
            received_at=timezone.now(),
            subject="B",
            sender="a@example.com",
            sender_id="loginid-move",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body B",
        )

        result = move_emails_to_user_sdwt_prod(
            email_ids=[email_a.id, email_b.id],
            to_user_sdwt_prod="group-new",
        )
        self.assertEqual(result["moved"], 2)

        email_a.refresh_from_db()
        email_b.refresh_from_db()
        self.assertEqual(email_a.user_sdwt_prod, "group-new")
        self.assertEqual(email_b.user_sdwt_prod, "group-new")
        self.assertTrue(bool(email_a.rag_doc_id))

    @patch("api.emails.services.insert_email_to_rag")
    def test_move_emails_to_user_sdwt_prod_reports_missing_ids(self, _mock_insert: Mock) -> None:
        """존재하지 않는 id가 ragMissing으로 집계되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성/수정.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="move-missing-msg",
            received_at=timezone.now(),
            subject="Missing",
            sender="missing@example.com",
            sender_id="loginid-move-missing",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        result = move_emails_to_user_sdwt_prod(
            email_ids=[email.id, 999999],
            to_user_sdwt_prod="group-b",
        )

        self.assertEqual(result["moved"], 1)
        self.assertEqual(result["ragRegistered"], 1)
        self.assertEqual(result["ragMissing"], 1)
        self.assertEqual(result["ragFailed"], 0)

        email.refresh_from_db()
        self.assertEqual(email.user_sdwt_prod, "group-b")

    def test_move_rechecks_latest_data_scope_instead_of_request_snapshot(self) -> None:
        """요청 초기에 허용됐어도 최신 앱 범위가 차단되면 메일을 이동하지 않아야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S-MOVE-SNAPSHOT",
            password="test-password",
        )
        email = Email.objects.create(
            message_id="move-stale-scope",
            received_at=timezone.now(),
            subject="Stale scope",
            sender="sender@example.com",
            sender_id="move-snapshot",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        with patch(
            "api.emails.services.mutations.account_services.get_affiliation_scope_decision",
            return_value={"allowed": False, "userSdwtProds": [], "all": False},
        ) as resolve_scope:
            with self.assertRaises(PermissionError):
                move_emails_to_user_sdwt_prod(
                    email_ids=[email.id],
                    to_user_sdwt_prod="group-b",
                    user=user,
                    is_privileged=True,
                    accessible_user_sdwt_prods={"group-a", "group-b"},
                )

        resolve_scope.assert_called_once()
        email.refresh_from_db()
        self.assertEqual(email.user_sdwt_prod, "group-a")

    @patch("api.emails.services.insert_email_to_rag")
    def test_move_uses_canonical_active_affiliation_identifier(self, _mock_insert: Mock) -> None:
        """메일 목적지는 입력 문자열이 아니라 활성 Affiliation의 정규 값을 저장해야 합니다."""

        canonical = account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="Canonical-Group",
        )
        email = Email.objects.create(
            message_id="move-canonical-target",
            received_at=timezone.now(),
            subject="Canonical target",
            sender="sender@example.com",
            sender_id="move-canonical",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        result = move_emails_to_user_sdwt_prod(
            email_ids=[email.id],
            to_user_sdwt_prod="canonical-group",
        )

        self.assertEqual(result["moved"], 1)
        email.refresh_from_db()
        self.assertEqual(email.user_sdwt_prod, canonical.user_sdwt_prod)

    def test_move_rejects_missing_or_inactive_target_affiliation(self) -> None:
        """존재하지 않거나 비활성인 소속으로 메일을 이동할 수 없어야 합니다."""

        inactive = account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="inactive-mail-target",
        )
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        email = Email.objects.create(
            message_id="move-invalid-target",
            received_at=timezone.now(),
            subject="Invalid target",
            sender="sender@example.com",
            sender_id="move-invalid",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        for target in ("missing-mail-target", inactive.user_sdwt_prod):
            with self.subTest(target=target):
                with self.assertRaisesRegex(
                    ValueError,
                    "Target affiliation must be active",
                ):
                    move_emails_to_user_sdwt_prod(
                        email_ids=[email.id],
                        to_user_sdwt_prod=target,
                    )

    @patch("api.emails.services.insert_email_to_rag")
    def test_move_sender_emails_after_filters_by_time(self, _mock_insert: Mock) -> None:
        """기준 시각 이후 메일만 이동되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성/수정.
        오류:
            조건 불일치 시 assertion 실패.
        """

        sender_id = "loginid-time"
        old = Email.objects.create(
            message_id="move-time-old",
            received_at=timezone.now() - timedelta(days=2),
            subject="Old",
            sender="a@example.com",
            sender_id=sender_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body Old",
        )
        new = Email.objects.create(
            message_id="move-time-new",
            received_at=timezone.now() - timedelta(hours=1),
            subject="New",
            sender="a@example.com",
            sender_id=sender_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body New",
        )

        cutoff = timezone.now() - timedelta(days=1)
        result = move_sender_emails_after(
            sender_id=sender_id,
            received_at_gte=cutoff,
            to_user_sdwt_prod="group-b",
        )
        self.assertEqual(result["moved"], 1)

        old.refresh_from_db()
        new.refresh_from_db()
        self.assertEqual(old.user_sdwt_prod, "group-a")
        self.assertEqual(new.user_sdwt_prod, "group-b")

    @patch("api.emails.services.insert_email_to_rag")
    def test_claim_unassigned_emails_for_user_includes_missing_count(self, _mock_insert: Mock) -> None:
        """UNASSIGNED 메일 귀속 결과 집계가 올바른지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S22222", password="test-password")
        user.knox_id = "loginid-claim"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-claim")

        Email.objects.create(
            message_id="claim-msg-a",
            received_at=timezone.now(),
            subject="Claim",
            sender="claim@example.com",
            sender_id="loginid-claim",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body",
        )

        result = claim_unassigned_emails_for_user(user=user)

        self.assertEqual(result["moved"], 1)
        self.assertEqual(result["ragRegistered"], 1)
        self.assertEqual(result["ragMissing"], 0)
        self.assertEqual(result["ragFailed"], 0)

    def test_claim_rejects_inactive_current_affiliation(self) -> None:
        """현재 소속이 비활성화되면 UNASSIGNED 메일을 귀속할 수 없어야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S-CLAIM-INACTIVE",
            password="test-password",
            knox_id="claim-inactive",
        )
        _set_current_affiliation(
            user,
            user_sdwt_prod="claim-inactive-group",
        )
        current = account_services.get_affiliation_overview(
            user=user,
            timezone_name="Asia/Seoul",
        )
        affiliation = account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod=current["currentUserSdwtProd"],
        )
        affiliation.is_active = False
        affiliation.save(update_fields=["is_active"])

        with self.assertRaisesRegex(
            ValueError,
            "user_sdwt_prod must be set",
        ):
            claim_unassigned_emails_for_user(user=user)


class EmailOutboxTests(TestCase):
    """emails.services RAG Outbox 처리 동작을 검증합니다."""

    @patch("api.emails.services.insert_email_to_rag")
    def test_process_outbox_index_updates_email(self, mock_insert: Mock) -> None:
        """Outbox 인덱싱 처리 후 상태가 업데이트되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email/Outbox 생성 및 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="outbox-msg-1",
            received_at=timezone.now(),
            subject="Outbox",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.PENDING,
            body_text="Body",
        )

        enqueue_rag_index(email=email)

        result = process_email_outbox_batch(limit=10)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["succeeded"], 1)

        email.refresh_from_db()
        outbox_item = EmailOutbox.objects.get()
        self.assertEqual(outbox_item.status, EmailOutbox.Status.DONE)
        self.assertEqual(email.rag_index_status, Email.RagIndexStatus.INDEXED)
        self.assertTrue(bool(email.rag_doc_id))
        mock_insert.assert_called_once()
        args, kwargs = mock_insert.call_args
        self.assertEqual(args[0].id, email.id)
        self.assertEqual(kwargs.get("index_name"), resolve_rag_index_name(RAG_INDEX_EMAILS))
        self.assertEqual(kwargs.get("permission_groups"), ["group-a", "sender"])

    @patch("api.emails.services.delete_rag_doc")
    @patch("api.emails.services.mutations.delete_email_objects")
    def test_delete_email_enqueues_outbox(self, _mock_delete_objects: Mock, mock_delete: Mock) -> None:
        """삭제 시 Outbox가 적재되고 처리되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email/Outbox 생성 및 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="outbox-msg-2",
            received_at=timezone.now(),
            subject="Delete",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            rag_doc_id="email-outbox-2",
            body_text="Body",
        )

        delete_single_email(email.id)

        self.assertFalse(Email.objects.filter(id=email.id).exists())
        outbox_item = EmailOutbox.objects.get(action=EmailOutbox.Action.DELETE)
        self.assertEqual(outbox_item.payload.get("rag_doc_id"), "email-outbox-2")

        process_email_outbox_batch(limit=10)

        outbox_item.refresh_from_db()
        self.assertEqual(outbox_item.status, EmailOutbox.Status.DONE)
        mock_delete.assert_called_once_with(
            "email-outbox-2",
            index_name=resolve_rag_index_name(RAG_INDEX_EMAILS),
            permission_groups=["group-a", "sender"],
        )


class EmailAssistantScopeSelectorTests(TestCase):
    """ChatWidget Email 현재 화면 범위의 서버 재검증을 확인합니다."""

    def setUp(self) -> None:
        """단일 메일함 사용자와 서로 다른 범위의 메일을 준비합니다."""

        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(sabun="S11880", password="test-password")
        self.user.knox_id = "knox-11880"
        self.user.save(update_fields=["knox_id"])
        _set_current_affiliation(self.user, user_sdwt_prod="group-a")
        self.own_mail = Email.objects.create(
            message_id="assistant-scope-own",
            received_at=timezone.now(),
            subject="내 메일",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="본문",
            rag_doc_id="rag-own",
        )
        self.other_mail = Email.objects.create(
            message_id="assistant-scope-other",
            received_at=timezone.now(),
            subject="다른 메일함",
            sender="other@example.com",
            sender_id="other",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="본문",
            rag_doc_id="rag-other",
        )
        self.sent_mail = Email.objects.create(
            message_id="assistant-scope-sent",
            received_at=timezone.now(),
            subject="보낸 메일",
            sender="me@example.com",
            sender_id="knox-11880",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="본문",
            rag_doc_id="rag-sent",
        )

    def test_scope_accepts_only_matching_accessible_mailbox_and_email(self) -> None:
        """접근 가능한 현재 메일함에 실제로 속한 메일만 RAG ID로 정규화합니다."""

        resolved = resolve_assistant_email_scope(
            user=self.user,
            mailbox="group-a",
            email_id=self.own_mail.id,
        )
        wrong_mailbox = resolve_assistant_email_scope(
            user=self.user,
            mailbox="group-b",
            email_id=self.other_mail.id,
        )
        mismatched_email = resolve_assistant_email_scope(
            user=self.user,
            mailbox="group-a",
            email_id=self.other_mail.id,
        )

        self.assertEqual(resolved, {"mailbox": "group-a", "emailId": "rag-own"})
        self.assertIsNone(wrong_mailbox)
        self.assertIsNone(mismatched_email)

    def test_sent_scope_requires_current_user_as_sender(self) -> None:
        """보낸 메일함은 현재 사용자가 실제 발신자인 선택 메일만 허용합니다."""

        resolved = resolve_assistant_email_scope(
            user=self.user,
            mailbox="sent",
            email_id=self.sent_mail.id,
        )
        denied = resolve_assistant_email_scope(
            user=self.user,
            mailbox="sent",
            email_id=self.other_mail.id,
        )
        missing_selection = resolve_assistant_email_scope(
            user=self.user,
            mailbox="sent",
        )

        self.assertEqual(resolved, {"mailbox": "group-b", "emailId": "rag-sent"})
        self.assertIsNone(denied)
        self.assertIsNone(missing_selection)



class RagIndexNameTests(SimpleTestCase):
    """RAG 인덱스 이름 해석 규칙을 검증합니다."""

    def test_resolve_rag_index_name_returns_explicit_value(self) -> None:
        """명시 값이 있으면 그대로 반환하는지 확인합니다.

        입력:
            없음.
        반환:
            없음.
        부작용:
            없음.
        오류:
            조건 불일치 시 assertion 실패.
        """

        self.assertEqual(resolve_rag_index_name("rp-emails"), "rp-emails")

    def test_resolve_rag_index_name_falls_back_to_default(self) -> None:
        """기본 인덱스로 폴백하는지 확인합니다.

        입력:
            없음(설정 패치).
        반환:
            없음.
        부작용:
            모듈 상수 패치.
        오류:
            조건 불일치 시 assertion 실패.
        """

        with patch("api.rag.services.RAG_INDEX_DEFAULT", "rp-unclassified"):
            self.assertEqual(resolve_rag_index_name(None), "rp-unclassified")

    def test_resolve_rag_index_name_uses_first_index_list_when_default_missing(self) -> None:
        """기본값이 없으면 목록 첫 항목으로 폴백하는지 확인합니다.

        입력:
            없음(설정 패치).
        반환:
            없음.
        부작용:
            모듈 상수 패치.
        오류:
            조건 불일치 시 assertion 실패.
        """

        with patch("api.rag.services.RAG_INDEX_DEFAULT", ""), patch(
            "api.rag.services.RAG_INDEX_LIST", ["rp-a", "rp-b"]
        ):
            self.assertEqual(resolve_rag_index_name(None), "rp-a")


class EmailParsingTests(SimpleTestCase):
    """메일 파싱 유틸 동작을 검증합니다."""

    def test_parse_message_to_fields_includes_cc_and_recipient_lists(self) -> None:
        """To/Cc가 리스트로 파싱되는지 확인합니다.

        입력:
            없음(테스트 메시지 생성).
        반환:
            없음.
        부작용:
            없음.
        오류:
            조건 불일치 시 assertion 실패.
        """

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg["From"] = "Sender <sender@example.com>"
        msg["To"] = "Jane <jane@x.com>, Bob <bob@y.com>"
        msg["Cc"] = "Team <team@corp.com>"
        msg["Date"] = "Mon, 01 Jan 2024 00:00:00 +0000"
        msg["Message-ID"] = "<msg-parse-1>"
        msg.set_content("Hello")

        fields = _parse_message_to_fields(msg)

        self.assertEqual(fields["recipient"], ["Jane <jane@x.com>", "Bob <bob@y.com>"])
        self.assertEqual(fields["cc"], ["Team <team@corp.com>"])

    def test_parse_message_to_fields_strips_signature_elements_from_html(self) -> None:
        """HTML 본문에서 제외 대상 서명 요소가 제거되는지 확인합니다.

        입력:
            없음(HTML 메시지 생성).
        반환:
            없음.
        부작용:
            없음.
        오류:
            조건 불일치 시 assertion 실패.
        """

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg["From"] = "Sender <sender@example.com>"
        msg["To"] = "Receiver <receiver@example.com>"
        msg["Date"] = "Mon, 01 Jan 2024 00:00:00 +0000"
        msg["Message-ID"] = "<msg-parse-html-1>"
        msg.set_content("Plain")

        html = (
            "<html><body>"
            "<p>Hello</p>"
            "<img id='standardSignature' src='cid:sig'>"
            "<table id='bannersignImg'><tr><td>Banner</td></tr></table>"
            "<table id='confidentialsignimg'><tr><td>Confidential</td></tr></table>"
            "<p>Bye</p>"
            "</body></html>"
        )
        msg.add_alternative(html, subtype="html")

        fields = _parse_message_to_fields(msg)

        self.assertIn("Hello", fields["body_text"])
        self.assertIn("Bye", fields["body_text"])
        self.assertNotIn("Banner", fields["body_text"])
        self.assertNotIn("Confidential", fields["body_text"])
        self.assertNotIn("standardSignature", fields["body_html"])
        self.assertNotIn("bannersignImg", fields["body_html"])
        self.assertNotIn("confidentialsignimg", fields["body_html"])

    def test_parse_message_to_fields_strips_signature_markers_from_text(self) -> None:
        """텍스트 본문에서 제외 대상 서명 마커가 제거되는지 확인합니다.

        입력:
            없음(텍스트 메시지 생성).
        반환:
            없음.
        부작용:
            없음.
        오류:
            조건 불일치 시 assertion 실패.
        """

        msg = EmailMessage()
        msg["Subject"] = "Test"
        msg["From"] = "Sender <sender@example.com>"
        msg["To"] = "Receiver <receiver@example.com>"
        msg["Date"] = "Mon, 01 Jan 2024 00:00:00 +0000"
        msg["Message-ID"] = "<msg-parse-text-1>"
        msg.set_content(
            "Hello\n"
            "<img id='standardSignature'>\n"
            "Keep\n"
            "<table id=\"bannersignImg\"></table>\n"
            "<table id=\"confidentialsignimg\"></table>\n"
            "Bye\n"
        )

        fields = _parse_message_to_fields(msg)
        lowered = fields["body_text"].lower()

        self.assertIn("Hello", fields["body_text"])
        self.assertIn("Bye", fields["body_text"])
        self.assertIn("Keep", fields["body_text"])
        self.assertNotIn("standardsignature", lowered)
        self.assertNotIn("bannersignimg", lowered)
        self.assertNotIn("confidentialsignimg", lowered)


class EmailSearchSelectorTests(TestCase):
    """메일 검색 필터 동작을 검증합니다."""

    def test_get_filtered_emails_search_includes_to_and_cc(self) -> None:
        """검색이 To/Cc에도 적용되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        Email.objects.create(
            message_id="search-1",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["Jane <jane@x.com>"],
            cc=["Team <team@corp.com>"],
            participants_search="jane <jane@x.com>\nteam <team@corp.com>",
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        Email.objects.create(
            message_id="search-2",
            received_at=timezone.now(),
            subject="Other",
            sender="other@example.com",
            sender_id="other",
            recipient=["Alice <alice@z.com>"],
            participants_search="alice <alice@z.com>",
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        by_name = get_filtered_emails(
            accessible_user_sdwt_prods=set(),
            is_privileged=True,
            can_view_unassigned=True,
            mailbox_user_sdwt_prod="",
            search="JANE",
            sender="",
            recipient="",
            date_from=None,
            date_to=None,
        )
        self.assertEqual(set(by_name.values_list("message_id", flat=True)), {"search-1"})

        by_cc = get_filtered_emails(
            accessible_user_sdwt_prods=set(),
            is_privileged=True,
            can_view_unassigned=True,
            mailbox_user_sdwt_prod="",
            search="",
            sender="",
            recipient="TEAM@corp.com",
            date_from=None,
            date_to=None,
        )
        self.assertEqual(set(by_cc.values_list("message_id", flat=True)), {"search-1"})

    def test_get_filtered_emails_returns_none_for_empty_accessible_set(self) -> None:
        """접근 가능 집합이 비어 있으면 결과가 없는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        Email.objects.create(
            message_id="search-guard-1",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        results = get_filtered_emails(
            accessible_user_sdwt_prods=set(),
            is_privileged=False,
            can_view_unassigned=False,
            mailbox_user_sdwt_prod="",
            search="",
            sender="",
            recipient="",
            date_from=None,
            date_to=None,
        )
        self.assertEqual(results.count(), 0)
