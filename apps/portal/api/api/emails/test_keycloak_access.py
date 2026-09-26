"""조직 목록 없이 Keycloak SDWT 권한으로 메일 데이터 접근을 검사합니다."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from api.account.services import (
    upsert_user_identity, build_authorization_snapshot, bind_authorization_context,
    AUTHORIZATION_SESSION_KEY,
)
from .models import Email
from .services.mutations import delete_single_email, move_emails_to_user_sdwt_prod


@override_settings(OIDC_CLIENT_ID="portal")
class KeycloakEmailAccessTests(TestCase):
    def setUp(self):
        self.user, _ = upsert_user_identity(identity={"avatarid": "9001"}, sabun="1001", knox_id="test.user")
        self.a = Email.objects.create(message_id="a", subject="A", sender="test@example.com", sender_id="test.user",
            received_at=timezone.now(), user_sdwt_prod="SDWT-A", body_text="A")
        self.b = Email.objects.create(message_id="b", subject="B", sender="other@example.com", sender_id="other",
            received_at=timezone.now(), user_sdwt_prod="SDWT-B", body_text="B")

    def login(self, *, roles=("emails-user",), groups=(), dept="OTHER"):
        snapshot = build_authorization_snapshot({"userid": self.user.avatarid, "deptid": dept,
            "groups": list(groups), "resource_access": {"portal": {"roles": list(roles)}}})
        bind_authorization_context(user=self.user, snapshot=snapshot)
        self.client.force_login(self.user)
        session = self.client.session; session[AUTHORIZATION_SESSION_KEY] = snapshot; session.save()

    def test_viewer_reads_only_granted_sdwt_without_catalog(self):
        self.login(groups=["/SDWT-A/viewer"])
        self.assertEqual(self.client.get(reverse("emails-detail", args=[self.a.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("emails-detail", args=[self.b.pk])).status_code, 403)
        with self.assertRaises(PermissionError):
            delete_single_email(self.a.pk, user=self.user)
        self.assertTrue(Email.objects.filter(pk=self.a.pk).exists())

    def test_sender_cannot_bypass_sdwt_scope(self):
        self.login(groups=["/SDWT-B/viewer"])
        self.assertEqual(self.client.get(reverse("emails-detail", args=[self.a.pk])).status_code, 403)

    def test_standard_role_does_not_imply_data_access(self):
        self.login(roles=["portal-all-apps"], dept="ETCH")
        self.assertEqual(self.client.get(reverse("emails-detail", args=[self.a.pk])).status_code, 403)

    def test_sdwt_group_without_app_role_cannot_call_api(self):
        self.login(roles=[], groups=["/SDWT-A/admin"])
        self.assertEqual(self.client.get(reverse("emails-detail", args=[self.a.pk])).status_code, 403)

    @patch("api.emails.services.mutations.delete_email_objects")
    def test_sdwt_admin_can_delete_without_affiliation_rows(self, _delete):
        self.login(groups=["/SDWT-A/admin"])
        delete_single_email(self.a.pk, user=self.user)
        self.assertFalse(Email.objects.filter(pk=self.a.pk).exists())

    def test_cross_sdwt_move_requires_both_write_grants(self):
        self.login(groups=["/SDWT-A/user", "/SDWT-B/viewer"])
        with self.assertRaises(PermissionError):
            move_emails_to_user_sdwt_prod(email_ids=[self.a.pk], to_user_sdwt_prod="SDWT-B", user=self.user)
        self.a.refresh_from_db(); self.assertEqual(self.a.user_sdwt_prod, "SDWT-A")

    @patch("api.emails.services.mutations.enqueue_rag_index_for_emails", return_value={"registered": 0, "failed": 0, "missing": 0})
    def test_move_with_both_grants_without_catalog(self, _enqueue):
        self.login(groups=["/SDWT-A/user", "/SDWT-B/user"])
        move_emails_to_user_sdwt_prod(email_ids=[self.a.pk], to_user_sdwt_prod="SDWT-B", user=self.user)
        self.a.refresh_from_db(); self.assertEqual(self.a.user_sdwt_prod, "SDWT-B")

    def test_full_admin_can_read_unlisted_sdwt(self):
        self.login(roles=["portal-admin"])
        self.assertEqual(self.client.get(reverse("emails-detail", args=[self.b.pk])).status_code, 200)

    def test_forged_privilege_flag_does_not_allow_write(self):
        self.login(groups=["/SDWT-A/viewer"])
        with self.assertRaises(PermissionError):
            delete_single_email(self.a.pk, user=self.user, is_privileged=True)
