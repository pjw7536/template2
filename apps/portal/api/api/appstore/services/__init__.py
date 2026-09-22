# =============================================================================
# 모듈 설명: appstore 서비스 파사드(공용 진입점)를 제공합니다.
# - 주요 대상: 앱/댓글 CRUD, 앱 노출 순서, dev seed, 좋아요/조회수 갱신
# - 불변 조건: 구현은 services/* 모듈로 위임합니다.
# =============================================================================

"""AppStore 도메인 서비스 파사드입니다."""

from __future__ import annotations

from .apps import (
    AppOrderConflictError,
    build_app_order_version,
    create_app,
    delete_app,
    reorder_apps,
    update_app,
)
from .comments import create_comment, delete_comment, toggle_comment_like, update_comment
from .dev_data import seed_appstore_dummy_data
from .likes import increment_view_count, toggle_like

__all__ = [
    "AppOrderConflictError",
    "build_app_order_version",
    "create_app",
    "create_comment",
    "delete_app",
    "delete_comment",
    "increment_view_count",
    "reorder_apps",
    "seed_appstore_dummy_data",
    "toggle_comment_like",
    "toggle_like",
    "update_app",
    "update_comment",
]
