"""Work Hub 도메인의 상대 API 경로를 등록합니다."""

from django.urls import path

from .views import GristWebhookView, WorkHubContextView


urlpatterns = [
    path("context", WorkHubContextView.as_view(), name="work-hub-context"),
    path("webhooks/grist", GristWebhookView.as_view(), name="work-hub-grist-webhook"),
]
