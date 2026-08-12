# =============================================================================
# 모듈: 어시스턴트 라우팅
# 주요 경로: /chat, /rag-indexes
# 주요 가정: 요청/응답 로직은 views에서 처리합니다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import (
    AssistantChatView,
    AssistantConversationDetailView,
    AssistantConversationListCreateView,
    AssistantConversationMessageView,
    AssistantConversationExportView,
    AssistantConversationSummaryView,
    AssistantConversationTitleView,
    AssistantOpenWebUIChatView,
    AssistantOpenWebUIStreamView,
    AssistantRagIndexListView,
    AssistantGenerationDetailView,
    AssistantGenerationListCreateView,
    AssistantMessageFeedbackView,
)

urlpatterns = [
    path("chat", AssistantChatView.as_view(), name="assistant-chat"),
    path(
        "openwebui-chat",
        AssistantOpenWebUIChatView.as_view(),
        name="assistant-openwebui-chat",
    ),
    path(
        "openwebui-chat/stream",
        AssistantOpenWebUIStreamView.as_view(),
        name="assistant-openwebui-stream",
    ),
    path(
        "conversations",
        AssistantConversationListCreateView.as_view(),
        name="assistant-conversation-list-create",
    ),
    path(
        "conversations/<uuid:conversation_id>",
        AssistantConversationDetailView.as_view(),
        name="assistant-conversation-detail",
    ),
    path(
        "conversations/<uuid:conversation_id>/messages",
        AssistantConversationMessageView.as_view(),
        name="assistant-conversation-messages",
    ),
    path(
        "conversations/<uuid:conversation_id>/messages/<str:client_id>/feedback",
        AssistantMessageFeedbackView.as_view(),
        name="assistant-message-feedback",
    ),
    path(
        "conversations/<uuid:conversation_id>/export",
        AssistantConversationExportView.as_view(),
        name="assistant-conversation-export",
    ),
    path(
        "conversations/<uuid:conversation_id>/generate-title",
        AssistantConversationTitleView.as_view(),
        name="assistant-conversation-generate-title",
    ),
    path(
        "conversations/<uuid:conversation_id>/refresh-summary",
        AssistantConversationSummaryView.as_view(),
        name="assistant-conversation-refresh-summary",
    ),
    path("rag-indexes", AssistantRagIndexListView.as_view(), name="assistant-rag-indexes"),
    path(
        "generations",
        AssistantGenerationListCreateView.as_view(),
        name="assistant-generation-list-create",
    ),
    path(
        "generations/<uuid:generation_id>",
        AssistantGenerationDetailView.as_view(),
        name="assistant-generation-detail",
    ),
]
