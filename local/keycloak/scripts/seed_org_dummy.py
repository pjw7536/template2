#!/usr/bin/env python3
"""개발 Keycloak의 팀 → 라인 → SDWT마다 더미 구성원을 채우거나 지웁니다.

- 대상: 개발 Keycloak(http://localhost:8180, realm portal)의 소속 그룹 /org/<팀>/<라인>/<SDWT> 전부
- SDWT마다 기본 20명을 소속시키고(자기 SDWT 일반 역할은 자동), 2명은 SDWT 관리자, 1명은 다음 SDWT 조회(지원)를 줍니다.
- 라인·팀마다 관리자 역할(team:…:line:…:admin, team:…:admin)을 1명씩 줍니다.
- 더미 사용자는 username이 99로 시작하는 8자리 EPID이고 이메일 도메인이 dummy.example.invalid입니다. 다시 실행하면 빠진 것만 채웁니다.
- --remove는 이 스크립트가 만든 더미 사용자(위 두 조건을 모두 만족)만 지웁니다.
- --lines 12 --total-users 2000은 기존 팀에 라인을 배분하고 라인당 SDWT 4~5개·직급·PL·파트장 예시를 채웁니다.

관리자 계정은 KEYCLOAK_ADMIN_USERNAME·KEYCLOAK_ADMIN_PASSWORD 환경변수, 없으면 로컬 kind의 local-runtime Secret에서 읽습니다.
"""

from __future__ import annotations

import argparse
import base64
import copy
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "deploy/keycloak/scripts"))
from init_sdwt import Admin, SetupError, segment  # noqa: E402
from org_sync import OrgSync  # noqa: E402

NAMESPACE = "tailwind-local"
CONTEXT = "kind-tailwind-local"
# User Profile에 없는 속성은 저장되지 않으므로 이메일 도메인으로 더미 사용자를 표시합니다.
DOMAIN = "dummy.example.invalid"
SURNAMES = "김 이 박 최 정 강 조 윤 장 임 한 오 서 신 권 황 안 송 류 홍".split()
GIVEN = "민준 서준 도윤 예준 시우 하준 지호 주원 지후 준우 서연 서윤 지우 하은 하윤 민서 지유 윤서 채원 수아".split()
ROMAN = {"김": "kim", "이": "lee", "박": "park", "최": "choi", "정": "jung", "강": "kang", "조": "cho", "윤": "yoon",
         "장": "jang", "임": "lim", "한": "han", "오": "oh", "서": "seo", "신": "shin", "권": "kwon", "황": "hwang",
         "안": "ahn", "송": "song", "류": "ryu", "홍": "hong"}


def secret_value(key: str) -> str:
    """로컬 kind Secret에서 관리자 계정 값을 읽습니다."""
    raw = subprocess.run(
        ["kubectl", "--context", CONTEXT, "-n", NAMESPACE, "get", "secret", "local-runtime", "-o", f"jsonpath={{.data.{key}}}"],
        check=True, capture_output=True, text=True,
    ).stdout
    return base64.b64decode(raw).decode()


def org_tree(api: Admin) -> list[dict]:
    """소속 트리 /org/<팀>/<라인>/<SDWT>를 읽습니다."""
    def children(group_id):
        return api.pages(f"groups/{segment(group_id)}/children", briefRepresentation="true")

    root = next((group for group in api.pages("groups", populateHierarchy="false") if group["name"] == "org"), None)
    if root is None:
        return []
    teams = []
    for team in children(root["id"]):
        lines = [{"id": line["id"], "name": line["name"], "sdwts": sorted(children(line["id"]), key=lambda item: item["name"])}
                 for line in children(team["id"])]
        teams.append({"id": team["id"], "name": team["name"], "lines": sorted(lines, key=lambda item: item["name"])})
    return sorted(teams, key=lambda item: item["name"])


def dummy_users(api: Admin) -> dict[str, dict]:
    # Keycloak search는 기본이 앞부분 일치라 *…*로 도메인을 찾습니다.
    users = api.pages("users", search=f"*{DOMAIN}*", briefRepresentation="false")
    return {user["username"]: user for user in users
            if user["username"].startswith("99") and (user.get("email") or "").endswith(f"@{DOMAIN}")}


def is_dummy(user: dict) -> bool:
    """대규모 모드는 예약 EPID와 더미 이메일 조건을 모두 만족하는 사용자만 수정합니다."""
    return bool(re.fullmatch(r"99\d{6}", user.get("username", ""))
                and (user.get("email") or "").endswith(f"@{DOMAIN}"))


def check_local(api: Admin) -> None:
    """더미 대량 입력은 loopback 주소의 개발 realm으로 제한합니다."""
    host = urlsplit(api.url).hostname
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        loopback = False
    if not loopback or api.realm != "portal":
        raise SetupError("대규모 더미 입력은 loopback Keycloak의 portal realm에서만 실행합니다.")


