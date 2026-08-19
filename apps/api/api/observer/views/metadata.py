"""Observer 메타데이터와 설비 정보 API입니다."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from rest_framework.views import APIView

from . import selectors
from ._shared import _query_id, _required_query_id


class ObserverLinesView(APIView):
    """라인 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 라인 목록 배열

        부작용:
        - 없음

        오류:
        - 없음

        예시 요청:
        - 예시 요청: GET /api/v1/observer/lines

        snake/camel 호환:
        - 해당 없음(쿼리/바디 없음)
        """
        return JsonResponse(selectors.list_lines(), safe=False)


class ObserverSdwtView(APIView):
    """라인 기준 SDWT 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인 기준 SDWT 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: SDWT 목록 배열

        부작용:
        - 없음

        오류:
        - 400: lineId 누락

        예시 요청:
        - 예시 요청: GET /api/v1/observer/sdwts?lineId=LINE-A

        snake/camel 호환:
        - lineId만 지원(snake_case 미지원)
        """
        line_id, error_response = _required_query_id(
            request,
            "lineId",
            "lineId is required",
        )
        if error_response:
            return error_response

        return JsonResponse(selectors.list_sdwt_for_line(line_id=line_id), safe=False)


class ObserverPrcGroupView(APIView):
    """라인/SDWT 조합 기준 PRC 그룹 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인/SDWT 기준 PRC 그룹 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: PRC 그룹 목록 배열

        부작용:
        - 없음

        오류:
        - 400: lineId 또는 sdwtId 누락

        예시 요청:
        - 예시 요청: GET /api/v1/observer/prc-groups?lineId=LINE-A&sdwtId=SD-10

        snake/camel 호환:
        - lineId/sdwtId만 지원(snake_case 미지원)
        """
        line_id = _query_id(request, "lineId")
        sdwt_id = _query_id(request, "sdwtId")

        if not line_id or not sdwt_id:
            return _missing_query_response("lineId and sdwtId are required")

        return JsonResponse(
            selectors.list_prc_groups(line_id=line_id, sdwt_id=sdwt_id),
            safe=False,
        )


class ObserverEquipmentsView(APIView):
    """라인/SDWT/PRC 그룹 조합 기준 설비 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """라인/SDWT/PRC 그룹 기준 설비 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 설비 목록 배열

        부작용:
        - 없음

        오류:
        - 400: lineId 누락

        예시 요청:
        - 예시 요청: GET /api/v1/observer/equipments?lineId=LINE-A
        - 예시 요청: GET /api/v1/observer/equipments?lineId=LINE-A&sdwtId=SD-10
        - 예시 요청: GET /api/v1/observer/equipments?lineId=LINE-A&sdwtId=SD-10&prcGroup=ETCH

        snake/camel 호환:
        - lineId/sdwtId/prcGroup만 지원(snake_case 미지원)
        """
        line_id, error_response = _required_query_id(
            request,
            "lineId",
            "lineId is required",
        )
        if error_response:
            return error_response
        sdwt_id = _query_id(request, "sdwtId")
        prc_group = _query_id(request, "prcGroup")

        return JsonResponse(
            selectors.list_equipments(
                line_id=line_id,
                sdwt_id=sdwt_id,
                prc_group=prc_group,
            ),
            safe=False,
        )


class ObserverEquipmentInfoView(APIView):
    """eqpId 기준 설비 메타데이터를 반환합니다(선택적으로 line 범위 제한)."""

    def get(
        self,
        request: HttpRequest,
        line_id: str | None = None,
        eqp_id: str | None = None,
        *args: object,
        **kwargs: object,
    ) -> JsonResponse:
        """eqpId 기준 설비 메타데이터를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - line_id: 라인 ID(선택, 경로 파라미터)
        - eqp_id: 설비 ID(경로 파라미터)
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: 설비 메타데이터

        부작용:
        - 없음

        오류:
        - 400: eqpId 누락
        - 404: 설비 미존재 또는 라인 범위 불일치

        예시 요청:
        - 예시 요청: GET /api/v1/observer/equipment-info/EQP-ALPHA
        - 예시 요청: GET /api/v1/observer/equipment-info/LINE-A/EQP-ALPHA

        snake/camel 호환:
        - 해당 없음(경로 파라미터만 사용)
        """
        # -----------------------------------------------------------------------------
        # 1) eqpId 유효성 확인
        # -----------------------------------------------------------------------------
        eqp_key = selectors.normalize_id(eqp_id)
        if not eqp_key:
            return _missing_query_response("eqpId is required")

        # -----------------------------------------------------------------------------
        # 2) 설비 메타데이터 조회
        # -----------------------------------------------------------------------------
        info = selectors.get_equipment_info(
            eqp_id=eqp_key,
            line_id=selectors.normalize_id(line_id) if line_id else "",
        )
        if not info:
            return JsonResponse({"error": "Equipment not found"}, status=404)

        # -----------------------------------------------------------------------------
        # 3) 라인 범위 제한 확인
        # -----------------------------------------------------------------------------
        if line_id and selectors.normalize_id(line_id) != selectors.normalize_id(info["lineId"]):
            return JsonResponse({"error": "Equipment not found for line"}, status=404)

        # -----------------------------------------------------------------------------
        # 4) 응답 반환
        # -----------------------------------------------------------------------------
        return JsonResponse(info)
