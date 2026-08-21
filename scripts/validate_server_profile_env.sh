#!/usr/bin/env bash
set -euo pipefail

PROFILE_ENV_FILE="${1:?사용법: validate_server_profile_env.sh <profile-env-file>}"
API_COMMON_ENV_FILE="${API_COMMON_ENV_FILE:-env/api.common.env}"
SERVER_COMMON_ENV_FILE="${SERVER_COMMON_ENV_FILE:-env/api.server.common.env}"
AIRFLOW_COMMON_ENV_FILE="${AIRFLOW_COMMON_ENV_FILE:-env/airflow.common.env}"

read_env_value() {
  local env_file="$1"
  local key="$2"

  awk -F= -v target="$key" '
    $0 ~ "^[[:space:]]*" target "=" {
      sub(/^[^=]*=/, "")
      result = $0
    }
    END { printf "%s", result }
  ' "$env_file"
}

validate_env_file() {
  local env_file="$1"
  shift
  local required_keys=("$@")
  local missing_keys=()
  local placeholder_keys=()
  local key value normalized_value

  if [[ ! -f "$env_file" ]]; then
    echo "환경변수 파일이 없습니다: $env_file" >&2
    exit 1
  fi

  for key in "${required_keys[@]}"; do
    value="$(read_env_value "$env_file" "$key")"

    if [[ -z "${value//[[:space:]]/}" ]]; then
      missing_keys+=("$key")
      continue
    fi

    normalized_value="${value,,}"
    if [[ "$normalized_value" == *"change-me"* \
      || "$normalized_value" == *"example.com"* \
      || "$normalized_value" == *'"token"'* \
      || "$normalized_value" == *'"apikey"'* ]]; then
      placeholder_keys+=("$key")
    fi
  done

  if (( ${#missing_keys[@]} > 0 )); then
    echo "서버 profile 필수값이 비어 있습니다: ${missing_keys[*]}" >&2
    exit 1
  fi

  if (( ${#placeholder_keys[@]} > 0 )); then
    echo "서버 profile placeholder를 실제 값으로 교체해야 합니다: ${placeholder_keys[*]}" >&2
    exit 1
  fi
}

# 서버 시작에 필요한 핵심 계약만 필수로 검사합니다. 선택 연동값은 비어 있어도 허용합니다.
PROFILE_REQUIRED_KEYS=(
  DJANGO_SECRET_KEY
  DJANGO_ALLOWED_HOSTS
  DJANGO_DB_NAME
  DJANGO_DB_USER
  DJANGO_DB_PASSWORD
  DJANGO_DB_HOST
  DJANGO_DB_PORT
  FRONTEND_BASE_URL
  DJANGO_CORS_ALLOWED_ORIGINS
  DJANGO_CSRF_TRUSTED_ORIGINS
  OIDC_CLIENT_ID
  OIDC_ISSUER
  ADFS_AUTH_URL
  ADFS_LOGOUT_URL
  OIDC_REDIRECT_URI
  ALLOWED_REDIRECT_HOSTS
  RAG_HEADERS
)

SERVER_COMMON_REQUIRED_KEYS=(
  PUBLIC_API_BASE_URL
  RAG_SEARCH_URL
  RAG_INSERT_URL
  RAG_DELETE_URL
  RAG_INDEX_INFO_URL
)

API_COMMON_REQUIRED_KEYS=(
  AIRFLOW_TRIGGER_TOKEN
  EMAIL_OCR_INTERNAL_TOKEN
)

AIRFLOW_COMMON_REQUIRED_KEYS=(
  AIRFLOW_TRIGGER_TOKEN
)

validate_env_file "$PROFILE_ENV_FILE" "${PROFILE_REQUIRED_KEYS[@]}"
validate_env_file "$SERVER_COMMON_ENV_FILE" "${SERVER_COMMON_REQUIRED_KEYS[@]}"
validate_env_file "$API_COMMON_ENV_FILE" "${API_COMMON_REQUIRED_KEYS[@]}"
validate_env_file "$AIRFLOW_COMMON_ENV_FILE" "${AIRFLOW_COMMON_REQUIRED_KEYS[@]}"

api_trigger_token="$(read_env_value "$API_COMMON_ENV_FILE" AIRFLOW_TRIGGER_TOKEN)"
airflow_trigger_token="$(read_env_value "$AIRFLOW_COMMON_ENV_FILE" AIRFLOW_TRIGGER_TOKEN)"
if [[ "$api_trigger_token" != "$airflow_trigger_token" ]]; then
  echo "API common과 Airflow common의 AIRFLOW_TRIGGER_TOKEN 값이 일치하지 않습니다." >&2
  exit 1
fi

echo "server profile env validation passed: $PROFILE_ENV_FILE"
