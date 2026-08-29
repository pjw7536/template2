# =============================================================================
# 모듈: Line Dashboard Airflow HTTP endpoint
# 주요 기능: 로그인 사용자의 DAG overview 요청을 service에 위임
# =============================================================================
"""Airflow credential을 노출하지 않는 Line Dashboard proxy endpoint입니다."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from .. import services
from ._shared import DroneAuthenticatedView


class AirflowDagOverviewView(DroneAuthenticatedView):
    """로그인 사용자에게 Airflow DAG overview를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """Django 서버가 Airflow를 조회한 결과를 반환합니다.

        요청 예시:
            GET /api/v1/line-dashboard/airflow/dag-overview

        반환:
            200 ``{"baseUrl":"/airflow","totals":{},"dags":[]}``

        부작용:
            Airflow REST API 조회가 발생합니다.

        오류:
            401: 로그인하지 않은 사용자.
            502: Airflow REST API 호출 실패.
            503: 서버 Airflow 설정 누락.
        """

        auth_response = self._authorize_user(request)
        if auth_response is not None:
            return auth_response

        try:
            return JsonResponse(services.get_airflow_dag_overview())
        except services.AirflowConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=503)
        except services.AirflowUpstreamError:
            return JsonResponse({"error": "Airflow API 정보를 불러오지 못했습니다."}, status=502)


__all__ = ["AirflowDagOverviewView"]
