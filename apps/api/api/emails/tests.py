from __future__ import annotations

import os
import gzip
from datetime import timedelta
from email.message import EmailMessage
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from api.account.models import Affiliation, ExternalAffiliationSnapshot, UserSdwtProdAccess, UserSdwtProdChange
from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD
from api.emails.models import Email, EmailOutbox
from api.emails.selectors import get_filtered_emails, resolve_email_affiliation
from api.emails.services import (
    MailSendError,
    _parse_message_to_fields,
    claim_unassigned_emails_for_user,
    delete_single_email,
    enqueue_rag_index_for_emails,
    enqueue_rag_index,
    move_emails_to_user_sdwt_prod,
    move_sender_emails_after,
    process_email_outbox_batch,
    send_knox_mail_api,
)
from api.rag.services import RAG_INDEX_EMAILS, resolve_rag_index_name


class EmailAffiliationTests(TestCase):
    """emails.selectors / emails.services의 소속 판별/재분류 동작을 검증합니다."""

    def test_resolve_email_affiliation_uses_user_knox_id(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S12345", password="test-password")
        user.knox_id = "loginid1"
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

        affiliation = resolve_email_affiliation(sender_id="loginid1", received_at=timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], "group-a")

    def test_resolve_email_affiliation_unknown_sender_defaults_to_unassigned(self) -> None:
        affiliation = resolve_email_affiliation(sender_id="unknown-sender", received_at=timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], UNASSIGNED_USER_SDWT_PROD)

    def test_resolve_email_affiliation_uses_external_prediction(self) -> None:
        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext",
            predicted_user_sdwt_prod="group-pred",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        affiliation = resolve_email_affiliation(sender_id="loginid-ext", received_at=timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], "group-pred")

    def test_resolve_email_affiliation_uses_current_user_sdwt_prod(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S77777", password="test-password")
        user.knox_id = "loginid3"
        user.user_sdwt_prod = "group-new"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

        effective_from = timezone.now()
        UserSdwtProdChange.objects.create(
            user=user,
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=effective_from,
            applied=True,
            approved=True,
        )

        before = resolve_email_affiliation(sender_id="loginid3", received_at=effective_from - timedelta(hours=1))
        self.assertEqual(before["user_sdwt_prod"], "group-new")

        after = resolve_email_affiliation(sender_id="loginid3", received_at=effective_from + timedelta(hours=1))
        self.assertEqual(after["user_sdwt_prod"], "group-new")


class EmailMoveServiceTests(TestCase):
    @patch("api.emails.services.insert_email_to_rag")
    def test_enqueue_rag_index_for_emails_reports_missing_ids(self, _mock_insert: Mock) -> None:
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

    @patch("api.emails.services.insert_email_to_rag")
    def test_move_sender_emails_after_filters_by_time(self, _mock_insert: Mock) -> None:
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
        User = get_user_model()
        user = User.objects.create_user(sabun="S22222", password="test-password")
        user.knox_id = "loginid-claim"
        user.user_sdwt_prod = "group-claim"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

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


class EmailOutboxTests(TestCase):
    @patch("api.emails.services.insert_email_to_rag")
    def test_process_outbox_index_updates_email(self, mock_insert: Mock) -> None:
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
    def test_delete_email_enqueues_outbox(self, mock_delete: Mock) -> None:
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


class EmailMailboxAccessViewTests(TestCase):
    """emails 뷰에서 user_sdwt_prod 기반 접근 제어를 검증합니다."""

    def test_user_only_sees_own_mailbox_by_default(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S11111", password="test-password")
        user.knox_id = "knox-11111"
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

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
        User = get_user_model()
        user = User.objects.create_user(sabun="S11110", password="test-password")
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["user_sdwt_prod"])

        self.client.force_login(user)

        response = self.client.get(reverse("emails-inbox"))
        self.assertEqual(response.status_code, 403)

    def test_sender_can_access_sent_email_without_mailbox_access(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S11113", password="test-password")
        user.knox_id = "loginid-sender"
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

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
        User = get_user_model()
        user = User.objects.create_user(sabun="S11114", password="test-password")
        user.knox_id = "loginid-sender"
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

        self.client.force_login(user)

        response = self.client.get(reverse("emails-sent"), {"knox_id": "loginid-sender"})
        self.assertEqual(response.status_code, 400)

    def test_mailbox_list_includes_empty_granted_mailbox(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S11112", password="test-password")
        user.knox_id = "knox-11112"
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

        UserSdwtProdAccess.objects.create(user=user, user_sdwt_prod="group-empty")

        self.client.force_login(user)

        mailbox_list = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_list.status_code, 200)
        self.assertIn("__sent__", mailbox_list.json()["results"])
        self.assertIn("group-a", mailbox_list.json()["results"])
        self.assertIn("group-empty", mailbox_list.json()["results"])

    def test_user_can_select_granted_mailbox(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S22222", password="test-password")
        user.knox_id = "knox-22222"
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

        UserSdwtProdAccess.objects.create(user=user, user_sdwt_prod="group-b")

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

        response = self.client.get(reverse("emails-inbox"), {"user_sdwt_prod": "group-b"})
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-b"})

    def test_user_can_view_mailbox_members_for_accessible_mailbox(self) -> None:
        User = get_user_model()
        requester = User.objects.create_user(sabun="S33333", password="test-password")
        requester.username = "홍길동"
        requester.knox_id = "loginid-requester"
        requester.user_sdwt_prod = "group-a"
        requester.save(update_fields=["username", "knox_id", "user_sdwt_prod"])

        affiliated = User.objects.create_user(sabun="S33334", password="test-password")
        affiliated.username = "김철수"
        affiliated.knox_id = "loginid-affiliated"
        affiliated.user_sdwt_prod = "group-a"
        affiliated.save(update_fields=["username", "knox_id", "user_sdwt_prod"])

        granted = User.objects.create_user(sabun="S33335", password="test-password")
        granted.username = "이영희"
        granted.knox_id = "loginid-granted"
        granted.user_sdwt_prod = "group-b"
        granted.save(update_fields=["username", "knox_id", "user_sdwt_prod"])
        UserSdwtProdAccess.objects.create(user=granted, user_sdwt_prod="group-a", can_manage=True)

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

        response = self.client.get(reverse("emails-mailbox-members"), {"user_sdwt_prod": "group-a"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        members = payload["members"]
        member_ids = {item["userId"] for item in members}
        self.assertEqual(member_ids, {requester.id, affiliated.id, granted.id})

        requester_member = next(item for item in members if item["userId"] == requester.id)
        self.assertEqual(requester_member["emailCount"], 2)
        self.assertEqual(requester_member["username"], requester.username)
        self.assertEqual(requester_member["knoxId"], requester.knox_id)

        affiliated_member = next(item for item in members if item["userId"] == affiliated.id)
        self.assertEqual(affiliated_member["emailCount"], 1)
        self.assertEqual(affiliated_member["username"], affiliated.username)
        self.assertEqual(affiliated_member["knoxId"], affiliated.knox_id)

        granted_member = next(item for item in members if item["userId"] == granted.id)
        self.assertTrue(granted_member["canManage"])
        self.assertEqual(granted_member["emailCount"], 0)
        self.assertEqual(granted_member["username"], granted.username)
        self.assertEqual(granted_member["knoxId"], granted.knox_id)

    def test_user_cannot_view_mailbox_members_for_ungranted_mailbox(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S44444", password="test-password")
        user.knox_id = "knox-44444"
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

        other = User.objects.create_user(sabun="S44445", password="test-password")
        other.knox_id = "knox-44445"
        other.user_sdwt_prod = "group-b"
        other.save(update_fields=["knox_id", "user_sdwt_prod"])

        self.client.force_login(user)

        response = self.client.get(reverse("emails-mailbox-members"), {"user_sdwt_prod": "group-b"})
        self.assertEqual(response.status_code, 403)

    def test_user_can_view_mailbox_members_for_granted_mailbox(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S55555", password="test-password")
        user.knox_id = "knox-55555"
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

        mailbox_owner = User.objects.create_user(sabun="S55556", password="test-password")
        mailbox_owner.knox_id = "knox-55556"
        mailbox_owner.user_sdwt_prod = "group-b"
        mailbox_owner.save(update_fields=["knox_id", "user_sdwt_prod"])

        UserSdwtProdAccess.objects.create(user=user, user_sdwt_prod="group-b")

        self.client.force_login(user)

        response = self.client.get(reverse("emails-mailbox-members"), {"user_sdwt_prod": "group-b"})
        self.assertEqual(response.status_code, 200)
        members = response.json()["members"]
        self.assertIn(mailbox_owner.id, {item["userId"] for item in members})

        forbidden = self.client.get(reverse("emails-inbox"), {"user_sdwt_prod": "group-c"})
        self.assertEqual(forbidden.status_code, 403)

    def test_staff_mailboxes_list_includes_unassigned(self) -> None:
        User = get_user_model()
        staff = User.objects.create_user(sabun="S33333", password="test-password", is_staff=True)
        staff.knox_id = "knox-33333"
        staff.save(update_fields=["knox_id"])

        Affiliation.objects.create(department="Dept", line="Line", user_sdwt_prod="group-empty")

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

        self.client.force_login(staff)

        mailbox_list = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_list.status_code, 200)
        self.assertIn("__sent__", mailbox_list.json()["results"])
        self.assertIn("group-a", mailbox_list.json()["results"])
        self.assertIn("group-b", mailbox_list.json()["results"])
        self.assertIn("group-empty", mailbox_list.json()["results"])
        self.assertIn(UNASSIGNED_USER_SDWT_PROD, mailbox_list.json()["results"])

        response = self.client.get(reverse("emails-inbox"))
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-a", "group-b", UNASSIGNED_USER_SDWT_PROD})

        unassigned_list = self.client.get(reverse("emails-inbox"), {"user_sdwt_prod": UNASSIGNED_USER_SDWT_PROD})
        self.assertEqual(unassigned_list.status_code, 200)

        detail = self.client.get(reverse("emails-detail", kwargs={"email_id": unassigned_email.id}))
        self.assertEqual(detail.status_code, 200)

        filtered = self.client.get(reverse("emails-inbox"), {"user_sdwt_prod": "group-b"})
        self.assertEqual(filtered.status_code, 200)
        results = filtered.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {"group-b"})

    def test_superuser_mailboxes_list_includes_unassigned(self) -> None:
        User = get_user_model()
        superuser = User.objects.create_superuser(sabun="S33334", password="test-password")
        superuser.knox_id = "knox-33334"
        superuser.save(update_fields=["knox_id"])

        Affiliation.objects.create(department="Dept", line="Line", user_sdwt_prod="group-empty")

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

        unassigned_list = self.client.get(reverse("emails-inbox"), {"user_sdwt_prod": UNASSIGNED_USER_SDWT_PROD})
        self.assertEqual(unassigned_list.status_code, 200)
        results = unassigned_list.json()["results"]
        self.assertEqual({item["userSdwtProd"] for item in results}, {UNASSIGNED_USER_SDWT_PROD})

    def test_user_can_claim_unassigned_emails(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S44444", password="test-password")
        user.knox_id = "loginid-claim"
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

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


class RagIndexNameTests(SimpleTestCase):
    def test_resolve_rag_index_name_returns_explicit_value(self) -> None:
        self.assertEqual(resolve_rag_index_name("rp-emails"), "rp-emails")

    def test_resolve_rag_index_name_falls_back_to_default(self) -> None:
        with patch("api.rag.services.RAG_INDEX_DEFAULT", "rp-unclassified"):
            self.assertEqual(resolve_rag_index_name(None), "rp-unclassified")

    def test_resolve_rag_index_name_uses_first_index_list_when_default_missing(self) -> None:
        with patch("api.rag.services.RAG_INDEX_DEFAULT", ""), patch(
            "api.rag.services.RAG_INDEX_LIST", ["rp-a", "rp-b"]
        ):
            self.assertEqual(resolve_rag_index_name(None), "rp-a")


class KnoxMailApiTests(SimpleTestCase):
    """emails.services.send_knox_mail_api 동작을 검증합니다."""

    @patch.dict(
        os.environ,
        {
            "MAIL_API_URL": "http://mail.test/send",
            "MAIL_API_KEY": "ticket",
            "MAIL_API_SYSTEM_ID": "plane",
            "MAIL_API_KNOX_ID": "knox-user",
        },
        clear=False,
    )
    @patch("api.emails.services.requests.post")
    def test_send_knox_mail_api_returns_json(self, mock_post: Mock) -> None:
        response = Mock()
        response.ok = True
        response.status_code = 200
        response.text = ""
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"status": "ok"}
        mock_post.return_value = response

        result = send_knox_mail_api(
            sender_email="sender@example.com",
            receiver_emails=["a@example.com", "b@example.com"],
            subject="Subject",
            html_content="<p>Hello</p>",
        )
        self.assertEqual(result, {"status": "ok"})
        mock_post.assert_called_once_with(
            "http://mail.test/send",
            params={"systemId": "plane", "loginUser.login": "knox-user"},
            headers={"x-dep-ticket": "ticket"},
            json={
                "receiverList": [
                    {"email": "a@example.com", "recipientType": "TO"},
                    {"email": "b@example.com", "recipientType": "TO"},
                ],
                "title": "Subject",
                "content": "<p>Hello</p>",
                "senderMailAddress": "sender@example.com",
            },
            timeout=10,
        )

    @patch.dict(
        os.environ,
        {
            "MAIL_API_URL": "http://mail.test/send",
            "MAIL_API_KEY": "ticket",
            "MAIL_API_KNOX_ID": "knox-user",
        },
        clear=False,
    )
    @patch("api.emails.services.requests.post")
    def test_send_knox_mail_api_returns_ok_for_non_json(self, mock_post: Mock) -> None:
        response = Mock()
        response.ok = True
        response.status_code = 204
        response.text = ""
        response.headers = {"content-type": "text/plain"}
        mock_post.return_value = response

        result = send_knox_mail_api(
            sender_email="sender@example.com",
            receiver_emails=["a@example.com"],
            subject="Subject",
            html_content="<p>Hello</p>",
        )
        self.assertEqual(result, {"ok": True})

    @patch.dict(
        os.environ,
        {
            "MAIL_API_URL": "http://mail.test/send",
            "MAIL_API_KEY": "ticket",
            "MAIL_API_KNOX_ID": "knox-user",
        },
        clear=False,
    )
    @patch("api.emails.services.requests.post")
    def test_send_knox_mail_api_raises_on_http_error(self, mock_post: Mock) -> None:
        response = Mock()
        response.ok = False
        response.status_code = 500
        response.text = "server error"
        response.headers = {"content-type": "text/plain"}
        mock_post.return_value = response

        with self.assertRaises(MailSendError) as ctx:
            send_knox_mail_api(
                sender_email="sender@example.com",
                receiver_emails=["a@example.com"],
                subject="Subject",
                html_content="<p>Hello</p>",
            )
        self.assertIn("메일 API 오류 500", str(ctx.exception))

    def test_send_knox_mail_api_raises_when_missing_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MAIL_API_URL": "",
                "MAIL_API_KEY": "",
                "MAIL_API_SYSTEM_ID": "",
                "MAIL_API_KNOX_ID": "",
            },
            clear=False,
        ):
            with self.assertRaises(MailSendError):
                send_knox_mail_api(
                    sender_email="sender@example.com",
                    receiver_emails=["a@example.com"],
                    subject="Subject",
                    html_content="<p>Hello</p>",
                )


class EmailParsingTests(SimpleTestCase):
    def test_parse_message_to_fields_includes_cc_and_recipient_lists(self) -> None:
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


class EmailSearchSelectorTests(TestCase):
    def test_get_filtered_emails_search_includes_to_and_cc(self) -> None:
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


class EmailEndpointTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(sabun="S11111", password="test-password")
        self.user.knox_id = "knox-11111"
        self.user.user_sdwt_prod = "group-a"
        self.user.save(update_fields=["knox_id", "user_sdwt_prod"])

        self.email = Email.objects.create(
            message_id="msg-111",
            received_at=timezone.now(),
            subject="Subject",
            sender="sender@example.com",
            sender_id="knox-11111",
            recipient=["dest@example.com"],
            user_sdwt_prod="group-a",
            body_text="Body",
            body_html_gzip=gzip.compress(b"<html>body</html>"),
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
        list_response = self.client.get(reverse("emails-inbox"))
        self.assertEqual(list_response.status_code, 200)

        detail_response = self.client.get(reverse("emails-detail", kwargs={"email_id": self.email.id}))
        self.assertEqual(detail_response.status_code, 200)

        html_response = self.client.get(reverse("emails-html", kwargs={"email_id": self.email.id}))
        self.assertEqual(html_response.status_code, 200)
        self.assertIn("<html>", html_response.content.decode("utf-8"))

        delete_response = self.client.delete(reverse("emails-detail", kwargs={"email_id": self.email.id}))
        self.assertEqual(delete_response.status_code, 200)

    def test_email_sent_list(self) -> None:
        sent_response = self.client.get(reverse("emails-sent"))
        self.assertEqual(sent_response.status_code, 200)
        results = sent_response.json()["results"]
        self.assertTrue(any(item["id"] == self.email.id for item in results))

    def test_email_mailboxes_and_members(self) -> None:
        mailbox_response = self.client.get(reverse("emails-mailboxes"))
        self.assertEqual(mailbox_response.status_code, 200)

        members_response = self.client.get(
            reverse("emails-mailbox-members"),
            {"user_sdwt_prod": "group-a"},
        )
        self.assertEqual(members_response.status_code, 200)

    def test_email_unassigned_summary_and_claim(self) -> None:
        summary = self.client.get(reverse("emails-unassigned-summary"))
        self.assertEqual(summary.status_code, 200)

        claim = self.client.post(reverse("emails-unassigned-claim"))
        self.assertEqual(claim.status_code, 200)

    def test_email_bulk_delete(self) -> None:
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
        response = self.client.post(
            reverse("emails-bulk-delete"),
            data='{"email_ids":[%d]}' % email.id,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    @patch("api.emails.services.insert_email_to_rag")
    def test_email_move_endpoint(self, _mock_insert: Mock) -> None:
        UserSdwtProdAccess.objects.create(user=self.user, user_sdwt_prod="group-b")

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
            data='{"email_ids":[%d],"to_user_sdwt_prod":"group-b"}' % email.id,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        email.refresh_from_db()
        self.assertEqual(email.user_sdwt_prod, "group-b")

    @patch("api.emails.views.run_pop3_ingest_from_env", return_value={"deleted": 1, "reindexed": 2})
    def test_email_ingest_trigger(self, _mock_ingest) -> None:
        response = self.client.post(reverse("emails-ingest"))
        self.assertEqual(response.status_code, 200)


class EmailOutboxTriggerAuthTests(TestCase):
    @override_settings(AIRFLOW_TRIGGER_TOKEN="expected-token")
    @patch("api.emails.views.process_email_outbox_batch")
    def test_outbox_trigger_requires_token(self, mock_process: Mock) -> None:
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
    @patch("api.emails.views.process_email_outbox_batch")
    def test_outbox_trigger_accepts_limit(self, mock_process: Mock) -> None:
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
