from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from api.models import AffiliationHierarchy, UserSdwtProdChange

User = get_user_model()

UNKNOWN = "UNKNOWN"
UNCLASSIFIED_USER_SDWT_PROD = "rp-unclassified"


def resolve_user_affiliation(user: User, at_time) -> dict:
    """
    Resolve a user's affiliation (department, line, user_sdwt_prod) at a given time.
    - Uses UserSdwtProdChange history (latest effective_from <= at_time).
    - Falls back to current user fields.
    """
    if at_time is None:
        at_time = timezone.now()

    change = (
        UserSdwtProdChange.objects.filter(user=user, effective_from__lte=at_time)
        .order_by("-effective_from", "-id")
        .first()
    )

    if change:
        return {
            "department": change.department or user.department or UNKNOWN,
            "line": change.line or user.line or "",
            "user_sdwt_prod": change.to_user_sdwt_prod or user.user_sdwt_prod or UNCLASSIFIED_USER_SDWT_PROD,
        }

    return {
        "department": user.department or UNKNOWN,
        "line": user.line or "",
        "user_sdwt_prod": user.user_sdwt_prod or UNCLASSIFIED_USER_SDWT_PROD,
    }


def resolve_user_affiliation_by_username(username: str, at_time) -> Optional[dict]:
    """Find user by username and resolve affiliation at the given time."""
    if not username:
        return None
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return None
    return resolve_user_affiliation(user, at_time)


def get_affiliation_option(department: str, line: str, user_sdwt_prod: str) -> Optional[AffiliationHierarchy]:
    if not department or not line or not user_sdwt_prod:
        return None
    try:
        return AffiliationHierarchy.objects.get(
            department=department.strip(),
            line=line.strip(),
            user_sdwt_prod=user_sdwt_prod.strip(),
        )
    except AffiliationHierarchy.DoesNotExist:
        return None
