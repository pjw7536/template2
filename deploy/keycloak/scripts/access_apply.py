#!/usr/bin/env python3
"""앱 역할 카탈로그(access/catalog.json)를 Keycloak에 멱등 반영합니다. 기본은 조회만 하는 dry-run입니다.

반영 대상
- 앱 client의 역할: viewer ⊂ user ⊂ admin(복합 역할)
  여러 기능을 가진 앱(Portal)은 <기능>:viewer… 와 묶음 역할 all:viewer·all:user·all:admin
- realm 기본 역할: default가 open인 앱·기능의 viewer를 넣고, closed면 뺍니다.
- 권한관리 웹용 공개 카탈로그: /iam 그룹 속성 iam.catalog(255자 이하 조각)

카탈로그에 없는 역할·포함 관계는 지우지 않고 경고만 출력합니다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from init_sdwt import Admin, SetupError, one, segment  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
LEVELS = ("viewer", "user", "admin")
LEVEL_LABELS = {"viewer": "조회", "user": "일반", "admin": "관리자"}
ALL_KEY = "all"
CATALOG_GROUP = "iam"
CATALOG_ATTRIBUTE = "iam.catalog"
# Keycloak 그룹 속성 값 하나는 255자까지 저장되므로 순번을 붙여 나눠 저장합니다.
CHUNK_SIZE = 250
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def load_catalog(path: Path) -> list[dict]:
    """카탈로그 형식을 검사하고 앱 목록을 돌려줍니다."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SetupError(f"카탈로그를 읽을 수 없습니다: {path}") from exc
    apps = data.get("apps") if isinstance(data, dict) else None
    if not isinstance(apps, list) or not apps:
        raise SetupError("카탈로그에 apps 목록이 없습니다.")
    clients, groups = set(), set()
    for number, app in enumerate(apps, 1):
        where = f"apps[{number}]"
        if not isinstance(app, dict) or not isinstance(app.get("name"), str) or not app["name"].strip():
            raise SetupError(f"{where}: name이 필요합니다.")
        if ("client" in app) == ("group" in app):
            raise SetupError(f"{where}: client와 group 중 하나만 지정하세요.")
        if "group" in app:
            if not isinstance(app["group"], str) or not app["group"].startswith("/") or app["group"] in groups:
                raise SetupError(f"{where}: group은 '/'로 시작하는 중복 없는 경로여야 합니다.")
            groups.add(app["group"])
            continue
        if not isinstance(app["client"], str) or not app["client"] or app["client"] in clients:
            raise SetupError(f"{where}: client가 비었거나 중복입니다.")
        clients.add(app["client"])
        if "features" in app:
            features = app["features"]
            if not isinstance(features, list) or not features:
                raise SetupError(f"{where}: features는 비어 있지 않은 목록이어야 합니다.")
            keys = set()
            for feature in features:
                check_entry(feature, f"{where}.{feature.get('key', '?') if isinstance(feature, dict) else '?'}")
                if feature["key"] == ALL_KEY or feature["key"] in keys:
                    raise SetupError(f"{where}: 기능 key '{feature['key']}'가 예약어이거나 중복입니다.")
                keys.add(feature["key"])
        else:
            check_entry({**app, "key": "app"}, where)
    return apps


def check_entry(entry: dict, where: str):
    """앱 또는 기능 하나의 key·name·default를 검사합니다."""
    if not isinstance(entry, dict):
        raise SetupError(f"{where}: 객체여야 합니다.")
    if not isinstance(entry.get("key"), str) or not KEY_PATTERN.match(entry["key"]):
        raise SetupError(f"{where}: key는 소문자·숫자·'-'만 씁니다.")
    if not isinstance(entry.get("name"), str) or not entry["name"].strip():
        raise SetupError(f"{where}: name이 필요합니다.")
    if entry.get("default") not in ("open", "closed"):
        raise SetupError(f"{where}: default는 open 또는 closed입니다.")
    if "dataAll" in entry:
        # 소속별 데이터 범위는 소속별 역할(client org)로 정하므로 앱 역할에 두지 않습니다.
        raise SetupError(f"{where}: dataAll은 쓰지 않습니다. 소속별 역할(make keycloak-org-sync)을 쓰세요.")


def level_roles(prefix: str, label: str) -> dict[str, dict]:
    """한 앱·기능의 viewer ⊂ user ⊂ admin 역할입니다."""
    roles = {}
    lower = None
    for level in LEVELS:
        roles[prefix + level] = {"description": f"{label} {LEVEL_LABELS[level]}", "composites": [lower] if lower else []}
        lower = prefix + level
    return roles


def desired_roles(app: dict) -> dict[str, dict]:
    """client 앱 하나에 있어야 할 역할과 포함 관계입니다."""
    if "features" not in app:
        return level_roles("", app["name"])
    roles = {}
    for feature in app["features"]:
        roles.update(level_roles(f"{feature['key']}:", f"{app['name']} {feature['name']}"))
    # 묶음 역할: all:<level>은 모든 기능의 <level>과 한 단계 아래 묶음 역할을 포함합니다.
    lower = None
    for level in LEVELS:
        composites = [f"{feature['key']}:{level}" for feature in app["features"]]
        if lower:
            composites.insert(0, lower)
        roles[f"{ALL_KEY}:{level}"] = {"description": f"{app['name']} 전체 {LEVEL_LABELS[level]}", "composites": composites}
        lower = f"{ALL_KEY}:{level}"
    return roles


