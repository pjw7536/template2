#!/usr/bin/env python3
"""기존 커스텀 속성을 사내 claim 이름으로 복사합니다. 기본은 dry-run입니다."""

import argparse
from copy import deepcopy
import os
import sys

from init_sdwt import Admin, SetupError, segment


RENAMES = {"knox_id": "loginid", "department": "deptname", "grd_name": "grdName"}


def migrated_attributes(attributes):
    """기존 값을 보존하고 비어 있는 새 속성만 채웁니다. 충돌은 중단합니다."""
    result = deepcopy(attributes)
    for old, new in RENAMES.items():
        source = attributes.get(old, [])
        target = attributes.get(new, [])
        for values in (source, target):
            if (not isinstance(values, list) or len(values) > 1
                    or any(not isinstance(value, str) for value in values)):
                raise SetupError("이전/신규 속성의 단일 문자열 계약이 다릅니다. 사용자 속성을 검토하세요.")
        if not source or source == [""]:
            continue
        if target and target != [""] and target != source:
            raise SetupError("이전/신규 속성값이 충돌합니다. 값을 검토한 후 다시 실행하세요.")
        result[new] = source.copy()
    return result


def migrate(api, apply=False):
    """전체 충돌 검사 후 저장 직전 재확인하며 사용자 신원·권한은 유지합니다."""
    profile = api.call("GET", "users/profile")
    if not set(RENAMES.values()) <= {a["name"] for a in profile.get("attributes", [])}:
        raise SetupError("User Profile 등록을 먼저 실행하세요.")
    if profile.get("unmanagedAttributePolicy") != "ADMIN_EDIT":
        raise SetupError("이전 속성 보존을 위해 User Profile의 ADMIN_EDIT 정책이 필요합니다.")
    planned = []
    for user in api.pages("users", briefRepresentation="false"):
        original = user.get("attributes", {})
        updated = migrated_attributes(original)
        if updated != original:
            planned.append((user["id"], original, updated))
    print(f"계획: 사용자 {len(planned)}명의 누락된 새 속성 복사, 이전 속성 보존")
    if not apply:
        print("dry-run 완료. 실제 복사는 --apply로 실행하세요.")
        return
    for user_id, original, updated in planned:
        endpoint = f"users/{segment(user_id)}"
        current = api.call("GET", endpoint)
        if current.get("attributes", {}) != original:
            raise SetupError("검사 후 사용자 속성이 변경되었습니다. 동시 수정을 멈추고 재실행하세요. 앞서 완료된 복사는 유지됩니다.")
        api.call("PUT", endpoint, {"attributes": updated})
    print("복사 완료. 기존 속성·사용자 ID·그룹·broker 연결은 유지합니다.")


def main(argv=None):
    """관리자 인증은 SDWT 도구와 같은 환경변수로만 받습니다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--realm", default=os.environ.get("KEYCLOAK_TARGET_REALM", "etch"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.realm or args.realm == "master":
            raise SetupError("업무 realm을 지정하세요. master는 변경할 수 없습니다.")
        migrate(Admin(args.realm), args.apply)
    except SetupError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
