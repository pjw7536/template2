# =============================================================================
# 모듈 설명: voc 서비스 파사드(export)를 제공합니다.
# - 주요 함수: create_post, update_post, delete_post, add_reply, can_manage_post
# - 불변 조건: 외부에서는 이 파사드만 호출합니다.
# =============================================================================

"""VOC 서비스 파사드."""

from __future__ import annotations

from .posts import add_reply, can_manage_post, create_post, delete_post, update_post

__all__ = [
    "add_reply",
    "can_manage_post",
    "create_post",
    "delete_post",
    "update_post",
]
