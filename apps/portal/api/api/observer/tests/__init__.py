# =============================================================================
# 모듈 설명: observer 엔드포인트 테스트를 제공합니다.
# - 주요 클래스: ObserverEndpointTests
# - 불변 조건: URL 네임(observer-*)이 등록되어 있어야 합니다.
# =============================================================================

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import Mock, patch
from uuid import UUID
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse

from api.common.services import ExternalCallCancellation

from api.observer import selectors
from api.observer import serializers as observer_serializers
from api.observer.services.analysis import (
    ANALYSIS_SYSTEM_PROMPT,
    MAX_PROMPT_CHARS,
    OBSERVER_ANALYSIS_PROMPT_VERSION,
    analyze_observer_logs_stream,
    build_observer_analysis_context,
    build_observer_analysis_messages,
    normalize_observer_analysis_result,
)
from api.observer.services.openwebui import (
    ObserverOpenWebUIConfig,
    ObserverOpenWebUIError,
    stream_observer_analysis,
)
from api.observer.services.timezone import observer_period_start



class RemovedObserverCompatibilityRoutesTests(TestCase):
    """삭제한 Observer 호환 경로가 다시 등록되지 않게 보장합니다."""

    def test_removed_analysis_routes_do_not_resolve(self) -> None:
        """Observer 분석은 Assistant Turn을 통해서만 실행해야 합니다."""

        for path in (
            "/api/v1/observer/analysis",
            "/api/v1/observer/analysis/stream",
            "/api/v1/observer/equipment-info/LINE-A/EQP-ALPHA",
            "/api/v1/observer/logs",
            "/api/v1/observer/logs/eqp",
            "/api/v1/observer/logs/tip",
            "/api/v1/observer/logs/spc-interlock",
            "/api/v1/observer/logs/fdc-interlock",
            "/api/v1/observer/logs/ctttm",
            "/api/v1/observer/logs/racb",
            "/api/v1/observer/logs/esop",
        ):
            with self.subTest(path=path), self.assertRaises(Resolver404):
                resolve(path)

def _allow_test_scope_access(test_case: TestCase) -> None:
    """도메인 endpoint 테스트에서 공통 portal/app 권한 경계를 격리합니다."""

    patcher = patch(
        "api.account.services.get_access_payload",
        return_value={"allowed": True},
    )
    patcher.start()
    test_case.addCleanup(patcher.stop)

OBSERVER_VIEW_SELECTORS = "api.observer.views.selectors"
OBSERVER_METADATA_SELECTORS = "api.observer.selectors.metadata"
OBSERVER_TKIN_SELECTORS = "api.observer.selectors.tkin"
OBSERVER_SOURCE_SELECTORS = "api.observer.selectors.sources"
OBSERVER_SELECTORS = OBSERVER_SOURCE_SELECTORS
OBSERVER_LOG_SELECTORS = "api.observer.selectors.logs"


def _fetch_observer_source_logs(
    *,
    eqp_id: str,
    log_key: str,
    start_at: object | None = None,
    end_at: object | None = None,
    limit: int | None = None,
):
    """source adapter의 정규화 결과를 endpoint와 독립적으로 조회합니다."""

    from api.observer.selectors.logs import _fetch_logs_by_type_normalized

    return _fetch_logs_by_type_normalized(
        eqp_key=selectors.normalize_id(eqp_id),
        type_key=log_key,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )


__all__ = [name for name in globals() if not name.startswith("__")]
