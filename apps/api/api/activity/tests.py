from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from api.activity.models import ActivityLog


class ActivityLogEndpointTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(sabun="S70000", password="test-password")

    def test_activity_logs_requires_auth(self) -> None:
        response = self.client.get(reverse("activity-logs"))
        self.assertEqual(response.status_code, 401)

    def test_activity_logs_requires_permission(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("activity-logs"))
        self.assertEqual(response.status_code, 403)

    def test_activity_logs_returns_recent_entries(self) -> None:
        ActivityLog.objects.create(
            user=self.user,
            action="UPDATE",
            path="/api/v1/demo",
            method="PATCH",
            status_code=200,
            metadata={"note": "ok"},
        )

        permission = Permission.objects.get(
            content_type__app_label="activity",
            codename="view_activitylog",
        )
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)

        response = self.client.get(reverse("activity-logs"), {"limit": "5"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["action"], "UPDATE")
