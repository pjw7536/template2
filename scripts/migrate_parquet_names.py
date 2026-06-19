"""parquet 파일명 마이그레이션: 구형 tuple 포맷 → # 구분자 포맷.

변환 규칙
  ('STEP_A_001', 'PPID_B')_0.parquet  →  STEP_A_001#PPID_B#0.parquet
  STEP_A_001_PPID_B_0.parquet          →  변환 불가 (skip, 경고 출력)

사용법
  python scripts/migrate_parquet_names.py [--root PATH] [--dry-run]

  --root    검색 루트 (기본값: /home/k/b/daily_anomaly)
  --dry-run 실제로 파일 이름을 바꾸지 않고 변환 목록만 출력
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# ('STEP_A_001', 'PPID_B')_0  ← stem 기준
_TUPLE_RE = re.compile(r"^\('([^']+)',\s*'([^']+)'\)_(\d+)$")

# 이미 # 포맷인 경우 (건너뜀)  STEP_A_001#PPID_B#0
_HASH_RE = re.compile(r"^[^(]+#[^#]+#\d+$")


def _sanitize_element(s: str) -> str:
    """persistence.py 의 _sanitize_element 와 동일한 로직."""
    for ch in (" ", "/", "\\", "(", ")", "'", '"', ",", "[", "]"):
        s = s.replace(ch, "")
    return s.strip()


def classify(stem: str) -> tuple[str, str, str] | None:
    """stem 에서 (step_seq, ppid, index) 파싱. 해당 없으면 None."""
    m = _TUPLE_RE.match(stem)
    if m:
        return _sanitize_element(m.group(1)), _sanitize_element(m.group(2)), m.group(3)
    return None


def migrate(root: str, dry_run: bool) -> None:
    root_path = Path(root)
    if not root_path.exists():
        print(f"[ERROR] 경로 없음: {root}")
        sys.exit(1)

    files = list(root_path.rglob("*.parquet"))
    print(f"발견된 parquet 파일: {len(files)}개  (root={root})")

    converted = skipped_hash = skipped_unknown = 0

    for path in sorted(files):
        stem = path.stem

        if _HASH_RE.match(stem):
            skipped_hash += 1
            continue

        parsed = classify(stem)
        if parsed is None:
            print(f"[SKIP] {path.relative_to(root_path)}")
            skipped_unknown += 1
            continue

        step_seq, ppid, idx = parsed
        new_name = f"{step_seq}#{ppid}#{idx}.parquet"
        new_path = path.parent / new_name

        if dry_run:
            print(f"[DRY] {path.name}  →  {new_name}")
        else:
            os.rename(path, new_path)
            print(f"[OK]  {path.name}  →  {new_name}")
        converted += 1

    print(
        f"\n완료: 변환={converted}, "
        f"이미 # 포맷={skipped_hash}, "
        f"미인식 skip={skipped_unknown}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="parquet 파일명 마이그레이션")
    parser.add_argument(
        "--root",
        default="/home/k/b/daily_anomaly",
        help="검색 루트 경로 (기본: /home/k/b/daily_anomaly)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 변환 없이 목록만 출력",
    )
    args = parser.parse_args()
    migrate(args.root, args.dry_run)


if __name__ == "__main__":
    main()
