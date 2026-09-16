# =============================================================================
# 모듈: 어시스턴트 연동 설정 로더
# 주요 구성: AssistantChatConfig
# 주요 가정: 설정 값은 settings/env에서 로드됩니다.
# =============================================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import api.rag.services as rag_services

from .constants import (
    DEFAULT_DUMMY_CONTEXTS,
    DEFAULT_DUMMY_DELAY_MS,
    DEFAULT_DUMMY_REPLY,
    DEFAULT_MODEL,
    DEFAULT_NUM_DOCS,
    DEFAULT_SYSTEM_MESSAGE,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
)
from .parsing import _parse_bool, _parse_float, _parse_int, _parse_string_list, _read_setting

@dataclass
class AssistantChatConfig:
    """Email RAG 검색과 구조화 답변 prompt에 필요한 설정값 묶음입니다."""

    use_dummy: bool = False
    dummy_reply: str = DEFAULT_DUMMY_REPLY
    dummy_contexts: List[str] = field(default_factory=list)
    dummy_delay_ms: int = DEFAULT_DUMMY_DELAY_MS
    dummy_use_rag: bool = False
    rag_url: str = ""
    rag_index_names: List[str] = field(default_factory=list)
    rag_num_docs: int = DEFAULT_NUM_DOCS
    request_timeout: int = DEFAULT_TIMEOUT
    temperature: float = DEFAULT_TEMPERATURE
    model: str = DEFAULT_MODEL
    system_message: str = DEFAULT_SYSTEM_MESSAGE

    @classmethod
    def from_settings(cls) -> "AssistantChatConfig":
        """settings/env에서 어시스턴트 설정을 로드합니다.

        반환:
            AssistantChatConfig 인스턴스.

        부작용:
            settings/env 값을 조회합니다.
        """

        # -----------------------------------------------------------------------------
        # 1) 더미 모드 설정
        # -----------------------------------------------------------------------------
        use_dummy = _parse_bool(_read_setting("ASSISTANT_DUMMY_MODE"), False)
        dummy_reply = (_read_setting("ASSISTANT_DUMMY_REPLY") or DEFAULT_DUMMY_REPLY).strip() or DEFAULT_DUMMY_REPLY
        dummy_contexts = _parse_string_list(_read_setting("ASSISTANT_DUMMY_CONTEXTS"))
        if not dummy_contexts:
            dummy_contexts = DEFAULT_DUMMY_CONTEXTS
        dummy_delay_ms = _parse_int(_read_setting("ASSISTANT_DUMMY_DELAY_MS"), DEFAULT_DUMMY_DELAY_MS)
        dummy_use_rag = _parse_bool(_read_setting("ASSISTANT_DUMMY_USE_RAG"), False)

        # -----------------------------------------------------------------------------
        # 2) RAG 설정
        # -----------------------------------------------------------------------------
        rag_url = (rag_services.RAG_SEARCH_URL or "").strip()
        rag_index_names = rag_services.resolve_rag_index_names(None)
        rag_num_docs = rag_services.RAG_NUM_DOCS
        request_timeout = _parse_int(
            _read_setting("ASSISTANT_REQUEST_TIMEOUT"),
            DEFAULT_TIMEOUT,
        )

        # -----------------------------------------------------------------------------
        # 3) Email RAG 구조화 답변 prompt 설정
        # -----------------------------------------------------------------------------
        temperature = _parse_float(_read_setting("ASSISTANT_LLM_TEMPERATURE"), DEFAULT_TEMPERATURE)
        system_message = (_read_setting("ASSISTANT_LLM_SYSTEM_MESSAGE") or DEFAULT_SYSTEM_MESSAGE).strip() or DEFAULT_SYSTEM_MESSAGE

        # -----------------------------------------------------------------------------
        # 4) 구성 객체 반환
        # -----------------------------------------------------------------------------
        return cls(
            rag_url=rag_url,
            rag_index_names=rag_index_names,
            rag_num_docs=rag_num_docs,
            request_timeout=request_timeout,
            temperature=temperature,
            system_message=system_message,
            use_dummy=use_dummy,
            dummy_reply=dummy_reply,
            dummy_contexts=dummy_contexts,
            dummy_delay_ms=dummy_delay_ms,
            dummy_use_rag=dummy_use_rag,
        )
