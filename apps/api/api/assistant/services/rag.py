# =============================================================================
# 모듈: 어시스턴트 RAG 검색/컨텍스트 변환
# 주요 함수: retrieve_documents, extract_rag_sources
# 주요 가정: RAG 검색 실패는 AssistantRequestError로 변환합니다.
# =============================================================================
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

from api.common.services import ExternalCallCancellation, ExternalCallCancelled

import api.rag.services as rag_services

from .config import AssistantChatConfig
from .errors import AssistantRequestError
from .parsing import _normalize_string_list

logger = logging.getLogger(__name__)


def extract_rag_sources(hits: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """RAG 검색 hits에서 출처 정보를 추출합니다.

    인자:
        hits: RAG 검색 결과 hits 목록.

    반환:
        공개 ID/제목과 내부 mailbox claim을 포함한 출처 목록.

    부작용:
        없음. 순수 추출입니다.
    """

    sources: List[Dict[str, Any]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        source = hit.get("_source") or {}
        if not isinstance(source, dict):
            continue
        raw_doc_id = source.get("doc_id") or hit.get("_id")
        doc_id = str(raw_doc_id).strip() if raw_doc_id is not None else ""
        if not doc_id:
            continue
        title_raw = source.get("title")
        title = str(title_raw).strip() if isinstance(title_raw, str) else ""
        metadata = source.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        mailbox = str(
            source.get("user_sdwt_prod")
            or metadata.get("user_sdwt_prod")
            or metadata.get("mailbox")
            or ""
        ).strip()
        sources.append(
            {
                "doc_id": doc_id,
                "title": title,
                **({"_mailbox": mailbox} if mailbox else {}),
            }
        )
    return sources


def _format_rag_documents(hits: Sequence[Dict[str, Any]]) -> List[str]:
    """RAG hits를 LLM 배경지식 문자열 목록으로 변환합니다."""

    documents: List[str] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        source = hit.get("_source") or {}
        if not isinstance(source, dict):
            continue
        merged = source.get("merge_title_content")
        if not isinstance(merged, str) or not merged.strip():
            continue

        raw_doc_id = source.get("doc_id") or hit.get("_id")
        doc_id = str(raw_doc_id).strip() if raw_doc_id is not None else ""
        title_raw = source.get("title")
        title = str(title_raw).strip() if isinstance(title_raw, str) else ""
        merged_clean = merged.strip()

        if doc_id:
            header_bits = [f"emailId: {doc_id}"]
            if title:
                header_bits.append(f"title: {title}")
            header = " | ".join(header_bits)
            documents.append(f"[{header}]\n{merged_clean}")
        else:
            documents.append(merged_clean)

    return documents


def _filter_authorized_rag_hits(
    hits: Sequence[Dict[str, Any]],
    *,
    permission_groups: Sequence[str],
) -> list[Dict[str, Any]]:
    """RAG 응답이 공개한 ACL/mailbox가 적용 group과 모순되면 제외합니다."""

    allowed = set(_normalize_string_list(permission_groups))
    filtered: list[Dict[str, Any]] = []
    for hit in hits:
        source = hit.get("_source") if isinstance(hit, dict) else None
        if not isinstance(source, dict):
            continue
        raw_groups = source.get("permission_groups")
        source_groups = set(
            _normalize_string_list(raw_groups if isinstance(raw_groups, list) else [])
        )
        metadata = source.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        mailbox = str(
            source.get("user_sdwt_prod")
            or metadata.get("user_sdwt_prod")
            or metadata.get("mailbox")
            or ""
        ).strip()
        if source_groups and not source_groups.intersection(allowed):
            continue
        if mailbox and mailbox not in allowed:
            continue
        filtered.append(hit)
    return filtered


def retrieve_documents(
    config: AssistantChatConfig,
    question: str,
    *,
    permission_groups: Optional[Sequence[str]] = None,
    rag_index_names: Optional[Sequence[str]] = None,
    cancellation: ExternalCallCancellation | None = None,
) -> Tuple[List[str], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """RAG에서 문서를 검색하고 컨텍스트/출처 목록을 반환합니다.

    인자:
        config: 어시스턴트 RAG 설정.
        question: 질문 문자열.
        permission_groups: 권한 그룹 목록.
        rag_index_names: 사용할 RAG 인덱스 목록.

    반환:
        (documents, rag_response, sources) 튜플.

    부작용:
        외부 RAG API 호출이 발생합니다.

    오류:
        RAG 호출 실패/응답 오류는 AssistantRequestError로 변환됩니다.
    """

    target_indexes = rag_services.resolve_rag_index_names(
        rag_index_names if rag_index_names is not None else config.rag_index_names
    )
    if not rag_services.RAG_SEARCH_URL or not target_indexes:
        return [], None, []

    try:
        search_kwargs: Dict[str, Any] = {
            "index_name": target_indexes,
            "num_result_doc": config.rag_num_docs,
            "timeout": config.request_timeout,
        }
        normalized_permission_groups = _normalize_string_list(permission_groups)
        if normalized_permission_groups:
            search_kwargs["permission_groups"] = normalized_permission_groups
        if cancellation is not None:
            data = rag_services.search_rag(
                question,
                **search_kwargs,
                cancellation=cancellation,
            )
        else:
            data = rag_services.search_rag(question, **search_kwargs)
    except ExternalCallCancelled:
        raise
    except requests.HTTPError as exc:
        response = exc.response
        status = response.status_code if response is not None else "unknown"
        logger.warning("Assistant RAG HTTP 오류: status=%s", status)
        raise AssistantRequestError("RAG 검색 요청에 실패했습니다.") from exc
    except requests.RequestException as exc:
        logger.warning(
            "Assistant RAG 요청 실패: exception_type=%s",
            type(exc).__name__,
        )
        raise AssistantRequestError("RAG 검색 요청에 실패했습니다.") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "Assistant RAG 응답 처리 실패: exception_type=%s",
            type(exc).__name__,
        )
        raise AssistantRequestError("RAG 검색 응답을 처리하지 못했습니다.") from exc

    hits = data.get("hits", {}).get("hits", [])
    if not isinstance(hits, list):
        return [], data, []
    hits = _filter_authorized_rag_hits(
        hits,
        permission_groups=normalized_permission_groups,
    )

    documents = _format_rag_documents(hits)
    sources = extract_rag_sources(hits)
    return documents, data, sources
