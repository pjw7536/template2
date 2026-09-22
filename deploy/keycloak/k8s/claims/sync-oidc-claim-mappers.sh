#!/usr/bin/env bash
set -Eeuo pipefail

# 사내 OIDC claim을 Keycloak 사용자 속성과 Portal token claim으로 동기화합니다.
readonly KCADM_BIN="${KCADM_BIN:-/opt/keycloak/bin/kcadm.sh}"
readonly KEYCLOAK_ADMIN_URL="${KEYCLOAK_ADMIN_URL:-http://keycloak:8080}"
readonly KEYCLOAK_TARGET_REALM="${KEYCLOAK_TARGET_REALM:-etch}"
readonly KEYCLOAK_IDP_ALIAS="${KEYCLOAK_IDP_ALIAS:-oidc}"
readonly KEYCLOAK_TARGET_CLIENT="${KEYCLOAK_TARGET_CLIENT:-portal}"
readonly KEYCLOAK_MAPPING_TARGET="${KEYCLOAK_MAPPING_TARGET:-all}"
readonly KCADM_CONFIG="${KCADM_CONFIG:-/tmp/keycloak-claims.config}"

kcadm() {
  if ! "$KCADM_BIN" "$@" --config "$KCADM_CONFIG" 2>/dev/null; then
    echo 'Keycloak 관리 요청 실패: 연결과 관리자 권한을 확인하세요.' >&2
    return 1
  fi
}
readonly CLAIMS=(
  loginid
  userid
  sabun
  username
  username_en
  givenname
  surname
  deptname
  deptid
  mail
  grdName
  grdname_en
  busname
  intcode
  intname
  employeetype
)

# 사내 claim과 account_user에 대응하는 Keycloak 속성 이름을 분리합니다.
profile_attribute() {
  case "$1" in
    loginid) printf '%s' knox_id ;;
    userid) printf '%s' username ;;
    username) printf '%s' display_name ;;
    givenname) printf '%s' firstName ;;
    surname) printf '%s' lastName ;;
    deptname) printf '%s' department ;;
    mail) printf '%s' email ;;
    grdName) printf '%s' grd_name ;;
    *) printf '%s' "$1" ;;
  esac
}

require_value() {
  local name="$1"
  local value="$2"

  if [[ -z "$value" ]]; then
    echo "필수 환경변수가 비어 있습니다: $name" >&2
    exit 1
  fi
}

login_admin() {
  local attempt

  for ((attempt = 1; attempt <= 60; attempt += 1)); do
    if kcadm config credentials \
      --server "$KEYCLOAK_ADMIN_URL" \
      --realm master \
      --user "$KEYCLOAK_ADMIN_USERNAME" \
      --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null 2>&1; then
      echo "Keycloak Admin API 로그인이 완료됐습니다."
      return 0
    fi

    echo "Keycloak Admin API 대기 중입니다. 시도: $attempt/60"
    sleep 5
  done

  echo "Keycloak Admin API 로그인에 실패했습니다." >&2
  return 1
}

find_mapper_id() {
  local endpoint="$1"
  local target_name="$2"
  local rows
  local first
  local second

  rows="$(
    kcadm get "$endpoint" \
      -r "$KEYCLOAK_TARGET_REALM" \
      --fields id,name \
      --format csv \
      --noquotes
  )" || return 2

  while IFS=, read -r first second; do
    first="${first%$'\r'}"
    second="${second%$'\r'}"

    if [[ "$first" == "$target_name" && -n "$second" ]]; then
      printf '%s' "$second"
      return 0
    fi

    if [[ "$second" == "$target_name" && -n "$first" ]]; then
      printf '%s' "$first"
      return 0
    fi
  done <<< "$rows"

  return 1
}

find_client_uuid() {
  local rows
  local row

  rows="$(
    kcadm get clients \
      -r "$KEYCLOAK_TARGET_REALM" \
      --query "clientId=$KEYCLOAK_TARGET_CLIENT" \
      --fields id \
      --format csv \
      --noquotes
  )"

  while IFS= read -r row; do
    row="${row%$'\r'}"
    if [[ -n "$row" ]]; then
      printf '%s' "$row"
      return 0
    fi
  done <<< "$rows"

  return 1
}

