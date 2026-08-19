"""도메인이 provider 세부 구현 없이 사용하는 RAG adapter입니다."""

from __future__ import annotations

from typing import Any, Sequence

from api.common.services import ExternalCallCancellation

from . import client


class RagAdapter:
    """RAG search/insert/delete/index-info 공용 진입점입니다."""

    def search(
        self,
        query_text: str,
        *,
        index_names: Sequence[str] | str | None = None,
        num_result_doc: int = 5,
        permission_groups: Sequence[str] | None = None,
        timeout: int | None = None,
        cancellation: ExternalCallCancellation | None = None,
    ) -> dict[str, Any]:
        """허용 index와 권한 그룹을 적용해 문서를 검색합니다."""

        return client.search_rag(
            query_text,
            index_name=index_names,
            num_result_doc=num_result_doc,
            permission_groups=permission_groups,
            timeout=timeout,
            cancellation=cancellation,
        )

    def insert_email(
        self,
        email: Any,
        *,
        index_name: str | None = None,
        permission_groups: Sequence[str] | None = None,
    ) -> None:
        """이메일 문서를 provider index에 등록합니다."""

        client.insert_email_to_rag(
            email,
            index_name=index_name,
            permission_groups=permission_groups,
        )

    def delete_document(
        self,
        doc_id: str,
        *,
        index_name: str | None = None,
        permission_groups: Sequence[str] | None = None,
    ) -> None:
        """provider index에서 문서를 삭제합니다."""

        client.delete_rag_doc(
            doc_id,
            index_name=index_name,
            permission_groups=permission_groups,
        )

    def get_index_info(self, *, timeout: int | None = None) -> dict[str, Any]:
        """provider index 목록과 상태를 조회합니다."""

        return client.get_rag_index_info(timeout=timeout)


rag_adapter = RagAdapter()


__all__ = ["RagAdapter", "rag_adapter"]
