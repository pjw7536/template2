#!/bin/sh

set -eu

: "${GRIST_ADMIN_EMAIL:?GRIST_ADMIN_EMAIL 설정이 필요합니다.}"

grist_org=${GRIST_ORG:-work-hub}
grist_base_url=${GRIST_BOOTSTRAP_URL:-http://grist:8484/o/$grist_org}
api_key_file=${GRIST_API_KEY_FILE:-/run/work-hub/grist_api_key}
cookie_file=$(mktemp)
temporary_key_file="${api_key_file}.tmp"

cleanup_bootstrap_files() {
  find "$cookie_file" -type f -delete 2>/dev/null || true
  find "$temporary_key_file" -type f -delete 2>/dev/null || true
}

trap cleanup_bootstrap_files EXIT INT TERM
umask 077

# 초기화 요청이 연결되거나 응답이 멈춰도 배포를 무기한 붙잡지 않게 합니다.
curl_with_timeout() {
  curl --connect-timeout 3 --max-time 15 "$@"
}

# Grist가 forward-auth endpoint를 받을 때까지 기다린 뒤 관리자 session을 만듭니다.
login_ready=0
attempt=1
while [ "$attempt" -le 60 ]; do
  login_status=$(curl_with_timeout -sS -o /dev/null -w '%{http_code}' \
    -c "$cookie_file" \
    -H "X-Forwarded-User: $GRIST_ADMIN_EMAIL" \
    "$grist_base_url/auth/login?next=/o/$grist_org/" 2>/dev/null || true)
  if [ "$login_status" = "302" ] || [ "$login_status" = "303" ]; then
    login_ready=1
    break
  fi
  attempt=$((attempt + 1))
  sleep 2
done

if [ "$login_ready" -ne 1 ]; then
  echo "Grist 관리자 session을 준비하지 못했습니다." >&2
  exit 1
fi

# 기존 key가 있으면 재사용하고, 새 사용자나 새 volume에서만 공식 API로 발급합니다.
api_key=$(curl_with_timeout -fsS -b "$cookie_file" "$grist_base_url/api/profile/apikey")
if [ -z "$api_key" ]; then
  api_key=$(curl_with_timeout -fsS -X POST \
    -b "$cookie_file" \
    -H 'Content-Type: application/json' \
    -d '{}' \
    "$grist_base_url/api/profile/apikey")
fi

case "$api_key" in
  ""|*[!0-9a-f]*)
    echo "Grist가 유효한 API key를 반환하지 않았습니다." >&2
    exit 1
    ;;
esac

if [ "${#api_key}" -ne 40 ]; then
  echo "Grist API key 길이가 올바르지 않습니다." >&2
  exit 1
fi

# 공유하기 전에 조직 workspace를 조회할 수 있는 server-to-server key인지 확인합니다.
curl_with_timeout -fsS -o /dev/null \
  -H "Authorization: Bearer $api_key" \
  "$grist_base_url/api/orgs/current/workspaces"

printf '%s\n' "$api_key" > "$temporary_key_file"
chmod 600 "$temporary_key_file"
mv -f "$temporary_key_file" "$api_key_file"
echo "Grist API key 초기화가 완료되었습니다."
