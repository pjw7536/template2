"""현재 코드의 API·모델·관리 명령·화면과 문서 색인의 누락·중복을 검사합니다."""

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

    inventory = (root / "docs/reference/02-inventory.md").read_text(encoding="utf-8")
    findings: list[str] = []
    api_root = root / "apps/portal/api/api"
    paths = [*api_root.glob("*/urls.py"), *api_root.glob("*/callback_urls.py")]
    for path in sorted(paths):
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


def read_model_names(source: str) -> set[str]:
    """구체적인 Django 모델을 찾고 열거형 등 일반 클래스는 제외합니다."""

    return {
        node.name for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef)
        and any(ast.unparse(base) in {"models.Model", "Model", "AbstractUser", "AbstractBaseUser"}
                for base in node.bases)
    }


def inventory_rows(text: str, token: str) -> list[str]:
    """본문의 우연한 언급과 구분해 정확한 코드 토큰이 있는 표 행을 찾습니다."""

    return [line for line in text.splitlines()
            if line.startswith("|") and f"`{token}`" in line]


def check_models(root: Path) -> list[str]:
    """중첩 Data Movement 모델까지 앱별 색인 누락·중복·삭제 잔재를 찾습니다."""

    inventory = (root / "docs/reference/02-inventory.md").read_text(encoding="utf-8")
    api_root = root / "apps/portal/api/api"
    findings: list[str] = []
    for path in sorted(api_root.rglob("models.py")):
        actual = read_model_names(path.read_text(encoding="utf-8"))
        if not actual:
            continue
        app = path.parent.relative_to(api_root.parent).as_posix().replace("/", ".")
        rows = inventory_rows(inventory, app)
        if len(rows) != 1:
            findings.append(f"{app}: 모델 색인 행은 정확히 하나여야 합니다.")
            continue
        names = re.findall(r"`([^`]+)`", rows[0].split("|")[2])
        documented = set(names)
        findings.extend(f"{app}: 모델 색인 누락: {name}" for name in sorted(actual - documented))
        findings.extend(f"{app}: 제거되거나 잘못된 모델 색인: {name}" for name in sorted(documented - actual))
        findings.extend(f"{app}: 모델 중복: {name}" for name in sorted(documented) if names.count(name) > 1)
    return findings


def check_commands(root: Path) -> list[str]:
    """관리 명령의 이름과 실제 파일을 한 행에서 연결하고 중복 등록을 거부합니다."""

    inventory = (root / "docs/reference/02-inventory.md").read_text(encoding="utf-8")
    findings: list[str] = []
    for path in sorted((root / "apps/portal/api/api").glob("**/management/commands/*.py")):
        if path.name == "__init__.py":
            continue
        relative = path.relative_to(root).as_posix()
        rows = inventory_rows(inventory, path.stem)
        if len(rows) != 1 or f"`{relative}`" not in rows[0]:
            findings.append(f"{relative}: 관리 명령 색인은 구현 파일과 함께 정확히 한 행이어야 합니다.")
    actual_paths = {path.relative_to(root).as_posix()
                    for path in (root / "apps/portal/api/api").glob("**/management/commands/*.py")
                    if path.name != "__init__.py"}
    documented_paths = set(re.findall(r"`(apps/portal/api/api/[^`]+/management/commands/[^`]+\.py)`", inventory))
    findings.extend(f"{name}: 제거되거나 잘못된 관리 명령 색인" for name in sorted(documented_paths - actual_paths))
    return findings


def check_frontend_features(root: Path) -> list[str]:
    """모든 화면 feature가 구현 색인과 기능 안내에서 한 번씩 연결되는지 확인합니다."""

    inventory = (root / "docs/reference/02-inventory.md").read_text(encoding="utf-8")
    modules = (root / "docs/modules/README.md").read_text(encoding="utf-8")
    findings: list[str] = []
    for path in sorted((root / "apps/portal/web/src/features").glob("*/routes.jsx")):
        relative = path.relative_to(root).as_posix()
        if len(inventory_rows(inventory, relative)) != 1:
            findings.append(f"{relative}: 화면 색인 행은 정확히 하나여야 합니다.")
        if len(inventory_rows(modules, path.parent.name)) != 1:
            findings.append(f"{path.parent.name}: 기능 안내 행은 정확히 하나여야 합니다.")
    return findings


def main() -> int:
    """현재 코드와 문서 색인의 차이를 출력하고 실패 상태를 반환합니다."""

    findings = [*check_inventory(ROOT), *check_models(ROOT),
                *check_commands(ROOT), *check_frontend_features(ROOT)]
    for finding in findings:
        print(f"FAIL: {finding}")
    if not findings:
        print("OK: API·모델·관리 명령·화면 feature 색인이 현재 코드와 일치합니다.")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
