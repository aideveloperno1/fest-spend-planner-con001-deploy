"""Public hierarchical synthetic evidence must be additive and selectable."""

import json
import re

import build_hierarchy_evidence as generated
from _evidence_builder import to_json_text
from fastapi.testclient import TestClient
from helpers import VALID_FORM, parse

from policy_signal_map.app import app
from policy_signal_map.config import DEFAULT_EVIDENCE_PATH
from policy_signal_map.evidence.loader import load_evidence
from policy_signal_map.plan.models import PlanInput, Region, RegionLevel
from policy_signal_map.plan.regions import load_regions, region_label
from policy_signal_map.review.context import select_main
from policy_signal_map.review.engine import run_review


def test_generated_file_is_reproducible_and_valid():
    assert DEFAULT_EVIDENCE_PATH.read_text(encoding="utf-8") == to_json_text(generated.build())
    loaded = load_evidence(DEFAULT_EVIDENCE_PATH)
    assert (len(loaded.file.records), len(loaded.profiles), len(loaded.warnings)) == (285, 285, 0)
    assert loaded.file.data_kind == "synthetic"


def test_every_parent_is_exact_sum_of_direct_children():
    children, labels, leaves = generated.hierarchy()
    assert (len(labels), len(leaves)) == (285, 255)
    data = generated.build()
    records = {row["scope"]["region_key"]: row for row in data["records"]}
    for parent, child_codes in children.items():
        for month_index in range(6):
            parent_month = records[parent]["months"][month_index]
            for key in ("total_amount", "foreign_amount", "unknown_amount", "transaction_count"):
                assert parent_month[key] == sum(records[child]["months"][month_index][key] for child in child_codes), (parent, key, month_index)
    assert records["4117000000"]["months"][0]["total_amount"] == sum(
        records[key]["months"][0]["total_amount"] for key in ("4117100000", "4117300000")
    )
    assert children["4159000000"] == ("4159100000", "4159300000", "4159500000", "4159700000")
    assert all(code not in labels for code in ("4159200000", "4159400000"))


def test_region_catalog_excludes_service_offices_and_marks_snapshot():
    regions = load_regions()["sido"]
    actual = [row for row in regions if row["code"].isdigit()]
    choices = [item for sido in actual for item in sido["sigungu"]]
    assert (len(actual), len(choices)) == (17, 267)
    assert all(item["name"].endswith(("시", "군", "구")) for item in choices)
    assert not {"4159200000", "4159400000"} & {item["code"] for item in choices}
    assert {item["name"] for item in next(row for row in actual if row["name"] == "인천광역시")["sigungu"]} >= {"중구", "동구", "서구"}
    client = TestClient(app)
    html = client.get("/step/1").text
    assert "지역 선택지는 2026년 6월 기준" in html
    assert "화성시동부출장소" not in html
    assert "화성시동탄출장소" not in html


def test_profile_marginals_and_period_share_match_records():
    data = generated.build()
    records = {row["scope"]["region_key"]: row for row in data["records"]}
    profiles = {row["region_key"]: row for row in data["profiles"]}
    for profile in data["profiles"]:
        months = records[profile["region_key"]]["months"]
        total = sum(row["total_amount"] for row in months)
        foreign = sum(row["foreign_amount"] for row in months)
        assert sum(row["amount"] for row in profile["industry"]) == total
        assert abs(profile["foreign_share_pct"] - foreign / total * 100) < 1e-6
        assert abs(sum(row["share_pct"] for row in profile["industry"]) - 100) < 1e-5
        assert abs(sum(row["share_pct"] for row in profile["age"]) - 100) < 1e-5
    children, _, _ = generated.hierarchy()
    for parent, child_codes in children.items():
        for dimension in ("industry", "age"):
            for index, item in enumerate(profiles[parent][dimension]):
                assert item["amount"] == sum(profiles[child][dimension][index]["amount"] for child in child_codes)


