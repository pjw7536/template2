from __future__ import annotations

from django.urls import path

from .views import AssistantChatView, AssistantRagIndexListView

urlpatterns = [
    path("chat", AssistantChatView.as_view(), name="assistant-chat"),
    path("rag-indexes", AssistantRagIndexListView.as_view(), name="assistant-rag-indexes"),
]
