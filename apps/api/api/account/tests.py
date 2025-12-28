from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from api.account.models import (
    Affiliation,
    ExternalAffiliationSnapshot,
    UserProfile,
    UserSdwtProdAccess,
    UserSdwtProdChange,
)
from api.account.selectors import (
    get_accessible_user_sdwt_prods_for_user,
    get_next_user_sdwt_prod_change,
    get_affiliation_jira_key_for_line,
    list_affiliation_options,
    list_line_sdwt_pairs,
    resolve_user_affiliation,
)
from api.account.services import (
    approve_affiliation_change,
    get_account_overview,
    get_affiliation_change_requests,
    get_affiliation_overview,
    request_affiliation_change,
    submit_affiliation_reconfirm_response,
    sync_external_affiliations,
    update_affiliation_jira_key,
)
from api.emails.models import Email


class AccountEndpointTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(sabun="S50000", password="test-password")
        self.user.knox_id = "knox-50000"
        self.user.user_sdwt_prod = "group-a"
        self.user.department = "Dept"
        self.user.line = "L1"
        self.user.save(update_fields=["knox_id", "user_sdwt_prod", "department", "line"])

        self.manager = User.objects.create_user(
            sabun="S50001",
            password="test-password",
            knox_id="knox-50001",
        )
        UserSdwtProdAccess.objects.create(user=self.manager, user_sdwt_prod="group-a", can_manage=True)
        UserSdwtProdAccess.objects.create(user=self.manager, user_sdwt_prod="group-b", can_manage=True)

        self.superuser = User.objects.create_superuser(
            sabun="S50002",
            password="test-password",
            knox_id="knox-50002",
        )

        Affiliation.objects.create(department="Dept", line="L1", user_sdwt_prod="group-a")
        Affiliation.objects.create(department="Dept", line="L1", user_sdwt_prod="group-b")

    def test_account_overview_and_affiliation_endpoints(self) -> None:
        self.client.force_login(self.user)

        overview = self.client.get(reverse("account-overview"))
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["user"]["userSdwtProd"], "group-a")

        affiliation = self.client.get(reverse("account-affiliation"))
        self.assertEqual(affiliation.status_code, 200)

        options = self.client.get(reverse("account-line-sdwt-options"))
        self.assertEqual(options.status_code, 200)
        self.assertIn("lines", options.json())

    def test_account_affiliation_request_and_approval_flow(self) -> None:
        self.client.force_login(self.user)

        create_response = self.client.post(
            reverse("account-affiliation"),
            data='{"department":"Dept","line":"L1","user_sdwt_prod":"group-b"}',
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 202)
        change_id = create_response.json()["changeId"]

        self.client.force_login(self.manager)
        list_response = self.client.get(reverse("account-affiliation-requests"))
        self.assertEqual(list_response.status_code, 200)

        approve_response = self.client.post(
            reverse("account-affiliation-approve"),
            data='{"changeId": %d, "decision": "approve"}' % change_id,
            content_type="application/json",
        )
        self.assertEqual(approve_response.status_code, 200)

    def test_account_affiliation_rejects_non_string_user_sdwt_prod(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("account-affiliation"),
            data='{"department":"Dept","line":"L1","user_sdwt_prod":123}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("error"), "user_sdwt_prod is required")

    def test_account_affiliation_reconfirm(self) -> None:
        ExternalAffiliationSnapshot.objects.create(
            knox_id="knox-50000",
            predicted_user_sdwt_prod="group-b",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )
        self.user.requires_affiliation_reconfirm = True
        self.user.save(update_fields=["requires_affiliation_reconfirm"])

        self.client.force_login(self.user)

        status_response = self.client.get(reverse("account-affiliation-reconfirm"))
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.json()["requiresReconfirm"])

        confirm_response = self.client.post(
            reverse("account-affiliation-reconfirm"),
            data='{"accepted": true, "user_sdwt_prod": "group-b"}',
            content_type="application/json",
        )
        self.assertEqual(confirm_response.status_code, 202)

    def test_account_jira_key_sync_and_grants(self) -> None:
        self.client.force_login(self.superuser)

        jira_get = self.client.get(reverse("account-affiliation-jira-key"), {"lineId": "L1"})
        self.assertEqual(jira_get.status_code, 200)

        jira_post = self.client.post(
            reverse("account-affiliation-jira-key"),
            data='{"lineId":"L1","jiraKey":"PROJ"}',
            content_type="application/json",
        )
        self.assertEqual(jira_post.status_code, 200)

        sync_response = self.client.post(
            reverse("account-external-affiliation-sync"),
            data='{"records":[{"knox_id":"knox-50000","user_sdwt_prod":"group-a"}]}',
            content_type="application/json",
        )
        self.assertEqual(sync_response.status_code, 200)

        self.client.force_login(self.manager)
        grant_response = self.client.post(
            reverse("account-access-grant"),
            data='{"user_sdwt_prod":"group-a","userId":%d,"action":"grant","canManage":false}' % self.user.id,
            content_type="application/json",
        )
        self.assertEqual(grant_response.status_code, 200)

        manageable = self.client.get(reverse("account-access-manageable"))
        self.assertEqual(manageable.status_code, 200)


