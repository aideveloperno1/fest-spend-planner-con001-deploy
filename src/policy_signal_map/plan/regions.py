"""시도·시군구 선택 목록. scripts/build_regions.py가 만든 regions.json을 읽는다."""

import json
from functools import cache

from ..paths import RESOURCES_DIR
from .models import Region, RegionLevel

DATA_FILE = RESOURCES_DIR / "regions.json"
DEMO_DATA_FILE = RESOURCES_DIR / "demo_regions.json"


@cache
def load_regions() -> dict:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if DEMO_DATA_FILE.exists():
        demo = json.loads(DEMO_DATA_FILE.read_text(encoding="utf-8"))["sido"]
        # 공개 전달본의 가상 지역을 실제 행정구역과 섞어 보이지 않게 별도 묶음으로 앞에 둔다.
        data = {**data, "sido": [demo, *data["sido"]]}
    return data


def sido_list() -> list[dict]:
    return load_regions()["sido"]


def find_sido(code: str) -> dict | None:
    return next((s for s in sido_list() if s["code"] == code), None)


def is_known_region(region: Region) -> bool:
    if region.level is RegionLevel.NATIONAL:
        return True
    sido = find_sido(region.sido_code)
    if sido is None:
        return False
    if region.level is RegionLevel.SIDO:
        return True
    return any(g["code"] == region.sigungu_code for g in sido["sigungu"])


def region_label(region: Region | None) -> str:
    if region is None:
        return ""
    if region.level is RegionLevel.NATIONAL:
        return "전국"
    sido = find_sido(region.sido_code)
    if sido is None:
        return ""
    if region.level is RegionLevel.SIDO:
        return sido["name"]
    sigungu = next((g for g in sido["sigungu"] if g["code"] == region.sigungu_code), None)
    return f"{sido['name']} {sigungu['name']}" if sigungu else sido["name"]


def find_sigungu(code: str) -> tuple[dict, dict] | None:
    """시군구 행정표준코드로 (시도, 시군구)를 찾는다. 없으면 None."""
    for sido in sido_list():
        for gu in sido["sigungu"]:
            if gu["code"] == code:
                return sido, gu
    return None


def sigungu_name(code: str) -> str:
    """시군구 코드를 "강원특별자치도 강릉시"처럼 바꾼다. 목록에 없으면 빈 글자."""
    found = find_sigungu(code)
    return f"{found[0]['name']} {found[1]['name']}" if found else ""
