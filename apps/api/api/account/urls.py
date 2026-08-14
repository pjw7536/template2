"""Keycloak 전환 후 유지하는 Account 읽기 전용 URL을 정의합니다."""

from django.urls import path

from .views import AccountUserPoolView, LineSdwtOptionsView


urlpatterns = [
    path("users", AccountUserPoolView.as_view(), name="account-users"),
    path("line-sdwt-options", LineSdwtOptionsView.as_view(), name="account-line-sdwt-options"),
]
