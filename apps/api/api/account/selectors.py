# =============================================================================
# 모듈 설명: account 도메인의 읽기 전용 셀렉터를 제공합니다.
# - 주요 대상: 소속/권한/변경 요청 조회 함수
# - 불변 조건: 모든 조회는 부작용 없는 ORM 읽기만 수행합니다.
# =============================================================================

"""계정 도메인의 읽기 전용 셀렉터 모음.

- 주요 대상: 소속/권한/변경 요청 조회 함수
- 주요 엔드포인트/클래스: 없음(셀렉터 함수 제공)
- 가정/불변 조건: 모든 조회는 부작용 없는 ORM 읽기만 수행함
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from django.contrib.auth import get_user_model
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Lower, NullIf, Trim
from django.utils import timezone

from api.common.services import UNKNOWN, UNCLASSIFIED_USER_SDWT_PROD

from .models import (
    ACCESS_SCOPE_PORTAL,
    AccessAuditLog,
    AccessPolicyRule,
    AccessScope,
    AccessSource,
    Affiliation,
    ExternalAffiliationSnapshot,
    UserAccess,
    UserCurrentAffiliation,
    UserScopeAffiliationGrant,
    UserSdwtProdAccess,
    UserSdwtProdChange,
    _build_user_sdwt_display_map,
    _collapse_user_sdwt_prod_values,
    _normalize_user_sdwt_prod,
)


def _normalize_text(value: Any) -> str | None:
    """문자열 값을 공백 제거 기준으로 정규화합니다."""

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_text_list(values: Iterable[Any]) -> list[str]:
    """문자열 iterable에서 빈 값을 제거한 정규화 목록을 반환합니다."""

    normalized: list[str] = []
    for value in values:
        cleaned = _normalize_text(value)
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _collapse_text_values(values: Iterable[Any]) -> list[str]:
    """표시값을 유지하면서 대소문자 비구분 중복을 제거합니다."""

    display_by_key: dict[str, str] = {}
    for value in values:
        normalized = _normalize_text(value)
        if not normalized:
            continue
        display_by_key.setdefault(normalized.casefold(), normalized)
    return sorted(display_by_key.values())


def _normalize_positive_int_set(values: Iterable[Any], *, allow_cast: bool = False) -> set[int]:
    """양의 정수 ID 집합을 중복 없이 정규화합니다."""

    normalized: set[int] = set()
    for value in values:
        if allow_cast:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
        elif isinstance(value, int):
            parsed = value
        else:
            continue
        if parsed > 0:
            normalized.add(parsed)
    return normalized


def _resolved_access_department_expression():
    """정책 비교용 부서를 PostgreSQL `Lower` 결과로 반환합니다."""

    return Lower(
        Coalesce(
            NullIf(Trim("department"), Value("")),
            NullIf(
                Case(
                    When(
                        current_affiliation__affiliation__is_active=True,
                        then=Trim("current_affiliation__affiliation__department"),
                    ),
                    default=Value(""),
                    output_field=CharField(),
                ),
                Value(""),
            ),
            Value(""),
            output_field=CharField(),
        ),
    )


def _active_access_policy_queryset(
    *,
    department: str | None = None,
) -> QuerySet[AccessPolicyRule]:
    """활성 정책 값과 선택한 부서를 PostgreSQL에서 같은 방식으로 정규화합니다."""

    annotations = {
        "_access_policy_value": Lower(Trim("value")),
    }
    if department is not None:
        annotations["_access_department"] = Lower(
            Trim(Value(department, output_field=CharField()))
        )
    return AccessPolicyRule.objects.filter(is_active=True).annotate(**annotations)


def _list_active_user_contact_values_by_user_sdwt_prod(
    *,
    user_sdwt_prod: str,
    contact_field: str,
) -> list[str]:
    """소속에 연결된 활성 사용자 연락처 값을 중복 없이 조회합니다."""

    if contact_field not in {"email", "knox_id"}:
        raise ValueError("contact_field must be email or knox_id")

    normalized_user_sdwt_prod = _normalize_text(user_sdwt_prod)
    if not normalized_user_sdwt_prod:
        return []

    User = get_user_model()
    rows = (
        User.objects.filter(
            current_affiliation__affiliation__user_sdwt_prod__iexact=normalized_user_sdwt_prod,
            current_affiliation__affiliation__is_active=True,
            is_active=True,
        )
        .exclude(**{f"{contact_field}__isnull": True})
        .exclude(**{f"{contact_field}__exact": ""})
        .values_list(contact_field, flat=True)
        .order_by(contact_field)
        .distinct()
    )

    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in rows:
        cleaned = _normalize_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized_values.append(cleaned)
    return normalized_values


def get_current_affiliation_record(*, user: Any) -> UserCurrentAffiliation | None:
    """사용자의 현재 앱 소속 행을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserCurrentAffiliation | None: 현재 소속 행 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    if not user:
        return None

    return (
        UserCurrentAffiliation.objects.filter(
            user=user,
            affiliation__is_active=True,
        )
        .select_related("affiliation")
        .order_by("id")
        .first()
    )


def get_current_affiliation_values(*, user: Any) -> dict[str, Any]:
    """현재 앱 소속 값을 평탄화해 반환합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - dict[str, Any]: affiliation/department/line/user_sdwt_prod/reconfirm 값

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    row = get_current_affiliation_record(user=user)
    affiliation = row.affiliation if row and row.affiliation_id else None
    return {
        "affiliation": affiliation,
        "department": affiliation.department if affiliation else None,
        "line": affiliation.line if affiliation else None,
        "user_sdwt_prod": affiliation.user_sdwt_prod if affiliation else None,
        "requires_reconfirm": bool(row.requires_reconfirm) if row else False,
        "confirmed_at": row.confirmed_at if row else None,
        "source": row.source if row else None,
    }


def get_current_affiliation_values_by_user_ids(*, user_ids: Iterable[int]) -> dict[int, dict[str, Any]]:
    """사용자 id별 현재 앱 소속 값을 평탄화해 반환합니다.

    입력:
    - user_ids: 사용자 id iterable

    반환:
    - dict[int, dict[str, Any]]: user_id → 소속 값 매핑

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized_ids = _normalize_positive_int_set(user_ids, allow_cast=True)
    if not normalized_ids:
        return {}

    rows = (
        UserCurrentAffiliation.objects.filter(
            user_id__in=normalized_ids,
            affiliation__is_active=True,
        )
        .select_related("affiliation")
        .order_by("user_id")
    )
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        affiliation = row.affiliation if row.affiliation_id else None
        result[row.user_id] = {
            "department": affiliation.department if affiliation else None,
            "line": affiliation.line if affiliation else None,
            "user_sdwt_prod": affiliation.user_sdwt_prod if affiliation else None,
            "source": row.source,
        }
    return result


def get_current_user_sdwt_prod(*, user: Any) -> str | None:
    """현재 앱 소속의 user_sdwt_prod 값을 반환합니다."""

    values = get_current_affiliation_values(user=user)
    current = values.get("user_sdwt_prod")
    return current if isinstance(current, str) and current.strip() else None


def get_accessible_user_sdwt_prods_for_user(user: Any) -> set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 값 집합을 조회합니다.

    입력:
    - user: Django 사용자 객체(비인증 가능)

    반환:
    - set[str]: 접근 가능한 user_sdwt_prod 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 인증 여부 확인
    # -----------------------------------------------------------------------------
    if not user or not getattr(user, "is_authenticated", False):
        return set()

    # -----------------------------------------------------------------------------
    # 2) 슈퍼유저는 전체 집합 반환
    # -----------------------------------------------------------------------------
    if getattr(user, "is_superuser", False):
        values = set(list_distinct_user_sdwt_prod_values())
        values.update(
            UserCurrentAffiliation.objects.select_related("affiliation")
            .filter(affiliation__is_active=True)
            .exclude(affiliation__user_sdwt_prod__isnull=True)
            .exclude(affiliation__user_sdwt_prod="")
            .values_list("affiliation__user_sdwt_prod", flat=True)
            .distinct()
        )
        return _collapse_user_sdwt_prod_values(values)

    # -----------------------------------------------------------------------------
    # 3) 접근 권한 및 본인 소속 포함
    # -----------------------------------------------------------------------------
    values = set(
        UserSdwtProdAccess.objects.filter(
            user=user,
            affiliation__is_active=True,
        ).values_list(
            "affiliation__user_sdwt_prod",
            flat=True,
        )
    )

    user_sdwt_prod = get_current_user_sdwt_prod(user=user)
    if isinstance(user_sdwt_prod, str) and user_sdwt_prod.strip():
        values.add(user_sdwt_prod)
    # -----------------------------------------------------------------------------
    # 4) 최종 정제 및 반환
    # -----------------------------------------------------------------------------
    return _collapse_user_sdwt_prod_values(values)


