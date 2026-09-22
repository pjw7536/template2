#!/usr/bin/env bash
set -Eeuo pipefail

# 원본에서 CP1 전달용 파일을 생성하며 클러스터에 연결하거나 적용하지 않습니다.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
KUBECTL_BIN="${KUBECTL_BIN:-kubectl}"
OUTPUT_DIR="${ROOT_DIR}/deploy/keycloak/rendered"
RENDER_TMP="$(mktemp -d)"
trap 'rm -rf -- "${RENDER_TMP}"' EXIT

{
  printf '%s\n' \
    '# 자동 생성 파일입니다. deploy/keycloak/k8s·deploy/shared/ingress 원본 수정 후 make k8s-export로 갱신합니다.' \
    '# 실제 credential과 TLS 개인키는 포함하지 않으며 Kubernetes Secret으로 별도 생성합니다.'
  "${KUBECTL_BIN}" kustomize "${ROOT_DIR}/deploy/keycloak/k8s"
} > "${RENDER_TMP}/internal-keycloak-stack.yaml"

{
  printf '%s\n' '# 자동 생성 파일입니다. mapper ConfigMap과 Job만 적용하며 서버·Ingress는 변경하지 않습니다.'
  "${KUBECTL_BIN}" create configmap keycloak-claim-mapper -n etch-sso \
    --from-file="${ROOT_DIR}/deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh" \
    --from-file="${ROOT_DIR}/deploy/keycloak/k8s/oidc/admin-common.sh" \
    --from-file="${ROOT_DIR}/deploy/keycloak/k8s/oidc/setup-oidc.sh" \
    --from-file="${ROOT_DIR}/deploy/keycloak/k8s/claims/account-user-profile.json" \
    --dry-run=client -o yaml
  printf '\n---\n'
  cat "${ROOT_DIR}/deploy/keycloak/k8s/claims/claim-mappers-job.yaml"
} > "${RENDER_TMP}/internal-keycloak-claim-mappers.yaml"

mkdir -p "${OUTPUT_DIR}"
install -m 0644 "${RENDER_TMP}/internal-keycloak-stack.yaml" "${OUTPUT_DIR}/internal-keycloak-stack.yaml"
install -m 0644 "${RENDER_TMP}/internal-keycloak-claim-mappers.yaml" "${OUTPUT_DIR}/internal-keycloak-claim-mappers.yaml"
echo "생성 완료: ${OUTPUT_DIR}/internal-keycloak-stack.yaml"
echo "생성 완료: ${OUTPUT_DIR}/internal-keycloak-claim-mappers.yaml"
