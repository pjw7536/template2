#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
APP="${1:-}"
PROFILE="${2:-prod}"
[[ -n "$APP" ]] || { echo 'APP에 앱 또는 그룹 이름을 지정하세요. 예: make server-check APP=all' >&2; exit 1; }
[[ "$PROFILE" == prod ]] || { echo "사내 서버는 Kubernetes 전용입니다. $PROFILE 환경의 Kubernetes 정의가 없습니다." >&2; exit 1; }
cd "$ROOT_DIR"

# 앱·그룹 이름과 앱별 정적 검사 명령은 공통 앱 카탈로그(commands.static)가 원본입니다.
# 클러스터와 실제 credential은 확인하지 않습니다. Kubernetes 정의가 없는 앱을 Compose 검사로 대신 통과시키지 않습니다.
while IFS= read -r app; do
  python3 deploy/shared/scripts/app.py static "$app"
done < <(python3 deploy/shared/scripts/app-paths.py "$APP")
