"""분석 쪽 지역표를 서비스 지역 코드에 잇는 대응표 (7지역확장계획.md 4장).

실제 지역표 파일은 저장소 밖에 있으므로, 여기서는 만들어 낸 작은 입력으로 판단 규칙만 확인한다.
"""

from build_region_mapping import (
    COMPOSED,
    LINKED,
    SOURCE_ONLY,
    UNLINKED,
    basis_date,
    build,
    double_count_risk,
    link_status,
    service_regions,
    split_codes,
)

REGIONS = {
    "sido": [
        {
            "code": "4100000000",
            "name": "가상도",
            "sigungu": [
                {"code": "4111000000", "name": "가상시"},
                {"code": "4111100000", "name": "가상시 첫째구"},
                {"code": "4113000000", "name": "둘째시"},
            ],
        },
        {"code": "3600000000", "name": "단층시", "sigungu": []},
    ]
}


def source(key: str, *, current: str = "41111", before: str = "41111", note: str = "", pop_note: str = "") -> dict:
    return {
        "region_key": key,
        "sgg_code5": current,
        "sgg_code5_pre2026": before,
        "code_status": "대조 완료(2026-08 행정기관코드)",
        "pop_note": pop_note,
        "note": note,
    }


def test_기준시점을_문구에서_꺼낸다():
    assert basis_date("대조 완료(2026-08 행정기관코드)") == "2026-08"
    assert basis_date("") == ""


def test_코드칸이_여러개면_나눠서_보관한다():
    assert split_codes("28125;28155") == ["28125", "28155"]
    assert split_codes("") == []
    assert split_codes("  41111  ") == ["41111"]


def test_자료에_줄이_없으면_미연결():
    assert link_status(None) == UNLINKED


def test_코드가_하나면_그대로_연결():
    assert link_status(source("가상도 가상시 첫째구")) == LINKED


def test_코드가_여럿이거나_나눠_합친_지역은_구성으로_표시():
    assert link_status(source("가상도 가상시 첫째구", current="28125;28155")) == COMPOSED
    assert link_status(source("가상도 가상시 첫째구", pop_note="옛 구 일부 동을 합침")) == COMPOSED


def test_시군구가_없는_시도는_시도_한_줄로_들어간다():
    rows = service_regions(REGIONS)
    단층 = [r for r in rows if r["region_code10"] == "3600000000"]
    assert len(단층) == 1
    assert 단층[0]["region_level"] == "sido"
    # 자료 쪽에서는 시도 이름이 두 번 들어간 한 줄로 온다
    assert 단층[0]["source_key"] == "단층시 단층시"


def test_연결_개수와_미연결_개수를_센다():
    result = build([source("가상도 가상시 첫째구"), source("단층시 단층시", current="36110")], REGIONS)
    counts = result["counts"]
    assert counts[LINKED] == 2
    assert counts[UNLINKED] == 2  # 가상시(구를 둔 시)와 둘째시
    assert SOURCE_ONLY not in counts


def test_서비스_목록에_없는_자료_줄은_따로_남긴다():
    result = build([source("없는도 없는군", current="99999")], REGIONS)
    assert [row["source_key"] for row in result["source_only"]] == ["없는도 없는군"]
    assert result["counts"][SOURCE_ONLY] == 1


def test_미연결_지역은_코드칸을_비워_둔다():
    result = build([], REGIONS)
    for row in result["rows"]:
        assert row["link_status"] == UNLINKED
        assert row["source_code_current"] == []
        assert row["source_key"] == ""


def test_구를_둔_시와_그_구가_둘다_연결되면_합계가_두번_더해진다():
    rows = [
        {"region_name": "가상도 가상시", "link_status": LINKED},
        {"region_name": "가상도 가상시 첫째구", "link_status": LINKED},
    ]
    assert double_count_risk(rows) == ["가상도 가상시 첫째구"]


def test_모시가_미연결이면_합계가_두번_더해지지_않는다():
    rows = [
        {"region_name": "가상도 가상시", "link_status": UNLINKED},
        {"region_name": "가상도 가상시 첫째구", "link_status": LINKED},
    ]
    assert double_count_risk(rows) == []
