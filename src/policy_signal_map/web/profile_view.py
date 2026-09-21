"""2단계 "지역 소비 프로필" 카드에 넘길 데이터 조립 (7지역확장계획.md 3장).

**고른 지역의 자료만 쓴다.** 금액·비중 비교(R07)는 자료가 없으면 한 칸 넓혀 전국까지 올라가지만,
프로필은 넓히지 않는다. 다른 지역 구성을 그 지역 것처럼 보여 주게 되기 때문이다 (최종검토v3 8-2).

준비됐다고 적히지 않은 부분은 보여 주지 않는다. 모르면 보여 주지 않는 쪽이 맞다.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..evidence.loader import LoadResult
from ..evidence.profile_schema import RegionProfile, ShareItem
from ..formatting import month_label
from ..plan.models import PlanInput
from ..plan.regions import region_label
from ..review.context import exact_region_key, region_display

# 순위 칸 이름 → 화면 글자. 근거 파일에 없는 이름이 오면 그 이름을 그대로 쓰지 않고 건너뛴다
RANK_LABELS = {
    "foreign_share": "외국인 결제 비중",
    "payment_amount": "결제금액 규모",
    "payment_count": "결제건수",
}

NOT_LINKED_NOTE = "이 지역은 아직 지역 소비 프로필에 연결되지 않았습니다."
BASIS_NOTES = {
    "merchant": "그 지역 가맹점에서 결제된 금액입니다.",
    "cardholder": "그 지역에 사는 사람이 결제한 금액입니다.",
    "unconfirmed": "지역 구분의 기준(가맹점 자리인지 이용자 기준인지)은 확인 중입니다. 주민의 소비로 읽지 마세요.",
}


@dataclass(frozen=True)
class CodeOption:
    """근거 파일이 알려 주는 선택지 하나 (업종·연령).

    서비스가 목록을 지어내지 않는다. 자료에 없는 업종·연령은 고를 수 없다.
    """

    code: str
    label: str


@dataclass(frozen=True)
class Catalog:
    industries: tuple[CodeOption, ...] = ()
    ages: tuple[CodeOption, ...] = ()

    @property
    def ready(self) -> bool:
        return bool(self.industries or self.ages)

    def industry_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.industries)

    def age_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.ages)

    def label_of(self, code: str) -> str:
        """화면에 쓸 이름. 모르는 코드는 코드를 그대로 내보내지 않고 빈 글자를 준다."""
        for item in (*self.industries, *self.ages):
            if item.code == code:
                return item.label
        return ""


def option_catalog(result: LoadResult | None) -> Catalog:
    """고를 수 있는 업종·연령 목록. 전국(ALL) 프로필을 기준 목록으로 쓴다.

    전국 프로필이 없거나 준비되지 않았으면 빈 목록이다 — 그때는 화면에 입력칸을 두지 않는다.
    지역마다 목록이 다를 수 있지만, 입력 화면은 지역을 고르기 전에도 보여야 해서 전국을 쓴다.
    """
    profile = result.profile("ALL") if result is not None else None
    if profile is None:
        return Catalog()
    industries = tuple(CodeOption(item.code, item.label) for item in profile.industry) if profile.ready("industry") else ()
    ages = tuple(CodeOption(item.code, item.label) for item in profile.age) if profile.ready("age") else ()
    return Catalog(industries=industries, ages=ages)


@dataclass(frozen=True)
class MonthIndex:
    label: str
    status: str
    value: float | None

    @property
    def missing(self) -> bool:
        return self.value is None


@dataclass(frozen=True)
class RankRow:
    label: str
    percentile: float
    regions: int


@dataclass(frozen=True)
class PeerRow:
    label: str
    distance: float


@dataclass(frozen=True)
class Section:
    """카드 안의 한 묶음. 보여 줄 수 없으면 이유 한 줄만 남는다."""

    ready: bool
    note: str
    rows: tuple[ShareItem, ...] = ()
    months: tuple[MonthIndex, ...] = ()


@dataclass(frozen=True)
class ProfileView:
    region_label: str
    available: bool
    note: str | None
    basis_note: str = ""
    period: str = ""
    industry: Section | None = None
    age: Section | None = None
    season: Section | None = None
    foreign_share_pct: float | None = None
    foreign_type: str | None = None
    foreign_type_status: str | None = None
    unknown_share_pct: float | None = None
    foreign_ready: bool = False
    foreign_note: str = ""
    ranks: tuple[RankRow, ...] = ()
    peers: tuple[PeerRow, ...] = ()
    peer_method_note: str = ""
    age_denominator_note: str = ""
    limitations: tuple[str, ...] = ()


# 고른 지역의 키는 review/context.py가 정한다 (검토 질문과 화면이 같은 기준을 쓰게)
region_key_for = exact_region_key


def _section(profile: RegionProfile, key: str, rows: tuple[ShareItem, ...] = (), months: tuple[MonthIndex, ...] = ()) -> Section:
    ready = profile.ready(key) and bool(rows or months)
    if profile.ready(key) and not (rows or months):
        # 쓸 수 있다고 적혀 있는데 값이 없으면, 있는 척하지 않고 없다고 적는다
        return Section(ready=False, note="이 지역은 해당 자료가 비어 있습니다.")
    return Section(ready=ready, note="" if ready else profile.readiness_note(key), rows=rows, months=months)


def _ranks(profile: RegionProfile) -> tuple[RankRow, ...]:
    rows = []
    for name, rank in profile.ranks.items():
        label = RANK_LABELS.get(name)
        if label is None:
            continue  # 모르는 칸 이름을 화면에 그대로 내보내지 않는다
        rows.append(RankRow(label=label, percentile=rank.percentile, regions=rank.regions))
    return tuple(rows)


def _peers(profile: RegionProfile) -> tuple[PeerRow, ...]:
    if not profile.ready("peers"):
        return ()
    return tuple(
        PeerRow(region_display("sigungu", peer.region_key), peer.distance)
        for peer in profile.peers
    )


def build_profile_view(plan: PlanInput, result: LoadResult | None) -> ProfileView:
    label = region_label(plan.region) or "선택한 지역"
    key = region_key_for(plan)
    profile = result.profile(key) if (result is not None and key) else None

    if profile is None:
        return ProfileView(region_label=label, available=False, note=NOT_LINKED_NOTE)
    if not profile.ready("profile"):
        return ProfileView(region_label=label, available=False, note=profile.readiness_note("profile"))

    months = tuple(
        MonthIndex(label=month_label(m.month), status=m.status, value=m.season_index) for m in profile.months
    )
    age_note = (
        "연령을 알 수 없는 결제는 빼고 계산한 비중입니다."
        if profile.age_denominator == "known_only"
        else "연령을 알 수 없는 결제를 포함해 계산한 비중입니다."
    )
    return ProfileView(
        region_label=label,
        available=True,
        note=None,
        basis_note=BASIS_NOTES.get(profile.region_basis, BASIS_NOTES["unconfirmed"]),
        period=f"{month_label(profile.period_start)} ~ {month_label(profile.period_end)}",
        industry=_section(profile, "industry", rows=profile.industry),
        age=_section(profile, "age", rows=profile.age),
        season=_section(profile, "season", months=months),
        foreign_share_pct=profile.foreign_share_pct,
        foreign_type=profile.foreign_type,
        foreign_type_status=profile.foreign_type_status,
        unknown_share_pct=profile.unknown_share_pct,
        foreign_ready=profile.ready("foreign") and profile.foreign_share_pct is not None,
        foreign_note="" if profile.ready("foreign") else profile.readiness_note("foreign"),
        ranks=_ranks(profile),
        peers=_peers(profile),
        peer_method_note=(
            "분석 전달본이 업종·연령·외국인 결제 구성을 표준화해 계산한 유사도입니다."
            if profile.ready("peers") and profile.peer_method
            else ""
        ),
        age_denominator_note=age_note,
        limitations=profile.limitations,
    )
