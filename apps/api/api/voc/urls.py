from __future__ import annotations

from django.urls import path

from .views import VocPostDetailView, VocPostsView, VocReplyView

urlpatterns = [
    path("posts", VocPostsView.as_view(), name="voc-posts"),
    path("posts/<int:post_id>", VocPostDetailView.as_view(), name="voc-post-detail"),
    path("posts/<int:post_id>/replies", VocReplyView.as_view(), name="voc-post-reply"),
]

