# =============================================================================
# 모듈: 어시스턴트 라우팅
# 주요 경로: /chat, /rag-indexes
# 주요 가정: 요청/응답 로직은 views에서 처리합니다.
# =============================================================================
from __future__ import annotations

from django.urls import path

from .views import AssistantChatView, AssistantRagIndexListView

urlpatterns = [
    path("chat", AssistantChatView.as_view(), name="assistant-chat"),
    path("rag-indexes", AssistantRagIndexListView.as_view(), name="assistant-rag-indexes"),
]
