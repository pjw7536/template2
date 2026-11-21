#!/usr/bin/env python3
"""소속(/org 그룹 트리)에 맞춰 소속별 역할과 토큰 claim 설정을 멱등 반영합니다. 기본은 dry-run입니다.

권한 모델
- 소속: 그룹 /org/<팀>/<라인>/<SDWT>. 사람당 SDWT 그룹 하나에만 가입합니다.
- 소속별 역할: client `org`의 역할
    sdwt:<SDWT>:viewer|user|admin              SDWT 하나의 역할(위치를 넣지 않아 SDWT를 옮겨도 이름이 같음)
    team:<팀>:line:<라인>:viewer|user|admin     그 라인의 모든 SDWT 역할을 포함(복합 역할)
    team:<팀>:viewer|user|admin                그 팀의 모든 SDWT 역할을 포함(복합 역할)
  이름은 모두 `종류:이름(:종류:이름):등급` 형식이며, 팀·라인·SDWT 이름에는 ':'를 쓸 수 없습니다.
  SDWT 그룹에는 sdwt:<SDWT>:user가 연결되어 소속하면 자기 SDWT 일반 역할을 자동으로 받습니다.
- 토큰: client scope `org-claims`가 affiliation{team,line,sdwt}(사용자 속성 deptname·line_id·user_sdwt_prod)과
  org_roles(sdwt:<SDWT>:<등급> 목록. 라인·팀 역할은 펼쳐진 SDWT 역할로만 나감)를 발급합니다. realm 기본 scope이며 카탈로그 앱 client에도 연결합니다.

라인·팀 복합 역할의 하위 역할은 트리와 정확히 맞춥니다(SDWT 이동 반영). 그 밖의 역할은 지우지 않습니다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from init_sdwt import Admin, SetupError, one, segment  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
ORG_ROOT = "org"
ORG_CLIENT = "org"
ALL_ROLE = "org-all"
SCOPE = "org-claims"
LEVELS = ("viewer", "user", "admin")
LEVEL_LABELS = {"viewer": "조회", "user": "일반", "admin": "관리자"}
ATTRIBUTE_CLAIMS = (("team", "deptname"), ("line", "line_id"), ("sdwt", "user_sdwt_prod"))


def sdwt_role(sdwt: str, level: str) -> str:
    return f"sdwt:{sdwt}:{level}"


def line_role(team: str, line: str, level: str) -> str:
    return f"team:{team}:line:{line}:{level}"


def team_role(team: str, level: str) -> str:
    return f"team:{team}:{level}"


def desired_roles(tree: list[dict]) -> dict[str, dict]:
    """트리에서 필요한 역할과 정확한 하위 역할(복합 역할만)을 계산합니다.

    tree: [{"name": 팀, "lines": [{"name": 라인, "sdwts": [SDWT 이름, ...]}]}]
    """
    roles: dict[str, dict] = {}
    for team in tree:
        for level in LEVELS:
            team_children = []
            for line in team["lines"]:
                line_children = [sdwt_role(sdwt, level) for sdwt in line["sdwts"]]
                for sdwt in line["sdwts"]:
                    roles[sdwt_role(sdwt, level)] = {"description": f"{sdwt} {LEVEL_LABELS[level]}", "composites": None}
                roles[line_role(team["name"], line["name"], level)] = {
                    "description": f"{team['name']} / {line['name']} 라인 전체 {LEVEL_LABELS[level]}", "composites": line_children}
                team_children += line_children
            roles[team_role(team["name"], level)] = {"description": f"{team['name']} 팀 전체 {LEVEL_LABELS[level]}", "composites": team_children}
    return roles


def token_roles(roles: dict[str, dict]) -> list[str]:
    """토큰 scope 묶음(org-all)에 넣을 역할입니다. SDWT 역할만 넣어 토큰 org_roles에 sdwt:… 값만 나가게 합니다.

    라인·팀 역할은 Keycloak 안에서 SDWT 역할로 펼쳐진 뒤 scope에서 걸러지므로 토큰에 이름이 나가지 않습니다.
    """
    return [name for name, spec in roles.items() if spec["composites"] is None]


def claims_scope() -> dict:
    """affiliation 객체와 org_roles 목록을 발급하는 client scope입니다."""
    mappers = [{
        "name": f"affiliation-{claim}", "protocol": "openid-connect",
        "protocolMapper": "oidc-usermodel-attribute-mapper", "consentRequired": False,
        "config": {"user.attribute": attribute, "claim.name": f"affiliation.{claim}", "jsonType.label": "String",
                   "id.token.claim": "true", "access.token.claim": "true", "userinfo.token.claim": "true"},
    } for claim, attribute in ATTRIBUTE_CLAIMS]
    mappers.append({
        "name": "org-roles", "protocol": "openid-connect",
        "protocolMapper": "oidc-usermodel-client-role-mapper", "consentRequired": False,
        "config": {"usermodel.clientRoleMapping.clientId": ORG_CLIENT, "claim.name": "org_roles", "multivalued": "true",
                   "jsonType.label": "String", "id.token.claim": "true", "access.token.claim": "true", "userinfo.token.claim": "true"},
    })
    return {"name": SCOPE, "protocol": "openid-connect", "description": "소속(affiliation)과 소속별 역할(org_roles)",
            "attributes": {"include.in.token.scope": "false", "display.on.consent.screen": "false"}, "protocolMappers": mappers}


def catalog_clients() -> list[str]:
    """org-claims를 연결할 앱 client입니다(앱 역할 카탈로그 기준)."""
    path = BASE / "access/catalog.json"
    if not path.exists():
        return []
    return [app["client"] for app in json.loads(path.read_text(encoding="utf-8")).get("apps", []) if "client" in app]


class OrgSync:
    """현재 상태를 읽어 필요한 변경을 계획하고 적용합니다."""

    def __init__(self, api: Admin):
        self.api = api
        self.plan: list[str] = []
        self.warnings: list[str] = []

    def children(self, group_id: str) -> list[dict]:
        return self.api.pages(f"groups/{segment(group_id)}/children", briefRepresentation="true")

    def read_tree(self) -> list[dict]:
        root = one(self.api.pages("groups", populateHierarchy="false"), "name", ORG_ROOT)
        if root is None:
            return []
        tree = []
        for team in self.children(root["id"]):
            lines = []
            for line in self.children(team["id"]):
                sdwts = self.children(line["id"])
                lines.append({"name": line["name"], "sdwts": sorted(item["name"] for item in sdwts),
                              "groups": {item["name"]: item["id"] for item in sdwts}})
            tree.append({"name": team["name"], "lines": sorted(lines, key=lambda item: item["name"])})
        return sorted(tree, key=lambda item: item["name"])

    def inspect(self):
        api = self.api
        self.tree = self.read_tree()
        names = [sdwt for team in self.tree for line in team["lines"] for sdwt in line["sdwts"]]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            raise SetupError(f"SDWT 이름이 여러 곳에 있습니다: {', '.join(duplicated)}")
        self.client = one(api.call("GET", "clients", query={"clientId": ORG_CLIENT}), "clientId", ORG_CLIENT)
        if self.client is None:
            self.plan.append(f"역할 보관용 client '{ORG_CLIENT}' 생성")
            current = {}
        else:
            current = {role["name"]: role for role in api.call("GET", f"clients/{segment(self.client['id'])}/roles",
                                                                query={"briefRepresentation": "false"})}
        self.desired = desired_roles(self.tree)
        self.current_roles = current
        self.create = [name for name in [ALL_ROLE, *self.desired] if name not in current]
        if self.create:
            self.plan.append(f"org 역할 생성 {len(self.create)}개")
        # 복합 역할의 하위 역할 차이
        self.compose: dict[str, tuple[list[str], list[str]]] = {}
        for name, spec in [*self.desired.items(), (ALL_ROLE, {"composites": token_roles(self.desired)})]:
            if spec["composites"] is None:
                continue
            have = set()
            if name in current and current[name].get("composite"):
                have = {item["name"] for item in api.call("GET", f"clients/{segment(self.client['id'])}/roles/{segment(name)}/composites")}
            want = set(spec["composites"])
            add, remove = sorted(want - have), sorted(have - want)
            if add or remove:
                self.compose[name] = (add, remove)
        if self.compose:
            changes = sum(len(add) + len(remove) for add, remove in self.compose.values())
            self.plan.append(f"라인·팀 복합 역할 하위 역할 맞춤 {changes}건(SDWT 추가·이동 반영)")
        # SDWT 그룹의 자기 SDWT 일반 역할
        self.group_maps = []
        for team in self.tree:
            for line in team["lines"]:
                for sdwt, group_id in line["groups"].items():
                    have = set()
                    if self.client:
                        have = {item["name"] for item in api.call("GET", f"groups/{segment(group_id)}/role-mappings/clients/{segment(self.client['id'])}")}
                    if sdwt_role(sdwt, "user") not in have:
                        self.group_maps.append((group_id, sdwt))
        if self.group_maps:
            self.plan.append(f"SDWT 그룹에 자기 SDWT 일반 역할 연결 {len(self.group_maps)}개")
        unknown = sorted(set(current) - set(self.desired) - {ALL_ROLE})
        if unknown:
            self.warnings.append(f"트리에 없는 org 역할 {len(unknown)}개(삭제하지 않음): {', '.join(unknown[:10])}")
        self.inspect_scope()

    def inspect_scope(self):
        api = self.api
        self.scope = one(api.call("GET", "client-scopes"), "name", SCOPE)
        if self.scope is None:
            self.plan.append(f"토큰 scope '{SCOPE}' 생성(affiliation, org_roles)")
        defaults = api.call("GET", "default-default-client-scopes")
        self.scope_default = any(item["name"] == SCOPE for item in defaults)
        if not self.scope_default:
            self.plan.append(f"'{SCOPE}'를 realm 기본 scope로 지정")
        self.map_scope = True
        if self.scope and self.client:
            mapped = api.call("GET", f"client-scopes/{segment(self.scope['id'])}/scope-mappings/clients/{segment(self.client['id'])}")
            self.map_scope = not any(item["name"] == ALL_ROLE for item in mapped)
        if self.map_scope:
            self.plan.append(f"'{SCOPE}'에 '{ALL_ROLE}' 역할 연결")
        self.attach = []
        for client_id in catalog_clients():
            client = one(api.call("GET", "clients", query={"clientId": client_id}), "clientId", client_id)
            if client is None:
                continue
            scopes = api.call("GET", f"clients/{segment(client['id'])}/default-client-scopes")
            if not any(item["name"] == SCOPE for item in scopes):
                self.attach.append(client)
        if self.attach:
            self.plan.append(f"앱 client에 '{SCOPE}' 연결: {', '.join(client['clientId'] for client in self.attach)}")

    def apply(self):
        api = self.api
        if self.client is None:
            api.call("POST", "clients", {"clientId": ORG_CLIENT, "name": "소속별 역할", "protocol": "openid-connect",
                                         "publicClient": True, "standardFlowEnabled": False, "implicitFlowEnabled": False,
                                         "directAccessGrantsEnabled": False, "serviceAccountsEnabled": False,
                                         "description": "소속별 역할 보관용. 로그인에 쓰지 않습니다."})
            self.client = one(api.call("GET", "clients", query={"clientId": ORG_CLIENT}), "clientId", ORG_CLIENT)
        base = f"clients/{segment(self.client['id'])}/roles"
        for name in self.create:
            description = self.desired.get(name, {}).get("description", "토큰 scope용 전체 org 역할 묶음")
            api.call("POST", base, {"name": name, "description": description})
        roles = {role["name"]: role for role in api.call("GET", base, query={"briefRepresentation": "false"})}
        for name, (add, remove) in self.compose.items():
            if add:
                api.call("POST", f"{base}/{segment(name)}/composites", [roles[item] for item in add])
            if remove:
                api.call("DELETE", f"{base}/{segment(name)}/composites", [roles[item] for item in remove if item in roles])
        for group_id, sdwt in self.group_maps:
            api.call("POST", f"groups/{segment(group_id)}/role-mappings/clients/{segment(self.client['id'])}", [roles[sdwt_role(sdwt, "user")]])
        if self.scope is None:
            api.call("POST", "client-scopes", claims_scope())
            self.scope = one(api.call("GET", "client-scopes"), "name", SCOPE)
        # org client 역할이 앱 토큰에 들어가도록 scope에 전체 묶음 역할을 연결합니다(앱 client는 fullScopeAllowed=false).
        if self.map_scope:
            api.call("POST", f"client-scopes/{segment(self.scope['id'])}/scope-mappings/clients/{segment(self.client['id'])}", [roles[ALL_ROLE]])
        if not self.scope_default:
            api.call("PUT", f"default-default-client-scopes/{segment(self.scope['id'])}")
        for client in self.attach:
            api.call("PUT", f"clients/{segment(client['id'])}/default-client-scopes/{segment(self.scope['id'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--realm", default=os.environ.get("KEYCLOAK_TARGET_REALM", "etch"))
    parser.add_argument("--apply", action="store_true", default=os.environ.get("KEYCLOAK_ORG_APPLY") == "1")
    args = parser.parse_args()
    try:
        if not args.realm or args.realm == "master":
            raise SetupError("업무 realm을 지정하세요. master에는 적용하지 않습니다.")
        task = OrgSync(Admin(args.realm))
        task.inspect()
        for line in task.plan or ["변경 없음"]:
            print("계획: " + line)
        for line in task.warnings:
            print("경고: " + line)
        if args.apply:
            task.apply()
            print("적용 완료.")
        else:
            print("dry-run 완료. 적용하려면 --apply(KEYCLOAK_ORG_APPLY=1)를 지정하세요.")
        return 0
    except SetupError as exc:
        print(f"소속 역할 반영 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
