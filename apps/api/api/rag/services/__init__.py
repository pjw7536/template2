# =============================================================================
# 모듈 설명: RAG 서비스 파사드(공용 진입점)를 제공합니다.
# - 주요 대상: search_rag, insert_email_to_rag, delete_rag_doc 등
# - 불변 조건: 내부 구현은 services/* 모듈을 통해 호출합니다.
# =============================================================================

"""RAG 서비스 파사드 모듈입니다."""

from __future__ import annotations

from .client import (
    delete_rag_doc,
    get_rag_index_candidates,
    insert_email_to_rag,
    requests,
    resolve_rag_index_name,
    resolve_rag_index_names,
    search_rag,
)
from .config import (
    RAG_CHUNK_FACTOR,
    RAG_DELETE_URL,
    RAG_HEADERS,
    RAG_INDEX_DEFAULT,
    RAG_INDEX_EMAILS,
    RAG_INDEX_LIST,
    RAG_INDEX_NAME,
    RAG_INSERT_URL,
    RAG_PUBLIC_GROUP,
    RAG_PERMISSION_GROUPS,
    RAG_SEARCH_URL,
)

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
    "get_rag_index_candidates",
    "insert_email_to_rag",
    "requests",
    "resolve_rag_index_name",
    "resolve_rag_index_names",
    "search_rag",
]
