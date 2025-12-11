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
    value = os.environ.get(name)
    if value is None:
        value = getattr(settings, name, default)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _parse_headers(raw: str | None) -> Dict[str, str]:
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


def _parse_chunk_factor(raw: str | None) -> Dict[str, str | int] | None:
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


RAG_SEARCH_URL = _read_setting("ASSISTANT_RAG_URL") or _read_setting("RAG_SEARCH_URL", "")
RAG_INSERT_URL = _read_setting("ASSISTANT_RAG_INSERT_URL") or _read_setting("RAG_INSERT_URL", "")
RAG_DELETE_URL = _read_setting("ASSISTANT_RAG_DELETE_URL") or _read_setting("RAG_DELETE_URL", "")
RAG_INDEX_NAME = _read_setting("ASSISTANT_RAG_INDEX_NAME") or _read_setting("RAG_INDEX_NAME", "")
RAG_PERMISSION_GROUPS = (
    _parse_permission_groups(_read_setting("ASSISTANT_RAG_PERMISSION_GROUPS"))
    or _parse_permission_groups(_read_setting("RAG_PERMISSION_GROUPS"))
)
RAG_CHUNK_FACTOR = _parse_chunk_factor(_read_setting("ASSISTANT_RAG_CHUNK_FACTOR") or _read_setting("RAG_CHUNK_FACTOR"))
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


def _ensure_rag_error_logger() -> logging.Logger:
    """
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


def _log_rag_failure(action: str, payload: Dict[str, Any] | None, error: Exception) -> None:
    logger = _ensure_rag_error_logger()
    payload_data = payload.get("data", {}) if isinstance(payload, dict) else {}
    context = {
        "action": action,
        "index_name": payload.get("index_name") if isinstance(payload, dict) else None,
        "doc_id": payload_data.get("doc_id"),
        "email_id": payload_data.get("email_id"),
        "department_code": payload_data.get("department_code"),
        **_safe_response_details(getattr(error, "response", None)),
    }
    try:
        logger.error("RAG request failed | context=%s | error=%s", context, error)
    except Exception:
        logger.error("RAG request failed | error=%s", error)


def _build_insert_payload(email) -> Dict[str, Any]:
    created_time = getattr(email, "received_at", None) or timezone.now()
    payload: Dict[str, Any] = {
        "index_name": RAG_INDEX_NAME,
        "data": {
            "doc_id": getattr(email, "rag_doc_id", None),
            "title": email.subject,
            "content": email.body_text or "",
            "permission_groups": RAG_PERMISSION_GROUPS,
            "created_time": created_time.isoformat(),
            "department_code": email.department_code,
            "email_id": email.id,
            "sender": email.sender,
            "recipient": email.recipient,
            "received_at": created_time.isoformat(),
        },
    }
    if RAG_CHUNK_FACTOR:
        payload["chunk_factor"] = RAG_CHUNK_FACTOR
    return payload


def _build_delete_payload(doc_id: str) -> Dict[str, Any]:
    return {
        "index_name": RAG_INDEX_NAME,
        "permission_groups": RAG_PERMISSION_GROUPS,
        "doc_id": doc_id,
    }


def insert_email_to_rag(email):
    """Email 모델을 RAG 인덱스에 등록."""

    payload = _build_insert_payload(email)

    if not RAG_INSERT_URL:
        error = ValueError("RAG_INSERT_URL is not configured")
        _log_rag_failure("insert", payload, error)
        raise error
    if not RAG_INDEX_NAME:
        error = ValueError("RAG_INDEX_NAME is not configured")
        _log_rag_failure("insert", payload, error)
        raise error

    try:
        resp = requests.post(RAG_INSERT_URL, headers=RAG_HEADERS, json=payload, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        _log_rag_failure("insert", payload, exc)
        raise


def delete_rag_doc(doc_id: str):
    """RAG에서 doc_id에 해당하는 문서를 삭제."""

    payload = _build_delete_payload(doc_id)

    if not RAG_DELETE_URL:
        error = ValueError("RAG_DELETE_URL is not configured")
        _log_rag_failure("delete", payload, error)
        raise error
    if not RAG_INDEX_NAME:
        error = ValueError("RAG_INDEX_NAME is not configured")
        _log_rag_failure("delete", payload, error)
        raise error

    try:
        resp = requests.post(RAG_DELETE_URL, headers=RAG_HEADERS, json=payload, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        _log_rag_failure("delete", payload, exc)
        raise


def search_rag_by_department(query_text: str, department_codes: List[str], num_result_doc: int = 5):
    """
    department_code 필터를 적용하여 RAG 문서를 검색하는 예시 함수.
    - 모든 검색 요청은 department_code 필터를 포함해야 한다.
    """

    if not RAG_SEARCH_URL:
        raise ValueError("RAG_SEARCH_URL is not configured")
    if not RAG_INDEX_NAME:
        raise ValueError("RAG_INDEX_NAME is not configured")

    payload = {
        "index_name": RAG_INDEX_NAME,
        "permission_groups": RAG_PERMISSION_GROUPS,
        "query_text": query_text,
        "num_result_doc": num_result_doc,
        "filter": {
            "department_code": department_codes,
        },
    }
    resp = requests.post(RAG_SEARCH_URL, headers=RAG_HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()
