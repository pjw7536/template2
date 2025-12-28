# =============================================================================
# 모듈: 어시스턴트 서비스 파사드
# 주요 구성: chat/config/normalization/reply/memory 서비스 묶음
# 주요 가정: 외부 연동 설정은 settings/env에서 주입됩니다.
# =============================================================================
"""어시스턴트 서비스 파사드 모듈입니다."""

from __future__ import annotations

from .chat import AssistantChatResult, AssistantChatService, assistant_chat_service
from .config import AssistantChatConfig
from .errors import AssistantConfigError, AssistantRequestError
from .memory import ConversationMemory, conversation_memory
from .normalization import (
    append_user_prompt,
    build_rag_index_list_payload,
    default_permission_groups,
    normalize_csv_string,
    normalize_history,
    normalize_room_id,
    normalize_segments,
    normalize_sources,
    resolve_permission_groups,
    resolve_rag_index_names,
    resolve_sender_id,
    validate_user_identity,
)
from .reply import AssistantStructuredSegment

__all__ = [
    "AssistantChatConfig",
    "AssistantChatResult",
    "AssistantChatService",
    "AssistantConfigError",
    "AssistantRequestError",
    "AssistantStructuredSegment",
    "ConversationMemory",
    "append_user_prompt",
    "assistant_chat_service",
    "build_rag_index_list_payload",
    "conversation_memory",
    "default_permission_groups",
    "normalize_csv_string",
    "normalize_history",
    "normalize_room_id",
    "normalize_segments",
    "normalize_sources",
    "resolve_permission_groups",
    "resolve_rag_index_names",
    "resolve_sender_id",
    "validate_user_identity",
]
