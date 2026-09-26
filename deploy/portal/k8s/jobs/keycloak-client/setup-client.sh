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

# 사용자에게 권한을 부여하지 않고 Portal 전용 역할·발급 계약만 준비합니다.
client_id="$(kc get clients -r "$KEYCLOAK_TARGET_REALM" -q "clientId=$OIDC_CLIENT_ID" --fields id --format csv --noquotes)"
[[ -n "$client_id" && "$client_id" != *$'\n'* ]] || { echo 'Portal client 식별 실패' >&2; exit 1; }
role_names="$(kc get "clients/$client_id/roles" -r "$KEYCLOAK_TARGET_REALM" --fields name --format csv --noquotes)"
roles=(portal-all-apps portal-admin)
for scope in access-stats appstore assistant emails l0-spider l1-spider l3-spider line-dashboard observer pm-spider teamstaff tttm-spider voc; do
  roles+=("$scope-user")
done
for scope in access-stats appstore emails l3-spider line-dashboard voc; do
  roles+=("$scope-admin")
done
for role in "${roles[@]}"; do
  if ! grep -Fxq "$role" <<< "$role_names"; then
    kc create "clients/$client_id/roles" -r "$KEYCLOAK_TARGET_REALM" -s "name=$(json_string "$role")" >/dev/null
  fi
done

# 같은 이름의 mapper만 upsert하여 기존 client 설정을 보존합니다.
for mapper in portal-app-roles portal-sdwt-groups; do
  mapper_rows="$(kc get "clients/$client_id/protocol-mappers/models" -r "$KEYCLOAK_TARGET_REALM" --fields id,name --format csv --noquotes)"
  mapper_id=""
  while IFS=, read -r candidate_id candidate_name; do
    if [[ "${candidate_name%$'\r'}" == "$mapper" ]]; then
      [[ -z "$mapper_id" ]] || { echo '중복 Portal mapper' >&2; exit 1; }
      mapper_id="$candidate_id"
    fi
  done <<< "$mapper_rows"
  [[ "$mapper_id" != *$'\n'* ]] || { echo '중복 Portal mapper' >&2; exit 1; }
  mapper_args=(-s "name=$(json_string "$mapper")" -s protocol=openid-connect
    -s 'config."id.token.claim"="true"' -s 'config."access.token.claim"="true"'
    -s 'config."userinfo.token.claim"="true"')
  if [[ "$mapper" == portal-app-roles ]]; then
    mapper_args+=(-s protocolMapper=oidc-usermodel-client-role-mapper
      -s "config.\"usermodel.clientRoleMapping.clientId\"=$(json_string "$OIDC_CLIENT_ID")"
      -s "config.\"claim.name\"=$(json_string "resource_access.$OIDC_CLIENT_ID.roles")"
      -s 'config."jsonType.label"="String"' -s 'config.multivalued="true"')
  else
    mapper_args+=(-s protocolMapper=oidc-group-membership-mapper
      -s 'config."claim.name"="groups"' -s 'config."full.path"="true"')
  fi
  if [[ -n "$mapper_id" ]]; then
    kc update "clients/$client_id/protocol-mappers/models/$mapper_id" -r "$KEYCLOAK_TARGET_REALM" "${mapper_args[@]}" >/dev/null
  else
    kc create "clients/$client_id/protocol-mappers/models" -r "$KEYCLOAK_TARGET_REALM" "${mapper_args[@]}" >/dev/null
  fi
done
echo 'Portal 앱 역할과 SDWT 그룹 발급 설정 완료. 사용자 역할은 관리자가 지정하세요.'

# 조직 정책에 따른 구성원 지정은 운영자가 수행하고 Portal에는 그룹의 client 역할을 발급합니다.
group_names="$(kc get groups -r "$KEYCLOAK_TARGET_REALM" -q search=portal-members -q exact=true --fields name --format csv --noquotes)"
if ! grep -Fxq portal-members <<< "$group_names"; then
  kc create groups -r "$KEYCLOAK_TARGET_REALM" -s 'name="portal-members"' >/dev/null
fi
kc add-roles -r "$KEYCLOAK_TARGET_REALM" --gname portal-members \
  --cclientid "$OIDC_CLIENT_ID" --rolename portal-all-apps >/dev/null
echo 'portal-members 표준 그룹 준비 완료. 조직 정책에 따라 운영자가 구성원을 지정하세요.'