class AffiliationSelectorTests(TestCase):
    def test_list_affiliation_options_orders_rows(self) -> None:
        Affiliation.objects.create(department="DeptB", line="L2", user_sdwt_prod="S1")
        Affiliation.objects.create(department="DeptA", line="L2", user_sdwt_prod="S2")
        Affiliation.objects.create(department="DeptA", line="L1", user_sdwt_prod="S1")

        rows = list_affiliation_options()
        self.assertEqual(
            rows,
            [
                {"department": "DeptA", "line": "L1", "user_sdwt_prod": "S1"},
                {"department": "DeptA", "line": "L2", "user_sdwt_prod": "S2"},
                {"department": "DeptB", "line": "L2", "user_sdwt_prod": "S1"},
            ],
        )

    def test_update_affiliation_jira_key_updates_all_line_rows(self) -> None:
        Affiliation.objects.create(department="DeptA", line="L1", user_sdwt_prod="S1")
        Affiliation.objects.create(department="DeptB", line="L1", user_sdwt_prod="S2")

        updated = update_affiliation_jira_key(line_id="L1", jira_key="PROJ")

        self.assertEqual(updated, 2)
        self.assertEqual(get_affiliation_jira_key_for_line(line_id="L1"), "PROJ")

    def test_list_line_sdwt_pairs_dedupes_across_departments(self) -> None:
        Affiliation.objects.bulk_create(
            [
                Affiliation(department="DeptA", line="L1", user_sdwt_prod="S1"),
                Affiliation(department="DeptB", line="L1", user_sdwt_prod="S1"),
                Affiliation(department="DeptA", line="L1", user_sdwt_prod="S2"),
                Affiliation(department="DeptA", line="L2", user_sdwt_prod="S0"),
                Affiliation(department="DeptA", line="L3", user_sdwt_prod=""),
            ],
            ignore_conflicts=True,
        )

        rows = list_line_sdwt_pairs()
        self.assertEqual(
            rows,
            [
                {"line_id": "L1", "user_sdwt_prod": "S1"},
                {"line_id": "L1", "user_sdwt_prod": "S2"},
                {"line_id": "L2", "user_sdwt_prod": "S0"},
            ],
        )


class AccessibleUserSdwtProdTests(TestCase):
    def test_pending_change_included_when_no_current_affiliation(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S42000",
            password="test-password",
            knox_id="knox-42000",
        )

        UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod=None,
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        accessible = get_accessible_user_sdwt_prods_for_user(user)
        self.assertEqual(accessible, {"group-new"})

    def test_pending_change_ignored_when_current_affiliation_exists(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S42001",
            password="test-password",
            knox_id="knox-42001",
        )
        user.user_sdwt_prod = "group-old"
        user.save(update_fields=["user_sdwt_prod"])

        UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=user,
        )

        accessible = get_accessible_user_sdwt_prods_for_user(user)
        self.assertIn("group-old", accessible)
        self.assertNotIn("group-new", accessible)


