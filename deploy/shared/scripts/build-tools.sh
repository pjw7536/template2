#!/usr/bin/env bash
# 이미지 빌드 도구(nerdctl·BuildKit)를 확인하거나 설치한다. 기존 containerd를 사용하며 재시작하지 않는다.
#   build-tools.sh check    설치·서비스·BuildKit worker 상태를 조회한다(변경 없음).
#   build-tools.sh install  없는 것만 설치한다. 기존 BuildKit 설정·서비스 파일은 덮어쓰지 않는다.
set -euo pipefail

NERDCTL_VERSION=2.4.2
BUILDKIT_VERSION=0.34.1
# 공식 릴리스 파일의 SHA-256. 버전을 바꾸면 함께 갱신한다.
NERDCTL_SHA256=41a66995888043c0ba05f8061574eaba1b9e06b9b21c2a238215179df2728d3f
BUILDKIT_SHA256=a59539daf547fe0958efe2d07e41c0a6944e1112a66d7e519ec1cf5b673ef15b
# 사내 GitHub 릴리스 미러. 다른 미러나 반입 폴더를 쓰면 환경변수로 바꾼다.
GITHUB_MIRROR="${GITHUB_MIRROR:-http://repository.samsungds.net/repository/proxy-raw-github.com}"
BUILD_TOOLS_DIR="${BUILD_TOOLS_DIR:-$HOME/build-tools}"
CONTAINERD_ADDRESS="${CONTAINERD_ADDRESS:-/run/containerd/containerd.sock}"
CONTAINERD_NAMESPACE="${CONTAINERD_NAMESPACE:-default}"
BUILDKIT_HOST="${BUILDKIT_HOST:-unix:///run/buildkit/buildkitd.sock}"

# root가 아니면 비밀번호를 묻지 않는 sudo만 사용한다. agent가 입력 대기로 멈추지 않게 한다.
if [[ $EUID -eq 0 ]]; then SUDO=(); else SUDO=(sudo -n); fi

fail() { echo "빌드 도구 준비 실패: $*" >&2; exit 1; }

check() {
  local missing=0 name
  for name in nerdctl buildctl buildkitd; do
    if command -v "$name" >/dev/null; then
      echo "[통과] $name: $("$name" --version 2>/dev/null | head -n 1)"
    else
      echo "[없음] $name"; missing=1
    fi
  done
  if (( missing )); then
    echo '빌드 도구가 없습니다. make build-tools-install을 실행하세요.'
    return 1
  fi
  "${SUDO[@]}" nerdctl --address "$CONTAINERD_ADDRESS" --namespace "$CONTAINERD_NAMESPACE" info >/dev/null 2>&1 ||
    { echo '[실패] nerdctl이 containerd에 연결하지 못합니다. containerd 상태와 sudo 권한을 확인하세요.'; return 1; }
  echo '[통과] containerd 연결'
  local workers
  workers="$("${SUDO[@]}" buildctl --addr "$BUILDKIT_HOST" debug workers --verbose 2>/dev/null)" ||
    { echo '[실패] BuildKit worker를 조회하지 못합니다. sudo systemctl status buildkit을 확인하세요.'; return 1; }
  # buildctl은 이름과 값 사이를 탭으로 맞춰 출력한다. 공백 종류와 개수에 묶이지 않게 비교한다.
  grep -Eq 'org\.mobyproject\.buildkit\.worker\.executor:[[:space:]]+containerd([[:space:]]|$)' <<<"$workers" &&
    grep -Eq "org\.mobyproject\.buildkit\.worker\.containerd\.namespace:[[:space:]]+${CONTAINERD_NAMESPACE//./\\.}([[:space:]]|\$)" <<<"$workers" ||
    { echo "[실패] BuildKit worker가 containerd($CONTAINERD_NAMESPACE)가 아닙니다. /etc/buildkit/buildkitd.toml을 확인하세요."; return 1; }
  echo "[통과] BuildKit containerd worker(namespace $CONTAINERD_NAMESPACE)"
  echo '빌드 도구 준비 완료'
}