def get_accessible_user_sdwt_prod_roles_for_user(user: Any) -> dict[str, str]:
    """사용자가 접근 가능한 소속별 viewer/member/manager 역할을 반환합니다.

    현재 소속은 명시 권한이 없을 때 member로 간주하며, 슈퍼유저는 모든 활성
    소속을 manager 역할로 조회합니다. 외부 도메인은 이 함수의 결과만 사용하고
    account 모델을 직접 조회하지 않습니다.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return {}

    if getattr(user, "is_superuser", False):
        return {
            value: UserSdwtProdAccess.Roles.MANAGER
            for value in sorted(list_distinct_user_sdwt_prod_values(), key=str.casefold)
        }

    role_priority = {
        UserSdwtProdAccess.Roles.VIEWER: 1,
        UserSdwtProdAccess.Roles.MEMBER: 2,
        UserSdwtProdAccess.Roles.MANAGER: 3,
    }
    roles_by_lookup: dict[str, tuple[str, str]] = {}
    rows = (
        UserSdwtProdAccess.objects.filter(user=user, affiliation__is_active=True)
        .select_related("affiliation")
        .order_by("affiliation__user_sdwt_prod", "id")
    )
    for row in rows:
        value = _normalize_user_sdwt_prod(row.affiliation.user_sdwt_prod)
        lookup = value.casefold() if value else ""
        if not lookup:
            continue
        previous = roles_by_lookup.get(lookup)
        if previous is None or role_priority[row.role] > role_priority[previous[1]]:
            roles_by_lookup[lookup] = (value, row.role)

    current = get_current_user_sdwt_prod(user=user)
    current_value = _normalize_user_sdwt_prod(current)
    current_lookup = current_value.casefold() if current_value else ""
    if current_lookup:
        explicit = roles_by_lookup.get(current_lookup)
        effective_role = (
            UserSdwtProdAccess.Roles.MANAGER
            if explicit and explicit[1] == UserSdwtProdAccess.Roles.MANAGER
            else UserSdwtProdAccess.Roles.MEMBER
        )
        roles_by_lookup[current_lookup] = (current_value, effective_role)

    return {
        value: role
        for value, role in sorted(roles_by_lookup.values(), key=lambda item: item[0].casefold())
    }


def get_active_affiliation_by_user_sdwt_prod(*, user_sdwt_prod: str) -> Affiliation | None:
    """정규화된 user_sdwt_prod와 일치하는 활성 소속을 반환합니다."""

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return None
    return (
        Affiliation.objects.filter(
            is_active=True,
            user_sdwt_prod__iexact=normalized,
        )
        .order_by("id")
        .first()
    )


def list_distinct_user_sdwt_prod_values() -> set[str]:
    """시스템에 등록된 user_sdwt_prod 값 집합을 조회합니다.

    입력:
    - 없음

    반환:
    - set[str]: 중복 제거된 user_sdwt_prod 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    affiliation_values = set(
        Affiliation.objects.filter(is_active=True)
        .exclude(user_sdwt_prod="")
        .values_list("user_sdwt_prod", flat=True)
        .distinct()
    )
    access_values = set(
        UserSdwtProdAccess.objects.filter(affiliation__is_active=True)
        .exclude(affiliation__user_sdwt_prod="")
        .values_list("affiliation__user_sdwt_prod", flat=True)
        .distinct()
    )

    combined = affiliation_values | access_values
    return _collapse_user_sdwt_prod_values(combined)


def list_affiliation_options() -> list[dict[str, object]]:
    """소속 선택 옵션(부서/라인/user_sdwt_prod) 전체를 조회합니다.

    입력:
    - 없음

    반환:
    - list[dict[str, str]]: 소속 옵션 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return list(
        Affiliation.objects.filter(is_active=True)
        .order_by("department", "line", "user_sdwt_prod")
        .values("id", "department", "line", "user_sdwt_prod")
    )


def affiliation_exists_for_user_sdwt_prod(*, user_sdwt_prod: str) -> bool:
    """user_sdwt_prod에 대응하는 Affiliation 존재 여부를 확인합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - bool: 존재 여부

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized = _normalize_text(user_sdwt_prod)
    if not normalized:
        return False

    return Affiliation.objects.filter(
        is_active=True,
        user_sdwt_prod__iexact=normalized,
    ).exists()


def list_active_user_emails_by_user_sdwt_prod(*, user_sdwt_prod: str) -> list[str]:
    """user_sdwt_prod에 대응하는 활성 사용자 이메일 목록을 조회합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - list[str]: 이메일 주소 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return _list_active_user_contact_values_by_user_sdwt_prod(
        user_sdwt_prod=user_sdwt_prod,
        contact_field="email",
    )


def list_effective_affiliation_member_role_users(
    *, user_sdwt_prod: str
) -> list[dict[str, object]]:
    """소속에 유효한 활성 사용자 ID·이메일·최종 역할을 반환합니다.

    현재 소속 사용자는 최소 member로 취급하고, 명시적으로 부여된
    ``UserSdwtProdAccess`` 역할이 더 높으면 그 역할을 사용합니다. 다른 소속
    사용자에게 부여된 명시 권한도 포함하므로 외부 시스템은 이 결과만으로
    소속별 접근 projection을 구성할 수 있습니다.
    """

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return []
    affiliation = (
        Affiliation.objects.filter(
            user_sdwt_prod__iexact=normalized,
            is_active=True,
        )
        .order_by("id")
        .first()
    )
    if affiliation is None:
        return []

    role_priority = {
        UserSdwtProdAccess.Roles.VIEWER: 1,
        UserSdwtProdAccess.Roles.MEMBER: 2,
        UserSdwtProdAccess.Roles.MANAGER: 3,
    }
    roles_by_user_id: dict[int, tuple[str, str]] = {}
    User = get_user_model()
    current_rows = (
        User.objects.filter(
            current_affiliation__affiliation=affiliation,
            is_active=True,
        )
        .exclude(email__isnull=True)
        .exclude(email="")
        .values_list("id", "email")
    )
    for user_id, email in current_rows:
        normalized_email = (_normalize_text(email) or "").lower()
        if normalized_email:
            roles_by_user_id[user_id] = (
                normalized_email,
                UserSdwtProdAccess.Roles.MEMBER,
            )

    access_rows = (
        UserSdwtProdAccess.objects.filter(
            affiliation=affiliation,
            user__is_active=True,
        )
        .exclude(user__email__isnull=True)
        .exclude(user__email="")
        .values_list("user_id", "user__email", "role")
    )
    for user_id, email, role in access_rows:
        normalized_email = (_normalize_text(email) or "").lower()
        if not normalized_email or role not in role_priority:
            continue
        previous = roles_by_user_id.get(user_id)
        if previous is None or role_priority[role] > role_priority[previous[1]]:
            roles_by_user_id[user_id] = (normalized_email, role)

    return [
        {"user_id": user_id, "email": email, "role": role}
        for user_id, (email, role) in sorted(
            roles_by_user_id.items(),
            key=lambda item: (item[1][0], item[0]),
        )
    ]


def get_current_affiliation_id_by_record_id(*, record_id: int) -> int | None:
    """현재 소속 레코드 ID에 연결된 소속 ID를 반환합니다."""

    return (
        UserCurrentAffiliation.objects.filter(id=record_id)
        .values_list("affiliation_id", flat=True)
        .first()
    )


def get_access_affiliation_id_by_record_id(*, record_id: int) -> int | None:
    """명시 소속 권한 레코드 ID에 연결된 소속 ID를 반환합니다."""

    return (
        UserSdwtProdAccess.objects.filter(id=record_id)
        .values_list("affiliation_id", flat=True)
        .first()
    )


def list_affiliation_ids_for_user_id(*, user_id: int) -> set[int]:
    """사용자의 현재·역할·앱별 grant 소속 ID를 활성 여부와 무관하게 반환합니다."""

    if not isinstance(user_id, int) or user_id <= 0:
        return set()
    affiliation_ids = set(
        UserCurrentAffiliation.objects.filter(user_id=user_id).values_list(
            "affiliation_id", flat=True
        )
    )
    affiliation_ids.update(
        UserSdwtProdAccess.objects.filter(user_id=user_id).values_list(
            "affiliation_id", flat=True
        )
    )
    affiliation_ids.update(
        UserScopeAffiliationGrant.objects.filter(user_id=user_id).values_list(
            "affiliation_id", flat=True
        )
    )
    return {value for value in affiliation_ids if isinstance(value, int)}


def get_user_access_sync_state(*, user_id: int) -> dict[str, object] | None:
    """사용자 저장 전후 권한 동기화 비교에 필요한 최소 상태를 반환합니다."""

    User = get_user_model()
    values = User.objects.filter(id=user_id).values(
        "email",
        "is_active",
        "is_superuser",
        "department",
    ).first()
    if values is None:
        return None
    return {
        "email": (_normalize_text(values.get("email")) or "").lower(),
        "is_active": bool(values.get("is_active")),
        "is_superuser": bool(values.get("is_superuser")),
        "department": _normalize_text(values.get("department")) or "",
        "affiliation_ids": list_affiliation_ids_for_user_id(user_id=user_id),
    }


def list_active_user_knox_ids_by_user_sdwt_prod(*, user_sdwt_prod: str) -> list[str]:
    """user_sdwt_prod에 대응하는 활성 사용자 knox_id 목록을 조회합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - list[str]: knox_id 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return _list_active_user_contact_values_by_user_sdwt_prod(
        user_sdwt_prod=user_sdwt_prod,
        contact_field="knox_id",
    )