class AffiliationChangeApprovalTests(TestCase):
    def test_manager_can_approve_and_preserves_effective_from(self) -> None:
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10000",
            password="test-password",
            knox_id="knox-10000",
        )
        requester.user_sdwt_prod = "group-old"
        requester.save(update_fields=["user_sdwt_prod"])

        manager = User.objects.create_user(
            sabun="S20000",
            password="test-password",
            knox_id="knox-20000",
        )
        UserSdwtProdAccess.objects.create(user=manager, user_sdwt_prod="group-new", can_manage=True)

        past = timezone.now() - timedelta(days=7)
        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=past,
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        _payload, status_code = approve_affiliation_change(approver=manager, change_id=change.id)

        self.assertEqual(status_code, 200)
        change.refresh_from_db()
        requester.refresh_from_db()

        self.assertEqual(requester.user_sdwt_prod, "group-new")
        self.assertTrue(change.approved)
        self.assertTrue(change.applied)
        self.assertEqual(change.status, UserSdwtProdChange.Status.APPROVED)
        self.assertEqual(change.approved_by_id, manager.id)
        self.assertIsNotNone(change.approved_at)
        self.assertEqual(change.effective_from, past)

    def test_non_manager_cannot_approve(self) -> None:
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S10001",
            password="test-password",
            knox_id="knox-10001",
        )
        requester.user_sdwt_prod = "group-old"
        requester.save(update_fields=["user_sdwt_prod"])

        other = User.objects.create_user(
            sabun="S30000",
            password="test-password",
            knox_id="knox-30000",
        )

        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now() - timedelta(days=1),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        _payload, status_code = approve_affiliation_change(approver=other, change_id=change.id)
        self.assertEqual(status_code, 403)
        requester.refresh_from_db()
        self.assertEqual(requester.user_sdwt_prod, "group-old")


class AffiliationChangeSelectorTests(TestCase):
    def test_resolve_user_affiliation_ignores_unapproved_change(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S40000",
            password="test-password",
            knox_id="knox-40000",
        )
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["user_sdwt_prod"])

        UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now() - timedelta(days=1),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
        )

        affiliation = resolve_user_affiliation(user, timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], "group-a")

    def test_get_next_user_sdwt_prod_change_ignores_unapproved_change(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S40001",
            password="test-password",
            knox_id="knox-40001",
        )
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["user_sdwt_prod"])

        now = timezone.now()
        UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-b",
            effective_from=now + timedelta(days=1),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
        )

        approved_change = UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-c",
            effective_from=now + timedelta(days=2),
            status=UserSdwtProdChange.Status.APPROVED,
            applied=True,
            approved=True,
        )

        next_change = get_next_user_sdwt_prod_change(user=user, effective_from=now)
        self.assertIsNotNone(next_change)
        self.assertEqual(next_change.id, approved_change.id)


class AffiliationChangeRequestListTests(TestCase):
    def test_manager_only_sees_manageable_groups(self) -> None:
        User = get_user_model()
        manager = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            knox_id="knox-90000",
        )
        UserSdwtProdAccess.objects.create(user=manager, user_sdwt_prod="group-a", can_manage=True)

        requester_a = User.objects.create_user(
            sabun="S90001",
            password="test-password",
            knox_id="knox-90001",
        )
        requester_b = User.objects.create_user(
            sabun="S90002",
            password="test-password",
            knox_id="knox-90002",
        )

        change_a = UserSdwtProdChange.objects.create(
            user=requester_a,
            to_user_sdwt_prod="group-a",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester_a,
        )
        UserSdwtProdChange.objects.create(
            user=requester_b,
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester_b,
        )

        payload, status_code = get_affiliation_change_requests(
            user=manager,
            status="pending",
            search=None,
            user_sdwt_prod=None,
            page=1,
            page_size=20,
        )

        self.assertEqual(status_code, 200)
        ids = [entry["id"] for entry in payload["results"]]
        self.assertIn(change_a.id, ids)
        self.assertEqual(len(ids), 1)

    def test_search_filters_by_sabun(self) -> None:
        User = get_user_model()
        manager = User.objects.create_user(
            sabun="S91000",
            password="test-password",
            knox_id="knox-91000",
        )
        UserSdwtProdAccess.objects.create(user=manager, user_sdwt_prod="group-c", can_manage=True)

        requester = User.objects.create_user(
            sabun="S91001",
            password="test-password",
            knox_id="knox-91001",
        )
        change = UserSdwtProdChange.objects.create(
            user=requester,
            to_user_sdwt_prod="group-c",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        payload, status_code = get_affiliation_change_requests(
            user=manager,
            status="pending",
            search="S91001",
            user_sdwt_prod=None,
            page=1,
            page_size=20,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["results"][0]["id"], change.id)
        self.assertEqual(payload["results"][0]["user"]["sabun"], "S91001")

    def test_non_manager_is_forbidden(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S92000",
            password="test-password",
            knox_id="knox-92000",
        )

        payload, status_code = get_affiliation_change_requests(
            user=user,
            status="pending",
            search=None,
            user_sdwt_prod=None,
            page=1,
            page_size=20,
        )

        self.assertEqual(status_code, 403)
        self.assertEqual(payload["error"], "forbidden")

    def test_non_manager_can_view_own_group_requests(self) -> None:
        User = get_user_model()
        requester = User.objects.create_user(
            sabun="S93000",
            password="test-password",
            knox_id="knox-93000",
        )
        requester.user_sdwt_prod = "group-own"
        requester.save(update_fields=["user_sdwt_prod"])

        change = UserSdwtProdChange.objects.create(
            user=requester,
            to_user_sdwt_prod="group-own",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=requester,
        )

        payload, status_code = get_affiliation_change_requests(
            user=requester,
            status="pending",
            search=None,
            user_sdwt_prod="group-own",
            page=1,
            page_size=20,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(payload["results"][0]["id"], change.id)
        self.assertFalse(payload["canManage"])


class AffiliationChangeRequestTests(TestCase):
    def test_request_affiliation_change_respects_effective_from_for_all(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50000",
            password="test-password",
            knox_id="knox-50000",
        )
        user.user_sdwt_prod = "group-old"
        user.save(update_fields=["user_sdwt_prod"])

        option = Affiliation.objects.create(department="Dept", line="Line", user_sdwt_prod="group-new")
        requested_effective_from = timezone.now() - timedelta(days=30)

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=requested_effective_from,
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 202)
        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.effective_from, requested_effective_from)
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)


