#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/admin-common.sh"
KEYCLOAK_IDP_ALIAS="${KEYCLOAK_IDP_ALIAS:-oidc}"
for key in CORP_OIDC_AUTH_URL CORP_OIDC_TOKEN_URL CORP_OIDC_ISSUER CORP_OIDC_CLIENT_ID CORP_OIDC_CLIENT_SECRET CORP_OIDC_CLIENT_AUTH_METHOD CORP_OIDC_VALIDATE_SIGNATURE; do
  [[ -n "${!key:-}" ]] || { echo "필수 설정 누락: $key" >&2; exit 1; }
done
case "$CORP_OIDC_CLIENT_AUTH_METHOD" in
  client_secret_basic|client_secret_post) ;;
  *) echo '사내 OIDC client 인증 방식 오류' >&2; exit 1 ;;
esac
case "$CORP_OIDC_VALIDATE_SIGNATURE" in
  true) : "${CORP_OIDC_JWKS_URL:?서명 검증에 필요한 JWKS URL이 없습니다.}" ;;
  false) ;;
  *) echo '서명 검증 설정은 true 또는 false여야 합니다.' >&2; exit 1 ;;
esac
admin_login
endpoint="identity-provider/instances"
aliases="$(kc get "$endpoint" -r "$KEYCLOAK_TARGET_REALM" --fields alias --format csv --noquotes)"
operation=create
while IFS= read -r alias; do
  if [[ "${alias%$'\r'}" == "$KEYCLOAK_IDP_ALIAS" ]]; then
    operation=update
    endpoint="$endpoint/$KEYCLOAK_IDP_ALIAS"
  fi
done <<< "$aliases"
args=(--set "alias=$(json_string "$KEYCLOAK_IDP_ALIAS")" --set providerId=oidc --set enabled=true)
# update의 GET/merge 동작으로 지정하지 않은 기존 연결·로그인 정책을 보존합니다.
for pair in authorizationUrl:CORP_OIDC_AUTH_URL tokenUrl:CORP_OIDC_TOKEN_URL issuer:CORP_OIDC_ISSUER clientId:CORP_OIDC_CLIENT_ID clientSecret:CORP_OIDC_CLIENT_SECRET clientAuthMethod:CORP_OIDC_CLIENT_AUTH_METHOD validateSignature:CORP_OIDC_VALIDATE_SIGNATURE; do
  property="${pair%%:*}"; key="${pair#*:}"
  args+=(--set "config.$property=$(json_string "${!key}")")
done
if [[ "$CORP_OIDC_VALIDATE_SIGNATURE" == true ]]; then
  args+=(--set 'config.useJwksUrl="true"' --set "config.jwksUrl=$(json_string "$CORP_OIDC_JWKS_URL")")
fi
for pair in userInfoUrl:CORP_OIDC_USERINFO_URL logoutUrl:CORP_OIDC_LOGOUT_URL; do
  property="${pair%%:*}"; key="${pair#*:}"
  [[ -z "${!key:-}" ]] || args+=(--set "config.$property=$(json_string "${!key}")")
done
if [[ "$operation" == create ]]; then
  args+=(--set 'displayName="사내 로그인"' --set 'config.defaultScope="openid"')
fi
kc "$operation" "$endpoint" -r "$KEYCLOAK_TARGET_REALM" "${args[@]}" >/dev/null
echo '사내 OIDC 설정 완료. 기존 사용자와 realm은 유지됩니다.'