def scale_layout(teams: list[dict], line_count: int) -> list[dict]:
    """기존 조직을 보존하면서 팀별 라인을 균등하게 늘리고 SDWT를 4~5개로 맞춥니다."""
    result = copy.deepcopy(teams)
    if not result or line_count < 1 or line_count < sum(len(team["lines"]) for team in result):
        raise SetupError("기존 팀이 필요하며 현재보다 적은 라인 수로 줄일 수 없습니다.")
    while sum(len(team["lines"]) for team in result) < line_count:
        team = min(result, key=lambda item: (len(item["lines"]), item["name"]))
        names = {line["name"] for line in team["lines"]}
        number = 1
        while f"LINE-{number}" in names:
            number += 1
        team["lines"].append({"name": f"LINE-{number}", "sdwts": []})
        team["lines"].sort(key=lambda item: item["name"])
    occupied = {sdwt["name"] for team in result for line in team["lines"] for sdwt in line["sdwts"]}
    serial = 0
    for ti, team in enumerate(result, 1):
        for li, line in enumerate(team["lines"], 1):
            wanted = 4 + serial % 2
            serial += 1
            if len(line["sdwts"]) > 5:
                raise SetupError("SDWT가 5개보다 많은 기존 라인은 자동으로 줄이지 않습니다.")
            number = 1
            while len(line["sdwts"]) < wanted:
                name = f"SDWT-T{ti:02d}-L{li:02d}-P{number:02d}"
                number += 1
                if name in occupied:
                    continue
                occupied.add(name)
                line["sdwts"].append({"name": name})
    return result


