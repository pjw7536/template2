#!/usr/bin/env python3
"""SDWT 그룹·앱 claim·신규 사용자를 기본 dry-run으로 초기 설정합니다."""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import os
from pathlib import Path
import ssl
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


BASE = Path(__file__).resolve().parents[1]
ROLES = ("admin", "user", "viewer")
PAGE_SIZE = 100
# CSV는 사내 claim 이름을 사용하고 저장 시 기존 Keycloak 속성으로 변환합니다.
CSV_ATTRIBUTES = {
    "sabun": "sabun",
    "loginid": "knox_id",
    "username": "display_name",
    "deptname": "department",
    "grdname_en": "grdname_en",
}


class SetupError(Exception):
    """개인정보와 서버 응답 원문 없이 보고할 초기 설정 오류입니다."""


def segment(value: str) -> str:
    """관리 API 경로의 식별자를 인코딩합니다."""
    return quote(value, safe="")


def read_csv(path: Path, required: set[str], optional: set[str]) -> list[dict]:
    """BOM을 허용하고 중복 헤더·잘못된 열 수·빈 파일을 거부합니다."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            fields = reader.fieldnames or []
            if (not required <= set(fields) or set(fields) - required - optional
                    or len(fields) != len(set(fields))):
                raise SetupError(f"CSV 헤더 오류. 필수: {','.join(sorted(required))}")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SetupError("CSV를 읽을 수 없습니다.") from exc
    if not rows:
        raise SetupError("CSV에 데이터 행이 없습니다.")
    for number, row in enumerate(rows, 2):
        if None in row or any(value is None for value in row.values()):
            raise SetupError(f"CSV {number}행: 열 수가 맞지 않습니다.")
        if any(value != value.strip() or any(ord(char) < 32 for char in value)
               for value in row.values()):
            raise SetupError(f"CSV {number}행: 앞뒤 공백 또는 제어문자가 있습니다.")
    return rows


def load_inputs(sdwts_path: Path, users_path: Path | None) -> tuple[dict, list]:
    """참조 목록 전체를 검증한 뒤 SDWT별 line과 사용자 입력을 반환합니다."""
    sdwts = {}
    for number, row in enumerate(read_csv(sdwts_path, {"user_sdwt_prod", "line_id"}, set()), 2):
        name, line = row["user_sdwt_prod"], row["line_id"]
        if not name or not line or "/" in name or name in {".", ".."} or name in sdwts:
            raise SetupError(f"SDWT CSV {number}행: 빈 값·중복 SDWT·잘못된 경로 이름입니다.")
        sdwts[name] = line
    users = read_csv(users_path, {"userid", "user_sdwt_prod"},
                     set(CSV_ATTRIBUTES) | {"mail"}) if users_path else []
    seen = {key: set() for key in ("userid", "sabun", "loginid", "mail")}
    for number, row in enumerate(users, 2):
        epid = row["userid"]
        if (not epid or len(epid) > 255 or any(char in epid for char in '/\\<>"&?#')
                or row["user_sdwt_prod"] and row["user_sdwt_prod"] not in sdwts):
            raise SetupError(f"사용자 CSV {number}행: EPID 또는 SDWT가 올바르지 않습니다.")
        for key, values in seen.items():
            value = row.get(key, "").casefold()
            if value and value in values:
                raise SetupError(f"사용자 CSV {number}행: {key} 중복입니다.")
            if value:
                values.add(value)
    return sdwts, users


class NoRedirect(HTTPRedirectHandler):
    """인증 헤더·비밀번호를 다른 주소로 재전송하지 않습니다."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Admin:
    """외부 의존성이 없는 Keycloak Admin API 클라이언트입니다."""

    def __init__(self, realm: str):
        self.realm = realm
        self.url = os.environ.get("KEYCLOAK_ADMIN_URL", "").rstrip("/")
        parsed = urlsplit(self.url)
        try:
            loopback = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            loopback = False
        if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.scheme != "https" and not (parsed.scheme == "http" and loopback)):
            raise SetupError("KEYCLOAK_ADMIN_URL에는 HTTPS 주소 또는 loopback HTTP 주소를 지정하세요.")
        self.opener = build_opener(NoRedirect(), HTTPSHandler(
            context=ssl.create_default_context(cafile=os.environ.get("KEYCLOAK_CA_FILE") or None)))
        self.token = ""
        self.expires = 0.0

    def _send(self, method: str, path: str, data=None, form=False, auth=True):
        body = (urlencode(data).encode() if form else json.dumps(data).encode()) if data is not None else None
        headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            with self.opener.open(Request(self.url + path, data=body, headers=headers, method=method), timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            raise SetupError(f"Keycloak {method} 요청 실패 (HTTP {exc.code}). 설정·권한을 확인하고 재실행하세요.") from None
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise SetupError("Keycloak 연결 또는 응답 처리 실패. 서버 상태를 확인하고 재실행하세요.") from None

    def login(self):
        """비밀값은 환경변수로만 받고 토큰은 프로세스 메모리에만 보관합니다."""
        secret = os.environ.get("KEYCLOAK_ADMIN_CLIENT_SECRET")
        client = os.environ.get("KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli")
        data = {"client_id": client}
        if secret:
            data.update(grant_type="client_credentials", client_secret=secret)
        else:
            username = os.environ.get("KEYCLOAK_ADMIN_USERNAME")
            password = os.environ.get("KEYCLOAK_ADMIN_PASSWORD")
            if not username or not password:
                raise SetupError("관리자 username/password 또는 client secret 환경변수가 필요합니다.")
            data.update(grant_type="password", username=username, password=password)
        realm = os.environ.get("KEYCLOAK_ADMIN_REALM", "master")
        token = self._send("POST", f"/realms/{segment(realm)}/protocol/openid-connect/token", data, form=True, auth=False)
        if not isinstance(token, dict) or not token.get("access_token"):
            raise SetupError("관리자 토큰을 발급받지 못했습니다.")
        self.token = token["access_token"]
        self.expires = time.monotonic() + int(token.get("expires_in", 60))

    def call(self, method: str, path: str = "", data=None, query=None):
        """짧은 관리자 토큰을 갱신하며 대상 realm 안에서만 요청합니다."""
        if time.monotonic() >= self.expires - 15:
            self.login()
        url = f"/admin/realms/{segment(self.realm)}" + (f"/{path}" if path else "")
        if query:
            url += "?" + urlencode(query)
        return self._send(method, url, data)

    def pages(self, path: str, **query) -> list:
        """기본 100건 제한 때문에 사용자·그룹이 누락되지 않도록 조회합니다."""
        result = []
        first = 0
        while True:
            page = self.call("GET", path, query={**query, "first": first, "max": PAGE_SIZE})
            if not isinstance(page, list):
                raise SetupError("Keycloak 목록 응답 형식이 올바르지 않습니다.")
            result.extend(page)
            if len(page) < PAGE_SIZE:
                return result
            first += len(page)


def one(items: list, field: str, value: str):
    """정확히 일치하는 하나의 객체만 선택합니다."""
    matches = [item for item in items if item.get(field) == value]
    if len(matches) > 1:
        raise SetupError("Keycloak 객체가 중복되어 하나로 식별되지 않습니다.")
    return matches[0] if matches else None


def check_clean_group(api: Admin, group: dict):
    """기존 그룹의 역할·소속 상속을 업무 권한과 섞지 않습니다."""
    detail = api.call("GET", f"groups/{segment(group['id'])}")
    mappings = api.call("GET", f"groups/{segment(group['id'])}/role-mappings")
    if detail.get("attributes") or mappings.get("realmMappings") or mappings.get("clientMappings"):
        raise SetupError("대상 SDWT 그룹에 속성 또는 역할 매핑이 있습니다. 별도 검토 후 실행하세요.")


def mapper_equal(current: dict, desired: dict) -> bool:
    """서버가 추가한 id와 기본값은 제외하고 mapper 계약을 비교합니다."""
    return (current.get("protocol") == desired["protocol"]
            and current.get("protocolMapper") == desired["protocolMapper"]
            and all(current.get("config", {}).get(key) == value for key, value in desired["config"].items()))


def user_mapper(claim: str) -> dict:
    """기존 Portal과 같은 실제 소속·EPID 출력 mapper를 만듭니다."""
    return {
        "name": claim, "protocol": "openid-connect", "consentRequired": False,
        "protocolMapper": "oidc-usermodel-property-mapper" if claim == "userid" else "oidc-usermodel-attribute-mapper",
        "config": {"user.attribute": "username" if claim == "userid" else claim,
                   "claim.name": claim, "jsonType.label": "String", "multivalued": "false",
                   "id.token.claim": "true", "access.token.claim": "true", "userinfo.token.claim": "true"},
    }


class Setup:
    """쓰기 전 전체 사전 검사와 반복 실행 가능한 설정 단계를 관리합니다."""

    def __init__(self, api: Admin, sdwts: dict, users: list, clients: list[str]):
        self.api, self.sdwts, self.users, self.client_names = api, sdwts, users, clients
        self.scope_definition = json.loads((BASE / "k8s/claims/sdwt-access-scope.json").read_text())
        self.scope = None
        self.clients = []
        self.parents = {}
        self.children = {}
        self.new_users = []
        self.existing_count = 0
        self.profile = None
        self.profile_changed = False
        self.missing_mappers = {}
        self.optional_detach = {}
        self.dedicated_remove = {}

    def inspect(self):
        """CSV·현재 realm·계정·mapper 충돌을 쓰기 전에 모두 검사합니다."""
        realm = self.api.call("GET")
        if realm.get("registrationEmailAsUsername"):
            raise SetupError("EPID username을 사용하려면 Email as username을 꺼야 합니다.")
        # 기본 그룹에 의한 뜻하지 않은 권한 부여를 숨기지 않습니다.
        if self.users and self.api.call("GET", "default-groups"):
            raise SetupError("realm 기본 그룹이 있습니다. 신규 사용자의 자동 권한을 검토한 뒤 별도 정리하세요.")
        self.inspect_profile()
        roots = self.api.pages("groups", populateHierarchy="false")
        for name in self.sdwts:
            parent = one(roots, "name", name)
            self.parents[name] = parent
            children = []
            if parent:
                check_clean_group(self.api, parent)
                children = self.api.pages(f"groups/{segment(parent['id'])}/children", briefRepresentation="false")
                for child in children:
                    if child["name"] in ROLES:
                        check_clean_group(self.api, child)
            self.children[name] = {role: one(children, "name", role) for role in ROLES}
        self.inspect_clients()
        self.inspect_users()

    def inspect_profile(self):
        """다른 프로필 정의는 보존하고 등록에 필요한 관리 속성만 준비합니다."""
        self.profile = self.api.call("GET", "users/profile")
        desired = json.loads((BASE / "k8s/claims/account-user-profile.json").read_text())
        keys = {"user_sdwt_prod", "line_id", *CSV_ATTRIBUTES.values()}
        attributes = self.profile.setdefault("attributes", [])
        for definition in desired["attributes"]:
            if definition["name"] not in keys:
                continue
            current = one(attributes, "name", definition["name"])
            if current is None:
                attributes.append(definition)
                self.profile_changed = True
            elif (current.get("permissions") != definition["permissions"]
                  or current.get("multivalued", False) != definition.get("multivalued", False)):
                raise SetupError("등록용 사용자 속성의 편집 권한·타입이 기존 계약과 다릅니다. 프로필을 먼저 검토하세요.")

    def inspect_clients(self):
        """선택 client의 중복 groups mapper와 기존 출력 계약 충돌을 막습니다."""
        scopes = self.api.call("GET", "client-scopes")
        self.scope = one(scopes, "name", self.scope_definition["name"])
        desired = self.scope_definition["protocolMappers"][0]
        if self.scope:
            if self.scope.get("protocol") != "openid-connect":
                raise SetupError("공통 scope의 protocol이 다릅니다.")
            mappings = self.api.call("GET", f"client-scopes/{segment(self.scope['id'])}/scope-mappings")
            if mappings.get("realmMappings") or mappings.get("clientMappings"):
                raise SetupError("공통 scope에 역할 제한이 있습니다. 무권한 사용자의 빈 그룹 발급을 보장할 수 없습니다.")
            mappers = self.api.call("GET", f"client-scopes/{segment(self.scope['id'])}/protocol-mappers/models")
            if len(mappers) != 1 or not mapper_equal(mappers[0], desired):
                raise SetupError("기존 sdwt-access-v1 scope의 mapper 계약이 다릅니다.")
        for name in self.client_names:
            found = self.api.call("GET", "clients", query={"clientId": name})
            client = one(found, "clientId", name)
            if not client:
                raise SetupError("요청한 client가 없습니다. 로그인 client를 먼저 등록하세요.")
            client = self.api.call("GET", f"clients/{segment(client['id'])}")
            if client.get("protocol") != "openid-connect":
                raise SetupError("SDWT 계약은 OIDC client에만 연결할 수 있습니다.")
            self.clients.append(client)
            endpoint = f"clients/{segment(client['id'])}"
            mappers = list(client.get("protocolMappers", []))
            # 로컬 import의 동일 mapper를 공통 scope로 이전할 때만 기존 mapper를 제거합니다.
            owned = [m for m in mappers if m.get("name") == desired["name"] and mapper_equal(m, desired)]
            self.dedicated_remove[client["id"]] = [m["id"] for m in owned]
            mappers = [m for m in mappers if m not in owned]
            defaults = self.api.call("GET", endpoint + "/default-client-scopes")
            optional = self.api.call("GET", endpoint + "/optional-client-scopes")
            self.optional_detach[client["id"]] = []
            for scope in defaults + optional:
                if scope["name"] == self.scope_definition["name"]:
                    continue
                extra = self.api.call("GET", f"client-scopes/{segment(scope['id'])}/protocol-mappers/models")
                # 기본 microprofile-jwt의 groups는 realm role 배열이므로 함께 발급할 수 없습니다.
                if scope in optional and scope["name"] == "microprofile-jwt":
                    group_mappers = [m for m in extra if m.get("config", {}).get("claim.name") == "groups"]
                    if len(group_mappers) == 1 and group_mappers[0].get("protocolMapper") == "oidc-usermodel-realm-role-mapper":
                        self.optional_detach[client["id"]].append(scope["id"])
                        continue
                # 소속 claim이 optional scope에만 있으면 항상 발급된다고 볼 수 없습니다.
                if scope in optional and any(m.get("config", {}).get("claim.name") in {"userid", "user_sdwt_prod", "line_id"} for m in extra):
                    raise SetupError("선택 scope에 소속·EPID mapper가 있습니다. 중복 출력 계약을 먼저 정리하세요.")
                mappers.extend(extra)
            if any(m.get("config", {}).get("claim.name") == "groups" for m in mappers):
                raise SetupError("선택 client에 기존 groups mapper가 있습니다. 공통 scope와의 중복을 먼저 정리하세요.")
            missing = []
            for claim in ("userid", "user_sdwt_prod", "line_id"):
                expected = user_mapper(claim)
                existing = [m for m in mappers if m.get("config", {}).get("claim.name") == claim]
                if existing and (len(existing) != 1 or not mapper_equal(existing[0], expected)):
                    raise SetupError("선택 client의 기존 소속·EPID mapper 계약이 다릅니다.")
                if not existing:
                    if any(m.get("name") == claim for m in client.get("protocolMappers", [])):
                        raise SetupError("추가할 mapper 이름이 기존 mapper와 충돌합니다.")
                    missing.append(expected)
            self.missing_mappers[client["id"]] = missing

    def inspect_users(self):
        """기존 사용자는 그대로 두고 다른 신원으로 연결되는 충돌만 차단합니다."""
        if not self.users:
            return
        # custom attribute 검색 문법에 입력을 끼워 넣지 않고 정확한 값을 비교합니다.
        existing = self.api.pages("users", briefRepresentation="false")
        by_id = {user["id"]: user for user in existing}
        indexes = {key: {} for key in ("username", "email", "sabun", "knox_id")}
        for user in existing:
            for key, index in indexes.items():
                values = [user.get(key)] if key in {"username", "email"} else user.get("attributes", {}).get(key, [])
                for value in values:
                    if value:
                        index.setdefault(value.casefold(), set()).add(user["id"])
        for number, row in enumerate(self.users, 2):
            username_ids = indexes["username"].get(row["userid"].casefold(), set())
            matches = set(username_ids)
            for claim, key in (("mail", "email"), ("sabun", "sabun"), ("loginid", "knox_id")):
                value = row.get(claim, "")
                if value:
                    matches |= indexes[key].get(value.casefold(), set())
            if matches and (len(matches) != 1 or matches != username_ids):
                raise SetupError(f"사용자 CSV {number}행: 기존 계정 신원이 충돌합니다.")
            if username_ids:
                current = by_id[next(iter(username_ids))]
                for claim, key in (("sabun", "sabun"), ("loginid", "knox_id")):
                    values = current.get("attributes", {}).get(key, [])
                    if row.get(claim) and values and row[claim] not in values:
                        raise SetupError(f"사용자 CSV {number}행: 기존 계정의 {claim}와 다릅니다.")
                self.existing_count += 1
            else:
                self.new_users.append((number, row))

    def report(self):
        """개인정보 대신 작업별 건수를 출력합니다."""
        parent_count = sum(value is None for value in self.parents.values())
        child_count = sum(child is None for children in self.children.values() for child in children.values())
        print(f"계획: SDWT 부모 {parent_count}개 생성, 등급 하위 그룹 {child_count}개 생성")
        print(f"계획: client {len(self.clients)}개 연결, 신규 사용자 {len(self.new_users)}명, 기존 사용자 {self.existing_count}명 보존")
        print(f"계획: 사용자 프로필 {'보완' if self.profile_changed else '유지'}, 선택 client 토큰 수명 300초")
        print(f"계획: 충돌하는 선택 microprofile-jwt 연결 {sum(len(ids) for ids in self.optional_detach.values())}개 해제")
        print(f"계획: 동일한 sdwt-groups client mapper {sum(len(ids) for ids in self.dedicated_remove.values())}개를 공통 scope로 이전")

    def apply(self):
        """설정은 멱등적으로 준비하고 신규 사용자는 단일 요청으로 등록합니다."""
        if self.profile_changed:
            self.api.call("PUT", "users/profile", self.profile)
        for name in self.sdwts:
            if self.parents[name] is None:
                self.api.call("POST", "groups", {"name": name})
                self.parents[name] = one(self.api.pages("groups", populateHierarchy="false"), "name", name)
            parent = self.parents[name]
            if not parent:
                raise SetupError("생성한 SDWT 그룹을 찾지 못했습니다. 재실행하세요.")
            for role in ROLES:
                if self.children[name][role] is None:
                    self.api.call("POST", f"groups/{segment(parent['id'])}/children", {"name": role})
        if self.clients:
            self.apply_clients()
        for number, row in self.new_users:
            attributes = {attribute: [row[claim]] for claim, attribute in CSV_ATTRIBUTES.items() if row.get(claim)}
            name = row["user_sdwt_prod"]
            groups = []
            if name:
                attributes.update(user_sdwt_prod=[name], line_id=[self.sdwts[name]])
                groups = [f"/{name}/user"]
            body = {"username": row["userid"], "enabled": True, "attributes": attributes, "groups": groups}
            if row.get("mail"):
                body["email"] = row["mail"]
            try:
                self.api.call("POST", "users", body)
            except SetupError as exc:
                raise SetupError(f"사용자 CSV {number}행 등록 중단. 완료된 행은 유지됩니다. 원인을 해결하고 재실행하세요. {exc}") from None
        print("적용 완료. 기존 사용자·그룹 가입 관계는 변경하지 않았습니다.")

    def apply_clients(self):
        """기존 client 속성·다른 scope를 보존하고 지정한 client만 연결합니다."""
        if self.scope is None:
            self.api.call("POST", "client-scopes", self.scope_definition)
            self.scope = one(self.api.call("GET", "client-scopes"), "name", self.scope_definition["name"])
        if not self.scope:
            raise SetupError("생성한 공통 scope를 찾지 못했습니다. 재실행하세요.")
        for client in self.clients:
            endpoint = f"clients/{segment(client['id'])}"
            for scope_id in self.optional_detach[client["id"]]:
                self.api.call("DELETE", endpoint + f"/optional-client-scopes/{segment(scope_id)}")
            defaults = self.api.call("GET", endpoint + "/default-client-scopes")
            if not any(scope["id"] == self.scope["id"] for scope in defaults):
                self.api.call("PUT", endpoint + f"/default-client-scopes/{segment(self.scope['id'])}")
            for mapper_id in self.dedicated_remove[client["id"]]:
                self.api.call("DELETE", endpoint + f"/protocol-mappers/models/{segment(mapper_id)}")
            attributes = dict(client.get("attributes", {}))
            if attributes.get("access.token.lifespan") != "300":
                attributes["access.token.lifespan"] = "300"
                self.api.call("PUT", endpoint, {"attributes": attributes})
            for mapper in self.missing_mappers[client["id"]]:
                self.api.call("POST", endpoint + "/protocol-mappers/models", mapper)


def main() -> int:
    """명시 apply가 없으면 관리 API는 조회만 수행합니다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdwts", type=Path, default=os.environ.get("KEYCLOAK_SDWTS_CSV") or None, help="user_sdwt_prod,line_id CSV")
    parser.add_argument("--users", type=Path, default=os.environ.get("KEYCLOAK_USERS_CSV") or None, help="userid,user_sdwt_prod CSV, 생략하면 설정만 수행")
    parser.add_argument("--client", action="append", default=[], help="공통 권한을 연결할 기존 OIDC client, 반복 가능")
    parser.add_argument("--realm", default=os.environ.get("KEYCLOAK_TARGET_REALM", "etch"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", default=os.environ.get("KEYCLOAK_SDWT_APPLY") == "1")
    mode.add_argument("--validate-only", action="store_true", default=os.environ.get("KEYCLOAK_SDWT_VALIDATE_ONLY") == "1", help="연결 없이 CSV만 검증")
    args = parser.parse_args()
    try:
        if not args.sdwts:
            raise SetupError("--sdwts 또는 KEYCLOAK_SDWTS_CSV를 지정하세요.")
        if args.apply and args.validate_only:
            raise SetupError("CSV 전용 검증과 apply를 함께 지정할 수 없습니다.")
        sdwts, users = load_inputs(args.sdwts, args.users)
        if args.validate_only:
            print(f"CSV 검증 완료: SDWT {len(sdwts)}개, 사용자 {len(users)}명 (서버 연결 없음)")
            return 0
        if not args.realm or args.realm == "master":
            raise SetupError("업무 realm을 지정하세요. master에는 적용하지 않습니다.")
        clients = args.client or [name.strip() for name in os.environ.get("KEYCLOAK_SDWT_CLIENTS", "").split(",") if name.strip()]
        setup = Setup(Admin(args.realm), sdwts, users, list(dict.fromkeys(clients)))
        setup.inspect()
        setup.report()
        if args.apply:
            setup.apply()
        else:
            print("dry-run 완료. 서버 설정·사용자는 변경하지 않았습니다. 적용하려면 --apply를 지정하세요.")
        return 0
    except (SetupError, OSError) as exc:
        print(f"초기 설정 실패: {exc if isinstance(exc, SetupError) else '로컬 파일·인증서 설정을 확인하세요.'}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
