#!/usr/bin/env bash
set -euo pipefail

PROFILE_ENV_FILE="${1:?사용법: validate_server_profile_env.sh <profile-env-file>}"
PROFILE_ENV_DIR="${PROFILE_ENV_FILE%/*}"
AIRFLOW_PROFILE_ENV_FILE="${AIRFLOW_PROFILE_ENV_FILE:-$PROFILE_ENV_DIR/airflow.env}"

read_env_value() {
  local key="$1"
  shift

  awk -F= -v target="$key" '
    $0 ~ "^[[:space:]]*" target "=" {
      sub(/^[^=]*=/, "")
      result = $0
    }
    END { printf "%s", result }
  ' "$@"
}

validate_env_group() {
  local label="$1"
  shift
  local env_files=()
  while (( $# > 0 )) && [[ "$1" != "--" ]]; do
    env_files+=("$1")
    shift
  done
  shift
  local required_keys=("$@")
  local missing_keys=()
  local placeholder_keys=()
  local env_file key value normalized_value

  for env_file in "${env_files[@]}"; do
    if [[ ! -f "$env_file" ]]; then
      echo "환경변수 파일이 없습니다: $env_file" >&2
      exit 1
    fi
  done

  for key in "${required_keys[@]}"; do
    value="$(read_env_value "$key" "${env_files[@]}")"

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
    echo "$label 필수값이 비어 있습니다: ${missing_keys[*]}" >&2
    exit 1
  fi

  if (( ${#placeholder_keys[@]} > 0 )); then
    echo "$label placeholder를 실제 값으로 교체해야 합니다: ${placeholder_keys[*]}" >&2
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
  ADFS_CER_PATH
  OIDC_REDIRECT_URI
  ALLOWED_REDIRECT_HOSTS
  PUBLIC_API_BASE_URL
  RAG_SEARCH_URL
  RAG_INSERT_URL
  RAG_DELETE_URL
  RAG_INDEX_INFO_URL
  RAG_HEADERS
  AIRFLOW_BASE_URL
  AIRFLOW_PUBLIC_BASE_URL
  AIRFLOW_USERNAME
  AIRFLOW_PASSWORD
  AIRFLOW_TRIGGER_TOKEN
  EMAIL_OCR_INTERNAL_TOKEN
)

AIRFLOW_COMMON_REQUIRED_KEYS=(
  _AIRFLOW_WWW_USER_CREATE
  _AIRFLOW_WWW_USER_USERNAME
  _AIRFLOW_WWW_USER_PASSWORD
  AIRFLOW_API_BASE_URL
  AIRFLOW_TRIGGER_TOKEN
)

validate_env_group \
  "서버 profile" \
  "$PROFILE_ENV_FILE" \
  -- \
  "${PROFILE_REQUIRED_KEYS[@]}"
validate_env_group \
  "Airflow profile env" \
  "$AIRFLOW_PROFILE_ENV_FILE" \
  -- \
  "${AIRFLOW_COMMON_REQUIRED_KEYS[@]}"

api_trigger_token="$(read_env_value AIRFLOW_TRIGGER_TOKEN "$PROFILE_ENV_FILE")"
airflow_trigger_token="$(read_env_value AIRFLOW_TRIGGER_TOKEN "$AIRFLOW_PROFILE_ENV_FILE")"
if [[ "$api_trigger_token" != "$airflow_trigger_token" ]]; then
  echo "API profile과 Airflow profile의 AIRFLOW_TRIGGER_TOKEN 값이 일치하지 않습니다." >&2
  exit 1
fi

api_airflow_username="$(read_env_value AIRFLOW_USERNAME "$PROFILE_ENV_FILE")"
airflow_username="$(read_env_value _AIRFLOW_WWW_USER_USERNAME "$AIRFLOW_PROFILE_ENV_FILE")"
if [[ "$api_airflow_username" != "$airflow_username" ]]; then
  echo "API profile과 Airflow profile의 관리자 username이 일치하지 않습니다." >&2
  exit 1
fi

api_airflow_password="$(read_env_value AIRFLOW_PASSWORD "$PROFILE_ENV_FILE")"
airflow_password="$(read_env_value _AIRFLOW_WWW_USER_PASSWORD "$AIRFLOW_PROFILE_ENV_FILE")"
if [[ "$api_airflow_password" != "$airflow_password" ]]; then
  echo "API profile과 Airflow profile의 관리자 password가 일치하지 않습니다." >&2
  exit 1
fi

echo "server profile env validation passed: $PROFILE_ENV_FILE"
