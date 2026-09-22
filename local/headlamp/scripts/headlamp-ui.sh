#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

NAMESPACE="tailwind-local"
EXPECTED_CONTEXT="kind-tailwind-local"
KUBECTL_BIN="${KUBECTL_BIN:-kubectl}"

CURRENT_CONTEXT="$(${KUBECTL_BIN} config current-context)"
if [[ "${CURRENT_CONTEXT}" != "${EXPECTED_CONTEXT}" ]]; then
  echo "현재 Kubernetes context가 ${EXPECTED_CONTEXT}가 아닙니다: ${CURRENT_CONTEXT}" >&2
  echo "먼저 'make k8s-up'을 실행하세요." >&2
  exit 1
fi

${KUBECTL_BIN} -n "${NAMESPACE}" rollout status deployment/headlamp --timeout=180s

# 로그인 token은 파일에 저장하지 않고 실행할 때마다 8시간짜리로 발급합니다.
HEADLAMP_TOKEN="$(${KUBECTL_BIN} -n "${NAMESPACE}" create token headlamp-viewer --duration=8h)"

echo
echo "Headlamp URL: http://localhost:4466"
echo "아래 token을 Headlamp 로그인 화면에 붙여 넣으세요."
echo
echo "${HEADLAMP_TOKEN}"
echo
echo "이 터미널을 유지하세요. 종료하려면 Ctrl+C를 누르세요."

exec ${KUBECTL_BIN} -n "${NAMESPACE}" port-forward \
  --address 127.0.0.1 \
  service/headlamp \
  4466:80
