"""주민등록인구 CSV(공개 자료)에서 시도·시군구 선택 목록을 만든다.

실행: uv run python scripts/build_regions.py
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent.parent / "데이터" / "2" / "202601_202606_주민등록인구및세대현황_월간.csv"
OUT = HERE.parent / "src" / "policy_signal_map" / "resources" / "regions.json"

# The resident-population export includes service-office rows that are not
# disjoint city/county/district areas. They must not become region choices.
EXCLUDED_NON_GEOGRAPHIC_CODES = {"4159200000", "4159400000"}

JUNE_TOTAL_COLUMN = "2026년06월_총인구수"


def main() -> None:
    sido_list: list[dict] = []
    by_sido: dict[str, dict] = {}

    with SRC.open(encoding="cp949", newline="") as f:
        for row in csv.DictReader(f):
            raw = row["행정구역"]
            name_part, _, code_part = raw.rpartition("(")
            code = code_part.rstrip(")").strip()
            if code in EXCLUDED_NON_GEOGRAPHIC_CODES:
                continue
            if len(code) != 10 or not code.isdigit():
                raise ValueError(f"행정구역 형식을 읽을 수 없음: {raw}")
            name = " ".join(name_part.split())

            # 6월 총인구수가 0인 코드(폐지 등)는 선택 목록에서 제외
            if row[JUNE_TOTAL_COLUMN].replace(",", "").strip() == "0":
                continue

            sido_code = code[:2]
            if code.endswith("00000000"):
                sido = {"code": code, "name": name, "sigungu": []}
                sido_list.append(sido)
                by_sido[sido_code] = sido
                continue

            sido = by_sido.get(sido_code)
            if sido is None:
                raise ValueError(f"상위 시도 없음: {name}")
            sigungu_name = name[len(sido["name"]) :].strip()
            # 세종특별자치시처럼 시군구가 없는 단층 시도는 하위 목록을 비워 둔다
            if sigungu_name:
                sido["sigungu"].append({"code": code, "name": sigungu_name})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": "행정안전부 주민등록인구및세대현황 2026-06", "sido": sido_list}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(len(s["sigungu"]) for s in sido_list)
    print(f"시도 {len(sido_list)}개, 시군구 {total}개 -> {OUT}")


if __name__ == "__main__":
    main()
