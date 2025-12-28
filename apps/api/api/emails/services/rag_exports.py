# =============================================================================
# 모듈 설명: RAG 서비스 함수/상수를 emails 도메인에 재노출합니다.
# - 주요 항목: insert_email_to_rag, delete_rag_doc, resolve_rag_index_name
# - 불변 조건: 실제 구현은 api.rag.services에 위임합니다.
# =============================================================================

from __future__ import annotations

from api.rag import services as rag_services

insert_email_to_rag = rag_services.insert_email_to_rag
delete_rag_doc = rag_services.delete_rag_doc
resolve_rag_index_name = rag_services.resolve_rag_index_name
RAG_INDEX_EMAILS = rag_services.RAG_INDEX_EMAILS
RAG_PUBLIC_GROUP = rag_services.RAG_PUBLIC_GROUP

__all__ = [
    "RAG_INDEX_EMAILS",
    "RAG_PUBLIC_GROUP",
    "delete_rag_doc",
    "insert_email_to_rag",
    "resolve_rag_index_name",
]
