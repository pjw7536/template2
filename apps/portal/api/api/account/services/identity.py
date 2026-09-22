"""외부 인증 identity를 Account 사용자에 반영하는 쓰기 서비스를 제공합니다."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .. import selectors


def _apply_user_updates(*, user: Any, candidate_updates: dict[str, str | None]) -> list[str]:
    """사용자 model에 존재하는 비어 있지 않은 변경 필드만 반영합니다."""

    concrete_field_names = {field.name for field in user._meta.concrete_fields}
    update_fields: list[str] = []
    for field_name, value in candidate_updates.items():
        if not value or field_name not in concrete_field_names:
            continue
        if getattr(user, field_name) == value:
            continue
        setattr(user, field_name, value)
        update_fields.append(field_name)
    return update_fields


def upsert_user_identity(
    *,
    identity: dict[str, str | None],
    sabun: str,
    knox_id: str,
) -> tuple[Any, bool]:
    """정규화된 외부 identity로 Account 사용자를 원자적으로 생성하거나 갱신합니다."""

    normalized_sabun = str(sabun).strip()
    normalized_knox_id = str(knox_id).strip()
    UserModel = get_user_model()
    concrete_field_names = {field.name for field in UserModel._meta.concrete_fields}
    defaults = {
        key: value
        for key, value in identity.items()
        if key != "sabun" and key in concrete_field_names
    }
    defaults["knox_id"] = normalized_knox_id

    with transaction.atomic():
        user = selectors.get_user_by_sabun(sabun=normalized_sabun)
        created = False
        if user is None:
            try:
                user = UserModel.objects.create(sabun=normalized_sabun, **defaults)
                created = True
            except IntegrityError:
                user = selectors.get_user_by_sabun(sabun=normalized_sabun)
                if user is None:
                    raise

        candidate_updates = {**identity, "knox_id": normalized_knox_id}
        candidate_updates.pop("sabun", None)
        update_fields = _apply_user_updates(user=user, candidate_updates=candidate_updates)
        if created or update_fields:
            user.save(update_fields=update_fields or None)
    return user, created
