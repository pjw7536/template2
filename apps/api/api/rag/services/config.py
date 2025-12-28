"""RAG settings and normalization helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence

from django.conf import settings


def _read_setting(name: str, default: str | None = None) -> str | None:
    """환경변수/설정에서 값을 읽어 문자열로 반환합니다."""

    value = os.environ.get(name)
    if value is None:
        value = getattr(settings, name, default)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _parse_headers(raw: str | None) -> Dict[str, str]:
    """JSON 문자열로 된 헤더 설정을 dict[str, str]로 파싱합니다."""

    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}

    headers: Dict[str, str] = {}
    for key, value in parsed.items():
        if isinstance(key, str) and isinstance(value, (str, int, float, bool)):
            headers[key] = str(value)
    return headers


def _parse_permission_groups(raw: str | None) -> List[str]:
    """권한 그룹 설정(JSON 배열 또는 CSV)을 문자열 리스트로 정규화합니다."""

    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes, bytearray)):
        return [str(item).strip() for item in parsed if str(item).strip()]

    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]

    return []


def _parse_index_list(raw: str | None) -> List[str]:
    """인덱스 목록 설정(JSON 배열 또는 CSV)을 문자열 리스트로 정규화합니다."""

    return _parse_permission_groups(raw)


def _parse_chunk_factor(raw: str | None) -> Dict[str, str | int] | None:
    """chunk_factor 설정(JSON 객체)을 정상화해 dict로 반환합니다."""

    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    normalized: Dict[str, str | int] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, (str, int)):
            normalized[key] = value
    return normalized or None


def _normalize_permission_groups(groups: Sequence[str] | str | None) -> List[str]:
    """permission_groups 입력을 문자열 리스트로 정규화합니다."""

    if not groups:
        return []
    if isinstance(groups, str):
        values = [groups]
    elif isinstance(groups, Sequence):
        values = list(groups)
    else:
        return []

    normalized: List[str] = []
    for value in values:
        if value is None:
            continue
        cleaned = str(value).strip()
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _normalize_index_names(index_names: Sequence[str] | str | None) -> List[str]:
    """index_name 입력을 문자열 리스트로 정규화합니다."""

    if not index_names:
        return []
    if isinstance(index_names, str):
        values = index_names.split(",")
    elif isinstance(index_names, Sequence):
        values = list(index_names)
    else:
        return []

    normalized: List[str] = []
    for value in values:
        if value is None:
            continue
        cleaned = str(value).strip()
        if cleaned:
            normalized.append(cleaned)
    return list(dict.fromkeys(normalized))


RAG_SEARCH_URL = _read_setting("ASSISTANT_RAG_URL") or _read_setting("RAG_SEARCH_URL", "")
RAG_INSERT_URL = _read_setting("ASSISTANT_RAG_INSERT_URL") or _read_setting("RAG_INSERT_URL", "")
RAG_DELETE_URL = _read_setting("ASSISTANT_RAG_DELETE_URL") or _read_setting("RAG_DELETE_URL", "")
RAG_INDEX_NAME = _read_setting("ASSISTANT_RAG_INDEX_NAME") or _read_setting("RAG_INDEX_NAME", "")
RAG_INDEX_DEFAULT = (
    _read_setting("ASSISTANT_RAG_INDEX_DEFAULT")
    or _read_setting("RAG_INDEX_DEFAULT")
    or RAG_INDEX_NAME
    or ""
)
RAG_INDEX_EMAILS = (
    _read_setting("ASSISTANT_RAG_INDEX_EMAILS")
    or _read_setting("RAG_INDEX_EMAILS")
    or ""
)
RAG_INDEX_LIST = _parse_index_list(
    _read_setting("ASSISTANT_RAG_INDEX_LIST") or _read_setting("RAG_INDEX_LIST")
)
RAG_PERMISSION_GROUPS = (
    _parse_permission_groups(_read_setting("ASSISTANT_RAG_PERMISSION_GROUPS"))
    or _parse_permission_groups(_read_setting("RAG_PERMISSION_GROUPS"))
)
RAG_PUBLIC_GROUP = "rag-public"
RAG_CHUNK_FACTOR = _parse_chunk_factor(
    _read_setting("ASSISTANT_RAG_CHUNK_FACTOR") or _read_setting("RAG_CHUNK_FACTOR")
)
RAG_ERROR_LOG_PATH = _read_setting("RAG_ERROR_LOG_PATH") or str(Path(settings.BASE_DIR) / "logs" / "rag_errors.log")

_custom_headers = _parse_headers(_read_setting("ASSISTANT_RAG_HEADERS")) or _parse_headers(_read_setting("RAG_HEADERS"))
if _custom_headers:
    RAG_HEADERS = {"Content-Type": "application/json", **_custom_headers}
else:
    RAG_HEADERS = {
        "Content-Type": "application/json",
        "x-dep-ticket": _read_setting("RAG_PASS_KEY", "") or "",
        "api-key": _read_setting("RAG_API_KEY", "") or "",
    }

if not RAG_PERMISSION_GROUPS:
    RAG_PERMISSION_GROUPS = [RAG_PUBLIC_GROUP]

_resolved_index_list: List[str] = []
for value in [*RAG_INDEX_LIST, RAG_INDEX_DEFAULT, RAG_INDEX_EMAILS]:
    cleaned = str(value).strip() if isinstance(value, str) else ""
    if cleaned and cleaned not in _resolved_index_list:
        _resolved_index_list.append(cleaned)
RAG_INDEX_LIST = _resolved_index_list

__all__ = [
    "RAG_CHUNK_FACTOR",
    "RAG_DELETE_URL",
    "RAG_HEADERS",
    "RAG_INDEX_DEFAULT",
    "RAG_INDEX_EMAILS",
    "RAG_INDEX_LIST",
    "RAG_INDEX_NAME",
    "RAG_INSERT_URL",
    "RAG_PUBLIC_GROUP",
    "RAG_PERMISSION_GROUPS",
    "RAG_SEARCH_URL",
    "_normalize_index_names",
    "_normalize_permission_groups",
]