def scale_people(teams: list[dict], total: int) -> list[dict]:
    """전체 인원을 균등 분배하고 각 라인에 PL, 각 SDWT에 파트장 한 명을 배치합니다."""
    sdwts = [(team, line, sdwt, si) for team in teams for line in team["lines"] for si, sdwt in enumerate(line["sdwts"])]
    if total < len(sdwts) * 2 or total > 999999:
        raise SetupError("SDWT당 최소 2명 이상, 전체 999999명 이하로 지정하세요.")
    per, remainder = divmod(total, len(sdwts))
    people = []
    for offset, (team, line, sdwt, si) in enumerate(sdwts):
        for index in range(per + (offset < remainder)):
            serial = len(people) + 1
            surname, given = SURNAMES[serial % len(SURNAMES)], GIVEN[(serial // len(SURNAMES)) % len(GIVEN)]
            login = f"{ROMAN[surname]}.{serial:04d}"
            title = "파트장" if index == 0 else "PL" if si == 0 and index == 1 else ""
            attributes = {
                "loginid": [login], "display_name": [surname + given], "sabun": [f"D{serial:06d}"],
                "deptname": [team["name"]], "line_id": [line["name"]], "user_sdwt_prod": [sdwt["name"]],
                "grdName": [["사원", "선임", "책임", "수석"][serial % 4]],
            }
            if title:
                attributes["job_title"] = [title]
            people.append({"username": f"99{serial:06d}", "enabled": True, "email": f"{login}@{DOMAIN}",
                           "emailVerified": True, "firstName": given, "lastName": surname,
                           "attributes": attributes, "sdwt_id": sdwt.get("id")})
    return people


def update_dummy(api: Admin, user: dict, desired: dict, created: bool = False) -> None:
    """더미의 org 소속만 교체하고 다른 그룹·속성·권한은 보존합니다. 실패 시 재실행으로 수렴합니다."""
    if not is_dummy(user) or user["username"] != desired["username"]:
        raise SetupError("더미로 식별되지 않는 사용자는 수정하지 않습니다.")
    endpoint = f"users/{segment(user['id'])}"
    groups = [] if created else api.pages(endpoint + "/groups")
    for group in groups:
        if group.get("path", "").startswith("/org/") and group["id"] != desired["sdwt_id"]:
            api.call("DELETE", endpoint + f"/groups/{segment(group['id'])}")
    if desired["sdwt_id"] not in {group["id"] for group in groups}:
        api.call("PUT", endpoint + f"/groups/{segment(desired['sdwt_id'])}")
    attributes = {**user.get("attributes", {}), **desired["attributes"]}
    if "job_title" not in desired["attributes"]:
        attributes.pop("job_title", None)
    if attributes != user.get("attributes", {}):
        current = api.call("GET", endpoint)
        attributes = {**current.get("attributes", {}), **desired["attributes"]}
        if "job_title" not in desired["attributes"]:
            attributes.pop("job_title", None)
        api.call("PUT", endpoint, {**current, "attributes": attributes})


def scale(api: Admin, line_count: int, total: int) -> None:
    """개발 조직을 확장하고 실제 사용자 보존·단일 소속·인원·직책을 조회해 검증합니다."""
    check_local(api)
    planned = scale_layout(org_tree(api), line_count)
    desired_people = scale_people(planned, total)
    users = api.pages("users", briefRepresentation="false")
    by_name = {user["username"]: user for user in users}
    expected_names = {person["username"] for person in desired_people}
    if any(name in by_name and not is_dummy(by_name[name]) for name in expected_names):
        raise SetupError("생성할 EPID와 실제 사용자가 충돌합니다. 기존 사용자는 변경하지 않았습니다.")
    if any(is_dummy(user) and user["username"] not in expected_names for user in users):
        raise SetupError("목표 범위 밖의 더미 사용자가 있습니다. 자동으로 삭제하지 않습니다.")
    real_before = {user["id"]: (user, api.pages(f"users/{segment(user['id'])}/groups"),
                                api.call("GET", f"users/{segment(user['id'])}/role-mappings"))
                   for user in users if not is_dummy(user)}
    print(f"대상 {api.url}, realm {api.realm}: 라인 {line_count}개, SDWT {len({p['attributes']['user_sdwt_prod'][0] for p in desired_people})}개, 더미 {total}명", flush=True)
    for team in planned:
        for line in team["lines"]:
            if not line.get("id"):
                api.call("POST", f"groups/{segment(team['id'])}/children", {"name": line["name"]})
                line["id"] = next(item["id"] for item in api.pages(f"groups/{segment(team['id'])}/children") if item["name"] == line["name"])
            for sdwt in line["sdwts"]:
                if not sdwt.get("id"):
                    api.call("POST", f"groups/{segment(line['id'])}/children", {"name": sdwt["name"]})
    sync = OrgSync(api)
    sync.inspect()
    sync.apply()
    # 관리 속성은 deploy의 공통 정의를 재사용하고 다른 프로필 설정은 보존합니다.
    profile = api.call("GET", "users/profile")
    definitions = json.loads((ROOT / "deploy/keycloak/k8s/claims/account-user-profile.json").read_text())
    known = {item["name"] for item in profile.get("attributes", [])}
    additions = [item for item in definitions["attributes"] if item["name"] in {"job_title", "grdName"} and item["name"] not in known]
    if additions:
        profile.setdefault("attributes", []).extend(additions)
        api.call("PUT", "users/profile", profile)
    desired_people = scale_people(org_tree(api), total)
    created = 0
    for index, person in enumerate(desired_people, 1):
        user = by_name.get(person["username"])
        fresh = user is None
        if fresh:
            api.call("POST", "users", {key: value for key, value in person.items() if key != "sdwt_id"})
            user = api.call("GET", "users", query={"username": person["username"], "exact": "true"})[0]
            created += 1
        update_dummy(api, user, person, created=fresh)
        if index % 100 == 0:
            print(f"구성원 반영 {index}/{total}명 (신규 {created}명)", flush=True)
    after = {user["username"]: user for user in api.pages("users", briefRepresentation="false")}
    dummy_count = sum(is_dummy(user) for user in after.values())
    if dummy_count != total:
        raise SetupError(f"더미 수 검증 실패: 기대 {total}, 실제 {dummy_count}")
    pl = heads = 0
    for person in desired_people:
        user = after[person["username"]]
        groups = [group["id"] for group in api.pages(f"users/{segment(user['id'])}/groups") if group.get("path", "").startswith("/org/")]
        if groups != [person["sdwt_id"]] or any(user.get("attributes", {}).get(key) != value for key, value in person["attributes"].items()):
            raise SetupError("더미 구성원 속성 또는 단일 소속 검증에 실패했습니다.")
        title = (user.get("attributes", {}).get("job_title") or [""])[0]
        pl += title == "PL"
        heads += title == "파트장"
    sdwt_count = sum(len(line["sdwts"]) for team in org_tree(api) for line in team["lines"])
    if pl != line_count or heads != sdwt_count:
        raise SetupError("PL 또는 파트장 수 검증에 실패했습니다.")
    for user_id, (before, groups, roles) in real_before.items():
        current = api.call("GET", f"users/{segment(user_id)}")
        if (current.get("attributes", {}) != before.get("attributes", {})
                or {item["id"] for item in api.pages(f"users/{segment(user_id)}/groups")} != {item["id"] for item in groups}
                or api.call("GET", f"users/{segment(user_id)}/role-mappings") != roles):
            raise SetupError("일반 사용자 보존 검증에 실패했습니다.")
    print(f"검증 완료: 더미 {dummy_count}명, PL {pl}명, 파트장 {heads}명, 일반 사용자 {len(real_before)}명 보존", flush=True)


def seed(api: Admin, per_sdwt: int) -> None:
    existing = dummy_users(api)
    teams = org_tree(api)
    if not teams:
        raise SetupError("소속 트리(/org)가 없습니다. 권한관리 웹이나 make keycloak-sdwt-init으로 먼저 만드세요.")
    org = next(client for client in api.call("GET", "clients", query={"clientId": "org"}) if client["clientId"] == "org")
    roles = {role["name"]: role for role in api.call("GET", f"clients/{segment(org['id'])}/roles")}
    serial = created = joined = granted = 0
    sdwt_names = [sdwt["name"] for team in teams for line in team["lines"] for sdwt in line["sdwts"]]

    def grant(user, role_name):
        nonlocal granted
        have = {role["name"] for role in api.call("GET", f"users/{segment(user['id'])}/role-mappings/clients/{segment(org['id'])}")}
        if role_name not in have and role_name in roles:
            api.call("POST", f"users/{segment(user['id'])}/role-mappings/clients/{segment(org['id'])}", [roles[role_name]])
            granted += 1

    for team in teams:
        team_members = []
        for line in team["lines"]:
            line_members = []
            for sdwt in line["sdwts"]:
                for index in range(per_sdwt):
                    serial += 1
                    epid = f"99{serial:06d}"
                    surname, given = SURNAMES[serial % len(SURNAMES)], GIVEN[(serial * 7) % len(GIVEN)]
                    login = f"{ROMAN[surname]}.{serial:04d}"
                    user = existing.get(epid)
                    if user is None:
                        api.call("POST", "users", {
                            "username": epid, "enabled": True, "email": f"{login}@{DOMAIN}", "emailVerified": True,
                            "firstName": given, "lastName": surname,
                            "attributes": {
                                "loginid": [login], "display_name": [f"{surname}{given}"], "sabun": [f"D{serial:06d}"],
                                "deptname": [team["name"]], "user_sdwt_prod": [sdwt["name"]], "line_id": [line["name"]],
                            },
                        })
                        user = api.call("GET", "users", query={"username": epid, "exact": "true"})[0]
                        created += 1
                    # 소속: SDWT 그룹 하나에 가입하면 자기 SDWT 일반 역할을 자동으로 받습니다.
                    if sdwt["id"] not in {group["id"] for group in api.call("GET", f"users/{segment(user['id'])}/groups")}:
                        api.call("PUT", f"users/{segment(user['id'])}/groups/{segment(sdwt['id'])}")
                        joined += 1
                    if index < 2:
                        grant(user, f"sdwt:{sdwt['name']}:admin")  # 분임조장 2명
                    if index == 2 and len(sdwt_names) > 1:
                        # 지원 근무: 다음 SDWT 조회 권한
                        grant(user, f"sdwt:{sdwt_names[(sdwt_names.index(sdwt['name']) + 1) % len(sdwt_names)]}:viewer")
                    line_members.append(user)
                    team_members.append(user)
            if line_members:
                grant(line_members[0], f"team:{team['name']}:line:{line['name']}:admin")
        if team_members:
            grant(team_members[-1], f"team:{team['name']}:admin")
    total = len(sdwt_names)
    print(f"더미 채우기 완료: SDWT {total}개 × {per_sdwt}명, 새 사용자 {created}명, 새 소속 가입 {joined}건, 새 소속별 역할 {granted}건")


def remove(api: Admin) -> None:
    users = dummy_users(api)
    for user in users.values():
        api.call("DELETE", f"users/{segment(user['id'])}")
    print(f"더미 사용자 {len(users)}명을 지웠습니다.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-sdwt", type=int, default=20)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--remove", action="store_true", help="이 스크립트가 만든 더미 사용자만 지웁니다.")
    modes.add_argument("--lines", type=int, help="기존 팀에 배분할 전체 라인 수. SDWT는 라인당 4~5개입니다.")
    parser.add_argument("--total-users", type=int, default=2000, help="--lines 모드의 전체 더미 구성원 수")
    args = parser.parse_args()
    os.environ.setdefault("KEYCLOAK_ADMIN_URL", "http://localhost:8180")
    os.environ.setdefault("KEYCLOAK_ADMIN_REALM", "master")
    try:
        if not os.environ.get("KEYCLOAK_ADMIN_USERNAME"):
            os.environ["KEYCLOAK_ADMIN_USERNAME"] = secret_value("keycloak-admin-username")
            os.environ["KEYCLOAK_ADMIN_PASSWORD"] = secret_value("keycloak-admin-password")
        api = Admin(os.environ.get("KEYCLOAK_TARGET_REALM", "portal"))
        if args.remove:
            remove(api)
        elif args.lines is not None:
            scale(api, args.lines, args.total_users)
        else:
            seed(api, args.per_sdwt)
        return 0
    except (SetupError, subprocess.CalledProcessError) as exc:
        print(f"더미 데이터 작업 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
