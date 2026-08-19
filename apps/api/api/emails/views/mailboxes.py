# =============================================================================
# 모듈 설명: Emails mailbox·미분류 HTTP endpoint를 제공합니다.
# =============================================================================

from __future__ import annotations

import logging

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.services import UNASSIGNED_USER_SDWT_PROD

from ..permissions import user_can_access_mailbox
from ..selectors import (
    count_unassigned_emails_for_sender_id,
    list_mailbox_members,
    resolve_sender_id_from_user,
)
from ..services import (
    SENT_MAILBOX_ID,
    claim_unassigned_emails_for_user,
    get_mailbox_access_summary_for_user,
    parse_mailbox_user_sdwt_prod,
)
from ..services.mailbox import list_mailboxes_for_user_access
from ._shared import (
    _ensure_authenticated_user,
    _error_response,
    _resolve_email_access_control,
    validate_query_params,
)

logger = logging.getLogger(__name__)

class EmailMailboxListView(APIView):
    """현재 사용자가 접근 가능한 메일함(user_sdwt_prod) 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """사용자가 접근 가능한 메일함 목록을 반환합니다.

        입력:
            쿼리: 없음.
        반환:
            예시 응답: {"results": ["__sent__", "group-a", ...]}
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음(일반 사용자 + 접근 집합 없음)
        예시 요청:
            예시 요청: GET /api/v1/emails/mailboxes/
        snake/camel 호환:
            해당 없음(쿼리 파라미터 없음).
        """
        query_error = validate_query_params(request, allowed=set())
        if query_error is not None:
            return query_error
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        if not is_privileged and not accessible:
            return _error_response("forbidden", status=403)

        results = list_mailboxes_for_user_access(
            user=request.user,
            is_privileged=is_privileged,
            accessible_user_sdwt_prods=accessible,
        )
        return JsonResponse({"results": results})


@method_decorator(csrf_exempt, name="dispatch")
class EmailMailboxMembersView(APIView):
    """메일함(user_sdwt_prod)에 접근 가능한 멤버 목록을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """메일함 멤버 목록을 반환합니다.

        입력:
            쿼리:
                - userSdwtProd: 대상 메일함 식별자
        반환:
            예시 응답: {"userSdwtProd": "...", "members": [...]}
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 400: 메일함 값 누락/보낸메일함 요청
        예시 요청:
            예시 요청: GET /api/v1/emails/mailboxes/members/?userSdwtProd=group-a
        입력 표기:
            HTTP query는 camelCase만 지원합니다.
        """
        query_error = validate_query_params(request, allowed={"userSdwtProd"})
        if query_error is not None:
            return query_error
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error

        if not is_privileged and not accessible:
            return _error_response("forbidden", status=403)
        mailbox_user_sdwt_prod = parse_mailbox_user_sdwt_prod(request.GET)
        if not mailbox_user_sdwt_prod:
            return _error_response("userSdwtProd is required", status=400)
        if mailbox_user_sdwt_prod == SENT_MAILBOX_ID:
            return _error_response("sent mailbox has no members", status=400)
        if not user_can_access_mailbox(
            user=request.user,
            mailbox_user_sdwt_prod=mailbox_user_sdwt_prod,
            is_privileged=is_privileged,
            accessible=accessible,
        ):
            return _error_response("forbidden", status=403)
        members = list_mailbox_members(mailbox_user_sdwt_prod=mailbox_user_sdwt_prod)
        return JsonResponse({"userSdwtProd": mailbox_user_sdwt_prod, "members": members})


@method_decorator(csrf_exempt, name="dispatch")
class EmailMailboxSummaryView(APIView):
    """현재 사용자의 메일함 접근 요약을 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """메일함별 멤버/권한/메일 수 요약을 반환합니다.

        입력:
            요청: Django HttpRequest.
        반환:
            JsonResponse: {"results": [...]} 형태의 메일함 요약.
        부작용:
            없음.
        오류:
            - 401: 인증 실패
        """

        query_error = validate_query_params(request, allowed=set())
        if query_error is not None:
            return query_error
        auth_error = _ensure_authenticated_user(request)
        if auth_error is not None:
            return auth_error

        is_privileged, _accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        results = get_mailbox_access_summary_for_user(
            user=request.user,
            is_privileged=is_privileged,
        )
        return JsonResponse({"results": results})


@method_decorator(csrf_exempt, name="dispatch")
class EmailUnassignedSummaryView(APIView):
    """현재 사용자(sender_id=knox_id)의 UNASSIGNED 메일 개수를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자 기준 UNASSIGNED 메일 개수를 반환합니다.

        입력:
            쿼리: 없음.
        반환:
            예시 응답: {"mailbox": "UNASSIGNED", "count": int}
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: sender_id 미확인
        예시 요청:
            예시 요청: GET /api/v1/emails/unassigned/
        snake/camel 호환:
            해당 없음(쿼리 파라미터 없음).
        """
        query_error = validate_query_params(request, allowed=set())
        if query_error is not None:
            return query_error
        auth_error = _ensure_authenticated_user(request)
        if auth_error is not None:
            return auth_error
        user = request.user
        sender_id = resolve_sender_id_from_user(user)
        if not sender_id:
            return _error_response("forbidden", status=403)
        count = count_unassigned_emails_for_sender_id(sender_id=sender_id)
        return JsonResponse({"mailbox": UNASSIGNED_USER_SDWT_PROD, "count": count})


@method_decorator(csrf_exempt, name="dispatch")
class EmailUnassignedClaimView(APIView):
    """현재 사용자(sender_id=knox_id)의 UNASSIGNED 메일을 현재 user_sdwt_prod로 귀속(옮김)합니다."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """현재 사용자의 UNASSIGNED 메일을 자신의 메일함으로 이동합니다.

        입력:
            바디: 없음(JSON 본문 불필요).
        반환:
            예시 응답: {"moved": int, "ragRegistered": int, "ragFailed": int, "ragMissing": int}
        부작용:
            Email.user_sdwt_prod 업데이트 및 RAG 인덱싱 큐 적재.
        오류:
            - 401: 인증 실패
            - 403: knox_id 미설정
            - 400: user_sdwt_prod 미설정/UNASSIGNED
            - 500: 기타 서버 오류
        예시 요청:
            예시 요청: POST /api/v1/emails/unassigned/claim/
        snake/camel 호환:
            해당 없음(요청 본문 없음).
        """
        auth_error = _ensure_authenticated_user(request)
        if auth_error is not None:
            return auth_error
        user = request.user
        try:
            payload = claim_unassigned_emails_for_user(user=user)
        except PermissionError:
            return _error_response("forbidden", status=403)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:  # pragma: no cover  테스트 제외
            # 방어적 로깅
            logger.exception("Failed to claim UNASSIGNED emails for user_id=%s", getattr(user, "id", None))
            return JsonResponse({"error": "Failed to claim emails"}, status=500)
        return JsonResponse(payload)