class AccountOverviewTests(TestCase):
    def test_account_overview_includes_profile_history_and_mailbox(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S90000",
            password="test-password",
            knox_id="knox-90000",
        )
        user.username = "Tester"
        user.knox_id = "KNOX-90000"
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["username", "knox_id", "user_sdwt_prod"])

        profile, _created = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.Roles.MANAGER
        profile.save(update_fields=["role"])
        UserSdwtProdAccess.objects.create(user=user, user_sdwt_prod="group-b", can_manage=True)

        change = UserSdwtProdChange.objects.create(
            user=user,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-a",
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now(),
            status=UserSdwtProdChange.Status.APPROVED,
            applied=True,
            approved=True,
            created_by=user,
            approved_by=user,
        )

        Email.objects.create(
            message_id="msg-90000",
            received_at=timezone.now(),
            subject="Test",
            sender="tester@example.com",
            sender_id="KNOX-90000",
            recipient=["target@example.com"],
            user_sdwt_prod="group-a",
            classification_source=Email.ClassificationSource.CONFIRMED_USER,
            rag_index_status=Email.RagIndexStatus.INDEXED,
            body_text="hello",
        )

        payload = get_account_overview(user=user, timezone_name="Asia/Seoul")

        self.assertEqual(payload["user"]["role"], UserProfile.Roles.MANAGER)
        self.assertTrue(payload["affiliationHistory"])
        self.assertEqual(payload["affiliationHistory"][0]["id"], change.id)

        mailboxes = {row["userSdwtProd"] for row in payload["mailboxAccess"]}
        self.assertIn("group-a", mailboxes)
        self.assertIn("group-b", mailboxes)

        group_a_row = next(row for row in payload["mailboxAccess"] if row["userSdwtProd"] == "group-a")
        self.assertEqual(group_a_row["myEmailCount"], 1)

    def test_request_affiliation_change_defaults_to_request_time(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50001",
            password="test-password",
            is_staff=True,
            knox_id="knox-50001",
        )
        user.user_sdwt_prod = "group-old"
        user.save(update_fields=["user_sdwt_prod"])

        option = Affiliation.objects.create(department="Dept", line="Line", user_sdwt_prod="group-new")

        before = timezone.now()
        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=None,
            timezone_name="Asia/Seoul",
        )
        after = timezone.now()

        self.assertEqual(status_code, 202)
        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertGreaterEqual(change.effective_from, before)
        self.assertLessEqual(change.effective_from, after)
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)


class AffiliationOverviewTests(TestCase):
    def test_get_affiliation_overview_does_not_create_access_row(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S60000",
            password="test-password",
            knox_id="knox-60000",
        )
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["user_sdwt_prod"])

        self.assertEqual(UserSdwtProdAccess.objects.count(), 0)
        payload = get_affiliation_overview(user=user, timezone_name="Asia/Seoul")
        self.assertEqual(UserSdwtProdAccess.objects.count(), 0)

        self.assertEqual(payload["currentUserSdwtProd"], "group-a")
        self.assertEqual(payload["accessibleUserSdwtProds"][0]["userSdwtProd"], "group-a")


