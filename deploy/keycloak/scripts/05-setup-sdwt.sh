#!/usr/bin/env bash
set -Eeuo pipefail
# 기본은 dry-run이며 CSV·관리자 인증 계약은 기존 SDWT 도구를 따릅니다.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/init_sdwt.py" "$@"