sync_idp_mapper() {
  local claim="$1"
  local endpoint="identity-provider/instances/${KEYCLOAK_IDP_ALIAS}/mappers"
  local mapper_id
  local mapper_config
  local attribute
  attribute="$(profile_attribute "$claim")"

  mapper_config="{\"syncMode\":\"FORCE\",\"claim\":\"${claim}\",\"user.attribute\":\"${attribute}\"}"

  if mapper_id="$(find_mapper_id "$endpoint" "$claim")"; then
    kcadm update "${endpoint}/${mapper_id}" \
      -r "$KEYCLOAK_TARGET_REALM" \
      --set "name=$claim" \
      --set "identityProviderAlias=$KEYCLOAK_IDP_ALIAS" \
      --set identityProviderMapper=oidc-user-attribute-idp-mapper \
      --set "config=$mapper_config" >/dev/null
    echo "IdP mapper 갱신: $claim"
    return 0
  else
    # 조회 오류를 mapper 부재로 처리하면 중복을 만들 수 있어 즉시 중단합니다.
    [[ "$?" == 1 ]] || return 1
  fi

  kcadm create "$endpoint" \
    -r "$KEYCLOAK_TARGET_REALM" \
    --set "name=$claim" \
    --set "identityProviderAlias=$KEYCLOAK_IDP_ALIAS" \
    --set identityProviderMapper=oidc-user-attribute-idp-mapper \
    --set "config=$mapper_config" >/dev/null
  echo "IdP mapper 생성: $claim"
}

# 사내 EPID는 기본 username에만 반영하고 기존 broker 연결 식별자는 유지합니다.
sync_epid_username_mapper() {
  local endpoint="identity-provider/instances/${KEYCLOAK_IDP_ALIAS}/mappers"
  local name=epid-username mapper_id
  local mapper_config='{"syncMode":"FORCE","template":"${CLAIM.userid}","target":"LOCAL"}'

  if mapper_id="$(find_mapper_id "$endpoint" "$name")"; then
    kcadm update "${endpoint}/${mapper_id}" \
      -r "$KEYCLOAK_TARGET_REALM" \
      --set "name=$name" \
      --set "identityProviderAlias=$KEYCLOAK_IDP_ALIAS" \
      --set identityProviderMapper=oidc-username-idp-mapper \
      --set "config=$mapper_config" >/dev/null
    echo "EPID username mapper 갱신 완료"
    return 0
  else
    [[ "$?" == 1 ]] || return 1
  fi

  kcadm create "$endpoint" \
    -r "$KEYCLOAK_TARGET_REALM" \
    --set "name=$name" \
    --set "identityProviderAlias=$KEYCLOAK_IDP_ALIAS" \
    --set identityProviderMapper=oidc-username-idp-mapper \
    --set "config=$mapper_config" >/dev/null
  echo "EPID username mapper 생성 완료"
}

sync_client_mapper() {
  local client_uuid="$1"
  local claim="$2"
  local endpoint="clients/${client_uuid}/protocol-mappers/models"
  local mapper_id
  local mapper_config
  local attribute
  attribute="$(profile_attribute "$claim")"

  mapper_config="{\"user.attribute\":\"${attribute}\",\"claim.name\":\"${claim}\",\"jsonType.label\":\"String\",\"multivalued\":\"false\",\"id.token.claim\":\"true\",\"access.token.claim\":\"true\",\"userinfo.token.claim\":\"true\"}"
  # EPID·이메일·성·이름은 Keycloak 기본 사용자 property에서 읽습니다.
  local mapper_type=oidc-usermodel-attribute-mapper
  if [[ "$attribute" == username || "$attribute" == email || "$attribute" == firstName || "$attribute" == lastName ]]; then
    mapper_type=oidc-usermodel-property-mapper
  fi


  if mapper_id="$(find_mapper_id "$endpoint" "$claim")"; then
    kcadm update "${endpoint}/${mapper_id}" \
      -r "$KEYCLOAK_TARGET_REALM" \
      --set "name=$claim" \
      --set protocol=openid-connect \
      --set "protocolMapper=$mapper_type" \
      --set "config=$mapper_config" >/dev/null
    echo "Portal token mapper 갱신: $claim"
    return 0
  else
    [[ "$?" == 1 ]] || return 1
  fi

  kcadm create "$endpoint" \
    -r "$KEYCLOAK_TARGET_REALM" \
    --set "name=$claim" \
    --set protocol=openid-connect \
    --set "protocolMapper=$mapper_type" \
    --set "config=$mapper_config" >/dev/null
  echo "Portal token mapper 생성: $claim"
}

