#!/usr/bin/env bash
# 관리 작업에서 공통으로 사용하는 Admin CLI 호출과 JSON 문자열 처리입니다.
KCADM_BIN="${KCADM_BIN:-/opt/keycloak/bin/kcadm.sh}"
KEYCLOAK_ADMIN_URL="${KEYCLOAK_ADMIN_URL:-http://keycloak:8080}"
KEYCLOAK_TARGET_REALM="${KEYCLOAK_TARGET_REALM:-etch}"
KCADM_CONFIG="${KCADM_CONFIG:-/tmp/keycloak-admin.config}"

json_string() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '"%s"' "$value"
}

kc() {
  # Admin API 오류 응답에 credential이 포함될 수 있어 원문을 로그에 남기지 않습니다.
  if ! "$KCADM_BIN" "$@" --config "$KCADM_CONFIG" 2>/dev/null; then
    echo 'Keycloak 관리 요청 실패: 연결, 계정 권한과 입력 설정을 확인하세요.' >&2
    return 1
  fi
}

admin_login() {
  : "${KEYCLOAK_ADMIN_USERNAME:?관리자 계정이 필요합니다.}"
  : "${KEYCLOAK_ADMIN_PASSWORD:?관리자 비밀번호가 필요합니다.}"
  umask 077
  kc config credentials --server "$KEYCLOAK_ADMIN_URL" --realm master \
    --user "$KEYCLOAK_ADMIN_USERNAME" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null
  kc get "realms/$KEYCLOAK_TARGET_REALM" >/dev/null
}
