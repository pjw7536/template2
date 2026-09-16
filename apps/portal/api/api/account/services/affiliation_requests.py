# =============================================================================
# 모듈 설명: 소속 변경 요청/승인/거절 서비스 로직을 제공합니다.
# - 주요 대상: request_affiliation_change, approve_affiliation_change, reject_affiliation_change
# - 불변 조건: 승인/거절은 권한 검증 후 처리합니다.
# =============================================================================

"""소속 변경 요청/승인/거절 서비스 모음.

- 주요 대상: 변경 요청 조회/생성/승인/거절
- 주요 엔드포인트/클래스: request_affiliation_change 등
- 가정/불변 조건: 승인/거절은 권한 검증 후 처리됨
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Tuple

from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.utils import timezone

from ..models import UserCurrentAffiliation, UserSdwtProdChange
from .. import selectors
from .access import downgrade_member_access, ensure_self_access
from .utils import (
    _build_user_sdwt_display_map,
    _is_privileged_user,
    _normalize_user_sdwt_prod,
    _normalize_user_sdwt_lookup_key,
    _resolve_user_sdwt_prod_role,
    _same_user_sdwt_prod,
    _user_can_approve_affiliation_change,
)


def _serialize_actor(user: Any) -> dict[str, object] | None:
    """승인/요청 사용자 정보를 직렬화합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - dict[str, object] | None: 직렬화 결과 또는 None

    부작용:
    - 없음

    오류:
    - 없음
    """

    if not user:
        return None
    username = getattr(user, "username", "") or ""
    return {"id": user.id, "username": username}


def _serialize_affiliation_change(change: UserSdwtProdChange) -> dict[str, object]:
    """UserSdwtProdChange를 응답용 dict로 직렬화합니다.

    입력:
    - change: UserSdwtProdChange 객체

    반환:
    - dict[str, object]: 직렬화 결과

    부작용:
    - 없음

    오류:
    - 없음
    """

    return {
        "id": change.id,
        "status": change.status,
        "department": change.department,
        "line": change.line,
        "fromUserSdwtProd": change.from_user_sdwt_prod,
        "toUserSdwtProd": change.to_user_sdwt_prod,
        "effectiveFrom": change.effective_from.isoformat(),
        "approvedAt": change.approved_at.isoformat() if change.approved_at else None,
        "requestedAt": change.created_at.isoformat(),
        "approvedBy": _serialize_actor(change.approved_by),
        "requestedBy": _serialize_actor(change.created_by),
        "rejectionReason": change.rejection_reason,
    }


def _serialize_affiliation_change_request(
    change: UserSdwtProdChange,
    *,
    role: str,
) -> dict[str, object]:
    """승인 요청용 UserSdwtProdChange 응답 payload를 구성합니다.

    입력:
    - change: UserSdwtProdChange 객체
    - role: 사용자 역할(viewer/member/manager)

    반환:
    - dict[str, object]: 승인 요청용 payload

    부작용:
    - 없음

    오류:
    - 없음
    """

    user = change.user
    current_values = selectors.get_current_affiliation_values(user=user)
    user_payload = {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
        "sabun": getattr(user, "sabun", None),
        "knoxId": getattr(user, "knox_id", None),
        "department": current_values.get("department"),
        "line": current_values.get("line"),
        "userSdwtProd": current_values.get("user_sdwt_prod"),
    }

    return {
        **_serialize_affiliation_change(change),
        "role": role,
        "user": user_payload,
    }


def _resolve_affiliation_change_role(*, user: Any, change: UserSdwtProdChange) -> str:
    """소속 변경 요청 항목의 역할을 계산합니다.

    입력:
    - user: Django 사용자 객체
    - change: UserSdwtProdChange 객체

    반환:
    - str: viewer/member/manager

    부작용:
    - 없음

    오류:
    - 없음
    """

    role = _resolve_user_sdwt_prod_role(
        user=user,
        user_sdwt_prod=change.to_user_sdwt_prod,
    )
    return role or "viewer"


def get_pending_user_sdwt_prod_change(*, user: Any) -> UserSdwtProdChange | None:
    """대기 중인 user_sdwt_prod 변경 요청을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserSdwtProdChange | None: 대기 중인 변경 요청 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return selectors.get_pending_user_sdwt_prod_change(user=user)


def get_current_user_sdwt_prod_change(*, user: Any) -> UserSdwtProdChange | None:
    """현재 적용 중인 user_sdwt_prod 변경 이력을 조회합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - UserSdwtProdChange | None: 가장 최근 변경 이력 또는 None

    부작용:
    - 없음(읽기 전용)

    오류:
    - 없음
    """

    return selectors.get_current_user_sdwt_prod_change(user=user)


def get_affiliation_change_requests(
    *,
    user: Any,
    status: str | None,
    search: str | None,
    user_sdwt_prod: str | None,
    page: int,
    page_size: int,
) -> Tuple[dict[str, object], int]:
    """조회 가능한 소속 변경 요청 목록을 페이지 단위로 조회합니다.

    입력:
    - user: Django 사용자 객체
    - status/search/user_sdwt_prod: 필터 조건
    - page/page_size: 페이지네이션 값

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - 없음(읽기 전용)

    오류:
    - 403: 조회 권한 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 승인 가능 범위 산정
    # -----------------------------------------------------------------------------
    is_privileged = _is_privileged_user(user)
    approvable_user_sdwt_prods = None
    allowed_user_sdwt_prods: set[str] | None = None
    if not is_privileged:
        approvable_user_sdwt_prods = selectors.list_approvable_user_sdwt_prod_values(user=user)
        allowed_user_sdwt_prods = set(approvable_user_sdwt_prods)
        current_user_sdwt = selectors.get_current_user_sdwt_prod(user=user)
        if isinstance(current_user_sdwt, str) and current_user_sdwt.strip():
            allowed_user_sdwt_prods.add(current_user_sdwt.strip())
        if not allowed_user_sdwt_prods:
            return {"error": "forbidden"}, 403
        allowed_lookup_keys = set(_build_user_sdwt_display_map(allowed_user_sdwt_prods).keys())
        requested_lookup_key = _normalize_user_sdwt_lookup_key(user_sdwt_prod)
        if requested_lookup_key and requested_lookup_key not in allowed_lookup_keys:
            return {"error": "forbidden"}, 403
        approvable_user_sdwt_prods = allowed_user_sdwt_prods

    # -----------------------------------------------------------------------------
    # 2) 변경 요청 목록 조회
    # -----------------------------------------------------------------------------
    qs = selectors.list_affiliation_change_requests(
        allowed_user_sdwt_prods=approvable_user_sdwt_prods,
        status=status,
        search=search,
        user_sdwt_prod=user_sdwt_prod,
    )

    # -----------------------------------------------------------------------------
    # 3) 페이지네이션 처리
    # -----------------------------------------------------------------------------
    paginator = Paginator(qs, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    # -----------------------------------------------------------------------------
    # 4) 응답 구성 및 반환
    # -----------------------------------------------------------------------------
    results = [
        _serialize_affiliation_change_request(
            change,
            role=_resolve_affiliation_change_role(user=user, change=change),
        )
        for change in page_obj.object_list
    ]

    return (
        {
            "results": results,
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
        },
        200,
    )


def _apply_affiliation_change(*, change: UserSdwtProdChange, approver: Any | None) -> dict[str, object]:
    """소속 변경을 즉시 승인/적용합니다.

    입력:
    - change: UserSdwtProdChange 객체
    - approver: 승인자 사용자(없으면 None)

    반환:
    - dict[str, object]: 승인/적용 결과 payload

    부작용:
    - 사용자 소속 필드 업데이트
    - UserSdwtProdChange 상태 업데이트
    - 접근 권한 행 보장

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 현재 앱 소속 업데이트
    # -----------------------------------------------------------------------------
    target_user = change.user
    previous_user_sdwt = (getattr(change, "from_user_sdwt_prod", None) or "").strip()
    now = timezone.now()
    option = selectors.get_affiliation_option_by_user_sdwt_prod(
        user_sdwt_prod=change.to_user_sdwt_prod
    )
    if option is None:
        raise ValueError("Invalid user_sdwt_prod")

    source = (
        UserCurrentAffiliation.Sources.ADMIN_ASSIGNED
        if approver is not None and getattr(approver, "id", None) != target_user.id
        else UserCurrentAffiliation.Sources.USER_SELECTED
    )
    UserCurrentAffiliation.objects.update_or_create(
        user=target_user,
        defaults={
            "affiliation": option,
            "source": source,
            "confirmed_at": now,
            "requires_reconfirm": False,
        },
    )

    # -----------------------------------------------------------------------------
    # 2) 변경 요청 승인/적용 상태 반영
    # -----------------------------------------------------------------------------
    change.approved = True
    change.approved_by = approver
    change.approved_at = now
    change.applied = True
    change.status = UserSdwtProdChange.Status.APPROVED
    change.rejection_reason = None
    change.save(
        update_fields=[
            "approved",
            "approved_by",
            "approved_at",
            "applied",
            "status",
            "rejection_reason",
        ]
    )

    audit_actor = approver or target_user
    audit_reason = f"소속 변경 요청 #{change.id} 적용"
    ensure_self_access(
        target_user,
        role="member",
        audit_actor=audit_actor,
        audit_reason=audit_reason,
    )
    if previous_user_sdwt and not _same_user_sdwt_prod(previous_user_sdwt, change.to_user_sdwt_prod):
        downgrade_member_access(
            user=target_user,
            user_sdwt_prod=previous_user_sdwt,
            audit_actor=audit_actor,
            audit_reason=audit_reason,
        )

    return {
        "status": "applied",
        "changeId": change.id,
        "userId": target_user.id,
        "userSdwtProd": option.user_sdwt_prod,
        "effectiveFrom": change.effective_from.isoformat(),
    }


def _should_auto_apply_affiliation_change(
    *,
    predicted_user_sdwt: str,
    target_user_sdwt: str,
    force_pending: bool,
    has_existing_pending: bool,
) -> bool:
    """예측 소속과 요청 상태를 기준으로 자동 적용 가능 여부를 판단합니다."""

    return (
        _same_user_sdwt_prod(predicted_user_sdwt, target_user_sdwt)
        and not force_pending
        and not has_existing_pending
    )


def _lock_affiliation_change_for_decision(
    *,
    change_id: int,
) -> tuple[UserSdwtProdChange | None, dict[str, object] | None, int | None]:
    """소속·사용자·요청 순서로 잠그고 현재 유효한 대기 요청을 반환합니다.

    호출자는 반드시 `transaction.atomic()` 안에서 실행해야 합니다. 소속 역할 변경과
    같은 `Affiliation` 잠금을 먼저 사용해 manager 재검사 시점과 역할 변경을 직렬화합니다.
    """

    preview = selectors.get_user_sdwt_prod_change_by_id(change_id=change_id)
    if preview is None:
        return None, {"error": "Change not found"}, 404

    locked_affiliation = (
        selectors.get_affiliation_option_for_update_by_user_sdwt_prod(
            user_sdwt_prod=preview.to_user_sdwt_prod,
        )
    )
    if locked_affiliation is None:
        return None, {"error": "forbidden"}, 403

    locked_user = selectors.get_user_by_id_for_update(user_id=preview.user_id)
    if locked_user is None:
        return None, {"error": "User not found"}, 404

    change = selectors.get_user_sdwt_prod_change_by_id_for_update(
        change_id=change_id
    )
    if change is None:
        return None, {"error": "Change not found"}, 404
    if (
        change.user_id != locked_user.id
        or not _same_user_sdwt_prod(
            change.to_user_sdwt_prod,
            locked_affiliation.user_sdwt_prod,
        )
    ):
        return None, {"error": "affiliation_request_changed"}, 409

    change.user = locked_user
    current_pending = selectors.get_pending_user_sdwt_prod_change(
        user=locked_user
    )
    if (
        change.status not in {None, "", UserSdwtProdChange.Status.PENDING}
        or change.approved
        or change.applied
        or current_pending is None
        or current_pending.id != change.id
    ):
        return (
            None,
            {"error": "Affiliation request already decided"},
            409,
        )
    return change, None, None


