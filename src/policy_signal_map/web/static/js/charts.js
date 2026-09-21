// 2단계 근거 차트. 서버가 넘긴 #chart-data만 사용하고 숫자를 다시 계산하지 않는다.
// 같은 수치는 모두 표에 있으므로, Chart.js를 불러오지 못하면 안내만 보여준다.
(() => {
  const dataEl = document.getElementById("chart-data");
  if (!dataEl) return;

  const cards = document.querySelectorAll(".chart-card");
  const fallback = document.querySelector(".chart-fallback");
  if (typeof window.Chart === "undefined") {
    cards.forEach((card) => (card.hidden = true));
    if (fallback) fallback.hidden = false;
    return;
  }

  const data = JSON.parse(dataEl.textContent);
  const BLUE = "#2563EB";
  const LIGHT_BLUE = "#93B8F8";
  const GRID = "rgba(27, 36, 48, 0.08)";
  const won = new Intl.NumberFormat("ko-KR");

  const amountText = (value) => {
    if (value === null) return "자료 없음";
    return data.unit === "억원" ? `${value.toFixed(2)}억원` : `${won.format(value)}원`;
  };

  new window.Chart(document.getElementById("amount-chart"), {
    type: "bar",
    data: {
      labels: data.labels,
      datasets: [{ label: `외국인 결제금액 (${data.unit})`, data: data.foreign_amount, backgroundColor: LIGHT_BLUE, borderRadius: 6 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => amountText(ctx.raw) } } },
      scales: { y: { beginAtZero: true, grid: { color: GRID } }, x: { grid: { display: false } } },
    },
  });

  const series = { all: data.share_all_pct, known: data.share_known_pct };
  const names = { all: "전체 분모 비중", known: "미상 제외 비중" };
  const shareChart = new window.Chart(document.getElementById("share-chart"), {
    type: "line",
    data: {
      labels: data.labels,
      datasets: [
        { label: names.all, data: series.all, borderColor: BLUE, backgroundColor: BLUE, spanGaps: false, tension: 0, pointRadius: 4 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (ctx) => (ctx.raw === null ? "계산 불가" : `${ctx.raw.toFixed(2)}%`) } },
      },
      scales: {
        y: { grid: { color: GRID }, ticks: { callback: (value) => `${Number(value).toFixed(2)}%` } },
        x: { grid: { display: false } },
      },
    },
  });

  const buttons = document.querySelectorAll("button[data-denominator]");
  buttons.forEach((button) =>
    button.addEventListener("click", () => {
      const key = button.dataset.denominator;
      shareChart.data.datasets[0].data = series[key];
      shareChart.data.datasets[0].label = names[key];
      shareChart.update();
      buttons.forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
    }),
  );
})();
