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
    store_email_html_and_assets,
)
from api.emails.services.ingest import _LongLinePOP3, _iter_pop3_messages
from api.rag.services import RAG_INDEX_EMAILS, resolve_rag_index_name

UTC = getattr(timezone, "utc", dt_timezone.utc)

from api.emails.tests import (
    _allow_test_scope_access,
    _grant_emails_admin,
    _grant_emails_affiliation_data,
    _set_current_affiliation,
)

class EmailEndpointTests(TestCase):
    """emails API 엔드포인트의 기본 동작을 검증합니다."""

    def setUp(self) -> None:
        """공통 테스트 데이터와 로그인 상태를 준비합니다.

        입력:
            없음.
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성, 클라이언트 로그인.
        오류:
            없음.
        """

        _allow_test_scope_access(self)
        User = get_user_model()
        self.user = User.objects.create_user(sabun="S11111", password="test-password")
        self.user.knox_id = "knox-11111"
        self.user.save(update_fields=["knox_id"])
        _set_current_affiliation(self.user, user_sdwt_prod="group-a")

        self.email = Email.objects.create(
            message_id="msg-111",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="knox-11111",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
            body_html_object_key="html/1.html",
        )
        Email.objects.create(
            message_id="msg-unassigned",
            received_at=timezone.now(),
            subject="Unassigned",
            sender="sender@example.com",
            sender_id="knox-11111",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body",
        )

        self.client.force_login(self.user)

    def test_email_list_detail_html_and_delete(self) -> None:
        """목록/상세/HTML/삭제 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(사전 데이터 사용).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청 및 DB 삭제.
        오류:
            조건 불일치 시 assertion 실패.
        """

        with patch("api.emails.views.content.load_email_html", return_value=b"<html>body</html>"), patch(
            "api.emails.services.mutations.delete_email_objects"
        ):
            list_response = self.client.get(reverse("emails-inbox"))
            self.assertEqual(list_response.status_code, 200)

            detail_response = self.client.get(reverse("emails-detail", kwargs={"email_id": self.email.id}))
            self.assertEqual(detail_response.status_code, 200)

            html_response = self.client.get(reverse("emails-html", kwargs={"email_id": self.email.id}))
            self.assertEqual(html_response.status_code, 200)
            self.assertIn("<html>", html_response.content.decode("utf-8"))

            account_services.ensure_self_access(self.user, role="manager")
            delete_response = self.client.delete(reverse("emails-detail", kwargs={"email_id": self.email.id}))
            self.assertEqual(delete_response.status_code, 200)

    def test_email_asset_endpoint(self) -> None:
        """이미지 자산 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(사전 데이터 사용).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        EmailAsset.objects.create(
            email=self.email,
            sequence=1,
            object_key="assets/1/1.png",
            content_type="image/png",
            source=EmailAsset.Source.CID,
        )

        with patch("api.emails.views.content.load_email_asset", return_value=b"png-data"):
            response = self.client.get(
                reverse("emails-asset", kwargs={"email_id": self.email.id, "sequence": 1})
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")

    def test_member_cannot_delete_single_or_bulk_email(self) -> None:
        """현재 소속 member는 단일·대량 삭제를 수행할 수 없습니다."""

        bulk_email = Email.objects.create(
            message_id="msg-member-delete",
            received_at=timezone.now(),
            subject="Member delete",
            sender="sender@example.com",
            sender_id="knox-11111",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        single_response = self.client.delete(
            reverse("emails-detail", kwargs={"email_id": self.email.id})
        )
        bulk_response = self.client.post(
            reverse("emails-bulk-delete"),
            data='{"emailIds":[%d]}' % bulk_email.id,
            content_type="application/json",
        )

        self.assertEqual(single_response.status_code, 403)
        self.assertEqual(bulk_response.status_code, 403)
        self.assertTrue(Email.objects.filter(id=self.email.id).exists())
        self.assertTrue(Email.objects.filter(id=bulk_email.id).exists())

    def test_email_sent_list(self) -> None:
        """보낸메일 목록 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(사전 데이터 사용).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        sent_response = self.client.get(reverse("emails-sent"))
        self.assertEqual(sent_response.status_code, 200)
        results = sent_response.json()["results"]
        self.assertTrue(any(item["id"] == self.email.id for item in results))

    def test_email_mailboxes_and_members(self) -> None:
        """메일함 목록/멤버 조회가 정상 동작하는지 확인합니다.

        입력:
            없음(사전 데이터 사용).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        manager = User.objects.create_user(sabun="S11112", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=self.user,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        self.assertEqual(status_code, 200)
        _grant_emails_affiliation_data(
            user=self.user,
            user_sdwt_prods=("group-b",),
        )

        mailbox_response = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_response.status_code, 200)

        summary_response = self.client.get(reverse("emails-mailbox-summary"))
        self.assertEqual(summary_response.status_code, 200)
        summary_rows = summary_response.json()["results"]
        self.assertIn("group-a", {row["userSdwtProd"] for row in summary_rows})
        summary_by_mailbox = {row["userSdwtProd"]: row for row in summary_rows}
        self.assertEqual(summary_by_mailbox["group-a"]["accessSource"], "self")
        self.assertEqual(summary_by_mailbox["group-b"]["accessSource"], "grant")

        members_response = self.client.get(
            reverse("emails-mailbox-members"),
            {"userSdwtProd": "group-a"},
        )
        self.assertEqual(members_response.status_code, 200)

    def test_email_unassigned_summary_and_claim(self) -> None:
        """UNASSIGNED 요약/귀속 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(사전 데이터 사용).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청 및 DB 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        summary = self.client.get(reverse("emails-unassigned-summary"))
        self.assertEqual(summary.status_code, 200)

        claim = self.client.post(reverse("emails-unassigned-claim"))
        self.assertEqual(claim.status_code, 200)

    def test_email_bulk_delete(self) -> None:
        """일괄 삭제 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성 및 삭제.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="msg-bulk",
            received_at=timezone.now(),
            subject="Bulk",
            sender="sender@example.com",
            sender_id="knox-11111",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        account_services.ensure_self_access(self.user, role="manager")
        with patch("api.emails.services.mutations.delete_email_objects"):
            response = self.client.post(
                reverse("emails-bulk-delete"),
                data='{"emailIds":[%d]}' % email.id,
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

    def test_email_write_validation_error_contract(self) -> None:
        """일괄 삭제와 이동 입력 오류가 기존 응답 계약을 유지하는지 확인합니다."""

        bulk_response = self.client.post(
            reverse("emails-bulk-delete"),
            data='{"emailIds":[]}',
            content_type="application/json",
        )
        move_response = self.client.post(
            reverse("emails-move"),
            data='{"emailIds":[1]}',
            content_type="application/json",
        )

        self.assertEqual(bulk_response.status_code, 400)
        self.assertEqual(
            bulk_response.json(),
            {
                "code": "invalid_request",
                "message": "emailIds must be a non-empty list",
                "details": {"reason": "emailIds must be a non-empty list"},
                "fieldErrors": {},
            },
        )
        self.assertEqual(move_response.status_code, 400)
        self.assertEqual(
            move_response.json(),
            {
                "code": "invalid_request",
                "message": "toUserSdwtProd is required",
                "details": {"reason": "toUserSdwtProd is required"},
                "fieldErrors": {},
            },
        )

    @patch("api.emails.services.insert_email_to_rag")
    def test_email_move_endpoint(self, _mock_insert: Mock) -> None:
        """메일 이동 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성/수정.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        manager = User.objects.create_user(sabun="S77779", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=self.user,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        self.assertEqual(status_code, 200)
        _grant_emails_affiliation_data(
            user=self.user,
            user_sdwt_prods=("group-b",),
        )

        email = Email.objects.create(
            message_id="msg-move",
            received_at=timezone.now(),
            subject="Move",
            sender="sender@example.com",
            sender_id="knox-11111",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        response = self.client.post(
            reverse("emails-move"),
            data='{"emailIds":[%d],"toUserSdwtProd":"group-b"}' % email.id,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        email.refresh_from_db()
        self.assertEqual(email.user_sdwt_prod, "group-b")

    @patch("api.emails.services.insert_email_to_rag")
    def test_viewer_cannot_move_email(self, _mock_insert: Mock) -> None:
        """추가 소속 viewer는 source와 target을 조회해도 메일을 이동할 수 없습니다."""

        User = get_user_model()
        manager = User.objects.create_user(
            sabun="S77780",
            password="test-password",
            knox_id="knox-77780",
        )
        viewer = User.objects.create_user(
            sabun="S77781",
            password="test-password",
            knox_id="knox-77781",
        )
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        _set_current_affiliation(viewer, user_sdwt_prod="group-c")
        account_services.ensure_self_access(self.user, role="manager")
        account_services.ensure_self_access(manager, role="manager")
        for group in ("group-a", "group-b"):
            _, status_code = account_services.grant_or_revoke_access(
                grantor=manager if group == "group-b" else self.user,
                target_group=group,
                target_user=viewer,
                action="grant",
                role="viewer",
                reason="테스트 권한 변경",
            )
            self.assertEqual(status_code, 200)
        _grant_emails_affiliation_data(
            user=viewer,
            user_sdwt_prods=("group-a", "group-b"),
        )

        email = Email.objects.create(
            message_id="msg-viewer-move",
            received_at=timezone.now(),
            subject="Viewer move",
            sender="viewer@example.com",
            sender_id="knox-77781",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        self.client.force_login(viewer)

        response = self.client.post(
            reverse("emails-move"),
            data='{"emailIds":[%d],"toUserSdwtProd":"group-b"}' % email.id,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        email.refresh_from_db()
        self.assertEqual(email.user_sdwt_prod, "group-a")

    @patch("api.emails.views.triggers.run_pop3_ingest_from_settings", return_value={"deleted": 1, "reindexed": 2})
    def test_email_ingest_trigger(self, _mock_ingest) -> None:
        """POP3 수집 트리거 엔드포인트가 정상 동작하는지 확인합니다.

        입력:
            없음(서비스 모킹).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        response = self.client.post(reverse("emails-ingest"))
        self.assertEqual(response.status_code, 200)


class EmailAssetOcrClaimViewTests(TestCase):
    """OCR 작업 클레임 엔드포인트 동작을 검증합니다."""

    @override_settings(
        EMAIL_OCR_INTERNAL_TOKEN="expected-token",
        EMAIL_OCR_CLAIM_LIMIT=50,
        EMAIL_OCR_LEASE_SECONDS=1800,
        EMAIL_OCR_MAX_ATTEMPTS=3,
    )
    def test_ocr_claim_assigns_lock(self) -> None:
        """OCR 클레임 시 자산 락이 부여되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            EmailAsset OCR 상태/락 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="ocr-claim-1",
            received_at=timezone.now(),
            subject="OCR Claim",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.INDEXED,
            body_text="Body",
        )
        asset = EmailAsset.objects.create(
            email=email,
            sequence=1,
            object_key="assets/1/1.png",
            content_type="image/png",
            source=EmailAsset.Source.CID,
        )

        response = self.client.post(
            reverse("emails-assets-ocr-claim"),
            data="{}",
            content_type="application/json",
            HTTP_X_INTERNAL_TOKEN="expected-token",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload.get("tasks", [])), 1)
        self.assertEqual(payload["tasks"][0]["asset_id"], asset.id)

        asset.refresh_from_db()
        self.assertEqual(asset.ocr_status, EmailAsset.OcrStatus.PROCESSING)
        self.assertIsNotNone(asset.ocr_lock_token)
        self.assertIsNotNone(asset.ocr_lock_expires_at)
        self.assertEqual(asset.ocr_attempt_count, 1)


class EmailAssetOcrUpdateViewTests(TestCase):
    """OCR 결과 업데이트 엔드포인트 동작을 검증합니다."""

    @override_settings(EMAIL_OCR_INTERNAL_TOKEN="expected-token", EMAIL_OCR_MAX_ATTEMPTS=3)
    def test_ocr_update_enqueues_rag(self) -> None:
        """OCR 결과가 반영되고 RAG 재인덱싱이 요청되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            EmailAsset/Outbox 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="ocr-msg-1",
            received_at=timezone.now(),
            subject="OCR",
            sender="sender@example.com",
            sender_id="sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.INDEXED,
            body_text="Body",
        )
        asset = EmailAsset.objects.create(
            email=email,
            sequence=1,
            object_key="assets/1/1.png",
            content_type="image/png",
            source=EmailAsset.Source.CID,
            ocr_status=EmailAsset.OcrStatus.PROCESSING,
            ocr_lock_token="lock-token",
            ocr_lock_expires_at=timezone.now() + timedelta(minutes=30),
            ocr_attempt_count=1,
        )

        response = self.client.post(
            reverse("emails-assets-ocr-update"),
            data='{"results":[{"asset_id":%d,"lock_token":"lock-token","status":"DONE","text":"ocr-text"}]}'
            % asset.id,
            content_type="application/json",
            HTTP_X_INTERNAL_TOKEN="expected-token",
        )
        self.assertEqual(response.status_code, 200)

        asset.refresh_from_db()
        self.assertEqual(asset.ocr_status, EmailAsset.OcrStatus.DONE)
        self.assertEqual(asset.ocr_text, "ocr-text")
        self.assertEqual(EmailOutbox.objects.filter(action=EmailOutbox.Action.INDEX).count(), 1)


class EmailOutboxTriggerAuthTests(TestCase):
    """Outbox 트리거 인증/파라미터 동작을 검증합니다."""

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.emails.views.triggers.process_email_outbox_batch")
    def test_outbox_trigger_requires_token(self, mock_process: Mock) -> None:
        """토큰 인증이 필수로 적용되는지 확인합니다.

        입력:
            없음(토큰/서비스 모킹).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        mock_process.return_value = {"processed": 1, "succeeded": 1, "failed": 0}

        url = reverse("emails-outbox-process")

        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_process.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer wrong-token")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(mock_process.call_count, 0)

        resp = self.client.post(url, HTTP_AUTHORIZATION="Bearer expected-token")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("processed"), 1)
        mock_process.assert_called_once_with()

    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.emails.views.triggers.process_email_outbox_batch")
    def test_outbox_trigger_accepts_limit(self, mock_process: Mock) -> None:
        """limit 파라미터가 전달되는지 확인합니다.

        입력:
            없음(토큰/서비스 모킹).
        반환:
            없음.
        부작용:
            테스트 클라이언트 요청.
        오류:
            조건 불일치 시 assertion 실패.
        """

        mock_process.return_value = {"processed": 0, "succeeded": 0, "failed": 0}

        url = reverse("emails-outbox-process")

        resp = self.client.post(
            url,
            data='{"limit": 123}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer expected-token",
        )
        self.assertEqual(resp.status_code, 200)
        mock_process.assert_called_once_with(limit=123)


class EmailHtmlStorageTests(TestCase):
    """HTML/이미지 자산 저장 규칙을 검증합니다."""

    @patch("api.emails.services.storage.upload_bytes")
    def test_store_email_html_preserves_external_urls(self, mock_upload: Mock) -> None:
        """외부 URL 이미지는 원문 유지되고 자산으로 기록되는지 확인합니다.

        입력:
            없음(테스트 Email/HTML 준비).
        반환:
            없음.
        부작용:
            테스트 DB에 Email/EmailAsset 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="msg-html-1",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="knox-html-1",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        external_url = "https://example.com/external.png"
        payload = base64.b64encode(b"image-bytes").decode("ascii")
        body_html = (
            f"<html><body><img src=\"{external_url}\" />"
            f"<img src=\"data:image/png;base64,{payload}\" /></body></html>"
        )

        store_email_html_and_assets(email=email, body_html=body_html, cid_map={})

        html_uploads = [
            call.kwargs
            for call in mock_upload.call_args_list
            if str(call.kwargs.get("content_type", "")).startswith("text/html")
        ]
        self.assertEqual(len(html_uploads), 1)
        uploaded_html = html_uploads[0]["data"].decode("utf-8")
        self.assertIn(external_url, uploaded_html)
        self.assertIn(f"/api/v1/emails/{email.id}/assets/", uploaded_html)
        self.assertNotIn("data:image/png;base64", uploaded_html)

        external_asset = EmailAsset.objects.get(email=email, source=EmailAsset.Source.EXTERNAL_URL)
        self.assertEqual(external_asset.original_url, external_url)
        self.assertIsNone(external_asset.object_key)

        data_asset = EmailAsset.objects.get(email=email, source=EmailAsset.Source.DATA_URL)
        self.assertIsNotNone(data_asset.object_key)


class EmailIngestHtmlRetryTests(TestCase):
    """POP3 수집 시 HTML 저장 재시도 조건을 검증합니다."""

    def test_ingest_calls_store_when_html_key_missing(self) -> None:
        """HTML 키가 비어 있으면 생성 여부와 무관하게 저장을 시도하는지 확인합니다.

        입력:
            없음(세션/서비스 모킹).
        반환:
            없음.
        부작용:
            테스트 DB에 Email 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        email = Email.objects.create(
            message_id="msg-pop3-1",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="knox-pop3-1",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )

        fields = {
            "message_id": email.message_id,
            "received_at": email.received_at,
            "subject": email.subject,
            "sender": email.sender,
            "sender_id": email.sender_id,
            "recipient": email.recipient,
            "cc": [],
            "body_text": email.body_text,
            "body_html": "<html><body>Body</body></html>",
            "cid_map": {},
        }

        session = Mock()

        with patch("api.emails.services.ingest._iter_pop3_messages", return_value=[(1, Mock())]), patch(
            "api.emails.services.ingest._extract_subject_header", return_value=email.subject
        ), patch("api.emails.services.ingest._is_excluded_subject", return_value=False), patch(
            "api.emails.services.ingest._parse_message_to_fields", return_value=fields
        ), patch(
            "api.emails.services.ingest.resolve_email_affiliation",
            return_value={
                "user_sdwt_prod": "group-a",
                "classification_source": Email.ClassificationSource.UNASSIGNED,
            },
        ), patch(
            "api.emails.services.ingest.save_parsed_email", return_value=(email, False)
        ), patch(
            "api.emails.services.ingest.store_email_html_and_assets"
        ) as mock_store, patch(
            "api.emails.services.ingest._delete_pop3_messages"
        ) as mock_delete:
            ingest_pop3_mailbox(session)

        mock_store.assert_called_once_with(
            email=email,
            body_html=fields["body_html"],
            cid_map=fields["cid_map"],
        )
        mock_delete.assert_called_once_with(session, [1])


class EmailPop3MailboxTransportTests(SimpleTestCase):
    """emails POP3 mailbox transport 동작을 검증합니다."""

    def test_iter_pop3_messages_allows_long_html_lines(self) -> None:
        """기본 poplib 제한보다 긴 HTML 라인도 메시지로 파싱하는지 확인합니다."""

        long_html = b"<html><body>" + (b"A" * 3000) + b"</body></html>"
        raw_response = (
            b"+OK message follows\r\n"
            b"Subject: long-line\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"\r\n"
            + long_html
            + b"\r\n.\r\n"
        )

        class FakePop3(_LongLinePOP3):
            """네트워크 없이 long response를 재현하는 테스트 client입니다."""

            def __init__(self) -> None:
                self.file = BytesIO(raw_response)
                self._debugging = 0

            def _putcmd(self, line: str) -> None:
                self.sent_command = line

            def list(self) -> tuple[bytes, list[bytes], int]:
                return b"+OK", [b"1 9999"], 9999

        messages = list(_iter_pop3_messages(FakePop3()))

        self.assertEqual(len(messages), 1)
        msg_num, msg = messages[0]
        self.assertEqual(msg_num, 1)
        self.assertEqual(msg.get("Subject"), "long-line")
        self.assertIn("A" * 3000, msg.get_content())
