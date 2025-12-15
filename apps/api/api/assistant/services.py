"""Assistant feature services."""

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

from api.rag import services as rag_services

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
STRUCTURED_REPLY_SYSTEM_MESSAGE = (
    "너는 반드시 JSON 객체 1개만 출력한다. 마크다운, 코드펜스, 설명 문장, 추가 텍스트는 금지다."
)


@dataclass(frozen=True)
class AssistantStructuredSegment:
    """LLM 구조화 응답에서 segment 1개를 표현합니다."""

    answer: str
    used_email_ids: List[str]


class AssistantConfigError(RuntimeError):
    """어시스턴트 연동에 필요한 설정이 누락되었을 때 발생합니다.

    Raised when assistant integration is missing required configuration.
    """


class AssistantRequestError(RuntimeError):
    """외부 어시스턴트(RAG/LLM) 호출이 실패했을 때 발생합니다.

    Raised when external assistant call fails.
    """


def _read_setting(name: str, fallback: Optional[str] = None) -> Optional[str]:
    """Django settings 또는 환경변수에서 설정 값을 문자열로 읽습니다."""

    value = getattr(settings, name, None)
    if value is None:
        value = os.environ.get(name, fallback)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _parse_int(value: Optional[str], default: int) -> int:
    """문자열 값을 양의 정수로 파싱하고 실패 시 기본값을 반환합니다."""

    if value is None:
        return default
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _parse_float(value: Optional[str], default: float) -> float:
    """문자열 값을 float로 파싱하고 실패 시 기본값을 반환합니다."""

    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    """문자열 값을 boolean으로 파싱합니다(1/true/yes/on=True)."""

    if value is None:
        return default
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _parse_string_list(raw: Optional[str]) -> List[str]:
    """JSON 배열/개행 문자열 등을 문자열 리스트로 정규화합니다."""

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


def _strip_markdown_code_fence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1]).strip()

    return cleaned


def _parse_structured_llm_reply(raw_reply: str) -> Tuple[str, Optional[List[AssistantStructuredSegment]]]:
    """LLM 응답(JSON)을 파싱해 answer/segments를 추출합니다.

    반환:
      - answer(표시용 문자열)
      - segments (형식이 유효할 때만 list[AssistantStructuredSegment], 그 외 None)

    지원 형식:
      - 최신: {"answer": string, "segments": [{"answer": string, "usedEmailIds": string[]}]}
      - 레거시: {"answer": string, "usedEmailIds": string[]}
    """

    fallback_answer = _strip_markdown_code_fence(raw_reply)
    if not fallback_answer:
        return "", None

    candidates = [fallback_answer]
    first_brace = fallback_answer.find("{")
    last_brace = fallback_answer.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(fallback_answer[first_brace : last_brace + 1].strip())

    parsed: Optional[Dict[str, Any]] = None
    for candidate in candidates:
        try:
            loaded = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(loaded, dict):
            parsed = loaded
            break

    if not parsed:
        return fallback_answer, None

    segments: List[AssistantStructuredSegment] = []
    segments_raw = parsed.get("segments")
    if segments_raw is not None:
        if not isinstance(segments_raw, list):
            answer_raw = parsed.get("answer")
            answer = (
                answer_raw.strip() if isinstance(answer_raw, str) and answer_raw.strip() else fallback_answer
            )
            return answer, None

        for entry in segments_raw:
            if not isinstance(entry, dict):
                continue
            segment_answer_raw = entry.get("answer")
            segment_answer = (
                segment_answer_raw.strip()
                if isinstance(segment_answer_raw, str) and segment_answer_raw.strip()
                else ""
            )
            used_raw = entry.get("usedEmailIds")
            if not segment_answer or not isinstance(used_raw, list):
                continue

            used_ids: List[str] = []
            for item in used_raw:
                if isinstance(item, str) and item.strip():
                    used_ids.append(item.strip())

            deduped_used_ids = list(dict.fromkeys(used_ids))
            segments.append(
                AssistantStructuredSegment(answer=segment_answer, used_email_ids=deduped_used_ids)
            )

        answer_raw = parsed.get("answer")
        if isinstance(answer_raw, str) and answer_raw.strip():
            answer = answer_raw.strip()
        elif segments:
            answer = "\n\n".join(segment.answer for segment in segments).strip() or fallback_answer
        else:
            answer = fallback_answer

        return answer, segments

    used_raw = parsed.get("usedEmailIds")
    answer_raw = parsed.get("answer")
    answer = answer_raw.strip() if isinstance(answer_raw, str) and answer_raw.strip() else fallback_answer
    if not isinstance(used_raw, list):
        return answer, None

    used_ids: List[str] = []
    for item in used_raw:
        if isinstance(item, str) and item.strip():
            used_ids.append(item.strip())

    deduped_used_ids = list(dict.fromkeys(used_ids))
    if deduped_used_ids:
        segments.append(AssistantStructuredSegment(answer=answer, used_email_ids=deduped_used_ids))

    return answer, segments


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
    rag_index_name: str = ""
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
        rag_index_name = (rag_services.RAG_INDEX_NAME or "").strip()
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


