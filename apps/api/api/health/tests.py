# =============================================================================
# 모듈 설명: health 엔드포인트 테스트를 제공합니다.
# - 주요 대상: HealthView
# - 불변 조건: URL 네임(health)이 등록되어 있어야 합니다.
# =============================================================================

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    """헬스 체크 엔드포인트를 검증합니다."""

    def test_health_returns_ok(self) -> None:
        """헬스 체크 응답이 정상인지 확인합니다."""
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