def request_affiliation_change(
    *,
    user: Any,
    option: Any,
    to_user_sdwt_prod: str,
    effective_from: datetime | None,
    timezone_name: str,
    force_pending: bool = False,
) -> Tuple[dict[str, object], int]:
    """user_sdwt_prod 소속 변경을 요청합니다.

    입력:
    - user: Django 사용자 객체
    - option: 소속 옵션 객체
    - to_user_sdwt_prod: 대상 소속
    - effective_from: 효력 시작 시각(None이면 현재 시각)
    - timezone_name: 시간대 이름
    - force_pending: 자동 승인 차단 여부

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - UserSdwtProdChange 생성
    - 자동 적용 조건 충족 시 즉시 승인/반영

    오류:
    - 400: 동일 소속 요청
    """

    # -----------------------------------------------------------------------------
    # 1) 대상 소속과 외부 예측값 정규화
    # -----------------------------------------------------------------------------
    normalized_target = _normalize_user_sdwt_prod(to_user_sdwt_prod)
    knox_id = (getattr(user, "knox_id", None) or "").strip()
    predicted_user_sdwt = ""
    if knox_id:
        snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(knox_id=knox_id)
        predicted_user_sdwt = _normalize_user_sdwt_prod(
            snapshot.predicted_user_sdwt_prod if snapshot else None
        )

    # -----------------------------------------------------------------------------
    # 2) 사용자 단위로 요청 생성과 기존 대기 요청 대체를 직렬화
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        locked_user = selectors.get_user_by_id_for_update(
            user_id=getattr(user, "id", None),
        )
        if locked_user is None:
            return {"error": "User not found"}, 404

        current_user_sdwt = _normalize_user_sdwt_prod(
            selectors.get_current_user_sdwt_prod(user=locked_user)
        )
        if _same_user_sdwt_prod(current_user_sdwt, normalized_target):
            return {"error": "already current affiliation"}, 400

        ensure_self_access(locked_user, role="member")
        existing_pending = selectors.get_pending_user_sdwt_prod_change(
            user=locked_user
        )
        should_auto_apply = _should_auto_apply_affiliation_change(
            predicted_user_sdwt=predicted_user_sdwt,
            target_user_sdwt=normalized_target,
            force_pending=force_pending,
            has_existing_pending=existing_pending is not None,
        )

        if should_auto_apply:
            resolved_effective_from = timezone.now()
        elif effective_from is None:
            resolved_effective_from = timezone.now()
        elif timezone.is_naive(effective_from):
            resolved_effective_from = timezone.make_aware(
                effective_from,
                timezone.utc,
            )
        else:
            resolved_effective_from = effective_from

        if existing_pending is not None:
            existing_pending.status = UserSdwtProdChange.Status.SUPERSEDED
            existing_pending.approved = False
            existing_pending.approved_by = None
            existing_pending.approved_at = None
            existing_pending.applied = False
            existing_pending.rejection_reason = "취소(대체됨)"
            existing_pending.save(
                update_fields=[
                    "status",
                    "approved",
                    "approved_by",
                    "approved_at",
                    "applied",
                    "rejection_reason",
                ]
            )

        change = UserSdwtProdChange.objects.create(
            user=locked_user,
            department=getattr(option, "department", None),
            line=getattr(option, "line", None),
            from_user_sdwt_prod=selectors.get_current_user_sdwt_prod(
                user=locked_user
            ),
            to_user_sdwt_prod=normalized_target,
            effective_from=resolved_effective_from,
            status=UserSdwtProdChange.Status.PENDING,
            applied=False,
            approved=False,
            created_by=locked_user,
        )

        if should_auto_apply:
            return _apply_affiliation_change(
                change=change,
                approver=locked_user,
            ), 200

        current_affiliation = selectors.get_current_affiliation_record(
            user=locked_user
        )
        if current_affiliation is not None and current_affiliation.requires_reconfirm:
            current_affiliation.requires_reconfirm = False
            current_affiliation.save(update_fields=["requires_reconfirm"])

    # -----------------------------------------------------------------------------
    # 3) 승인 대기 응답 반환
    # -----------------------------------------------------------------------------
    return (
        {
            "status": "pending",
            "changeId": change.id,
            "userSdwtProd": normalized_target,
            "effectiveFrom": change.effective_from.isoformat(),
        },
        202,
    )


