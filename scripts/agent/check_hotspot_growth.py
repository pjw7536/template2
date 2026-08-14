#!/usr/bin/env python3
"""기존 대형 파일과 테스트 클래스의 신규 증가를 차단합니다."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = (ROOT_DIR / "apps" / "api" / "api", ROOT_DIR / "apps" / "web" / "src")
FILE_BASELINE = ROOT_DIR / "scripts" / "agent" / "hotspot-baseline.tsv"
CLASS_BASELINE = ROOT_DIR / "scripts" / "agent" / "test-class-hotspot-baseline.tsv"


def read_rows(path: Path, columns: int) -> list[tuple[str, ...]]:
    """주석과 빈 줄을 제외한 TSV 행을 읽습니다."""

    rows: list[tuple[str, ...]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        values = tuple(line.split("\t"))
        if len(values) != columns:
            raise ValueError(f"{path}: 잘못된 baseline 행: {raw_line}")
        rows.append(values)
    return rows


def is_test_file(path: Path) -> bool:
    """production/test LOC 임계값 구분을 반환합니다."""

    return path.name == "tests.py" or path.name.startswith("test_") or ".test." in path.name


def iter_sources():
    """감사 대상 Python/JavaScript source를 순회합니다."""

    for root in SOURCE_ROOTS:
        for path in sorted(root.rglob("*")):
            if path.suffix not in {".py", ".js", ".jsx"} or "migrations" in path.parts:
                continue
            yield path


def main() -> int:
    """기준선을 초과한 신규 증가를 출력하고 실패 상태를 반환합니다."""

    file_baseline = {path: int(limit) for path, limit in read_rows(FILE_BASELINE, 2)}
    class_baseline = {
        (path, class_name): int(limit)
        for path, class_name, limit in read_rows(CLASS_BASELINE, 3)
    }
    findings: list[str] = []
    seen_files: set[str] = set()
    seen_classes: set[tuple[str, str]] = set()

    for path in iter_sources():
        rel_path = path.relative_to(ROOT_DIR).as_posix()
        seen_files.add(rel_path)
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        default_limit = 1500 if is_test_file(path) else 1000
        limit = file_baseline.get(rel_path, default_limit)
        if line_count > limit:
            findings.append(f"{rel_path}: {line_count} lines exceeds {limit}")
        elif rel_path in file_baseline and line_count <= default_limit:
            findings.append(f"obsolete file baseline: {rel_path}")

        if path.suffix != ".py" or not is_test_file(path):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.end_lineno is None:
                continue
            key = (rel_path, node.name)
            seen_classes.add(key)
            class_lines = node.end_lineno - node.lineno + 1
            class_limit = class_baseline.get(key, 500)
            if class_lines > class_limit:
                findings.append(
                    f"{rel_path}:{node.lineno}: {node.name} has {class_lines} lines; limit {class_limit}"
                )
            elif key in class_baseline and class_lines <= 500:
                findings.append(
                    f"obsolete test class baseline: {rel_path}:{node.name}"
                )

    stale_files = sorted(set(file_baseline) - seen_files)
    stale_classes = sorted(set(class_baseline) - seen_classes)
    if stale_files:
        findings.extend(f"unused file baseline: {path}" for path in stale_files)
    if stale_classes:
        findings.extend(
            f"unused test class baseline: {path}:{class_name}"
            for path, class_name in stale_classes
        )

    print("== Source hotspot growth ==")
    if findings:
        print("\n".join(findings))
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
