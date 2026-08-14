#!/usr/bin/env python3
"""React feature facade, 의존 방향과 lib 소유권을 점검합니다."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
WEB_SRC = ROOT_DIR / "apps" / "web" / "src"
FEATURES_DIR = WEB_SRC / "features"
SOURCE_SUFFIXES = {".js", ".jsx"}
ALLOWED_FEATURE_DEPENDENCIES = {
    "auth": {"account"},
    "emails": {"account"},
    "line-dashboard": {"account"},
}
ALLOWED_SUBDIRECTORIES = {"pages", "components", "hooks", "api", "store", "utils"}
ALLOWED_COMPONENT_GROUPS = {
    "list",
    "detail",
    "form",
    "dialog",
    "table",
    "chart",
    "filters",
    "cards",
    "sections",
}
IMPORT_SPECIFIER_PATTERN = re.compile(
    r"(?:\b(?:import|export)\s+(?:[^\"'`;]*?\s+from\s*)?[\"']([^\"']+)[\"']"
    r"|\bimport\s*\(\s*[\"']([^\"']+)[\"'])"
)


def iter_sources(root: Path):
    """JavaScript/JSX source를 안정된 순서로 순회합니다."""

    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            yield path


def feature_for_path(path: Path) -> str | None:
    """source가 속한 feature 이름을 반환합니다."""

    try:
        return path.relative_to(FEATURES_DIR).parts[0]
    except ValueError:
        return None


def iter_import_specifiers(text: str):
    """정적·side-effect·동적 import의 specifier와 위치를 반환합니다."""

    for match in IMPORT_SPECIFIER_PATTERN.finditer(text):
        specifier = match.group(1) or match.group(2)
        yield specifier, match.start()


def resolve_project_import(path: Path, specifier: str) -> Path | None:
    """alias 또는 상대 import를 `src` 아래의 실제 경로로 정규화합니다."""

    if specifier.startswith("@/"):
        candidate = WEB_SRC / specifier[2:]
    elif specifier.startswith("."):
        candidate = path.parent / specifier
    else:
        return None
    return candidate.resolve()


def resolved_feature(path: Path) -> tuple[str, tuple[str, ...]] | None:
    """해석된 project 경로가 가리키는 feature와 내부 경로를 반환합니다."""

    try:
        parts = path.relative_to(FEATURES_DIR.resolve()).parts
    except ValueError:
        return None
    if not parts:
        return None
    return parts[0], parts[1:]


def check_feature_imports() -> tuple[list[str], list[str], dict[str, set[str]]]:
    """feature import의 public facade 사용과 선언된 의존 방향을 점검합니다."""

    internal_imports: list[str] = []
    dependency_findings: list[str] = []
    graph: dict[str, set[str]] = defaultdict(set)
    for path in iter_sources(WEB_SRC):
        source_feature = feature_for_path(path)
        text = path.read_text(encoding="utf-8")
        for specifier, position in iter_import_specifiers(text):
            resolved = resolve_project_import(path, specifier)
            target = resolved_feature(resolved) if resolved else None
            if target is None:
                continue
            target_feature, tail = target
            line = text.count("\n", 0, position) + 1
            rel_path = path.relative_to(ROOT_DIR).as_posix()
            is_alias_facade = specifier == f"@/features/{target_feature}"
            if tail or not is_alias_facade:
                if source_feature != target_feature or specifier.startswith("@/features/"):
                    internal_imports.append(
                        f"{rel_path}:{line}: feature import must use facade: {specifier}"
                    )
                continue
            if source_feature is None or source_feature == target_feature:
                continue
            graph[source_feature].add(target_feature)
            if target_feature not in ALLOWED_FEATURE_DEPENDENCIES.get(source_feature, set()):
                dependency_findings.append(
                    f"{rel_path}:{line}: undeclared dependency {source_feature} -> {target_feature}"
                )
    return internal_imports, dependency_findings, graph


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    """feature dependency graph의 첫 순환 경로를 반환합니다."""

    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            start = visiting.index(node)
            return [*visiting[start:], node]
        if node in visited:
            return None
        visiting.append(node)
        for target in sorted(graph.get(node, set())):
            cycle = visit(target)
            if cycle:
                return cycle
        visiting.pop()
        visited.add(node)
        return None

    for node in sorted(graph):
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def print_section(title: str, findings: list[str]) -> int:
    """감사 section과 상태를 출력합니다."""

    print(f"== {title} ==")
    if findings:
        print("\n".join(findings))
        print()
        return 1
    print("OK\n")
    return 0


def main() -> int:
    """frontend boundary 위반을 모아 종료 상태로 반환합니다."""

    if not FEATURES_DIR.is_dir():
        print("Missing feature directory: apps/web/src/features")
        return 2

    internal_imports, dependency_findings, graph = check_feature_imports()

    cycle = find_cycle(graph)
    if cycle:
        dependency_findings.append(f"feature dependency cycle: {' -> '.join(cycle)}")

    facade_findings: list[str] = []
    structure_findings: list[str] = []
    for feature_dir in sorted(path for path in FEATURES_DIR.iterdir() if path.is_dir()):
        for required in ("index.js", "routes.jsx"):
            if not (feature_dir / required).is_file():
                structure_findings.append(f"{feature_dir.name}: missing {required}")
        facade = feature_dir / "index.js"
        if facade.is_file():
            for line_number, line in enumerate(facade.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"\bexport\s+\*", line):
                    facade_findings.append(
                        f"{facade.relative_to(ROOT_DIR)}:{line_number}: export-star is forbidden"
                    )
        for child in sorted(path for path in feature_dir.iterdir() if path.is_dir()):
            if child.name not in ALLOWED_SUBDIRECTORIES:
                structure_findings.append(child.relative_to(ROOT_DIR).as_posix())
        components = feature_dir / "components"
        if components.is_dir():
            for group in sorted(path for path in components.iterdir() if path.is_dir()):
                if group.name not in ALLOWED_COMPONENT_GROUPS:
                    structure_findings.append(group.relative_to(ROOT_DIR).as_posix())
                for nested in sorted(path for path in group.rglob("*") if path.is_dir()):
                    structure_findings.append(nested.relative_to(ROOT_DIR).as_posix())

    lib_findings: list[str] = []
    forbidden_lib_dirs = [WEB_SRC / "lib" / "account"]
    for path in forbidden_lib_dirs:
        if path.exists():
            lib_findings.append(f"{path.relative_to(ROOT_DIR)}: domain-owned lib directory is forbidden")
    for path in iter_sources(WEB_SRC / "lib"):
        text = path.read_text(encoding="utf-8")
        rel_path = path.relative_to(ROOT_DIR).as_posix()
        if "@tanstack/react-query" in text and path.name != "queryClient.js":
            lib_findings.append(f"{rel_path}: React Query belongs to a feature")
        if re.search(r"[\"']/api/v1/", text):
            lib_findings.append(f"{rel_path}: domain HTTP endpoint belongs to a feature")

    status = 0
    status |= print_section("Cross-feature internal imports", internal_imports)
    status |= print_section("Feature dependency graph", dependency_findings)
    status |= print_section("Feature facade exports", facade_findings)
    status |= print_section("Feature structure", structure_findings)
    status |= print_section("Lib ownership", lib_findings)
    if status:
        print("Frontend boundary audit found review candidates.")
    else:
        print("Frontend boundary audit passed.")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
