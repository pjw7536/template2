# =============================================================================
# 모듈: Assistant Runtime Profile registry
# 주요 대상: AssistantProfile, get_assistant_profile
# 핵심 전제: 지원 중인 과거 버전은 의미 재현용이고 권한 하한은 항상 최신 버전입니다.
# =============================================================================
"""Assistant 실행 의미와 현재 권한 하한을 분리한 Profile registry입니다."""

from __future__ import annotations

from dataclasses import dataclass


class AssistantProfileUnavailableError(ValueError):
    """요청한 Profile 또는 지원 버전이 registry에 없을 때 발생합니다."""


@dataclass(frozen=True)
class AssistantProfile:
    """Provider, Tool, memory partition과 권한 하한을 고정한 실행 Profile입니다."""

    key: str
    version: int
    provider: str
    allowed_tools: tuple[str, ...]
    account_scopes: tuple[str, ...]
    read_partitions: tuple[str, ...]
    write_partition: str
    timeout_seconds: int
    max_output_chars: int = 10_000


_PROFILES: dict[tuple[str, int], AssistantProfile] = {
    ("portal-default", 1): AssistantProfile(
        key="portal-default",
        version=1,
        provider="openwebui",
        allowed_tools=(),
        account_scopes=("assistant",),
        read_partitions=("shared",),
        write_partition="shared",
        timeout_seconds=130,
    ),
    ("portal-default", 2): AssistantProfile(
        key="portal-default",
        version=2,
        provider="openwebui",
        allowed_tools=(),
        account_scopes=("assistant",),
        read_partitions=("shared", "scope:emails", "scope:observer"),
        write_partition="shared",
        timeout_seconds=130,
    ),
    ("email-rag", 1): AssistantProfile(
        key="email-rag",
        version=1,
        provider="email-rag",
        allowed_tools=("rag.search",),
        account_scopes=("assistant", "emails"),
        read_partitions=("shared", "scope:emails"),
        write_partition="scope:emails",
        timeout_seconds=130,
    ),
    ("email-rag", 2): AssistantProfile(
        key="email-rag",
        version=2,
        provider="email-rag",
        allowed_tools=("rag.search",),
        account_scopes=("assistant", "emails"),
        read_partitions=("shared", "scope:emails"),
        write_partition="scope:emails",
        timeout_seconds=130,
    ),
    ("observer-analysis", 1): AssistantProfile(
        key="observer-analysis",
        version=1,
        provider="observer-analysis",
        allowed_tools=("observer.analysis",),
        account_scopes=("assistant", "observer"),
        read_partitions=("shared", "scope:observer"),
        write_partition="scope:observer",
        timeout_seconds=130,
    ),
    ("observer-analysis", 2): AssistantProfile(
        key="observer-analysis",
        version=2,
        provider="observer-analysis",
        allowed_tools=("observer.analysis",),
        account_scopes=("assistant", "observer"),
        read_partitions=("shared", "scope:observer"),
        write_partition="scope:observer",
        timeout_seconds=130,
    ),
    ("appstore-context", 1): AssistantProfile(
        key="appstore-context",
        version=1,
        provider="appstore-context",
        allowed_tools=("appstore.catalog",),
        account_scopes=("assistant", "appstore"),
        read_partitions=("shared", "scope:appstore"),
        write_partition="scope:appstore",
        timeout_seconds=130,
    ),
    ("appstore-context", 2): AssistantProfile(
        key="appstore-context",
        version=2,
        provider="appstore-context",
        allowed_tools=("appstore.catalog",),
        account_scopes=("assistant", "appstore"),
        read_partitions=("shared", "scope:appstore"),
        write_partition="scope:appstore",
        timeout_seconds=130,
    ),
    ("line-dashboard-context", 1): AssistantProfile(
        key="line-dashboard-context",
        version=1,
        provider="line-dashboard-context",
        allowed_tools=("line-dashboard.snapshot",),
        account_scopes=("assistant", "line-dashboard"),
        read_partitions=("shared", "scope:line-dashboard"),
        write_partition="scope:line-dashboard",
        timeout_seconds=130,
    ),
    ("line-dashboard-context", 2): AssistantProfile(
        key="line-dashboard-context",
        version=2,
        provider="line-dashboard-context",
        allowed_tools=("line-dashboard.snapshot",),
        account_scopes=("assistant", "line-dashboard"),
        read_partitions=("shared", "scope:line-dashboard"),
        write_partition="scope:line-dashboard",
        timeout_seconds=130,
    ),
    ("auto-knowledge", 1): AssistantProfile(
        key="auto-knowledge",
        version=1,
        provider="auto-knowledge",
        allowed_tools=(
            "rag.search",
            "observer.analysis",
            "appstore.catalog",
            "line-dashboard.snapshot",
        ),
        account_scopes=("assistant",),
        read_partitions=(
            "shared",
            "scope:emails",
            "scope:observer",
            "scope:appstore",
            "scope:line-dashboard",
        ),
        write_partition="shared",
        timeout_seconds=260,
    ),
}

_CURRENT_VERSIONS = {
    "portal-default": 2,
    "email-rag": 2,
    "observer-analysis": 2,
    "appstore-context": 2,
    "line-dashboard-context": 2,
    "auto-knowledge": 1,
}


def get_assistant_profile(
    *,
    profile_key: str,
    profile_version: int | None = None,
) -> AssistantProfile:
    """Profile 의미를 요청 버전 또는 현재 버전으로 해석합니다.

    입력:
        profile_key: 공개 Profile key입니다.
        profile_version: 재실행 시 보존할 과거 버전이며 생략하면 현재 버전입니다.

    반환:
        불변 AssistantProfile 객체입니다.

    오류:
        지원하지 않는 key/version이면 AssistantProfileUnavailableError가 발생합니다.
    """

    normalized_key = str(profile_key or "").strip()
    resolved_version = profile_version or _CURRENT_VERSIONS.get(normalized_key)
    profile = _PROFILES.get((normalized_key, resolved_version))
    if profile is None:
        raise AssistantProfileUnavailableError("profile_version_unavailable")
    return profile


def get_current_assistant_profile(*, profile_key: str) -> AssistantProfile:
    """현재 authorization floor에 사용할 최신 Profile을 반환합니다."""

    return get_assistant_profile(profile_key=profile_key)


__all__ = [
    "AssistantProfile",
    "AssistantProfileUnavailableError",
    "get_assistant_profile",
    "get_current_assistant_profile",
]
