#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "${ROOT_DIR}/deploy/shared/scripts/env-lib.sh"
APP="${1:?사용법: check-env.sh <앱> <환경> [server|oidc|api|client|web|minio] [파일]}"
PROFILE="${2:?환경 이름이 필요합니다.}"
COMPONENT="${3:-server}"
[[ "$APP/$COMPONENT" != portal/server ]] || COMPONENT=api
ENV_FILE="${4:-}"
[[ -n "$ENV_FILE" ]] || ENV_FILE="$(resolve_env_file "$ROOT_DIR" "$APP" "$PROFILE" "$COMPONENT")"
# Helm 앱은 각 앱의 Kubernetes 입력·렌더 검사 계약을 재사용합니다.
case "$APP" in
  airflow|monitoring|headlamp)
    [[ "$PROFILE/$COMPONENT" == prod/server ]] || { echo '이 앱은 prod/server Kubernetes 검사를 사용하세요.' >&2; exit 1; }
    exec python3 "$ROOT_DIR/deploy/$APP/scripts/manage.py" check --env "$ENV_FILE" ;;
esac
[[ "$PROFILE" != oidc ]] || { echo '폐기된 oidc 환경입니다. prod를 사용하세요.' >&2; exit 1; }
echo "선택한 앱: $APP / 환경: $PROFILE / 작업: $COMPONENT"
echo "읽는 설정: $ENV_FILE"
load_env "$ENV_FILE"
resolve_keycloak_discovery "$ROOT_DIR" "$APP" "$COMPONENT" "$ENV_FILE"
validate_app_env "$APP" "$COMPONENT"
if [[ "$APP/$PROFILE" == portal/prod ]]; then
  validate_portal_prod_env "$COMPONENT"
fi
echo '설정 검사 통과 (설정값은 출력하지 않습니다.)'