def default_roles(app: dict) -> tuple[set[str], set[str]]:
    """realm 기본 역할에 넣을 역할과 뺄 역할입니다."""
    entries = app["features"] if "features" in app else [{**app, "key": ""}]
    add, remove = set(), set()
    for entry in entries:
        name = f"{entry['key']}:viewer" if entry["key"] else "viewer"
        (add if entry["default"] == "open" else remove).add(name)
    return add, remove


def public_entry(app: dict, uuid: str | None) -> dict:
    """권한관리 웹이 읽는 카탈로그 항목입니다. client 내부 id를 함께 넣어 view-clients 없이 동작하게 합니다."""
    if "group" in app:
        return {"group": app["group"], "name": app["name"], "infra": bool(app.get("infra"))}
    entry = {"client": app["client"], "uuid": uuid, "name": app["name"]}
    if "features" in app:
        entry["features"] = [{key: feature[key] for key in ("key", "name", "default")}
                             for feature in app["features"]]
    else:
        entry["default"] = app["default"]
    return entry


def chunk(text: str) -> list[str]:
    """순번 4자리('000:')를 붙여 255자 이하로 나눕니다."""
    parts = [text[index:index + CHUNK_SIZE] for index in range(0, len(text), CHUNK_SIZE)] or [""]
    return [f"{number:03d}:{part}" for number, part in enumerate(parts)]


def unchunk(values: list[str]) -> str:
    return "".join(value[4:] for value in sorted(values))


