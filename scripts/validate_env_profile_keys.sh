#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_DIR="$ROOT_DIR/env"

required_files=(
  overlays/local/api.config.env
  overlays/local/api.secret.env
  overlays/local/web.config.env
  overlays/local/airflow.config.env
  overlays/local/airflow.secret.env
  overlays/local/minio.config.env
  overlays/local/minio.secret.env
  overlays/oidc/api.config.env
  overlays/oidc/api.secret.env
  overlays/oidc/web.config.env
  overlays/oidc/airflow.config.env
  overlays/oidc/airflow.secret.env
  overlays/oidc/minio.config.env
  overlays/oidc/minio.secret.env
  overlays/oidc/grafana.config.env
  overlays/oidc/grafana.secret.env
  overlays/prod/api.config.env
  overlays/prod/api.secret.env
  overlays/prod/web.config.env
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
compare_server_key_sets airflow.config.env
compare_server_key_sets airflow.secret.env
compare_server_key_sets minio.config.env
compare_server_key_sets minio.secret.env
compare_server_key_sets grafana.config.env
compare_server_key_sets grafana.secret.env

read_env_value() {
  local env_file="$1"
  local key="$2"

  awk -F= -v target="$key" '
    $1 == target {
      sub(/^[^=]*=/, "")
      print
      exit
    }
  ' "$env_file"
}

# API가 Airflow에 로그인할 때 쓰는 계정은 Airflow 초기 관리자 계정과 같아야 합니다.
compare_profile_values() {
  local profile="$1"
  local left_file="$2"
  local left_key="$3"
  local right_file="$4"
  local right_key="$5"
  local label="$6"
  local left_value
  local right_value

  left_value="$(read_env_value "$ENV_DIR/overlays/$profile/$left_file" "$left_key")"
  right_value="$(read_env_value "$ENV_DIR/overlays/$profile/$right_file" "$right_key")"

  if [[ -z "$left_value" || -z "$right_value" ]]; then
    echo "$profile profile의 $label 값이 비어 있습니다." >&2
    exit 1
  fi

  if [[ "$left_value" != "$right_value" ]]; then
    echo "$profile profile의 $label 값이 서로 다릅니다." >&2
    exit 1
  fi
}

for profile in local oidc prod; do
  compare_profile_values "$profile" api.config.env AIRFLOW_USERNAME airflow.config.env _AIRFLOW_WWW_USER_USERNAME "Airflow 사용자 이름"
  compare_profile_values "$profile" api.secret.env AIRFLOW_PASSWORD airflow.secret.env _AIRFLOW_WWW_USER_PASSWORD "Airflow 비밀번호"
  compare_profile_values "$profile" api.secret.env AIRFLOW_TRIGGER_TOKEN airflow.secret.env AIRFLOW_TRIGGER_TOKEN "Airflow trigger token"
done

echo "env profile key validation passed"
