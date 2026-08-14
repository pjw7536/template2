"""Portal account를 Grist forward-auth ticket으로 교환합니다."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.core import signing

from api.account import selectors as account_selectors
from api.account import services as account_services


GRIST_FORWARD_AUTH_SALT = "work_hub.grist_forward_auth"


class GristForwardAuthConfigurationError(RuntimeError):
    """forward-auth 환경 설정이 누락되었거나 안전하지 않을 때 발생합니다."""


class GristForwardAuthRequestError(ValueError):
    """로그인 return URL이나 서명 ticket이 유효하지 않을 때 발생합니다."""


class GristForwardAuthUserError(ValueError):
    """Portal 사용자를 Grist identity로 변환할 수 없을 때 발생합니다."""


def _ticket_secret() -> str:
    """Portal이 forward-auth ticket에 사용할 전용 서명 secret을 반환합니다."""

    secret = str(
        getattr(settings, "GRIST_FORWARD_AUTH_TICKET_SECRET", "") or ""
    ).strip()
    if not secret:
        raise GristForwardAuthConfigurationError(
            "Grist forward-auth ticket secret이 설정되지 않았습니다."
        )
    return secret


def validate_grist_login_return_url(return_url: str) -> str:
    """설정된 Grist origin의 forward-auth login URL만 허용합니다."""

    public_url = str(getattr(settings, "GRIST_PUBLIC_URL", "") or "").strip()
    login_path = str(
        getattr(settings, "GRIST_FORWARD_AUTH_LOGIN_PATH", "/auth/login")
        or "/auth/login"
    ).strip()
    if not login_path.startswith("/"):
        login_path = f"/{login_path}"

    public = urlparse(public_url)
    target = urlparse(str(return_url or "").strip())
    if (
        public.scheme not in {"http", "https"}
        or target.scheme != public.scheme
        or target.netloc != public.netloc
        or target.username is not None
        or target.password is not None
        or target.path.rstrip("/") != login_path.rstrip("/")
        or target.query
        or target.fragment
    ):
        raise GristForwardAuthRequestError(
            "Grist forward-auth return URL이 허용되지 않습니다."
        )
    return target.geturl()


def validate_grist_login_next_path(next_path: str) -> str:
    """Grist login 이후 이동할 같은 origin 내부 경로만 허용합니다."""

    candidate = str(next_path or "").strip()
    if not candidate:
        return ""

    target = urlparse(candidate)
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
        or any(ord(character) < 32 for character in candidate)
        or target.scheme
        or target.netloc
        or target.params
        or target.query
        or target.fragment
        or target.path != candidate
    ):
        raise GristForwardAuthRequestError(
            "Grist forward-auth next 경로가 허용되지 않습니다."
        )
    return target.path


def _require_portal_identity(user: Any) -> tuple[int, str]:
    """활성 Portal account의 안정적인 ID와 email을 반환합니다."""

    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        raise GristForwardAuthUserError("활성 Portal account가 필요합니다.")
    try:
        user_id = int(getattr(user, "pk", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise GristForwardAuthUserError("Portal account ID가 올바르지 않습니다.") from exc
    email = str(getattr(user, "email", "") or "").strip().casefold()
    if user_id <= 0 or not email:
        raise GristForwardAuthUserError(
            "Grist 로그인에 사용할 Portal account ID와 email이 필요합니다."
        )
    return user_id, email


def issue_grist_forward_auth_redirect(
    *,
    user: Any,
    return_url: str,
    next_path: str = "",
) -> str:
    """Portal account ID와 이동 경로를 서명해 Grist login으로 반환합니다."""

    user_id, _email = _require_portal_identity(user)
    validated_return_url = validate_grist_login_return_url(return_url)
    validated_next_path = validate_grist_login_next_path(next_path)
    ticket = signing.dumps(
        {"user_id": user_id, "next": validated_next_path},
        key=_ticket_secret(),
        salt=GRIST_FORWARD_AUTH_SALT,
        compress=False,
    )
    query = {"ticket": ticket}
    if validated_next_path:
        query["next"] = validated_next_path
    return f"{validated_return_url}?{urlencode(query)}"


def has_grist_forward_auth_access(*, user: Any, request: Any) -> bool:
    """기능 플래그와 Portal·Work Hub app 접근이 모두 허용되는지 반환합니다."""

    if not getattr(settings, "WORK_HUB_ENABLED", False):
        return False

    portal_access = account_services.get_access_payload(
        user=user,
        scope_key="portal",
        request=request,
    )
    work_hub_access = account_services.get_access_payload(
        user=user,
        scope_key="work-hub",
        request=request,
    )
    return bool(portal_access.get("allowed") and work_hub_access.get("allowed"))


def resolve_grist_forward_auth_user(*, ticket: str, next_path: str = "") -> Any:
    """서명·만료·이동 경로를 검증해 현재 활성 Portal account를 조회합니다."""

    max_age = int(
        getattr(settings, "GRIST_FORWARD_AUTH_TICKET_MAX_AGE_SECONDS", 30) or 30
    )
    try:
        payload = signing.loads(
            str(ticket or "").strip(),
            key=_ticket_secret(),
            salt=GRIST_FORWARD_AUTH_SALT,
            max_age=max_age,
        )
        if not isinstance(payload, dict):
            raise TypeError
        user_id = int(payload.get("user_id") or 0)
        signed_next_path = validate_grist_login_next_path(
            str(payload.get("next") or "")
        )
        requested_next_path = validate_grist_login_next_path(next_path)
        if signed_next_path != requested_next_path:
            raise ValueError
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise GristForwardAuthRequestError(
            "Grist forward-auth ticket이 올바르지 않거나 만료되었습니다."
        ) from exc

    user = account_selectors.get_user_by_id(user_id=user_id) if user_id > 0 else None
    _require_portal_identity(user)
    return user
