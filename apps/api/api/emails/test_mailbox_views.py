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

class EmailMailboxAccessBasicsViewTests(TestCase):
    """emails 뷰에서 user_sdwt_prod 기반 접근 제어를 검증합니다."""

    def setUp(self) -> None:
        """메일함 계약과 무관한 공통 scope 권한 경계를 격리합니다."""

        _allow_test_scope_access(self)

    def test_user_only_sees_own_mailbox_by_default(self) -> None:
        """일반 사용자가 기본적으로 자신의 메일함만 보는지 확인합니다.

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
        user = User.objects.create_user(sabun="S11111", password="test-password")
        user.knox_id = "knox-11111"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        Email.objects.create(
            message_id="msg-a",
            received_at=timezone.now(),
            subject="A",
            sender="a@example.com",
            sender_id="a",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body A",
        )
        Email.objects.create(
            message_id="msg-b",
            received_at=timezone.now(),
            subject="B",
            sender="b@example.com",
            sender_id="b",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body B",
        )

        self.client.force_login(user)

        response = self.client.get(reverse("emails-inbox"))
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-a"})

        detail = self.client.get(reverse("emails-detail", kwargs={"email_id": Email.objects.get(message_id="msg-b").id}))
        self.assertEqual(detail.status_code, 403)

    def test_missing_knox_id_is_forbidden(self) -> None:
        """knox_id가 없으면 접근이 거부되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S11110", password="test-password")
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        self.client.force_login(user)

        response = self.client.get(reverse("emails-inbox"))
        self.assertEqual(response.status_code, 403)

    def test_emails_admin_without_knox_id_is_not_privileged(self) -> None:
        """Emails 관리자도 전역 사용자 식별자인 knox_id가 없으면 특권을 얻지 못해야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S11109",
            password="test-password",
        )
        request = Mock(user=user)

        with patch(
            "api.emails.permissions.account_services.has_scope_role",
            return_value=True,
        ) as has_scope_role:
            self.assertEqual(
                resolve_access_control(request),
                (True, False, set()),
            )

        has_scope_role.assert_not_called()

    def test_all_data_scope_without_emails_admin_is_not_privileged(self) -> None:
        """전체 데이터 범위만으로 삭제·미분류 접근 특권이 생기지 않아야 합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S11108",
            password="test-password",
            knox_id="knox-11108",
        )
        request = Mock(user=user)

        with patch(
            "api.emails.permissions.account_services.get_effective_affiliation_scope",
            return_value={
                "allowed": True,
                "all": True,
                "affiliations": [{"userSdwtProd": "group-a"}],
            },
        ), patch(
            "api.emails.permissions.account_services.has_scope_role",
            return_value=False,
        ):
            self.assertEqual(
                resolve_access_control(request),
                (True, False, {"group-a"}),
            )

    def test_sender_can_access_sent_email_without_mailbox_access(self) -> None:
        """발신자는 메일함 접근 권한 없이도 보낸메일 접근이 가능한지 확인합니다.

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
        user = User.objects.create_user(sabun="S11113", password="test-password")
        user.knox_id = "loginid-sender"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        sent_email = Email.objects.create(
            message_id="msg-sent-1",
            received_at=timezone.now(),
            subject="Sent",
            sender="sender@example.com",
            sender_id="loginid-sender",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body",
        )

        self.client.force_login(user)

        detail = self.client.get(reverse("emails-detail", kwargs={"email_id": sent_email.id}))
        self.assertEqual(detail.status_code, 200)

        sent_list = self.client.get(reverse("emails-sent"))
        self.assertEqual(sent_list.status_code, 200)
        results = sent_list.json()["results"]
        self.assertTrue(any(item["id"] == sent_email.id for item in results))

    def test_sent_rejects_knox_id_query_param(self) -> None:
        """보낸메일 조회에서 knox_id 파라미터가 거부되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S11114", password="test-password")
        user.knox_id = "loginid-sender"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        self.client.force_login(user)

        response = self.client.get(reverse("emails-sent"), {"knox_id": "loginid-sender"})
        self.assertEqual(response.status_code, 400)

    def test_inbox_rejects_removed_snake_case_query_aliases(self) -> None:
        """받은메일 목록에서 제거된 snake_case query를 거부합니다."""

        User = get_user_model()
        user = User.objects.create_user(
            sabun="S11115",
            password="test-password",
            knox_id="loginid-query",
        )
        _set_current_affiliation(user, user_sdwt_prod="group-a")
        self.client.force_login(user)

        response = self.client.get(
            reverse("emails-inbox"),
            {"user_sdwt_prod": "group-a", "page_size": 20},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")
        self.assertIn("page_size", response.json()["message"])

    def test_mailbox_list_includes_empty_granted_mailbox(self) -> None:
        """접근 권한만 있는 빈 메일함도 목록에 포함되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/접근 권한 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S11112", password="test-password")
        user.knox_id = "knox-11112"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        manager = User.objects.create_user(sabun="S11113", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-empty")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-empty",
            target_user=user,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        self.assertEqual(status_code, 200)
        _grant_emails_affiliation_data(
            user=user,
            user_sdwt_prods=("group-empty",),
        )

        self.client.force_login(user)

        mailbox_list = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_list.status_code, 200)
        self.assertIn("__sent__", mailbox_list.json()["results"])
        self.assertIn("group-a", mailbox_list.json()["results"])
        self.assertIn("group-empty", mailbox_list.json()["results"])

    def test_user_can_select_granted_mailbox(self) -> None:
        """접근 권한이 있는 메일함을 선택해 조회할 수 있는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email/권한 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S22222", password="test-password")
        user.knox_id = "knox-22222"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        manager = User.objects.create_user(sabun="S22223", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=user,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        self.assertEqual(status_code, 200)
        _grant_emails_affiliation_data(
            user=user,
            user_sdwt_prods=("group-b",),
        )

        Email.objects.create(
            message_id="msg-a2",
            received_at=timezone.now(),
            subject="A2",
            sender="a@example.com",
            sender_id="a",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body A2",
        )
        Email.objects.create(
            message_id="msg-b2",
            received_at=timezone.now(),
            subject="B2",
            sender="b@example.com",
            sender_id="b",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body B2",
        )

        self.client.force_login(user)

        mailbox_list = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_list.status_code, 200)
        self.assertEqual(mailbox_list.json()["results"], ["__sent__", "group-a", "group-b"])

        response = self.client.get(reverse("emails-inbox"), {"userSdwtProd": "group-b"})
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-b"})

class EmailMailboxMemberViewTests(TestCase):
    """메일함 멤버 조회 권한과 응답을 검증합니다."""

    def setUp(self) -> None:
        """메일함 계약과 무관한 공통 scope 권한 경계를 격리합니다."""

        _allow_test_scope_access(self)

    def test_user_can_view_mailbox_members_for_accessible_mailbox(self) -> None:
        """접근 가능한 메일함의 멤버 목록을 조회할 수 있는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email/권한 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        requester = User.objects.create_user(sabun="S33333", password="test-password")
        requester.username = "홍길동"
        requester.knox_id = "loginid-requester"
        requester.save(update_fields=["username", "knox_id"])
        _set_current_affiliation(requester, user_sdwt_prod="group-a")

        affiliated = User.objects.create_user(sabun="S33334", password="test-password")
        affiliated.username = "김철수"
        affiliated.knox_id = "loginid-affiliated"
        affiliated.save(update_fields=["username", "knox_id"])
        _set_current_affiliation(affiliated, user_sdwt_prod="group-a")

        granted = User.objects.create_user(sabun="S33335", password="test-password")
        granted.username = "이영희"
        granted.knox_id = "loginid-granted"
        granted.save(update_fields=["username", "knox_id"])
        _set_current_affiliation(granted, user_sdwt_prod="group-b")
        manager = User.objects.create_user(sabun="S33336", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-a")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-a",
            target_user=granted,
            action="grant",
            role="manager",
            reason="테스트 권한 변경",
        )
        self.assertEqual(status_code, 200)

        Email.objects.create(
            message_id="mailbox-members-1",
            received_at=timezone.now(),
            subject="Requester mail 1",
            sender="requester@example.com",
            sender_id=requester.knox_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        Email.objects.create(
            message_id="mailbox-members-2",
            received_at=timezone.now(),
            subject="Requester mail 2",
            sender="requester@example.com",
            sender_id=requester.knox_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        Email.objects.create(
            message_id="mailbox-members-3",
            received_at=timezone.now(),
            subject="Affiliated mail 1",
            sender="affiliated@example.com",
            sender_id=affiliated.knox_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
        )
        Email.objects.create(
            message_id="mailbox-members-outside",
            received_at=timezone.now(),
            subject="Outside mailbox",
            sender="requester@example.com",
            sender_id=requester.knox_id,
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body",
        )

        self.client.force_login(requester)

        response = self.client.get(reverse("emails-mailbox-members"), {"userSdwtProd": "group-a"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        members = payload["members"]
        member_ids = {item["userId"] for item in members}
        self.assertEqual(member_ids, {requester.id, affiliated.id, granted.id, manager.id})

        requester_member = next(item for item in members if item["userId"] == requester.id)
        self.assertEqual(requester_member["emailCount"], 2)
        self.assertEqual(requester_member["username"], requester.username)
        self.assertEqual(requester_member["knoxId"], requester.knox_id)

        affiliated_member = next(item for item in members if item["userId"] == affiliated.id)
        self.assertEqual(affiliated_member["emailCount"], 1)
        self.assertEqual(affiliated_member["username"], affiliated.username)
        self.assertEqual(affiliated_member["knoxId"], affiliated.knox_id)

        granted_member = next(item for item in members if item["userId"] == granted.id)
        self.assertEqual(granted_member["role"], "manager")
        self.assertEqual(granted_member["emailCount"], 0)
        self.assertEqual(granted_member["username"], granted.username)
        self.assertEqual(granted_member["knoxId"], granted.knox_id)

    def test_user_cannot_view_mailbox_members_for_ungranted_mailbox(self) -> None:
        """권한 없는 메일함의 멤버 목록은 거부되는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S44444", password="test-password")
        user.knox_id = "knox-44444"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        other = User.objects.create_user(sabun="S44445", password="test-password")
        other.knox_id = "knox-44445"
        other.save(update_fields=["knox_id"])
        _set_current_affiliation(other, user_sdwt_prod="group-b")

        self.client.force_login(user)

        response = self.client.get(reverse("emails-mailbox-members"), {"userSdwtProd": "group-b"})
        self.assertEqual(response.status_code, 403)

    def test_user_can_view_mailbox_members_for_granted_mailbox(self) -> None:
        """권한이 있는 메일함의 멤버 목록을 조회할 수 있는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/권한 생성.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S55555", password="test-password")
        user.knox_id = "knox-55555"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        mailbox_owner = User.objects.create_user(sabun="S55556", password="test-password")
        mailbox_owner.knox_id = "knox-55556"
        mailbox_owner.save(update_fields=["knox_id"])
        _set_current_affiliation(mailbox_owner, user_sdwt_prod="group-b")

        manager = User.objects.create_user(sabun="S55557", password="test-password")
        _set_current_affiliation(manager, user_sdwt_prod="group-b")
        account_services.ensure_self_access(manager, role="manager")
        _, status_code = account_services.grant_or_revoke_access(
            grantor=manager,
            target_group="group-b",
            target_user=user,
            action="grant",
            role="member",
            reason="테스트 권한 변경",
        )
        self.assertEqual(status_code, 200)
        _grant_emails_affiliation_data(
            user=user,
            user_sdwt_prods=("group-b",),
        )

        self.client.force_login(user)

        response = self.client.get(reverse("emails-mailbox-members"), {"userSdwtProd": "group-b"})
        self.assertEqual(response.status_code, 200)
        members = response.json()["members"]
        self.assertIn(mailbox_owner.id, {item["userId"] for item in members})

        forbidden = self.client.get(reverse("emails-inbox"), {"userSdwtProd": "group-c"})
        self.assertEqual(forbidden.status_code, 403)

class EmailMailboxAdminAndClaimViewTests(TestCase):
    """관리자 mailbox와 미분류 claim 흐름을 검증합니다."""

    def setUp(self) -> None:
        """메일함 계약과 무관한 공통 scope 권한 경계를 격리합니다."""

        _allow_test_scope_access(self)

    def test_emails_admin_mailboxes_list_includes_unassigned(self) -> None:
        """Emails 관리자가 UNASSIGNED 메일함을 포함해 조회하는지 확인합니다.

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
        emails_admin = User.objects.create_user(sabun="S33333", password="test-password")
        emails_admin.knox_id = "knox-33333"
        emails_admin.save(update_fields=["knox_id"])
        authority = User.objects.create_superuser(
            sabun="S33330",
            password="test-password",
        )
        _grant_emails_admin(user=emails_admin, actor=authority)
        self.assertTrue(
            account_services.has_scope_role(
                user=emails_admin,
                scope_key="emails",
            )
        )

        account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="group-empty",
        )

        Email.objects.create(
            message_id="msg-staff-a",
            received_at=timezone.now(),
            subject="A3",
            sender="a@example.com",
            sender_id="a",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body A3",
        )
        Email.objects.create(
            message_id="msg-staff-b",
            received_at=timezone.now(),
            subject="B3",
            sender="b@example.com",
            sender_id="b",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body B3",
        )
        unassigned_email = Email.objects.create(
            message_id="msg-staff-unassigned",
            received_at=timezone.now(),
            subject="U",
            sender="u@example.com",
            sender_id="u",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body U",
        )

        self.client.force_login(emails_admin)

        mailbox_list = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_list.status_code, 200, mailbox_list.json())
        self.assertIn("__sent__", mailbox_list.json()["results"])
        self.assertIn("group-a", mailbox_list.json()["results"])
        self.assertIn("group-b", mailbox_list.json()["results"])
        self.assertIn("group-empty", mailbox_list.json()["results"])
        self.assertIn(UNASSIGNED_USER_SDWT_PROD, mailbox_list.json()["results"])

        response = self.client.get(reverse("emails-inbox"))
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-a", "group-b", UNASSIGNED_USER_SDWT_PROD})

        unassigned_list = self.client.get(reverse("emails-inbox"), {"userSdwtProd": UNASSIGNED_USER_SDWT_PROD})
        self.assertEqual(unassigned_list.status_code, 200)

        detail = self.client.get(reverse("emails-detail", kwargs={"email_id": unassigned_email.id}))
        self.assertEqual(detail.status_code, 200)

        filtered = self.client.get(reverse("emails-inbox"), {"userSdwtProd": "group-b"})
        self.assertEqual(filtered.status_code, 200)
        results = filtered.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-b"})

    def test_superuser_mailboxes_list_includes_unassigned(self) -> None:
        """슈퍼유저가 UNASSIGNED 메일함을 포함해 조회하는지 확인합니다.

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
        superuser = User.objects.create_superuser(sabun="S33334", password="test-password")
        superuser.knox_id = "knox-33334"
        superuser.save(update_fields=["knox_id"])

        account_services.ensure_affiliation_option(
            department="Dept",
            line="Line",
            user_sdwt_prod="group-empty",
        )

        Email.objects.create(
            message_id="msg-su-a",
            received_at=timezone.now(),
            subject="A4",
            sender="a@example.com",
            sender_id="a",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body A4",
        )
        Email.objects.create(
            message_id="msg-su-unassigned",
            received_at=timezone.now(),
            subject="U4",
            sender="u@example.com",
            sender_id="u",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body U4",
        )

        self.client.force_login(superuser)

        mailbox_list = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_list.status_code, 200)
        self.assertIn("__sent__", mailbox_list.json()["results"])
        self.assertIn("group-a", mailbox_list.json()["results"])
        self.assertIn("group-empty", mailbox_list.json()["results"])
        self.assertIn(UNASSIGNED_USER_SDWT_PROD, mailbox_list.json()["results"])

        unassigned_list = self.client.get(reverse("emails-inbox"), {"userSdwtProd": UNASSIGNED_USER_SDWT_PROD})
        self.assertEqual(unassigned_list.status_code, 200)
        results = unassigned_list.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {UNASSIGNED_USER_SDWT_PROD})

    def test_user_can_claim_unassigned_emails(self) -> None:
        """UNASSIGNED 메일 귀속 처리 플로우가 동작하는지 확인합니다.

        입력:
            없음(테스트 데이터 생성).
        반환:
            없음.
        부작용:
            테스트 DB에 사용자/Email 생성 및 업데이트.
        오류:
            조건 불일치 시 assertion 실패.
        """

        User = get_user_model()
        user = User.objects.create_user(sabun="S44444", password="test-password")
        user.knox_id = "loginid-claim"
        user.save(update_fields=["knox_id"])
        _set_current_affiliation(user, user_sdwt_prod="group-a")

        unassigned = Email.objects.create(
            message_id="msg-unassigned",
            received_at=timezone.now(),
            subject="U",
            sender="loginid-claim@example.com",
            sender_id="loginid-claim",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body U",
        )
        classified = Email.objects.create(
            message_id="msg-classified",
            received_at=timezone.now(),
            subject="C",
            sender="loginid-claim@example.com",
            sender_id="loginid-claim",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-b",
            body_text="Body C",
        )

        self.client.force_login(user)

        summary = self.client.get(reverse("emails-unassigned-summary"))
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["count"], 1)

        claimed = self.client.post(reverse("emails-unassigned-claim"))
        self.assertEqual(claimed.status_code, 200)
        self.assertEqual(claimed.json()["moved"], 1)

        unassigned.refresh_from_db()
        classified.refresh_from_db()
        self.assertEqual(unassigned.user_sdwt_prod, "group-a")
        self.assertEqual(classified.user_sdwt_prod, "group-b")

        after_summary = self.client.get(reverse("emails-unassigned-summary"))
        self.assertEqual(after_summary.status_code, 200)
        self.assertEqual(after_summary.json()["count"], 0)

    def test_claim_unassigned_requires_user_sdwt_prod(self) -> None:
        """user_sdwt_prod 미설정 시 귀속이 실패하는지 확인합니다.

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
        user = User.objects.create_user(sabun="S55555", password="test-password")
        user.knox_id = "loginid-no-sdwt"
        user.save(update_fields=["knox_id"])

        Email.objects.create(
            message_id="msg-unassigned-2",
            received_at=timezone.now(),
            subject="U2",
            sender="loginid-no-sdwt@example.com",
            sender_id="loginid-no-sdwt",
            recipient=["dest@example.com"],
            user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD,
            body_text="Body U2",
        )

        self.client.force_login(user)
        claimed = self.client.post(reverse("emails-unassigned-claim"))
        self.assertEqual(claimed.status_code, 400)
