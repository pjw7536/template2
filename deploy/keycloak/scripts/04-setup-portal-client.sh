#!/usr/bin/env bash
set -Eeuo pipefail
# 지정한 한 단계만 실행하며 다른 설정 단계는 호출하지 않습니다.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/setup_discovery.py" apply --step portal "$@"
