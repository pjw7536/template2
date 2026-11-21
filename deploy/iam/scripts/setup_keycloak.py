#!/usr/bin/env python3
"""Etch Members에 필요한 Keycloak 조직 역할·client·권한·카탈로그를 반영합니다."""

from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

KEYCLOAK = Path(__file__).resolve().parents[2] / "keycloak"
sys.path.insert(0, str(KEYCLOAK / "scripts"))
from access_apply import Apply as AccessApply, load_catalog  # noqa: E402
from init_sdwt import Admin, SetupError, mapper_equal, one, segment, user_mapper  # noqa: E402
from org_sync import OrgSync  # noqa: E402

CLIENT_ID = "iam"
GROUP_ADMINS = "platform-admins"
ADMIN_ROLES = ("view-users", "query-users", "query-groups", "manage-users")
DEFAULT_SCOPES = {"basic", "profile", "roles"}
PROFILE_MAPPERS = (user_mapper("display_name"), user_mapper("loginid"))
ORG_PERMISSION = "iam-org-client"
ORG_POLICY = "iam-platform-admins"
ORG_SCOPES = ["view", "manage", "map-roles", "map-roles-composite"]


def check_public_url(url: str) -> str:
    """운영은 HTTPS origin, 개발은 loopback HTTP origin을 받습니다."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise SetupError("IAM_PUBLIC_URL의 주소 형식을 확인하세요.") from None
    host = parsed.hostname
    loopback = host == "localhost"
    if host and not loopback:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
    if (not host or parsed.username is not None or parsed.query or parsed.fragment or
            parsed.path.rstrip("/") or port == 0 or any(char.isspace() for char in url) or
            parsed.scheme != "https" and not (parsed.scheme == "http" and loopback)):
        raise SetupError("IAM_PUBLIC_URL에는 경로 없는 HTTPS 주소 또는 loopback HTTP 주소를 지정하세요.")
    return url.rstrip("/")


def client_definition(public_url: str) -> dict:
    return {
        "clientId": CLIENT_ID, "name": "Etch Members", "protocol": "openid-connect", "enabled": True,
        "publicClient": True, "standardFlowEnabled": True, "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": False, "serviceAccountsEnabled": False, "fullScopeAllowed": False,
        "rootUrl": public_url, "baseUrl": "/", "redirectUris": [public_url + "/*"],
        "webOrigins": [public_url],
        "attributes": {"pkce.code.challenge.method": "S256", "post.logout.redirect.uris": public_url + "/*"},
    }


class Setup:
    """IAM client·그룹과 IAM이 관리하는 세분화된 권한을 조회해 필요한 변경을 반영합니다."""

    def __init__(self, api: Admin, public_url: str, org: dict | None, usernames: list[str]):
        self.api, self.org, self.usernames = api, org, usernames
        self.definition = client_definition(public_url)
        self.plan: list[str] = []

    def find_client(self, client_id: str):
        return one(self.api.call("GET", "clients", query={"clientId": client_id}), "clientId", client_id)

    def inspect(self):
        api = self.api
        realm = api.call("GET")
        self.fgap_enabled = realm.get("adminPermissionsEnabled") is True
        if not self.fgap_enabled:
            features = api.server_info().get("features", [])
            if not any(item["name"] == "ADMIN_FINE_GRAINED_AUTHZ_V2" and item.get("enabled") for item in features):
                raise SetupError("Keycloak에서 세분화 관리 권한 v2를 지원해야 합니다.")
            self.plan.append("realm의 세분화 관리 권한 v2 활성화")
        self.rm = self.find_client("realm-management")
        if self.rm is None:
            raise SetupError("realm-management client가 없습니다.")
        roles = {role["name"]: role for role in api.pages(f"clients/{segment(self.rm['id'])}/roles")}
        missing = sorted(set(ADMIN_ROLES) - roles.keys())
        if missing:
            raise SetupError("realm-management role이 없습니다: " + ", ".join(missing))
        self.roles = {name: roles[name] for name in ADMIN_ROLES}
        self.inspect_client()
        self.inspect_group()
        self.events = api.call("GET", "events/config")
        if not (self.events.get("adminEventsEnabled") and self.events.get("adminEventsDetailsEnabled")):
            self.plan.append("realm의 관리 이벤트 상세 기록 활성화")
        self.inspect_permissions()

    def inspect_client(self):
        api = self.api
        self.client = self.find_client(CLIENT_ID)
        self.current_client = None
        self.client_changed = False
        attached = set()
        mappers = []
        if self.client is None:
            self.plan.append("client 'iam' 생성")
        else:
            path = f"clients/{segment(self.client['id'])}"
            self.current_client = current = api.call("GET", path)
            if not current.get("publicClient"):
                raise SetupError("기존 client 'iam'가 public client가 아닙니다.")
            self.client_changed = (
                any(current.get(key) != value for key, value in self.definition.items() if key != "attributes")
                or any((current.get("attributes") or {}).get(key) != value
                       for key, value in self.definition["attributes"].items())
            )
            if self.client_changed:
                self.plan.append("client 'iam'의 표시 이름·주소·흐름 갱신")
            attached = {scope["name"] for scope in api.call("GET", path + "/default-client-scopes")}
            mappers = api.call("GET", path + "/protocol-mappers/models")
        self.profile_mappers = []
        for desired in PROFILE_MAPPERS:
            mapper = one(mappers, "name", desired["name"])
            if mapper is None or not mapper_equal(mapper, desired):
                self.profile_mappers.append((mapper, desired))
                self.plan.append(f"client 'iam'의 {desired['name']} token mapper 반영")
        scopes = {scope["name"]: scope for scope in api.call("GET", "client-scopes")}
        missing = sorted(DEFAULT_SCOPES - scopes.keys())
        if missing:
            raise SetupError("필수 client scope가 없습니다: " + ", ".join(missing))
        self.missing_scopes = [scopes[name] for name in sorted(DEFAULT_SCOPES - attached)]
        self.client_roles = self.missing_roles(self.client, "clients", "scope-mappings")
        if self.missing_scopes or self.client_roles:
            self.plan.append("client 'iam'의 기본 scope·관리 역할 연결")

    def inspect_group(self):
        api = self.api
        parents = api.pages("groups", search=CLIENT_ID, exact="true", populateHierarchy="false")
        self.parent = one(parents, "path", f"/{CLIENT_ID}")
        self.admins = None
        if self.parent:
            self.admins = one(api.pages(f"groups/{segment(self.parent['id'])}/children"), "name", GROUP_ADMINS)
        if self.admins is None:
            self.plan.append("그룹 /iam/platform-admins 생성")
        self.group_roles = self.missing_roles(self.admins, "groups", "role-mappings")
        if self.group_roles:
            self.plan.append("플랫폼 관리자 그룹의 관리 역할 연결")
        self.join = []
        for username in self.usernames:
            user = one(api.pages("users", username=username, exact="true"), "username", username)
            if user is None:
                raise SetupError(f"IAM_PLATFORM_ADMIN_USERNAMES의 기존 사용자 '{username}'를 찾지 못했습니다.")
            user_path = f"users/{segment(user['id'])}/groups"
            if self.admins is None or not one(api.pages(user_path), "id", self.admins["id"]):
                self.join.append(user_path)
        if self.join:
            self.plan.append(f"지정한 기존 사용자 {len(self.join)}명을 플랫폼 관리자 그룹에 추가")

    def missing_roles(self, item, collection, mapping):
        assigned = set()
        if item:
            path = f"{collection}/{segment(item['id'])}/{mapping}/clients/{segment(self.rm['id'])}"
            assigned = {role["name"] for role in self.api.call("GET", path)}
        return [role for name, role in self.roles.items() if name not in assigned]

    def inspect_permissions(self):
        self.policy = self.permission = None
        self.policy_changed = self.permission_changed = True
        if self.fgap_enabled:
            base = self.permissions_path()
            self.policy = self.find_authz(base, "policy", ORG_POLICY, "group")
            if self.policy and self.admins:
                policy = self.api.call("GET", f"{base}/policy/group/{segment(self.policy['id'])}")
                self.policy_changed = (
                    policy.get("logic") != "POSITIVE"
                    or policy.get("groups") != self.policy_definition()["groups"]
                )
            self.permission = self.find_authz(base, "permission", ORG_PERMISSION, "scope")
            if self.permission and self.org and self.policy:
                path = f"{base}/permission/{segment(self.permission['id'])}"
                resources = {item["name"] for item in self.api.call("GET", f"{path}/resources")}
                scopes = {item["name"] for item in self.api.call("GET", f"{path}/scopes")}
                policies = {item["id"] for item in self.api.call("GET", f"{path}/associatedPolicies")}
                self.permission_changed = (
                    self.permission.get("resourceType") != "Clients"
                    or self.permission.get("decisionStrategy") != "UNANIMOUS"
                    or self.permission.get("logic") != "POSITIVE"
                    or resources != {self.org["id"]} or scopes != set(ORG_SCOPES)
                    or policies != {self.policy["id"]}
                )
        if self.policy_changed or self.permission_changed:
            self.plan.append("플랫폼 관리자 그룹에 client 'org'의 관리 권한 연결")

    def permissions_path(self):
        client = self.find_client("admin-permissions")
        if client is None:
            raise SetupError("admin-permissions client가 없습니다. 세분화 관리 권한 v2 상태를 확인하세요.")
        return f"clients/{segment(client['id'])}/authz/resource-server"

    def find_authz(self, base, endpoint, name, expected_type):
        item = one(self.api.call("GET", f"{base}/{endpoint}", query={"name": name}), "name", name)
        if item and item.get("type") != expected_type:
            raise SetupError(f"기존 Keycloak 권한 설정 '{name}'의 유형이 다릅니다.")
        return item

    def policy_definition(self):
        return {"name": ORG_POLICY, "logic": "POSITIVE",
                "groups": [{"id": self.admins["id"], "extendChildren": False}]}

    def enable_permissions(self):
        if not self.fgap_enabled:
            # realm 표현 전체를 보내면 다른 설정을 덮어쓸 수 있으므로 변경할 키만 보냅니다.
            self.api.call("PUT", data={"adminPermissionsEnabled": True})
            self.permissions_path()

    def apply(self):
        api = self.api
        base = self.permissions_path()
        if self.client is None:
            api.call("POST", "clients", self.definition)
            self.client = self.find_client(CLIENT_ID)
        elif self.client_changed:
            attributes = {**(self.current_client.get("attributes") or {}), **self.definition["attributes"]}
            api.call("PUT", f"clients/{segment(self.client['id'])}",
                     {**self.current_client, **self.definition, "attributes": attributes})
        client = f"clients/{segment(self.client['id'])}"
        for scope in self.missing_scopes:
            api.call("PUT", f"{client}/default-client-scopes/{segment(scope['id'])}")
        mapper_path = client + "/protocol-mappers/models"
        for current, desired in self.profile_mappers:
            if current is None:
                api.call("POST", mapper_path, desired)
            else:
                config = {**(current.get("config") or {}), **desired["config"]}
                api.call("PUT", f"{mapper_path}/{segment(current['id'])}", {**current, **desired, "config": config})
        roles = f"clients/{segment(self.rm['id'])}"
        if self.client_roles:
            api.call("POST", f"{client}/scope-mappings/{roles}", self.client_roles)
        if self.parent is None:
            api.call("POST", "groups", {"name": CLIENT_ID})
            self.parent = one(api.pages("groups", search=CLIENT_ID, exact="true", populateHierarchy="false"),
                              "path", f"/{CLIENT_ID}")
        if self.admins is None:
            children = f"groups/{segment(self.parent['id'])}/children"
            api.call("POST", children, {"name": GROUP_ADMINS})
            self.admins = one(api.pages(children), "name", GROUP_ADMINS)
        if self.group_roles:
            api.call("POST", f"groups/{segment(self.admins['id'])}/role-mappings/{roles}", self.group_roles)
        if not (self.events.get("adminEventsEnabled") and self.events.get("adminEventsDetailsEnabled")):
            api.call("PUT", "events/config", {**self.events, "adminEventsEnabled": True, "adminEventsDetailsEnabled": True})
        self.apply_permissions(base)

    def apply_members(self):
        """역할·정책·카탈로그가 반영된 뒤 지정된 기존 사용자만 추가합니다."""
        for user_path in self.join:
            self.api.call("PUT", f"{user_path}/{segment(self.admins['id'])}")

    def apply_permissions(self, base):
        api = self.api
        if self.policy_changed:
            definition = self.policy_definition()
            path = f"{base}/policy/group"
            if self.policy is None:
                api.call("POST", path, definition)
                self.policy = self.find_authz(base, "policy", ORG_POLICY, "group")
            else:
                api.call("PUT", f"{path}/{segment(self.policy['id'])}", definition)
        if self.permission_changed:
            definition = {
                "name": ORG_PERMISSION, "resourceType": "Clients", "resources": [self.org["id"]],
                "scopes": ORG_SCOPES, "policies": [self.policy["id"]], "decisionStrategy": "UNANIMOUS",
                "logic": "POSITIVE", "description": "Etch Members: 소속별 역할 client만 관리",
            }
            path = f"{base}/permission/scope"
            if self.permission is None:
                api.call("POST", path, definition)
            else:
                api.call("PUT", f"{path}/{segment(self.permission['id'])}", definition)


def inspect(api, public_url, usernames, apps):
    """각 단계의 계획을 같은 관리자 세션과 realm으로 수집합니다."""
    org = OrgSync(api)
    org.inspect()
    iam = Setup(api, public_url, org.client, usernames)
    iam.inspect()
    access = AccessApply(api, apps)
    access.inspect(include_catalog=bool(iam.parent and org.client))
    return org, iam, access


def reconcile(api, public_url, usernames, apps, mode):
    org, iam, access = inspect(api, public_url, usernames, apps)
    plan = [*org.plan, *iam.plan, *access.plan]
    if not iam.parent or not org.client:
        plan.append("IAM 그룹에 앱 역할 카탈로그 게시")
    print(f"IAM 설정 대상 realm: {api.realm}", flush=True)
    for line in plan or ["변경 없음"]:
        print("계획: " + line, flush=True)
    if mode == "check":
        for line in [*org.warnings, *access.warnings]:
            print("경고: " + line)
        print("dry-run 완료.")
        return
    if mode == "apply" and plan:
        iam.enable_permissions()
        if org.plan:
            org.apply()
        iam.org = org.client
        if iam.plan:
            iam.apply()
        # org와 IAM 그룹의 내부 id가 정해진 뒤 카탈로그를 구성합니다.
        access = AccessApply(api, apps)
        access.inspect()
        if access.plan:
            access.apply()
        iam.apply_members()
        org, iam, access = inspect(api, public_url, usernames, apps)
    remaining = [*org.plan, *iam.plan, *access.plan]
    if remaining:
        raise SetupError("설정 검증 불일치: " + " / ".join(remaining))
    for line in [*org.warnings, *access.warnings]:
        print("경고: " + line)
    print("IAM Keycloak 설정 검증 통과.")
    if mode == "apply":
        print("IAM Keycloak 설정 적용 완료.")


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, help="IAM 환경 파일. 동일한 이름의 환경변수가 우선합니다.")
    parser.add_argument("--realm", default="")
    parser.add_argument("--public-url", default="")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="계획에 따라 적용하고 결과를 검증")
    mode.add_argument("--verify", action="store_true", help="조회로 적용 상태를 확인하고 차이가 있으면 실패")
    args = parser.parse_args()
    try:
        declared = read_env(args.env) if args.env else {}
        realm = args.realm or os.environ.get("KEYCLOAK_TARGET_REALM") or declared.get("KEYCLOAK_TARGET_REALM") or "etch"
        if not realm.strip() or realm != realm.strip() or realm.lower() == "master":
            raise SetupError("업무 realm을 지정하세요. master에는 적용하지 않습니다.")
        public_url = check_public_url(args.public_url or os.environ.get("IAM_PUBLIC_URL") or declared.get("IAM_PUBLIC_URL", ""))
        names = os.environ.get("IAM_PLATFORM_ADMIN_USERNAMES", declared.get("IAM_PLATFORM_ADMIN_USERNAMES", ""))
        usernames = list(dict.fromkeys(name.strip() for name in names.split(",") if name.strip()))
        apps = load_catalog(KEYCLOAK / "access/catalog.json")
        reconcile(Admin(realm), public_url, usernames, apps, "apply" if args.apply else "verify" if args.verify else "check")
        return 0
    except (SetupError, OSError) as exc:
        print(f"Etch Members Keycloak 설정 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
