"""Observer 분석 prompt message와 모델 응답 정규화 계약입니다."""

from __future__ import annotations

import json
from typing import Mapping

from .analysis_context import (
    ANALYSIS_SYSTEM_PROMPT,
    MAX_ANALYSIS_QUESTION_CHARS,
    MAX_CONVERSATION_SUMMARY_CHARS,
    _text,
)
from .openwebui import ObserverOpenWebUIError


def _build_analysis_user_content(
    *,
    context: Mapping[str, object],
    question: str,
    conversation_summary: str = "",
) -> str:
    """일반·stream 분석이 공유하는 사용자 message content를 생성합니다."""

    return "\n".join(
        [
            "analysis_question:",
            _text(question, max_chars=MAX_ANALYSIS_QUESTION_CHARS),
            "",
            "conversation_summary:",
            _text(
                conversation_summary,
                max_chars=MAX_CONVERSATION_SUMMARY_CHARS,
            ),
            "",
            "observer_analysis_context_json:",
            json.dumps(context, ensure_ascii=False, separators=(",", ":")),
        ]
    )


def build_observer_analysis_messages(
    *,
    context: Mapping[str, object],
    question: str,
    conversation_summary: str = "",
) -> list[dict[str, str]]:
    """구조화 context와 사용자 질문을 단일 JSON 분석 message로 변환합니다."""

    return [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _build_analysis_user_content(
                context=context,
                question=question,
                conversation_summary=conversation_summary,
            ),
        },
    ]


def _parse_json_object(raw_content: str) -> dict[str, object]:
    """OpenWebUI content가 단일 JSON 객체 계약을 정확히 지키는지 검증합니다."""

    content = raw_content.strip()
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ObserverOpenWebUIError("OpenWebUI 분석 응답이 JSON 형식이 아닙니다.") from exc
    if not isinstance(payload, dict):
        raise ObserverOpenWebUIError("OpenWebUI 분석 응답이 JSON 객체가 아닙니다.")
    return payload


def _string_list(value: object, *, limit: int = 20) -> list[str]:
    """모델 응답의 문자열 목록을 화면 계약에 맞게 제한합니다."""

    if not isinstance(value, list):
        return []
    return [_text(item, max_chars=1000) for item in value[:limit] if _text(item)]


def normalize_observer_analysis_result(payload: Mapping[str, object]) -> dict[str, object]:
    """OpenWebUI JSON을 Observer 화면의 안정적인 응답 계약으로 정규화합니다."""

    findings: list[dict[str, object]] = []
    raw_findings = payload.get("findings")
    if isinstance(raw_findings, list):
        for raw_finding in raw_findings[:5]:
            if not isinstance(raw_finding, dict):
                continue
            findings.append(
                {
                    "category": _text(raw_finding.get("category"), max_chars=30),
                    "target": _text(raw_finding.get("target"), max_chars=200),
                    "assessment": _text(
                        raw_finding.get("assessment"),
                        max_chars=3000,
                    ),
                    "recordedCauses": _string_list(raw_finding.get("recordedCauses")),
                    "inferredCauses": _string_list(raw_finding.get("inferredCauses")),
                    "evidenceIds": _string_list(raw_finding.get("evidenceIds"), limit=50),
                }
            )
    return {
        "headline": _text(payload.get("headline"), max_chars=500),
        "summary": _text(payload.get("summary"), max_chars=5000),
        "findings": findings,
        "recommendedChecks": _string_list(payload.get("recommendedChecks")),
        "limitations": _string_list(payload.get("limitations")),
    }


def _get_available_evidence_ids(context: Mapping[str, object]) -> set[str]:
    """실제 모델 입력 context에 포함된 근거 event ID 집합을 반환합니다."""

    available: set[str] = set()

    def collect_named_ids(value: object) -> None:
        """통계·target event에 명시된 event/evidence ID를 재귀 수집합니다."""

        if isinstance(value, Mapping):
            event_id = _text(value.get("eventId"))
            if event_id:
                available.add(event_id)
            evidence_ids = value.get("evidenceIds")
            if isinstance(evidence_ids, list):
                available.update(
                    evidence_id
                    for item in evidence_ids
                    if (evidence_id := _text(item))
                )
            for nested_value in value.values():
                collect_named_ids(nested_value)
        elif isinstance(value, list):
            for nested_value in value:
                collect_named_ids(nested_value)

    collect_named_ids(context)

    context_events = context.get("contextEvents")
    if not isinstance(context_events, Mapping):
        return available
    columns = context_events.get("columns")
    rows = context_events.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        return available
    try:
        event_id_index = columns.index("eventId")
    except ValueError:
        return available
    for row in rows:
        if isinstance(row, list) and len(row) > event_id_index:
            event_id = _text(row[event_id_index])
            if event_id:
                available.add(event_id)
    return available


def _filter_analysis_evidence_ids(
    *,
    analysis: dict[str, object],
    available_evidence_ids: set[str],
) -> None:
    """모델이 실제 입력에 없는 evidence ID를 응답에 남기지 않게 제한합니다."""

    findings = analysis.get("findings")
    if not isinstance(findings, list):
        return
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        evidence_ids = finding.get("evidenceIds")
        if not isinstance(evidence_ids, list):
            finding["evidenceIds"] = []
            continue
        finding["evidenceIds"] = [
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id in available_evidence_ids
        ]

__all__ = [
    "build_observer_analysis_messages",
    "normalize_observer_analysis_result",
]
