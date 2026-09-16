#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "${ROOT_DIR}/deploy/shared/scripts/env-lib.sh"
OUTPUT_FILE="${1:?생성할 임시 env 파일 경로가 필요합니다.}"
umask 077
load_env "${ROOT_DIR}/local/portal/env/api.env"
load_env "${ROOT_DIR}/local/portal/env/api-k8s.env"
# 전체 로컬 실행이 생성한 DB·Airflow 연결값도 같은 Secret에 한 번만 합성합니다.
RUNTIME_ENV="${LOCAL_K8S_API_OVERRIDES:-${ROOT_DIR}/local/shared/runtime/api-overrides.env}"
if [[ -f "$RUNTIME_ENV" ]]; then
  load_env "$RUNTIME_ENV"
fi
# MinIO client credential만 API에 전달하며 관리자·서버 설정은 전달하지 않습니다.
for key in MINIO_ACCESS_KEY MINIO_SECRET_KEY; do
  ENV_VALUES["$key"]="$(awk -F= -v key="$key" '$1==key {sub(/^[^=]*=/, ""); print; exit}' "${ROOT_DIR}/local/portal/env/minio.env")"
done
for key in "${!ENV_VALUES[@]}"; do
  printf '%s=%s\n' "$key" "${ENV_VALUES[$key]}"
done | LC_ALL=C sort > "$OUTPUT_FILE"
chmod 600 "$OUTPUT_FILE"
