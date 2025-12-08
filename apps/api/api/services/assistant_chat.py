from __future__ import annotations

import json
import logging
import os
import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_NUM_DOCS = 5
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT = 30
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_SYSTEM_MESSAGE = "항상 한국어로 대답하는 친절한 AI"
NO_CONTEXT_MESSAGE = "※ 검색된 배경지식이 없습니다. 일반적인 지식을 바탕으로 답변해주세요."
DEFAULT_DUMMY_REPLY = "개발용 더미 응답입니다. 질문({question})을 받아 임시로 답변합니다."
DEFAULT_DUMMY_CONTEXTS = [
    "Etch 장비 점검 시 확인해야 할 주요 체크리스트 요약본입니다. 공정 상태, 안전 장비, 로그 기록 점검을 포함합니다.",
    "RAG 개발용 더미 문서: 공정 변경 시 보고 절차와 협업 흐름을 설명합니다.",
]
DEFAULT_DUMMY_DELAY_MS = 0


class AssistantConfigError(RuntimeError):
    """Raised when assistant integration is missing required configuration."""


class AssistantRequestError(RuntimeError):
    """Raised when external assistant call fails."""


def _read_setting(name: str, fallback: Optional[str] = None) -> Optional[str]:
    value = getattr(settings, name, None)
    if value is None:
        value = os.environ.get(name, fallback)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _parse_int(value: Optional[str], default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _parse_float(value: Optional[str], default: float) -> float:
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _parse_permission_groups(raw: Optional[str]) -> List[str]:
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes)):
        return [str(item).strip() for item in parsed if str(item).strip()]

    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]

    return []


def _parse_string_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes)):
        return [str(item).strip() for item in parsed if str(item).strip()]

    if isinstance(raw, str):
        if "\n" in raw:
            return [item.strip() for item in raw.splitlines() if item.strip()]
        return [raw.strip()]

    return []


def _parse_headers(raw: Optional[str], source: str) -> Dict[str, str]:
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
    use_dummy: bool = False
    dummy_reply: str = DEFAULT_DUMMY_REPLY
    dummy_contexts: List[str] = field(default_factory=list)
    dummy_delay_ms: int = DEFAULT_DUMMY_DELAY_MS
    rag_url: str = ""
    rag_index_name: str = ""
    rag_permission_groups: List[str] = field(default_factory=list)
    rag_num_docs: int = DEFAULT_NUM_DOCS
    rag_headers: Dict[str, str] = field(default_factory=dict)
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

        rag_url = (_read_setting("ASSISTANT_RAG_URL") or "").strip()
        rag_index_name = (_read_setting("ASSISTANT_RAG_INDEX_NAME") or "").strip()
        rag_permission_groups = _parse_permission_groups(_read_setting("ASSISTANT_RAG_PERMISSION_GROUPS"))
        rag_headers = _parse_headers(_read_setting("ASSISTANT_RAG_HEADERS"), "ASSISTANT_RAG_HEADERS")
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
            rag_index_name=rag_index_name,
            rag_permission_groups=rag_permission_groups,
            rag_num_docs=rag_num_docs,
            rag_headers=rag_headers,
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
        )


@dataclass
class AssistantChatResult:
    reply: str
    contexts: List[str]
    llm_response: Dict[str, Any]
    rag_response: Optional[Dict[str, Any]] = None
    is_dummy: bool = False


