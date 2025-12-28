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

from api.common.affiliations import UNASSIGNED_USER_SDWT_PROD

from ..models import UserSdwtProdChange
from .. import selectors
from .access import ensure_self_access
from .utils import _is_privileged_user, _user_can_manage_user_sdwt_prod


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
    }


def _serialize_affiliation_change_request(change: UserSdwtProdChange) -> dict[str, object]:
    """승인 요청용 UserSdwtProdChange 응답 payload를 구성합니다.

    입력:
    - change: UserSdwtProdChange 객체

    반환:
    - dict[str, object]: 승인 요청용 payload

    부작용:
    - 없음

    오류:
    - 없음
    """

    user = change.user
    user_payload = {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "email": getattr(user, "email", None),
        "sabun": getattr(user, "sabun", None),
        "knoxId": getattr(user, "knox_id", None),
        "department": getattr(user, "department", None),
        "line": getattr(user, "line", None),
        "userSdwtProd": getattr(user, "user_sdwt_prod", None),
    }

    return {
        **_serialize_affiliation_change(change),
        "user": user_payload,
    }


def get_affiliation_change_requests(
    *,
    user: Any,
    status: str | None,
    search: str | None,
    user_sdwt_prod: str | None,
    page: int,
    page_size: int,
) -> Tuple[dict[str, object], int]:
    """승인 가능한 소속 변경 요청 목록을 페이지 단위로 조회합니다.

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
    # 1) 권한 범위 산정
    # -----------------------------------------------------------------------------
    is_privileged = _is_privileged_user(user)
    manageable_user_sdwt_prods = None
    can_manage = False
    allowed_user_sdwt_prods: set[str] | None = None
    if not is_privileged:
        manageable_user_sdwt_prods = selectors.list_manageable_user_sdwt_prod_values(user=user)
        can_manage = bool(manageable_user_sdwt_prods)
        allowed_user_sdwt_prods = set(manageable_user_sdwt_prods)
        current_user_sdwt = getattr(user, "user_sdwt_prod", None)
        if isinstance(current_user_sdwt, str) and current_user_sdwt.strip():
            allowed_user_sdwt_prods.add(current_user_sdwt.strip())
        if not allowed_user_sdwt_prods:
            return {"error": "forbidden"}, 403
        if user_sdwt_prod and user_sdwt_prod not in allowed_user_sdwt_prods:
            return {"error": "forbidden"}, 403
        manageable_user_sdwt_prods = allowed_user_sdwt_prods
    else:
        can_manage = True

    # -----------------------------------------------------------------------------
    # 2) 변경 요청 목록 조회
    # -----------------------------------------------------------------------------
    qs = selectors.list_affiliation_change_requests(
        manageable_user_sdwt_prods=manageable_user_sdwt_prods,
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
    results = [_serialize_affiliation_change_request(change) for change in page_obj.object_list]

    return (
        {
            "results": results,
            "page": page_obj.number,
            "pageSize": page_size,
            "total": paginator.count,
            "totalPages": paginator.num_pages,
            "canManage": can_manage,
        },
        200,
    )


def request_affiliation_change(
    *,
    user: Any,
    option: Any,
    to_user_sdwt_prod: str,
    effective_from: datetime,
    timezone_name: str,
) -> Tuple[dict[str, object], int]:
    """user_sdwt_prod 소속 변경을 요청합니다.

    입력:
    - user: Django 사용자 객체
    - option: 소속 옵션 객체
    - to_user_sdwt_prod: 대상 소속
    - effective_from: 효력 시작 시각
    - timezone_name: 시간대 이름

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - UserSdwtProdChange 생성

    오류:
    - 409: 대기 중 요청 존재
    """

    # -----------------------------------------------------------------------------
    # 1) 자기 접근 권한 보장
    # -----------------------------------------------------------------------------
    ensure_self_access(user, as_manager=False)

    # -----------------------------------------------------------------------------
    # 2) 기존 대기 요청 확인
    # -----------------------------------------------------------------------------
    existing_pending = selectors.get_pending_user_sdwt_prod_change(user=user)
    if existing_pending is not None:
        return {"error": "pending change exists", "changeId": existing_pending.id}, 409

    # -----------------------------------------------------------------------------
    # 3) effective_from 보정
    # -----------------------------------------------------------------------------
    if effective_from is None:
        effective_from = timezone.now()
    elif timezone.is_naive(effective_from):
        effective_from = timezone.make_aware(effective_from, timezone.utc)
    # -----------------------------------------------------------------------------
    # 4) 변경 요청 생성
    # -----------------------------------------------------------------------------
    change = UserSdwtProdChange.objects.create(
        user=user,
        department=getattr(option, "department", None),
        line=getattr(option, "line", None),
        from_user_sdwt_prod=getattr(user, "user_sdwt_prod", None),
        to_user_sdwt_prod=to_user_sdwt_prod,
        effective_from=effective_from,
        status=UserSdwtProdChange.Status.PENDING,
        applied=False,
        approved=False,
        created_by=user,
    )

    # -----------------------------------------------------------------------------
    # 5) 응답 반환
    # -----------------------------------------------------------------------------
    return (
        {
            "status": "pending",
            "changeId": change.id,
            "requestedUserSdwtProd": to_user_sdwt_prod,
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
    - 403: 권한 없음
    - 404: 변경 요청 없음
    - 400: 이미 처리됨
    """

    # -----------------------------------------------------------------------------
    # 1) 변경 요청 조회
    # -----------------------------------------------------------------------------
    change = selectors.get_user_sdwt_prod_change_by_id(change_id=change_id)
    if change is None:
        return {"error": "Change not found"}, 404

    # -----------------------------------------------------------------------------
    # 2) 권한 검증
    # -----------------------------------------------------------------------------
    if not _user_can_manage_user_sdwt_prod(user=approver, user_sdwt_prod=change.to_user_sdwt_prod):
        return {"error": "forbidden"}, 403

    # -----------------------------------------------------------------------------
    # 3) 상태 검증
    # -----------------------------------------------------------------------------
    if change.status == UserSdwtProdChange.Status.APPROVED or change.approved or change.applied:
        return {"error": "already applied"}, 400
    if change.status == UserSdwtProdChange.Status.REJECTED:
        return {"error": "already rejected"}, 400

    # -----------------------------------------------------------------------------
    # 4) 대상 사용자 및 이전 소속 준비
    # -----------------------------------------------------------------------------
    target_user = change.user
    previous_user_sdwt = getattr(target_user, "user_sdwt_prod", None)
    had_previous_affiliation = bool(
        isinstance(previous_user_sdwt, str)
        and previous_user_sdwt.strip()
        and previous_user_sdwt.strip() != UNASSIGNED_USER_SDWT_PROD
    )

    # -----------------------------------------------------------------------------
    # 5) 트랜잭션 내 승인/적용 처리
    # -----------------------------------------------------------------------------
    now = timezone.now()
    with transaction.atomic():
        target_user.user_sdwt_prod = change.to_user_sdwt_prod
        target_user.department = change.department
        target_user.line = change.line
        target_user.affiliation_confirmed_at = now
        target_user.requires_affiliation_reconfirm = False
        target_user.save(
            update_fields=[
                "user_sdwt_prod",
                "department",
                "line",
                "affiliation_confirmed_at",
                "requires_affiliation_reconfirm",
            ]
        )

        change.approved = True
        change.approved_by = approver
        change.approved_at = now
        change.applied = True
        change.status = UserSdwtProdChange.Status.APPROVED
        change.save(
            update_fields=[
                "approved",
                "approved_by",
                "approved_at",
                "applied",
                "status",
            ]
        )

        ensure_self_access(target_user, as_manager=False)

        # 소속 변경 시 기존 접근 권한 행은 유지합니다.

    # -----------------------------------------------------------------------------
    # 6) 응답 반환
    # -----------------------------------------------------------------------------
    return (
        {
            "status": "approved",
            "changeId": change.id,
            "userId": target_user.id,
            "userSdwtProd": target_user.user_sdwt_prod,
            "effectiveFrom": change.effective_from.isoformat(),
        },
        200,
    )


