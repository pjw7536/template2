from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from api.account.models import Affiliation, UserSdwtProdAccess, UserSdwtProdChange
from api.account.selectors import (
    get_next_user_sdwt_prod_change,
    list_affiliation_options,
    list_line_sdwt_pairs,
    resolve_user_affiliation,
)
from api.account.services import approve_affiliation_change, request_affiliation_change


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

    def test_list_line_sdwt_pairs_dedupes_across_departments(self) -> None:
        Affiliation.objects.create(department="DeptA", line="L1", user_sdwt_prod="S1")
        Affiliation.objects.create(department="DeptB", line="L1", user_sdwt_prod="S1")
        Affiliation.objects.create(department="DeptA", line="L1", user_sdwt_prod="S2")
        Affiliation.objects.create(department="DeptA", line="L2", user_sdwt_prod="S0")
        Affiliation.objects.create(department="DeptA", line="L3", user_sdwt_prod="")

        rows = list_line_sdwt_pairs()
        self.assertEqual(
            rows,
            [
                {"line_id": "L1", "user_sdwt_prod": "S1"},
                {"line_id": "L1", "user_sdwt_prod": "S2"},
                {"line_id": "L2", "user_sdwt_prod": "S0"},
            ],
        )


class AffiliationChangeApprovalTests(TestCase):
    def test_manager_can_approve_and_effective_from_is_approval_time(self) -> None:
        User = get_user_model()
        requester = User.objects.create_user(sabun="S10000", password="test-password")
        requester.user_sdwt_prod = "group-old"
        requester.save(update_fields=["user_sdwt_prod"])

        manager = User.objects.create_user(sabun="S20000", password="test-password")
        UserSdwtProdAccess.objects.create(user=manager, user_sdwt_prod="group-new", can_manage=True)

        past = timezone.now() - timedelta(days=7)
        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=past,
            applied=False,
            approved=False,
            created_by=requester,
        )

        before = timezone.now()
        _payload, status_code = approve_affiliation_change(approver=manager, change_id=change.id)
        after = timezone.now()

        self.assertEqual(status_code, 200)
        change.refresh_from_db()
        requester.refresh_from_db()

        self.assertEqual(requester.user_sdwt_prod, "group-new")
        self.assertTrue(change.approved)
        self.assertTrue(change.applied)
        self.assertEqual(change.approved_by_id, manager.id)
        self.assertIsNotNone(change.approved_at)
        self.assertEqual(change.effective_from, change.approved_at)
        self.assertNotEqual(change.effective_from, past)
        self.assertGreaterEqual(change.effective_from, before)
        self.assertLessEqual(change.effective_from, after)

    def test_non_manager_cannot_approve(self) -> None:
        User = get_user_model()
        requester = User.objects.create_user(sabun="S10001", password="test-password")
        requester.user_sdwt_prod = "group-old"
        requester.save(update_fields=["user_sdwt_prod"])

        other = User.objects.create_user(sabun="S30000", password="test-password")

        change = UserSdwtProdChange.objects.create(
            user=requester,
            department="Dept",
            line="Line",
            from_user_sdwt_prod="group-old",
            to_user_sdwt_prod="group-new",
            effective_from=timezone.now() - timedelta(days=1),
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
        user = User.objects.create_user(sabun="S40000", password="test-password")
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["user_sdwt_prod"])

        UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-b",
            effective_from=timezone.now() - timedelta(days=1),
            applied=False,
            approved=False,
        )

        affiliation = resolve_user_affiliation(user, timezone.now())
        self.assertEqual(affiliation["user_sdwt_prod"], "group-a")

    def test_get_next_user_sdwt_prod_change_ignores_unapproved_change(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S40001", password="test-password")
        user.user_sdwt_prod = "group-a"
        user.save(update_fields=["user_sdwt_prod"])

        now = timezone.now()
        UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-b",
            effective_from=now + timedelta(days=1),
            applied=False,
            approved=False,
        )

        approved_change = UserSdwtProdChange.objects.create(
            user=user,
            to_user_sdwt_prod="group-c",
            effective_from=now + timedelta(days=2),
            applied=True,
            approved=True,
        )

        next_change = get_next_user_sdwt_prod_change(user=user, effective_from=now)
        self.assertIsNotNone(next_change)
        self.assertEqual(next_change.id, approved_change.id)


class AffiliationChangeRequestTests(TestCase):
    def test_request_affiliation_change_ignores_effective_from_for_non_staff(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S50000", password="test-password")
        user.user_sdwt_prod = "group-old"
        user.save(update_fields=["user_sdwt_prod"])

        option = Affiliation.objects.create(department="Dept", line="Line", user_sdwt_prod="group-new")
        requested_effective_from = timezone.now() - timedelta(days=30)

        before = timezone.now()
        payload, status_code = request_affiliation_change(
            user=user,
            option=option,
            to_user_sdwt_prod="group-new",
            effective_from=requested_effective_from,
            timezone_name="Asia/Seoul",
        )
        after = timezone.now()

        self.assertEqual(status_code, 202)
        change = UserSdwtProdChange.objects.get(id=payload["changeId"])
        self.assertNotEqual(change.effective_from, requested_effective_from)
        self.assertGreaterEqual(change.effective_from, before)
        self.assertLessEqual(change.effective_from, after)
