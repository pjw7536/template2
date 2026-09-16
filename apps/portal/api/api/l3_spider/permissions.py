from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission

from api.account import services as account_services


L3_SPIDER_SCOPE = "l3-spider"


def can_view_developer_options(user: Any, *, request: Any | None = None) -> bool:
    """L3 Spider admin 역할 보유 여부를 반환합니다."""

    return account_services.has_scope_role(
        user=user,
        scope_key=L3_SPIDER_SCOPE,
        request=request,
    )


class CanViewL3SpiderDeveloperOptions(BasePermission):
    """L3 Spider admin 역할을 검사합니다."""

    message = "L3 Spider 개발자 옵션 조회 권한이 없습니다."

    def has_permission(self, request, view) -> bool:
        """현재 요청 사용자의 개발자 옵션 조회 권한을 검사합니다."""

        return can_view_developer_options(request.user, request=request)
