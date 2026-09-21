import json
import shutil
import subprocess
from pathlib import Path

import pytest
from check_public_bundle import REPO_ROOT, find_violations, tracked_files

needs_git = pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(),
    reason="git 저장소가 아닌 환경",
)


def write(root: Path, rel: str, content: str | dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else content
    path.write_text(text, encoding="utf-8")


def reasons(root: Path, files: list[str]) -> list[str]:
    return [f"{v.path}: {v.reason}" for v in find_violations(root, files)]


@needs_git
def test_tracked_files_have_no_violations():
    assert reasons(REPO_ROOT, tracked_files(REPO_ROOT)) == []


def test_detects_real_marker(tmp_path: Path):
    write(tmp_path, "data/result.json", {"records": [{"data_kind": "real"}]})
    assert reasons(tmp_path, ["data/result.json"]) == ["data/result.json: 실제 자료 표시(data_kind가 synthetic이 아님)가 있는 파일"]


def test_detects_real_marker_in_broken_json(tmp_path: Path):
    write(tmp_path, "broken.json", '{"data_kind": "real", ')
    assert "실제 자료 표시" in reasons(tmp_path, ["broken.json"])[0]


def test_detects_other_non_synthetic_kind(tmp_path: Path):
    # 약속과 다른 이름을 적어도 실제 자료 표시로 본다 (2026-09-17 임시본이 "actual_internal"이었음)
    write(tmp_path, "a.json", {"records": [{"data_kind": "actual_internal"}]})
    write(tmp_path, "b.json", '{"data_kind": "REAL", ')
    write(tmp_path, "c.json", {"records": [{"data_kind": "synthetic"}]})
    assert [r.split(":")[0] for r in reasons(tmp_path, ["a.json", "b.json", "c.json"])] == ["a.json", "b.json"]


def test_allows_registered_fixture(tmp_path: Path):
    rel = "tests/fixtures/evidence/mixed_data_kind.json"
    write(tmp_path, rel, {"schema_version": "2.0", "dataset_version": "fixture-x", "records": [{"data_kind": "real"}]})
    assert reasons(tmp_path, [rel]) == []


def test_evidence_file_must_use_synthetic_version(tmp_path: Path):
    write(tmp_path, "e.json", {"schema_version": "2.0", "dataset_version": "2026-09-17", "records": []})
    assert reasons(tmp_path, ["e.json"]) == ["e.json: 합성 버전 이름(demo-, fixture-)이 아닌 근거 파일"]


def test_detects_private_env_real_name_and_raw_data(tmp_path: Path):
    files = (
        "private/README.md",
        ".env.example",
        "private/x.txt",
        ".env",
        ".env.local",
        "a_real_b.txt",
        "data.csv",
        "model.pkl",
    )
    for rel in files:
        write(tmp_path, rel, "x")
    found = reasons(tmp_path, list(files))
    assert found == [
        "private/README.md: 배포본에 금지된 private 폴더 파일이 추적됨",
        "private/x.txt: 배포본에 금지된 private 폴더 파일이 추적됨",
        ".env: 비밀 설정 파일이 추적됨",
        ".env.local: 비밀 설정 파일이 추적됨",
        "a_real_b.txt: 실제 자료 이름 규칙(_real_) 파일이 추적됨",
        "data.csv: 원자료·중간 산출물 형식(csv·엑셀·parquet·pickle) 파일이 추적됨",
        "model.pkl: 원자료·중간 산출물 형식(csv·엑셀·parquet·pickle) 파일이 추적됨",
    ]


def test_unreadable_tracked_file_is_violation(tmp_path: Path):
    assert reasons(tmp_path, ["missing.json"]) == ["missing.json: 추적 파일을 읽을 수 없음 (삭제했다면 git rm으로 반영)"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git 없음")
def test_korean_file_name_is_scanned(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    write(tmp_path, "외국인분석결과.json", {"records": [{"data_kind": "real"}]})
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)

    files = tracked_files(tmp_path)
    assert files == ["외국인분석결과.json"]
    assert reasons(tmp_path, files) == ["외국인분석결과.json: 실제 자료 표시(data_kind가 synthetic이 아님)가 있는 파일"]
