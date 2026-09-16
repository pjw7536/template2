#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

# 저장소 전용 도구 경로에 checksum을 검증한 kind binary를 설치합니다.
KIND_VERSION="${KIND_VERSION:-v0.32.0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
INSTALL_DIR="${ROOT_DIR}/.tools/bin"

case "$(uname -m)" in
  x86_64|amd64)
    KIND_ARCH="amd64"
    ;;
  aarch64|arm64)
    KIND_ARCH="arm64"
    ;;
  *)
    echo "지원하지 않는 CPU 아키텍처입니다: $(uname -m)" >&2
    exit 1
    ;;
esac

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TEMP_DIR}"' EXIT

KIND_FILE="kind-linux-${KIND_ARCH}"
KIND_URL="https://kind.sigs.k8s.io/dl/${KIND_VERSION}/${KIND_FILE}"

mkdir -p "${INSTALL_DIR}"
curl --fail --location --silent --show-error \
  "${KIND_URL}" \
  --output "${TEMP_DIR}/${KIND_FILE}"
curl --fail --location --silent --show-error \
  "${KIND_URL}.sha256sum" \
  --output "${TEMP_DIR}/${KIND_FILE}.sha256sum"
(
  cd "${TEMP_DIR}"
  sha256sum --check "${KIND_FILE}.sha256sum"
)
install -m 0755 "${TEMP_DIR}/${KIND_FILE}" "${INSTALL_DIR}/kind"

"${INSTALL_DIR}/kind" version
