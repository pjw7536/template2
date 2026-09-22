"""Observer TKIN Prevent 조회 API입니다."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from rest_framework.views import APIView

from . import selectors
from ._shared import _missing_query_response, _query_id, _required_query_id


def _required_tkin_scope(
    request: HttpRequest,
) -> tuple[dict[str, str], JsonResponse | None]:
    """m_tkin_prevent scope query 값을 검증합니다."""

    user_sdwt_prod = _query_id(request, "userSdwtProd")
    prc_group = _query_id(request, "prcGroup")

    if not user_sdwt_prod or not prc_group:
        return {}, _missing_query_response("userSdwtProd and prcGroup are required")

    return {"user_sdwt_prod": user_sdwt_prod, "prc_group": prc_group}, None


def _required_tkin_user_sdwt_prod(
    request: HttpRequest,
) -> tuple[str, JsonResponse | None]:
    """m_tkin_prevent user_sdwt_prod query 값을 검증합니다."""

    user_sdwt_prod = _query_id(request, "userSdwtProd")
    if not user_sdwt_prod:
        return "", _missing_query_response("userSdwtProd is required")
    return user_sdwt_prod, None


class ObserverTkinPreventPrcGroupsView(APIView):
    """m_tkin_prevent 조회에 사용할 PRC 그룹 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """m_tkin_prevent PRC 그룹 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: PRC 그룹 option 목록

        부작용:
        - 없음

        오류:
        - 400: userSdwtProd 누락

        예시 요청:
        - 예시 요청: GET /api/v1/observer/tkin-prevent/prc-groups?userSdwtProd=S1

        snake/camel 호환:
        - userSdwtProd만 지원(snake_case 미지원)
        """
        user_sdwt_prod, error_response = _required_tkin_user_sdwt_prod(request)
        if error_response:
            return error_response

        return JsonResponse(
            selectors.list_tkin_prevent_prc_groups(user_sdwt_prod=user_sdwt_prod),
            safe=False,
        )


class ObserverTkinPreventProcessesView(APIView):
    """m_tkin_prevent process_id 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """m_tkin_prevent process_id 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: process_id option 목록

        부작용:
        - 없음

        오류:
        - 400: userSdwtProd, prcGroup 누락

        예시 요청:
        - 예시 요청: GET /api/v1/observer/tkin-prevent/processes?userSdwtProd=S1&prcGroup=P1

        snake/camel 호환:
        - userSdwtProd/prcGroup만 지원(snake_case 미지원)
        """
        scope, error_response = _required_tkin_scope(request)
        if error_response:
            return error_response

        return JsonResponse(
            selectors.list_tkin_prevent_processes(**scope),
            safe=False,
        )


class ObserverTkinPreventStepSeqsView(APIView):
    """m_tkin_prevent step_seq 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """m_tkin_prevent step_seq 목록을 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: step_seq option 목록

        부작용:
        - 없음

        오류:
        - 400: userSdwtProd, prcGroup, processId 누락

        예시 요청:
        - 예시 요청: GET /api/v1/observer/tkin-prevent/step-seqs?userSdwtProd=S1&prcGroup=P1&processId=P100

        snake/camel 호환:
        - userSdwtProd/prcGroup/processId만 지원(snake_case 미지원)
        """
        scope, error_response = _required_tkin_scope(request)
        if error_response:
            return error_response

        process_id = _query_id(request, "processId")
        if not process_id:
            return _missing_query_response("processId is required")

        return JsonResponse(
            selectors.list_tkin_prevent_step_seqs(
                **scope,
                process_id=process_id,
            ),
            safe=False,
        )


class ObserverTkinPreventMatrixView(APIView):
    """m_tkin_prevent matrix 데이터를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """m_tkin_prevent matrix 데이터를 반환합니다.

        입력:
        - 요청: Django HttpRequest
        - args/kwargs: URL 라우팅 인자

        반환:
        - JsonResponse: columns/rows matrix 데이터

        부작용:
        - 없음

        오류:
        - 400: userSdwtProd, prcGroup, processId, stepSeq 누락

        예시 요청:
        - 예시 요청: GET /api/v1/observer/tkin-prevent/matrix?userSdwtProd=S1&prcGroup=P1&processId=P100&stepSeq=10

        snake/camel 호환:
        - userSdwtProd/prcGroup/processId/stepSeq만 지원(snake_case 미지원)
        """
        scope, error_response = _required_tkin_scope(request)
        if error_response:
            return error_response

        process_id = _query_id(request, "processId")
        step_seq = _query_id(request, "stepSeq")
        if not process_id or not step_seq:
            return _missing_query_response("processId and stepSeq are required")

        return JsonResponse(
            selectors.get_tkin_prevent_matrix(
                **scope,
                process_id=process_id,
                step_seq=step_seq,
            ),
        )