class AssistantChatService:
    def __init__(self, config: Optional[AssistantChatConfig] = None) -> None:
        self.config = config or AssistantChatConfig.from_settings()

    def _generate_dummy_result(self, question: str) -> AssistantChatResult:
        contexts = list(self.config.dummy_contexts)[: max(1, self.config.rag_num_docs)]
        reply_template = self.config.dummy_reply or DEFAULT_DUMMY_REPLY
        reply = reply_template.replace("{question}", question)

        delay_ms = max(0, int(self.config.dummy_delay_ms))
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        return AssistantChatResult(
            reply=reply,
            contexts=contexts,
            llm_response={
                "mode": "dummy",
                "echo": question,
                "model": self.config.model,
                "temperature": self.config.temperature,
            },
            rag_response={
                "mode": "dummy",
                "contexts": contexts,
                "count": len(contexts),
            },
            is_dummy=True,
        )

    def _post(
        self,
        session: requests.Session,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=self.config.request_timeout)
            resp.raise_for_status()
            try:
                return resp.json()
            except (json.JSONDecodeError, ValueError) as exc:
                raise AssistantRequestError(
                    f"응답을 JSON 으로 파싱하는데 실패했습니다. (url={url}, status={resp.status_code}, text={resp.text[:500]!r})"
                ) from exc

        except requests.HTTPError as exc:
            status = resp.status_code if "resp" in locals() else "unknown"
            text_preview = getattr(resp, "text", "")[:500]
            raise AssistantRequestError(f"HTTP 오류 [{status}]: {text_preview!r} (url={url})") from exc

        except requests.RequestException as exc:
            raise AssistantRequestError(f"요청 중 오류 발생 (url={url}): {exc}") from exc

    def _retrieve_documents(self, session: requests.Session, question: str) -> Tuple[List[str], Optional[Dict[str, Any]]]:
        if not self.config.rag_url or not self.config.rag_index_name:
            return [], None

        payload: Dict[str, Any] = {
            "index_name": self.config.rag_index_name,
            "permission_groups": self.config.rag_permission_groups,
            "query_text": question,
            "num_result_doc": self.config.rag_num_docs,
        }

        data = self._post(session, self.config.rag_url, self.config.rag_headers, payload)

        hits = data.get("hits", {}).get("hits", [])
        if not isinstance(hits, list):
            return [], data

        documents: List[str] = []
        for hit in hits:
            source = hit.get("_source") or {}
            merged = source.get("merge_title_content")
            if isinstance(merged, str) and merged.strip():
                documents.append(merged)

        return documents, data

    def _generate_llm_payload(self, question: str, contexts: List[str]) -> Dict[str, Any]:
        context_str = "\n".join(contexts) if contexts else NO_CONTEXT_MESSAGE

        system_msg = {
            "role": "system",
            "content": self.config.system_message,
        }
        user_msg = {
            "role": "user",
            "content": f"질문: {question}\n\n[배경지식]\n{context_str}",
        }

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [system_msg, user_msg],
            "temperature": self.config.temperature,
            "stream": False,
        }
        return payload

    def _extract_llm_reply(self, resp_json: Dict[str, Any]) -> str:
        try:
            choices = resp_json["choices"]
            if not choices:
                raise AssistantRequestError("LLM 응답에 choices가 비어 있습니다.")
            message = choices[0]["message"]
            content = message["content"]
            if not isinstance(content, str):
                raise AssistantRequestError("LLM 응답 content가 문자열이 아닙니다.")
            return content
        except (KeyError, IndexError, TypeError) as exc:
            raise AssistantRequestError(f"LLM 응답 포맷이 기대와 다릅니다. raw={resp_json!r}") from exc

    def _call_llm(self, session: requests.Session, question: str, contexts: List[str]) -> Tuple[str, Dict[str, Any]]:
        if not self.config.llm_url:
            raise AssistantConfigError("LLM URL 설정이 비어 있습니다.")
        if not self.config.llm_credential:
            raise AssistantConfigError("LLM 인증 토큰이 비어 있습니다.")

        headers = {
            "Content-Type": "application/json",
            **self.config.llm_headers,
            "x-dep-ticket": self.config.llm_credential,
            "Prompt-Msg-Id": str(uuid.uuid4()),
            "Completion-Msg-Id": str(uuid.uuid4()),
        }

        payload = self._generate_llm_payload(question, contexts)
        resp_json = self._post(session, self.config.llm_url, headers, payload)
        reply = self._extract_llm_reply(resp_json)
        return reply, resp_json

    def generate_reply(self, question: str) -> AssistantChatResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise AssistantRequestError("질문이 비어 있습니다.")

        if self.config.use_dummy:
            return self._generate_dummy_result(normalized_question)

        with requests.Session() as session:
            contexts, rag_response = self._retrieve_documents(session, normalized_question)
            reply, llm_response = self._call_llm(session, normalized_question, contexts)

        return AssistantChatResult(
            reply=reply,
            contexts=contexts,
            llm_response=llm_response,
            rag_response=rag_response,
        )


assistant_chat_service = AssistantChatService()
