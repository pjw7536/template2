# =============================================================================
# 모듈 설명: Emails 받은·보낸 메일 목록 HTTP endpoint를 제공합니다.
# =============================================================================

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from ..permissions import user_can_access_mailbox
from ..selectors import get_filtered_emails, get_sent_emails, resolve_sender_id_from_user
from ..services import SENT_MAILBOX_ID, build_email_filters
from ._shared import (
    _build_email_list_response,
    _error_response,
    _resolve_email_access_control,
    validate_query_params,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

class EmailInboxListView(APIView):
    """메일함(user_sdwt_prod) 기준 메일 리스트 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """메일함 메일 리스트를 조회합니다.

        입력:
            쿼리:
                - userSdwtProd: 메일함 식별자(옵션)
                - q: 검색어(제목/본문/발신자/참여자)
                - sender: 발신자 필터
                - recipient: 수신자 필터(To/Cc)
                - dateFrom/dateTo: 수신 기간 필터(ISO, 기본 타임존 기준 날짜/시간)
                - page/pageSize: 페이지네이션
        반환:
            예시 응답: {"results": [...], "page": int, "pageSize": int, "total": int, "totalPages": int}
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: 접근 권한 없음
            - 400: 보낸메일함 접근/UNASSIGNED 접근 오류
        예시 요청:
            예시 요청: GET /api/v1/emails/inbox/?userSdwtProd=group-a&q=report&page=1&pageSize=20
        입력 표기:
            HTTP query는 camelCase만 지원합니다.
        날짜 해석:
            - 타임존 없는 값은 Django 기본 타임존(TIME_ZONE)으로 해석 후 UTC로 변환합니다.
            - 날짜만 입력 시 date_from=해당 날짜 00:00:00, date_to=해당 날짜 23:59:59.999999로 처리됩니다.
        """
        query_error = validate_query_params(
            request,
            allowed={"userSdwtProd", "q", "sender", "recipient", "dateFrom", "dateTo", "page", "pageSize"},
        )
        if query_error is not None:
            return query_error
        is_privileged, accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error

        if not is_privileged and not accessible:
            return _error_response("forbidden", status=403)
        filters = build_email_filters(
            params=request.GET,
            default_page_size=DEFAULT_PAGE_SIZE,
            max_page_size=MAX_PAGE_SIZE,
        )
        mailbox_user_sdwt_prod = filters["mailbox_user_sdwt_prod"]
        if mailbox_user_sdwt_prod == SENT_MAILBOX_ID:
            return _error_response("use sent endpoint", status=400)
        if not user_can_access_mailbox(
            user=request.user,
            mailbox_user_sdwt_prod=mailbox_user_sdwt_prod,
            is_privileged=is_privileged,
            accessible=accessible,
        ):
            return _error_response("forbidden", status=403)
        qs = get_filtered_emails(
            accessible_user_sdwt_prods=accessible,
            is_privileged=is_privileged,
            can_view_unassigned=is_privileged,
            mailbox_user_sdwt_prod=mailbox_user_sdwt_prod,
            search=filters["search"],
            sender=filters["sender"],
            recipient=filters["recipient"],
            date_from=filters["date_from"],
            date_to=filters["date_to"],
        )
        page = filters["page"]
        page_size = filters["page_size"]

        return _build_email_list_response(qs, page, page_size)


@method_decorator(csrf_exempt, name="dispatch")
class EmailSentListView(APIView):
    """보낸 메일(sender_id) 기준 리스트 조회."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        """발신자(sender_id) 기준 보낸메일 리스트를 조회합니다.

        입력:
            쿼리:
                - q/sender/recipient/dateFrom/dateTo/page/pageSize (검색/기간/페이지, 기본 타임존 기준 날짜/시간)
        반환:
            예시 응답: {"results": [...], "page": int, "pageSize": int, "total": int, "totalPages": int}
        부작용:
            없음. 조회 전용.
        오류:
            - 401: 인증 실패
            - 403: sender_id 미확인
            - 400: knox_id/knoxId 파라미터 사용 금지
        예시 요청:
            예시 요청: GET /api/v1/emails/sent/?q=report&page=1&pageSize=20
        입력 표기:
            HTTP query는 camelCase만 지원하며 발신자 식별자 override는 허용하지 않습니다.
        날짜 해석:
            - 타임존 없는 값은 Django 기본 타임존(TIME_ZONE)으로 해석 후 UTC로 변환합니다.
            - 날짜만 입력 시 date_from=해당 날짜 00:00:00, date_to=해당 날짜 23:59:59.999999로 처리됩니다.
        """
        query_error = validate_query_params(
            request,
            allowed={"q", "sender", "recipient", "dateFrom", "dateTo", "page", "pageSize"},
        )
        if query_error is not None:
            return query_error
        _is_privileged, _accessible, auth_error = _resolve_email_access_control(request)
        if auth_error is not None:
            return auth_error
        sender_id = resolve_sender_id_from_user(request.user)
        if not sender_id:
            return _error_response("forbidden", status=403)
        filters = build_email_filters(
            params=request.GET,
            default_page_size=DEFAULT_PAGE_SIZE,
            max_page_size=MAX_PAGE_SIZE,
        )

        qs = get_sent_emails(
            sender_id=sender_id,
            search=filters["search"],
            sender=filters["sender"],
            recipient=filters["recipient"],
            date_from=filters["date_from"],
            date_to=filters["date_to"],
        )
        page = filters["page"]
        page_size = filters["page_size"]

        return _build_email_list_response(qs, page, page_size)
