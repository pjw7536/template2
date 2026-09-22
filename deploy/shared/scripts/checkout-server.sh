#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
APP="${1:?사용법: checkout-server.sh <앱> [--with-source]}"
if [[ $# -gt 2 || ( $# -eq 2 && "$2" != --with-source ) ]]; then
  echo '사용법: checkout-server.sh <앱> [--with-source]' >&2
  exit 1
fi
# 조회 실패를 process substitution으로 숨기지 않고 checkout 전에 중단한다.
selected_paths="$(python3 "$ROOT_DIR/deploy/shared/scripts/app-paths.py" "$@")"
mapfile -t paths <<< "$selected_paths"

# 선택 경로를 교체하므로 수정 파일이 없는 서버 전용 checkout에서만 실행합니다.
status="$(git -C "$ROOT_DIR" status --porcelain --untracked-files=normal)"
[[ -z "$status" ]] || { echo '작업 파일 변경이 있어 선택 체크아웃을 중단합니다. 변경을 보존한 뒤 다시 실행하세요.' >&2; exit 1; }
git -C "$ROOT_DIR" sparse-checkout set --cone "${paths[@]}"
echo "서버 선택 체크아웃 완료: $APP"
echo 'local/은 선택 범위에 포함되지 않습니다. 기존 ignored 파일은 자동 삭제하지 않습니다.'
