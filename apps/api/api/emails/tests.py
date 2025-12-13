from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from api.emails.models import Email
from api.emails.selectors import resolve_email_affiliation
from api.emails.services import reclassify_emails_for_user_sdwt_change


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

    def test_reclassify_emails_for_user_sdwt_change_targets_knox_id(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S99999", password="test-password")
        user.knox_id = "loginid2"
        user.user_sdwt_prod = "group-b"
        user.save(update_fields=["knox_id", "user_sdwt_prod"])

        received_at = timezone.now()
        email = Email.objects.create(
            message_id="msg-1",
            received_at=received_at,
            subject="Subject",
            sender="loginid2@example.com",
            sender_id="loginid2",
            recipient="dest@example.com",
            user_sdwt_prod="group-old",
            body_text="Body",
        )

        updated = reclassify_emails_for_user_sdwt_change(
            user,
            effective_from=received_at - timedelta(days=1),
        )
        self.assertEqual(updated, 1)
        email.refresh_from_db()
        self.assertEqual(email.user_sdwt_prod, "group-b")
