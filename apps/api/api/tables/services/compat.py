# =============================================================================
# 모듈 설명: tables 서비스에서 사용하는 공용 호환 인터페이스를 제공합니다.
# - 주요 대상: execute, resolve_table_schema, selectors
# - 불변 조건: 공용 헬퍼를 그대로 재노출합니다.
# =============================================================================

from __future__ import annotations

from api.common.db import execute
from api.common.utils import resolve_table_schema

from .. import selectors

__all__ = ["execute", "resolve_table_schema", "selectors"]
