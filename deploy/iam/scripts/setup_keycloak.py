#!/usr/bin/env python3
"""권한관리 웹용 Keycloak client·플랫폼 관리자 그룹·관리 이벤트·org client 관리 권한을 멱등 준비합니다.

관리자 연결값은 환경변수로만 받습니다. 기본은 조회만 하는 dry-run이며 --apply로 적용합니다.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

CLIENT_ID = "iam"
GROUP_PARENT = "iam"
GROUP_ADMINS = "platform-admins"
# 권한관리 웹이 사용자·그룹·앱 역할 매핑을 조회·수정하는 데 필요한 realm-management role만 허용합니다.
# client 설정(secret 포함)을 읽는 view-clients는 주지 않습니다.
ADMIN_ROLES = ("view-users", "query-users", "query-groups", "manage-users")
DEFAULT_SCOPES = ("basic", "profile", "roles")
# 소속별 역할을 보관하는 client(deploy/keycloak의 org_sync가 만듦). 플랫폼 관리자는 세분화 관리 권한(v2)으로
# 이 client 하나만 조회·관리·역할 부여·복합 역할 편집할 수 있습니다. 다른 client와 secret은 볼 수 없습니다.
ORG_CLIENT = "org"
ORG_PERMISSION = "iam-org-client"
ORG_POLICY = "iam-platform-admins"
ORG_SCOPES = ["view", "manage", "map-roles", "map-roles-composite"]


class SetupError(Exception):
    """서버 응답 원문과 비밀값 없이 보고할 오류입니다."""


class NoRedirect(HTTPRedirectHandler):
    """인증 헤더를 다른 주소로 재전송하지 않습니다."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_url(url: str, name: str) -> str:
    """HTTPS 또는 loopback HTTP 주소만 허용합니다."""
    parsed = urlsplit(url)
    try:
        loopback = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        loopback = False
    if (not parsed.hostname or parsed.username or parsed.query or parsed.fragment
            or parsed.scheme != "https" and not (parsed.scheme == "http" and loopback)):
        raise SetupError(f"{name}에는 HTTPS 주소 또는 loopback HTTP 주소를 지정하세요.")
    return url.rstrip("/")


