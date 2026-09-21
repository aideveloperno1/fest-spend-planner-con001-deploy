"""분석 쪽 지역표를 서비스 지역 목록(행정표준코드 10자리)에 잇는 대응표를 만든다.

형식과 결정 이유: `7지역확장계획.md` 4장.

**만든 대응표는 공개 저장소에 올리지 않는다.** 어느 지역이 제공 자료에 들어 있는지가 드러나므로
기본 저장 위치는 git에서 제외되는 `private/`이다. 화면에 찍는 것은 개수와 상태뿐이고
지역 이름은 파일에만 쓴다.

실행: uv run python scripts/build_region_mapping.py
      uv run python scripts/build_region_mapping.py --자료 <지역표.csv> --결과 <나올 파일.json>
"""

import argparse
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
# 분석 쪽 지역표는 저장소 밖에 있다 (작업 폴더). build_regions.py와 같은 방식
DEFAULT_SOURCE = REPO_ROOT.parent / "검토사항" / "전체파일" / "region_code_map.csv"
DEFAULT_OUT = REPO_ROOT / "private" / "region_mapping.json"
REGIONS = REPO_ROOT / "src" / "policy_signal_map" / "resources" / "regions.json"

FORMAT_VERSION = "1.0"

# 연결 상태 (7지역확장계획.md 4장)
LINKED = "linked"  # 한 줄이 한 지역에 그대로 붙음
COMPOSED = "composed"  # 여러 코드를 합치거나 나눠서 붙음 — 구성 목록을 함께 본다
UNLINKED = "unlinked"  # 서비스 지역인데 자료에 그 줄이 없음
SOURCE_ONLY = "source_only"  # 자료에는 있는데 서비스 지역 목록에 없음

_BASIS_DATE = re.compile(r"(\d{4}-\d{2})")


def basis_date(code_status: str) -> str:
    """'대조 완료(2026-08 행정기관코드)' 같은 문구에서 기준 시점만 꺼낸다."""
    found = _BASIS_DATE.search(code_status or "")
    return found.group(1) if found else ""


def split_codes(raw: str) -> list[str]:
    """코드 칸은 세미콜론으로 여러 개일 수 있다. 하나로 잘라 쓰지 않는다 (인천 개편)."""
    return [code.strip() for code in (raw or "").split(";") if code.strip()]


def link_status(source_row: dict | None) -> str:
    """서비스 지역 한 곳의 연결 상태를 정한다."""
    if source_row is None:
        return UNLINKED
    if len(split_codes(source_row.get("sgg_code5", ""))) > 1:
        return COMPOSED
    if (source_row.get("pop_note") or "").strip():
        # 옛 구를 행정동 단위로 나눠 합친 경우 등
        return COMPOSED
    return LINKED


def service_regions(regions: dict) -> list[dict]:
    """서비스가 고를 수 있는 지역. 시군구가 없는 시도(세종)는 시도 한 줄로 넣는다."""
    rows = []
    for sido in regions["sido"]:
        sigungu = sido.get("sigungu", [])
        if not sigungu:
            rows.append(
                {
                    "region_code10": sido["code"],
                    "region_name": sido["name"],
                    "region_level": "sido",
                    "source_key": f"{sido['name']} {sido['name']}",
                }
            )
            continue
        for item in sigungu:
            rows.append(
                {
                    "region_code10": item["code"],
                    "region_name": f"{sido['name']} {item['name']}",
                    "region_level": "sigungu",
                    "source_key": f"{sido['name']} {item['name']}",
                }
            )
    return rows


def double_count_risk(rows: list[dict]) -> list[str]:
    """구를 둔 시와 그 구가 **둘 다** 연결되면 전국 합계가 두 번 더해진다.

    그런 지역이 있으면 이름을 돌려준다 (없어야 정상).
    """
    linked = {r["region_name"]: r for r in rows if r["link_status"] in (LINKED, COMPOSED)}
    risky = []
    for name in linked:
        # "경기도 수원시 장안구" → 모시 이름은 "경기도 수원시"
        parts = name.rsplit(" ", 1)
        if len(parts) == 2 and parts[0] in linked:
            risky.append(name)
    return sorted(risky)


def build(source_rows: list[dict], regions: dict) -> dict:
    by_key = {row["region_key"]: row for row in source_rows}
    used: set[str] = set()

    rows = []
    for region in service_regions(regions):
        source = by_key.get(region["source_key"])
        if source is not None:
            used.add(region["source_key"])
        status = link_status(source)
        rows.append(
            {
                **region,
                "source_key": region["source_key"] if source else "",
                "source_code_current": split_codes(source.get("sgg_code5", "")) if source else [],
                "source_code_before": split_codes(source.get("sgg_code5_pre2026", "")) if source else [],
                "code_basis_date": basis_date(source.get("code_status", "")) if source else "",
                "compose": (source.get("pop_note") or "").strip() if source else "",
                "link_status": status,
                "note": (source.get("note") or "").strip() if source else "자료에 이 지역 줄이 없음",
            }
        )

    leftover = [
        {
            "source_key": row["region_key"],
            "source_code_current": split_codes(row.get("sgg_code5", "")),
            "link_status": SOURCE_ONLY,
            "note": "서비스 지역 목록에서 같은 이름을 찾지 못함",
        }
        for row in source_rows
        if row["region_key"] not in used
    ]

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["link_status"]] = counts.get(row["link_status"], 0) + 1
    if leftover:
        counts[SOURCE_ONLY] = len(leftover)

    return {
        "format_version": FORMAT_VERSION,
        "service_regions_source": "resources/regions.json",
        "counts": counts,
        "double_count_risk": double_count_risk(rows),
        "rows": rows,
        "source_only": leftover,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="분석 쪽 지역표를 서비스 지역 코드에 잇는다")
    parser.add_argument("--자료", dest="source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--결과", dest="out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.source.exists():
        print(f"지역표를 찾지 못했습니다: {args.source.name}")
        return 1

    with args.source.open(encoding="utf-8-sig", newline="") as f:
        source_rows = list(csv.DictReader(f))
    regions = json.loads(REGIONS.read_text(encoding="utf-8"))

    mapping = build(source_rows, regions)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 지역 이름은 찍지 않는다 (어느 지역이 자료에 있는지 드러나지 않게). 개수와 상태만.
    counts = mapping["counts"]
    print(f"자료 {len(source_rows)}줄, 서비스 지역 {len(mapping['rows'])}곳")
    for status in (LINKED, COMPOSED, UNLINKED, SOURCE_ONLY):
        if status in counts:
            print(f"  {status}: {counts[status]}")
    risk = mapping["double_count_risk"]
    print(f"합계 두 번 더해질 위험: {'없음' if not risk else f'{len(risk)}곳 — 파일 확인 필요'}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
