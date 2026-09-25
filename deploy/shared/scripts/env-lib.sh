#!/usr/bin/env bash

# dotenv를 실행하지 않고 데이터로 읽습니다. 파일 내부 중복은 오류이며 파일 간 병합은 명시된 순서입니다.
declare -A ENV_VALUES=()
load_env() {
  local file="$1" line key value line_number=0
  local -A seen=()
  [[ -f "$file" ]] || { echo "설정 파일이 없습니다: $file" >&2; return 1; }
  while IFS= read -r line || [[ -n "$line" ]]; do
    line_number=$((line_number + 1))
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    if [[ ! "$line" =~ ^[A-Za-z_][A-Za-z0-9_-]*= ]]; then
      echo "설정 형식 오류: $file:$line_number (KEY=값 형식 필요)" >&2
      return 1
    fi
    key="${line%%=*}"; value="${line#*=}"
    [[ ! -v seen[$key] ]] || { echo "중복 설정: $key ($file)" >&2; return 1; }
    seen["$key"]=1
    ENV_VALUES["$key"]="$value"
  done < "$file"

}

require_env_keys() {
  local key value failed=0
  for key in "$@"; do
    value="${ENV_VALUES[$key]:-}"
    if [[ -z "${value//[[:space:]]/}" ]]; then
      echo "누락된 필수 설정: $key" >&2; failed=1
    elif [[ "$value" == *'<'* || "$value" == *example.invalid* || "$value" == *replace-me* || "$value" == *change-me* ]]; then
      echo "실제 값으로 교체할 설정: $key" >&2; failed=1
    fi
  done
  return "$failed"
}

# URL 문자열에 credential이나 허용되지 않은 와일드카드가 섞이지 않도록 검사합니다.
require_url() {
  local key="$1" value="${ENV_VALUES[$1]:-}"
  if [[ ! "$value" =~ ^https?://[^/[:space:]@]+(/[^[:space:]]*)?$ || "$value" == *'*'* ]]; then
    echo "HTTP(S) URL 형식 오류: $key" >&2; return 1
  fi
}

# Keycloak discovery 입력을 기존 Job의 endpoint 계약으로 변환합니다.
resolve_keycloak_discovery() {
  local root="$1" app="$2" component="$3" file="$4" resolved status=0
  [[ "$app/$component" == keycloak/oidc && -n "${ENV_VALUES[CORP_OIDC_DISCOVERY_URL]:-}" ]] || return 0
  resolved="$(mktemp)" || return
  if python3 "$root/deploy/keycloak/scripts/setup_discovery.py" resolve --env "$file" --output "$resolved"; then
    load_env "$resolved" || status=$?
  else
    status=$?
  fi
  rm -f -- "$resolved"
  return "$status"
}

resolve_env_file() {
  local root="$1" app="$2" profile="$3" component="$4"
  [[ "$profile" =~ ^[a-z0-9_-]+$ ]] || { echo '환경 이름 형식 오류' >&2; return 1; }
  case "$profile" in local|prod|test) ;; *) echo '지원하지 않는 환경입니다. local 또는 prod, CI test를 사용하세요.' >&2; return 1 ;; esac
  if [[ "$profile" == local ]]; then
    case "$app" in
      portal)
        [[ "$component" =~ ^(api|client|web|minio)$ ]] || return 1
        [[ "$component" != client ]] || component=api
        printf '%s/local/portal/env/%s.env' "$root" "$component" ;;
      *) echo "지원하지 않는 로컬 앱: $app" >&2; return 1 ;;
    esac
    return
  fi
  case "$app" in
    keycloak) printf '%s/deploy/keycloak/env/%s.env' "$root" "$profile" ;;
    airflow|monitoring|headlamp)
      [[ "$profile/$component" == prod/server ]] || { echo '이 앱은 prod/server Kubernetes 검사를 사용하세요.' >&2; return 1; }
      printf '%s/deploy/%s/env/k8s.env' "$root" "$app" ;;
    portal)
      [[ "$component" =~ ^(api|client|web|minio)$ ]] || return 1
      [[ "$component" != client ]] || component=api
      printf '%s/deploy/portal/env/%s/%s.env' "$root" "$profile" "$component" ;;
    *) echo "지원하지 않는 앱: $app" >&2; return 1 ;;
  esac
}

