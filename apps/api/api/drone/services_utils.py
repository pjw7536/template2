from __future__ import annotations

import logging
import zlib
from typing import Any

from django.db import connection

logger = logging.getLogger(__name__)


def _lock_key(name: str) -> int:
    return int(zlib.crc32(name.encode("utf-8")))


def _try_advisory_lock(lock_id: int) -> bool:
    if connection.vendor != "postgresql":
        return True

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
        row = cursor.fetchone()
    return bool(row and row[0])


def _release_advisory_lock(lock_id: int) -> None:
    if connection.vendor != "postgresql":
        return

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
    except Exception:
        logger.exception("Failed to release advisory lock id=%s", lock_id)


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _parse_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed

