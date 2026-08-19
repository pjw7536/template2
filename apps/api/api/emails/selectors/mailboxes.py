# =============================================================================
# 모듈 설명: Emails 소속·mailbox 읽기 selector를 제공합니다.
# =============================================================================

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from django.db.models import Count, Q
from django.utils import timezone

import api.account.selectors as account_selectors
import api.account.services as account_services
from api.common.services import UNASSIGNED_USER_SDWT_PROD

from ..models import Email

class EmailAffiliation(TypedDict):
    """이메일 발신자 소속 판별 결과를 담는 타입입니다."""

    user_sdwt_prod: str
    classification_source: str


def _normalize_time(value: datetime | None) -> datetime:
    """datetime 값을 timezone-aware(UTC)로 정규화합니다.

    입력:
        value: datetime 또는 None.
    반환:
        timezone-aware datetime(UTC 기준).
    부작용:
        없음.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) None 처리 및 timezone 정규화
    # -----------------------------------------------------------------------------
    if value is None:
        return timezone.now()
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.utc)
    return value


def get_accessible_user_sdwt_prods_for_user(user: Any) -> set[str]:
    """사용자가 접근 가능한 user_sdwt_prod 값 집합을 조회합니다.

    입력:
        user: Django User 또는 유사 객체.
    반환:
        접근 가능한 user_sdwt_prod 집합.
    부작용:
        없음. 조회 전용.
    오류:
        없음.
    """

    return account_services.get_accessible_user_sdwt_prods_for_scope(
        user=user,
        scope_key="emails",
    )


def resolve_sender_id_from_user(user: Any) -> str | None:
    """사용자 객체의 Knox ID를 메일 sender_id 형식으로 정규화합니다."""

    sender_id = getattr(user, "knox_id", None)
    if not isinstance(sender_id, str):
        return None
    return sender_id.strip() or None


def list_mailbox_members(*, mailbox_user_sdwt_prod: str) -> list[dict[str, object]]:
    """메일함(user_sdwt_prod)에 접근 가능한 사용자 목록을 반환합니다.

    입력:
        mailbox_user_sdwt_prod: 메일함 user_sdwt_prod 값.
    반환:
        멤버 dict 리스트(권한/발신자 카운트 포함).
    부작용:
        없음. 조회 전용.
    오류:
        mailbox_user_sdwt_prod가 비어 있으면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화
    # -----------------------------------------------------------------------------
    normalized = mailbox_user_sdwt_prod.strip() if isinstance(mailbox_user_sdwt_prod, str) else ""
    if not normalized:
        return []

    # -----------------------------------------------------------------------------
    # 2) 접근 권한/소속 사용자 조회
    # -----------------------------------------------------------------------------
    access_rows = list(account_selectors.list_group_members(user_sdwt_prods={normalized}))
    access_by_user_id = {row.user_id: row for row in access_rows}

    affiliated_users = account_selectors.list_current_affiliation_users_by_user_sdwt_prod(
        user_sdwt_prod=normalized
    )

    members: list[dict[str, object]] = []
    seen_user_ids: set[int] = set()
    sender_id_by_user_id: dict[int, str] = {}

    def serialize_user(user: Any, access: Any | None) -> dict[str, object]:
        """사용자/권한 정보를 멤버 dict로 직렬화합니다."""

        sender_id = resolve_sender_id_from_user(user) or ""
        sender_id_by_user_id[user.id] = sender_id
        display_username = getattr(user, "username", None)
        display_username_value = display_username.strip() if isinstance(display_username, str) else ""
        role_value = getattr(access, "role", None) if access else "member"
        return {
            "userId": user.id,
            "username": display_username_value,
            "name": display_username_value,
            "knoxId": sender_id,
            "avatarid": getattr(user, "avatarid", None),
            "userSdwtProd": normalized,
            "role": role_value,
            "grantedBy": getattr(access, "granted_by_id", None) if access else None,
            "grantedAt": access.created_at.isoformat() if access else None,
            "emailCount": 0,
        }

    # -----------------------------------------------------------------------------
    # 3) 소속 사용자/권한 부여 사용자 병합
    # -----------------------------------------------------------------------------
    for user in affiliated_users:
        access = access_by_user_id.get(user.id)
        members.append(serialize_user(user, access))
        seen_user_ids.add(user.id)

    for access in access_rows:
        if access.user_id in seen_user_ids:
            continue
        members.append(serialize_user(access.user, access))
        seen_user_ids.add(access.user_id)

    # -----------------------------------------------------------------------------
    # 4) 발신자별 이메일 카운트 계산
    # -----------------------------------------------------------------------------
    sender_ids = sorted({value for value in sender_id_by_user_id.values() if value})
    if sender_ids:
        email_count_rows = (
            Email.objects.filter(user_sdwt_prod=normalized, sender_id__in=sender_ids)
            .values("sender_id")
            .annotate(email_count=Count("id"))
        )
        count_by_sender_id = {row["sender_id"]: row["email_count"] for row in email_count_rows}

        for member in members:
            user_id = member.get("userId")
            sender_id = sender_id_by_user_id.get(user_id) if isinstance(user_id, int) else ""
            member["emailCount"] = int(count_by_sender_id.get(sender_id, 0)) if sender_id else 0

    # -----------------------------------------------------------------------------
    # 5) 정렬 및 반환
    # -----------------------------------------------------------------------------
    role_order = {"manager": 0, "member": 1, "viewer": 2}
    members.sort(
        key=lambda member: (
            role_order.get(member.get("role", "viewer"), 2),
            str(member.get("username", "")),
        )
    )
    return members


