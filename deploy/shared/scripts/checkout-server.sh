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
# Git은 제외할 디렉터리 안의 ignored 파일도 지울 수 있으므로 먼저 보존 여부를 확인합니다.
ignored_file_list="$(mktemp)"
trap 'rm -f -- "$ignored_file_list"' EXIT
git -C "$ROOT_DIR" ls-files --others --ignored --exclude-standard -z > "$ignored_file_list"
while IFS= read -r -d '' ignored_path; do
  [[ "$ignored_path" == */* ]] || continue
  kept=0
  for selected_path in "${paths[@]}"; do
    # 선택 폴더 전체와 cone 모드가 유지하는 상위 폴더의 바로 아래 파일을 허용합니다.
    if [[ "$ignored_path" == "$selected_path/"* ||
          ( "$ignored_path" != */ && "$selected_path" == "${ignored_path%/*}/"* ) ]]; then
      kept=1
      break
    fi
  done
  [[ "$kept" == 1 ]] && continue
  printf '선택에서 제외될 ignored 파일이 있어 중단합니다: %q\n' "$ignored_path" >&2
  echo '필요한 파일을 저장소 밖에 보존한 뒤 다시 실행하세요.' >&2
  exit 1
done < "$ignored_file_list"
git -C "$ROOT_DIR" sparse-checkout set --cone "${paths[@]}"
echo "서버 선택 체크아웃 완료: $APP"
echo 'local/은 선택 범위에 포함되지 않습니다. 기존 ignored 파일은 자동 삭제하지 않습니다.'
