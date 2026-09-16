# =============================================================================
# 모듈: 어시스턴트 서비스 파사드
# 주요 구성: chat/config/normalization/reply/memory 서비스 묶음
# 주요 가정: 외부 연동 설정은 settings/env에서 주입됩니다.
# =============================================================================
"""어시스턴트 서비스 파사드 모듈입니다."""

from __future__ import annotations

from .chat import AssistantChatResult, AssistantChatService, assistant_chat_service
from .config import AssistantChatConfig
from .conversation_access import list_accessible_assistant_conversation_page
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
    refresh_authorized_assistant_conversation_summary,
    update_assistant_conversation,
    upsert_assistant_message_feedback,
)
from .errors import AssistantConfigError, AssistantRequestError
from .exports import build_assistant_csv_export, build_assistant_markdown_export
from .generations import (
    finalize_assistant_generation,
)
from .normalization import (
    build_rag_index_list_payload,
    default_permission_groups,
    normalize_csv_string,
    resolve_permission_groups,
    resolve_rag_index_names,
    resolve_sender_id,
    validate_user_identity,
)
from .openwebui import (
    AssistantOpenWebUIConfig,
    build_openwebui_app_system_message,
    build_openwebui_grounded_system_message,
    build_openwebui_headers,
    build_openwebui_messages,
    normalize_openwebui_conversation_title,
    request_openwebui_chat,
    request_openwebui_conversation_summary,
    request_openwebui_conversation_title,
)
from .reply import AssistantStructuredSegment
from .access_requirements import (
    AssistantAccessDecision,
    access_requirements_for_scopes,
    empty_access_requirements,
    merge_access_requirements,
    normalize_access_requirements,
    validate_access_requirements,
)
from .profiles import (
    AssistantProfile,
    AssistantProfileUnavailableError,
    get_assistant_profile,
    get_current_assistant_profile,
)
from .runtime import AssistantRuntime, AssistantRuntimeResult, assistant_runtime
from .runtime_memory import AssistantRuntimeMemory, build_assistant_runtime_memory
from .turns import AssistantTurnError, AssistantTurnService, assistant_turn_service

__all__ = [
    "AssistantChatConfig",
    "AssistantChatResult",
    "AssistantChatService",
    "AssistantConfigError",
    "AssistantOpenWebUIConfig",
    "AssistantRequestError",
    "AssistantStructuredSegment",
    "AssistantAccessDecision",
    "AssistantProfile",
    "AssistantProfileUnavailableError",
    "AssistantRuntime",
    "AssistantRuntimeResult",
    "AssistantRuntimeMemory",
    "AssistantTurnError",
    "AssistantTurnService",
    "append_assistant_messages",
    "assistant_chat_service",
    "assistant_runtime",
    "assistant_turn_service",
    "access_requirements_for_scopes",
    "build_rag_index_list_payload",
    "build_assistant_runtime_memory",
    "build_assistant_csv_export",
    "build_assistant_markdown_export",
    "build_openwebui_messages",
    "build_openwebui_app_system_message",
    "build_openwebui_grounded_system_message",
    "build_openwebui_headers",
    "clear_assistant_messages",
    "create_assistant_conversation",
    "create_assistant_context_snapshot",
    "default_permission_groups",
    "empty_access_requirements",
    "delete_assistant_conversation",
    "delete_assistant_message_feedback",
    "finalize_assistant_generation",
    "generate_assistant_conversation_title",
    "is_default_assistant_conversation_title",
    "list_accessible_assistant_conversation_page",
    "get_assistant_profile",
    "get_current_assistant_profile",
    "merge_access_requirements",
    "normalize_access_requirements",
    "normalize_csv_string",
    "normalize_openwebui_conversation_title",
    "resolve_permission_groups",
    "resolve_rag_index_names",
    "resolve_sender_id",
    "request_openwebui_chat",
    "request_openwebui_conversation_summary",
    "request_openwebui_conversation_title",
    "refresh_assistant_conversation_summary",
    "refresh_authorized_assistant_conversation_summary",
    "update_assistant_conversation",
    "upsert_assistant_message_feedback",
    "validate_user_identity",
    "validate_access_requirements",
]