class AffiliationJiraKeyPermissionTests(TestCase):
    def setUp(self) -> None:
        Affiliation.objects.create(department="Dept", line="L1", user_sdwt_prod="S1")

    def test_jira_key_update_requires_superuser(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S60001",
            password="test-password",
            knox_id="knox-60001",
        )
        superuser = User.objects.create_superuser(
            sabun="S60002",
            password="test-password",
            knox_id="knox-60002",
        )

        url = reverse("account-affiliation-jira-key")

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.post(url, data={"lineId": "L1", "jiraKey": "PROJ"}, format="json")
        self.assertEqual(resp.status_code, 403)

        client.force_authenticate(user=superuser)
        resp = client.post(url, data={"lineId": "L1", "jiraKey": "PROJ"}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_request_affiliation_change_creates_pending_for_first_affiliation(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(
            sabun="S50001",
            password="test-password",
            knox_id="knox-50001",
        )

        option = Affiliation.objects.create(department="Dept", line="Line", user_sdwt_prod="group-new")

        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now() - timedelta(days=30),
            timezone_name="Asia/Seoul",
        )

        self.assertEqual(status_code, 202)

        user.refresh_from_db()
        self.assertIsNone(user.user_sdwt_prod)

        change = UserSdwtProdChange.objects.get(user=user, to_user_sdwt_prod="group-new")
        self.assertFalse(change.approved)
        self.assertFalse(change.applied)
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)


class ExternalAffiliationSyncTests(TestCase):
    def test_sync_external_affiliations_flags_user_on_change(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S70001", password="test-password")
        user.knox_id = "loginid-ext-1"
        user.save(update_fields=["knox_id"])

        sync_external_affiliations(
            records=[
                {"knox_id": "loginid-ext-1", "user_sdwt_prod": "group-a", "source_updated_at": timezone.now()}
            ]
        )
        user.refresh_from_db()
        self.assertFalse(user.requires_affiliation_reconfirm)

        result = sync_external_affiliations(
            records=[
                {"knox_id": "loginid-ext-1", "user_sdwt_prod": "group-b", "source_updated_at": timezone.now()}
            ]
        )
        user.refresh_from_db()

        self.assertEqual(result["updated"], 1)
        self.assertTrue(user.requires_affiliation_reconfirm)

    def test_sync_external_affiliations_dedupes_knox_ids(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S70003", password="test-password")
        user.knox_id = "loginid-ext-3"
        user.save(update_fields=["knox_id"])

        ExternalAffiliationSnapshot.objects.create(
            knox_id="loginid-ext-3",
            predicted_user_sdwt_prod="group-a",
            source_updated_at=timezone.now(),
            last_seen_at=timezone.now(),
        )

        result = sync_external_affiliations(
            records=[
                {"knox_id": "loginid-ext-3", "user_sdwt_prod": "group-b", "source_updated_at": timezone.now()},
                {"knox_id": "loginid-ext-3", "user_sdwt_prod": "group-c", "source_updated_at": timezone.now()},
            ]
        )

        self.assertEqual(result["updated"], 1)
        user.refresh_from_db()
        self.assertTrue(user.requires_affiliation_reconfirm)
        snapshot = ExternalAffiliationSnapshot.objects.get(knox_id="loginid-ext-3")
        self.assertEqual(snapshot.predicted_user_sdwt_prod, "group-c")

    def test_reconfirm_response_creates_pending_change(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S70002", password="test-password")
        user.knox_id = "loginid-ext-2"
        user.requires_affiliation_reconfirm = True
        user.save(update_fields=["knox_id", "requires_affiliation_reconfirm"])

        Affiliation.objects.create(department="Dept", line="Line", user_sdwt_prod="group-a")

        sync_external_affiliations(
            records=[
                {"knox_id": "loginid-ext-2", "user_sdwt_prod": "group-a", "source_updated_at": timezone.now()}
            ]
        )

        payload, status_code = submit_affiliation_reconfirm_response(
            user=user,
            accepted=True,
            department="Dept",
            line="Line",
            user_sdwt_prod="group-a",
            timezone_name="Asia/Seoul",
        )
        self.assertEqual(status_code, 202)
        self.assertEqual(payload["status"], "pending")

        user.refresh_from_db()
        self.assertFalse(user.requires_affiliation_reconfirm)

        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertEqual(change.status, UserSdwtProdChange.Status.PENDING)
