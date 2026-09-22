"""Build reproducible, strictly additive public synthetic evidence.

Only disjoint leaf areas receive generated amounts. Every selectable parent is
an exact sum of its direct children; percentages are recomputed afterward.
No real transaction data or internal/private files are read.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from _evidence_builder import ok_month, pct, record, to_json_text

from policy_signal_map.paths import RESOURCES_DIR
from policy_signal_map.plan.regions import load_regions

OUT = RESOURCES_DIR / "evidence" / "review_evidence_hierarchy_v1.json"
VERSION = "demo-hierarchy-002"
SEED = "public-hierarchy-2026-09-v1"
MONTHS = tuple(f"2026-{month:02d}" for month in range(1, 7))

# These are explicit *direct* children, not inferred by code prefix at runtime.
# A parent city and its wards must never both be included in a province sum.
CITY_WARDS: dict[str, tuple[str, ...]] = {
    "4111000000": ("4111100000", "4111300000", "4111500000", "4111700000"),
    "4113000000": ("4113100000", "4113300000", "4113500000"),
    "4117000000": ("4117100000", "4117300000"),
    "4119000000": ("4119200000", "4119400000", "4119600000"),
    "4127000000": ("4127100000", "4127300000"),
    "4128000000": ("4128100000", "4128500000", "4128700000"),
    "4146000000": ("4146100000", "4146300000", "4146500000"),
    "4159000000": ("4159100000", "4159300000", "4159500000", "4159700000"),
    "4311000000": ("4311100000", "4311200000", "4311300000", "4311400000"),
    "4413000000": ("4413100000", "4413300000"),
    "5211000000": ("5211100000", "5211300000"),
    "4711000000": ("4711100000", "4711300000"),
    "4812000000": ("4812100000", "4812300000", "4812500000", "4812700000", "4812900000"),
}

INDUSTRIES = (
    ("4004", "대형할인점"), ("4010", "편의점"), ("4020", "슈퍼마켓"),
    ("8001", "일반한식"), ("8002", "갈비전문점"), ("8003", "한정식"),
    ("8004", "일식회집"), ("8005", "중국음식"), ("8006", "서양음식"),
    ("8021", "스넥"), ("8301", "제과점"),
)
AGES = (("1", "20대 이하"), ("2", "20대"), ("3", "30대"),
        ("4", "40대"), ("5", "50대"), ("6", "60대 이상"))
AGE_CODES = tuple(code for code, _ in AGES) + ("unknown",)
SEX_CODES = ("foreign", "unknown", "other")


def stable(*parts: object) -> int:
    digest = hashlib.sha256(":".join(map(str, (SEED, *parts))).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def allocate(total: int, weights: list[int]) -> list[int]:
    denominator = sum(weights)
    if total < 0 or denominator <= 0:
        raise ValueError("allocation requires nonnegative total and positive weights")
    quotients = [divmod(total * weight, denominator) for weight in weights]
    parts = [quotient for quotient, _ in quotients]
    for index in sorted(range(len(parts)), key=lambda i: (-quotients[i][1], i))[:total - sum(parts)]:
        parts[index] += 1
    return parts


@dataclass(frozen=True)
class Month:
    T: int
    F: int
    U: int
    C: int
    industry: tuple[int, ...]
    age: tuple[int, ...]  # six known bands plus an independent age-unknown band


def sum_months(months: list[Month]) -> Month:
    if not months:
        raise ValueError("an aggregate needs at least one child")
    return Month(
        *(sum(getattr(month, field) for month in months) for field in ("T", "F", "U", "C")),
        tuple(sum(month.industry[index] for month in months) for index in range(len(INDUSTRIES))),
        tuple(sum(month.age[index] for month in months) for index in range(len(AGE_CODES))),
    )


def leaf_month(code: str, index: int) -> Month:
    base = 45_000_000 + stable(code, "scale") % 95_000_000
    common = (98, 89, 103, 110, 118, 106)[index]
    local = (stable(code, "phase", index) % 31) - 15
    T = base * (common + local) // 100
    foreign_permille = 54 + stable(code, "foreign") % 75 + (stable(code, "foreign-month", index) % 23) - 11
    unknown_permille = 25 + stable(code, "unknown") % 44
    F, U = T * foreign_permille // 1000, T * unknown_permille // 1000
    C = T // (21_000 + stable(code, "ticket", index) % 13_000)
    amounts = (F, U, T - F - U)
    industry = [0] * len(INDUSTRIES)
    age = [0] * len(AGE_CODES)
    for sex, amount in zip(SEX_CODES, amounts, strict=True):
        weights = [
            (20 + stable(code, "industry", industry_code) % 65)
            * (15 + stable(code, "age", age_code) % 50)
            * (8 + stable(code, sex, industry_code, age_code, index) % 5)
            for industry_code, _ in INDUSTRIES for age_code in AGE_CODES
        ]
        cells = allocate(amount, weights)
        for n, value in enumerate(cells):
            industry[n // len(AGE_CODES)] += value
            age[n % len(AGE_CODES)] += value
    return Month(T, F, U, C, tuple(industry), tuple(age))


def hierarchy() -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, str]], set[str]]:
    regions = load_regions()["sido"]
    real_sidos = [row for row in regions if row["code"].isdigit()]
    if len(real_sidos) != 17:
        raise ValueError("expected 17 province-level choices; review the region snapshot")
    children: dict[str, tuple[str, ...]] = {"ALL": tuple(row["code"] for row in real_sidos)}
    labels: dict[str, tuple[str, str]] = {"ALL": ("national", "전국")}
    observed: set[str] = set()
    for sido in real_sidos:
        code = sido["code"]
        labels[code] = ("sido", sido["name"])
        items = {item["code"]: item["name"] for item in sido["sigungu"]}
        if len(items) != len(sido["sigungu"]):
            raise ValueError(f"duplicate subregion in {code}")
        if any(not name.endswith(("시", "군", "구")) for name in items.values()):
            raise ValueError(f"non-geographic region in {code}")
        roots = tuple(item for item in items if item not in {child for group in CITY_WARDS.values() for child in group})
        if roots:
            children[code] = roots
        for item, name in items.items():
            if item in observed:
                raise ValueError(f"duplicate region code {item}")
            observed.add(item)
            shown = name + " 전체" if item in CITY_WARDS else name
            labels[item] = ("sigungu", f"{sido['name']} {shown}")
    if len(observed) != 267 or len(CITY_WARDS) != 13 or sum(map(len, CITY_WARDS.values())) != 39:
        raise ValueError("region hierarchy changed; review all direct-child mappings")
    for parent, wards in CITY_WARDS.items():
        if parent not in labels or any(ward not in labels for ward in wards):
            raise ValueError(f"missing explicit hierarchy member: {parent}")
        parent_sido = next(row for row in real_sidos if any(item["code"] == parent for item in row["sigungu"]))
        names = {item["code"]: item["name"] for item in parent_sido["sigungu"]}
        if any(not names[ward].startswith(names[parent] + " ") for ward in wards):
            raise ValueError(f"ward name no longer matches reviewed parent: {parent}")
        # Detect new wards rather than silently dropping them from the city aggregate.
        if set(wards) != {key for key, name in names.items() if name.startswith(names[parent] + " ")}:
            raise ValueError(f"review completeness of wards under {parent}")
        children[parent] = wards
    reachable = set()
    def visit(key: str, stack: set[str]) -> None:
        if key in stack or key in reachable:
            raise ValueError("duplicate or cyclic hierarchy path")
        reachable.add(key)
        for child in children.get(key, ()):
            visit(child, stack | {key})
    visit("ALL", set())
    if reachable != set(labels):
        raise ValueError(f"unreachable region nodes: {set(labels) - reachable}")
    leaves = set(labels) - set(children)
    if len(leaves) != 255:  # 254 sigungu leaves plus Sejong province
        raise ValueError("unexpected disjoint leaf count")
    return children, labels, leaves


def build() -> dict:
    children, labels, leaves = hierarchy()
    values: dict[str, tuple[Month, ...]] = {
        code: tuple(leaf_month(code, index) for index in range(6)) for code in sorted(leaves)
    }
    def value_for(code: str) -> tuple[Month, ...]:
        if code not in values:
            parts = [value_for(child) for child in children[code]]
            values[code] = tuple(sum_months([part[index] for part in parts]) for index in range(6))
        return values[code]
    value_for("ALL")
    if len(values) != 285:
        raise ValueError("every selectable region needs one record")

    national = values["ALL"]
    national_avg = sum(month.T for month in national) / 6
    records, profiles = [], []
    for code in ["ALL", *sorted(key for key in labels if key != "ALL")]:
        scope, label = labels[code]
        months = values[code]
        record_months = [
            ok_month(month, value.F, value.T, value.U, value.C)
            for month, value in zip(MONTHS, months, strict=True)
        ]
        records.append(record(
            f"DEMO-HIERARCHY-{label.replace(' ', '-')}", record_months,
            geographic_scope=scope, region_key=code,
            region_basis="synthetic_merchant_location",
            applicability={
                "R07": {"status": "allowed", "reason": "합성 월별 금액과 비중 비교"},
                "R06": {"status": "blocked", "reason": "고급 소비 근거 검토 제외"},
                "R02": {"status": "blocked", "reason": "업종 순위 기준 미연결"},
            },
            limitations=["시연용 합성 자료", "실제 지역명의 실제 관측값이 아님", "사업 성과를 판정하지 않음"],
        ))
        total = sum(month.T for month in months)
        foreign = sum(month.F for month in months)
        unknown = sum(month.U for month in months)
        known_age = sum(sum(month.age[:-1]) for month in months)
        industry_amounts = [sum(month.industry[i] for month in months) for i in range(len(INDUSTRIES))]
        age_amounts = [sum(month.age[i] for month in months) for i in range(len(AGES))]
        own_avg = total / 6
        season = [
            {"month": month, "status": "ok", "season_index": round((value.T / own_avg) / (national[index].T / national_avg), 6)}
            for index, (month, value) in enumerate(zip(MONTHS, months, strict=True))
        ]
        profiles.append({
            "region_key": code, "geographic_scope": scope, "region_basis": "merchant",
            "period_start": MONTHS[0], "period_end": MONTHS[-1],
            "industry": [
                {"code": item, "label": name, "amount": amount, "share_pct": pct(amount, total), "status": "ok"}
                for (item, name), amount in zip(INDUSTRIES, industry_amounts, strict=True)
            ],
            "age": [
                {"code": item, "label": name, "amount": amount, "share_pct": pct(amount, known_age), "status": "ok"}
                for (item, name), amount in zip(AGES, age_amounts, strict=True)
            ],
            "age_denominator": "known_only", "months": season,
            "foreign_share_pct": pct(foreign, total), "unknown_share_pct": pct(unknown, total),
            "readiness": {
                "profile": "ok", "industry": "ok", "age": "ok", "season": "ok", "foreign": "ok",
                "industry_age": "unlinked", "external": "unlinked", "peers": "unlinked",
            },
            "limitations": ["실제 지역명이지만 모든 금액과 구성비는 시연용 합성값입니다.", "인구·유사 지역·순위는 제공하지 않습니다."],
        })
    return {"schema_version": "2.1", "dataset_version": VERSION, "records": records,
            "profiles": profiles, "thresholds": {"version": VERSION}}


def main() -> None:
    OUT.write_text(to_json_text(build()), encoding="utf-8", newline="\n")
    print(f"generated {OUT.name}")


if __name__ == "__main__":
    main()
