"""LLM assistant 채팅용 임시 엔드포인트."""
from __future__ import annotations

import logging
from typing import Dict, List

from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.common.utils import parse_json_body

from .services import (
    AssistantConfigError,
    AssistantRequestError,
    append_user_prompt,
    assistant_chat_service,
    build_rag_index_list_payload,
    conversation_memory,
    normalize_history,
    normalize_room_id,
    normalize_segments,
    normalize_sources,
    resolve_permission_groups,
    resolve_rag_index_names,
    validate_user_identity,
)

logger = logging.getLogger(__name__)


def _normalize_sources(raw_sources: object) -> List[Dict[str, str]]:
    """tests.py에서 사용하는 normalize_sources 래퍼."""

    return normalize_sources(raw_sources)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantRagIndexListView(APIView):
    """현재 사용자가 선택 가능한 RAG 인덱스/권한 그룹 정보를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        try:
            return JsonResponse(build_rag_index_list_payload(user=user))
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)


@method_decorator(csrf_exempt, name="dispatch")
class AssistantChatView(APIView):
    """프론트엔드 어시스턴트 위젯에서 사용하는 채팅 엔드포인트."""

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        payload = parse_json_body(request)
        if payload is None:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return JsonResponse({"error": "prompt is required"}, status=400)

        if not request.user.is_authenticated:
            return JsonResponse({"error": "로그인이 필요합니다."}, status=401)

        try:
            user_key, user_header_id = validate_user_identity(request.user)
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)

        room_id_raw = payload.get("roomId") or payload.get("room_id")
        room_id = normalize_room_id(room_id_raw)

        prompt_clean = prompt.strip()
        try:
            permission_groups = resolve_permission_groups(payload, request.user)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)

        try:
            rag_index_names = resolve_rag_index_names(payload)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        incoming_history = normalize_history(
            payload.get("history"),
            limit=conversation_memory.max_messages,
        )
        stored_history = conversation_memory.load(user_key, room_id)
        base_history = stored_history if stored_history else incoming_history

        history_with_prompt = append_user_prompt(
            base_history,
            prompt_clean,
            limit=conversation_memory.max_messages,
        )
        conversation_memory.save(user_key, room_id, history_with_prompt)

        reply = ""
        contexts_used: List[str] = []
        sources_used: List[Dict[str, str]] = []
        segments_used: List[Dict[str, object]] = []
        is_dummy = False
        try:
            chat_result = assistant_chat_service.generate_reply(
                prompt_clean,
                user_header_id=user_header_id,
                rag_index_names=rag_index_names,
                permission_groups=permission_groups,
            )
            reply = chat_result.reply.strip() if isinstance(chat_result.reply, str) else ""
            contexts_used = chat_result.contexts
            sources_used = normalize_sources(getattr(chat_result, "sources", []))
            segments_used = normalize_segments(getattr(chat_result, "segments", []))
            is_dummy = getattr(chat_result, "is_dummy", False)
        except AssistantConfigError as exc:
            logger.error(
                "Assistant service configuration is missing required values.",
                extra={
                    "username": user_key,
                    "roomId": room_id,
                    "llmConfigured": bool(assistant_chat_service.config.llm_url),
                    "ragConfigured": bool(assistant_chat_service.config.rag_url),
                },
                exc_info=exc,
            )
            return JsonResponse(
                {"error": "어시스턴트 API 설정이 누락되었습니다. 관리자에게 문의해주세요."},
                status=503,
            )
        except AssistantRequestError as exc:
            logger.exception(
                "Assistant upstream request failed",
                extra={"username": user_key, "roomId": room_id},
            )
            return JsonResponse({"error": str(exc)}, status=502)

        if not reply:
            logger.error(
                "Assistant reply is empty despite successful upstream call.",
                extra={"username": user_key, "roomId": room_id, "contextCount": len(contexts_used)},
            )
            return JsonResponse({"error": "어시스턴트 응답이 비어 있습니다. 관리자에게 문의해주세요."}, status=502)

        assistant_history_payload = (
            [{"role": "assistant", "content": segment["reply"]} for segment in segments_used]
            if segments_used
            else [{"role": "assistant", "content": reply}]
        )
        updated_history = conversation_memory.append(user_key, room_id, assistant_history_payload)

        logger.debug(
            "Assistant chat request received",
            extra={
                "historyCount": len(updated_history),
                "username": user_key,
                "roomId": room_id,
                "llmConfigured": bool(assistant_chat_service.config.llm_url) or is_dummy,
                "ragConfigured": bool(assistant_chat_service.config.rag_url) or is_dummy or bool(contexts_used),
                "contextCount": len(contexts_used),
                "sourceCount": len(sources_used),
                "isDummy": is_dummy,
            },
        )

        return JsonResponse(
            {
                "reply": reply,
                "contexts": contexts_used,
                "sources": sources_used,
                "segments": segments_used,
                "meta": {
                    "isDummy": is_dummy,
                    "llmConfigured": bool(assistant_chat_service.config.llm_url) or is_dummy,
                    "ragConfigured": bool(assistant_chat_service.config.rag_url) or is_dummy or bool(contexts_used),
                },
                "echo": {
                    "prompt": prompt_clean,
                    "historyCount": len(updated_history),
                    "username": user_key,
                    "roomId": room_id,
                },
            }
        )
