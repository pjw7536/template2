"""LLM assistant 채팅용 임시 엔드포인트."""
from __future__ import annotations

import logging
import re
from typing import Dict, List

from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from api.services.assistant_chat import AssistantConfigError, AssistantRequestError, assistant_chat_service

from .utils import parse_json_body

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_LIMIT = 20
HISTORY_CACHE_TTL = 60 * 60 * 6  # 6 hours
DEFAULT_ROOM_ID = "default"


def _normalize_history(raw_history: object, *, limit: int = DEFAULT_HISTORY_LIMIT) -> List[Dict[str, str]]:
    """history 배열에서 role/content가 있는 메시지만 정규화."""

    normalized: List[Dict[str, str]] = []
    if not isinstance(raw_history, list):
        return normalized

    for entry in raw_history:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = entry.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            continue

        role_clean = role.strip()
        content_clean = content.strip()
        if role_clean and content_clean:
            normalized.append({"role": role_clean, "content": content_clean})

        if len(normalized) >= limit:
            break

    return normalized


def _normalize_room_id(room_id: object) -> str:
    """방 ID를 문자열로 정규화하고 기본값을 적용."""

    if isinstance(room_id, str):
        cleaned = room_id.strip()
        if cleaned:
            safe = re.sub(r"[^a-zA-Z0-9_-]", "-", cleaned)
            return safe[:64]
    return DEFAULT_ROOM_ID


def _append_user_prompt(history: List[Dict[str, str]], prompt: str, *, limit: int = DEFAULT_HISTORY_LIMIT) -> List[Dict[str, str]]:
    """정규화된 이력에 현재 사용자 메시지를 중복 없이 추가."""

    prompt_clean = prompt.strip()
    normalized_history = _normalize_history(history, limit=limit)
    prompt_message = {"role": "user", "content": prompt_clean}

    if normalized_history and normalized_history[-1] == prompt_message:
        return normalized_history[-limit:]

    normalized_history.append(prompt_message)
    if len(normalized_history) > limit:
        normalized_history = normalized_history[-limit:]

    return normalized_history


class ConversationMemory:
    """사용자별 대화 이력을 캐시에 저장/슬라이딩 윈도우로 관리."""

    def __init__(self, max_messages: int = DEFAULT_HISTORY_LIMIT, ttl_seconds: int = HISTORY_CACHE_TTL) -> None:
        self.max_messages = max(1, max_messages)
        self.ttl_seconds = max(60, ttl_seconds)

    def _key(self, username: str, room_id: str) -> str:
        return f"assistant:history:{username}:{room_id}"

    def load(self, username: str, room_id: str) -> List[Dict[str, str]]:
        stored = cache.get(self._key(username, room_id), [])
        return _normalize_history(stored, limit=self.max_messages)

    def save(self, username: str, room_id: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        trimmed = _normalize_history(messages, limit=self.max_messages)
        cache.set(self._key(username, room_id), trimmed, self.ttl_seconds)
        return trimmed

    def append(self, username: str, room_id: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        current = self.load(username, room_id)
        current.extend(_normalize_history(messages, limit=self.max_messages))
        return self.save(username, room_id, current)


conversation_memory = ConversationMemory()


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

        username = request.user.get_username()
        if not isinstance(username, str) or not username.strip():
            return JsonResponse({"error": "username이 필요합니다."}, status=400)

        room_id_raw = payload.get("roomId") or payload.get("room_id")
        room_id = _normalize_room_id(room_id_raw)

        username_clean = username.strip()
        prompt_clean = prompt.strip()

        incoming_history = _normalize_history(
            payload.get("history"),
            limit=conversation_memory.max_messages,
        )
        stored_history = conversation_memory.load(username_clean, room_id)
        base_history = stored_history if stored_history else incoming_history

        history_with_prompt = _append_user_prompt(
            base_history,
            prompt_clean,
            limit=conversation_memory.max_messages,
        )
        conversation_memory.save(username_clean, room_id, history_with_prompt)

        reply = ""
        contexts_used: List[str] = []
        is_dummy = False
        try:
            chat_result = assistant_chat_service.generate_reply(prompt_clean)
            reply = chat_result.reply.strip() if isinstance(chat_result.reply, str) else ""
            contexts_used = chat_result.contexts
            is_dummy = getattr(chat_result, "is_dummy", False)
        except AssistantConfigError as exc:
            logger.error(
                "Assistant service configuration is missing required values.",
                extra={
                    "username": username_clean,
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
                extra={"username": username_clean, "roomId": room_id},
            )
            return JsonResponse({"error": str(exc)}, status=502)

        if not reply:
            logger.error(
                "Assistant reply is empty despite successful upstream call.",
                extra={"username": username_clean, "roomId": room_id, "contextCount": len(contexts_used)},
            )
            return JsonResponse({"error": "어시스턴트 응답이 비어 있습니다. 관리자에게 문의해주세요."}, status=502)

        updated_history = conversation_memory.append(
            username_clean,
            room_id,
            [{"role": "assistant", "content": reply}],
        )

        logger.debug(
            "Assistant chat request received",
            extra={
                "historyCount": len(updated_history),
                "username": username_clean,
                "roomId": room_id,
                "llmConfigured": bool(assistant_chat_service.config.llm_url) or is_dummy,
                "ragConfigured": bool(assistant_chat_service.config.rag_url) or is_dummy or bool(contexts_used),
                "contextCount": len(contexts_used),
                "isDummy": is_dummy,
            },
        )

        return JsonResponse(
            {
                "reply": reply,
                "contexts": contexts_used,
                "meta": {
                    "isDummy": is_dummy,
                    "llmConfigured": bool(assistant_chat_service.config.llm_url) or is_dummy,
                    "ragConfigured": bool(assistant_chat_service.config.rag_url) or is_dummy or bool(contexts_used),
                },
                "echo": {
                    "prompt": prompt_clean,
                    "historyCount": len(updated_history),
                    "username": username_clean,
                    "roomId": room_id,
                },
            }
        )
