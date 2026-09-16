#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$ROOT_DIR/deploy/shared/scripts/env-lib.sh"
SELECT_APP="${1:-all}"
SELECT_PROFILE="${2:-all}"
case "$SELECT_APP" in all|portal|keycloak|airflow|monitoring|headlamp|shared) ;; *) echo '지원하지 않는 앱입니다.' >&2; exit 1 ;; esac
case "$SELECT_PROFILE" in all|local|prod|test) ;; *) echo '지원하지 않는 환경입니다.' >&2; exit 1 ;; esac

# 선택한 앱·환경의 공개 입력만 필수로 요구합니다. 실제 운영 env는 있을 때만 형식을 검사합니다.
required_files=(
  "shared local local/shared/env/k8s.env.example"
  "portal local local/portal/env/api.env"
  "portal local local/portal/env/api-k8s.env"
  "portal local local/portal/env/web.env"
  "portal local local/portal/env/minio.env"
  "portal prod deploy/portal/env/prod/api.env.example"
  "portal prod deploy/portal/env/prod/web.env.example"
  "portal prod deploy/portal/env/prod/minio.env.example"
  "keycloak prod deploy/keycloak/env/prod.env.example"
  "airflow prod deploy/airflow/env/k8s.env.example"
  "airflow prod deploy/airflow/env/build.env.example"
  "monitoring prod deploy/monitoring/env/k8s.env.example"
  "headlamp prod deploy/headlamp/env/k8s.env.example"
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
  legacy_file="$(
    find "${file%/*}" -maxdepth 1 -type f \
      \( -name '*.config.env' -o -name '*.secret.env' \) -print -quit
  )"
  if [[ -n "$legacy_file" ]]; then
    echo "이전 config/secret 환경변수 파일을 단일 env로 통합해야 합니다: $legacy_file" >&2
    exit 1
  fi
done
[[ "$selected_count" -gt 0 ]] || { echo "지원하지 않는 앱·환경 조합: $SELECT_APP/$SELECT_PROFILE" >&2; exit 1; }

echo "env profile key validation passed"
