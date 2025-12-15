from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthMeTests(TestCase):
    def test_auth_me_requires_login(self) -> None:
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "unauthorized"})

    def test_auth_me_returns_username_as_name_and_knox_id_as_usr_id(self) -> None:
        User = get_user_model()
        user = User.objects.create_user(sabun="S12345", password="test-password")
        user.knox_id = "KNOX-12345"
        user.username = "홍길동"
        user.first_name = "John"
        user.last_name = "Doe"
        user.email = "hong@example.com"
        user.save(update_fields=["knox_id", "username", "first_name", "last_name", "email"])

        self.client.force_login(user)

        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["usr_id"], "KNOX-12345")
        self.assertEqual(payload["username"], "홍길동")
        self.assertEqual(payload["name"], "홍길동")
        self.assertEqual(payload["email"], "hong@example.com")
