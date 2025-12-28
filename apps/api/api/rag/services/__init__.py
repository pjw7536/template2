"""RAG service facade."""

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
