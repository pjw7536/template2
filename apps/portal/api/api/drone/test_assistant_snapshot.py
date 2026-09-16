# =============================================================================
# 모듈: Line Dashboard Assistant snapshot 회귀 테스트
# 주요 대상: get_line_dashboard_assistant_snapshot
# 주요 가정: snapshot은 표와 같은 line·시간 범위를 사용하고 개인정보를 제외합니다.
# =============================================================================
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from api.drone import selectors
from api.drone.models import DroneSOP, DroneSopTarget


class DroneAssistantSnapshotTests(TestCase):
    """ESOP Assistant snapshot의 범위와 공개 field를 검증합니다."""

    def test_snapshot_limits_scope_and_excludes_personal_fields(self) -> None:
        """line·기간을 적용하고 사용자·댓글 field를 응답에서 제외합니다."""

        included = DroneSOP.objects.create(
            line_id="L1",
            eqp_id="EQP-1",
            chamber_ids="A",
            lot_id="LOT-1",
            main_step="STEP-1",
            status="RUN",
            knox_id="private-user",
            comment="private-comment",
        )
        DroneSOP.objects.create(
            line_id="L2",
            eqp_id="EQP-2",
            chamber_ids="B",
            lot_id="LOT-2",
            main_step="STEP-2",
            status="DOWN",
        )
        today = timezone.localdate().isoformat()

        payload = selectors.get_line_dashboard_assistant_snapshot(
            line_id="l1",
            view="status",
            from_value=today,
            to_value=today,
            line_filter_mode="target_user_sdwt_prod",
            recent_hours_start=8,
            recent_hours_end=0,
        )

        self.assertEqual(payload["totalCount"], 1)
        self.assertEqual(payload["statusCounts"], [{"status": "RUN", "count": 1}])
        self.assertEqual(payload["recentRows"][0]["id"], included.id)
        self.assertNotIn("knoxId", payload["recentRows"][0])
        self.assertNotIn("comment", payload["recentRows"][0])

    def test_snapshot_matches_status_line_and_recent_hour_filters(self) -> None:
        """status 표와 같은 target mapping·최근 시간 범위를 적용합니다."""

        DroneSopTarget.objects.create(
            line_id="L1",
            target_user_sdwt_prod="TARGET-A",
        )
        now = timezone.now()
        mapped_recent = DroneSOP.objects.create(
            line_id="OTHER",
            target_user_sdwt_prod="target-a",
            lot_id="LOT-MAPPED-RECENT",
            status="MAPPED",
        )
        direct_recent = DroneSOP.objects.create(
            line_id="l1",
            target_user_sdwt_prod="OTHER",
            lot_id="LOT-DIRECT-RECENT",
            status="DIRECT",
        )
        mapped_old = DroneSOP.objects.create(
            line_id="OTHER",
            target_user_sdwt_prod="TARGET-A",
            lot_id="LOT-MAPPED-OLD",
            status="OLD",
        )
        DroneSOP.objects.filter(pk=mapped_recent.pk).update(created_at=now - timedelta(hours=4))
        DroneSOP.objects.filter(pk=direct_recent.pk).update(created_at=now - timedelta(hours=2))
        DroneSOP.objects.filter(pk=mapped_old.pk).update(created_at=now - timedelta(hours=12))

        with patch("api.drone.selectors.assistant.timezone.now", return_value=now):
            payload = selectors.get_line_dashboard_assistant_snapshot(
                line_id="l1",
                view="status",
                from_value=(timezone.localdate() - timedelta(days=1)).isoformat(),
                to_value=timezone.localdate().isoformat(),
                line_filter_mode="target_user_sdwt_prod",
                recent_hours_start=8,
                recent_hours_end=0,
            )

        self.assertEqual(payload["totalCount"], 2)
        self.assertEqual(
            {row["id"] for row in payload["recentRows"]},
            {mapped_recent.id, direct_recent.id},
        )
        self.assertEqual(payload["lineFilterMode"], "target_user_sdwt_prod")
        self.assertEqual(payload["recentHoursStart"], 8)
        self.assertEqual(payload["recentHoursEnd"], 0)
