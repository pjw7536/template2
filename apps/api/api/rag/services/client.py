"""RAG API client operations."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

import requests
from django.utils import timezone

from .config import _normalize_index_names, _normalize_permission_groups
from .logging import _log_rag_failure


def _get_rag_services():
    from api.rag import services as rag_services

    return rag_services


def _resolve_email_permission_groups(email: Any) -> List[str]:
    """이메일의 user_sdwt_prod 값을 permission_groups로 변환합니다."""

    rag_services = _get_rag_services()
    groups: List[str] = []
    raw_group = getattr(email, "user_sdwt_prod", None)
    if isinstance(raw_group, str) and raw_group.strip():
        groups.append(raw_group.strip())
    raw_sender_id = getattr(email, "sender_id", None)
    if isinstance(raw_sender_id, str) and raw_sender_id.strip():
        groups.append(raw_sender_id.strip())
    if groups:
        return list(dict.fromkeys(groups))
    return _normalize_permission_groups(rag_services.RAG_PERMISSION_GROUPS) or [rag_services.RAG_PUBLIC_GROUP]


def get_rag_index_candidates() -> List[str]:
    """허용 가능한 RAG 인덱스 후보 목록을 반환합니다."""

    rag_services = _get_rag_services()
    return list(rag_services.RAG_INDEX_LIST)


def resolve_rag_index_name(index_name: str | None) -> str:
    """RAG 인덱스명을 결정합니다."""

    rag_services = _get_rag_services()
    resolved = index_name.strip() if isinstance(index_name, str) else ""
    if resolved:
        return resolved

    default_index = str(rag_services.RAG_INDEX_DEFAULT or "").strip()
    if default_index:
        return default_index
    if rag_services.RAG_INDEX_LIST:
        return rag_services.RAG_INDEX_LIST[0]
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

    rag_services = _get_rag_services()
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
        else _normalize_permission_groups(rag_services.RAG_PERMISSION_GROUPS)
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
    if rag_services.RAG_CHUNK_FACTOR:
        payload["chunk_factor"] = rag_services.RAG_CHUNK_FACTOR
    return payload


def _build_delete_payload(
    doc_id: str,
    index_name: str | None = None,
    permission_groups: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """doc_id 기반 RAG delete 요청 payload를 생성합니다."""

    rag_services = _get_rag_services()
    resolved_index_name = resolve_rag_index_name(index_name)
    resolved_permission_groups = (
        _normalize_permission_groups(permission_groups)
        if permission_groups is not None
        else _normalize_permission_groups(rag_services.RAG_PERMISSION_GROUPS)
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

    rag_services = _get_rag_services()
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
        else _normalize_permission_groups(rag_services.RAG_PERMISSION_GROUPS),
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

    rag_services = _get_rag_services()
    if not rag_services.RAG_SEARCH_URL:
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
        resp = requests.post(
            rag_services.RAG_SEARCH_URL,
            headers=rag_services.RAG_HEADERS,
            json=payload,
            timeout=max(1, int(timeout)),
        )
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

    rag_services = _get_rag_services()
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

    if not rag_services.RAG_INSERT_URL:
        error = ValueError("RAG_INSERT_URL is not configured")
        _log_rag_failure("insert", payload, error)
        raise error
    if not resolved_index_name:
        error = ValueError("RAG_INDEX_DEFAULT is not configured")
        _log_rag_failure("insert", payload, error)
        raise error

    try:
        resp = requests.post(
            rag_services.RAG_INSERT_URL,
            headers=rag_services.RAG_HEADERS,
            json=payload,
            timeout=30,
        )
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

    rag_services = _get_rag_services()
    payload = _build_delete_payload(doc_id, index_name=index_name, permission_groups=permission_groups)

    resolved_index_name = payload.get("index_name")

    if not rag_services.RAG_DELETE_URL:
        error = ValueError("RAG_DELETE_URL is not configured")
        _log_rag_failure("delete", payload, error)
        raise error
    if not resolved_index_name:
        error = ValueError("RAG_INDEX_DEFAULT is not configured")
        _log_rag_failure("delete", payload, error)
        raise error

    try:
        resp = requests.post(
            rag_services.RAG_DELETE_URL,
            headers=rag_services.RAG_HEADERS,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        _log_rag_failure("delete", payload, exc)
        raise