def list_active_user_ids_by_ids(*, user_ids: Iterable[int]) -> set[int]:
    """활성 사용자 id 집합을 조회합니다.

    입력:
    - user_ids: 검증할 사용자 id 목록

    반환:
    - set[int]: 실제 존재하는 활성 사용자 id 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized_ids = _normalize_positive_int_set(user_ids)
    if not normalized_ids:
        return set()

    User = get_user_model()
    return set(
        User.objects.filter(id__in=normalized_ids, is_active=True).values_list("id", flat=True)
    )


def list_active_acl_projection_users(*, user_ids: Iterable[int]) -> list[Any]:
    """지정 사용자와 이메일이 있는 활성 superuser를 ACL 투영 형태로 반환합니다.

    Portal superuser는 launcher에서 모든 소속을 관리하므로 개별 소속 구성원이
    아니어도 외부 document ACL 계산 대상에 포함합니다.
    """

    normalized_ids = _normalize_positive_int_set(user_ids, allow_cast=True)
    User = get_user_model()
    return list(
        User.objects.filter(
            Q(id__in=normalized_ids) | Q(is_superuser=True),
            is_active=True,
        )
        .exclude(email__isnull=True)
        .exclude(email="")
        .select_related("current_affiliation__affiliation")
        .annotate(_access_department=_resolved_access_department_expression())
        .order_by("id")
    )


def list_active_user_ids_with_contact_by_ids(*, user_ids: Iterable[int], contact_field: str) -> set[int]:
    """활성 사용자 중 지정 연락처 값이 있는 사용자 id 집합을 조회합니다.

    입력:
    - user_ids: 검증할 사용자 id 목록
    - contact_field: email 또는 knox_id

    반환:
    - set[int]: 연락처 값이 있는 활성 사용자 id 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - ValueError: 지원하지 않는 연락처 필드일 때
    """

    if contact_field not in {"email", "knox_id"}:
        raise ValueError("contact_field must be email or knox_id")
    normalized_ids = _normalize_positive_int_set(user_ids)
    if not normalized_ids:
        return set()

    User = get_user_model()
    rows = (
        User.objects.filter(id__in=normalized_ids, is_active=True)
        .exclude(**{f"{contact_field}__isnull": True})
        .values("id", contact_field)
    )
    valid_ids: set[int] = set()
    for row in rows:
        value = row.get(contact_field)
        if isinstance(value, str) and value.strip():
            valid_ids.add(int(row["id"]))
    return valid_ids


def list_distinct_active_user_sdwt_prod_values(
    *,
    include_external_snapshots: bool = False,
    department: str = "",
) -> list[str]:
    """활성 사용자 pool에 존재하는 user_sdwt_prod 목록을 반환합니다.

    입력:
    - include_external_snapshots: 외부 소속 스냅샷의 예측 소속 포함 여부
    - department: 특정 department로 소속 목록을 좁힐 값

    반환:
    - list[str]: 정렬된 user_sdwt_prod 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 활성 사용자에서 소속 값 수집
    # -----------------------------------------------------------------------------
    User = get_user_model()
    normalized_department = _normalize_text(department) or ""
    queryset = (
        User.objects.filter(
            is_active=True,
            current_affiliation__affiliation__is_active=True,
        )
        .exclude(current_affiliation__affiliation__user_sdwt_prod__isnull=True)
        .exclude(current_affiliation__affiliation__user_sdwt_prod__exact="")
    )
    if normalized_department:
        queryset = queryset.filter(
            current_affiliation__affiliation__department__iexact=normalized_department
        )
    values = (
        queryset.values_list("current_affiliation__affiliation__user_sdwt_prod", flat=True)
        .order_by("current_affiliation__affiliation__user_sdwt_prod")
        .distinct()
    )

    # -----------------------------------------------------------------------------
    # 2) 공백 제거 및 대소문자 비구분 중복 제거
    # -----------------------------------------------------------------------------
    collapsed_values = set(_collapse_user_sdwt_prod_values(values))
    if include_external_snapshots:
        external_queryset = ExternalAffiliationSnapshot.objects.exclude(
            predicted_user_sdwt_prod__exact=""
        )
        if normalized_department:
            external_queryset = external_queryset.filter(department__iexact=normalized_department)
        external_values = external_queryset.values_list("predicted_user_sdwt_prod", flat=True)
        collapsed_values.update(_collapse_user_sdwt_prod_values(external_values))
    return sorted(collapsed_values)


def list_distinct_active_departments(*, include_external_snapshots: bool = False) -> list[str]:
    """활성 사용자/외부 스냅샷의 department 목록을 조회합니다."""

    User = get_user_model()
    values = (
        User.objects.filter(
            is_active=True,
            current_affiliation__affiliation__is_active=True,
        )
        .exclude(current_affiliation__affiliation__department__isnull=True)
        .exclude(current_affiliation__affiliation__department__exact="")
        .values_list("current_affiliation__affiliation__department", flat=True)
        .order_by("current_affiliation__affiliation__department")
        .distinct()
    )
    collapsed_values = set(_collapse_text_values(values))
    if include_external_snapshots:
        external_values = (
            ExternalAffiliationSnapshot.objects.exclude(department__isnull=True)
            .exclude(department__exact="")
            .values_list("department", flat=True)
        )
        collapsed_values.update(_collapse_text_values(external_values))
    return sorted(collapsed_values)


def _build_external_snapshot_email(*, knox_id: str) -> str:
    """외부 스냅샷 사용자의 표준 Samsung 메일 주소를 생성합니다."""

    return f"{knox_id}@samsung.com"


def _list_active_user_knox_lookup_keys() -> set[str]:
    """활성 account_user의 knox_id lookup key 집합을 반환합니다."""

    User = get_user_model()
    return {
        str(value or "").strip().lower()
        for value in (
            User.objects.filter(is_active=True)
            .exclude(knox_id__isnull=True)
            .exclude(knox_id__exact="")
            .annotate(knox_lookup=Lower("knox_id"))
            .values_list("knox_lookup", flat=True)
        )
        if str(value or "").strip()
    }


def get_active_users_by_knox_lookup_keys(*, knox_ids: list[str]) -> dict[str, Any]:
    """입력 knox_id 중 활성 account_user 매핑을 lookup key 기준으로 반환합니다."""

    lookup_keys = sorted({value.lower() for value in _normalize_text_list(knox_ids)})
    if not lookup_keys:
        return {}

    User = get_user_model()
    rows = (
        User.objects.filter(is_active=True)
        .exclude(knox_id__isnull=True)
        .exclude(knox_id__exact="")
        .annotate(knox_lookup=Lower("knox_id"))
        .filter(knox_lookup__in=lookup_keys)
        .order_by("knox_lookup", "id")
    )
    users: dict[str, Any] = {}
    for user in rows:
        lookup_key = str(getattr(user, "knox_id", "") or "").strip().lower()
        if lookup_key and lookup_key not in users:
            users[lookup_key] = user
    return users


def _list_external_affiliation_pool(
    *,
    search: str = "",
    department: str = "",
    user_sdwt_prod: str = "",
    limit: int | None = 50,
) -> list[dict[str, object]]:
    """수신인 선택 UI에 표시할 미가입 외부 스냅샷 사용자 목록을 조회합니다."""

    safe_limit = None if limit is None else max(1, min(int(limit or 50), 500))
    normalized_search = _normalize_text(search) or ""
    normalized_department = _normalize_text(department) or ""
    normalized_user_sdwt = _normalize_text(user_sdwt_prod) or ""
    active_knox_lookup_keys = _list_active_user_knox_lookup_keys()

    queryset = ExternalAffiliationSnapshot.objects.all()
    if normalized_department:
        queryset = queryset.filter(department__iexact=normalized_department)
    if normalized_user_sdwt:
        queryset = queryset.filter(predicted_user_sdwt_prod__iexact=normalized_user_sdwt)
    if normalized_search:
        queryset = queryset.filter(
            Q(knox_id__icontains=normalized_search)
            | Q(username__icontains=normalized_search)
            | Q(department__icontains=normalized_search)
            | Q(predicted_user_sdwt_prod__icontains=normalized_search)
        )

    rows = queryset.order_by("predicted_user_sdwt_prod", "username", "knox_id")
    if safe_limit is not None:
        rows = rows[:safe_limit]

    results: list[dict[str, object]] = []
    for snapshot in rows:
        knox_id = _normalize_text(snapshot.knox_id) or ""
        knox_lookup_key = knox_id.lower()
        if not knox_id or knox_lookup_key in active_knox_lookup_keys:
            continue
        recipient_key = f"external:{knox_lookup_key}"
        results.append(
            {
                "id": recipient_key,
                "userId": None,
                "recipientType": "external",
                "recipientKey": recipient_key,
                "externalKnoxId": knox_id,
                "username": snapshot.username or "",
                "displayName": snapshot.username or knox_id,
                "sabun": "",
                "knoxId": knox_id,
                "email": _build_external_snapshot_email(knox_id=knox_id),
                "department": snapshot.department or "",
                "line": "",
                "userSdwtProd": snapshot.predicted_user_sdwt_prod or "",
            }
        )
    return results


