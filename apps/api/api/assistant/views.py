"""LLM assistant 채팅용 임시 엔드포인트."""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Tuple

from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from . import selectors
from .services import AssistantConfigError, AssistantRequestError, assistant_chat_service
from api.common.utils import parse_json_body
from api.rag import services as rag_services

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


def _validate_user_identity(user: object) -> Tuple[str, str]:
    """사용자 객체에서 knox_id를 추출한다.

    - knox_id가 있어야 downstream 서비스 호출 시 User-Id 헤더를 보낼 수 있다.
    - 모든 검증 오류는 예외로 처리한다.
    """

    knox_id = getattr(user, "knox_id", None)
    if not isinstance(knox_id, str) or not knox_id.strip():
        raise AssistantRequestError("knox_id가 필요합니다.")

    normalized = knox_id.strip()
    return normalized, normalized


def _normalize_string_list(raw: object) -> List[str]:
    """문자열 리스트를 정규화합니다."""

    if not isinstance(raw, list):
        return []
    normalized: List[str] = []
    for item in raw:
        if item is None:
            continue
        cleaned = str(item).strip()
        if cleaned:
            normalized.append(cleaned)
    return list(dict.fromkeys(normalized))


def _normalize_csv_string(raw: str) -> List[str]:
    """comma-separated 문자열을 리스트로 정규화합니다."""

    if not raw:
        return []
    normalized = [value.strip() for value in raw.split(",") if value.strip()]
    return list(dict.fromkeys(normalized))


def _resolve_sender_id(user: object) -> str | None:
    """사용자에서 sender_id(knox_id)를 추출합니다."""

    knox_id = getattr(user, "knox_id", None)
    if isinstance(knox_id, str) and knox_id.strip():
        return knox_id.strip()
    return None


def _default_permission_groups(user: object) -> List[str]:
    """기본 permission_groups 값을 계산합니다."""

    groups: List[str] = []
    raw_user_sdwt = getattr(user, "user_sdwt_prod", "")
    if isinstance(raw_user_sdwt, str) and raw_user_sdwt.strip():
        groups.append(raw_user_sdwt.strip())
    sender_id = _resolve_sender_id(user)
    if sender_id:
        groups.append(sender_id)
    groups.append(rag_services.RAG_PUBLIC_GROUP)
    return list(dict.fromkeys(groups))


def _resolve_permission_groups(payload: Dict[str, object], user: object) -> List[str]:
    """요청/사용자 정보로 permission_groups를 결정합니다."""

    raw_groups = payload.get("permission_groups") or payload.get("permissionGroups")
    if raw_groups is not None and not isinstance(raw_groups, list):
        raise ValueError("permission_groups must be an array")

    normalized = _normalize_string_list(raw_groups)
    if not normalized:
        normalized = _default_permission_groups(user)

    accessible = selectors.get_accessible_user_sdwt_prods_for_user(user=user)
    allowed = set(accessible)
    sender_id = _resolve_sender_id(user)
    if sender_id:
        allowed.add(sender_id)
    allowed.add(rag_services.RAG_PUBLIC_GROUP)
    invalid = [group for group in normalized if group not in allowed]
    if invalid:
        raise AssistantRequestError("해당 permission_groups에 대한 접근 권한이 없습니다.")

    return normalized


def _resolve_rag_index_names(payload: Dict[str, object]) -> List[str]:
    """요청 페이로드로 RAG 인덱스 목록을 결정합니다."""

    raw_indexes = payload.get("rag_index_name") or payload.get("ragIndexName")
    if raw_indexes is None:
        normalized: List[str] = []
    elif isinstance(raw_indexes, str):
        normalized = _normalize_csv_string(raw_indexes)
    elif isinstance(raw_indexes, list):
        normalized = _normalize_string_list(raw_indexes)
    else:
        raise ValueError("rag_index_name must be a comma-separated string or array")
    if not normalized:
        return rag_services.resolve_rag_index_names(None)

    candidates = rag_services.get_rag_index_candidates()
    if candidates:
        invalid = [value for value in normalized if value not in candidates]
        if invalid:
            raise ValueError("rag_index_name contains invalid index")

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


