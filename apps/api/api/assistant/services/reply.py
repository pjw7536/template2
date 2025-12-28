# =============================================================================
# 모듈: LLM 구조화 응답 파싱
# 주요 구성: AssistantStructuredSegment, _parse_structured_llm_reply
# 주요 가정: 응답은 JSON 객체 1개 또는 레거시 usedEmailIds 형태입니다.
# =============================================================================
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AssistantStructuredSegment:
    """LLM 구조화 응답에서 segment 1개를 표현합니다."""

    answer: str
    used_email_ids: List[str]


def _strip_markdown_code_fence(text: str) -> str:
    """마크다운 코드펜스를 제거한 문자열을 반환합니다.

    인자:
        text: 원본 문자열.

    반환:
        코드펜스가 제거된 문자열.

    부작용:
        없음. 순수 문자열 처리입니다.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정리 및 코드펜스 여부 확인
    # -----------------------------------------------------------------------------
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    # -----------------------------------------------------------------------------
    # 2) 코드펜스 블록 해제
    # -----------------------------------------------------------------------------
    lines = cleaned.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1]).strip()

    return cleaned


def _parse_structured_llm_reply(raw_reply: str) -> Tuple[str, Optional[List[AssistantStructuredSegment]]]:
    """LLM 응답(JSON)을 파싱해 answer/segments를 추출합니다.

    인자:
        raw_reply: LLM 원본 응답 문자열.

    반환:
        (answer, segments) 튜플.
        - answer: 표시용 문자열
        - segments: 형식이 유효할 때 list[AssistantStructuredSegment], 아니면 None

    부작용:
        없음. 순수 파싱입니다.

    지원 형식:
        - 최신: {"answer": string, "segments": [{"answer": string, "usedEmailIds": string[]}]}
        - 레거시: {"answer": string, "usedEmailIds": string[]}
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 문자열 정리
    # -----------------------------------------------------------------------------
    fallback_answer = _strip_markdown_code_fence(raw_reply)
    if not fallback_answer:
        return "", None

    # -----------------------------------------------------------------------------
    # 2) JSON 후보 문자열 추출
    # -----------------------------------------------------------------------------
    candidates = [fallback_answer]
    first_brace = fallback_answer.find("{")
    last_brace = fallback_answer.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(fallback_answer[first_brace : last_brace + 1].strip())

    # -----------------------------------------------------------------------------
    # 3) JSON 파싱 시도
    # -----------------------------------------------------------------------------
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

    # -----------------------------------------------------------------------------
    # 4) 최신 segments 스키마 처리
    # -----------------------------------------------------------------------------
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

    # -----------------------------------------------------------------------------
    # 5) 레거시 usedEmailIds 스키마 처리
    # -----------------------------------------------------------------------------
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