@dataclass
class AssistantChatResult:
    """어시스턴트 채팅 결과(reply/contexts/원본 응답)를 담는 DTO입니다."""

    reply: str
    contexts: List[str]
    llm_response: Dict[str, Any]
    rag_response: Optional[Dict[str, Any]] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)
    segments: List[Dict[str, Any]] = field(default_factory=list)
    is_dummy: bool = False


class AssistantChatService:
    """RAG 검색 결과를 바탕으로 LLM 답변을 생성하는 서비스입니다."""

    def __init__(self, config: Optional[AssistantChatConfig] = None) -> None:
        self.config = config or AssistantChatConfig.from_settings()

    def _filter_sources_by_used_email_ids(self, sources: List[Dict[str, Any]], used_email_ids: List[str]) -> List[Dict[str, Any]]:
        """출처 목록에서 사용된 emailId(doc_id)만 남깁니다."""

        if not used_email_ids:
            return []

        allowed_ids = {
            entry.get("doc_id").strip()
            for entry in sources
            if isinstance(entry, dict)
            and isinstance(entry.get("doc_id"), str)
            and entry.get("doc_id").strip()
        }
        used_set = {email_id for email_id in used_email_ids if email_id in allowed_ids}
        if not used_set:
            return []

        return [
            entry
            for entry in sources
            if isinstance(entry, dict)
            and isinstance(entry.get("doc_id"), str)
            and entry.get("doc_id").strip() in used_set
        ]

    def _build_segments(
        self,
        sources: List[Dict[str, Any]],
        segments: List[AssistantStructuredSegment],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """LLM segment 목록을 기반으로 segment별 출처와 전체 출처를 계산합니다.

        반환:
          - segments: [{"reply": str, "sources": list[dict]}]
          - sources: 전체 segment에서 사용된 출처(중복 제거)
        """

        allowed_ids = {
            entry.get("doc_id").strip()
            for entry in sources
            if isinstance(entry, dict)
            and isinstance(entry.get("doc_id"), str)
            and entry.get("doc_id").strip()
        }

        normalized_segments: List[Dict[str, Any]] = []
        used_ids_union: List[str] = []

        for segment in segments:
            used_ids = [email_id for email_id in segment.used_email_ids if email_id in allowed_ids]
            if not used_ids:
                continue

            segment_sources = self._filter_sources_by_used_email_ids(sources, used_ids)
            if not segment_sources:
                continue

            normalized_segments.append(
                {
                    "reply": segment.answer,
                    "sources": segment_sources,
                }
            )

            for email_id in used_ids:
                if email_id not in used_ids_union:
                    used_ids_union.append(email_id)

        filtered_sources = self._filter_sources_by_used_email_ids(sources, used_ids_union)
        return normalized_segments, filtered_sources

    def _generate_dummy_result(
        self,
        question: str,
        *,
        contexts: Optional[List[str]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        rag_response: Optional[Dict[str, Any]] = None,
    ) -> AssistantChatResult:
        resolved_contexts = contexts or list(self.config.dummy_contexts)
        trimmed_contexts = resolved_contexts[: max(1, self.config.rag_num_docs)] if resolved_contexts else []
        reply_template = self.config.dummy_reply or DEFAULT_DUMMY_REPLY
        reply = reply_template.replace("{question}", question)

        delay_ms = max(0, int(self.config.dummy_delay_ms))
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        return AssistantChatResult(
            reply=reply,
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

    def _extract_sources(self, hits: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
            merged = source.get("merge_title_content")
            snippet = str(merged).strip() if isinstance(merged, str) and merged.strip() else ""
            sources.append(
                {
                    "doc_id": doc_id,
                    "title": title,
                    "snippet": snippet,
                }
            )
        return sources

    def _retrieve_documents(
        self, session: requests.Session, question: str, index_name: Optional[str] = None
    ) -> Tuple[List[str], Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        target_index_raw = (index_name or "").strip() or self.config.rag_index_name
        if not rag_services.RAG_SEARCH_URL or not target_index_raw:
            return [], None, []

        try:
            data = rag_services.search_rag(
                question,
                index_name=target_index_raw,
                num_result_doc=self.config.rag_num_docs,
                timeout=self.config.request_timeout,
            )
        except requests.HTTPError as exc:
            resp = exc.response
            status = resp.status_code if resp is not None else "unknown"
            text_preview = (getattr(resp, "text", "") or "")[:500]
            raise AssistantRequestError(f"RAG HTTP 오류 [{status}]: {text_preview!r}") from exc
        except requests.RequestException as exc:
            raise AssistantRequestError(f"RAG 요청 중 오류 발생: {exc}") from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise AssistantRequestError(f"RAG 응답 처리 실패: {exc}") from exc

        hits = data.get("hits", {}).get("hits", [])
        if not isinstance(hits, list):
            return [], data, []

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

        sources = self._extract_sources(hits)
        return documents, data, sources

    def _generate_llm_payload(self, question: str, contexts: List[str], *, email_ids: List[str]) -> Dict[str, Any]:
        context_str = "\n".join(contexts) if contexts else NO_CONTEXT_MESSAGE
        email_id_list = "\n".join(f"- {email_id}" for email_id in email_ids) if email_ids else "- (없음)"

        system_msg = {
            "role": "system",
            "content": self.config.system_message,
        }
        format_msg = {
            "role": "system",
            "content": STRUCTURED_REPLY_SYSTEM_MESSAGE,
        }
        user_msg = {
            "role": "user",
            "content": "\n".join(
                [
                    "아래 규칙을 반드시 지켜서 JSON으로만 답해.",
                    "",
                    '[응답 형식] {"answer": string, "segments": {"answer": string, "usedEmailIds": string[]}[]}',
                    "- answer: 통합 답변(출처가 없을 때만 화면에 표시됨)",
                    "- segments: 출처(메일) 기반 답변 블록 목록",
                    "- segments의 각 항목은 반드시 usedEmailIds를 포함해야 함",
                    "- 출처를 1개 이상 사용했다면 segments는 반드시 1개 이상이어야 함",
                    "- 사용한 메일이 없거나 질문과 무관하면 segments는 빈 배열([])",
                    "- 가능하면 메일별로 segments를 분리하되, 여러 메일을 함께 사용하면 한 segment에 usedEmailIds 여러 개를 넣어도 됨",
                    "- 위 목록에 없는 emailId를 새로 만들거나 추측하지 말 것",
                    "",
                    "[사용 가능한 emailId 목록]",
                    email_id_list,
                    "",
                    f"질문: {question}",
                    "",
                    "[배경지식]",
                    context_str,
                ]
            ),
        }

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": [system_msg, format_msg, user_msg],
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

    def _call_llm(
        self,
        session: requests.Session,
        question: str,
        contexts: List[str],
        sources: List[Dict[str, Any]],
        user_header_id: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
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
        if user_header_id:
            headers["User-Id"] = user_header_id

        email_ids: List[str] = []
        for entry in sources:
            if not isinstance(entry, dict):
                continue
            doc_id = entry.get("doc_id")
            if isinstance(doc_id, str) and doc_id.strip():
                email_ids.append(doc_id.strip())
        payload = self._generate_llm_payload(question, contexts, email_ids=list(dict.fromkeys(email_ids)))
        resp_json = self._post(session, self.config.llm_url, headers, payload)
        reply = self._extract_llm_reply(resp_json)
        return reply, resp_json

    def generate_reply(
        self, question: str, *, user_header_id: Optional[str] = None, rag_index_name: Optional[str] = None
    ) -> AssistantChatResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise AssistantRequestError("질문이 비어 있습니다.")

        if self.config.use_dummy:
            if self.config.dummy_use_rag:
                try:
                    with requests.Session() as session:
                        contexts, rag_response, sources = self._retrieve_documents(
                            session, normalized_question, rag_index_name
                        )
                except AssistantRequestError:
                    contexts, rag_response, sources = [], None, []
                dummy_result = self._generate_dummy_result(
                    normalized_question,
                    contexts=contexts,
                    sources=sources,
                    rag_response=rag_response,
                )
            else:
                dummy_result = self._generate_dummy_result(normalized_question)

            answer, segments = _parse_structured_llm_reply(dummy_result.reply)
            dummy_result.reply = answer
            if segments is None:
                dummy_result.sources = []
                dummy_result.segments = []
                return dummy_result

            built_segments, filtered_sources = self._build_segments(
                list(getattr(dummy_result, "sources", [])),
                segments,
            )
            dummy_result.segments = built_segments
            dummy_result.sources = filtered_sources
            return dummy_result

        with requests.Session() as session:
            contexts, rag_response, sources = self._retrieve_documents(
                session, normalized_question, rag_index_name
            )
            reply, llm_response = self._call_llm(
                session,
                normalized_question,
                contexts,
                sources,
                user_header_id=user_header_id,
            )

        answer, segments = _parse_structured_llm_reply(reply)
        if segments is None:
            return AssistantChatResult(
                reply=answer,
                contexts=contexts,
                llm_response=llm_response,
                rag_response=rag_response,
                sources=[],
                segments=[],
            )

        built_segments, filtered_sources = self._build_segments(sources, segments)

        return AssistantChatResult(
            reply=answer,
            contexts=contexts,
            llm_response=llm_response,
            rag_response=rag_response,
            sources=filtered_sources,
            segments=built_segments,
        )


assistant_chat_service = AssistantChatService()
