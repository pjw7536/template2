# =============================================================================
# 모듈: 어시스턴트 채팅 오케스트레이션
# 주요 구성: AssistantChatService, AssistantChatResult
# 주요 가정: RAG/LLM 세부 책임은 rag.py, llm.py, sources.py에 위임합니다.
# =============================================================================
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from api.common.services import ExternalCallCancellation

from .config import AssistantChatConfig
from .errors import AssistantRequestError
from .llm import (
    build_llm_payload,
    stream_llm_reply,
)
from .rag import extract_rag_sources, retrieve_documents
from .reply import AssistantStructuredSegment, _parse_structured_llm_reply
from .sources import build_structured_segments, filter_sources_by_used_email_ids


@dataclass
class AssistantChatResult:
    """어시스턴트 채팅 결과(reply/contexts/원본 응답)를 담는 DTO입니다."""

    reply: str
    contexts: List[str]
    llm_response: Dict[str, Any]
    rag_response: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)
    retrieved_sources: List[Dict[str, Any]] = field(default_factory=list)
    segments: List[Dict[str, Any]] = field(default_factory=list)
    is_dummy: bool = False


class AssistantChatService:
    """RAG 검색 결과를 바탕으로 LLM 답변을 생성하는 오케스트레이션 서비스입니다.

    부작용:
        외부 RAG/LLM API 호출이 발생할 수 있습니다.
    """

    def __init__(self, config: Optional[AssistantChatConfig] = None) -> None:
        """서비스 설정을 초기화합니다.

        인자:
            config: 주입할 설정(없으면 settings/env에서 로드).
        """

        self.config = config or AssistantChatConfig.from_settings()

    def _filter_sources_by_used_email_ids(
        self,
        sources: List[Dict[str, Any]],
        used_email_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """출처 목록에서 사용된 emailId(doc_id)만 남깁니다."""

        return filter_sources_by_used_email_ids(sources, used_email_ids)

    def _build_segments(
        self,
        sources: List[Dict[str, Any]],
        segments: List[AssistantStructuredSegment],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """LLM segment 목록을 기반으로 segment별 출처와 전체 출처를 계산합니다."""

        return build_structured_segments(sources, segments)

    def _generate_dummy_result(
        self,
        question: str,
        *,
        contexts: Optional[List[str]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        rag_response: Optional[Dict[str, Any]] = None,
    ) -> AssistantChatResult:
        """더미 모드 응답을 생성합니다.

        인자:
            question: 사용자 질문 문자열.
            contexts: 더미 컨텍스트 목록(없으면 기본값 사용).
            sources: 더미 출처 목록.
            rag_response: 더미 RAG 응답(raw).

        반환:
            AssistantChatResult 더미 응답.

        부작용:
            더미 지연(delay) 설정에 따라 sleep이 발생할 수 있습니다.
        """

        resolved_contexts = contexts or list(self.config.dummy_contexts)
        trimmed_contexts = resolved_contexts[: max(1, self.config.rag_num_docs)] if resolved_contexts else []
        reply_template = self.config.dummy_reply or ""
        reply = reply_template.replace("{question}", question)
        source_ids = [
            str(source.get("doc_id") or "").strip()
            for source in (sources or [])
            if isinstance(source, dict) and str(source.get("doc_id") or "").strip()
        ]
        structured_reply = {
            "answer": reply,
            "segments": [
                {"answer": reply, "usedEmailIds": source_ids}
            ] if source_ids else [],
        }

        delay_ms = max(0, int(self.config.dummy_delay_ms))
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        return AssistantChatResult(
            reply=json.dumps(
                structured_reply,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            contexts=trimmed_contexts,
            llm_response={
                "mode": "dummy",
                "echo": question,
                "model": self.config.model,
                "temperature": self.config.temperature,
            },
            rag_response=rag_response
            or {
                "mode": "dummy",
                "contexts": trimmed_contexts,
                "count": len(trimmed_contexts),
            },
            sources=sources or [],
            retrieved_sources=list(sources or []),
            is_dummy=True,
        )

    def _extract_sources(self, hits: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """RAG 검색 hits에서 출처 정보를 추출합니다."""

        return extract_rag_sources(hits)

    def _retrieve_documents(
        self,
        question: str,
        *,
        permission_groups: Optional[Sequence[str]] = None,
        rag_index_names: Optional[Sequence[str]] = None,
        cancellation: ExternalCallCancellation | None = None,
    ) -> Tuple[List[str], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """RAG에서 문서를 검색하고 컨텍스트/출처 목록을 반환합니다."""

        return retrieve_documents(
            self.config,
            question,
            permission_groups=permission_groups,
            rag_index_names=rag_index_names,
            cancellation=cancellation,
        )

    def _generate_llm_payload(
        self,
        question: str,
        contexts: List[str],
        *,
        email_ids: List[str],
    ) -> Dict[str, Any]:
        """LLM 호출용 payload를 구성합니다."""

        return build_llm_payload(self.config, question, contexts, email_ids=email_ids)

    def _apply_structured_reply(self, result: AssistantChatResult) -> AssistantChatResult:
        """구조화 응답을 파싱해 reply/sources/segments를 결과 DTO에 반영합니다."""

        answer, segments = _parse_structured_llm_reply(result.reply)
        result.reply = answer
        built_segments, filtered_sources = self._build_segments(result.sources, segments)
        result.segments = built_segments
        result.sources = filtered_sources
        return result

    def _build_chat_result(
        self,
        *,
        reply: str,
        contexts: List[str],
        llm_response: Dict[str, Any],
        rag_response: Optional[Dict[str, Any]],
        sources: List[Dict[str, Any]],
    ) -> AssistantChatResult:
        """LLM 원문 응답을 최종 채팅 결과 DTO로 변환합니다."""

        return self._apply_structured_reply(
            AssistantChatResult(
                reply=reply,
                contexts=contexts,
                llm_response=llm_response,
                rag_response=rag_response,
                sources=sources,
                retrieved_sources=list(sources),
            )
        )

    def generate_reply_stream(
        self,
        question: str,
        *,
        cancellation: ExternalCallCancellation,
        user_header_id: Optional[str] = None,
        rag_index_names: Optional[Sequence[str]] = None,
        permission_groups: Optional[Sequence[str]] = None,
        conversation_context: str = "",
    ) -> AssistantChatResult:
        """RAG 조회 후 구조화 LLM 응답을 취소 가능한 stream으로 완성합니다."""

        normalized_question = question.strip()
        if not normalized_question:
            raise AssistantRequestError("질문이 비어 있습니다.")
        if self.config.use_dummy:
            cancellation.raise_if_cancelled()
            if self.config.dummy_use_rag:
                contexts, rag_response, sources = self._retrieve_documents(
                    normalized_question,
                    permission_groups=permission_groups,
                    rag_index_names=rag_index_names,
                    cancellation=cancellation,
                )
            else:
                contexts, rag_response, sources = [], None, []
            result = self._apply_structured_reply(
                self._generate_dummy_result(
                    normalized_question,
                    contexts=contexts,
                    sources=sources,
                    rag_response=rag_response,
                )
            )
            cancellation.raise_if_cancelled()
            return result
        cancellation.raise_if_cancelled()
        contexts, rag_response, sources = self._retrieve_documents(
            normalized_question,
            permission_groups=permission_groups,
            rag_index_names=rag_index_names,
            cancellation=cancellation,
        )
        cancellation.raise_if_cancelled()
        normalized_context = conversation_context.strip()
        llm_question = (
            f"[이전 대화 문맥]\n{normalized_context}\n\n"
            f"[현재 질문]\n{normalized_question}"
            if normalized_context
            else normalized_question
        )
        reply = stream_llm_reply(
            self.config,
            llm_question,
            contexts,
            sources,
            cancellation=cancellation,
            user_header_id=user_header_id,
        )
        cancellation.raise_if_cancelled()
        return self._build_chat_result(
            reply=reply,
            contexts=contexts,
            llm_response={"mode": "stream"},
            rag_response=rag_response,
            sources=sources,
        )


assistant_chat_service = AssistantChatService()
