# =============================================================================
# 모듈: 어시스턴트 서비스 파사드
# 주요 구성: chat/config/normalization/reply/memory 서비스 묶음
# 주요 가정: 외부 연동 설정은 settings/env에서 주입됩니다.
# =============================================================================
"""어시스턴트 서비스 파사드 모듈입니다."""

from __future__ import annotations

from .chat import AssistantChatResult, AssistantChatService, assistant_chat_service
from .config import AssistantChatConfig
from .conversations import (
    append_assistant_messages,
    clear_assistant_messages,
    create_assistant_context_snapshot,
    create_assistant_conversation,
    delete_assistant_message_feedback,
    delete_assistant_conversation,
    generate_assistant_conversation_title,
    is_default_assistant_conversation_title,
    refresh_assistant_conversation_summary,
    update_assistant_conversation,
    upsert_assistant_message_feedback,
)
from .errors import AssistantConfigError, AssistantRequestError
from .memory import ConversationMemory, conversation_memory
from .exports import build_assistant_csv_export, build_assistant_markdown_export
from .generations import (
    AssistantGenerationBusyError,
    acquire_assistant_generation,
    finalize_assistant_generation,
)
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
from .openwebui import (
    AssistantOpenWebUIConfig,
    build_openwebui_app_system_message,
    build_openwebui_messages,
    normalize_openwebui_conversation_title,
    request_openwebui_chat,
    request_openwebui_conversation_summary,
    request_openwebui_conversation_title,
    stream_openwebui_chat,
)
from .reply import AssistantStructuredSegment

__all__ = [
    "AssistantChatConfig",
    "AssistantChatResult",
    "AssistantChatService",
    "AssistantConfigError",
    "AssistantOpenWebUIConfig",
    "AssistantRequestError",
    "AssistantStructuredSegment",
    "ConversationMemory",
    "append_user_prompt",
    "append_assistant_messages",
    "acquire_assistant_generation",
    "assistant_chat_service",
    "build_rag_index_list_payload",
    "build_assistant_csv_export",
    "build_assistant_markdown_export",
    "build_openwebui_messages",
    "build_openwebui_app_system_message",
    "clear_assistant_messages",
    "conversation_memory",
    "create_assistant_conversation",
    "create_assistant_context_snapshot",
    "default_permission_groups",
    "delete_assistant_conversation",
    "delete_assistant_message_feedback",
    "AssistantGenerationBusyError",
    "finalize_assistant_generation",
    "generate_assistant_conversation_title",
    "is_default_assistant_conversation_title",
    "normalize_csv_string",
    "normalize_history",
    "normalize_openwebui_conversation_title",
    "normalize_room_id",
    "normalize_segments",
    "normalize_sources",
    "resolve_permission_groups",
    "resolve_rag_index_names",
    "resolve_sender_id",
    "request_openwebui_chat",
    "request_openwebui_conversation_summary",
    "request_openwebui_conversation_title",
    "refresh_assistant_conversation_summary",
    "stream_openwebui_chat",
    "update_assistant_conversation",
    "upsert_assistant_message_feedback",
    "validate_user_identity",
]
