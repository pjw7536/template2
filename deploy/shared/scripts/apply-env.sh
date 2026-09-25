#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "${ROOT_DIR}/deploy/shared/scripts/env-lib.sh"
APP="${1:?사용법: apply-env.sh <keycloak|portal> <환경> [server|oidc|api|client|web|minio] [env 파일]}"
PROFILE="${2:?환경 이름이 필요합니다.}"
COMPONENT="${3:-server}"
[[ "$APP/$COMPONENT" != portal/server ]] || COMPONENT=api
if [[ "$APP" == portal && "$PROFILE" != local && "$PROFILE" != prod ]]; then
  echo 'Portal Kubernetes 환경은 local 또는 prod입니다. 운영 입력은 deploy/portal/env/prod를 사용하세요.' >&2
  exit 1
fi
ENV_FILE="${4:-}"
if [[ "$APP/$PROFILE/$COMPONENT" == portal/local/api && -z "$ENV_FILE" ]]; then
  echo '로컬 API는 합성된 env 파일을 네 번째 인자로 전달하세요. 기본 실행은 make k8s-env APP=portal PROFILE=local을 사용하세요.' >&2
  exit 1
fi
[[ -n "$ENV_FILE" ]] || ENV_FILE="$(resolve_env_file "$ROOT_DIR" "$APP" "$PROFILE" "$COMPONENT")"
KUBECTL_BIN="${KUBECTL_BIN:-kubectl}"
echo "설정 입력: $ENV_FILE / 앱: $APP / 작업: $COMPONENT"
load_env "$ENV_FILE"
resolve_keycloak_discovery "$ROOT_DIR" "$APP" "$COMPONENT" "$ENV_FILE"
validate_app_env "$APP" "$COMPONENT"
if [[ "$APP/$PROFILE" == portal/prod ]]; then
  validate_portal_prod_env "$COMPONENT"
fi

case "$APP/$COMPONENT" in
  keycloak/server)
    namespace=etch-sso; secret=keycloak-runtime
    keys=(postgres-password bootstrap-admin-username bootstrap-admin-password keycloak-public-url) ;;
  keycloak/oidc)
    namespace=etch-sso; secret=keycloak-oidc-settings
    keys=(CORP_OIDC_AUTH_URL CORP_OIDC_TOKEN_URL CORP_OIDC_ISSUER CORP_OIDC_CLIENT_ID CORP_OIDC_CLIENT_SECRET CORP_OIDC_CLIENT_AUTH_METHOD CORP_OIDC_VALIDATE_SIGNATURE CORP_OIDC_JWKS_URL CORP_OIDC_USERINFO_URL CORP_OIDC_LOGOUT_URL) ;;
  portal/client)
    namespace=etch-sso; secret=portal-keycloak-client
    keys=(OIDC_CLIENT_ID OIDC_CLIENT_SECRET OIDC_ISSUER OIDC_REDIRECT_URI FRONTEND_BASE_URL) ;;
  portal/api|portal/web|portal/minio)
    namespace=tailwind-internal
    [[ "$PROFILE" != local ]] || namespace=tailwind-local
    secret="$COMPONENT-env"; keys=("${!ENV_VALUES[@]}") ;;
  *) echo '이 앱의 Kubernetes Secret 등록은 지원하지 않습니다.' >&2; exit 1 ;;
esac

umask 077
ENV_TMP="$(mktemp -d)"
trap 'rm -rf -- "$ENV_TMP"' EXIT
for key in "${keys[@]}"; do
  [[ ! -v ENV_VALUES[$key] ]] || printf '%s=%s\n' "$key" "${ENV_VALUES[$key]}"
done > "$ENV_TMP/input.env"
"$KUBECTL_BIN" create secret generic "$secret" -n "$namespace" \
  --from-env-file="$ENV_TMP/input.env" --dry-run=client -o yaml | "$KUBECTL_BIN" apply -f -
echo "설정 등록 완료: $namespace / $secret"
echo '기동 설정은 Pod 재시작 시, 설정 Job 입력은 해당 Job 재실행 시 반영됩니다.'
