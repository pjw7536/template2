"""Tables feature service facade."""

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
