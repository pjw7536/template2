"""Grist 서버 간 Webhook 인증 permission입니다."""

from __future__ import annotations

import secrets
from typing import Any

from rest_framework.permissions import BasePermission

from .services.webhook import build_grist_webhook_token


class HasGristWebhookSecret(BasePermission):
    """요청 대상 전용 Bearer token과 constant-time 비교한 요청만 허용합니다."""

    message = "유효한 Grist Webhook secret이 필요합니다."

    def has_permission(self, request: Any, view: Any) -> bool:
        """Authorization header에서 Bearer secret을 읽고 안전하게 비교합니다."""

        expected = build_grist_webhook_token(
            doc_id=str(request.query_params.get("doc_id") or ""),
            table_id=str(request.query_params.get("table_id") or ""),
        )
        provided_header = str(request.headers.get("Authorization", "") or "")
        prefix = "Bearer "
        provided = provided_header[len(prefix):] if provided_header.startswith(prefix) else ""
        return bool(expected and provided and secrets.compare_digest(provided, expected))
