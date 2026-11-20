#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$ROOT_DIR/deploy/shared/scripts/env-lib.sh"
SELECT_APP="${1:-all}"
SELECT_PROFILE="${2:-all}"

# 선택한 앱·환경의 추적 env를 필수로 요구하고 형식을 검사합니다.
required_files=(
  "shared local local/shared/env/k8s.env.example"
  "portal local local/portal/env/api.env"
  "portal local local/portal/env/api-k8s.env"
  "portal local local/portal/env/web.env"
  "minio local local/minio/env/minio.env"
  "portal prod deploy/portal/env/prod/api.env"
  "portal prod deploy/portal/env/prod/web.env"
  "minio prod deploy/minio/env/prod.env"
  "keycloak prod deploy/keycloak/env/prod.env"
  "airflow prod deploy/airflow/env/k8s.env"
  "airflow prod deploy/airflow/env/build.env"
  "monitoring prod deploy/monitoring/env/k8s.env"
  "headlamp prod deploy/headlamp/env/k8s.env"
  "ftp prod deploy/ftp/env/prod.env"
  "registry prod deploy/registry/env/k8s.env"
  "iam prod deploy/iam/env/prod.env"
  "shared prod deploy/shared/env/node-exec.env"
  "portal test deploy/portal/env/test/api.env"
)
selected_count=0
for entry in "${required_files[@]}"; do
  read -r app profile relative_path <<< "$entry"
  [[ "$SELECT_APP" == all || "$SELECT_APP" == "$app" ]] || continue
  [[ "$SELECT_PROFILE" == all || "$SELECT_PROFILE" == "$profile" ]] || continue
  selected_count=$((selected_count + 1))
  file="$ROOT_DIR/$relative_path"
  ENV_VALUES=()
  load_env "$file"
  if [[ "$file" == *.example && -f "${file%.example}" ]]; then
    ENV_VALUES=()
    load_env "${file%.example}"
  fi
done
[[ "$selected_count" -gt 0 ]] || { echo "지원하지 않는 앱·환경 조합: $SELECT_APP/$SELECT_PROFILE" >&2; exit 1; }

echo "env profile key validation passed"
