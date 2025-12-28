# =============================================================================
# 모듈 설명: tables 서비스 파사드(공용 진입점)를 제공합니다.
# - 주요 대상: get_table_list_payload, update_table_record
# - 불변 조건: 구현은 services/* 모듈로 위임합니다.
# =============================================================================

"""tables 서비스 파사드 모듈입니다."""

from __future__ import annotations

from .compat import execute, resolve_table_schema, selectors
from .listing import get_table_list_payload
from .types import TableNotFoundError, TableRecordNotFoundError, TableUpdateResult
from .update import update_table_record

__all__ = [
    "TableNotFoundError",
    "TableRecordNotFoundError",
    "TableUpdateResult",
    "execute",
    "get_table_list_payload",
    "resolve_table_schema",
    "selectors",
    "update_table_record",
]
