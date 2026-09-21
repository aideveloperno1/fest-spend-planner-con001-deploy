"""공개 저장소에 실제 자료·비밀 설정이 섞이지 않았는지 검사한다.

실행: uv run python scripts/check_public_bundle.py   (푸시·배포 전)
파일 이름뿐 아니라 내용으로 검사해, 이름을 바꿔 둔 실수도 잡는다.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# 이름표만 real이고 수치는 가짜인 테스트 사례 (tests/fixtures/evidence/README.md)
ALLOWED_REAL_MARKERS = frozenset({"tests/fixtures/evidence/mixed_data_kind.json"})
SYNTHETIC_VERSION_PREFIXES = ("demo-", "fixture-")
# 원본 카드 자료가 들어 있을 수 있는 형식
RAW_DATA_SUFFIXES = (".csv", ".xlsx", ".xls", ".parquet", ".pkl", ".pickle", ".joblib")

# synthetic이 아닌 data_kind는 모두 실제 자료 표시로 본다 ("actual_internal" 같은 다른 이름도 잡는다)
_REAL_MARKER_RE = re.compile(r'"data_kind"\s*:\s*"(?!synthetic")[^"]*"')


@dataclass(frozen=True)
class Violation:
    path: str
    reason: str


def tracked_files(repo_root: Path = REPO_ROOT) -> list[str]:
    # quotepath=false: 한글 경로가 "\354\236..."로 이스케이프되면 파일을 열지 못해 검사가 빠진다
    output = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    ).stdout
    return [path for path in output.decode("utf-8").split("\0") if path]


def _has_real_kind(data: Any) -> bool:
    if isinstance(data, dict):
        kind = data.get("data_kind")
        if isinstance(kind, str) and kind != "synthetic":
            return True
        return any(_has_real_kind(value) for value in data.values())
    if isinstance(data, list):
        return any(_has_real_kind(item) for item in data)
    return False


def find_violations(repo_root: Path, files: Iterable[str]) -> list[Violation]:
    violations: list[Violation] = []
    for rel in files:
        name = rel.rsplit("/", 1)[-1]
        lower = rel.lower()

        if rel.startswith("private/"):
            violations.append(Violation(rel, "배포본에 금지된 private 폴더 파일이 추적됨"))
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            violations.append(Violation(rel, "비밀 설정 파일이 추적됨"))
        if "_real_" in lower:
            violations.append(Violation(rel, "실제 자료 이름 규칙(_real_) 파일이 추적됨"))
        if lower.endswith(RAW_DATA_SUFFIXES):
            violations.append(Violation(rel, "원자료·중간 산출물 형식(csv·엑셀·parquet·pickle) 파일이 추적됨"))

        if not lower.endswith(".json"):
            continue
        try:
            text = (repo_root / rel).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            # 열 수 없는 파일을 건너뛰면 검사가 빠진다
            violations.append(Violation(rel, "추적 파일을 읽을 수 없음 (삭제했다면 git rm으로 반영)"))
            continue
        try:
            data = json.loads(text)
        except ValueError:
            data = None

        if rel not in ALLOWED_REAL_MARKERS and (_REAL_MARKER_RE.search(text) or _has_real_kind(data)):
            violations.append(Violation(rel, "실제 자료 표시(data_kind가 synthetic이 아님)가 있는 파일"))
        if isinstance(data, dict) and "schema_version" in data and "records" in data:
            version = data.get("dataset_version")
            if not (isinstance(version, str) and version.startswith(SYNTHETIC_VERSION_PREFIXES)):
                violations.append(Violation(rel, "합성 버전 이름(demo-, fixture-)이 아닌 근거 파일"))
    return violations


def main() -> int:
    files = tracked_files(REPO_ROOT)
    violations = find_violations(REPO_ROOT, files)
    if violations:
        print(f"공개 금지 위반 {len(violations)}건:")
        for v in violations:
            print(f"  {v.path}: {v.reason}")
        return 1
    print(f"추적 파일 {len(files)}개 검사, 위반 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
