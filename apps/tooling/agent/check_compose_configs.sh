#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"
bash ./deploy/shared/scripts/validate_env_profile_keys.sh

# 실제 runtime·비밀값 없이 남아 있는 세 Compose 구성을 검사합니다.
CHECK_TMP="$(mktemp -d)"
trap 'rm -rf -- "$CHECK_TMP"' EXIT
printf 'DJANGO_SETTINGS_MODULE=api.settings\n' > "$CHECK_TMP/api.env"
export K8S_API_ENV_FILE="$CHECK_TMP/api.env"
export POSTGRES_PASSWORD=compose-check-only
export PORTAL_DB_PASSWORD=compose-check-only
export AIRFLOW_DB_PASSWORD=compose-check-only
export KEYCLOAK_DB_PASSWORD=compose-check-only
export LOCAL_DB_PORT=55432

docker compose --env-file /dev/null -f local/shared/compose/k8s-db.yml config --quiet
docker compose --env-file /dev/null -f local/shared/compose/k8s-check.yml config --quiet
docker compose --env-file /dev/null -f deploy/portal/compose/test.yml config --quiet

echo 'compose config passed: local database, local API checks, CI'
