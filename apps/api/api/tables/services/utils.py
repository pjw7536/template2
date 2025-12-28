from __future__ import annotations

from .types import TableNotFoundError


def _raise_if_table_missing(exc: Exception, table_name: str) -> None:
    error_code = getattr(exc, "code", None) or getattr(exc, "pgcode", None)
    if error_code in {"ER_NO_SUCH_TABLE", "42P01"}:
        raise TableNotFoundError(table_name=table_name) from exc