# 이전 배포에서 생성한 폐기 mapper만 이름으로 찾아 제거합니다.
remove_retired_mapper() {
  local endpoint="$1" name="$2" mapper_id
  if mapper_id="$(find_mapper_id "$endpoint" "$name")"; then
    kcadm delete "${endpoint}/${mapper_id}" -r "$KEYCLOAK_TARGET_REALM" >/dev/null
    echo "폐기 mapper 삭제: $name"
  else
    # 조회 실패를 이미 삭제된 상태로 처리하지 않습니다.
    [[ "$?" == 1 ]] || return 1
  fi
}

require_value KEYCLOAK_ADMIN_USERNAME "${KEYCLOAK_ADMIN_USERNAME:-}"
require_value KEYCLOAK_ADMIN_PASSWORD "${KEYCLOAK_ADMIN_PASSWORD:-}"
case "$KEYCLOAK_MAPPING_TARGET" in
  idp|client|all) ;;
  *) echo 'KEYCLOAK_MAPPING_TARGET은 idp, client, all 중 하나여야 합니다.' >&2; exit 1 ;;
esac
login_admin

if [[ "$KEYCLOAK_MAPPING_TARGET" != client ]] && ! kcadm get \
  "identity-provider/instances/$KEYCLOAK_IDP_ALIAS" \
  -r "$KEYCLOAK_TARGET_REALM" >/dev/null; then
  echo "Identity Provider를 찾을 수 없습니다: $KEYCLOAK_IDP_ALIAS" >&2
  exit 1
fi

if [[ "$KEYCLOAK_MAPPING_TARGET" != idp ]] && ! client_uuid="$(find_client_uuid)"; then
  echo "OIDC client를 찾을 수 없습니다: $KEYCLOAK_TARGET_CLIENT" >&2
  exit 1
fi

# 이메일을 username으로 쓰는 realm에서는 LOCAL mapper가 무시되므로 변경 전에 중단합니다.
if [[ "$KEYCLOAK_MAPPING_TARGET" != client ]]; then
  email_as_username="$(kcadm get "realms/$KEYCLOAK_TARGET_REALM" \
    --fields registrationEmailAsUsername --format csv --noquotes)"
  case "${email_as_username%$'\r'}" in
    false) ;;
    true)
      echo 'EPID username을 사용하려면 realm의 Email as username 설정을 먼저 꺼야 합니다.' >&2
      exit 1 ;;
    *)
      echo 'realm의 Email as username 설정을 확인할 수 없습니다.' >&2
      exit 1 ;;
  esac
fi

# 사용자 승인대로 프로필 정의를 교체하며 실제 사용자 레코드는 삭제하지 않습니다.
if [[ "$KEYCLOAK_MAPPING_TARGET" != client ]]; then
  kcadm update users/profile \
    -r "$KEYCLOAK_TARGET_REALM" \
    -n -f "${KEYCLOAK_CONFIG_DIR:-/opt/keycloak-config}/account-user-profile.json" >/dev/null
  echo "account_user 기준 User Profile 등록 완료"
fi

for retired_claim in origincomp first_name last_name; do
  if [[ "$KEYCLOAK_MAPPING_TARGET" != client ]]; then
    remove_retired_mapper "identity-provider/instances/${KEYCLOAK_IDP_ALIAS}/mappers" "$retired_claim"
  fi
  if [[ "$KEYCLOAK_MAPPING_TARGET" != idp ]]; then
    remove_retired_mapper "clients/${client_uuid}/protocol-mappers/models" "$retired_claim"
  fi
done

# EPID는 기본 username에만 저장하므로 이전 avatarid 수집 mapper를 제거합니다.
if [[ "$KEYCLOAK_MAPPING_TARGET" != client ]]; then
  remove_retired_mapper "identity-provider/instances/${KEYCLOAK_IDP_ALIAS}/mappers" userid
fi

for claim in "${CLAIMS[@]}"; do
  if [[ "$KEYCLOAK_MAPPING_TARGET" != client && "$claim" != userid ]]; then
    sync_idp_mapper "$claim"
  fi
  if [[ "$KEYCLOAK_MAPPING_TARGET" != idp ]]; then
    sync_client_mapper "$client_uuid" "$claim"
  fi
done

if [[ "$KEYCLOAK_MAPPING_TARGET" != client ]]; then
  sync_epid_username_mapper
fi

echo "사내 OIDC claim ${#CLAIMS[@]}개의 동기화가 완료됐습니다. 대상: $KEYCLOAK_MAPPING_TARGET"
