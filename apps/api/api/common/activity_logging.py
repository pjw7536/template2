"""Shared helpers for enriching activity logs with domain-specific details."""
from __future__ import annotations

from typing import Any, Dict, MutableMapping, Optional

from django.http import HttpRequest


ContextDict = MutableMapping[str, Any]


def _ensure_context(request: HttpRequest) -> ContextDict:
    """요청 단위 활동 로그 컨텍스트(dict)를 반환합니다.

    Return the per-request activity log context dictionary.
    """

    context = getattr(request, "_activity_log_context", None)
    if context is None:
        context = {}
        setattr(request, "_activity_log_context", context)
    return context


def set_activity_summary(request: HttpRequest, summary: str) -> None:
    """요청에서 수행 중인 작업 요약(summary)을 기록합니다.

    Store a human-readable summary of the action being performed.
    """

    context = _ensure_context(request)
    context["summary"] = summary


def set_activity_previous_state(request: HttpRequest, data: Optional[Any]) -> None:
    """변경 전(before) 상태를 활동 로그에 기록합니다.

    Record the state of the resource before a mutation occurs.
    """

    context = _ensure_context(request)
    context["before"] = data


def set_activity_new_state(request: HttpRequest, data: Optional[Any]) -> None:
    """변경 후(after) 상태를 활동 로그에 기록합니다.

    Record the state of the resource after a mutation occurs.
    """

    context = _ensure_context(request)
    context["after"] = data


def merge_activity_metadata(request: HttpRequest, **extra: Any) -> None:
    """활동 로그에 저장할 추가 메타데이터를 병합합니다.

    Merge additional metadata to be persisted with the activity log.
    """

    context = _ensure_context(request)
    metadata: Dict[str, Any] = context.setdefault("extra_metadata", {})
    metadata.update(extra)


__all__ = [
    "merge_activity_metadata",
    "set_activity_new_state",
    "set_activity_previous_state",
    "set_activity_summary",
]
