#!/usr/bin/env bash
# 이 파일이 속한 ops checkout에 배포용 파일 선택 목록을 적용한다.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
root=$(git rev-parse --show-toplevel)
cd -- "$root"
patterns=deploy/shared/ops-checkout.patterns
[[ -r "$patterns" ]] || { echo "파일 선택 목록이 없습니다: $patterns" >&2; exit 1; }

folders=(.claude .chatgpt)
changes=$(git status --porcelain --untracked-files=no -- "${folders[@]}")
if [[ -n "$changes" ]]; then
  echo '.claude 또는 .chatgpt의 추적 파일에 로컬 변경이 있습니다. 변경을 보존한 뒤 다시 실행하세요.' >&2
  exit 1
fi

# Git이 관리하지 않는 파일(ignored 포함)이 섞여 있으면 디렉터리 전체를 보관한다.
git_dir=$(git rev-parse --absolute-git-dir)
backup=
preserve_folder() {
  if [[ -z "$backup" ]]; then
    backup=$(mktemp -d "$git_dir/ops-agent-files.XXXXXXXX")
    echo "로컬 파일 보관 위치: $backup"
  fi
  mv -- "$1" "$backup/"
}

for folder in "${folders[@]}"; do
  local_files=$(git ls-files --others -- "$folder")
  if [[ -n "$local_files" ]]; then
    preserve_folder "$folder"
  fi
done

if ! git sparse-checkout set --no-cone --stdin < "$patterns"; then
  for folder in "${folders[@]}"; do
    if [[ -n "$backup" && ! -e "$folder" && ! -L "$folder" && -e "$backup/$folder" ]]; then
      mv -- "$backup/$folder" "$folder"
    fi
  done
  exit 1
fi

# 추적 파일이 전혀 없는 빈 디렉터리도 작업 트리에서 치운다.
for folder in "${folders[@]}"; do
  if [[ -e "$folder" || -L "$folder" ]]; then
    preserve_folder "$folder"
  fi
done
echo "ops checkout 적용 완료: $root (.claude, .chatgpt 제외)"
