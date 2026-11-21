#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/admin-common.sh"
: "${KEYCLOAK_ADMIN_USERNAME:?관리자 계정이 필요합니다.}"
: "${KEYCLOAK_ADMIN_PASSWORD:?관리자 비밀번호가 필요합니다.}"
[[ "$KEYCLOAK_TARGET_REALM" == etch ]] || { echo '이 배포의 대상 realm은 etch입니다.' >&2; exit 1; }
umask 077
kc config credentials --server "$KEYCLOAK_ADMIN_URL" --realm master \
  --user "$KEYCLOAK_ADMIN_USERNAME" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null
# 조회 실패를 realm 부재로 간주하지 않습니다.
definition="$(dirname "${BASH_SOURCE[0]}")/etch-realm.json"
realms="$(kc get realms --fields realm --format csv --noquotes)"
while IFS= read -r realm; do
  if [[ "${realm%$'\r'}" == "$KEYCLOAK_TARGET_REALM" ]]; then
    # 조회 결과를 병합하지 않고 원본에 선언한 realm 속성만 보냅니다.
    kc update "realms/$KEYCLOAK_TARGET_REALM" -n -f "$definition" >/dev/null
    echo 'etch realm 설정 반영 완료.'
    exit 0
  fi
done <<< "$realms"
kc create realms -f "$definition" >/dev/null
echo 'etch realm 생성 완료.'
