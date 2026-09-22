"""Assistant rag API입니다."""

from ._shared import *  # noqa: F403


@method_decorator(csrf_exempt, name="dispatch")
class AssistantRagIndexListView(APIView):
    """현재 사용자가 선택 가능한 RAG 인덱스/권한 그룹 정보를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """접근 가능한 RAG 인덱스/권한 그룹 정보를 반환합니다.

        요청 예시:
            예시 요청: GET /api/v1/assistant/rag-indexes

        반환:
            200: {
                예시 "ragIndexes": [...],
                예시 "defaultRagIndex": "...",
                예시 "emailRagIndex": "...",
                예시 "permissionGroups": [...],
                예시 "currentUserSdwtProd": "...",
                예시 "ragPublicGroup": "..."
            }

        부작용:
            없음. 읽기 전용 조회입니다.

        오류:
            401: 비인증
            403: 권한 없음

        요청/응답 계약:
            입력 파라미터는 없으며, 응답 키는 camelCase로 반환합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 인증 확인
        # -----------------------------------------------------------------------------
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        permission_error = _require_account_scopes(
            request=request,
            scopes=("assistant", "emails"),
        )
        if permission_error is not None:
            return permission_error

        # -----------------------------------------------------------------------------
        # 2) 접근 가능한 인덱스/권한 그룹 조회
        # -----------------------------------------------------------------------------
        try:
            return JsonResponse(build_rag_index_list_payload(user=user))
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