def test_all_selectable_regions_have_exact_main_record():
    loaded = load_evidence(DEFAULT_EVIDENCE_PATH)
    children, labels, _ = generated.hierarchy()
    for code, (scope, _) in labels.items():
        if scope == "national":
            region = Region(RegionLevel.NATIONAL)
        elif scope == "sido":
            region = Region(RegionLevel.SIDO, sido_code=code)
        else:
            parent = next(key for key, members in children.items() if code in members)
            region = Region(RegionLevel.SIGUNGU, sido_code=parent, sigungu_code=code)
            if parent in generated.CITY_WARDS:
                parent = next(key for key, members in children.items() if parent in members)
                region = Region(RegionLevel.SIGUNGU, sido_code=parent, sigungu_code=code)
        selection = select_main(loaded.file, PlanInput(region=region))
        assert selection.record is not None
        assert selection.record.scope.region_key == code
        assert selection.region_note is None


def test_step_two_uses_selected_ward_and_rejects_old_demo_code(use_evidence):
    use_evidence(DEFAULT_EVIDENCE_PATH)
    client = TestClient(app)
    form = {**VALID_FORM, "sido": "4100000000", "sigungu": "4117100000"}
    response = client.post("/step/1", data=form, follow_redirects=True)
    assert response.status_code == 200
    assert str(response.url).endswith("/step/2")
    assert "안양시 만안구 범위 참고" in response.text
    assert "전국 참고 — 특정 지역의 진단이 아님" not in response.text
    assert 'id="chart-data"' in response.text

    bad = TestClient(app).post("/step/1", data={**VALID_FORM, "sido": "DEMO", "sigungu": "DEMO-SGG-A"})
    assert bad.status_code == 422
    assert "시연 자료가 연결된 지역" in bad.text or "지역" in bad.text
    for code in ("4159200000", "4159400000"):
        office = TestClient(app).post(
            "/step/1", data={**VALID_FORM, "sido": "4100000000", "sigungu": code}
        )
        assert office.status_code == 422


def test_switching_city_and_wards_changes_chart_series(use_evidence):
    use_evidence(DEFAULT_EVIDENCE_PATH)
    assert region_label(Region(RegionLevel.SIGUNGU, sido_code="4100000000", sigungu_code="4117000000")) == "경기도 안양시 전체"
    series = {}
    for code in ("4117000000", "4117100000", "4117300000"):
        client = TestClient(app)
        html = client.post(
            "/step/1",
            data={**VALID_FORM, "sido": "4100000000", "sigungu": code},
            follow_redirects=True,
        ).text
        match = re.search(r'<script type="application/json" id="chart-data">(.*?)</script>', html, re.S)
        assert match is not None
        if code == "4117000000":
            assert "경기도 안양시 전체" in html
        series[code] = json.loads(match.group(1))["foreign_amount"]
    assert series["4117000000"] != series["4117100000"] != series["4117300000"]
    assert len({tuple(values) for values in series.values()}) == 3


def test_hierarchy_dataset_completes_five_steps_and_word_download(use_evidence):
    loaded = use_evidence(DEFAULT_EVIDENCE_PATH).result
    form = {**VALID_FORM, "sido": "4100000000", "sigungu": "4117100000"}
    client = TestClient(app)
    assert client.post("/step/1", data=form, follow_redirects=False).status_code == 303
    for step in (2, 3, 4):
        assert client.get(f"/step/{step}").status_code == 200
    review = run_review(parse(form), loaded)
    assert review.evidence_id == "DEMO-HIERARCHY-경기도-안양시-만안구"
    for question in review.questions:
        answer = client.post("/step/4", data={"question_key": question.question_key, "decision": "keep_original"})
        assert answer.status_code == 200
    draft = client.get("/step/5")
    assert draft.status_code == 200
    assert "demo-hierarchy-002" in draft.text
    download = client.get("/step/5/download")
    assert download.status_code == 200
    assert download.content[:2] == b"PK"