def approve_affiliation_change(
    *,
    approver: Any,
    change_id: int,
) -> Tuple[dict[str, object], int]:
    """대기 중인 UserSdwtProdChange를 승인하고 사용자 정보에 반영합니다.

    입력:
    - approver: 승인자 사용자
    - change_id: 변경 요청 id

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - 사용자 소속 필드 업데이트
    - UserSdwtProdChange 상태 업데이트
    - 접근 권한 행 보장

    오류:
    - 403: 권한 없음 또는 자기 요청 승인
    - 404: 변경 요청 없음
    - 409: 이미 처리됨
    """

    # -----------------------------------------------------------------------------
    # 1) 소속·사용자·요청을 잠근 뒤 최신 manager 권한을 재검사
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        change, error_payload, error_status = _lock_affiliation_change_for_decision(
            change_id=change_id
        )
        if error_payload is not None:
            return error_payload, int(error_status or 409)
        if change is None:  # 타입 안전성을 위한 방어 분기입니다.
            return {"error": "Change not found"}, 404
        if getattr(approver, "id", None) == change.user_id:
            return {"error": "Cannot approve your own affiliation request"}, 403
        if not _user_can_approve_affiliation_change(
            user=approver,
            target_user_sdwt_prod=change.to_user_sdwt_prod,
        ):
            return {"error": "forbidden"}, 403

        # -----------------------------------------------------------------------------
        # 2) 승인과 소속 적용을 원자적으로 처리
        # -----------------------------------------------------------------------------
        payload = _apply_affiliation_change(change=change, approver=approver)
        payload["status"] = "approved"

    # -----------------------------------------------------------------------------
    # 3) 응답 반환
    # -----------------------------------------------------------------------------
    return payload, 200


def reject_affiliation_change(
    *,
    approver: Any,
    change_id: int,
    rejection_reason: str | None,
) -> Tuple[dict[str, object], int]:
    """대기 중인 UserSdwtProdChange를 거절 처리합니다.

    입력:
    - approver: 승인자 사용자
    - change_id: 변경 요청 id
    - rejection_reason: 거절 사유(없으면 None)

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - UserSdwtProdChange 상태를 REJECTED로 업데이트
    - 거절 사유 저장

    오류:
    - 403: 권한 없음 또는 자기 요청 거절
    - 404: 변경 요청 없음
    - 409: 이미 처리됨
    """

    # -----------------------------------------------------------------------------
    # 1) 소속·사용자·요청을 잠근 뒤 최신 manager 권한을 재검사
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        change, error_payload, error_status = _lock_affiliation_change_for_decision(
            change_id=change_id
        )
        if error_payload is not None:
            return error_payload, int(error_status or 409)
        if change is None:  # 타입 안전성을 위한 방어 분기입니다.
            return {"error": "Change not found"}, 404
        if getattr(approver, "id", None) == change.user_id:
            return {"error": "Cannot reject your own affiliation request"}, 403
        if not _user_can_approve_affiliation_change(
            user=approver,
            target_user_sdwt_prod=change.to_user_sdwt_prod,
        ):
            return {"error": "forbidden"}, 403

        # -----------------------------------------------------------------------------
        # 2) 거절 상태와 처리자 정보를 원자적으로 저장
        # -----------------------------------------------------------------------------
        normalized_reason = (
            rejection_reason.strip() if isinstance(rejection_reason, str) else ""
        )
        change.status = UserSdwtProdChange.Status.REJECTED
        change.approved = False
        change.approved_by = approver
        change.approved_at = timezone.now()
        change.applied = False
        change.rejection_reason = normalized_reason or None
        change.save(
            update_fields=[
                "status",
                "approved",
                "approved_by",
                "approved_at",
                "applied",
                "rejection_reason",
            ]
        )

        return {"status": "rejected", "changeId": change.id}, 200
