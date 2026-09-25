#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/admin-common.sh"
: "${KEYCLOAK_ADMIN_USERNAME:?관리자 계정이 필요합니다.}"
: "${KEYCLOAK_ADMIN_PASSWORD:?관리자 비밀번호가 필요합니다.}"
[[ "$KEYCLOAK_TARGET_REALM" == etch ]] || { echo '이 배포의 대상 realm은 etch입니다.' >&2; exit 1; }
umask 077
kc config credentials --server "$KEYCLOAK_ADMIN_URL" --realm master \
  --user "$KEYCLOAK_ADMIN_USERNAME" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null
# 조회 실패를 realm 부재로 간주하지 않습니다. 기존 realm 설정은 갱신하지 않습니다.
realms="$(kc get realms --fields realm --format csv --noquotes)"
while IFS= read -r realm; do
  if [[ "${realm%$'\r'}" == "$KEYCLOAK_TARGET_REALM" ]]; then
    echo 'etch realm이 이미 있어 기존 설정을 유지합니다.'
    exit 0
  fi
done <<< "$realms"
kc create realms -f "$(dirname "${BASH_SOURCE[0]}")/etch-realm.json" >/dev/null
echo 'etch realm 생성 완료.'
