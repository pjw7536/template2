# =============================================================================
# 모듈 설명: RAG 요청 실패 로깅 헬퍼를 제공합니다.
# - 주요 대상: _ensure_rag_error_logger, _log_rag_failure
# - 불변 조건: RAG_ERROR_LOG_PATH가 있으면 파일 로깅을 시도합니다.
# =============================================================================

"""RAG 요청 실패 로그를 기록하는 헬퍼 모음.

- 주요 대상: _ensure_rag_error_logger, _log_rag_failure
- 주요 엔드포인트/클래스: 없음(헬퍼 함수 제공)
- 가정/불변 조건: RAG_ERROR_LOG_PATH가 있으면 파일 로깅을 시도함
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import requests

from .config import RAG_ERROR_LOG_PATH

_rag_logger = logging.getLogger("api.rag")


def _ensure_rag_error_logger() -> logging.Logger:
    """RAG 실패 로그를 파일로 남기기 위한 로거 핸들러를 보장합니다.

    입력:
    - 없음

    반환:
    - logging.Logger: 구성된 로거

    부작용:
    - 로그 디렉터리 생성 및 파일 핸들러 추가 가능

    오류:
    - 없음(파일 작업 실패 시 기본 로거 반환)
    """

    # -----------------------------------------------------------------------------
    # 1) 로그 경로 확인
    # -----------------------------------------------------------------------------
    if not RAG_ERROR_LOG_PATH:
        return _rag_logger

    # -----------------------------------------------------------------------------
    # 2) 로그 디렉터리 생성 시도
    # -----------------------------------------------------------------------------
    log_path = Path(RAG_ERROR_LOG_PATH)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return _rag_logger

    # -----------------------------------------------------------------------------
    # 3) 파일 핸들러 유무 확인 및 추가
    # -----------------------------------------------------------------------------
    has_handler = any(
        isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", "") == str(log_path)
        for handler in _rag_logger.handlers
    )
    if not has_handler:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        _rag_logger.addHandler(file_handler)

    # -----------------------------------------------------------------------------
    # 4) 로거 레벨 보정
    # -----------------------------------------------------------------------------
    if _rag_logger.level == logging.NOTSET:
        _rag_logger.setLevel(logging.INFO)
    return _rag_logger


def _safe_response_details(response: requests.Response | None) -> Dict[str, Any]:
    """응답 객체 정보를 안전하게 요약합니다.

    입력:
    - response: requests.Response 또는 None

    반환:
    - Dict[str, Any]: 상태 코드와 응답 텍스트 요약

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 응답 객체 유무 확인
    # -----------------------------------------------------------------------------
    if response is None:
        return {}
    # -----------------------------------------------------------------------------
    # 2) 응답 텍스트 읽기
    # -----------------------------------------------------------------------------
    try:
        text = response.text
    except Exception:
        text = "<unavailable>"

    # -----------------------------------------------------------------------------
    # 3) 길이 제한 적용
    # -----------------------------------------------------------------------------
    if len(text) > 500:
        text = f"{text[:500]}...(truncated)"

    # -----------------------------------------------------------------------------
    # 4) 요약 결과 반환
    # -----------------------------------------------------------------------------
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
    """RAG 요청 실패를 파일/표준 로거에 구조화된 형태로 기록합니다.

    입력:
    - action: 수행한 RAG 액션 이름
    - payload: 요청 페이로드
    - error: 발생한 예외
    - response: requests.Response(선택)

    반환:
    - 없음

    부작용:
    - 파일/표준 로거에 에러 로그 기록

    오류:
    - 없음(로깅 실패 시 표준 로거로 폴백)
    """

    # -----------------------------------------------------------------------------
    # 1) 로거 확보
    # -----------------------------------------------------------------------------
    logger = _ensure_rag_error_logger()
    # -----------------------------------------------------------------------------
    # 2) 페이로드 정규화 및 주요 필드 추출
    # -----------------------------------------------------------------------------
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

    # -----------------------------------------------------------------------------
    # 3) 컨텍스트 구성
    # -----------------------------------------------------------------------------
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
    # -----------------------------------------------------------------------------
    # 4) 에러 로그 기록
    # -----------------------------------------------------------------------------
    try:
        logger.error("RAG request failed | context=%s | error=%s", context, error)
    except Exception:
        logger.error("RAG request failed | error=%s", error)
