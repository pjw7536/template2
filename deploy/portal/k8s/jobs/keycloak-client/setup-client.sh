#!/usr/bin/env bash
set -Eeuo pipefail
CONFIG_DIR="${KEYCLOAK_CONFIG_DIR:-/opt/keycloak-config}"
source "$CONFIG_DIR/admin-common.sh"
for key in OIDC_CLIENT_ID OIDC_CLIENT_SECRET OIDC_ISSUER OIDC_REDIRECT_URI FRONTEND_BASE_URL KEYCLOAK_PUBLIC_URL; do
  [[ -n "${!key:-}" ]] || { echo "필수 설정 누락: $key" >&2; exit 1; }
done
if [[ "$OIDC_ISSUER" != "${KEYCLOAK_PUBLIC_URL%/}/realms/$KEYCLOAK_TARGET_REALM" ]]; then
  echo 'Portal issuer가 대상 Keycloak realm과 다릅니다.' >&2; exit 1
fi
admin_login
rows="$(kc get clients -r "$KEYCLOAK_TARGET_REALM" -q "clientId=$OIDC_CLIENT_ID" --fields id --format csv --noquotes)"
ids=()
while IFS= read -r id; do
  id="${id%$'\r'}"; [[ -z "$id" ]] || ids+=("$id")
done <<< "$rows"
[[ "${#ids[@]}" -le 1 ]] || { echo 'client ID가 하나로 식별되지 않습니다.' >&2; exit 1; }
args=(--set "clientId=$(json_string "$OIDC_CLIENT_ID")" --set protocol=openid-connect --set enabled=true
  --set publicClient=false --set standardFlowEnabled=true --set directAccessGrantsEnabled=false
  --set "secret=$(json_string "$OIDC_CLIENT_SECRET")"
  --set "redirectUris=[$(json_string "$OIDC_REDIRECT_URI")]"
  --set "webOrigins=[$(json_string "$FRONTEND_BASE_URL")]"
  --set 'attributes."pkce.code.challenge.method"="S256"'
  --set "attributes.\"post.logout.redirect.uris\"=$(json_string "${FRONTEND_BASE_URL%/}/*")")
if [[ "${#ids[@]}" == 0 ]]; then
  args+=(--set 'name="Portal"' --set 'defaultClientScopes=["web-origins","acr","roles","profile","email"]'
    --set 'optionalClientScopes=["address","phone","offline_access","microprofile-jwt"]')
  kc create clients -r "$KEYCLOAK_TARGET_REALM" "${args[@]}" >/dev/null
else
  kc update "clients/${ids[0]}" -r "$KEYCLOAK_TARGET_REALM" "${args[@]}" >/dev/null
fi
# 앱의 token mapper는 해당 앱을 등록할 때 설정합니다. 사내 IdP 연결은 건드리지 않습니다.
KEYCLOAK_MAPPING_TARGET=client KEYCLOAK_TARGET_CLIENT="$OIDC_CLIENT_ID" \
  bash "$CONFIG_DIR/sync-oidc-claim-mappers.sh"
echo 'Portal client와 token mapper 등록 완료.'