def reject_affiliation_change(
    *,
    approver: Any,
    change_id: int,
) -> Tuple[dict[str, object], int]:
    """대기 중인 UserSdwtProdChange를 거절 처리합니다.

    입력:
    - approver: 승인자 사용자
    - change_id: 변경 요청 id

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - UserSdwtProdChange 상태를 REJECTED로 업데이트

    오류:
    - 403: 권한 없음
    - 404: 변경 요청 없음
    - 400: 이미 처리됨
    """

    # -----------------------------------------------------------------------------
    # 1) 변경 요청 조회
    # -----------------------------------------------------------------------------
    change = selectors.get_user_sdwt_prod_change_by_id(change_id=change_id)
    if change is None:
        return {"error": "Change not found"}, 404

    # -----------------------------------------------------------------------------
    # 2) 권한 검증
    # -----------------------------------------------------------------------------
    if not _user_can_manage_user_sdwt_prod(user=approver, user_sdwt_prod=change.to_user_sdwt_prod):
        return {"error": "forbidden"}, 403

    # -----------------------------------------------------------------------------
    # 3) 상태 검증
    # -----------------------------------------------------------------------------
    if change.status == UserSdwtProdChange.Status.REJECTED:
        return {"error": "already rejected"}, 400
    if change.status == UserSdwtProdChange.Status.APPROVED or change.approved or change.applied:
        return {"error": "already applied"}, 400

    # -----------------------------------------------------------------------------
    # 4) 거절 처리 및 저장
    # -----------------------------------------------------------------------------
    change.status = UserSdwtProdChange.Status.REJECTED
    change.approved = False
    change.approved_by = approver
    change.approved_at = timezone.now()
    change.applied = False
    change.save(update_fields=["status", "approved", "approved_by", "approved_at", "applied"])

    return {"status": "rejected", "changeId": change.id}, 200
