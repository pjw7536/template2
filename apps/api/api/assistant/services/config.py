from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from api.rag import services as rag_services

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

logger = logging.getLogger(__name__)


def _parse_headers(raw: Optional[str], source: str) -> Dict[str, str]:
    """JSON 문자열로 된 헤더 설정을 dict[str, str]로 파싱합니다."""

    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("%s 환경변수를 JSON 객체로 파싱하지 못했습니다.", source)
        return {}

    if not isinstance(parsed, dict):
        logger.warning("%s 값이 JSON 객체 형식이 아닙니다.", source)
        return {}

    headers: Dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, (str, int, float, bool)):
            headers[key] = str(value)
    return headers


@dataclass
class AssistantChatConfig:
    """어시스턴트 채팅(RAG + LLM) 호출에 필요한 설정값 묶음입니다."""

    use_dummy: bool = False
    dummy_reply: str = DEFAULT_DUMMY_REPLY
    dummy_contexts: List[str] = field(default_factory=list)
    dummy_delay_ms: int = DEFAULT_DUMMY_DELAY_MS
    dummy_use_rag: bool = False
    rag_url: str = ""
    rag_index_names: List[str] = field(default_factory=list)
    rag_num_docs: int = DEFAULT_NUM_DOCS
    llm_url: str = ""
    llm_headers: Dict[str, str] = field(default_factory=dict)
    llm_credential: str = ""
    temperature: float = DEFAULT_TEMPERATURE
    model: str = DEFAULT_MODEL
    system_message: str = DEFAULT_SYSTEM_MESSAGE
    request_timeout: int = DEFAULT_TIMEOUT

    @classmethod
    def from_settings(cls) -> "AssistantChatConfig":
        use_dummy = _parse_bool(_read_setting("ASSISTANT_DUMMY_MODE"), False)
        dummy_reply = (_read_setting("ASSISTANT_DUMMY_REPLY") or DEFAULT_DUMMY_REPLY).strip() or DEFAULT_DUMMY_REPLY
        dummy_contexts = _parse_string_list(_read_setting("ASSISTANT_DUMMY_CONTEXTS"))
        if not dummy_contexts:
            dummy_contexts = DEFAULT_DUMMY_CONTEXTS
        dummy_delay_ms = _parse_int(_read_setting("ASSISTANT_DUMMY_DELAY_MS"), DEFAULT_DUMMY_DELAY_MS)
        dummy_use_rag = _parse_bool(_read_setting("ASSISTANT_DUMMY_USE_RAG"), False)

        rag_url = (rag_services.RAG_SEARCH_URL or "").strip()
        rag_index_names = rag_services.resolve_rag_index_names(None)
        rag_num_docs = _parse_int(_read_setting("ASSISTANT_RAG_NUM_DOCS"), DEFAULT_NUM_DOCS)

        llm_url = (_read_setting("ASSISTANT_LLM_URL") or _read_setting("LLM_API_URL") or "").strip()
        llm_headers = _parse_headers(
            _read_setting("ASSISTANT_LLM_COMMON_HEADERS") or _read_setting("LLM_COMMON_HEADERS"),
            "ASSISTANT_LLM_COMMON_HEADERS",
        )
        llm_credential = (_read_setting("ASSISTANT_LLM_CREDENTIAL") or _read_setting("LLM_API_KEY") or "").strip()
        temperature = _parse_float(_read_setting("ASSISTANT_LLM_TEMPERATURE"), DEFAULT_TEMPERATURE)
        model = (_read_setting("ASSISTANT_LLM_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
        system_message = (_read_setting("ASSISTANT_LLM_SYSTEM_MESSAGE") or DEFAULT_SYSTEM_MESSAGE).strip() or DEFAULT_SYSTEM_MESSAGE
        request_timeout = _parse_int(
            _read_setting("ASSISTANT_REQUEST_TIMEOUT") or _read_setting("LLM_REQUEST_TIMEOUT"),
            DEFAULT_TIMEOUT,
        )

        return cls(
            rag_url=rag_url,
            rag_index_names=rag_index_names,
            rag_num_docs=rag_num_docs,
            llm_url=llm_url,
            llm_headers=llm_headers,
            llm_credential=llm_credential,
            temperature=temperature,
            model=model,
            system_message=system_message,
            request_timeout=request_timeout,
            use_dummy=use_dummy,
            dummy_reply=dummy_reply,
            dummy_contexts=dummy_contexts,
            dummy_delay_ms=dummy_delay_ms,
            dummy_use_rag=dummy_use_rag,
        )
