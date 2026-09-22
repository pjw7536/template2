# =============================================================================
# 모듈: 어시스턴트 API 뷰
# 주요 엔드포인트: AssistantTurnStreamView.post, AssistantRagIndexListView.get
# 주요 가정: parse_json_body는 실패 시 None을 반환합니다.
# =============================================================================
"""표준 Turn과 대화·인덱스 조회 엔드포인트 모음입니다."""
from __future__ import annotations

import json
import logging
from uuid import UUID

from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

import api.account.services as account_services

from api.common.services import (
    extract_first_error_message,
    parse_json_body,
    parse_json_body_or_error_when_present,
)

from api.assistant import selectors
from api.assistant.serializers import (
    AssistantConversationCreateSerializer,
    AssistantConversationExportQuerySerializer,
    AssistantConversationListQuerySerializer,
    AssistantConversationSummaryRequestSerializer,
    AssistantConversationSerializer,
    AssistantConversationUpdateSerializer,
    AssistantMessageFeedbackSerializer,
    AssistantMessageListQuerySerializer,
    AssistantMessageSerializer,
    AssistantTurnRequestSerializer,
)
from api.assistant.services import (
    AssistantConfigError,
    AssistantRequestError,
    build_rag_index_list_payload,
    build_assistant_csv_export,
    build_assistant_markdown_export,
    clear_assistant_messages,
    create_assistant_conversation,
    delete_assistant_conversation,
    delete_assistant_message_feedback,
    generate_assistant_conversation_title,
    list_accessible_assistant_conversation_page,
    refresh_authorized_assistant_conversation_summary,
    update_assistant_conversation,
    upsert_assistant_message_feedback,
    AssistantProfileUnavailableError,
    AssistantTurnError,
    assistant_turn_service,
    validate_access_requirements,
)

logger = logging.getLogger(__name__)

def _conversation_not_found_response() -> JsonResponse:
    """소유하지 않거나 존재하지 않는 대화방을 동일한 404로 반환합니다."""

    return JsonResponse({"error": "대화방을 찾을 수 없습니다."}, status=404)


def _require_account_scopes(
    *,
    request: HttpRequest,
    scopes: tuple[str, ...],
) -> JsonResponse | None:
    """현재 Account 앱 scope가 하나라도 없으면 안전한 403 응답을 반환합니다."""

    missing = [
        scope
        for scope in scopes
        if not account_services.get_access_payload(
            user=request.user,
            scope_key=scope,
            request=request,
        ).get("allowed")
    ]
    if not missing:
        return None
    return JsonResponse(
        {"error": "permission_denied", "missingScopes": missing},
        status=403,
    )


def _message_access_denied(*, request: HttpRequest, message: object) -> bool:
    """메시지의 현재 access requirements가 회수됐는지 반환합니다."""

    return not validate_access_requirements(
        user=request.user,
        requirements=getattr(message, "access_requirements", {}),
        request=request,
    ).allowed


def _encode_sse_event(event: str, payload: object) -> str:
    """브라우저가 해석할 수 있는 UTF-8 SSE event 문자열을 생성합니다."""

    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"

__all__ = [
    'annotations',
    'json',
    'logging',
    'UUID',
    'HttpRequest',
    'HttpResponse',
    'JsonResponse',
    'StreamingHttpResponse',
    'method_decorator',
    'csrf_exempt',
    'JSONRenderer',
    'APIView',
    'account_services',
    'extract_first_error_message',
    'parse_json_body',
    'parse_json_body_or_error_when_present',
    'selectors',
    'AssistantConversationCreateSerializer',
    'AssistantConversationExportQuerySerializer',
    'AssistantConversationListQuerySerializer',
    'AssistantConversationSummaryRequestSerializer',
    'AssistantConversationSerializer',
    'AssistantConversationUpdateSerializer',
    'AssistantMessageFeedbackSerializer',
    'AssistantMessageListQuerySerializer',
    'AssistantMessageSerializer',
    'AssistantTurnRequestSerializer',
    'AssistantConfigError',
    'AssistantRequestError',
    'build_rag_index_list_payload',
    'build_assistant_csv_export',
    'build_assistant_markdown_export',
    'clear_assistant_messages',
    'create_assistant_conversation',
    'delete_assistant_conversation',
    'delete_assistant_message_feedback',
    'generate_assistant_conversation_title',
    'list_accessible_assistant_conversation_page',
    'refresh_authorized_assistant_conversation_summary',
    'update_assistant_conversation',
    'upsert_assistant_message_feedback',
    'AssistantProfileUnavailableError',
    'AssistantTurnError',
    'assistant_turn_service',
    'validate_access_requirements',
    'logger',
    '_conversation_not_found_response',
    '_require_account_scopes',
    '_message_access_denied',
    '_encode_sse_event',
]
