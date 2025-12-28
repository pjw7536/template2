"""RAG request logging helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import requests

from .config import RAG_ERROR_LOG_PATH

_rag_logger = logging.getLogger("api.rag")


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
