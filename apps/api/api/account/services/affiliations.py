from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

from django.db import transaction
from django.utils import timezone

from ..models import Affiliation
from .. import selectors
from .access import _current_access_list
from .affiliation_requests import request_affiliation_change


def get_affiliation_overview(*, user: Any, timezone_name: str) -> dict[str, object]:
    """AccountAffiliationView(GET) 응답 payload를 구성합니다.

    Build the AccountAffiliationView GET response payload.
    """

    access_list = _current_access_list(user)
    manageable = [entry["userSdwtProd"] for entry in access_list if entry["canManage"]]
    options = selectors.list_affiliation_options()

    return {
        "currentUserSdwtProd": getattr(user, "user_sdwt_prod", None),
        "currentDepartment": getattr(user, "department", None),
        "currentLine": getattr(user, "line", None),
        "timezone": timezone_name,
        "accessibleUserSdwtProds": access_list,
        "manageableUserSdwtProds": manageable,
        "affiliationOptions": options,
    }


def get_affiliation_reconfirm_status(*, user: Any) -> dict[str, object]:
    """사용자의 소속 재확인 상태와 예측값을 반환합니다.

    Returns:
        Dict with requiresReconfirm, predictedUserSdwtProd, currentUserSdwtProd.
    """

    if not user:
        return {"requiresReconfirm": False, "predictedUserSdwtProd": None, "currentUserSdwtProd": None}

    snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(
        knox_id=getattr(user, "knox_id", "") or ""
    )
    predicted = snapshot.predicted_user_sdwt_prod if snapshot else None
    return {
        "requiresReconfirm": bool(getattr(user, "requires_affiliation_reconfirm", False)),
        "predictedUserSdwtProd": predicted,
        "currentUserSdwtProd": getattr(user, "user_sdwt_prod", None),
    }


def submit_affiliation_reconfirm_response(
    *,
    user: Any,
    accepted: bool,
    department: str | None,
    line: str | None,
    user_sdwt_prod: str | None,
    timezone_name: str,
) -> Tuple[dict[str, object], int]:
    """재확인 응답을 처리해 소속 변경 요청을 생성합니다.

    Returns:
        (payload, http_status)
    """

    if not user:
        return {"error": "unauthorized"}, 401

    selected_user_sdwt = (user_sdwt_prod or "").strip()
    if accepted and not selected_user_sdwt:
        snapshot = selectors.get_external_affiliation_snapshot_by_knox_id(
            knox_id=getattr(user, "knox_id", "") or ""
        )
        if snapshot:
            selected_user_sdwt = snapshot.predicted_user_sdwt_prod

    if not selected_user_sdwt:
        return {"error": "user_sdwt_prod is required"}, 400

    option = None
    if department and line:
        option = selectors.get_affiliation_option(
            (department or "").strip(),
            (line or "").strip(),
            selected_user_sdwt,
        )
    if option is None:
        option = selectors.get_affiliation_option_by_user_sdwt_prod(
            user_sdwt_prod=selected_user_sdwt
        )
    if option is None:
        return {"error": "Invalid department/line/user_sdwt_prod combination"}, 400

    response_payload, status_code = request_affiliation_change(
        user=user,
        option=option,
        to_user_sdwt_prod=selected_user_sdwt,
        effective_from=timezone.now(),
        timezone_name=timezone_name,
    )
    if status_code in (200, 202):
        user.requires_affiliation_reconfirm = False
        user.save(update_fields=["requires_affiliation_reconfirm"])

    return response_payload, status_code


def update_affiliation_jira_key(*, line_id: str, jira_key: str | None) -> int:
    """line_id에 해당하는 Affiliation의 jira_key를 업데이트합니다.

    Args:
        line_id: 대상 line_id 문자열.
        jira_key: Jira 프로젝트 키(없으면 None).

    Returns:
        업데이트된 row 개수.

    Side effects:
        Updates Affiliation.jira_key rows.
    """

    if not isinstance(line_id, str) or not line_id.strip():
        raise ValueError("line_id is required")

    normalized = jira_key.strip() if isinstance(jira_key, str) and jira_key.strip() else None
    with transaction.atomic():
        updated = Affiliation.objects.filter(line=line_id.strip()).update(jira_key=normalized)
    return int(updated or 0)


def get_line_sdwt_options_payload(*, pairs: list[dict[str, str]]) -> dict[str, object]:
    """(line_id, user_sdwt_prod) 목록으로 LineSdwtOptionsView 응답 payload를 구성합니다.

    Build LineSdwtOptionsView response payload from (line_id, user_sdwt_prod) rows.
    """

    grouped: Dict[str, List[str]] = {}
    for row in pairs:
        line_id = row["line_id"]
        user_sdwt_prod = row["user_sdwt_prod"]
        grouped.setdefault(line_id, []).append(user_sdwt_prod)

    lines = [
        {
            "lineId": line_id,
            "userSdwtProds": sorted(list(set(user_sdwt_list))),
        }
        for line_id, user_sdwt_list in grouped.items()
    ]
    all_user_sdwt = sorted(
        {usdwt for user_sdwt_list in grouped.values() for usdwt in user_sdwt_list}
    )

    return {"lines": lines, "userSdwtProds": all_user_sdwt}
