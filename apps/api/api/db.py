"""Database helper utilities for the API views."""
from __future__ import annotations

from contextlib import contextmanager
from typing import List, Optional, Sequence

from django.db import connection


def _dictfetchall(cursor) -> List[dict]:
    """Return all rows from a cursor as a list of dictionaries."""

    columns = [col[0] for col in cursor.description] if cursor.description else []
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@contextmanager
def get_cursor():
    """Yield a database cursor and ensure it is closed afterwards."""

    with connection.cursor() as cursor:  # pragma: no cover - thin wrapper
        yield cursor


def run_query(sql: str, params: Optional[Sequence[object]] = None) -> List[dict]:
    """Execute a SELECT style query and return rows as dictionaries."""

    with get_cursor() as cursor:
        cursor.execute(sql, params or [])
        return _dictfetchall(cursor)


def execute(sql: str, params: Optional[Sequence[object]] = None) -> tuple[int, Optional[int]]:
    """Execute a data-modifying query and return affected row count and last row id."""

    with get_cursor() as cursor:
        cursor.execute(sql, params or [])
        lastrowid = None
        if cursor.description:
            try:
                row = cursor.fetchone()
            except Exception:  # pragma: no cover - defensive guard
                row = None
            if row:
                lastrowid = row[0]
        else:
            lastrowid = getattr(cursor, "lastrowid", None)
        return cursor.rowcount, lastrowid
