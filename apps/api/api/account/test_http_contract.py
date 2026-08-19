"""Account HTTP camelCase와 공통 오류 계약 회귀 테스트입니다."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Affiliation


class AccountHttpContractTests(TestCase):
    """남아 있던 소속 재확인·외부 sync snake_case 입력을 거절합니다."""

    def test_reconfirm_rejects_snake_case_input(self) -> None:
        """브라우저 재확인 body는 userSdwtProd만 허용합니다."""

        user = get_user_model().objects.create_user(
            sabun="ACCOUNT-HTTP-1",
            password="test-password",
            knox_id="account.http.1",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("account-affiliation-reconfirm"),
            data={"accepted": True, "user_sdwt_prod": "group-a"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["fieldErrors"]["unexpectedFields"],
            ["user_sdwt_prod"],
        )

    def test_affiliation_options_use_camel_case(self) -> None:
        """소속 선택 옵션 성공 응답은 내부 model field 이름을 노출하지 않습니다."""

        user = get_user_model().objects.create_user(
            sabun="ACCOUNT-HTTP-OPTIONS",
            password="test-password",
            knox_id="account.http.options",
        )
        Affiliation.objects.create(
            department="Dept",
            line="L1",
            user_sdwt_prod="group-a",
            is_active=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("account-affiliation"))

        self.assertEqual(response.status_code, 200)
        option = response.json()["affiliationOptions"][0]
        self.assertEqual(option["userSdwtProd"], "group-a")
        self.assertNotIn("user_sdwt_prod", option)

    @override_settings(AIRFLOW_TRIGGER_TOKEN="token")
    def test_external_sync_rejects_snake_case_input(self) -> None:
        """Airflow sync record도 camelCase field만 허용합니다."""

        response = self.client.post(
            reverse("account-external-affiliation-sync"),
            data={
                "records": [
                    {
                        "knox_id": "account.http.2",
                        "department": "Dept",
                        "user_sdwt_prod": "group-a",
                    }
                ]
            },
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer token",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["fieldErrors"]["records"][0]["unexpectedFields"],
            ["knox_id", "user_sdwt_prod"],
        )