def list_active_user_pool(
    *,
    search: str = "",
    department: str = "",
    user_sdwt_prod: str = "",
    contact_field: str = "",
    limit: int | None = 50,
    include_external_snapshots: bool = False,
) -> list[dict[str, object]]:
    """수신인 선택 UI에서 사용할 활성 사용자 pool을 조회합니다.

    입력:
    - search: 이름/사번/knox_id/email 검색어
    - department: 특정 department 필터
    - user_sdwt_prod: 특정 소속 필터
    - contact_field: email 또는 knox_id 보유 사용자 필터
    - limit: 최대 반환 개수(None이면 제한 없음)
    - include_external_snapshots: 미가입 외부 스냅샷 사용자 포함 여부

    반환:
    - list[dict[str, object]]: 사용자 선택 옵션 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 사용자 queryset 구성
    # -----------------------------------------------------------------------------
    safe_limit = None if limit is None else max(1, min(int(limit or 50), 500))
    normalized_search = _normalize_text(search) or ""
    normalized_department = _normalize_text(department) or ""
    normalized_user_sdwt = _normalize_text(user_sdwt_prod) or ""
    normalized_contact_field = _normalize_text(contact_field) or ""

    User = get_user_model()
    queryset = User.objects.filter(is_active=True).select_related(
        "current_affiliation__affiliation"
    )
    if normalized_user_sdwt:
        queryset = queryset.filter(
            current_affiliation__affiliation__is_active=True,
            current_affiliation__affiliation__user_sdwt_prod__iexact=normalized_user_sdwt
        )
    if normalized_department:
        queryset = queryset.filter(
            current_affiliation__affiliation__is_active=True,
            current_affiliation__affiliation__department__iexact=normalized_department
        )
    if normalized_contact_field in {"email", "knox_id"}:
        queryset = queryset.exclude(**{f"{normalized_contact_field}__isnull": True}).exclude(
            **{f"{normalized_contact_field}__exact": ""}
        )

    # -----------------------------------------------------------------------------
    # 2) 검색어 필터 적용
    # -----------------------------------------------------------------------------
    if normalized_search:
        queryset = queryset.filter(
            Q(username__icontains=normalized_search)
            | Q(username_en__icontains=normalized_search)
            | Q(givenname__icontains=normalized_search)
            | Q(surname__icontains=normalized_search)
            | Q(sabun__icontains=normalized_search)
            | Q(knox_id__icontains=normalized_search)
            | Q(email__icontains=normalized_search)
            | Q(current_affiliation__affiliation__user_sdwt_prod__icontains=normalized_search)
        )

    rows = queryset.order_by(
        "current_affiliation__affiliation__user_sdwt_prod",
        "username",
        "id",
    )
    if safe_limit is not None:
        rows = rows[:safe_limit]

    # -----------------------------------------------------------------------------
    # 3) 프론트엔드 선택 옵션 형태로 직렬화
    # -----------------------------------------------------------------------------
    results: list[dict[str, object]] = []
    for user in rows:
        affiliation = getattr(
            getattr(user, "current_affiliation", None),
            "affiliation",
            None,
        )
        if affiliation is not None and not affiliation.is_active:
            affiliation = None
        display_name = (
            getattr(user, "username", None)
            or getattr(user, "username_en", None)
            or getattr(user, "givenname", None)
            or getattr(user, "knox_id", None)
            or getattr(user, "sabun", None)
            or ""
        )
        results.append(
            {
                "id": user.id,
                "userId": user.id,
                "recipientType": "user",
                "recipientKey": f"user:{user.id}",
                "username": getattr(user, "username", None) or "",
                "displayName": display_name,
                "sabun": getattr(user, "sabun", None) or "",
                "knoxId": getattr(user, "knox_id", None) or "",
                "email": getattr(user, "email", None) or "",
                "department": getattr(affiliation, "department", "") or "",
                "line": getattr(affiliation, "line", "") or "",
                "userSdwtProd": getattr(affiliation, "user_sdwt_prod", "") or "",
            }
        )
    if include_external_snapshots:
        results.extend(
            _list_external_affiliation_pool(
                search=normalized_search,
                department=normalized_department,
                user_sdwt_prod=normalized_user_sdwt,
                limit=limit,
            )
        )
        results = sorted(
            results,
            key=lambda item: (
                str(item.get("userSdwtProd") or "").casefold(),
                str(item.get("displayName") or item.get("knoxId") or "").casefold(),
                str(item.get("recipientKey") or "").casefold(),
            ),
        )
        if safe_limit is not None:
            results = results[:safe_limit]
    return results


def list_user_sdwt_prod_access_rows(*, user: Any) -> list[UserSdwtProdAccess]:
    """사용자의 접근 권한(UserSdwtProdAccess) 행 목록을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - list[UserSdwtProdAccess]: 접근 권한 행 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return list(
        UserSdwtProdAccess.objects.filter(
            user=user,
            affiliation__is_active=True,
        )
        .select_related("affiliation", "user", "granted_by")
        .order_by("affiliation__user_sdwt_prod", "id")
    )


def get_access_scope_by_key(*, scope_key: str) -> AccessScope | None:
    """scope key로 접근 권한 대상을 조회합니다."""

    normalized = _normalize_text(scope_key)
    if not normalized:
        return None
    return AccessScope.objects.filter(key=normalized).first()


def get_access_scope_key_by_id(*, scope_id: int) -> str | None:
    """접근 변경 signal이 사용할 scope key를 ID로 반환합니다."""

    if not isinstance(scope_id, int) or scope_id <= 0:
        return None
    return AccessScope.objects.filter(id=scope_id).values_list("key", flat=True).first()


def get_user_access_signal_state(*, record_id: int) -> dict[str, object] | None:
    """UserAccess 저장 전 사용자와 scope 식별 상태를 반환합니다."""

    values = (
        UserAccess.objects.filter(id=record_id)
        .values("user_id", "scope__key")
        .first()
    )
    if values is None:
        return None
    return {
        "user_id": values["user_id"],
        "scope_key": values["scope__key"],
    }


def get_scope_affiliation_grant_signal_state(
    *, record_id: int
) -> dict[str, object] | None:
    """앱별 소속 grant 저장 전 scope와 소속 식별 상태를 반환합니다."""

    values = (
        UserScopeAffiliationGrant.objects.filter(id=record_id)
        .values("scope__key", "affiliation_id")
        .first()
    )
    if values is None:
        return None
    return {
        "scope_key": values["scope__key"],
        "affiliation_id": values["affiliation_id"],
    }


def get_access_policy_scope_key_by_record_id(*, record_id: int) -> str | None:
    """접근 정책 저장 전 연결된 scope key를 반환합니다."""

    return (
        AccessPolicyRule.objects.filter(id=record_id)
        .values_list("scope__key", flat=True)
        .first()
    )


def get_access_scope_by_key_for_update(*, scope_key: str) -> AccessScope | None:
    """트랜잭션 안에서 scope 행을 잠가 조회합니다."""

    normalized = _normalize_text(scope_key)
    if not normalized:
        return None
    return AccessScope.objects.select_for_update().filter(key=normalized).first()


def list_access_scopes() -> list[AccessScope]:
    """역할 판정에 사용할 전체 접근 scope를 안정적인 순서로 반환합니다."""

    return list(AccessScope.objects.all().order_by("id"))


def list_active_app_access_scopes() -> list[AccessScope]:
    """Portal 일괄 부여 대상인 활성 앱 scope를 반환합니다."""

    return list(
        AccessScope.objects.filter(
            scope_type=AccessScope.ScopeTypes.APP,
            is_active=True,
        ).order_by("name", "key")
    )


def list_managed_access_scopes() -> list[AccessScope]:
    """권한 매트릭스에 표시할 Portal과 모든 활성 하위 scope를 반환합니다."""

    scopes = list(
        AccessScope.objects.filter(
            Q(key=ACCESS_SCOPE_PORTAL) | Q(is_active=True),
        ).order_by("name", "key")
    )
    return sorted(
        scopes,
        key=lambda scope: (
            scope.key != ACCESS_SCOPE_PORTAL,
            scope.name,
            scope.key,
        ),
    )


def list_active_access_policy_rules(
    *,
    scope: AccessScope,
    department: str | None = None,
) -> list[AccessPolicyRule]:
    """scope의 활성 정책과 PostgreSQL 정규화 값을 반환합니다."""

    return list(
        _active_access_policy_queryset(department=department)
        .filter(scope=scope)
        .select_related("scope")
        .order_by("rule_type", "id")
    )


def list_active_access_policy_rules_for_scopes(
    *,
    scopes: list[AccessScope],
    department: str | None = None,
) -> list[AccessPolicyRule]:
    """여러 scope의 활성 정책과 PostgreSQL 정규화 값을 한 번에 반환합니다."""

    scope_ids = [scope.id for scope in scopes]
    if not scope_ids:
        return []
    return list(
        _active_access_policy_queryset(department=department)
        .filter(scope_id__in=scope_ids)
        .select_related("scope")
        .order_by("scope_id", "rule_type", "id")
    )


def get_user_access_for_scope(*, user: Any, scope: AccessScope) -> UserAccess | None:
    """사용자의 scope별 접근 상태 행을 조회합니다."""

    if not user or scope is None:
        return None

    return (
        UserAccess.objects.filter(user=user, scope=scope)
        .select_related("scope", "user", "decided_by")
        .order_by("id")
        .first()
    )


def get_user_access_for_scope_for_update(*, user: Any, scope: AccessScope) -> UserAccess | None:
    """트랜잭션 안에서 사용자의 scope 접근 행을 잠가 조회합니다."""

    if not user or scope is None:
        return None

    return (
        UserAccess.objects.select_for_update(of=("self",))
        .filter(user=user, scope=scope)
        .select_related("scope", "user", "decided_by")
        .first()
    )


