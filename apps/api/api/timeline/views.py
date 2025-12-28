"""Dummy timeline endpoints used by the frontend timeline feature."""
from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from rest_framework.views import APIView

from . import selectors


class TimelineLinesView(APIView):
    """더미 라인 목록을 반환합니다.

    Returns dummy line data.
    """

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        return JsonResponse(selectors.list_lines(), safe=False)


class TimelineSdwtView(APIView):
    """라인 기준 SDWT 목록을 반환합니다.

    Returns SDWT list for a line.
    """

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        line_id = selectors.normalize_id(request.GET.get("lineId"))
        if not line_id:
            return JsonResponse({"error": "lineId is required"}, status=400)

        return JsonResponse(selectors.list_sdwt_for_line(line_id=line_id), safe=False)


class TimelinePrcGroupView(APIView):
    """라인/SDWT 조합 기준 PRC 그룹 목록을 반환합니다.

    Returns PRC group list for a line/SDWT pair.
    """

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        line_id = selectors.normalize_id(request.GET.get("lineId"))
        sdwt_id = selectors.normalize_id(request.GET.get("sdwtId"))

        if not line_id or not sdwt_id:
            return JsonResponse({"error": "lineId and sdwtId are required"}, status=400)

        return JsonResponse(selectors.list_prc_groups(line_id=line_id, sdwt_id=sdwt_id), safe=False)


class TimelineEquipmentsView(APIView):
    """라인/SDWT/PRC 그룹 조합 기준 설비 목록을 반환합니다.

    Returns equipment list for a line/SDWT/PRC group.
    """

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        line_id = selectors.normalize_id(request.GET.get("lineId"))
        sdwt_id = selectors.normalize_id(request.GET.get("sdwtId"))
        prc_group = selectors.normalize_id(request.GET.get("prcGroup"))

        if not line_id or not sdwt_id or not prc_group:
            return JsonResponse(
                {"error": "lineId, sdwtId, and prcGroup are required"}, status=400
            )

        return JsonResponse(
            selectors.list_equipments(line_id=line_id, sdwt_id=sdwt_id, prc_group=prc_group),
            safe=False,
        )


class TimelineEquipmentInfoView(APIView):
    """eqpId 기준 설비 메타데이터를 반환합니다(선택적으로 line 범위 제한).

    Returns equipment metadata by eqpId, optionally scoped by line.
    """

    def get(
        self,
        request: HttpRequest,
        line_id: str | None = None,
        eqp_id: str | None = None,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        eqp_key = selectors.normalize_id(eqp_id)
        if not eqp_key:
            return JsonResponse({"error": "eqpId is required"}, status=400)

        info = selectors.get_equipment_info(eqp_id=eqp_key)
        if not info:
            return JsonResponse({"error": "Equipment not found"}, status=404)

        if line_id and selectors.normalize_id(line_id) != selectors.normalize_id(info["lineId"]):
            return JsonResponse({"error": "Equipment not found for line"}, status=404)

        return JsonResponse(info)


class _TimelineLogsByTypeView(APIView):
    """log_key에 해당하는 더미 로그 배열을 반환하는 베이스 뷰입니다."""

    log_key: str = ""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        eqp_id = selectors.normalize_id(request.GET.get("eqpId"))
        if not eqp_id:
            return JsonResponse({"error": "eqpId is required"}, status=400)

        return JsonResponse(selectors.get_logs_by_type(eqp_id=eqp_id, log_key=self.log_key), safe=False)


class TimelineLogsView(_TimelineLogsByTypeView):
    """설비의 전체 로그를 타입별로 합쳐 반환합니다.

    Returns merged logs for an equipment.
    """

    log_key = ""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        eqp_id = selectors.normalize_id(request.GET.get("eqpId"))
        if not eqp_id:
            return JsonResponse({"error": "eqpId is required"}, status=400)

        return JsonResponse(selectors.get_merged_logs(eqp_id=eqp_id), safe=False)


class TimelineEqpLogsView(_TimelineLogsByTypeView):
    """설비(EQP) 타입 로그만 반환합니다."""

    log_key = "eqp"


class TimelineTipLogsView(_TimelineLogsByTypeView):
    """TIP 타입 로그만 반환합니다."""

    log_key = "tip"


class TimelineCtttmLogsView(_TimelineLogsByTypeView):
    """CTTTM 타입 로그만 반환합니다."""

    log_key = "ctttm"


class TimelineRacbLogsView(_TimelineLogsByTypeView):
    """RACB 타입 로그만 반환합니다."""

    log_key = "racb"


class TimelineJiraLogsView(_TimelineLogsByTypeView):
    """Jira 타입 로그만 반환합니다."""

    log_key = "jira"


__all__ = [
    "TimelineCtttmLogsView",
    "TimelineEquipmentInfoView",
    "TimelineEqpLogsView",
    "TimelineEquipmentsView",
    "TimelineJiraLogsView",
    "TimelineLinesView",
    "TimelineLogsView",
    "TimelinePrcGroupView",
    "TimelineRacbLogsView",
    "TimelineSdwtView",
    "TimelineTipLogsView",
]
