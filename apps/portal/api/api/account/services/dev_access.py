# =============================================================================
# 모듈 설명: 로컬 dev 권한 관리 화면 검증용 더미 데이터를 생성합니다.
# - 주요 함수: seed_dev_access_data
# - 불변 조건: 전달받은 prefix의 account 더미 사용자만 초기화합니다.
# =============================================================================

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..models import (
    ACCESS_SCOPE_PORTAL,
    AccessAuditLog,
    AccessRole,
    Affiliation,
    UserAccess,
    UserCurrentAffiliation,
)
from .access_control import decide_user_access, request_access
from .affiliations import (
    AFFILIATION_AUDIT_SOURCE_DEV_SEED,
    ensure_affiliation_option,
)

PENDING_USER_COUNT = 24
APP_SCOPE_KEYS = (
    "appstore",
    "assistant",
    "line-dashboard",
    "observer",
    "voc",
    "l3-spider",
)
AFFILIATION_SAMPLES = (
    ("개발 플랫폼팀", "DEV-L1", "ALPHA"),
    ("데이터 운영팀", "DEV-L2", "BETA"),
    ("품질 자동화팀", "DEV-L3", "GAMMA"),
)
MATRIX_SAMPLES = (
    ("appstore", "approve", AccessRole.USER, "approve", AccessRole.ADMIN),
    ("line-dashboard", "approve", AccessRole.USER, "approve", AccessRole.USER),
    ("observer", "reject", AccessRole.USER, "approve", AccessRole.USER),
    ("assistant", "approve", AccessRole.ADMIN, "reject", AccessRole.USER),
)


def _seed_user_marker(prefix: str) -> str:
    """account 더미 사용자를 식별할 사번 prefix를 반환합니다."""

    return f"{prefix}-ACCESS-"


def _ensure_affiliation(
    *,
    prefix: str,
    sample_index: int,
) -> Affiliation:
    """더미 사용자의 현재 소속으로 사용할 공유 소속 행을 보장합니다."""

    department, line, suffix = AFFILIATION_SAMPLES[
        sample_index % len(AFFILIATION_SAMPLES)
    ]
    affiliation = ensure_affiliation_option(
        department=department,
        line=line,
        user_sdwt_prod=f"{prefix}_ACCESS_{suffix}",
        audit_source=AFFILIATION_AUDIT_SOURCE_DEV_SEED,
        audit_reason="개발 권한 관리 시드 소속 보장",
    )
    return affiliation


def _ensure_seed_user(
    *,
    prefix: str,
    sequence: int,
    sample_index: int,
) -> Any:
    """결정적인 식별자와 소속을 가진 account 더미 사용자를 보장합니다."""

    UserModel = get_user_model()
    sabun = f"{_seed_user_marker(prefix)}{sequence:03d}"
    affiliation = _ensure_affiliation(
        prefix=prefix,
        sample_index=sample_index,
    )
    user, _created = UserModel.objects.update_or_create(
        sabun=sabun,
        defaults={
            "username": f"개발 사용자 {sequence:02d}",
            "knox_id": f"{prefix.lower()}.access.{sequence:03d}",
            "email": f"{prefix.lower()}.access.{sequence:03d}@example.com",
            "department": affiliation.department,
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
        },
    )
    UserCurrentAffiliation.objects.update_or_create(
        user=user,
        defaults={
            "affiliation": affiliation,
            "source": UserCurrentAffiliation.Sources.ADMIN_ASSIGNED,
            "requires_reconfirm": False,
            "confirmed_at": timezone.now(),
        },
    )
    return user


def _require_success(
    *,
    operation: str,
    result: tuple[dict[str, object], int],
) -> dict[str, object]:
    """더미 시드의 canonical 권한 작업이 성공했는지 확인합니다."""

    payload, status_code = result
    if status_code != 200:
        raise RuntimeError(
            f"account dev seed {operation} 실패: status={status_code}, payload={payload}"
        )
    return payload


