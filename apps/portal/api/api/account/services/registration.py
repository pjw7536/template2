"""참조 파일의 신규 사용자를 소속과 함께 등록하며 기존 계정·권한은 보존합니다."""

from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

from .. import selectors
from ..models import User, UserCurrentAffiliation


@transaction.atomic
def register_reference_users(*, records: Iterable[dict[str, str]], apply: bool = False) -> dict[str, int]:
    """EPID·사번·Knox ID·SDWT CSV 레코드를 검증하고 신규 사용자만 등록합니다.

    기본은 dry-run이며 오류가 나면 전체를 롤백합니다. 기존 식별자 충돌이나
    미등록 SDWT는 ValueError입니다. 접근 권한과 비밀번호는 부여하지 않습니다.
    """

    created = skipped = 0
    seen = {key: set() for key in ("epid", "sabun", "knox_id")}
    for number, record in enumerate(records, start=2):
        values = {key: (record.get(key) or "").strip() for key in (
            "epid", "sabun", "knox_id", "user_sdwt_prod", "username", "email", "department",
        )}
        for key, limit in (("epid", 50), ("sabun", 50), ("knox_id", 150)):
            value = values[key]
            if not value or len(value) > limit or value in seen[key]:
                raise ValueError(f"{number}행: {key} 누락·길이 초과·중복")
            seen[key].add(value)
        for key, limit in (("username", 150), ("email", 254), ("department", 128), ("user_sdwt_prod", 64)):
            if len(values[key]) > limit:
                raise ValueError(f"{number}행: {key} 길이 초과")

        matches = selectors.list_users_by_registration_identifiers(
            sabun=values["sabun"], epid=values["epid"], knox_id=values["knox_id"],
        )
        if matches:
            if len(matches) != 1 or any((getattr(matches[0], field) or "") != values[key]
                                       for field, key in (("sabun", "sabun"), ("avatarid", "epid"), ("knox_id", "knox_id"))):
                raise ValueError(f"{number}행: 기존 사용자 식별자 충돌")
            skipped += 1
            continue

        option = None
        if values["user_sdwt_prod"]:
            option = selectors.get_affiliation_option_by_user_sdwt_prod(
                user_sdwt_prod=values["user_sdwt_prod"],
            )
            if option is None:
                raise ValueError(f"{number}행: 활성 SDWT 목록에 없는 값")
        user = User.objects.create_user(
            sabun=values["sabun"], avatarid=values["epid"], knox_id=values["knox_id"],
            username=values["username"] or None, email=values["email"],
            department=values["department"] or None,
        )
        if option is not None:
            UserCurrentAffiliation.objects.create(
                user=user, affiliation=option,
                source=UserCurrentAffiliation.Sources.ADMIN_ASSIGNED,
                confirmed_at=timezone.now(),
            )
        created += 1
    if not apply:
        transaction.set_rollback(True)
    return {"created": created, "skipped": skipped}
