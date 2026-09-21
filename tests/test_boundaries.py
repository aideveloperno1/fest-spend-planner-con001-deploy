"""패키지 의존 방향 검사 (src/policy_signal_map/README.md).

직접 import만 확인한다. llm → review → evidence처럼 거쳐서 불러오는 것은 막지 못하며,
LLM에 카드 수치가 넘어가지 않게 하는 실제 장치는 C 단계의 수치 없는 요약 함수와 출력 검사다.
"""

import ast
from pathlib import Path

PACKAGE = "policy_signal_map"
PACKAGE_DIR = Path(__file__).resolve().parent.parent / "src" / PACKAGE

LOGIC_PACKAGES = ("plan", "evidence", "review", "choices", "document", "llm")
RULES: list[tuple[tuple[str, ...], tuple[str, ...], str]] = [
    (
        LOGIC_PACKAGES,
        ("fastapi", "starlette", f"{PACKAGE}.web", f"{PACKAGE}.app"),
        "로직은 웹을 직접 import하지 않는다",
    ),
    (
        ("evidence",),
        tuple(f"{PACKAGE}.{name}" for name in ("review", "choices", "document", "llm", "plan")),
        "근거 계산은 위층을 직접 import하지 않는다",
    ),
    (
        ("llm",),
        (f"{PACKAGE}.evidence",),
        "LLM은 근거 계산을 직접 import하지 않는다",
    ),
]


def module_name(package_dir: Path, path: Path) -> str:
    parts = list(path.relative_to(package_dir.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported_modules(package_dir: Path, path: Path) -> set[str]:
    name = module_name(package_dir, path)
    package_parts = name.split(".") if path.name == "__init__.py" else name.split(".")[:-1]
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package_parts[: len(package_parts) - (node.level - 1)]
                prefix = ".".join(base + ([node.module] if node.module else []))
            else:
                prefix = node.module or ""
            found.add(prefix)
            # from . import evidence 형태
            found.update(f"{prefix}.{alias.name}" for alias in node.names)
    return found


def boundary_violations(package_dir: Path) -> list[str]:
    violations = []
    for sources, forbidden, rule in RULES:
        for source in sources:
            folder = package_dir / source
            if not folder.exists():
                continue
            for path in sorted(folder.rglob("*.py")):
                for module in sorted(imported_modules(package_dir, path)):
                    if any(module == f or module.startswith(f + ".") for f in forbidden):
                        violations.append(f"{path.relative_to(package_dir)}: {module} ({rule})")
    return violations


def test_package_boundaries_are_respected():
    assert boundary_violations(PACKAGE_DIR) == []


def test_checker_detects_relative_and_absolute_violations(tmp_path: Path):
    package_dir = tmp_path / PACKAGE
    (package_dir / "evidence").mkdir(parents=True)
    (package_dir / "llm").mkdir()
    (package_dir / "evidence" / "compare.py").write_text("from ..review import engine\nimport fastapi\n", encoding="utf-8")
    (package_dir / "llm" / "prompt.py").write_text(f"from {PACKAGE}.evidence.schema import MonthValue\n", encoding="utf-8")

    found = boundary_violations(package_dir)
    assert any("evidence\\compare.py" in v or "evidence/compare.py" in v for v in found if "fastapi" in v)
    assert any(f"{PACKAGE}.review" in v for v in found)
    assert any("llm" in v and f"{PACKAGE}.evidence" in v for v in found)


def test_allowed_imports_are_not_flagged(tmp_path: Path):
    package_dir = tmp_path / PACKAGE
    (package_dir / "evidence").mkdir(parents=True)
    (package_dir / "evidence" / "loader.py").write_text(
        "from .schema import parse_evidence\nfrom ..paths import RESOURCES_DIR\nimport json\n", encoding="utf-8"
    )
    assert boundary_violations(package_dir) == []
