"""Observer canonical 로그 조회 API입니다."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from rest_framework.views import APIView

from . import selectors
from ._shared import _log_query_options, _required_query_id
from api.observer import serializers as observer_serializers


class ObserverLogsPageView(APIView):
    """유형별 compact log 첫 페이지를 한 번에 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """Observer 최초 화면용 bounded log page를 반환합니다.

        예시 요청:
        - GET /api/v1/observer/logs/page?eqpId=EQP-1&from=2026-07-01&to=2026-07-07

        snake/camel 호환:
        - eqpId/pageSize만 지원합니다.
        """

        query = observer_serializers.ObserverLogPageQuerySerializer(data=request.GET)
        if not query.is_valid():
            return JsonResponse(
                {"error": "invalid_query", "details": query.errors},
                status=400,
            )

        values = query.validated_data
        payload = selectors.get_log_pages(
            eqp_id=values["eqp_id"],
            log_types=values["log_types"],
            start_at=values["start_at"],
            end_at=values["end_at"],
            page_size=values["pageSize"],
            range_key=values["range_key"],
        )
        status = 503 if payload["meta"]["allFailed"] else 200
        return JsonResponse(payload, status=status)


class ObserverLogsByTypePageView(APIView):
    """지정된 log type의 compact page를 반환합니다."""

    def get(
        self,
        request: HttpRequest,
        log_key: str,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """유형별 cursor page를 반환합니다.

        예시 요청:
        - GET /api/v1/observer/logs/tip/page?eqpId=EQP-1&from=2026-07-01&to=2026-07-07&pageSize=250

        snake/camel 호환:
        - eqpId/pageSize만 지원합니다.
        """

        type_key = str(log_key or "").strip().lower()
        if type_key not in observer_serializers.OBSERVER_LOG_TYPES:
            return JsonResponse({"error": "unsupported_log_type"}, status=404)

        query = observer_serializers.ObserverLogPageQuerySerializer(
            data=request.GET,
            context={"log_type": type_key},
        )
        if not query.is_valid():
            return JsonResponse(
                {"error": "invalid_query", "details": query.errors},
                status=400,
            )

        values = query.validated_data
        payload = selectors.get_log_page(
            eqp_id=values["eqp_id"],
            log_key=type_key,
            start_at=values["start_at"],
            end_at=values["end_at"],
            page_size=values["pageSize"],
            range_key=values["range_key"],
            cursor_payload=values["cursor_payload"],
        )
        return JsonResponse(payload)


class ObserverLogDetailView(APIView):
    """선택된 compact log의 상세 payload를 반환합니다."""

    def get(
        self,
        request: HttpRequest,
        log_key: str,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """설비와 source PK가 일치하는 상세 log를 반환합니다.

        예시 요청:
        - GET /api/v1/observer/logs/esop/detail?eqpId=EQP-1&logId=123

        snake/camel 호환:
        - eqpId/logId만 지원합니다.
        """

        type_key = str(log_key or "").strip().lower()
        if type_key not in observer_serializers.OBSERVER_LOG_TYPES:
            return JsonResponse({"error": "unsupported_log_type"}, status=404)

        query = observer_serializers.ObserverLogDetailQuerySerializer(
            data=request.GET
        )
        if not query.is_valid():
            return JsonResponse(
                {"error": "invalid_query", "details": query.errors},
                status=400,
            )

        values = query.validated_data
        payload = selectors.get_log_detail(
            eqp_id=values["eqpId"],
            log_key=type_key,
            log_id=values["logId"],
        )
        if payload is None:
            return JsonResponse({"error": "log_not_found"}, status=404)
        return JsonResponse(payload)


class ObserverEvidenceLogView(APIView):
    """AI 분석에 사용된 근거 로그 한 건을 복원합니다."""

    def get(
        self,
        request: HttpRequest,
        log_key: str,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """분석 당시 설비·범위·event ID가 일치하는 로그를 반환합니다.

        예시 요청:
        - GET /api/v1/observer/logs/eqp/evidence?eqpId=EQP-1&from=2026-08-01&to=2026-08-03&evidenceId=EQP:1

        snake/camel 호환:
        - eqpId/evidenceId/from/to만 지원합니다.
        """

        type_key = str(log_key or "").strip().lower()
        if type_key not in observer_serializers.OBSERVER_LOG_TYPES:
            return JsonResponse({"error": "unsupported_log_type"}, status=404)

        query = observer_serializers.ObserverEvidenceLogQuerySerializer(
            data=request.GET
        )
        if not query.is_valid():
            return JsonResponse(
                {"error": "invalid_query", "details": query.errors},
                status=400,
            )

        values = query.validated_data
        payload = selectors.get_analysis_evidence_log(
            eqp_id=values["eqp_id"],
            log_key=type_key,
            evidence_id=values["evidence_id"],
            start_at=values["start_at"],
            end_at=values["end_at"],
        )
        if payload is None:
            return JsonResponse({"error": "evidence_log_not_found"}, status=404)
        return JsonResponse(payload)
