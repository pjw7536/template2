# =============================================================================
# 모듈 설명: voc 엔드포인트 라우팅을 정의합니다.
# - 주요 경로: posts, posts/<id>, posts/<id>/replies
# - 불변 조건: 상대 경로만 선언합니다.
# =============================================================================

from __future__ import annotations

from django.urls import path

from .views import VocPostDetailView, VocPostsView, VocReplyView

urlpatterns = [
    path("posts", VocPostsView.as_view(), name="voc-posts"),
    path("posts/<int:post_id>", VocPostDetailView.as_view(), name="voc-post-detail"),
    path("posts/<int:post_id>/replies", VocReplyView.as_view(), name="voc-post-reply"),
]
