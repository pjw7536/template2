"""Observer 분석 source 조회와 OpenWebUI 실행을 조율합니다."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence

from api.common.services import ExternalCallCancellation

from .analysis_context import (
    ANALYSIS_SOURCE_LIMIT,
    ANALYSIS_SYSTEM_PROMPT,
    EQP_TARGET_STATUSES,
    MAX_PROMPT_CHARS,
    OBSERVER_ANALYSIS_PROMPT_VERSION,
    OBSERVER_ANALYSIS_SCHEMA_VERSION,
    TIP_EXCLUDED_STATUSES,
    TIP_TARGET_PATTERN,
    build_observer_analysis_context,
    build_observer_evidence_id,
)
from .analysis_payload import (
    _filter_analysis_evidence_ids,
    _get_available_evidence_ids,
    _parse_json_object,
    build_observer_analysis_messages,
    normalize_observer_analysis_result,
)
from .openwebui import ObserverOpenWebUIConfig, stream_observer_analysis


def _collect_observer_analysis_context(
    *,
    eqp_id: str,
    start_at: datetime,
    end_at: datetime,
    log_types: Sequence[str],
    selected_tip_groups: Sequence[str],
) -> dict[str, object]:
    """현재 조회 조건에 맞는 source를 읽어 분석 context를 생성합니다.

    입력:
    - eqp_id/start_at/end_at: Observer 조회 조건
    - log_types/selected_tip_groups: 현재 화면 filter

    반환:
    - dict: OpenWebUI에 전달할 압축 분석 context

    부작용:
    - Observer selector로 DB를 읽습니다.

    오류:
    - 모든 source 조회가 실패하면 RuntimeError가 발생합니다.
    """

    # services facade 초기화 중 selectors가 다시 services를 읽는 순환 import를 피합니다.
    from api.observer import selectors

    logs_by_type: dict[str, list[dict[str, object]]] = {}
    source_errors: dict[str, str] = {}
    for log_type in log_types:
        try:
            logs_by_type[log_type] = selectors.get_analysis_logs_by_type(
                eqp_id=eqp_id,
                log_key=log_type,
                start_at=start_at.isoformat(),
                end_at=end_at.isoformat(),
                limit=ANALYSIS_SOURCE_LIMIT,
            )
        except Exception as exc:  # source별 부분 실패를 coverage에 남기고 성공 source를 유지합니다.
            source_errors[log_type] = type(exc).__name__
            logs_by_type[log_type] = []

    if log_types and len(source_errors) == len(log_types):
        raise RuntimeError("Observer 분석 대상 로그를 조회하지 못했습니다.")

    return build_observer_analysis_context(
        eqp_id=eqp_id,
        start_at=start_at,
        end_at=end_at,
        log_types=log_types,
        selected_tip_groups=selected_tip_groups,
        logs_by_type=logs_by_type,
        source_errors=source_errors,
    )


def _finalize_observer_analysis_payload(
    *,
    context: Mapping[str, object],
    analysis: dict[str, object],
    openwebui_config: ObserverOpenWebUIConfig,
    prompt_version: str,
) -> dict[str, object]:
    """모델 분석에 근거 검증과 coverage 한계를 반영해 응답을 완성합니다."""

    _filter_analysis_evidence_ids(
        analysis=analysis,
        available_evidence_ids=_get_available_evidence_ids(context),
    )
    coverage = context["coverage"]
    deterministic_limitations: list[str] = []
    if coverage["sourceMayBeTruncated"]:
        deterministic_limitations.append(
            "일부 source가 조회 상한에 도달해 전체 기간의 발생 건수가 더 많을 수 있습니다."
        )
    if coverage["sourceErrors"]:
        failed_sources = ", ".join(sorted(coverage["sourceErrors"]))
        deterministic_limitations.append(
            f"일부 source 조회가 실패해 분석에서 제외되었습니다: {failed_sources}"
        )
    if coverage["promptTruncated"]:
        truncation = coverage.get("promptTruncation") or {}
        reduced_sections = [
            key
            for key, counts in truncation.items()
            if isinstance(counts, dict)
            and counts.get("after", 0) < counts.get("before", 0)
        ]
        deterministic_limitations.append(
            "입력 크기 제한으로 다음 분석 항목을 축소했습니다: "
            + ", ".join(reduced_sections)
        )
    analysis["limitations"] = list(
        dict.fromkeys([*analysis["limitations"], *deterministic_limitations])
    )
    return {
        "analysis": analysis,
        "meta": {
            **coverage,
            "analysisModel": openwebui_config.model,
            "promptVersion": prompt_version,
            "schemaVersion": OBSERVER_ANALYSIS_SCHEMA_VERSION,
        },
        "scope": context["scope"],
    }


def analyze_observer_logs_stream(
    *,
    eqp_id: str,
    start_at: datetime,
    end_at: datetime,
    log_types: Sequence[str],
    selected_tip_groups: Sequence[str],
    question: str,
    cancellation: ExternalCallCancellation,
    conversation_summary: str = "",
) -> dict[str, object]:
    """현재 Observer 데이터를 재조회하고 취소 가능한 stream으로 구조화 응답을 완성합니다."""

    cancellation.raise_if_cancelled()
    context = _collect_observer_analysis_context(
        eqp_id=eqp_id,
        start_at=start_at,
        end_at=end_at,
        log_types=log_types,
        selected_tip_groups=selected_tip_groups,
    )
    cancellation.raise_if_cancelled()
    openwebui_config = ObserverOpenWebUIConfig.from_settings()
    raw_result = "".join(
        stream_observer_analysis(
            messages=build_observer_analysis_messages(
                context=context,
                question=question,
                conversation_summary=conversation_summary,
            ),
            cancellation=cancellation,
            config=openwebui_config,
        )
    )
    cancellation.raise_if_cancelled()
    analysis = normalize_observer_analysis_result(_parse_json_object(raw_result))
    return _finalize_observer_analysis_payload(
        context=context,
        analysis=analysis,
        openwebui_config=openwebui_config,
        prompt_version=OBSERVER_ANALYSIS_PROMPT_VERSION,
    )

__all__ = [
    "ANALYSIS_SOURCE_LIMIT",
    "ANALYSIS_SYSTEM_PROMPT",
    "EQP_TARGET_STATUSES",
    "TIP_EXCLUDED_STATUSES",
    "TIP_TARGET_PATTERN",
    "OBSERVER_ANALYSIS_PROMPT_VERSION",
    "OBSERVER_ANALYSIS_SCHEMA_VERSION",
    "MAX_PROMPT_CHARS",
    "analyze_observer_logs_stream",
    "build_observer_analysis_context",
    "build_observer_analysis_messages",
    "build_observer_evidence_id",
    "normalize_observer_analysis_result",
]