validate_app_env() {
  local app="$1" component="$2"
  case "$app/$component" in
    keycloak/server)
      require_env_keys postgres-password bootstrap-admin-username bootstrap-admin-password keycloak-public-url || return
      require_url keycloak-public-url ;;
    keycloak/oidc)
      require_env_keys CORP_OIDC_AUTH_URL CORP_OIDC_TOKEN_URL CORP_OIDC_ISSUER CORP_OIDC_CLIENT_ID CORP_OIDC_CLIENT_SECRET CORP_OIDC_CLIENT_AUTH_METHOD CORP_OIDC_VALIDATE_SIGNATURE || return
      case "${ENV_VALUES[CORP_OIDC_CLIENT_AUTH_METHOD]}" in
        client_secret_basic|client_secret_post) ;;
        *) echo 'CORP_OIDC_CLIENT_AUTH_METHOD: client_secret_basic 또는 client_secret_post 필요' >&2; return 1 ;;
      esac
      require_url CORP_OIDC_AUTH_URL && require_url CORP_OIDC_TOKEN_URL && require_url CORP_OIDC_ISSUER || return
      case "${ENV_VALUES[CORP_OIDC_VALIDATE_SIGNATURE]}" in
        true) require_env_keys CORP_OIDC_JWKS_URL && require_url CORP_OIDC_JWKS_URL ;;
        false) ;;
        *) echo 'CORP_OIDC_VALIDATE_SIGNATURE: true 또는 false 필요' >&2; return 1 ;;
      esac ;;
    portal/client)
      require_env_keys OIDC_PROVIDER OIDC_CLIENT_ID OIDC_CLIENT_SECRET OIDC_ISSUER OIDC_REDIRECT_URI FRONTEND_BASE_URL || return
      [[ "${ENV_VALUES[OIDC_PROVIDER]}" == keycloak ]] || { echo 'Portal client 등록은 OIDC_PROVIDER=keycloak일 때만 가능합니다.' >&2; return 1; }
      require_url OIDC_ISSUER && require_url OIDC_REDIRECT_URI && require_url FRONTEND_BASE_URL || return
      [[ "${ENV_VALUES[FRONTEND_BASE_URL]}" != */ ]] || { echo 'FRONTEND_BASE_URL 끝의 /를 제거하세요.' >&2; return 1; } ;;
    portal/api)
      require_env_keys DJANGO_SECRET_KEY DJANGO_ALLOWED_HOSTS DJANGO_DB_NAME DJANGO_DB_USER DJANGO_DB_PASSWORD DJANGO_DB_HOST OIDC_PROVIDER OIDC_CLIENT_ID OIDC_ISSUER ADFS_AUTH_URL OIDC_REDIRECT_URI FRONTEND_BASE_URL || return
      case "${ENV_VALUES[OIDC_PROVIDER]}" in
        keycloak) require_env_keys OIDC_CLIENT_SECRET OIDC_TOKEN_URL OIDC_JWKS_URL ADFS_LOGOUT_URL ;;
        adfs) require_env_keys ADFS_CER_PATH ;;
        *) echo 'OIDC_PROVIDER: adfs 또는 keycloak 필요' >&2; return 1 ;;
      esac ;;
    portal/web) require_env_keys VITE_SITE_URL VITE_BACKEND_URL BACKEND_API_URL ;;
    portal/minio) require_env_keys MINIO_ROOT_USER MINIO_ROOT_PASSWORD MINIO_ACCESS_KEY MINIO_SECRET_KEY ;;
    *) echo "지원하지 않는 설정 작업: $app/$component" >&2; return 1 ;;
  esac
}

# 운영 Kubernetes는 Keycloak과 Portal 파일 저장소를 사용합니다. 업무 연동은 별도 검증합니다.
validate_portal_prod_env() {
  local component="$1" key
  case "$component" in
    api)
      [[ "${ENV_VALUES[OIDC_PROVIDER]:-}" == keycloak ]] || { echo '운영 Portal은 OIDC_PROVIDER=keycloak을 사용합니다.' >&2; return 1; }
      require_env_keys DJANGO_DB_PORT DJANGO_CORS_ALLOWED_ORIGINS DJANGO_CSRF_TRUSTED_ORIGINS PUBLIC_API_BASE_URL ALLOWED_REDIRECT_HOSTS MINIO_ENDPOINT MINIO_ACCESS_KEY MINIO_SECRET_KEY || return
      for key in FRONTEND_BASE_URL PUBLIC_API_BASE_URL OIDC_ISSUER OIDC_REDIRECT_URI ADFS_AUTH_URL ADFS_LOGOUT_URL OIDC_TOKEN_URL OIDC_JWKS_URL MINIO_ENDPOINT; do
        require_url "$key" || return
      done ;;
    web)
      require_env_keys VITE_MINIO_ENDPOINT || return
      for key in VITE_SITE_URL VITE_BACKEND_URL BACKEND_API_URL VITE_MINIO_ENDPOINT; do
        require_url "$key" || return
      done ;;
    minio)
      require_env_keys MINIO_SERVER_URL || return
      require_url MINIO_SERVER_URL || return
      [[ -z "${ENV_VALUES[MINIO_BROWSER_REDIRECT_URL]:-}" ]] || require_url MINIO_BROWSER_REDIRECT_URL ;;
    client) return 0 ;;
  esac
}
