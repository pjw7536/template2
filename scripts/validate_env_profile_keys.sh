#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="$ROOT_DIR/env"

required_files=(
  overlays/local/api.config.env
  overlays/local/api.secret.env
  overlays/local/web.config.env
  overlays/local/web.secret.env
  overlays/local/airflow.config.env
  overlays/local/airflow.secret.env
  overlays/local/minio.config.env
  overlays/local/minio.secret.env
  overlays/oidc/api.config.env
  overlays/oidc/api.secret.env
  overlays/oidc/web.config.env
  overlays/oidc/web.secret.env
  overlays/oidc/airflow.config.env
  overlays/oidc/airflow.secret.env
  overlays/oidc/minio.config.env
  overlays/oidc/minio.secret.env
  overlays/oidc/grafana.config.env
  overlays/oidc/grafana.secret.env
  overlays/prod/api.config.env
  overlays/prod/api.secret.env
  overlays/prod/web.config.env
  overlays/prod/web.secret.env
  overlays/prod/airflow.config.env
  overlays/prod/airflow.secret.env
  overlays/prod/minio.config.env
  overlays/prod/minio.secret.env
  overlays/prod/grafana.config.env
  overlays/prod/grafana.secret.env
  overlays/test/api.config.env
  overlays/test/api.secret.env
)

for relative_path in "${required_files[@]}"; do
  if [[ ! -f "$ENV_DIR/$relative_path" ]]; then
    echo "환경변수 파일이 없습니다: env/$relative_path" >&2
    exit 1
  fi
done

if find "$ENV_DIR/base" -maxdepth 1 -type f -print -quit 2>/dev/null | grep -q .; then
  echo "env/base에는 환경변수 파일을 둘 수 없습니다." >&2
  exit 1
fi

# 한 파일 안의 중복 key는 마지막 값이 조용히 덮어써지는 문제를 만들므로 차단합니다.
while IFS= read -r env_file; do
  awk -F= '
    /^[A-Za-z_][A-Za-z0-9_]*=/ {
      if (++seen[$1] > 1) {
        printf "%s: 중복 key %s\n", FILENAME, $1 > "/dev/stderr"
        duplicate = 1
      }
    }
    END { exit duplicate }
  ' "$env_file"
done < <(find "$ENV_DIR/overlays" -type f -name '*.env' | sort)

list_keys() {
  local env_file="$1"
  local ignore_web_dev_only="${2:-0}"

  awk -F= -v ignore_web_dev_only="$ignore_web_dev_only" '
    /^[A-Za-z_][A-Za-z0-9_]*=/ {
      if (ignore_web_dev_only == "1" && ($1 == "CHOKIDAR_USEPOLLING" || $1 == "NPM_CONFIG_PRODUCTION" || $1 == "WATCHPACK_POLLING")) {
        next
      }
      print $1
    }
  ' "$env_file" | sort -u
}

compare_server_key_sets() {
  local file_name="$1"
  local ignore_web_dev_only="${2:-0}"
  local oidc_file="$ENV_DIR/overlays/oidc/$file_name"
  local prod_file="$ENV_DIR/overlays/prod/$file_name"

  if ! diff -u \
    <(list_keys "$oidc_file" "$ignore_web_dev_only") \
    <(list_keys "$prod_file" "$ignore_web_dev_only") >/dev/null; then
    echo "OIDC/prod 환경변수 key 구성이 다릅니다: $file_name" >&2
    exit 1
  fi
}

compare_server_key_sets api.config.env
compare_server_key_sets api.secret.env
compare_server_key_sets web.config.env 1
compare_server_key_sets web.secret.env
compare_server_key_sets airflow.config.env
compare_server_key_sets airflow.secret.env
compare_server_key_sets minio.config.env
compare_server_key_sets minio.secret.env
compare_server_key_sets grafana.config.env
compare_server_key_sets grafana.secret.env

echo "env profile key validation passed"
