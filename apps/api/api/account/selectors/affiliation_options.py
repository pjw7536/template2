"""소속 식별자를 단일 Affiliation 행으로 해석하는 selector입니다."""

from __future__ import annotations

from ..models import Affiliation


def _normalize_text(value: object) -> str | None:
    """입력을 빈 값 없는 문자열로 정규화합니다."""

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def get_affiliation_option_by_user_sdwt_prod(*, user_sdwt_prod: str) -> Affiliation | None:
    """활성 소속 식별자가 유일할 때 해당 Affiliation을 반환합니다."""

    normalized = _normalize_text(user_sdwt_prod)
    if not normalized:
        return None
    rows = list(
        Affiliation.objects.filter(
            is_active=True,
            user_sdwt_prod__iexact=normalized,
        ).order_by("id")[:2]
    )
    return rows[0] if len(rows) == 1 else None


def get_affiliation_option_for_update_by_user_sdwt_prod(
    *,
    user_sdwt_prod: str,
) -> Affiliation | None:
    """트랜잭션에서 활성 소속 식별자가 유일한 행을 잠가 반환합니다."""

    normalized = _normalize_text(user_sdwt_prod)
    if not normalized:
        return None
    rows = list(
        Affiliation.objects.select_for_update(of=("self",))
        .filter(is_active=True, user_sdwt_prod__iexact=normalized)
        .order_by("id")[:2]
    )
    return rows[0] if len(rows) == 1 else None