class Apply:
    """현재 Keycloak 상태와 카탈로그를 비교해 필요한 변경만 계획·적용합니다."""

    def __init__(self, api: Admin, apps: list[dict]):
        self.api, self.apps = api, apps
        self.plan: list[str] = []
        self.warnings: list[str] = []
        self.clients: dict[str, dict] = {}
        self.public: list[dict] = []
        self.catalog_group = None

    def inspect(self, *, include_catalog=True):
        api = self.api
        realm = api.realm
        self.default_role = api.call("GET", f"roles/{segment('default-roles-' + realm.lower())}")
        for app in self.apps:
            if "group" in app:
                found = api.call("GET", "groups", query={"search": app["group"].rsplit("/", 1)[-1], "exact": "true"})
                if not any(group.get("path") == app["group"] for group in self.walk(found)):
                    self.warnings.append(f"그룹 {app['group']}이 없습니다. 만들기 전까지 매트릭스에서 변경할 수 없습니다.")
                self.public.append(public_entry(app, None))
                continue
            client = one(api.call("GET", "clients", query={"clientId": app["client"]}), "clientId", app["client"])
            if not client:
                self.warnings.append(f"client '{app['client']}'가 없어 건너뜁니다. 앱 배포에서 로그인 client를 먼저 만드세요.")
                continue
            self.inspect_client(app, client)
            self.public.append(public_entry(app, client["id"]))
        if include_catalog:
            self.inspect_catalog()

    @staticmethod
    def walk(groups: list[dict]):
        for group in groups or []:
            yield group
            yield from Apply.walk(group.get("subGroups", []))

    def inspect_client(self, app: dict, client: dict):
        api = self.api
        base = f"clients/{segment(client['id'])}"
        current = {role["name"]: role for role in api.call("GET", base + "/roles", query={"briefRepresentation": "false"})}
        desired = desired_roles(app)
        state = {"client": client, "base": base, "desired": desired, "create": [], "describe": [], "compose": {},
                 "default_add": set(), "default_remove": set()}
        for name, spec in desired.items():
            role = current.get(name)
            if role is None:
                state["create"].append(name)
                if spec["composites"]:
                    state["compose"][name] = list(spec["composites"])
                continue
            if role.get("description") != spec["description"]:
                state["describe"].append(name)
            have = set()
            if role.get("composite"):
                have = {item["name"] for item in api.call("GET", f"{base}/roles/{segment(name)}/composites")}
            missing = [item for item in spec["composites"] if item not in have]
            if missing:
                state["compose"][name] = missing
            extra = have - set(spec["composites"])
            if extra:
                self.warnings.append(f"{app['client']} 역할 {name}에 카탈로그에 없는 포함 역할: {', '.join(sorted(extra))} (유지)")
        unknown = sorted(set(current) - set(desired) - {"uma_protection"})
        if unknown:
            self.warnings.append(f"{app['client']}에 카탈로그에 없는 역할 {len(unknown)}개: {', '.join(unknown)} (삭제하지 않음)")
        defaults = {role["name"] for role in api.call(
            "GET", f"roles-by-id/{segment(self.default_role['id'])}/composites/clients/{segment(client['id'])}")}
        add, remove = default_roles(app)
        state["default_add"] = add - defaults
        state["default_remove"] = remove & defaults
        self.clients[app["client"]] = state
        for label, names in (("역할 생성", state["create"]), ("설명 갱신", state["describe"])):
            if names:
                self.plan.append(f"{app['client']}: {label} {len(names)}개 ({', '.join(names)})")
        if state["compose"]:
            self.plan.append(f"{app['client']}: 포함 관계 추가 {sum(map(len, state['compose'].values()))}개")
        if state["default_add"]:
            self.plan.append(f"{app['client']}: 기본 역할에 추가 {', '.join(sorted(state['default_add']))}")
        if state["default_remove"]:
            self.plan.append(f"{app['client']}: 기본 역할에서 제거(닫힌 앱) {', '.join(sorted(state['default_remove']))}")

    def inspect_catalog(self):
        groups = self.api.call("GET", "groups", query={"search": CATALOG_GROUP, "exact": "true"})
        self.catalog_group = one(groups, "name", CATALOG_GROUP)
        # 권한관리 웹은 client 목록을 볼 수 없으므로 소속별 역할 client(org) 내부 id도 카탈로그로 전달합니다.
        org = one(self.api.call("GET", "clients", query={"clientId": "org"}), "clientId", "org")
        published = {"apps": self.public, **({"org": {"uuid": org["id"]}} if org else {})}
        if org is None:
            self.warnings.append("client 'org'가 없어 소속별 역할 정보를 카탈로그에 넣지 않습니다. make keycloak-org-sync를 먼저 실행하세요.")
        self.catalog_text = json.dumps(published, ensure_ascii=False, separators=(",", ":"))
        if self.catalog_group is None:
            self.warnings.append(f"/{CATALOG_GROUP} 그룹이 없어 권한관리 웹용 카탈로그를 저장하지 않습니다. make iam-keycloak-setup을 먼저 실행하세요.")
            return
        self.catalog_group = self.api.call("GET", f"groups/{segment(self.catalog_group['id'])}")
        stored = self.catalog_group.get("attributes", {}).get(CATALOG_ATTRIBUTE, [])
        self.catalog_changed = unchunk(stored) != self.catalog_text
        if self.catalog_changed:
            self.plan.append(f"권한관리 웹 카탈로그 갱신(/{CATALOG_GROUP} 속성 {CATALOG_ATTRIBUTE}, 앱 {len(self.public)}개)")

    def apply(self):
        api = self.api
        for state in self.clients.values():
            base = state["base"]
            for name in state["create"]:
                api.call("POST", base + "/roles", {"name": name, "description": state["desired"][name]["description"]})
            roles = {role["name"]: role for role in api.call("GET", base + "/roles", query={"briefRepresentation": "false"})}
            for name in state["describe"]:
                api.call("PUT", f"{base}/roles/{segment(name)}", {**roles[name], "description": state["desired"][name]["description"]})
            for name, children in state["compose"].items():
                api.call("POST", f"{base}/roles/{segment(name)}/composites", [roles[child] for child in children])
            default_path = f"roles-by-id/{segment(self.default_role['id'])}/composites"
            if state["default_add"]:
                api.call("POST", default_path, [roles[name] for name in sorted(state["default_add"])])
            if state["default_remove"]:
                api.call("DELETE", default_path, [roles[name] for name in sorted(state["default_remove"]) if name in roles])
        if self.catalog_group is not None and self.catalog_changed:
            group = self.catalog_group
            attributes = {**group.get("attributes", {}), CATALOG_ATTRIBUTE: chunk(self.catalog_text)}
            api.call("PUT", f"groups/{segment(group['id'])}", {**group, "attributes": attributes})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalog", type=Path, default=Path(os.environ.get("KEYCLOAK_ACCESS_CATALOG") or BASE / "access/catalog.json"))
    parser.add_argument("--realm", default=os.environ.get("KEYCLOAK_TARGET_REALM", "etch"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", default=os.environ.get("KEYCLOAK_ACCESS_APPLY") == "1")
    mode.add_argument("--validate-only", action="store_true", help="서버 연결 없이 카탈로그만 검사")
    args = parser.parse_args()
    try:
        apps = load_catalog(args.catalog)
        if args.validate_only:
            print(f"카탈로그 검사 통과: 앱 {len(apps)}개 (서버 연결 없음)")
            return 0
        if not args.realm or args.realm == "master":
            raise SetupError("업무 realm을 지정하세요. master에는 적용하지 않습니다.")
        task = Apply(Admin(args.realm), apps)
        task.inspect()
        for line in task.plan or ["변경 없음"]:
            print("계획: " + line)
        for line in task.warnings:
            print("경고: " + line)
        if args.apply:
            task.apply()
            print("적용 완료. 사용자가 다시 로그인하거나 토큰이 갱신되면 앱에 반영됩니다.")
        else:
            print("dry-run 완료. 적용하려면 --apply(KEYCLOAK_ACCESS_APPLY=1)를 지정하세요.")
        return 0
    except SetupError as exc:
        print(f"앱 역할 반영 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