class Admin:
    """대상 realm의 Keycloak Admin API를 호출합니다."""

    def __init__(self, url: str, realm: str):
        self.url = check_url(url, "KEYCLOAK_ADMIN_URL")
        self.root = "/admin/realms/" + quote(realm, safe="")
        self.opener = build_opener(NoRedirect(), HTTPSHandler(
            context=ssl.create_default_context(cafile=os.environ.get("KEYCLOAK_CA_FILE") or None)))
        self.token = ""

    def send(self, method: str, path: str, data=None, form=False):
        body = None
        headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
        if data is not None:
            body = urlencode(data).encode() if form else json.dumps(data).encode()
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            with self.opener.open(Request(self.url + path, data=body, headers=headers, method=method), timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            raise SetupError(f"Keycloak {method} 요청 실패 (HTTP {exc.code}).") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise SetupError("Keycloak 연결 또는 응답 처리 실패.") from None

    def login(self):
        username = os.environ.get("KEYCLOAK_ADMIN_USERNAME")
        password = os.environ.get("KEYCLOAK_ADMIN_PASSWORD")
        if not username or not password:
            raise SetupError("KEYCLOAK_ADMIN_USERNAME, KEYCLOAK_ADMIN_PASSWORD를 지정하세요.")
        realm = quote(os.environ.get("KEYCLOAK_ADMIN_REALM", "master"), safe="")
        token = self.send("POST", f"/realms/{realm}/protocol/openid-connect/token", {
            "grant_type": "password", "client_id": "admin-cli", "username": username, "password": password,
        }, form=True)
        self.token = (token or {}).get("access_token", "")
        if not self.token:
            raise SetupError("관리자 토큰을 발급받지 못했습니다.")

    def call(self, method: str, path: str = "", data=None, **query):
        url = self.root + (f"/{path}" if path else "")
        if query:
            url += "?" + urlencode(query)
        return self.send(method, url, data)


def one(items: list, field: str, value: str):
    """정확히 일치하는 객체 하나를 고릅니다."""
    matches = [item for item in items or [] if item.get(field) == value]
    if len(matches) > 1:
        raise SetupError(f"같은 {field} '{value}'가 여러 개입니다.")
    return matches[0] if matches else None


def client_definition(public_url: str) -> dict:
    """브라우저 전용 public client입니다. 관리 role은 scope mapping으로만 토큰에 넣습니다."""
    parsed = urlsplit(public_url)
    return {
        "clientId": CLIENT_ID, "name": "권한관리", "protocol": "openid-connect", "enabled": True,
        "publicClient": True, "standardFlowEnabled": True, "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": False, "serviceAccountsEnabled": False, "fullScopeAllowed": False,
        "rootUrl": public_url, "baseUrl": "/", "redirectUris": [public_url + "/*"],
        "webOrigins": [f"{parsed.scheme}://{parsed.netloc}"],
        "attributes": {"pkce.code.challenge.method": "S256", "post.logout.redirect.uris": public_url + "/*"},
    }


class Setup:
    """현재 상태를 조회해 필요한 변경만 계획하고 적용합니다."""

    def __init__(self, api: Admin, public_url: str):
        self.api = api
        self.definition = client_definition(public_url)
        self.plan: list[str] = []

    def inspect(self):
        api = self.api
        found = api.call("GET", "clients", clientId="realm-management")
        self.rm = one(found, "clientId", "realm-management")
        if not self.rm:
            raise SetupError("realm-management client가 없습니다.")
        roles = {role["name"]: role for role in api.call("GET", f"clients/{self.rm['id']}/roles")}
        missing = [name for name in ADMIN_ROLES if name not in roles]
        if missing:
            raise SetupError("realm-management role이 없습니다: " + ",".join(missing))
        self.roles = [roles[name] for name in ADMIN_ROLES]
        self.client = one(api.call("GET", "clients", clientId=CLIENT_ID), "clientId", CLIENT_ID)
        if self.client is None:
            self.plan.append(f"client '{CLIENT_ID}' 생성")
        else:
            current = api.call("GET", f"clients/{self.client['id']}")
            if not current.get("publicClient"):
                raise SetupError(f"기존 client '{CLIENT_ID}'가 public client가 아닙니다. 수동으로 확인하세요.")
            self.plan.append(f"client '{CLIENT_ID}' 주소·흐름 설정 갱신")
        parent = one(api.call("GET", "groups", search=GROUP_PARENT, exact="true"), "name", GROUP_PARENT)
        self.parent = parent
        self.admins = None
        if parent:
            children = api.call("GET", f"groups/{parent['id']}/children", max=100)
            self.admins = one(children, "name", GROUP_ADMINS)
        if self.admins is None:
            self.plan.append(f"그룹 /{GROUP_PARENT}/{GROUP_ADMINS} 생성")
        self.plan.append("그룹·client에 관리 role " + ",".join(ADMIN_ROLES) + " 연결")
        events = api.call("GET", "events/config")
        self.events = events
        if not (events.get("adminEventsEnabled") and events.get("adminEventsDetailsEnabled")):
            self.plan.append("관리 이벤트(상세 포함) 기록 켜기")
        self.inspect_org_permission()

    def inspect_org_permission(self):
        """플랫폼 관리자가 org client 하나만 관리하도록 세분화 관리 권한을 계획합니다."""
        api = self.api
        self.org = one(api.call("GET", "clients", clientId=ORG_CLIENT), "clientId", ORG_CLIENT)
        if self.org is None:
            raise SetupError(f"client '{ORG_CLIENT}'가 없습니다. 소속 역할 반영(make keycloak-org-sync KEYCLOAK_ORG_APPLY=1)을 먼저 실행하세요.")
        self.realm = api.call("GET")
        if not self.realm.get("adminPermissionsEnabled"):
            self.plan.append("realm 세분화 관리 권한(admin permissions v2) 켜기")
        self.plan.append(f"/{GROUP_PARENT}/{GROUP_ADMINS}에 client '{ORG_CLIENT}' 관리 권한({', '.join(ORG_SCOPES)}) 부여")

    def apply(self):
        api = self.api
        if self.client is None:
            api.call("POST", "clients", self.definition)
            self.client = one(api.call("GET", "clients", clientId=CLIENT_ID), "clientId", CLIENT_ID)
        else:
            current = api.call("GET", f"clients/{self.client['id']}")
            attributes = {**current.get("attributes", {}), **self.definition["attributes"]}
            api.call("PUT", f"clients/{self.client['id']}", {**current, **self.definition, "attributes": attributes})
        client_path = f"clients/{self.client['id']}"
        defaults = {scope["name"] for scope in api.call("GET", client_path + "/default-client-scopes")}
        for scope in api.call("GET", "client-scopes"):
            if scope["name"] in DEFAULT_SCOPES and scope["name"] not in defaults:
                api.call("PUT", client_path + f"/default-client-scopes/{scope['id']}")
        api.call("POST", client_path + f"/scope-mappings/clients/{self.rm['id']}", self.roles)
        if self.parent is None:
            api.call("POST", "groups", {"name": GROUP_PARENT})
            self.parent = one(api.call("GET", "groups", search=GROUP_PARENT, exact="true"), "name", GROUP_PARENT)
        if self.admins is None:
            api.call("POST", f"groups/{self.parent['id']}/children", {"name": GROUP_ADMINS})
            children = api.call("GET", f"groups/{self.parent['id']}/children", max=100)
            self.admins = one(children, "name", GROUP_ADMINS)
        api.call("POST", f"groups/{self.admins['id']}/role-mappings/clients/{self.rm['id']}", self.roles)
        if not (self.events.get("adminEventsEnabled") and self.events.get("adminEventsDetailsEnabled")):
            api.call("PUT", "events/config", {**self.events, "adminEventsEnabled": True, "adminEventsDetailsEnabled": True})
        self.apply_org_permission()

    def apply_org_permission(self):
        api = self.api
        if not self.realm.get("adminPermissionsEnabled"):
            # 앞에서 읽은 realm 전체를 다시 쓰면 방금 켠 관리 이벤트 설정이 되돌아가므로 이 항목만 보냅니다.
            api.call("PUT", "", {"adminPermissionsEnabled": True})
        permissions = one(api.call("GET", "clients", clientId="admin-permissions"), "clientId", "admin-permissions")
        if permissions is None:
            raise SetupError("admin-permissions client가 없습니다. Keycloak 버전(26.2 이상)과 세분화 관리 권한 기능을 확인하세요.")
        base = f"clients/{permissions['id']}/authz/resource-server"
        policy = one(api.call("GET", f"{base}/policy", name=ORG_POLICY), "name", ORG_POLICY)
        if policy is None:
            api.call("POST", f"{base}/policy/group", {"name": ORG_POLICY, "logic": "POSITIVE",
                                                      "groups": [{"id": self.admins["id"], "extendChildren": False}]})
            policy = one(api.call("GET", f"{base}/policy", name=ORG_POLICY), "name", ORG_POLICY)
        definition = {"name": ORG_PERMISSION, "resourceType": "Clients", "resources": [self.org["id"]],
                      "scopes": ORG_SCOPES, "policies": [policy["id"]], "decisionStrategy": "UNANIMOUS",
                      "description": "권한관리 웹: 소속별 역할 client만 관리"}
        current = one(api.call("GET", f"{base}/permission", name=ORG_PERMISSION), "name", ORG_PERMISSION)
        if current is None:
            api.call("POST", f"{base}/permission/scope", definition)
        else:
            api.call("PUT", f"{base}/permission/scope/{current['id']}", {**current, **definition})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--realm", default=os.environ.get("KEYCLOAK_TARGET_REALM", "etch"))
    parser.add_argument("--public-url", default=os.environ.get("IAM_PUBLIC_URL", ""), help="권한관리 웹 공개 주소")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if not args.realm or args.realm == "master":
            raise SetupError("업무 realm을 지정하세요. master에는 적용하지 않습니다.")
        public_url = check_url(args.public_url, "IAM_PUBLIC_URL")
        api = Admin(os.environ.get("KEYCLOAK_ADMIN_URL", ""), args.realm)
        api.login()
        setup = Setup(api, public_url)
        setup.inspect()
        for line in setup.plan:
            print("계획: " + line)
        if args.apply:
            setup.apply()
            print("적용 완료. /iam/platform-admins 가입은 Admin Console에서 지정하세요.")
        else:
            print("dry-run 완료. 적용하려면 --apply를 지정하세요.")
        return 0
    except SetupError as exc:
        print(f"권한관리 Keycloak 설정 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
