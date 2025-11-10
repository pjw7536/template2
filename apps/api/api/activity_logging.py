"""Helpers for enriching activity logs with domain-specific details."""
from __future__ import annotations

from typing import Any, Dict, MutableMapping, Optional

from django.http import HttpRequest


ContextDict = MutableMapping[str, Any]


def _ensure_context(request: HttpRequest) -> ContextDict:
    """Return the per-request activity log context dictionary."""

    context = getattr(request, "_activity_log_context", None)
    if context is None:
        context = {}
        setattr(request, "_activity_log_context", context)
    return context


def set_activity_summary(request: HttpRequest, summary: str) -> None:
    """Store a human-readable summary of the action being performed."""

    context = _ensure_context(request)
    context["summary"] = summary


def set_activity_previous_state(request: HttpRequest, data: Optional[Any]) -> None:
    """Record the state of the resource before a mutation occurs."""

    context = _ensure_context(request)
    context["before"] = data


def set_activity_new_state(request: HttpRequest, data: Optional[Any]) -> None:
    """Record the state of the resource after a mutation occurs."""

    context = _ensure_context(request)
    context["after"] = data


def set_activity_changes(request: HttpRequest, changes: Optional[Dict[str, Any]]) -> None:
    """Attach an explicit change set for the current request."""

    context = _ensure_context(request)
    context["changes"] = changes


def merge_activity_metadata(request: HttpRequest, **extra: Any) -> None:
    """Merge additional metadata to be persisted with the activity log."""

    context = _ensure_context(request)
    metadata: Dict[str, Any] = context.setdefault("extra_metadata", {})
    metadata.update(extra)


__all__ = [
    "merge_activity_metadata",
    "set_activity_changes",
    "set_activity_new_state",
    "set_activity_previous_state",
    "set_activity_summary",
]
