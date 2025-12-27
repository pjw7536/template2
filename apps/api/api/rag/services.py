"""RAG integration services (index naming, search, insert, delete)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence

import requests
from django.conf import settings
from django.utils import timezone


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

_rag_logger = logging.getLogger("api.rag")

if not RAG_PERMISSION_GROUPS:
    RAG_PERMISSION_GROUPS = [RAG_PUBLIC_GROUP]

_resolved_index_list: List[str] = []
for value in [*RAG_INDEX_LIST, RAG_INDEX_DEFAULT, RAG_INDEX_EMAILS]:
    cleaned = str(value).strip() if isinstance(value, str) else ""
    if cleaned and cleaned not in _resolved_index_list:
        _resolved_index_list.append(cleaned)
RAG_INDEX_LIST = _resolved_index_list


def _resolve_email_permission_groups(email: Any) -> List[str]:
    """이메일의 user_sdwt_prod 값을 permission_groups로 변환합니다."""

    groups: List[str] = []
    raw_group = getattr(email, "user_sdwt_prod", None)
    if isinstance(raw_group, str) and raw_group.strip():
        groups.append(raw_group.strip())
    raw_sender_id = getattr(email, "sender_id", None)
    if isinstance(raw_sender_id, str) and raw_sender_id.strip():
        groups.append(raw_sender_id.strip())
    if groups:
        return list(dict.fromkeys(groups))
    return _normalize_permission_groups(RAG_PERMISSION_GROUPS) or [RAG_PUBLIC_GROUP]


def _ensure_rag_error_logger() -> logging.Logger:
    """RAG 실패 로그를 파일로 남기기 위한 로거 핸들러를 보장합니다.

    Attach a file handler for RAG failures so we can inspect errors after POP3 ingest.
    """

    if not RAG_ERROR_LOG_PATH:
        return _rag_logger

    log_path = Path(RAG_ERROR_LOG_PATH)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return _rag_logger

    has_handler = any(
        isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", "") == str(log_path)
        for handler in _rag_logger.handlers
    )
    if not has_handler:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        _rag_logger.addHandler(file_handler)

    if _rag_logger.level == logging.NOTSET:
        _rag_logger.setLevel(logging.INFO)
    return _rag_logger


def _safe_response_details(response: requests.Response | None) -> Dict[str, Any]:
    """예외 객체에 담긴 Response 정보를 안전하게 요약합니다."""

    if response is None:
        return {}
    try:
        text = response.text
    except Exception:
        text = "<unavailable>"

    if len(text) > 500:
        text = f"{text[:500]}...(truncated)"

    return {
        "status_code": response.status_code,
        "response_text": text,
    }


def _log_rag_failure(
    action: str,
    payload: Dict[str, Any] | None,
    error: Exception,
    *,
    response: requests.Response | None = None,
) -> None:
    """RAG 요청 실패를 파일/표준 로거에 구조화된 형태로 기록합니다."""

    logger = _ensure_rag_error_logger()
    payload_data = payload.get("data", {}) if isinstance(payload, dict) else {}
    if not isinstance(payload_data, dict):
        payload_data = {}

    doc_id = payload_data.get("doc_id")
    if not doc_id and isinstance(payload, dict):
        doc_id = payload.get("doc_id")

    email_id = payload_data.get("email_id")
    if not email_id and isinstance(payload, dict):
        email_id = payload.get("email_id")

    department = payload_data.get("department")
    if not department and isinstance(payload, dict):
        department = payload.get("department")

    query_text_preview = None
    if isinstance(payload, dict):
        query_text = payload.get("query_text")
        if isinstance(query_text, str):
            normalized = query_text.strip()
            if len(normalized) > 200:
                normalized = f"{normalized[:200]}...(truncated)"
            query_text_preview = normalized or None

    context = {
        "action": action,
        "index_name": payload.get("index_name") if isinstance(payload, dict) else None,
        "doc_id": doc_id,
        "email_id": email_id,
        "department": department,
        "query_text_preview": query_text_preview,
        "num_result_doc": payload.get("num_result_doc") if isinstance(payload, dict) else None,
        **_safe_response_details(getattr(error, "response", None) or response),
    }
    try:
        logger.error("RAG request failed | context=%s | error=%s", context, error)
    except Exception:
        logger.error("RAG request failed | error=%s", error)


def get_rag_index_candidates() -> List[str]:
    """허용 가능한 RAG 인덱스 후보 목록을 반환합니다."""

    return list(RAG_INDEX_LIST)


def resolve_rag_index_name(index_name: str | None) -> str:
    """RAG 인덱스명을 결정합니다."""

    resolved = index_name.strip() if isinstance(index_name, str) else ""
    if resolved:
        return resolved

    default_index = str(RAG_INDEX_DEFAULT or "").strip()
    if default_index:
        return default_index
    if RAG_INDEX_LIST:
        return RAG_INDEX_LIST[0]
    return ""


def resolve_rag_index_names(index_names: Sequence[str] | str | None) -> List[str]:
    """RAG 인덱스 목록을 정규화하고 기본값을 보정합니다."""

    resolved = _normalize_index_names(index_names)
    if resolved:
        return resolved
    fallback = resolve_rag_index_name(None)
    return [fallback] if fallback else []


def _build_insert_payload(
    email: Any,
    index_name: str | None = None,
    permission_groups: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """이메일 객체를 RAG insert 요청 payload로 변환합니다."""

    resolved_index_name = resolve_rag_index_name(index_name)
    created_time = getattr(email, "received_at", None) or timezone.now()
    recipient_value = getattr(email, "recipient", None)
    if isinstance(recipient_value, (list, tuple)):
        recipient = ", ".join([str(item).strip() for item in recipient_value if str(item).strip()])
    else:
        recipient = recipient_value
    resolved_permission_groups = (
        _normalize_permission_groups(permission_groups)
        if permission_groups is not None
        else _normalize_permission_groups(RAG_PERMISSION_GROUPS)
    )
    payload: Dict[str, Any] = {
        "index_name": resolved_index_name,
        "data": {
            "doc_id": getattr(email, "rag_doc_id", None),
            "title": email.subject,
            "content": email.body_text or "",
            "permission_groups": resolved_permission_groups,
            "created_time": created_time.isoformat(),
            "department": getattr(email, "department", None),
            "line": getattr(email, "line", None),
            "user_sdwt_prod": getattr(email, "user_sdwt_prod", None),
            "email_id": email.id,
            "sender": email.sender,
            "recipient": recipient,
            "received_at": created_time.isoformat(),
        },
    }
    if RAG_CHUNK_FACTOR:
        payload["chunk_factor"] = RAG_CHUNK_FACTOR
    return payload


def _build_delete_payload(
    doc_id: str,
    index_name: str | None = None,
    permission_groups: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """doc_id 기반 RAG delete 요청 payload를 생성합니다."""

    resolved_index_name = resolve_rag_index_name(index_name)
    resolved_permission_groups = (
        _normalize_permission_groups(permission_groups)
        if permission_groups is not None
        else _normalize_permission_groups(RAG_PERMISSION_GROUPS)
    )
    return {
        "index_name": resolved_index_name,
        "permission_groups": resolved_permission_groups,
        "doc_id": doc_id,
    }


def _build_search_payload(
    query_text: str,
    *,
    index_name: Sequence[str] | str | None = None,
    num_result_doc: int = 5,
    permission_groups: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """RAG search 요청 payload를 생성합니다."""

    resolved_index_names = resolve_rag_index_names(index_name)
    resolved_index_name = ",".join(resolved_index_names)

    normalized_query = str(query_text).strip()
    normalized_num = int(num_result_doc) if isinstance(num_result_doc, int) else 5
    if normalized_num <= 0:
        normalized_num = 5

    return {
        "index_name": resolved_index_name,
        "permission_groups": _normalize_permission_groups(permission_groups)
        if permission_groups is not None
        else _normalize_permission_groups(RAG_PERMISSION_GROUPS),
        "query_text": normalized_query,
        "num_result_doc": normalized_num,
    }


def search_rag(
    query_text: str,
    *,
    index_name: Sequence[str] | str | None = None,
    num_result_doc: int = 5,
    permission_groups: Sequence[str] | None = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """RAG에서 query_text 기반으로 문서 검색.

    Args:
        query_text: 검색 질의문
        index_name: 인덱스명 또는 인덱스명 리스트 (없으면 기본값 사용)
        num_result_doc: 반환 문서 개수
        permission_groups: 권한 그룹 override (없으면 기본값 사용)
        timeout: HTTP timeout (seconds)

    Returns:
        RAG 서버의 JSON 응답 dict

    Raises:
        ValueError: 필수 설정이 누락된 경우
        requests.RequestException: 네트워크/HTTP 오류
        json.JSONDecodeError: JSON 파싱 실패
    """

    payload = _build_search_payload(
        query_text,
        index_name=index_name,
        num_result_doc=num_result_doc,
        permission_groups=permission_groups,
    )

    resolved_index_name = payload.get("index_name")

    if not RAG_SEARCH_URL:
        error = ValueError("RAG_SEARCH_URL is not configured")
        _log_rag_failure("search", payload, error)
        raise error
    if not resolved_index_name:
        error = ValueError("RAG_INDEX_DEFAULT is not configured")
        _log_rag_failure("search", payload, error)
        raise error
    if not payload.get("query_text"):
        error = ValueError("query_text is empty")
        _log_rag_failure("search", payload, error)
        raise error

    try:
        resp = requests.post(RAG_SEARCH_URL, headers=RAG_HEADERS, json=payload, timeout=max(1, int(timeout)))
        resp.raise_for_status()
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            _log_rag_failure("search", payload, exc, response=resp)
            raise
    except Exception as exc:
        _log_rag_failure("search", payload, exc)
        raise


def insert_email_to_rag(
    email: Any,
    index_name: str | None = None,
    permission_groups: Sequence[str] | None = None,
) -> None:
    """Email 모델을 RAG 인덱스에 등록."""

    resolved_permission_groups = (
        _resolve_email_permission_groups(email)
        if permission_groups is None
        else _normalize_permission_groups(permission_groups)
    )
    payload = _build_insert_payload(
        email,
        index_name=index_name,
        permission_groups=resolved_permission_groups,
    )

    resolved_index_name = payload.get("index_name")

    if not RAG_INSERT_URL:
        error = ValueError("RAG_INSERT_URL is not configured")
        _log_rag_failure("insert", payload, error)
        raise error
    if not resolved_index_name:
        error = ValueError("RAG_INDEX_DEFAULT is not configured")
        _log_rag_failure("insert", payload, error)
        raise error

    try:
        resp = requests.post(RAG_INSERT_URL, headers=RAG_HEADERS, json=payload, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        _log_rag_failure("insert", payload, exc)
        raise


def delete_rag_doc(
    doc_id: str,
    index_name: str | None = None,
    permission_groups: Sequence[str] | None = None,
) -> None:
    """RAG에서 doc_id에 해당하는 문서를 삭제."""

    payload = _build_delete_payload(doc_id, index_name=index_name, permission_groups=permission_groups)

    resolved_index_name = payload.get("index_name")

    if not RAG_DELETE_URL:
        error = ValueError("RAG_DELETE_URL is not configured")
        _log_rag_failure("delete", payload, error)
        raise error
    if not resolved_index_name:
        error = ValueError("RAG_INDEX_DEFAULT is not configured")
        _log_rag_failure("delete", payload, error)
        raise error

    try:
        resp = requests.post(RAG_DELETE_URL, headers=RAG_HEADERS, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        _log_rag_failure("delete", payload, exc)
        raise


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
    "delete_rag_doc",
    "insert_email_to_rag",
    "get_rag_index_candidates",
    "search_rag",
    "resolve_rag_index_name",
    "resolve_rag_index_names",
]
