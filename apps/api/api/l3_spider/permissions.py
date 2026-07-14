from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission


L3_SPIDER_DEVELOPER_PERMISSION = "l3_spider.view_developer_options"


def can_view_developer_options(user: Any) -> bool:
    """사용자가 L3 Spider 개발자 옵션을 조회할 수 있는지 반환합니다."""

    return bool(
        getattr(user, "is_authenticated", False)
        and user.has_perm(L3_SPIDER_DEVELOPER_PERMISSION)
    )


class CanViewL3SpiderDeveloperOptions(BasePermission):
    """L3 Spider 개발자 옵션 custom permission을 검사합니다."""

    message = "L3 Spider 개발자 옵션 조회 권한이 없습니다."

    def has_permission(self, request, view) -> bool:
        """현재 요청 사용자의 개발자 옵션 조회 권한을 검사합니다."""

        return can_view_developer_options(request.user)
