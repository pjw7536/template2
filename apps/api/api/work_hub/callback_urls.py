"""Grist가 Portal 인증을 요청하는 auth callback 경로를 등록합니다."""

from django.urls import path

from .views import GristForwardAuthLoginView, GristForwardAuthVerifyView


urlpatterns = [
    path("login", GristForwardAuthLoginView.as_view(), name="work-hub-grist-login"),
    path("verify", GristForwardAuthVerifyView.as_view(), name="work-hub-grist-verify"),
]