def resolve_email_affiliation(*, sender_id: str, received_at: datetime | None) -> EmailAffiliation:
    """이메일 발신자 기준으로 user_sdwt_prod 소속을 판별합니다.

    입력:
        sender_id: 발신자 식별자(로컬파트/아이디).
        received_at: 수신 시각(현재 정책에서는 사용하지 않음).
    반환:
        user_sdwt_prod 및 classification_source를 포함한 dict.
    부작용:
        없음. 조회 전용.
    오류:
        없음.
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 소속 우선 확인
    # -----------------------------------------------------------------------------
    user = account_selectors.get_user_by_knox_id(knox_id=sender_id)
    if user is not None:
        resolved = (account_selectors.get_current_user_sdwt_prod(user=user) or "").strip()
        if resolved and resolved != UNASSIGNED_USER_SDWT_PROD:
            return {
                "user_sdwt_prod": resolved,
                "classification_source": Email.ClassificationSource.CONFIRMED_USER,
            }

    # -----------------------------------------------------------------------------
    # 2) 외부 예측 소속 확인
    # -----------------------------------------------------------------------------
    snapshot = account_selectors.get_external_affiliation_snapshot_by_knox_id(knox_id=sender_id)
    if snapshot is not None:
        predicted = (snapshot.predicted_user_sdwt_prod or "").strip()
        if predicted:
            return {
                "user_sdwt_prod": predicted,
                "classification_source": Email.ClassificationSource.PREDICTED_EXTERNAL,
            }

    # -----------------------------------------------------------------------------
    # 3) 기본값(UNASSIGNED) 반환
    # -----------------------------------------------------------------------------
    return {
        "user_sdwt_prod": UNASSIGNED_USER_SDWT_PROD,
        "classification_source": Email.ClassificationSource.UNASSIGNED,
    }


def _unassigned_mailbox_query() -> Q:
    """UNASSIGNED(미분류) 메일함 조건(Q)을 반환합니다.

    입력:
        없음.
    반환:
        UNASSIGNED 메일함에 해당하는 Q 객체.
    부작용:
        없음.
    오류:
        없음.
    """

    # 레거시 데이터 호환을 위해 NULL/빈값/rp-unclassified를 함께 포함합니다.
    return (
        Q(user_sdwt_prod__isnull=True)
        | Q(user_sdwt_prod__exact="")
        | Q(user_sdwt_prod=UNASSIGNED_USER_SDWT_PROD)
        | Q(user_sdwt_prod="rp-unclassified")
    )


def count_unassigned_emails_for_sender_id(*, sender_id: str) -> int:
    """발신자(sender_id)의 UNASSIGNED 메일 개수를 반환합니다.

    입력:
        sender_id: Email.sender_id 값.
    반환:
        UNASSIGNED 메일 개수.
    부작용:
        없음. 조회 전용.
    오류:
        sender_id가 비어 있으면 0 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(sender_id, str) or not sender_id.strip():
        return 0

    # -----------------------------------------------------------------------------
    # 2) 카운트 조회
    # -----------------------------------------------------------------------------
    normalized = sender_id.strip()
    return (
        Email.objects.filter(sender_id=normalized)
        .filter(_unassigned_mailbox_query())
        .count()
    )


def list_unassigned_email_ids_for_sender_id(*, sender_id: str) -> list[int]:
    """발신자(sender_id)의 UNASSIGNED 메일 id 목록을 반환합니다.

    입력:
        sender_id: Email.sender_id 값.
    반환:
        UNASSIGNED 메일 id 리스트.
    부작용:
        없음. 조회 전용.
    오류:
        sender_id가 비어 있으면 빈 리스트 반환.
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 검증
    # -----------------------------------------------------------------------------
    if not isinstance(sender_id, str) or not sender_id.strip():
        return []

    # -----------------------------------------------------------------------------
    # 2) id 목록 조회
    # -----------------------------------------------------------------------------
    normalized = sender_id.strip()
    return list(
        Email.objects.filter(sender_id=normalized)
        .filter(_unassigned_mailbox_query())
        .order_by("id")
        .values_list("id", flat=True)
    )
