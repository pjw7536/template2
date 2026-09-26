"""외부 인증 identity를 Account 사용자에 반영하는 쓰기 서비스를 제공합니다."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .. import selectors


def _apply_user_updates(*, user: Any, candidate_updates: dict[str, Any]) -> list[str]:
    """최근 토큰 필드를 반영하며 제거된 선택 필드는 비웁니다."""

    concrete_field_names = {field.name for field in user._meta.concrete_fields}
    update_fields: list[str] = []
    for field_name, value in candidate_updates.items():
        if field_name not in concrete_field_names:
            continue
        field = user._meta.get_field(field_name)
        if value is None and not field.null:
            value = ""
        if getattr(user, field_name) == value:
            continue
        setattr(user, field_name, value)
        update_fields.append(field_name)
    return update_fields


def upsert_user_identity(
    *,
    identity: dict[str, Any],
    sabun: str,
    knox_id: str,
) -> tuple[Any, bool]:
    """정규화된 외부 identity로 Account 사용자를 원자적으로 생성하거나 갱신합니다."""

    if any(not isinstance(value, str) or not value.strip() for value in (identity.get("avatarid"), sabun, knox_id)):
        raise ValueError("required_identity_missing")
    identity = {**identity, "avatarid": identity["avatarid"].strip()}
    normalized_sabun = str(sabun).strip()
    normalized_knox_id = str(knox_id).strip()
    UserModel = get_user_model()
    concrete_field_names = {field.name for field in UserModel._meta.concrete_fields}
    defaults = {
        key: value
        for key, value in identity.items()
        if key != "sabun" and key in concrete_field_names and value is not None
    }
    defaults["knox_id"] = normalized_knox_id

    with transaction.atomic():
        user = selectors.get_user_by_epid(epid=identity["avatarid"])
        created = False
        if user is None:
            try:
                with transaction.atomic():
                    user = UserModel(sabun=normalized_sabun, **defaults)
                    user.set_unusable_password()
                    user.save()
                created = True
            except IntegrityError:
                user = selectors.get_user_by_epid(epid=identity["avatarid"])
                if user is None:
                    raise

        if not user.is_active or user.is_staff or user.is_superuser:
            raise ValueError("identity_unavailable")
        candidate_updates = {**identity, "knox_id": normalized_knox_id, "sabun": normalized_sabun}
        update_fields = _apply_user_updates(user=user, candidate_updates=candidate_updates)
        if created or update_fields:
            user.save(update_fields=update_fields or None)
    return user, created
