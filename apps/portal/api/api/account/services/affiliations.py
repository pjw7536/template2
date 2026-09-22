# =============================================================================
# 모듈 설명: 소속 관련 서비스 로직을 제공합니다.
# - 주요 대상: get_affiliation_overview, ensure_affiliation_option, submit_affiliation_reconfirm_response
# - 불변 조건: 모든 쓰기 작업은 서비스 레이어에서 수행합니다.
# =============================================================================

"""소속 관련 서비스 로직 모음.

- 주요 대상: 소속 개요, 소속 옵션 보장, 재확인 처리, 옵션 페이로드
- 주요 엔드포인트/클래스: get_affiliation_overview 등
- 가정/불변 조건: 모든 쓰기 작업은 서비스 레이어에서 수행됨
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import AccessAuditLog, Affiliation, UserCurrentAffiliation
from .. import selectors
from .access import _current_access_list
from .access_control import create_access_audit_log
from .affiliation_requests import request_affiliation_change
from .utils import _normalize_user_sdwt_prod, _same_user_sdwt_prod

AFFILIATION_AUDIT_SOURCE_DJANGO_ADMIN = "django_admin"
AFFILIATION_AUDIT_SOURCE_SYSTEM_SYNC = "system_sync"
AFFILIATION_AUDIT_SOURCE_DEV_SEED = "dev_seed"


def _serialize_affiliation_state(
    option: Affiliation,
    *,
    source: str | None = None,
) -> dict[str, object]:
    """소속 lifecycle 감사에 사용할 고정 snapshot을 반환합니다."""

    snapshot: dict[str, object] = {
        "id": option.id,
        "department": option.department,
        "line": option.line,
        "userSdwtProd": option.user_sdwt_prod,
        "isActive": option.is_active,
    }
    if source:
        snapshot["source"] = source
    return snapshot


def create_affiliation(
    *,
    actor: Any,
    affiliation: Affiliation,
    reason: str,
    source: str = AFFILIATION_AUDIT_SOURCE_DJANGO_ADMIN,
) -> Affiliation:
    """superuser가 새 활성 소속을 감사 로그와 함께 생성합니다."""

    if not getattr(actor, "is_superuser", False):
        raise PermissionDenied("소속은 superuser만 생성할 수 있습니다.")
    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        raise ValidationError("소속 생성 사유를 입력하세요.")
    normalized_source = (
        (source or "").strip() or AFFILIATION_AUDIT_SOURCE_DJANGO_ADMIN
    )
    if affiliation.pk is not None:
        raise ValidationError("이미 저장된 소속은 생성 서비스로 저장할 수 없습니다.")

    affiliation.department = (affiliation.department or "").strip()
    affiliation.line = (affiliation.line or "").strip()
    affiliation.user_sdwt_prod = (affiliation.user_sdwt_prod or "").strip()
    if not all(
        (
            affiliation.department,
            affiliation.line,
            affiliation.user_sdwt_prod,
        )
    ):
        raise ValidationError("department/line/user_sdwt_prod is required")
    affiliation.is_active = True

    with transaction.atomic():
        try:
            with transaction.atomic():
                affiliation.save()
        except IntegrityError as error:
            raise ValidationError("동일한 소속 식별자가 이미 존재합니다.") from error
        create_access_audit_log(
            scope=None,
            actor=actor,
            target_user=None,
            policy_rule=None,
            affiliation=affiliation,
            action=AccessAuditLog.Actions.AFFILIATION_CREATE,
            before={},
            after=_serialize_affiliation_state(
                affiliation,
                source=normalized_source,
            ),
            reason=normalized_reason,
        )
    return affiliation


def set_affiliations_active(
    *,
    actor: Any,
    affiliation_ids: Iterable[int],
    is_active: bool,
    reason: str,
) -> tuple[dict[str, object], int]:
    """여러 소속의 전역 활성 상태를 한 transaction에서 변경합니다."""

    if not getattr(actor, "is_superuser", False):
        return {"error": "forbidden"}, 403
    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        return {"error": "reason_required"}, 400
    requested_ids = list(affiliation_ids)
    if not requested_ids or any(
        type(affiliation_id) is not int or affiliation_id <= 0
        for affiliation_id in requested_ids
    ):
        return {"error": "affiliation_ids_required"}, 400
    normalized_ids = sorted(set(requested_ids))

    with transaction.atomic():
        options = selectors.list_affiliations_by_ids_for_update(
            affiliation_ids=normalized_ids,
        )
        found_ids = {option.id for option in options}
        if found_ids != set(normalized_ids):
            return {
                "error": "affiliation_not_found",
                "affiliationIds": sorted(set(normalized_ids) - found_ids),
            }, 404

        results: list[dict[str, object]] = []
        updated_count = 0
        for option in options:
            if option.is_active == bool(is_active):
                results.append(
                    {
                        "status": "unchanged",
                        "affiliation": _serialize_affiliation_state(option),
                    }
                )
                continue

            before = _serialize_affiliation_state(option)
            option.is_active = bool(is_active)
            option.save(update_fields=["is_active"])
            create_access_audit_log(
                scope=None,
                actor=actor,
                target_user=None,
                policy_rule=None,
                affiliation=option,
                action=(
                    AccessAuditLog.Actions.AFFILIATION_ACTIVATE
                    if option.is_active
                    else AccessAuditLog.Actions.AFFILIATION_DEACTIVATE
                ),
                before=before,
                after=_serialize_affiliation_state(option),
                reason=normalized_reason,
            )
            updated_count += 1
            results.append(
                {
                    "status": "updated",
                    "affiliation": _serialize_affiliation_state(option),
                }
            )

    return {
        "status": "updated" if updated_count else "unchanged",
        "updated": updated_count,
        "unchanged": len(results) - updated_count,
        "results": results,
    }, 200


def set_affiliation_active(
    *,
    actor: Any,
    affiliation_id: int,
    is_active: bool,
    reason: str,
) -> tuple[dict[str, object], int]:
    """superuser가 소속의 전역 활성 상태를 감사 로그와 함께 변경합니다.

    입력:
    - actor: 변경 작업을 수행하는 Django 사용자
    - affiliation_id: 변경할 Affiliation 기본 키
    - is_active: 적용할 활성 상태
    - reason: 운영 변경 사유

    반환:
    - tuple[dict[str, object], int]: 결과 payload와 HTTP 호환 상태 코드

    부작용:
    - Affiliation.is_active 변경
    - AccessAuditLog 생성

    오류:
    - 403: superuser가 아님
    - 404: 소속이 없음
    - 400: 변경 사유가 없음
    """

    if not getattr(actor, "is_superuser", False):
        return {"error": "forbidden"}, 403
    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        return {"error": "reason_required"}, 400

    payload, status_code = set_affiliations_active(
        actor=actor,
        affiliation_ids=[affiliation_id],
        is_active=is_active,
        reason=normalized_reason,
    )
    if status_code != 200:
        return payload, status_code
    result = payload["results"][0]
    return {
        "status": result["status"],
        "affiliation": result["affiliation"],
    }, 200


def _update_affiliation_option_values(
    *,
    option: Affiliation,
    department: str,
    line: str,
    user_sdwt_prod: str,
) -> tuple[Affiliation, dict[str, object] | None]:
    """소속 옵션의 표시 값을 필요한 경우에만 갱신합니다."""

    before = _serialize_affiliation_state(option)
    changed_fields: list[str] = []
    if option.department != department:
        option.department = department
        changed_fields.append("department")
    if option.line != line:
        option.line = line
        changed_fields.append("line")
    if option.user_sdwt_prod != user_sdwt_prod:
        option.user_sdwt_prod = user_sdwt_prod
        changed_fields.append("user_sdwt_prod")
    if changed_fields:
        option.save(update_fields=changed_fields)
        return option, before
    return option, None


def get_affiliation_overview(*, user: Any, timezone_name: str) -> dict[str, object]:
    """AccountAffiliationView(GET) 응답 payload를 구성합니다.

    입력:
    - user: Django 사용자 객체
    - timezone_name: 시간대 이름

    반환:
    - dict[str, object]: 소속 개요 payload

    부작용:
    - 없음

    오류:
    - 없음
    """

    access_list = _current_access_list(user)
    manageable = [entry["userSdwtProd"] for entry in access_list if entry["role"] == "manager"]
    options = [
        {
            "id": option["id"],
            "department": option["department"],
            "line": option["line"],
            "userSdwtProd": option["user_sdwt_prod"],
        }
        for option in selectors.list_affiliation_options()
    ]
    current_values = selectors.get_current_affiliation_values(user=user)
    current_department = current_values.get("department") or getattr(user, "department", None)

    knox_id = (getattr(user, "knox_id", None) or "").strip()
    snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(knox_id=knox_id) if knox_id else None
    snapshot_user_sdwt_prod = (snapshot.predicted_user_sdwt_prod or "").strip() if snapshot else None
    snapshot_department = (snapshot.department or "").strip() if snapshot else None
    if not snapshot_department:
        snapshot_department = (getattr(user, "department", None) or "").strip() or None

    return {
        "currentUserSdwtProd": current_values.get("user_sdwt_prod"),
        "currentDepartment": current_department,
        "currentLine": current_values.get("line"),
        "timezone": timezone_name,
        "accessibleUserSdwtProds": access_list,
        "manageableUserSdwtProds": manageable,
        "affiliationOptions": options,
        "snapshotUserSdwtProd": snapshot_user_sdwt_prod or None,
        "snapshotDepartment": snapshot_department or None,
    }


def get_affiliation_reconfirm_status(*, user: Any) -> dict[str, object]:
    """사용자의 소속 재확인 상태와 예측값을 반환합니다.

    입력:
    - user: Django 사용자 객체

    반환:
    - dict[str, object]: 재확인 상태/예측 소속 정보

    부작용:
    - 없음

    오류:
    - 없음
    """

    if not user:
        return {"requiresReconfirm": False, "predictedUserSdwtProd": None, "currentUserSdwtProd": None}

    snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(
        knox_id=getattr(user, "knox_id", "") or ""
    )
    predicted = snapshot.predicted_user_sdwt_prod if snapshot else None
    current_values = selectors.get_current_affiliation_values(user=user)
    return {
        "requiresReconfirm": bool(current_values.get("requires_reconfirm", False)),
        "predictedUserSdwtProd": predicted,
        "currentUserSdwtProd": current_values.get("user_sdwt_prod"),
    }


def auto_approve_affiliation_from_snapshot(
    *,
    user: Any,
    timezone_name: str,
) -> Tuple[dict[str, object], int] | None:
    """신규 사용자 첫 로그인 시 외부 예측 소속으로 자동 승인/적용합니다.

    입력:
    - user: Django 사용자 객체
    - timezone_name: 시간대 이름

    반환:
    - Tuple[dict[str, object], int] | None: 승인 결과 또는 None(미적용)

    부작용:
    - UserSdwtProdChange 생성 및 승인/적용
    - 사용자 소속 필드 업데이트

    오류:
    - 없음(조건 불충족 시 None 반환)
    """

    # -----------------------------------------------------------------------------
    # 1) 기본 조건 확인
    # -----------------------------------------------------------------------------
    if not user:
        return None

    current_user_sdwt = (selectors.get_current_user_sdwt_prod(user=user) or "").strip()
    if current_user_sdwt:
        return None

    knox_id = (getattr(user, "knox_id", None) or "").strip()
    if not knox_id:
        return None

    if selectors.get_pending_user_sdwt_prod_change(user=user) is not None:
        return None

    # -----------------------------------------------------------------------------
    # 2) 외부 예측 소속 확인
    # -----------------------------------------------------------------------------
    snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(knox_id=knox_id)
    if snapshot is None:
        return None

    predicted = (snapshot.predicted_user_sdwt_prod or "").strip()
    if not predicted:
        return None

    # -----------------------------------------------------------------------------
    # 3) 소속 옵션 확인
    # -----------------------------------------------------------------------------
    option = selectors.get_affiliation_option_by_user_sdwt_prod(user_sdwt_prod=predicted)
    if option is None:
        return None

    # -----------------------------------------------------------------------------
    # 4) 변경 요청 생성(예측값 일치 시 자동 적용)
    # -----------------------------------------------------------------------------
    return request_affiliation_change(
        user=user,
        option=option,
        to_user_sdwt_prod=predicted,
        effective_from=timezone.now(),
        timezone_name=timezone_name,
    )


def ensure_affiliation_option(
    *,
    department: str,
    line: str,
    user_sdwt_prod: str,
    audit_source: str = AFFILIATION_AUDIT_SOURCE_SYSTEM_SYNC,
    audit_reason: str = "소속 옵션 자동 동기화",
) -> Affiliation:
    """소속 옵션을 생성하거나 기존 행을 갱신합니다.

    입력:
    - department: 부서 식별자
    - line: 라인 식별자
    - user_sdwt_prod: 소속 그룹 값
    반환:
    - Affiliation: 소속 옵션 객체

    부작용:
    - Affiliation 생성 또는 실제 값 변경
    - 생성·변경 시 system 감사 로그 생성

    오류:
    - ValueError: 필수 입력 누락
    """

    # -----------------------------------------------------------------------------
    # 1) 입력 정규화 및 검증
    # -----------------------------------------------------------------------------
    normalized_department = (department or "").strip()
    normalized_line = (line or "").strip()
    normalized_user_sdwt = (user_sdwt_prod or "").strip()
    if not normalized_department or not normalized_line or not normalized_user_sdwt:
        raise ValueError("department/line/user_sdwt_prod is required")
    normalized_source = (
        (audit_source or "").strip() or AFFILIATION_AUDIT_SOURCE_SYSTEM_SYNC
    )
    normalized_reason = (audit_reason or "").strip() or "소속 옵션 자동 동기화"

    # -----------------------------------------------------------------------------
    # 2) 옵션 조회 및 생성/갱신 처리
    # -----------------------------------------------------------------------------
    with transaction.atomic():
        created = False
        before: dict[str, object] | None = None
        option = selectors.get_affiliation_option_by_user_sdwt_prod(
            user_sdwt_prod=normalized_user_sdwt,
        )
        if option is not None:
            option, before = _update_affiliation_option_values(
                option=option,
                department=normalized_department,
                line=normalized_line,
                user_sdwt_prod=normalized_user_sdwt,
            )
        else:
            try:
                with transaction.atomic():
                    option = Affiliation.objects.create(
                        department=normalized_department,
                        line=normalized_line,
                        user_sdwt_prod=normalized_user_sdwt,
                    )
                    created = True
            except IntegrityError:
                option = selectors.get_affiliation_option_by_user_sdwt_prod(
                    user_sdwt_prod=normalized_user_sdwt,
                )
                if option is None:
                    raise
                option, before = _update_affiliation_option_values(
                    option=option,
                    department=normalized_department,
                    line=normalized_line,
                    user_sdwt_prod=normalized_user_sdwt,
                )

        if created:
            create_access_audit_log(
                scope=None,
                actor=None,
                target_user=None,
                policy_rule=None,
                affiliation=option,
                action=AccessAuditLog.Actions.AFFILIATION_CREATE,
                before={},
                after=_serialize_affiliation_state(
                    option,
                    source=normalized_source,
                ),
                reason=normalized_reason,
            )
        elif before is not None:
            create_access_audit_log(
                scope=None,
                actor=None,
                target_user=None,
                policy_rule=None,
                affiliation=option,
                action=AccessAuditLog.Actions.AFFILIATION_UPDATE,
                before={
                    **before,
                    "source": normalized_source,
                },
                after=_serialize_affiliation_state(
                    option,
                    source=normalized_source,
                ),
                reason=normalized_reason,
            )
        return option


def set_current_affiliation_for_user(
    *,
    user: Any,
    department: str,
    line: str,
    user_sdwt_prod: str,
    source: str | None = None,
) -> None:
    """사용자의 현재 앱 소속을 account 도메인 규칙으로 설정합니다.

    입력:
    - user: 대상 사용자
    - department: 부서 식별자
    - line: 라인 식별자
    - user_sdwt_prod: 소속 그룹 값
    - source: 소속 출처(없으면 USER_SELECTED)

    반환:
    - 없음

    부작용:
    - Affiliation 옵션 생성/갱신
    - UserCurrentAffiliation 생성/갱신

    오류:
    - ValueError: 필수 입력 누락
    """

    if user is None:
        raise ValueError("user is required")

    option = ensure_affiliation_option(
        department=department,
        line=line,
        user_sdwt_prod=user_sdwt_prod,
    )
    normalized_source = (source or "").strip() or UserCurrentAffiliation.Sources.USER_SELECTED
    with transaction.atomic():
        UserCurrentAffiliation.objects.update_or_create(
            user=user,
            defaults={
                "affiliation": option,
                "source": normalized_source,
                "requires_reconfirm": False,
            },
        )


def _clear_reconfirm_requirement(current_affiliation: UserCurrentAffiliation) -> None:
    """현재 소속의 재확인 필요 플래그를 해제합니다."""

    current_affiliation.requires_reconfirm = False
    current_affiliation.save(update_fields=["requires_reconfirm"])


def _get_predicted_user_sdwt_prod(*, user: Any) -> str:
    """외부 스냅샷에서 예측 user_sdwt_prod 값을 정규화해 반환합니다."""

    snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(
        knox_id=getattr(user, "knox_id", "") or ""
    )
    return _normalize_user_sdwt_prod(snapshot.predicted_user_sdwt_prod if snapshot else None)


def _resolve_reconfirm_target_user_sdwt(
    *,
    selected_user_sdwt: str | None,
    predicted_user_sdwt: str,
) -> str:
    """재확인 수락 시 사용자가 선택한 값 또는 예측값을 적용 대상으로 결정합니다."""

    return _normalize_user_sdwt_prod(selected_user_sdwt) or predicted_user_sdwt


def submit_affiliation_reconfirm_response(
    *,
    user: Any,
    accepted: bool,
    user_sdwt_prod: str | None,
    timezone_name: str,
) -> Tuple[dict[str, object], int]:
    """재확인 응답을 처리해 소속 변경을 적용하거나 승인 대기를 생성하거나 유지합니다.

    입력:
    - user: Django 사용자 객체
    - accepted: 재확인 수락 여부
    - user_sdwt_prod: 선택된 소속 정보
    - timezone_name: 시간대 이름

    반환:
    - Tuple[dict[str, object], int]: (payload, status_code) (응답 본문, 상태 코드)

    부작용:
    - 예측값 일치 시 UserSdwtProdChange 생성/즉시 적용
    - 불일치 선택 시 UserSdwtProdChange 승인 대기 생성
    - 사용자 재확인 플래그 해제(기존 유지/적용/승인 대기 생성 성공 시)

    오류:
    - 400: 입력 오류
    - 401: 미인증
    - 409: 재확인 대상 아님
    """

    # -----------------------------------------------------------------------------
    # 1) 사용자 인증 확인
    # -----------------------------------------------------------------------------
    if not user:
        return {"error": "unauthorized"}, 401

    # -----------------------------------------------------------------------------
    # 2) 재확인 필요 여부 확인
    # -----------------------------------------------------------------------------
    current_affiliation = selectors.get_current_affiliation_record(user=user)
    if current_affiliation is None or not current_affiliation.requires_reconfirm:
        return {"error": "reconfirm not required"}, 409

    # -----------------------------------------------------------------------------
    # 3) 기존 소속 유지 선택 처리
    # -----------------------------------------------------------------------------
    if not accepted:
        _clear_reconfirm_requirement(current_affiliation)
        return {
            "status": "kept",
            "userSdwtProd": selectors.get_current_user_sdwt_prod(user=user),
        }, 200

    # -----------------------------------------------------------------------------
    # 4) 적용 대상 user_sdwt_prod 결정
    # -----------------------------------------------------------------------------
    predicted = _get_predicted_user_sdwt_prod(user=user)
    selected_user_sdwt = _resolve_reconfirm_target_user_sdwt(
        selected_user_sdwt=user_sdwt_prod,
        predicted_user_sdwt=predicted,
    )
    if not selected_user_sdwt:
        return {"error": "user_sdwt_prod is required"}, 400

    current_user_sdwt = _normalize_user_sdwt_prod(selectors.get_current_user_sdwt_prod(user=user))
    if _same_user_sdwt_prod(current_user_sdwt, selected_user_sdwt):
        _clear_reconfirm_requirement(current_affiliation)
        return {
            "status": "kept",
            "userSdwtProd": current_user_sdwt,
        }, 200

    # -----------------------------------------------------------------------------
    # 5) 소속 옵션 확인
    # -----------------------------------------------------------------------------
    option = selectors.get_affiliation_option_by_user_sdwt_prod(user_sdwt_prod=selected_user_sdwt)
    if option is None:
        return {"error": "Invalid user_sdwt_prod"}, 400

    # -----------------------------------------------------------------------------
    # 6) 변경 요청 생성 및 결과 반환
    # -----------------------------------------------------------------------------
    # 예측값과 다르면 승인 대기 강제
    force_pending = not _same_user_sdwt_prod(selected_user_sdwt, predicted)
    response_payload, status_code = request_affiliation_change(
        user=user,
        option=option,
        to_user_sdwt_prod=selected_user_sdwt,
        effective_from=timezone.now(),
        timezone_name=timezone_name,
        force_pending=force_pending,
    )

    if status_code in (200, 202):
        _clear_reconfirm_requirement(current_affiliation)

    return response_payload, status_code


def get_line_sdwt_options_payload(*, pairs: list[dict[str, str]]) -> dict[str, object]:
    """(line_id, user_sdwt_prod) 목록으로 LineSdwtOptionsView 응답 payload를 구성합니다.

    입력:
    - pairs: line_id/user_sdwt_prod 쌍 목록

    반환:
    - dict[str, object]: 옵션 페이로드

    부작용:
    - 없음

    오류:
    - 없음
    """

    # -----------------------------------------------------------------------------
    # 1) 라인별 그룹화
    # -----------------------------------------------------------------------------
    grouped: Dict[str, List[str]] = {}
    for row in pairs:
        line_id = row["line_id"]
        user_sdwt_prod = row["user_sdwt_prod"]
        grouped.setdefault(line_id, []).append(user_sdwt_prod)

    # -----------------------------------------------------------------------------
    # 2) 라인별 옵션 구성
    # -----------------------------------------------------------------------------
    lines = [
        {
            "lineId": line_id,
            "userSdwtProds": sorted(list(set(user_sdwt_list))),
        }
        for line_id, user_sdwt_list in grouped.items()
    ]
    # -----------------------------------------------------------------------------
    # 3) 전체 user_sdwt_prod 집합 구성
    # -----------------------------------------------------------------------------
    all_user_sdwt = sorted(
        {usdwt for user_sdwt_list in grouped.values() for usdwt in user_sdwt_list}
    )

    # -----------------------------------------------------------------------------
    # 4) 페이로드 반환
    # -----------------------------------------------------------------------------
    return {"lines": lines, "userSdwtProds": all_user_sdwt}
