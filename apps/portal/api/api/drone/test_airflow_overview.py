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
    AIRFLOW_BASE_URL="http://airflow-api-server:8080/airflow",
    AIRFLOW_PUBLIC_BASE_URL="/airflow",
    AIRFLOW_USERNAME="server-user",
    AIRFLOW_PASSWORD="server-password",
    AIRFLOW_REQUEST_TIMEOUT_SECONDS=7,
)
class AirflowOverviewServiceTests(SimpleTestCase):
    """Airflow client가 서버 설정만 사용해 overview를 구성하는지 검증합니다."""

    @patch("api.drone.services.airflow._get_access_token", return_value="server-token")
    @patch("api.drone.services.airflow._request_json")
    def test_overview_normalizes_dags_and_latest_run(self, mock_request_json: Mock, mock_token: Mock) -> None:
        """DAG 목록과 최근 실행을 기존 Web response shape로 변환합니다."""

        mock_request_json.side_effect = [
            {
                "dags": [
                    {
                        "dag_id": "daily report",
                        "description": "Daily report",
                        "is_paused": False,
                        "is_stale": False,
                        "owners": ["owner", None],
                        "tags": [{"name": "daily"}],
                        "timetable_description": "0 1 * * *",
                        "next_dagrun_logical_date": "2026-08-30T01:00:00Z",
                        "next_dagrun_run_after": "2026-08-31T01:00:00Z",
                    }
                ]
            },
            {
                "dag_runs": [
                    {
                        "dag_run_id": "scheduled__2026-08-29",
                        "state": "failed",
                        "logical_date": "2026-08-29T01:00:00Z",
                        "start_date": "2026-08-29T01:00:01Z",
                        "end_date": "2026-08-29T01:00:02Z",
                    }
                ]
            },
        ]

        payload = services.get_airflow_dag_overview()

        mock_token.assert_called_once_with("http://airflow-api-server:8080/airflow")
        self.assertEqual(payload["baseUrl"], "/airflow")
        self.assertEqual(payload["totals"], {"total": 1, "active": 1, "paused": 0, "failed": 1})
        self.assertEqual(payload["dags"][0]["dagId"], "daily report")
        self.assertEqual(payload["dags"][0]["owners"], ["owner"])
        self.assertEqual(payload["dags"][0]["tags"], ["daily"])
        self.assertEqual(payload["dags"][0]["nextRun"], "2026-08-30T01:00:00Z")
        self.assertEqual(payload["dags"][0]["nextRunCreateAfter"], "2026-08-31T01:00:00Z")
        self.assertEqual(payload["dags"][0]["latestRun"]["state"], "failed")
        latest_url = mock_request_json.call_args_list[1].args[0]
        self.assertIn("daily%20report", latest_url)
        self.assertEqual(payload["dags"][0]["latestRun"]["executionDate"], "2026-08-29T01:00:00Z")
        self.assertEqual(mock_request_json.call_args_list[1].kwargs, {"access_token": "server-token", "params": {"limit": 1, "order_by": "-run_after"}})

    @patch("api.drone.services.airflow.requests.get")
    def test_request_uses_server_side_bearer_token(self, mock_get: Mock) -> None:
        """Airflow 요청이 Django settings의 credential을 사용하는지 확인합니다."""

        response = Mock()
        response.json.return_value = {"dags": []}
        mock_get.return_value = response

        payload = airflow_client._request_json("http://airflow-api-server:8080/airflow/api/v2/dags", access_token="server-token")

        self.assertEqual(payload, {"dags": []})
        mock_get.assert_called_once_with(
            "http://airflow-api-server:8080/airflow/api/v2/dags",
            params=None,
            headers={"Accept": "application/json", "Authorization": "Bearer server-token"},
            timeout=7,
        )
        response.close.assert_called_once_with()

    def test_stale_dag_and_timetable_summary(self) -> None:
        """API v2에서 사라진 DAG는 비활성으로 표시하고 timetable 요약을 사용합니다."""
        dag = airflow_client._normalize_dag(
            {"dag_id": "removed", "is_stale": True, "is_paused": False, "timetable_summary": "@daily"}, None,
        )
        self.assertFalse(dag["isActive"])
        self.assertEqual(dag["timetable"], "@daily")

    @patch("api.drone.services.airflow.requests.post")
    def test_token_uses_server_credentials(self, mock_post: Mock) -> None:
        """인증값은 token 발급에만 사용하고 응답을 닫습니다."""
        response = mock_post.return_value
        response.json.return_value = {"access_token": "server-token"}
        self.assertEqual(airflow_client._get_access_token("http://airflow/airflow"), "server-token")
        mock_post.assert_called_once_with(
            "http://airflow/airflow/auth/token",
            json={"username": "server-user", "password": "server-password"},
            headers={"Accept": "application/json"}, timeout=7,
        )
        response.close.assert_called_once_with()

    @patch("api.drone.services.airflow.requests.post")
    def test_invalid_token_response_is_rejected(self, mock_post: Mock) -> None:
        """누락되거나 잘못된 token 응답은 API 요청으로 전달하지 않습니다."""
        for payload in ({}, {"access_token": " "}, {"access_token": 1}, []):
            with self.subTest(payload=payload):
                mock_post.return_value.json.return_value = payload
                with self.assertRaises(airflow_client.AirflowUpstreamError):
                    airflow_client._get_access_token("http://airflow/airflow")

    @patch("api.drone.services.airflow._request_json")
    def test_latest_run_failure_is_isolated(self, mock_request: Mock) -> None:
        """개별 DAG 실행 조회 실패는 전체 목록 조회를 막지 않습니다."""
        mock_request.side_effect = airflow_client.AirflowUpstreamError("unavailable")
        self.assertIsNone(airflow_client._fetch_latest_run("http://airflow", "daily", "token"))


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
