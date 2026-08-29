# =============================================================================
# 모듈: Line Dashboard Airflow backend proxy 회귀 테스트
# 주요 대상: 서버 credential 사용, 응답 정규화, 로그인 및 upstream 오류
# =============================================================================
"""브라우저에 Airflow credential을 노출하지 않는 proxy 계약을 검증합니다."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from api.drone import services
from api.drone.services import airflow as airflow_client
from api.drone.views import AirflowDagOverviewView


@override_settings(
    AIRFLOW_BASE_URL="http://airflow-webserver:8080",
    AIRFLOW_PUBLIC_BASE_URL="/airflow",
    AIRFLOW_USERNAME="server-user",
    AIRFLOW_PASSWORD="server-password",
    AIRFLOW_REQUEST_TIMEOUT_SECONDS=7,
)
class AirflowOverviewServiceTests(SimpleTestCase):
    """Airflow client가 서버 설정만 사용해 overview를 구성하는지 검증합니다."""

    @patch("api.drone.services.airflow._request_json")
    def test_overview_normalizes_dags_and_latest_run(self, mock_request_json: Mock) -> None:
        """DAG 목록과 최근 실행을 기존 Web response shape로 변환합니다."""

        mock_request_json.side_effect = [
            {
                "dags": [
                    {
                        "dag_id": "daily report",
                        "description": "Daily report",
                        "is_paused": False,
                        "is_active": True,
                        "owners": ["owner", None],
                        "tags": [{"name": "daily"}],
                        "timetable_description": "0 1 * * *",
                        "next_dagrun": "2026-08-30T01:00:00Z",
                    }
                ]
            },
            {
                "dag_runs": [
                    {
                        "dag_run_id": "scheduled__2026-08-29",
                        "state": "failed",
                        "execution_date": "2026-08-29T01:00:00Z",
                        "start_date": "2026-08-29T01:00:01Z",
                        "end_date": "2026-08-29T01:00:02Z",
                    }
                ]
            },
        ]

        payload = services.get_airflow_dag_overview()

        self.assertEqual(payload["baseUrl"], "/airflow")
        self.assertEqual(payload["totals"], {"total": 1, "active": 1, "paused": 0, "failed": 1})
        self.assertEqual(payload["dags"][0]["dagId"], "daily report")
        self.assertEqual(payload["dags"][0]["owners"], ["owner"])
        self.assertEqual(payload["dags"][0]["tags"], ["daily"])
        self.assertEqual(payload["dags"][0]["latestRun"]["state"], "failed")
        latest_url = mock_request_json.call_args_list[1].args[0]
        self.assertIn("daily%20report", latest_url)

    @patch("api.drone.services.airflow.requests.get")
    def test_request_uses_server_side_basic_auth(self, mock_get: Mock) -> None:
        """Airflow 요청이 Django settings의 credential을 사용하는지 확인합니다."""

        response = Mock()
        response.json.return_value = {"dags": []}
        mock_get.return_value = response

        payload = airflow_client._request_json("http://airflow-webserver:8080/api/v1/dags")

        self.assertEqual(payload, {"dags": []})
        mock_get.assert_called_once_with(
            "http://airflow-webserver:8080/api/v1/dags",
            params=None,
            auth=("server-user", "server-password"),
            headers={"Accept": "application/json"},
            timeout=7,
        )
        response.close.assert_called_once_with()


class AirflowDagOverviewViewTests(SimpleTestCase):
    """Airflow overview endpoint의 로그인과 오류 변환을 검증합니다."""

    def setUp(self) -> None:
        """DRF request factory를 준비합니다."""

        self.factory = APIRequestFactory()

    def test_anonymous_user_is_rejected(self) -> None:
        """로그인하지 않은 사용자는 Airflow proxy를 호출할 수 없습니다."""

        request = self.factory.get("/api/v1/line-dashboard/airflow/dag-overview")
        response = AirflowDagOverviewView.as_view()(request)

        self.assertEqual(response.status_code, 401)

    @patch("api.account.services.get_access_payload", return_value={"allowed": True})
    @patch("api.drone.views.airflow.services.get_airflow_dag_overview")
    def test_authenticated_user_receives_overview(
        self,
        mock_overview: Mock,
        _mock_access: Mock,
    ) -> None:
        """로그인 사용자는 credential 없이 정규화된 결과만 받습니다."""

        mock_overview.return_value = {
            "baseUrl": "/airflow",
            "fetchedAt": "2026-08-29T00:00:00Z",
            "totals": {"total": 0, "active": 0, "paused": 0, "failed": 0},
            "dags": [],
        }
        request = self.factory.get("/api/v1/line-dashboard/airflow/dag-overview")
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))

        response = AirflowDagOverviewView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"password", response.content.lower())
        mock_overview.assert_called_once_with()

    @patch("api.account.services.get_access_payload", return_value={"allowed": True})
    @patch("api.drone.views.airflow.services.get_airflow_dag_overview")
    def test_upstream_failure_returns_bad_gateway(
        self,
        mock_overview: Mock,
        _mock_access: Mock,
    ) -> None:
        """Airflow 목록 조회 실패는 외부 연동 오류인 502로 변환합니다."""

        mock_overview.side_effect = services.AirflowUpstreamError("upstream failed")
        request = self.factory.get("/api/v1/line-dashboard/airflow/dag-overview")
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True))

        response = AirflowDagOverviewView.as_view()(request)

        self.assertEqual(response.status_code, 502)
