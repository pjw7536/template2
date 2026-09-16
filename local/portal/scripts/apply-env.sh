#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
COMPONENT="${1:-api}"
[[ "$COMPONENT" != server ]] || COMPONENT=api
ENV_FILE="${2:-}"

# 기본 API 입력은 로컬 기동과 같은 합성 규칙으로 준비한다.
if [[ "$COMPONENT" == api && -z "$ENV_FILE" ]]; then
  umask 077
  LOCAL_ENV_TMP="$(mktemp -d)"
  trap 'rm -rf -- "$LOCAL_ENV_TMP"' EXIT
  ENV_FILE="$LOCAL_ENV_TMP/api.env"
  bash "$ROOT_DIR/local/portal/scripts/build-local-api-env.sh" "$ENV_FILE"
fi
bash "$ROOT_DIR/deploy/shared/scripts/apply-env.sh" portal local "$COMPONENT" "$ENV_FILE"