download() {
  local url="$1" file="$2" sum="$3"
  if [[ ! -f "$BUILD_TOOLS_DIR/$file" ]]; then
    curl -fL "$url" -o "$BUILD_TOOLS_DIR/$file" ||
      fail "$file 다운로드 실패. 같은 공식 릴리스 파일을 $BUILD_TOOLS_DIR 에 반입한 뒤 다시 실행하세요."
  fi
  echo "$sum  $BUILD_TOOLS_DIR/$file" | sha256sum -c - >/dev/null || fail "$file SHA-256 불일치. 파일을 지우고 다시 받으세요."
}

install_tools() {
  [[ "$(uname -m)" == x86_64 ]] || fail 'amd64(x86_64) 서버만 지원합니다.'
  "${SUDO[@]}" true 2>/dev/null || fail '비밀번호 없는 sudo 권한이 필요합니다. 서버 담당자가 한 번 실행하거나 sudo 권한을 부여하세요.'
  "${SUDO[@]}" test -S "$CONTAINERD_ADDRESS" || fail "containerd 소켓이 없습니다: $CONTAINERD_ADDRESS"
  mkdir -p "$BUILD_TOOLS_DIR"
  if ! command -v nerdctl >/dev/null; then
    # 기존 containerd를 사용하므로 nerdctl-full이 아닌 단독 패키지를 받는다.
    download "$GITHUB_MIRROR/containerd/nerdctl/releases/download/v$NERDCTL_VERSION/nerdctl-$NERDCTL_VERSION-linux-amd64.tar.gz" \
      "nerdctl-$NERDCTL_VERSION-linux-amd64.tar.gz" "$NERDCTL_SHA256"
    "${SUDO[@]}" install -d -m 0755 /usr/local/bin
    "${SUDO[@]}" tar -xzf "$BUILD_TOOLS_DIR/nerdctl-$NERDCTL_VERSION-linux-amd64.tar.gz" -C /usr/local/bin nerdctl
    echo "설치: nerdctl $NERDCTL_VERSION"
  fi
  if ! command -v buildctl >/dev/null || ! command -v buildkitd >/dev/null; then
    download "$GITHUB_MIRROR/moby/buildkit/releases/download/v$BUILDKIT_VERSION/buildkit-v$BUILDKIT_VERSION.linux-amd64.tar.gz" \
      "buildkit-v$BUILDKIT_VERSION.linux-amd64.tar.gz" "$BUILDKIT_SHA256"
    "${SUDO[@]}" tar -xzf "$BUILD_TOOLS_DIR/buildkit-v$BUILDKIT_VERSION.linux-amd64.tar.gz" -C /usr/local
    echo "설치: BuildKit $BUILDKIT_VERSION"
  fi
  if ! "${SUDO[@]}" test -e /etc/buildkit/buildkitd.toml; then
    # 두 단계 빌드가 첫 단계의 로컬 이미지를 읽도록 containerd worker만 사용한다.
    "${SUDO[@]}" install -d -m 0755 /etc/buildkit
    "${SUDO[@]}" tee /etc/buildkit/buildkitd.toml >/dev/null <<TOML
[worker.oci]
  enabled = false

[worker.containerd]
  enabled = true
  address = "$CONTAINERD_ADDRESS"
  namespace = "$CONTAINERD_NAMESPACE"
  max-parallelism = 2
TOML
    echo '생성: /etc/buildkit/buildkitd.toml'
  fi
  if ! "${SUDO[@]}" test -e /etc/systemd/system/buildkit.service; then
    "${SUDO[@]}" tee /etc/systemd/system/buildkit.service >/dev/null <<UNIT
[Unit]
Description=이미지 빌드용 BuildKit
Requires=containerd.service
After=containerd.service

[Service]
Type=simple
ExecStart=/usr/local/bin/buildkitd --config /etc/buildkit/buildkitd.toml --addr $BUILDKIT_HOST
Restart=on-failure
Delegate=yes

[Install]
WantedBy=multi-user.target
UNIT
    echo '생성: /etc/systemd/system/buildkit.service'
  fi
  "${SUDO[@]}" systemctl daemon-reload
  "${SUDO[@]}" systemctl enable --now buildkit
  check
}

case "${1:-}" in
  check) check ;;
  install) install_tools ;;
  *) echo '사용법: build-tools.sh check|install' >&2; exit 2 ;;
esac