def _normalize_sources(raw_sources: object) -> List[Dict[str, str]]:
    """RAG 검색 결과에서 프론트에 전달할 출처 리스트를 정규화."""

    normalized: List[Dict[str, str]] = []
    seen_doc_ids: set[str] = set()
    if not isinstance(raw_sources, list):
        return normalized

    for entry in raw_sources:
        if not isinstance(entry, dict):
            continue
        doc_id = entry.get("doc_id") or entry.get("docId")
        if not isinstance(doc_id, str) or not doc_id.strip():
            continue
        doc_id_clean = doc_id.strip()
        if doc_id_clean in seen_doc_ids:
            continue
        seen_doc_ids.add(doc_id_clean)
        title_raw = entry.get("title")
        title = title_raw.strip() if isinstance(title_raw, str) else ""
        snippet_raw = entry.get("snippet")
        snippet = snippet_raw.strip() if isinstance(snippet_raw, str) else ""
        normalized.append(
            {
                "docId": doc_id_clean,
                "title": title,
                "snippet": snippet,
            }
        )
    return normalized


def _normalize_segments(raw_segments: object) -> List[Dict[str, object]]:
    """LLM 응답 segment 목록을 프론트 전달용으로 정규화합니다."""

    normalized: List[Dict[str, object]] = []
    if not isinstance(raw_segments, list):
        return normalized

    for entry in raw_segments:
        if not isinstance(entry, dict):
            continue

        reply_raw = entry.get("reply") or entry.get("answer") or entry.get("content")
        reply = reply_raw.strip() if isinstance(reply_raw, str) else ""
        if not reply:
            continue

        sources = _normalize_sources(entry.get("sources"))
        if not sources:
            continue

        normalized.append({"reply": reply, "sources": sources})

    return normalized


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
class AssistantRagIndexListView(APIView):
    """현재 사용자가 선택 가능한 RAG 인덱스/권한 그룹 정보를 반환합니다."""

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)

        accessible = selectors.get_accessible_user_sdwt_prods_for_user(user=user)
        current_user_sdwt_prod = getattr(user, "user_sdwt_prod", None)
        permission_groups = set(accessible)
        sender_id = _resolve_sender_id(user)
        if not sender_id:
            return JsonResponse({"error": "forbidden"}, status=403)
        permission_groups.add(sender_id)
        permission_groups.add(rag_services.RAG_PUBLIC_GROUP)

        return JsonResponse(
            {
                "ragIndexes": rag_services.get_rag_index_candidates(),
                "defaultRagIndex": rag_services.resolve_rag_index_name(None),
                "emailRagIndex": rag_services.resolve_rag_index_name(rag_services.RAG_INDEX_EMAILS),
                "permissionGroups": sorted(permission_groups),
                "currentUserSdwtProd": current_user_sdwt_prod,
                "ragPublicGroup": rag_services.RAG_PUBLIC_GROUP,
            }
        )


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
            user_key, user_header_id = _validate_user_identity(request.user)
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)

        room_id_raw = payload.get("roomId") or payload.get("room_id")
        room_id = _normalize_room_id(room_id_raw)

        prompt_clean = prompt.strip()
        try:
            permission_groups = _resolve_permission_groups(payload, request.user)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except AssistantRequestError as exc:
            return JsonResponse({"error": str(exc)}, status=403)

        try:
            rag_index_names = _resolve_rag_index_names(payload)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        incoming_history = _normalize_history(
            payload.get("history"),
            limit=conversation_memory.max_messages,
        )
        stored_history = conversation_memory.load(user_key, room_id)
        base_history = stored_history if stored_history else incoming_history

        history_with_prompt = _append_user_prompt(
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
            sources_used = _normalize_sources(getattr(chat_result, "sources", []))
            segments_used = _normalize_segments(getattr(chat_result, "segments", []))
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
