"""Keycloak OIDC code flow와 읽기 전용 Admin API 연동을 제공합니다."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import jwt
import requests
from django.conf import settings
from django.http import HttpRequest


AFFILIATION_PREFIX = "/affiliations/"
AFFILIATION_ROLES = {"viewer", "member", "manager"}
PORTAL_ROLES = {"portal-user", "portal-admin"}
TOKEN_SESSION_KEY = "keycloak_tokens"
PKCE_SESSION_KEY = "keycloak_pkce_verifier"


class KeycloakError(RuntimeError):
    """Keycloak 설정, 토큰 또는 Admin API 계약 오류입니다."""


@dataclass(frozen=True)
class KeycloakIdentity:
    """검증된 Keycloak 사용자와 권한 snapshot입니다."""

    subject: str
    sabun: str
    knox_id: str
    affiliation_group_id: str
    affiliation: dict[str, str]
    groups: list[str]
    realm_roles: list[str]
    client_roles: dict[str, list[str]]
    claims: dict[str, Any]


def _timeout() -> tuple[float, float]:
    """Keycloak HTTP 연결/응답 제한 시간을 반환합니다."""

    return (
        float(getattr(settings, "KEYCLOAK_CONNECT_TIMEOUT", 3.0)),
        float(getattr(settings, "KEYCLOAK_READ_TIMEOUT", 10.0)),
    )


def _token_request(data: dict[str, str]) -> dict[str, Any]:
    """Keycloak token endpoint 응답을 검증해 반환합니다."""

    try:
        response = requests.post(
            settings.KEYCLOAK_TOKEN_URL,
            data=data,
            timeout=_timeout(),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise KeycloakError("Keycloak token endpoint 호출에 실패했습니다.") from exc
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise KeycloakError("Keycloak token 응답 형식이 올바르지 않습니다.")
    return payload


def create_pkce_pair() -> tuple[str, str]:
    """RFC 7636 S256 verifier와 challenge를 생성합니다."""

    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(*, request: HttpRequest, state: str, nonce: str) -> str:
    """세션에 PKCE verifier를 저장하고 Keycloak authorize URL을 반환합니다."""

    verifier, challenge = create_pkce_pair()
    request.session[PKCE_SESSION_KEY] = verifier
    params = {
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "response_mode": "query",
        "response_type": "code",
        "scope": "openid profile email",
        "nonce": nonce,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{settings.KEYCLOAK_AUTH_URL}?{urlencode(params)}"


def exchange_code(*, request: HttpRequest, code: str) -> dict[str, Any]:
    """일회용 authorization code를 token set으로 교환합니다."""

    verifier = str(request.session.pop(PKCE_SESSION_KEY, "") or "")
    if not verifier:
        raise KeycloakError("PKCE verifier가 없습니다.")
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.OIDC_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "code": code,
        "code_verifier": verifier,
    }
    return _token_request(data)


def refresh_tokens(*, refresh_token: str) -> dict[str, Any]:
    """refresh token으로 Keycloak token set을 갱신합니다."""

    return _token_request(
        {
            "grant_type": "refresh_token",
            "client_id": settings.OIDC_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
            "refresh_token": refresh_token,
        }
    )


def decode_id_token(
    raw_id_token: str,
    *,
    require_subject: bool = True,
) -> dict[str, Any]:
    """JWKS의 현재 서명키로 token의 서명·issuer·audience·만료를 검증합니다."""

    jwks_client = jwt.PyJWKClient(
        settings.KEYCLOAK_JWKS_URL,
        cache_keys=True,
        lifespan=int(getattr(settings, "KEYCLOAK_JWKS_CACHE_SECONDS", 300)),
        timeout=float(getattr(settings, "KEYCLOAK_READ_TIMEOUT", 10.0)),
    )
    signing_key = jwks_client.get_signing_key_from_jwt(raw_id_token)
    return jwt.decode(
        raw_id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.OIDC_CLIENT_ID,
        issuer=settings.OIDC_ISSUER,
        options={
            "require": [
                "exp",
                "iat",
                "iss",
                *(["sub"] if require_subject else []),
            ]
        },
    )


def _normalize_string_list(value: Any) -> list[str]:
    """클레임 배열을 중복 없는 문자열 목록으로 정규화합니다."""

    if not isinstance(value, list):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _client_roles(claims: dict[str, Any]) -> dict[str, list[str]]:
    """resource_access를 client ID별 역할 목록으로 정규화합니다."""

    resource_access = claims.get("resource_access")
    if not isinstance(resource_access, dict):
        return {}
    result: dict[str, list[str]] = {}
    for client_id, raw in resource_access.items():
        roles = raw.get("roles") if isinstance(raw, dict) else []
        normalized = _normalize_string_list(roles)
        if normalized:
            result[str(client_id)] = normalized
    return result


def _parse_affiliation_group(groups: list[str]) -> dict[str, str]:
    """단 하나의 `/affiliations/<소속>/<role>` group을 검증합니다."""

    matches: list[dict[str, str]] = []
    for path in groups:
        if not path.startswith(AFFILIATION_PREFIX):
            continue
        parts = [part for part in path.split("/") if part]
        if len(parts) != 3 or parts[0] != "affiliations" or parts[2] not in AFFILIATION_ROLES:
            raise KeycloakError("Keycloak 소속 group 경로가 올바르지 않습니다.")
        matches.append(
            {
                "name": parts[1],
                "user_sdwt_prod": parts[1],
                "role": parts[2],
                "path": path,
            }
        )
    if len(matches) != 1:
        raise KeycloakError("Keycloak 기본 소속 group은 정확히 하나여야 합니다.")
    return matches[0]


def identity_from_claims(claims: dict[str, Any]) -> KeycloakIdentity:
    """검증된 token claims에서 shadow User 저장 값을 생성합니다."""

    subject = str(claims.get("sub") or "").strip()
    sabun = str(claims.get("sabun") or "").strip()
    knox_id = str(claims.get("loginid") or claims.get("preferred_username") or "").strip()
    group_id = str(claims.get("affiliation_group_id") or "").strip()
    if not subject or not sabun or not knox_id or not group_id:
        raise KeycloakError("Keycloak 필수 식별 claim이 누락되었습니다.")

    groups = _normalize_string_list(claims.get("groups"))
    affiliation = _parse_affiliation_group(groups)
    realm_access = claims.get("realm_access")
    realm_roles = _normalize_string_list(
        realm_access.get("roles") if isinstance(realm_access, dict) else []
    )
    client_roles = _client_roles(claims)
    portal_roles = set(client_roles.get(settings.OIDC_CLIENT_ID, []))
    if not portal_roles.intersection(PORTAL_ROLES):
        raise KeycloakError("portal-user 또는 portal-admin 역할이 필요합니다.")

    return KeycloakIdentity(
        subject=subject,
        sabun=sabun,
        knox_id=knox_id,
        affiliation_group_id=group_id,
        affiliation=affiliation,
        groups=groups,
        realm_roles=realm_roles,
        client_roles=client_roles,
        claims=claims,
    )


def save_token_session(*, request: HttpRequest, token_set: dict[str, Any]) -> None:
    """token 원문과 만료 시각을 서버 측 Django session에만 저장합니다."""

    expires_in = max(int(token_set.get("expires_in") or 0), 0)
    request.session[TOKEN_SESSION_KEY] = {
        "access_token": str(token_set.get("access_token") or ""),
        "refresh_token": str(token_set.get("refresh_token") or ""),
        "id_token": str(token_set.get("id_token") or ""),
        "expires_at": int(time.time()) + expires_in,
    }


def refresh_session_if_needed(*, request: HttpRequest) -> dict[str, Any] | None:
    """access token 만료 30초 전이면 갱신하고 현재 token set을 반환합니다."""

    stored = request.session.get(TOKEN_SESSION_KEY)
    if not isinstance(stored, dict):
        return None
    if int(stored.get("expires_at") or 0) > int(time.time()) + 30:
        return stored
    refresh_token = str(stored.get("refresh_token") or "")
    if not refresh_token:
        return None
    try:
        token_set = refresh_tokens(refresh_token=refresh_token)
    except KeycloakError:
        request.session.pop(TOKEN_SESSION_KEY, None)
        return None
    if not token_set.get("refresh_token"):
        token_set["refresh_token"] = refresh_token
    if not token_set.get("id_token"):
        token_set["id_token"] = str(stored.get("id_token") or "")
    save_token_session(request=request, token_set=token_set)
    refreshed = request.session.get(TOKEN_SESSION_KEY)
    return refreshed if isinstance(refreshed, dict) else None


class KeycloakAdminClient:
    """읽기 전용 service account로 group 멤버와 client role을 조회합니다."""

    def __init__(self, *, base_url: str, realm: str, client_id: str, client_secret: str):
        self.base_url = base_url.rstrip("/")
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = ""
        self._expires_at = 0

    @classmethod
    def from_settings(cls) -> "KeycloakAdminClient":
        """Django settings에서 Admin API client를 생성합니다."""

        values = {
            "base_url": settings.KEYCLOAK_INTERNAL_URL,
            "realm": settings.KEYCLOAK_REALM,
            "client_id": settings.KEYCLOAK_ADMIN_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
        }
        if not all(str(value or "").strip() for value in values.values()):
            raise KeycloakError("Keycloak Admin API 설정이 누락되었습니다.")
        return cls(**values)

    def _ensure_token(self) -> str:
        """service account token을 필요할 때 발급하거나 재사용합니다."""

        if self._access_token and self._expires_at > int(time.time()) + 30:
            return self._access_token
        token_url = f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/token"
        try:
            response = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=_timeout(),
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise KeycloakError("Keycloak service account 인증에 실패했습니다.") from exc
        self._access_token = str(payload.get("access_token") or "")
        if not self._access_token:
            raise KeycloakError("Keycloak service account token이 없습니다.")
        self._expires_at = int(time.time()) + int(payload.get("expires_in") or 0)
        return self._access_token

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """Admin API GET 요청을 실행하고 JSON을 반환합니다."""

        url = f"{self.base_url}/admin/realms/{self.realm}{path}"
        try:
            response = requests.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self._ensure_token()}"},
                timeout=_timeout(),
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise KeycloakError(f"Keycloak Admin API 조회에 실패했습니다: {path}") from exc

    def _paged(self, path: str) -> list[dict[str, Any]]:
        """Keycloak pagination을 끝까지 조회합니다."""

        result: list[dict[str, Any]] = []
        first = 0
        while True:
            page = self._get(path, params={"first": first, "max": 100})
            if not isinstance(page, list):
                raise KeycloakError("Keycloak 목록 응답 형식이 올바르지 않습니다.")
            rows = [row for row in page if isinstance(row, dict)]
            result.extend(rows)
            if len(rows) < 100:
                return result
            first += len(rows)

    def get_affiliation_members(self, *, group_id: str) -> list[dict[str, str]]:
        """소속 parent group의 viewer/member/manager 멤버와 역할을 반환합니다."""

        group = self._get(f"/groups/{group_id}")
        subgroups = self._get(f"/groups/{group_id}/children")
        if not isinstance(subgroups, list):
            raise KeycloakError("Keycloak 소속 group을 찾을 수 없습니다.")
        by_subject: dict[str, dict[str, str]] = {}
        rank = {"viewer": 1, "member": 2, "manager": 3}
        for subgroup in subgroups:
            if not isinstance(subgroup, dict):
                continue
            role = str(subgroup.get("name") or "")
            child_id = str(subgroup.get("id") or "")
            if role not in AFFILIATION_ROLES or not child_id:
                continue
            for user in self._paged(f"/groups/{child_id}/members"):
                subject = str(user.get("id") or "")
                email = str(user.get("email") or "").strip()
                current = by_subject.get(subject)
                if subject and email and (current is None or rank[role] > rank[current["role"]]):
                    by_subject[subject] = {"email": email, "role": role}
        return list(by_subject.values())

    def get_client_role_members(self, *, client_id: str, role: str) -> list[dict[str, str]]:
        """지정 client role의 사용자 목록을 반환합니다."""

        clients = self._get("/clients", params={"clientId": client_id})
        if not isinstance(clients, list) or len(clients) != 1:
            raise KeycloakError(f"Keycloak client를 유일하게 찾을 수 없습니다: {client_id}")
        internal_id = str(clients[0].get("id") or "")
        users = self._paged(f"/clients/{internal_id}/roles/{role}/users")
        return [
            {"email": str(user.get("email") or "").strip(), "role": role}
            for user in users
            if str(user.get("email") or "").strip()
        ]


class KeycloakProvisioningClient(KeycloakAdminClient):
    """cutover 전용 service account로 검증된 사용자/group/role 상태를 반영합니다."""

    @classmethod
    def from_settings(cls) -> "KeycloakProvisioningClient":
        """쓰기 권한이 분리된 migration client 설정을 사용합니다."""

        values = {
            "base_url": settings.KEYCLOAK_INTERNAL_URL,
            "realm": settings.KEYCLOAK_REALM,
            "client_id": settings.KEYCLOAK_MIGRATION_CLIENT_ID,
            "client_secret": settings.KEYCLOAK_MIGRATION_CLIENT_SECRET,
        }
        if not all(str(value or "").strip() for value in values.values()):
            raise KeycloakError("Keycloak migration client 설정이 누락되었습니다.")
        return cls(**values)

    def _write(self, method: str, path: str, *, payload: Any = None) -> requests.Response:
        """Admin API 쓰기 요청을 실행합니다."""

        url = f"{self.base_url}/admin/realms/{self.realm}{path}"
        try:
            response = requests.request(
                method,
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._ensure_token()}",
                    "Content-Type": "application/json",
                },
                timeout=_timeout(),
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            raise KeycloakError(f"Keycloak Admin API 쓰기에 실패했습니다: {path}") from exc

    def _resolve_client(self, *, client_id: str) -> str:
        """clientId를 Keycloak 내부 UUID로 변환합니다."""

        clients = self._get("/clients", params={"clientId": client_id})
        if not isinstance(clients, list) or len(clients) != 1:
            raise KeycloakError(f"Keycloak client를 유일하게 찾을 수 없습니다: {client_id}")
        return str(clients[0].get("id") or "")

    def resolve_group_id(self, *, path: str) -> str:
        """전체 group path를 순회해 group UUID를 반환합니다."""

        parts = [part for part in str(path).split("/") if part]
        groups = self._get("/groups", params={"search": parts[0], "exact": "true"})
        candidates = [group for group in groups if isinstance(group, dict)] if isinstance(groups, list) else []
        current = next((group for group in candidates if group.get("name") == parts[0]), None)
        if current is None:
            raise KeycloakError(f"Keycloak group이 없습니다: {path}")
        for part in parts[1:]:
            group_id = str(current.get("id") or "")
            current = self._get(f"/groups/{group_id}")
            subgroups = self._get(f"/groups/{group_id}/children")
            current = next(
                (group for group in subgroups if isinstance(group, dict) and group.get("name") == part),
                None,
            )
            if current is None:
                raise KeycloakError(f"Keycloak group이 없습니다: {path}")
        return str(current.get("id") or "")

    def ensure_user(self, *, user: dict[str, Any]) -> str:
        """사용자 기본 정보와 필수 속성을 멱등 upsert합니다."""

        username = str(user["username"])
        matches = self._get(
            "/users",
            params={"username": username, "exact": "true"},
        )
        rows = [row for row in matches if isinstance(row, dict)] if isinstance(matches, list) else []
        if len(rows) > 1:
            raise KeycloakError(f"Keycloak 중복 사용자가 있습니다: {username}")
        payload = {
            "username": username,
            "enabled": True,
            "email": user["email"],
            "firstName": user.get("first_name", ""),
            "lastName": user.get("last_name", ""),
            "attributes": {
                "sabun": [user["sabun"]],
                "affiliation_group_id": [user["affiliation_group_id"]],
            },
        }
        if not rows:
            response = self._write("POST", "/users", payload=payload)
            location = response.headers.get("Location", "")
            user_id = location.rstrip("/").rsplit("/", maxsplit=1)[-1]
            if not user_id:
                raise KeycloakError(f"생성된 Keycloak 사용자 ID가 없습니다: {username}")
        else:
            user_id = str(rows[0].get("id") or "")
            self._write("PUT", f"/users/{user_id}", payload={**rows[0], **payload})
        return user_id

    def replace_affiliation_group(self, *, user_id: str, group_path: str) -> None:
        """사용자의 affiliation role group을 정확히 하나로 맞춥니다."""

        current = self._get(f"/users/{user_id}/groups")
        for group in current if isinstance(current, list) else []:
            path = str(group.get("path") or "") if isinstance(group, dict) else ""
            group_id = str(group.get("id") or "") if isinstance(group, dict) else ""
            if path.startswith(AFFILIATION_PREFIX) and group_id:
                self._write("DELETE", f"/users/{user_id}/groups/{group_id}")
        target_id = self.resolve_group_id(path=group_path)
        self._write("PUT", f"/users/{user_id}/groups/{target_id}")

    def replace_client_roles(self, *, user_id: str, client_id: str, roles: list[str]) -> None:
        """Portal client role mapping을 계획의 정확한 집합으로 교체합니다."""

        internal_id = self._resolve_client(client_id=client_id)
        current = self._get(f"/users/{user_id}/role-mappings/clients/{internal_id}")
        current_rows = [row for row in current if isinstance(row, dict)] if isinstance(current, list) else []
        if current_rows:
            self._write(
                "DELETE",
                f"/users/{user_id}/role-mappings/clients/{internal_id}",
                payload=current_rows,
            )
        desired = [self._get(f"/clients/{internal_id}/roles/{role}") for role in sorted(set(roles))]
        if desired:
            self._write(
                "POST",
                f"/users/{user_id}/role-mappings/clients/{internal_id}",
                payload=desired,
            )

    def get_user_state(self, *, username: str, client_id: str) -> dict[str, Any]:
        """이관 비교에 필요한 사용자 group/client role 현재 상태를 반환합니다."""

        matches = self._get(
            "/users",
            params={"username": username, "exact": "true"},
        )
        rows = [row for row in matches if isinstance(row, dict)] if isinstance(matches, list) else []
        if len(rows) != 1:
            raise KeycloakError(f"Keycloak 사용자를 유일하게 찾을 수 없습니다: {username}")
        user_id = str(rows[0].get("id") or "")
        groups = self._get(f"/users/{user_id}/groups")
        internal_id = self._resolve_client(client_id=client_id)
        roles = self._get(f"/users/{user_id}/role-mappings/clients/{internal_id}")
        return {
            "groups": sorted(
                str(group.get("path") or "")
                for group in groups if isinstance(group, dict)
            ),
            "client_roles": sorted(
                str(role.get("name") or "")
                for role in roles if isinstance(role, dict)
            ),
        }