def list_active_scope_affiliation_grants(
    *,
    user: Any,
    scope: AccessScope,
) -> list[UserScopeAffiliationGrant]:
    """사용자와 앱 scope의 활성·미만료 소속 데이터 grant를 반환합니다."""

    if not user or scope is None:
        return []
    now = timezone.now()
    return list(
        UserScopeAffiliationGrant.objects.filter(
            user=user,
            scope=scope,
            is_active=True,
            affiliation__is_active=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .select_related("scope", "affiliation", "granted_by")
        .order_by("affiliation__user_sdwt_prod", "id")
    )


def list_active_scope_affiliation_grant_user_ids(
    *,
    scope: AccessScope,
    affiliation_id: int,
    user_ids: Iterable[int],
) -> set[int]:
    """여러 사용자 중 지정 scope·소속의 활성·미만료 grant 사용자 ID를 반환합니다."""

    normalized_user_ids = _normalize_positive_int_set(user_ids)
    if (
        scope is None
        or not isinstance(affiliation_id, int)
        or affiliation_id <= 0
        or not normalized_user_ids
    ):
        return set()
    now = timezone.now()
    return set(
        UserScopeAffiliationGrant.objects.filter(
            user_id__in=normalized_user_ids,
            scope=scope,
            affiliation_id=affiliation_id,
            affiliation__is_active=True,
            is_active=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .values_list("user_id", flat=True)
    )


def list_expired_scope_affiliation_grants_for_update(
    *,
    scope: AccessScope,
    expired_at: Any,
    limit: int,
) -> list[UserScopeAffiliationGrant]:
    """지정 scope의 활성 만료 grant를 잠가 제한된 수만 반환합니다."""

    if scope is None or limit <= 0:
        return []
    return list(
        UserScopeAffiliationGrant.objects.select_for_update(skip_locked=True)
        .filter(
            scope=scope,
            is_active=True,
            expires_at__isnull=False,
            expires_at__lte=expired_at,
        )
        .select_related("scope", "affiliation", "user")
        .order_by("expires_at", "id")[:limit]
    )


def list_scope_affiliation_grants_for_update(
    *,
    user: Any,
    scope: AccessScope,
) -> list[UserScopeAffiliationGrant]:
    """트랜잭션 안에서 사용자와 앱 scope의 모든 소속 grant를 잠가 반환합니다."""

    if not user or scope is None:
        return []
    return list(
        UserScopeAffiliationGrant.objects.select_for_update(of=("self",))
        .filter(user=user, scope=scope)
        .select_related("scope", "affiliation", "granted_by")
        .order_by("affiliation_id", "id")
    )


def list_active_affiliations_by_ids(*, affiliation_ids: Iterable[int]) -> list[Affiliation]:
    """활성 소속을 요청 ID 순서와 무관하게 안정된 표시 순서로 반환합니다."""

    normalized_ids = _normalize_positive_int_set(affiliation_ids)
    if not normalized_ids:
        return []
    return list(
        Affiliation.objects.filter(id__in=normalized_ids, is_active=True).order_by(
            "department",
            "line",
            "user_sdwt_prod",
            "id",
        )
    )


def list_active_affiliations_by_ids_for_update(
    *,
    affiliation_ids: Iterable[int],
) -> list[Affiliation]:
    """트랜잭션 안에서 선택한 활성 소속 행을 잠가 안정된 순서로 반환합니다."""

    normalized_ids = _normalize_positive_int_set(affiliation_ids)
    if not normalized_ids:
        return []
    return list(
        Affiliation.objects.select_for_update(of=("self",))
        .filter(id__in=normalized_ids, is_active=True)
        .order_by("id")
    )


def list_affiliations_by_ids_for_update(
    *,
    affiliation_ids: Iterable[int],
) -> list[Affiliation]:
    """활성 상태와 무관하게 선택 소속을 id 오름차순으로 잠가 반환합니다."""

    normalized_ids = _normalize_positive_int_set(affiliation_ids)
    if not normalized_ids:
        return []
    return list(
        Affiliation.objects.select_for_update(of=("self",))
        .filter(id__in=normalized_ids)
        .order_by("id")
    )


def get_affiliation_by_id_for_update(*, affiliation_id: int) -> Affiliation | None:
    """트랜잭션 안에서 활성 상태와 무관하게 소속 한 건을 잠가 반환합니다."""

    if type(affiliation_id) is not int or affiliation_id <= 0:
        return None
    return (
        Affiliation.objects.select_for_update(of=("self",))
        .filter(id=affiliation_id)
        .first()
    )


def list_active_affiliations_by_user_sdwt_prods_for_update(
    *,
    user_sdwt_prods: Iterable[str],
) -> list[Affiliation]:
    """여러 활성 소속을 정규 식별자로 조회해 id 오름차순으로 잠급니다."""

    lookup_keys = list(_build_user_sdwt_display_map(user_sdwt_prods).keys())
    if not lookup_keys:
        return []
    return list(
        Affiliation.objects.select_for_update(of=("self",))
        .annotate(user_sdwt_prod_lookup=Lower(Trim("user_sdwt_prod")))
        .filter(
            is_active=True,
            user_sdwt_prod_lookup__in=lookup_keys,
        )
        .order_by("id")
    )


def list_active_affiliations() -> list[Affiliation]:
    """전체 활성 소속을 안정된 표시 순서로 반환합니다."""

    return list(
        Affiliation.objects.filter(is_active=True).order_by(
            "department",
            "line",
            "user_sdwt_prod",
            "id",
        )
    )


def list_user_access_rows_for_scopes_and_users(
    *,
    scopes: list[AccessScope],
    user_ids: list[int],
) -> list[UserAccess]:
    """여러 앱 scope와 사용자에 해당하는 명시 권한 행을 한 번에 반환합니다."""

    scope_ids = [scope.id for scope in scopes]
    if not scope_ids or not user_ids:
        return []
    return list(
        UserAccess.objects.filter(scope_id__in=scope_ids, user_id__in=user_ids)
        .select_related("scope", "user", "decided_by")
        .order_by("scope_id", "user_id", "id")
    )


def list_access_management_users(
    *,
    search: str | None,
    department: str | None,
    manual_grant_scope_ids: Iterable[int] | None = None,
) -> QuerySet[Any]:
    """접근 권한 관리 화면에 표시할 활성 사용자를 조건별로 조회합니다."""

    User = get_user_model()
    queryset = (
        User.objects.filter(is_active=True)
        .select_related("current_affiliation__affiliation")
        .annotate(_access_department=_resolved_access_department_expression())
    )

    normalized_department = _normalize_text(department)
    if normalized_department:
        queryset = queryset.filter(
            _access_department=Lower(
                Trim(Value(normalized_department, output_field=CharField()))
            )
        )

    normalized_search = _normalize_text(search)
    if normalized_search:
        queryset = queryset.filter(
            Q(username__icontains=normalized_search)
            | Q(username_en__icontains=normalized_search)
            | Q(givenname__icontains=normalized_search)
            | Q(surname__icontains=normalized_search)
            | Q(sabun__icontains=normalized_search)
            | Q(knox_id__icontains=normalized_search)
            | Q(email__icontains=normalized_search)
            | Q(department__icontains=normalized_search)
            | Q(current_affiliation__affiliation__department__icontains=normalized_search)
            | Q(current_affiliation__affiliation__line__icontains=normalized_search)
            | Q(current_affiliation__affiliation__user_sdwt_prod__icontains=normalized_search)
        )

    if manual_grant_scope_ids is not None:
        scope_ids = _normalize_positive_int_set(manual_grant_scope_ids)
        if not scope_ids:
            return queryset.none()
        queryset = queryset.filter(
            access_grants__scope_id__in=scope_ids,
            access_grants__status=UserAccess.Status.ALLOWED,
        ).distinct()

    return queryset.order_by("department", "username", "knox_id", "id")


def filter_access_management_users_by_effective_access(
    *,
    queryset: QuerySet[Any],
    scope: AccessScope,
    status: str | None,
    source: str | None,
) -> QuerySet[Any]:
    """최종 Portal 선행 조건까지 포함한 접근 필터를 DB에서 적용합니다."""

    normalized_status = (_normalize_text(status) or "").lower()
    normalized_source = (_normalize_text(source) or "").lower()
    if not normalized_status and not normalized_source:
        return queryset

    scope_access_rows = UserAccess.objects.filter(
        user_id=OuterRef("pk"),
        scope=scope,
    )
    queryset = queryset.annotate(
        _access_scope_status=Subquery(
            scope_access_rows.values("status")[:1],
            output_field=CharField(),
        )
    )

    scope_policy_departments = list(
        _active_access_policy_queryset()
        .filter(
            scope=scope,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
        )
        .values_list("_access_policy_value", flat=True)
    )
    queryset = queryset.annotate(
        _access_department=_resolved_access_department_expression(),
        _access_scope_policy=Case(
            When(
                _access_scope_status__isnull=True,
                _access_department__in=scope_policy_departments,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
    )

    portal_scope = (
        scope
        if scope.key == ACCESS_SCOPE_PORTAL
        else AccessScope.objects.filter(key=ACCESS_SCOPE_PORTAL).first()
    )
    if scope.key == ACCESS_SCOPE_PORTAL:
        portal_allowed_expression = Case(
            When(is_superuser=True, then=Value(True)),
            When(_access_scope_status=UserAccess.Status.ALLOWED, then=Value(True)),
            When(_access_scope_policy=True, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    elif portal_scope is None or not portal_scope.is_active:
        portal_allowed_expression = Case(
            When(is_superuser=True, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    else:
        portal_access_rows = UserAccess.objects.filter(
            user_id=OuterRef("pk"),
            scope=portal_scope,
        )
        portal_policy_departments = list(
            _active_access_policy_queryset()
            .filter(
                scope=portal_scope,
                rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            )
            .values_list("_access_policy_value", flat=True)
        )
        queryset = queryset.annotate(
            _access_portal_status=Subquery(
                portal_access_rows.values("status")[:1],
                output_field=CharField(),
            ),
            _access_portal_policy=Case(
                When(
                    _access_portal_status__isnull=True,
                    _access_department__in=portal_policy_departments,
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        portal_allowed_expression = Case(
            When(is_superuser=True, then=Value(True)),
            When(_access_portal_status=UserAccess.Status.ALLOWED, then=Value(True)),
            When(_access_portal_policy=True, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )

    queryset = queryset.annotate(_access_portal_allowed=portal_allowed_expression)

    status_cases = [When(is_superuser=True, then=Value("allowed"))]
    source_cases = [
        When(is_superuser=True, then=Value(AccessSource.SUPERUSER_BYPASS))
    ]
    if scope.key != ACCESS_SCOPE_PORTAL:
        status_cases.append(
            When(_access_portal_allowed=False, then=Value("denied"))
        )
        source_cases.append(
            When(
                _access_portal_allowed=False,
                then=Value(AccessSource.PORTAL_ACCESS_REQUIRED),
            )
        )
    if not scope.is_active:
        status_cases.append(When(pk__isnull=False, then=Value("inactive")))
        source_cases.append(
            When(pk__isnull=False, then=Value(AccessSource.SCOPE_INACTIVE))
        )
    else:
        status_cases.extend(
            [
                When(
                    _access_scope_status=UserAccess.Status.DENIED,
                    then=Value("denied"),
                ),
                When(
                    _access_scope_status=UserAccess.Status.ALLOWED,
                    then=Value("allowed"),
                ),
                When(
                    _access_scope_status=UserAccess.Status.PENDING,
                    then=Value("pending"),
                ),
                When(_access_scope_policy=True, then=Value("allowed")),
            ]
        )
        source_cases.extend(
            [
                When(
                    _access_scope_status=UserAccess.Status.DENIED,
                    then=Value(AccessSource.EXPLICIT_DENIED),
                ),
                When(
                    _access_scope_status=UserAccess.Status.ALLOWED,
                    then=Value(AccessSource.EXPLICIT_ALLOWED),
                ),
                When(
                    _access_scope_status=UserAccess.Status.PENDING,
                    then=Value(AccessSource.EXPLICIT_PENDING),
                ),
                When(
                    _access_scope_policy=True,
                    then=Value(AccessSource.POLICY_DEPARTMENT),
                ),
            ]
        )

    queryset = queryset.annotate(
        _access_effective_status=Case(
            *status_cases,
            default=Value("not_requested"),
            output_field=CharField(),
        ),
        _access_effective_source=Case(
            *source_cases,
            default=Value(AccessSource.NONE),
            output_field=CharField(),
        ),
    )

    if normalized_status:
        queryset = queryset.filter(_access_effective_status=normalized_status)
    if normalized_source:
        queryset = queryset.filter(_access_effective_source=normalized_source)

    return queryset


def list_user_access_rows_by_scope_and_user_ids(
    *,
    scope: AccessScope,
    user_ids: Iterable[int],
) -> list[UserAccess]:
    """scope와 사용자 id 목록으로 접근 상태 행을 조회합니다."""

    normalized_ids = _normalize_positive_int_set(user_ids, allow_cast=True)
    if not normalized_ids:
        return []

    return list(
        UserAccess.objects.filter(scope=scope, user_id__in=normalized_ids)
        .select_related("scope", "user", "decided_by")
        .order_by("user_id", "id")
    )


def list_pending_access_requests(*, scope_key: str | None) -> QuerySet[UserAccess]:
    """전체 또는 지정 scope의 승인 대기 요청을 최신 요청순으로 반환합니다."""

    queryset = (
        UserAccess.objects.filter(status=UserAccess.Status.PENDING)
        .select_related(
            "scope",
            "user",
            "user__current_affiliation__affiliation",
        )
    )
    normalized_scope_key = _normalize_text(scope_key)
    if normalized_scope_key:
        queryset = queryset.filter(scope__key=normalized_scope_key)
    return queryset.order_by("-requested_at", "-id")


def list_pending_access_request_counts() -> list[dict[str, Any]]:
    """승인 대기 요청 건수를 scope별로 집계합니다."""

    return list(
        UserAccess.objects.filter(status=UserAccess.Status.PENDING)
        .values(
            "scope__key",
            "scope__name",
            "scope__scope_type",
            "scope__is_active",
            "scope__requestable",
        )
        .annotate(total=Count("id"))
        .order_by("scope__name", "scope__key")
    )


def list_user_access_requests_by_ids(*, request_ids: Iterable[int]) -> list[UserAccess]:
    """일괄 결정 대상 UserAccess 행을 요청 ID 기준으로 조회합니다."""

    normalized_ids = _normalize_positive_int_set(request_ids)
    if not normalized_ids:
        return []
    return list(
        UserAccess.objects.filter(id__in=normalized_ids)
        .select_related(
            "scope",
            "user",
            "user__current_affiliation__affiliation",
        )
        .order_by("user_id", "scope_id", "id")
    )


def get_access_policy_rule_by_id_for_update(*, rule_id: int) -> AccessPolicyRule | None:
    """트랜잭션 안에서 ID에 해당하는 정책 규칙 행을 잠가 조회합니다."""

    if not rule_id:
        return None

    return (
        AccessPolicyRule.objects.select_for_update(of=("self",))
        .filter(id=rule_id)
        .select_related("scope")
        .first()
    )


def list_access_scopes_by_keys_for_update(*, scope_keys: list[str]) -> list[AccessScope]:
    """트랜잭션 안에서 요청한 scope를 안정된 순서로 잠가 반환합니다."""

    normalized_keys = sorted(set(_normalize_text_list(scope_keys)))
    return list(
        AccessScope.objects.select_for_update(of=("self",))
        .filter(key__in=normalized_keys)
        .order_by("id")
    )


def list_access_policy_rules_for_scopes_and_value_for_update(
    *,
    scopes: list[AccessScope],
    value: str,
) -> list[AccessPolicyRule]:
    """트랜잭션 안에서 scope별 동일 부서 정책 규칙을 잠가 반환합니다."""

    return list(
        AccessPolicyRule.objects.select_for_update(of=("self",))
        .filter(
            scope__in=scopes,
            rule_type=AccessPolicyRule.RuleTypes.DEPARTMENT,
            value__iexact=value.strip(),
        )
        .select_related("scope")
        .order_by("scope_id", "id")
    )


def list_access_policy_rules(
    *,
    scope_key: str | None,
    managed_only: bool = False,
) -> QuerySet[AccessPolicyRule]:
    """scope 조건에 맞는 접근 정책 규칙 목록을 조회합니다."""

    queryset = AccessPolicyRule.objects.select_related("scope").order_by(
        "scope__key",
        "rule_type",
        "value",
        "id",
    )
    normalized_scope = _normalize_text(scope_key)
    if normalized_scope:
        queryset = queryset.filter(scope__key=normalized_scope)
    if managed_only:
        queryset = queryset.filter(
            Q(scope__key=ACCESS_SCOPE_PORTAL)
            | Q(scope__is_active=True)
        )
    return queryset


def list_access_audit_logs(
    *,
    scope_key: str | None,
    user_id: int | None,
    action: str | None,
) -> QuerySet[AccessAuditLog]:
    """접근 권한 감사 로그 목록을 필터링하여 조회합니다."""

    queryset = AccessAuditLog.objects.select_related(
        "scope",
        "actor",
        "target_user",
        "affiliation",
        "policy_rule",
    ).order_by("-created_at", "-id")
    normalized_scope = _normalize_text(scope_key)
    if normalized_scope:
        queryset = queryset.filter(scope__key=normalized_scope)
    if user_id:
        queryset = queryset.filter(target_user_id=user_id)

    normalized_action = _normalize_text(action)
    if normalized_action:
        queryset = queryset.filter(action=normalized_action)
    return queryset


def list_user_sdwt_prod_changes(
    *, user: Any, limit: int = 50
) -> list[UserSdwtProdChange]:
    """사용자의 user_sdwt_prod 변경 히스토리를 최신순으로 반환합니다.

    입력:
    - user: Django 사용자 객체
    - limit: 최대 반환 개수

    반환:
    - list[UserSdwtProdChange]: 변경 이력 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 유효성 확인
    # -----------------------------------------------------------------------------
    if not user:
        return []

    # -----------------------------------------------------------------------------
    # 2) 조회 개수 보정 및 조회
    # -----------------------------------------------------------------------------
    normalized_limit = max(1, int(limit or 50))
    return list(
        UserSdwtProdChange.objects.filter(user=user)
        .select_related("approved_by", "created_by")
        .order_by("-effective_from", "-id")[:normalized_limit]
    )


def user_has_manage_permission(*, user: Any, user_sdwt_prod: str) -> bool:
    """사용자가 특정 user_sdwt_prod 그룹을 관리할 권한이 있는지 확인합니다.

    입력:
    - user: Django 사용자 객체
    - user_sdwt_prod: 소속 식별자

    반환:
    - bool: 관리 권한 여부

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return False

    return UserSdwtProdAccess.objects.filter(
        user=user,
        affiliation__is_active=True,
        affiliation__user_sdwt_prod__iexact=normalized,
        role=UserSdwtProdAccess.Roles.MANAGER,
    ).exists()


def get_user_by_id_for_update(*, user_id: int) -> Any | None:
    """트랜잭션 안에서 사용자 행과 권한 판정용 관계를 잠가 조회합니다."""

    if not user_id:
        return None

    UserModel = get_user_model()
    return (
        UserModel.objects.select_for_update(of=("self",))
        .select_related("current_affiliation__affiliation")
        .filter(id=user_id)
        .first()
    )


def get_user_by_id(*, user_id: int) -> Any | None:
    """사용자 id로 활성 상태와 무관하게 단일 사용자를 조회합니다."""

    if not user_id:
        return None
    UserModel = get_user_model()
    return (
        UserModel.objects.select_related("current_affiliation__affiliation")
        .filter(id=user_id)
        .first()
    )


def get_user_by_knox_id(*, knox_id: str) -> Any | None:
    """knox_id로 사용자를 조회하고 없으면 None을 반환합니다.

    입력:
    - knox_id: 사용자 knox_id

    반환:
    - Any | None: 사용자 객체 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized_knox_id = _normalize_text(knox_id)
    if not normalized_knox_id:
        return None

    UserModel = get_user_model()
    if not hasattr(UserModel, "knox_id"):
        return None

    return UserModel.objects.filter(knox_id=normalized_knox_id).first()


def get_users_by_knox_ids(*, knox_ids: list[str]) -> dict[str, Any]:
    """knox_id 목록으로 사용자 매핑을 조회합니다.

    입력:
    - knox_ids: knox_id 목록

    반환:
    - dict[str, Any]: knox_id → 사용자 객체 매핑

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized_ids = _normalize_text_list(knox_ids)
    if not normalized_ids:
        return {}

    UserModel = get_user_model()
    if not hasattr(UserModel, "knox_id"):
        return {}

    users = UserModel.objects.filter(knox_id__in=normalized_ids)
    mapped: dict[str, Any] = {}
    for user in users:
        knox_id = getattr(user, "knox_id", None)
        normalized_knox_id = _normalize_text(knox_id)
        if normalized_knox_id:
            mapped[normalized_knox_id] = user
    return mapped


def get_user_sdwt_prod_change_by_id(*, change_id: int) -> UserSdwtProdChange | None:
    """id로 UserSdwtProdChange를 조회하고 없으면 None을 반환합니다.

    입력:
    - change_id: 변경 요청 id

    반환:
    - UserSdwtProdChange | None: 변경 요청 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 변경 요청 조회 시도
    # -----------------------------------------------------------------------------
    try:
        return UserSdwtProdChange.objects.select_related("user").get(id=change_id)
    except UserSdwtProdChange.DoesNotExist:
        # -----------------------------------------------------------------------------
        # 2) 미존재 처리
        # -----------------------------------------------------------------------------
        return None


def get_user_sdwt_prod_change_by_id_for_update(
    *,
    change_id: int,
) -> UserSdwtProdChange | None:
    """트랜잭션 안에서 소속 변경 요청 행을 잠가 조회합니다.

    입력:
    - change_id: 변경 요청 id

    반환:
    - UserSdwtProdChange | None: 잠긴 변경 요청 또는 None

    부작용:
    - 현재 트랜잭션이 끝날 때까지 대상 행에 쓰기 잠금을 유지합니다.

    오류:
    - transaction.atomic() 밖에서 호출하면 데이터베이스가 오류를 반환할 수 있습니다.
    """

    if not change_id:
        return None
    return (
        UserSdwtProdChange.objects.select_for_update(of=("self",))
        .select_related("user")
        .filter(id=change_id)
        .first()
    )


def get_external_affiliation_snapshot_by_knox_id(
    *,
    knox_id: str,
) -> ExternalAffiliationSnapshot | None:
    """knox_id로 외부 예측 소속 스냅샷을 조회합니다.

    입력:
    - knox_id: 사용자 knox_id

    반환:
    - ExternalAffiliationSnapshot | None: 스냅샷 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized_knox_id = _normalize_text(knox_id)
    if not normalized_knox_id:
        return None

    return ExternalAffiliationSnapshot.objects.filter(knox_id=normalized_knox_id).first()


def get_external_affiliation_snapshots_by_knox_ids(
    *,
    knox_ids: list[str],
) -> dict[str, ExternalAffiliationSnapshot]:
    """knox_id 목록으로 외부 예측 소속 스냅샷을 조회해 dict로 반환합니다.

    입력:
    - knox_ids: knox_id 목록

    반환:
    - dict[str, ExternalAffiliationSnapshot]: knox_id → 스냅샷 매핑

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized_ids = _normalize_text_list(knox_ids)
    if not normalized_ids:
        return {}

    return ExternalAffiliationSnapshot.objects.in_bulk(normalized_ids, field_name="knox_id")


def get_external_affiliation_snapshots_by_knox_lookup_keys(
    *,
    knox_ids: list[str],
) -> dict[str, ExternalAffiliationSnapshot]:
    """knox_id 목록을 대소문자 비구분 lookup key 기준으로 조회합니다.

    입력:
    - knox_ids: knox_id 목록

    반환:
    - dict[str, ExternalAffiliationSnapshot]: 소문자 knox_id → 스냅샷 매핑

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    lookup_keys = sorted({value.lower() for value in _normalize_text_list(knox_ids)})
    if not lookup_keys:
        return {}

    snapshots = (
        ExternalAffiliationSnapshot.objects.annotate(knox_lookup=Lower("knox_id"))
        .filter(knox_lookup__in=lookup_keys)
        .order_by("knox_lookup", "id")
    )
    result: dict[str, ExternalAffiliationSnapshot] = {}
    for snapshot in snapshots:
        lookup_key = (snapshot.knox_id or "").strip().lower()
        if lookup_key and lookup_key not in result:
            result[lookup_key] = snapshot
    return result


def get_current_user_sdwt_prod_change(*, user: Any) -> UserSdwtProdChange | None:
    """현재 user_sdwt_prod에 해당하는 승인 변경 이력을 반환합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserSdwtProdChange | None: 승인된 변경 이력 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    if not user:
        return None

    current_user_sdwt_prod = get_current_user_sdwt_prod(user=user)
    normalized = _normalize_text(current_user_sdwt_prod)
    if not normalized:
        return None

    return (
        UserSdwtProdChange.objects.filter(user=user, to_user_sdwt_prod__iexact=normalized)
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
        .order_by("-effective_from", "-id")
        .first()
    )


def get_pending_user_sdwt_prod_change(*, user: Any) -> UserSdwtProdChange | None:
    """현재 사용자의 PENDING 상태 변경 요청을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserSdwtProdChange | None: 대기 변경 요청 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 유효성 확인
    # -----------------------------------------------------------------------------
    if not user:
        return None

    # -----------------------------------------------------------------------------
    # 2) 대기 상태 조회
    # -----------------------------------------------------------------------------
    return (
        UserSdwtProdChange.objects.filter(user=user)
        .filter(
            Q(status=UserSdwtProdChange.Status.PENDING)
            | Q(status__isnull=True, approved=False, applied=False)
        )
        .order_by("-created_at", "-id")
        .first()
    )


def get_pending_user_sdwt_prod_changes_by_user_ids(*, user_ids: list[int]) -> set[int]:
    """사용자 id 목록에 대한 PENDING 변경 요청 존재 여부를 조회합니다.

    입력:
    - user_ids: 사용자 id 목록

    반환:
    - set[int]: 대기 변경 요청이 존재하는 사용자 id 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized = _normalize_positive_int_set(user_ids)
    if not normalized:
        return set()

    rows = (
        UserSdwtProdChange.objects.filter(user_id__in=normalized)
        .filter(
            Q(status=UserSdwtProdChange.Status.PENDING)
            | Q(status__isnull=True, approved=False, applied=False)
        )
        .values_list("user_id", flat=True)
    )
    return {value for value in rows if isinstance(value, int)}


def get_access_row_for_user_and_prod(
    *,
    user: Any,
    user_sdwt_prod: str,
) -> UserSdwtProdAccess | None:
    """(user, user_sdwt_prod)에 대한 접근 권한 행을 조회합니다.

    입력:
    - user: Django 사용자 객체
    - user_sdwt_prod: 소속 식별자

    반환:
    - UserSdwtProdAccess | None: 접근 권한 행 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return None

    return (
        UserSdwtProdAccess.objects.filter(
            user=user,
            affiliation__is_active=True,
            affiliation__user_sdwt_prod__iexact=normalized,
        )
        .select_related("user", "affiliation")
        .order_by("id")
        .first()
    )


def list_active_affiliation_ids(
    *,
    affiliation_ids: Iterable[int],
) -> set[int]:
    """요청 ID 중 현재 활성 상태인 소속 ID 집합을 반환합니다."""

    normalized_ids = _normalize_positive_int_set(affiliation_ids)
    if not normalized_ids:
        return set()
    return set(
        Affiliation.objects.filter(
            id__in=normalized_ids,
            is_active=True,
        ).values_list("id", flat=True)
    )


def list_affiliation_roles_for_user_by_ids(
    *,
    user: Any,
    affiliation_ids: Iterable[int],
) -> dict[int, str]:
    """사용자의 활성 소속별 명시 역할을 한 번에 조회해 반환합니다."""

    normalized_ids = _normalize_positive_int_set(affiliation_ids)
    if not normalized_ids:
        return {}
    return dict(
        UserSdwtProdAccess.objects.filter(
            user=user,
            affiliation_id__in=normalized_ids,
            affiliation__is_active=True,
        ).values_list("affiliation_id", "role")
    )


def get_access_row_for_user_and_prod_for_update(
    *,
    user: Any,
    user_sdwt_prod: str,
) -> UserSdwtProdAccess | None:
    """트랜잭션 안에서 사용자의 소속 접근 권한 행을 잠가 조회합니다."""

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return None
    return (
        UserSdwtProdAccess.objects.select_for_update(of=("self",))
        .filter(
            user=user,
            affiliation__is_active=True,
            affiliation__user_sdwt_prod__iexact=normalized,
        )
        .select_related("user", "affiliation")
        .order_by("id")
        .first()
    )


def other_manager_exists(
    *,
    user_sdwt_prod: str,
    exclude_user: Any,
) -> bool:
    """그룹에 현재 사용자 외 다른 관리자(role=manager)가 존재하는지 확인합니다.

    입력:
    - user_sdwt_prod: 소속 식별자
    - exclude_user: 제외할 사용자

    반환:
    - bool: 다른 관리자 존재 여부

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return False

    return (
        UserSdwtProdAccess.objects.filter(
            affiliation__is_active=True,
            affiliation__user_sdwt_prod__iexact=normalized,
            role=UserSdwtProdAccess.Roles.MANAGER,
        )
        .exclude(user=exclude_user)
        .exists()
    )


def list_manageable_user_sdwt_prod_values(*, user: Any) -> set[str]:
    """사용자가 관리(role=manager)할 수 있는 user_sdwt_prod 값 집합을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - set[str]: 관리 가능한 user_sdwt_prod 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    values = set(
        UserSdwtProdAccess.objects.filter(
            user=user,
            affiliation__is_active=True,
            role=UserSdwtProdAccess.Roles.MANAGER,
        ).values_list(
            "affiliation__user_sdwt_prod",
            flat=True,
        )
    )
    return _collapse_user_sdwt_prod_values(values)


def list_approvable_user_sdwt_prod_values(*, user: Any) -> set[str]:
    """사용자가 승인(role=manager)할 수 있는 user_sdwt_prod 값 집합을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - set[str]: 승인 가능한 user_sdwt_prod 집합

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    values = set(
        UserSdwtProdAccess.objects.filter(
            user=user,
            affiliation__is_active=True,
            role=UserSdwtProdAccess.Roles.MANAGER,
        ).values_list(
            "affiliation__user_sdwt_prod",
            flat=True,
        )
    )
    return _collapse_user_sdwt_prod_values(values)


def list_affiliation_change_requests(
    *,
    allowed_user_sdwt_prods: set[str] | None,
    status: str | None,
    search: str | None,
    user_sdwt_prod: str | None,
) -> QuerySet[UserSdwtProdChange]:
    """승인 대상 소속 변경 요청 목록을 필터링하여 조회합니다.

    입력:
    - allowed_user_sdwt_prods: 조회 가능한 user_sdwt_prod 집합(None이면 전체)
    - status: 상태 필터(PENDING/APPROVED/REJECTED/SUPERSEDED)
    - search: 사용자 정보 검색어
    - user_sdwt_prod: to_user_sdwt_prod 필터

    반환:
    - QuerySet[UserSdwtProdChange]: 필터링된 변경 요청 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 쿼리셋(QuerySet) 준비
    # -----------------------------------------------------------------------------
    qs = UserSdwtProdChange.objects.select_related("user", "created_by", "approved_by")

    # -----------------------------------------------------------------------------
    # 2) 조회 가능 범위 필터
    # -----------------------------------------------------------------------------
    if allowed_user_sdwt_prods is not None:
        if not allowed_user_sdwt_prods:
            return UserSdwtProdChange.objects.none()
        allowed_lookup_keys = list(_build_user_sdwt_display_map(allowed_user_sdwt_prods).keys())
        if not allowed_lookup_keys:
            return UserSdwtProdChange.objects.none()
        qs = qs.annotate(to_user_sdwt_prod_lookup=Lower("to_user_sdwt_prod")).filter(
            to_user_sdwt_prod_lookup__in=allowed_lookup_keys
        )

    normalized_status_input = _normalize_text(status)
    if normalized_status_input:
        normalized_status = normalized_status_input.upper()
        if normalized_status == UserSdwtProdChange.Status.PENDING:
            qs = qs.filter(
                Q(status=UserSdwtProdChange.Status.PENDING)
                | Q(status__isnull=True, approved=False, applied=False)
            )
        elif normalized_status == UserSdwtProdChange.Status.APPROVED:
            qs = qs.filter(
                Q(status=UserSdwtProdChange.Status.APPROVED)
                | Q(approved=True)
                | Q(applied=True)
            )
        elif normalized_status == UserSdwtProdChange.Status.REJECTED:
            qs = qs.filter(
                status__in=[
                    UserSdwtProdChange.Status.REJECTED,
                    UserSdwtProdChange.Status.SUPERSEDED,
                ]
            )
        elif normalized_status == UserSdwtProdChange.Status.SUPERSEDED:
            qs = qs.filter(status=UserSdwtProdChange.Status.SUPERSEDED)

    normalized_user_sdwt_prod = _normalize_text(user_sdwt_prod)
    if normalized_user_sdwt_prod:
        qs = qs.filter(to_user_sdwt_prod__iexact=normalized_user_sdwt_prod)

    keyword = _normalize_text(search)
    if keyword:
        qs = qs.filter(
            Q(user__username__icontains=keyword)
            | Q(user__email__icontains=keyword)
            | Q(user__sabun__icontains=keyword)
            | Q(user__knox_id__icontains=keyword)
            | Q(user__givenname__icontains=keyword)
            | Q(user__surname__icontains=keyword)
        )

    # -----------------------------------------------------------------------------
    # 6) 정렬 및 반환
    # -----------------------------------------------------------------------------
    return qs.order_by("-created_at", "-id")


def list_group_members(*, user_sdwt_prods: set[str]) -> QuerySet[UserSdwtProdAccess]:
    """지정한 user_sdwt_prods 그룹에 속한 멤버 접근 권한 행을 조회합니다.

    입력:
    - user_sdwt_prods: 소속 식별자 집합

    반환:
    - QuerySet[UserSdwtProdAccess]: 멤버 접근 권한 행 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    lookup_keys = list(_build_user_sdwt_display_map(user_sdwt_prods).keys())
    if not lookup_keys:
        return UserSdwtProdAccess.objects.none()

    return (
        UserSdwtProdAccess.objects.annotate(
            user_sdwt_prod_lookup=Lower("affiliation__user_sdwt_prod")
        )
        .filter(
            affiliation__is_active=True,
            user_sdwt_prod_lookup__in=lookup_keys,
        )
        .select_related("user", "affiliation")
        .order_by("affiliation__user_sdwt_prod", "user_id")
    )


def list_current_affiliation_users_by_user_sdwt_prod(*, user_sdwt_prod: str) -> list[Any]:
    """현재 앱 소속이 지정 user_sdwt_prod인 사용자를 조회합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - list[Any]: 사용자 객체 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized = _normalize_user_sdwt_prod(user_sdwt_prod)
    if not normalized:
        return []

    UserModel = get_user_model()
    return list(
        UserModel.objects.filter(
            current_affiliation__affiliation__is_active=True,
            current_affiliation__affiliation__user_sdwt_prod__iexact=normalized,
        )
        .select_related("current_affiliation__affiliation")
        .order_by("id")
    )


def list_line_sdwt_pairs() -> list[dict[str, str]]:
    """활성 소속의 선택 가능한 (line_id, user_sdwt_prod) 쌍 목록을 조회합니다.

    입력:
    - 없음

    반환:
    - list[dict[str, str]]: line_id/user_sdwt_prod 쌍 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 활성 라인/소속 값 조회 및 정제
    # -----------------------------------------------------------------------------
    pairs = (
        Affiliation.objects.filter(is_active=True, line__isnull=False)
        .exclude(line__exact="")
        .exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod__exact="")
        .values("line", "user_sdwt_prod")
        .distinct()
        .order_by("line", "user_sdwt_prod")
    )
    # -----------------------------------------------------------------------------
    # 2) 응답 형식으로 변환
    # -----------------------------------------------------------------------------
    return [
        {"line_id": row["line"], "user_sdwt_prod": row["user_sdwt_prod"]}
        for row in pairs
    ]


def list_user_sdwt_prod_values_for_line(*, line_id: str) -> list[str]:
    """라인 ID에 매핑되는 account_affiliation user_sdwt_prod 목록을 조회합니다.

    입력:
    - line_id: 라인 ID

    반환:
    - list[str]: user_sdwt_prod 문자열 목록

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized_line_id = _normalize_text(line_id)
    if not normalized_line_id:
        return []

    values = (
        Affiliation.objects.filter(
            is_active=True,
            line__iexact=normalized_line_id,
        )
        .exclude(user_sdwt_prod__isnull=True)
        .exclude(user_sdwt_prod__exact="")
        .values_list("user_sdwt_prod", flat=True)
        .order_by("user_sdwt_prod")
    )
    return sorted(_collapse_user_sdwt_prod_values(values))


def get_next_user_sdwt_prod_change(
    *,
    user: Any,
    effective_from: datetime,
) -> UserSdwtProdChange | None:
    """effective_from 이후 예정된 다음 소속 변경을 조회합니다.

    입력:
    - user: Django 사용자 객체
    - effective_from: 기준 시각

    반환:
    - UserSdwtProdChange | None: 다음 변경 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 기준 시각 보정
    # -----------------------------------------------------------------------------
    if effective_from is None:
        effective_from = timezone.now()
    if timezone.is_naive(effective_from):
        effective_from = timezone.make_aware(effective_from, timezone.utc)

    # -----------------------------------------------------------------------------
    # 2) 다음 승인 변경 조회
    # -----------------------------------------------------------------------------
    return (
        UserSdwtProdChange.objects.filter(user=user, effective_from__gt=effective_from)
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
        .order_by("effective_from", "id")
        .first()
    )


def resolve_user_affiliation(user: Any, at_time: datetime | None) -> dict[str, str]:
    """지정 시점의 사용자 소속 스냅샷을 계산합니다.

    입력:
    - user: Django 사용자 객체
    - at_time: 기준 시각(없으면 현재 시각)

    반환:
    - dict[str, str]: 부서/라인/user_sdwt_prod 스냅샷

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 기준 시각 보정
    # -----------------------------------------------------------------------------
    if at_time is None:
        at_time = timezone.now()
    if timezone.is_naive(at_time):
        at_time = timezone.make_aware(at_time, timezone.utc)

    current_values = get_current_affiliation_values(user=user)
    current_department = current_values.get("department")
    current_line = current_values.get("line")
    current_user_sdwt_prod = current_values.get("user_sdwt_prod")

    # -----------------------------------------------------------------------------
    # 2) 기준 시각까지 승인된 변경 조회
    # -----------------------------------------------------------------------------
    change = (
        UserSdwtProdChange.objects.filter(user=user, effective_from__lte=at_time)
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
        .order_by("-effective_from", "-id")
        .first()
    )

    # -----------------------------------------------------------------------------
    # 3) 변경 이력이 있으면 해당 스냅샷 반환
    # -----------------------------------------------------------------------------
    if change:
        return {
            "department": change.department or current_department or UNKNOWN,
            "line": change.line or current_line or "",
            "user_sdwt_prod": change.to_user_sdwt_prod
            or current_user_sdwt_prod
            or UNCLASSIFIED_USER_SDWT_PROD,
        }

    # -----------------------------------------------------------------------------
    # 4) 다음 변경이 있는 경우 이전 소속 추정
    # -----------------------------------------------------------------------------
    next_change = (
        UserSdwtProdChange.objects.filter(user=user, effective_from__gt=at_time)
        .filter(Q(status=UserSdwtProdChange.Status.APPROVED) | Q(approved=True))
        .order_by("effective_from", "id")
        .first()
    )

    before_user_sdwt_prod = None
    if next_change:
        before_user_sdwt_prod = next_change.from_user_sdwt_prod

    # -----------------------------------------------------------------------------
    # 5) 기본 스냅샷 반환
    # -----------------------------------------------------------------------------
    return {
        "department": current_department or UNKNOWN,
        "line": current_line or "",
        "user_sdwt_prod": before_user_sdwt_prod
        or current_user_sdwt_prod
        or UNCLASSIFIED_USER_SDWT_PROD,
    }


def get_affiliation_option_by_user_sdwt_prod(*, user_sdwt_prod: str) -> Affiliation | None:
    """user_sdwt_prod로 단일 Affiliation 옵션을 조회합니다.

    입력:
    - user_sdwt_prod: 소속 식별자

    반환:
    - Affiliation | None: 단일 옵션 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    normalized = _normalize_text(user_sdwt_prod)
    if not normalized:
        return None

    rows = list(
        Affiliation.objects.filter(
            is_active=True,
            user_sdwt_prod__iexact=normalized,
        ).order_by("id")[:2]
    )
    if len(rows) != 1:
        return None
    return rows[0]


def get_affiliation_option_for_update_by_user_sdwt_prod(
    *,
    user_sdwt_prod: str,
) -> Affiliation | None:
    """트랜잭션 안에서 소속 행을 대소문자 비구분으로 잠가 조회합니다."""

    normalized = _normalize_text(user_sdwt_prod)
    if not normalized:
        return None
    rows = list(
        Affiliation.objects.select_for_update(of=("self",))
        .filter(
            is_active=True,
            user_sdwt_prod__iexact=normalized,
        )
        .order_by("id")[:2]
    )
    if len(rows) != 1:
        return None
    return rows[0]