def _seed_pending_users(*, prefix: str) -> None:
    """페이지네이션과 scope 필터 검증용 승인 대기 요청을 생성합니다."""

    base_time = timezone.now() - timedelta(hours=PENDING_USER_COUNT)
    for index in range(PENDING_USER_COUNT):
        sequence = index + 1
        user = _ensure_seed_user(
            prefix=prefix,
            sequence=sequence,
            sample_index=index,
        )
        primary_scope_index = index % len(APP_SCOPE_KEYS)
        requested_scopes = [APP_SCOPE_KEYS[primary_scope_index]]
        if sequence % 4 == 0:
            requested_scopes.append(
                APP_SCOPE_KEYS[(primary_scope_index + 1) % len(APP_SCOPE_KEYS)]
            )
        _require_success(
            operation=f"pending request user={user.sabun}",
            result=request_access(
                user=user,
                scope_keys=requested_scopes,
            ),
        )
        # 요청 순서가 화면에서 눈에 보이도록 사용자별 시각을 일정하게 벌립니다.
        UserAccess.objects.filter(
            user=user,
            status=UserAccess.Status.PENDING,
        ).update(requested_at=base_time + timedelta(hours=index))


def _seed_matrix_users(*, prefix: str, actor: Any) -> None:
    """역할 색상과 Portal 선행 차단을 비교할 권한 매트릭스 행을 생성합니다."""

    for index, (
        scope_key,
        portal_action,
        portal_role,
        app_action,
        app_role,
    ) in enumerate(MATRIX_SAMPLES):
        sequence = PENDING_USER_COUNT + index + 1
        user = _ensure_seed_user(
            prefix=prefix,
            sequence=sequence,
            sample_index=index,
        )
        _require_success(
            operation=f"matrix request user={user.sabun}",
            result=request_access(user=user, scope_keys=[scope_key]),
        )
        _require_success(
            operation=f"matrix portal decision user={user.sabun}",
            result=decide_user_access(
                actor=actor,
                user_id=user.id,
                scope_key=ACCESS_SCOPE_PORTAL,
                action=portal_action,
                role=portal_role if portal_action == "approve" else None,
                reason="로컬 개발 권한 매트릭스 더미데이터",
            ),
        )
        _require_success(
            operation=f"matrix app decision user={user.sabun}",
            result=decide_user_access(
                actor=actor,
                user_id=user.id,
                scope_key=scope_key,
                action=app_action,
                role=app_role if app_action == "approve" else None,
                reason="로컬 개발 권한 매트릭스 더미데이터",
            ),
        )


def seed_dev_access_data(
    *,
    prefix: str,
    actor: Any,
    reset: bool = False,
) -> dict[str, int]:
    """로컬 권한 관리 화면을 검증할 결정적 account 더미 데이터를 생성합니다.

    입력:
    - prefix: 다른 더미 데이터와 공유하는 식별 prefix
    - actor: 권한 결정 감사 로그에 기록할 dev 관리자
    - reset: 같은 prefix의 account 더미 사용자를 먼저 제거할지 여부

    반환:
    - dict[str, int]: 삭제 사용자와 생성된 상태별 행 수

    부작용:
    - User/Affiliation/UserCurrentAffiliation/UserAccess/AccessAuditLog DB 쓰기

    오류:
    - RuntimeError: canonical 권한 요청 또는 결정이 실패한 경우
    """

    normalized_prefix = str(prefix or "").strip().upper()
    if not normalized_prefix:
        raise ValueError("prefix는 비워둘 수 없습니다.")
    if not actor or not getattr(actor, "is_superuser", False):
        raise ValueError("account 더미데이터 actor는 dev 슈퍼유저여야 합니다.")

    user_marker = _seed_user_marker(normalized_prefix)
    with transaction.atomic():
        seeded_users = get_user_model().objects.filter(
            sabun__startswith=user_marker,
        )
        deleted_users = seeded_users.count() if reset else 0
        AccessAuditLog.objects.filter(
            Q(actor__in=seeded_users) | Q(target_user__in=seeded_users)
        ).delete()
        if reset:
            seeded_users.delete()
        else:
            # reset 없이 다시 실행해도 이전 화면 조작 결과를 결정적 초기 상태로 되돌립니다.
            UserAccess.objects.filter(user__in=seeded_users).delete()

        _seed_pending_users(prefix=normalized_prefix)
        _seed_matrix_users(prefix=normalized_prefix, actor=actor)

        seeded_users = get_user_model().objects.filter(
            sabun__startswith=user_marker,
        )
        seeded_accesses = UserAccess.objects.filter(user__in=seeded_users)
        return {
            "deletedUsers": deleted_users,
            "users": seeded_users.count(),
            "pending": seeded_accesses.filter(
                status=UserAccess.Status.PENDING,
            ).count(),
            "allowed": seeded_accesses.filter(
                status=UserAccess.Status.ALLOWED,
            ).count(),
            "denied": seeded_accesses.filter(
                status=UserAccess.Status.DENIED,
            ).count(),
        }
