# =============================================================================
# 모듈: LLM 구조화 응답 파싱
# 주요 구성: AssistantStructuredSegment, _parse_structured_llm_reply
# 주요 가정: 응답은 segments 배열과 조건부 answer를 가진 JSON 객체 하나입니다.
# =============================================================================
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class AssistantStructuredSegment:
    """LLM 구조화 응답에서 segment 1개를 표현합니다."""

    answer: str
    used_email_ids: List[str]


def _parse_structured_llm_reply(raw_reply: str) -> Tuple[str, List[AssistantStructuredSegment]]:
    """LLM 응답이 현재 Email JSON 계약을 정확히 지키는지 검증합니다.

    인자:
        raw_reply: LLM 원본 응답 문자열.

    반환:
        (answer, segments) 튜플.
        - answer: 표시용 문자열
        - segments: 검증된 list[AssistantStructuredSegment]

    부작용:
        없음. 순수 파싱입니다.

    허용 형식:
        {"answer": unknown, "segments": [{"answer": string, "usedEmailIds": string[]}]}
        - segments가 비어 있을 때는 answer가 반드시 필요합니다.
        - segments가 있을 때는 각 segment가 표시 답변이므로 answer는 문자열일 때만 사용합니다.
    """

    try:
        parsed = json.loads(raw_reply.strip())
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("Email LLM 응답이 JSON 형식이 아닙니다.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Email LLM 응답이 JSON 객체가 아닙니다.")

    segments_raw = parsed.get("segments")
    if not isinstance(segments_raw, list):
        raise ValueError("Email LLM 응답의 segments가 배열이 아닙니다.")

    segments: List[AssistantStructuredSegment] = []
    for entry in segments_raw:
        if not isinstance(entry, dict):
            raise ValueError("Email LLM segment가 JSON 객체가 아닙니다.")
        segment_answer = entry.get("answer")
        used_email_ids = entry.get("usedEmailIds")
        if not isinstance(segment_answer, str) or not segment_answer.strip():
            raise ValueError("Email LLM segment answer가 비어 있습니다.")
        if not isinstance(used_email_ids, list) or not used_email_ids:
            raise ValueError("Email LLM segment usedEmailIds가 비어 있습니다.")
        if any(not isinstance(item, str) or not item.strip() for item in used_email_ids):
            raise ValueError("Email LLM segment usedEmailIds 형식이 올바르지 않습니다.")
        segments.append(
            AssistantStructuredSegment(
                answer=segment_answer.strip(),
                used_email_ids=list(
                    dict.fromkeys(item.strip() for item in used_email_ids)
                ),
            )
        )

    answer_raw = parsed.get("answer")
    answer = answer_raw.strip() if isinstance(answer_raw, str) else ""
    if segments:
        return answer, segments
    if answer_raw is not None and not isinstance(answer_raw, str):
        raise ValueError("Email LLM 응답의 answer 형식이 올바르지 않습니다.")
    if not answer:
        raise ValueError("Email LLM 응답의 answer가 비어 있습니다.")

    return answer, segments
