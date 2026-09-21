// 기획 입력 화면의 즉시 반응 (서버 검증을 대신하지 않음)
(() => {
  const form = document.getElementById("plan-form");
  if (!form) return;
  const regions = JSON.parse(document.getElementById("regions-data").textContent).sido;

  // 기타 선택 시 내용 입력칸 표시
  form.addEventListener("change", (e) => {
    const t = e.target;
    const group = t.dataset?.toggleOther;
    if (group) {
      const otherChecked = form.querySelector(`[data-toggle-other="${group}"][value="other"]`).checked;
      form.querySelector(`[data-other="${group}"]`).hidden = !otherChecked;
    }
  });

  // 지역: 범위에 따라 시도·시군구 선택 표시, 시도에 맞춰 시군구 목록 갱신
  const sido = form.elements.namedItem("sido");
  const sigungu = form.elements.namedItem("sigungu");
  const regionNote = form.querySelector('[data-note="region"]');

  function level() {
    return form.querySelector('input[name="region_level"]:checked')?.value ?? "";
  }

  function fillSigungu() {
    const found = regions.find((s) => s.code === sido.value);
    const options = found?.sigungu ?? [];
    sigungu.replaceChildren(new Option(found ? (options.length ? "시군구 선택" : "시군구 없음 (시도 단위 선택)") : "시도를 먼저 선택", ""));
    for (const g of options) sigungu.add(new Option(g.name, g.code));
    sigungu.disabled = Boolean(found) && options.length === 0;
  }

  function syncRegion() {
    const lv = level();
    sido.hidden = lv !== "sido" && lv !== "sigungu";
    sigungu.hidden = lv !== "sigungu";
    regionNote.hidden = sido.hidden;
  }

  form.querySelectorAll('input[name="region_level"]').forEach((r) => r.addEventListener("change", syncRegion));
  sido.addEventListener("change", fillSigungu);

  // 예산: 미정이면 금액 입력 비활성화
  const krw = form.elements.namedItem("budget_krw");
  const undecided = form.elements.namedItem("budget_undecided");
  const budgetNote = form.querySelector('[data-note="budget"]');

  function syncBudget() {
    // 금액칸을 잠그지 않는다. 잠그면 입력한 금액이 서버로 가지 않아 조용히 사라진다 (9/18)
    const digits = krw.value.replaceAll(",", "").trim();
    if (undecided.checked && digits !== "")
      budgetNote.textContent = "금액과 [미정] 중 하나만 남겨 주세요. 금액을 쓰려면 [미정] 체크를 풀어 주세요.";
    else if (undecided.checked) budgetNote.textContent = "미정은 0원과 다르게 기록되며 기획안에 ‘추가 확정 필요’로 남습니다.";
    else if (/^\d+$/.test(digits)) budgetNote.textContent = `${Number(digits).toLocaleString("ko-KR")}원`;
    else budgetNote.textContent = "";
  }

  undecided.addEventListener("change", syncBudget);
  krw.addEventListener("input", syncBudget);

  // 지표 용도 안내 문구
  const useNote = form.querySelector('[data-note="indicator_use"]');
  form.querySelectorAll('input[name="indicator_use"]').forEach((r) =>
    r.addEventListener("change", () => {
      useNote.textContent = r.dataset.noteText;
    }),
  );

  // 입력 상태 패널: 입력하는 즉시 다시 센다.
  // 서버 검증(plan/validation.py)을 대신하지 않으며, 저장은 [검토 시작]을 눌러야 된다.
  // 항목 이름과 판단 기준은 validation.py와 같게 유지한다 (다르면 제출 후 숫자가 달라 보인다).
  const summary = {
    required: form.parentElement.querySelector('[data-summary="required"]'),
    count: form.parentElement.querySelector('[data-summary="pending-count"]'),
    list: form.parentElement.querySelector('[data-summary="pending-list"]'),
  };

  const value = (name) => (form.elements.namedItem(name)?.value ?? "").trim();
  const checkedValues = (name) => [...form.querySelectorAll(`input[name="${name}"]:checked`)].map((i) => i.value);
  const dataStatusLabel = () => {
    const select = form.elements.namedItem("data_status");
    return select.value ? select.options[select.selectedIndex].text : "";
  };

  function requiredMissing() {
    const goals = checkedValues("goals");
    const metrics = checkedValues("metrics");
    const lv = level();
    const start = value("period_start");
    const end = value("period_end");
    const digits = value("budget_krw").replaceAll(",", "");
    return [
      !value("name"),
      goals.length === 0 || (goals.includes("other") && !value("goal_other")),
      !value("target"),
      !lv || (lv !== "national" && !sido.value) || (lv === "sigungu" && !sigungu.value),
      !start || !end || end < start,
      metrics.length === 0 || (metrics.includes("other") && !value("metric_other")),
      checkedValues("indicator_use").length === 0,
      !undecided.checked && digits !== "" && !/^\d+$/.test(digits),
      undecided.checked && digits !== "",
    ].filter(Boolean).length;
  }

  function pendingItems() {
    const items = [];
    const digits = value("budget_krw").replaceAll(",", "");
    if (undecided.checked) items.push("예산 (미정)");
    else if (digits === "") items.push("예산 (미입력)");
    if (!value("usage_place")) items.push("쿠폰 사용처");
    const status = form.elements.namedItem("data_status").value;
    if (!status) items.push("자료 확보 상태 (선택 안 함)");
    else if (status !== "secured") items.push(`성과 자료 확보 (${dataStatusLabel()})`);
    return items;
  }

  function touched() {
    return (
      Boolean(value("name") || value("target") || value("usage_place") || value("goal_other") ||
              value("metric_other") || value("fixed_conditions") || value("period_start") || value("period_end") ||
              value("budget_krw") || form.elements.namedItem("data_status").value || level()) ||
      undecided.checked || checkedValues("goals").length > 0 || checkedValues("metrics").length > 0 ||
      checkedValues("indicator_use").length > 0
    );
  }

  function syncSummary() {
    if (!summary.required) return;
    const missing = requiredMissing();
    summary.required.textContent = !touched() ? "입력 전" : missing ? `${missing}개 확인 필요` : "모두 입력됨";
    summary.required.classList.toggle("text-warn", touched() && missing > 0);
    summary.required.classList.toggle("text-ok", !touched() || missing === 0);

    const items = pendingItems();
    summary.count.textContent = `${items.length}개`;
    summary.list.replaceChildren(
      ...items.map((item) => {
        const badge = document.createElement("span");
        badge.className = "badge-warn";
        badge.textContent = item;
        return badge;
      }),
    );
    summary.list.hidden = items.length === 0;
  }

  form.addEventListener("input", syncSummary);
  form.addEventListener("change", syncSummary);
  syncSummary();

  // 잘못된 항목이 있으면 첫 오류로 이동
  form.querySelector(".has-error")?.scrollIntoView({ block: "center" });
})();
