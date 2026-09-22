"""Django settings 기반 RAG 설정을 엄격하게 로드합니다."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from django.conf import settings


class RagConfigError(ValueError):
    """RAG 설정 형식이나 필수 값이 올바르지 않을 때 발생합니다."""


def _parse_json_object(raw: object, *, setting_name: str) -> dict[str, Any]:
    """JSON object 설정을 파싱하고 잘못된 형식은 명시적으로 거절합니다."""

    if raw in (None, ""):
        return {}
    if isinstance(raw, dict):
        parsed = raw
    else:
        try:
            parsed = json.loads(str(raw))
        except (json.JSONDecodeError, TypeError) as exc:
            raise RagConfigError(f"{setting_name}은 JSON object여야 합니다.") from exc
    if not isinstance(parsed, dict):
        raise RagConfigError(f"{setting_name}은 JSON object여야 합니다.")
    return parsed


def _parse_headers(raw: object) -> dict[str, str]:
    """RAG_HEADERS를 문자열 header dict로 검증합니다."""

    parsed = _parse_json_object(raw, setting_name="RAG_HEADERS")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    for key, value in parsed.items():
        if not isinstance(key, str) or not isinstance(value, (str, int, float, bool)):
            raise RagConfigError("RAG_HEADERS의 key/value는 문자열 변환 가능한 scalar여야 합니다.")
        headers[key] = str(value)
    return headers


def _parse_permission_groups(raw: object) -> list[str]:
    """RAG_PERMISSION_GROUPS JSON 배열을 문자열 목록으로 검증합니다."""

    if raw in (None, ""):
        return []
    if isinstance(raw, (list, tuple)):
        parsed = list(raw)
    else:
        try:
            parsed = json.loads(str(raw))
        except (json.JSONDecodeError, TypeError) as exc:
            raise RagConfigError("RAG_PERMISSION_GROUPS는 JSON array여야 합니다.") from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise RagConfigError("RAG_PERMISSION_GROUPS는 문자열 JSON array여야 합니다.")
    return list(dict.fromkeys(item.strip() for item in parsed if item.strip()))


def _parse_index_list(raw: object) -> list[str]:
    """comma-separated RAG index allowlist를 정규화합니다."""

    if raw in (None, ""):
        return []
    values = raw if isinstance(raw, (list, tuple)) else str(raw).split(",")
    if any(not isinstance(value, str) for value in values):
        raise RagConfigError("RAG_INDEX_LIST는 문자열 목록이어야 합니다.")
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _normalize_string_sequence(
    values: Sequence[str] | str | None,
    *,
    split_commas: bool = False,
    dedupe: bool = False,
) -> list[str]:
    """요청 단계 문자열 목록을 공통 규칙으로 정규화합니다."""

    if not values:
        return []
    raw_values = values.split(",") if isinstance(values, str) and split_commas else [values] if isinstance(values, str) else list(values)
    normalized = [str(value).strip() for value in raw_values if value is not None and str(value).strip()]
    return list(dict.fromkeys(normalized)) if dedupe else normalized


def _normalize_permission_groups(groups: Sequence[str] | str | None) -> list[str]:
    """요청 권한 그룹을 문자열 목록으로 정규화합니다."""

    return _normalize_string_sequence(groups)


def _normalize_index_names(index_names: Sequence[str] | str | None) -> list[str]:
    """요청 index 이름을 중복 없는 목록으로 정규화합니다."""

    return _normalize_string_sequence(index_names, split_commas=True, dedupe=True)


@dataclass(frozen=True)
class RagConfig:
    """RAG adapter가 사용하는 immutable 설정입니다."""

    search_url: str
    insert_url: str
    delete_url: str
    index_info_url: str
    index_default: str
    index_emails: str
    index_list: tuple[str, ...]
    permission_groups: tuple[str, ...]
    public_group: str
    headers: dict[str, str]
    chunk_factor: dict[str, Any]
    timeout_seconds: int
    num_docs: int
    error_log_path: str

    @classmethod
    def from_settings(cls) -> "RagConfig":
        """canonical RAG_* Django settings만 읽어 설정을 생성합니다."""

        public_group = str(getattr(settings, "RAG_PUBLIC_GROUP", "rag-public") or "").strip()
        permission_groups = _parse_permission_groups(getattr(settings, "RAG_PERMISSION_GROUPS", ""))
        if not permission_groups and public_group:
            permission_groups = [public_group]
        index_default = str(getattr(settings, "RAG_INDEX_DEFAULT", "") or "").strip()
        index_emails = str(getattr(settings, "RAG_INDEX_EMAILS", "") or "").strip()
        index_list = _parse_index_list(getattr(settings, "RAG_INDEX_LIST", ""))
        for index_name in (index_default, index_emails):
            if index_name and index_name not in index_list:
                index_list.append(index_name)
        try:
            timeout_seconds = max(1, int(getattr(settings, "RAG_TIMEOUT_SECONDS", 30) or 30))
        except (TypeError, ValueError) as exc:
            raise RagConfigError("RAG_TIMEOUT_SECONDS는 양의 정수여야 합니다.") from exc
        try:
            num_docs = max(1, int(getattr(settings, "RAG_NUM_DOCS", 5) or 5))
        except (TypeError, ValueError) as exc:
            raise RagConfigError("RAG_NUM_DOCS는 양의 정수여야 합니다.") from exc
        return cls(
            search_url=str(getattr(settings, "RAG_SEARCH_URL", "") or "").strip(),
            insert_url=str(getattr(settings, "RAG_INSERT_URL", "") or "").strip(),
            delete_url=str(getattr(settings, "RAG_DELETE_URL", "") or "").strip(),
            index_info_url=str(getattr(settings, "RAG_INDEX_INFO_URL", "") or "").strip(),
            index_default=index_default,
            index_emails=index_emails,
            index_list=tuple(index_list),
            permission_groups=tuple(permission_groups),
            public_group=public_group,
            headers=_parse_headers(getattr(settings, "RAG_HEADERS", "")),
            chunk_factor=_parse_json_object(
                getattr(settings, "RAG_CHUNK_FACTOR", ""),
                setting_name="RAG_CHUNK_FACTOR",
            ),
            timeout_seconds=timeout_seconds,
            num_docs=num_docs,
            error_log_path=str(
                getattr(settings, "RAG_ERROR_LOG_PATH", "")
                or Path(settings.BASE_DIR) / "logs" / "rag_errors.log"
            ),
        )


RAG_CONFIG = RagConfig.from_settings()
RAG_SEARCH_URL = RAG_CONFIG.search_url
RAG_INSERT_URL = RAG_CONFIG.insert_url
RAG_DELETE_URL = RAG_CONFIG.delete_url
RAG_INDEX_INFO_URL = RAG_CONFIG.index_info_url
RAG_INDEX_DEFAULT = RAG_CONFIG.index_default
RAG_INDEX_EMAILS = RAG_CONFIG.index_emails
RAG_INDEX_LIST = list(RAG_CONFIG.index_list)
RAG_PERMISSION_GROUPS = list(RAG_CONFIG.permission_groups)
RAG_PUBLIC_GROUP = RAG_CONFIG.public_group
RAG_HEADERS = dict(RAG_CONFIG.headers)
RAG_CHUNK_FACTOR = dict(RAG_CONFIG.chunk_factor)
RAG_TIMEOUT_SECONDS = RAG_CONFIG.timeout_seconds
RAG_NUM_DOCS = RAG_CONFIG.num_docs
RAG_ERROR_LOG_PATH = RAG_CONFIG.error_log_path


__all__ = [
    "RAG_CHUNK_FACTOR",
    "RAG_CONFIG",
    "RAG_DELETE_URL",
    "RAG_HEADERS",
    "RAG_INDEX_DEFAULT",
    "RAG_INDEX_EMAILS",
    "RAG_INDEX_INFO_URL",
    "RAG_INDEX_LIST",
    "RAG_INSERT_URL",
    "RAG_PERMISSION_GROUPS",
    "RAG_PUBLIC_GROUP",
    "RAG_SEARCH_URL",
    "RAG_TIMEOUT_SECONDS",
    "RAG_NUM_DOCS",
    "RagConfig",
    "RagConfigError",
    "_normalize_index_names",
    "_normalize_permission_groups",
]
