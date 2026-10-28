"""실제 Django route와 문서 인벤토리의 모듈별 endpoint를 대조합니다."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def normalize_route(route: str) -> str:
    """Django converter와 끝 슬래시를 제거해 문서의 상대 경로로 맞춥니다."""

    return re.sub(r"<[^:>]+:([^>]+)>", r"<\1>", route).rstrip("/")


def read_routes(source: str) -> set[str]:
    """따옴표·줄바꿈 형식과 무관하게 urlpatterns의 리터럴 path를 읽습니다."""

    routes: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "urlpatterns"
                   for target in node.targets):
            continue
        for call in ast.walk(node.value):
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == "path" and call.args
                    and isinstance(call.args[0], ast.Constant)
                    and isinstance(call.args[0].value, str)):
                route = normalize_route(call.args[0].value)
                if route:
                    routes.add(route)
    return routes


def check_inventory(root: Path) -> list[str]:
    """각 라우팅 파일의 색인 누락과 삭제된 endpoint 안내를 반환합니다."""

    inventory = (root / "docs/inventory.md").read_text(encoding="utf-8")
    findings: list[str] = []
    for path in sorted((root / "apps/portal/api/api").glob("*/urls.py")):
        relative = path.relative_to(root).as_posix()
        rows = [line for line in inventory.splitlines()
                if line.startswith("|") and f"`{relative}`" in line]
        if len(rows) != 1:
            findings.append(f"{relative}: 인벤토리 행은 정확히 하나여야 합니다.")
            continue
        cells = rows[0].split("|")
        documented = {normalize_route(value) for value in re.findall(r"`([^`]+)`", cells[-2])}
        actual = read_routes(path.read_text(encoding="utf-8"))
        findings.extend(f"{relative}: endpoint 색인 누락: {route}"
                        for route in sorted(actual - documented))
        findings.extend(f"{relative}: 제거되거나 잘못된 endpoint 색인: {route}"
                        for route in sorted(documented - actual))
    return findings


def main() -> int:
    """저장소의 endpoint 색인 정합성을 검사하고 실패 상태를 반환합니다."""

    findings = check_inventory(ROOT)
    for finding in findings:
        print(f"FAIL: {finding}")
    if not findings:
        print("OK: 모든 backend 모듈의 endpoint 색인이 실제 urlpatterns와 일치합니다.")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
