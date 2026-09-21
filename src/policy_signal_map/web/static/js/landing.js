/* 랜딩 화면의 움직임. 전부 "향상"일 뿐이다.
 *
 * - 이 파일이 실행되지 않아도 모든 글자가 그대로 보인다 (숨김은 .js-on이 붙을 때만 걸린다)
 * - 등장 효과는 화면에 들어올 때마다 재생된다. 위로 올렸다가 다시 내리면 또 보인다
 * - 주소에 ?motion=off를 붙이면 움직임 없이 최종 상태로 보여 준다 (캡처·인쇄용)
 * - 운영체제에서 "동작 줄이기"를 켠 사람에게는 CSS가 움직임을 끈다
 * - 라이브러리를 쓰지 않는다. 화면 진입 감지는 IntersectionObserver 하나로 끝낸다
 */
(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const motionOff = params.get("motion") === "off";

  // 움직임을 끄는 경우에는 .js-on을 붙이지 않는다 → CSS 숨김 규칙이 하나도 걸리지 않아
  // 서버가 그린 그대로(= 최종 상태)가 보인다. 캡처가 빈 화면으로 찍히는 일을 막는다.
  if (motionOff) {
    showEverything();
    bindLadder();
    return;
  }

  document.documentElement.classList.add("js-on");
  document.body.classList.add("js-on");

  bindLadder();
  observeReveals();
  bindFlow();

  // Ribbon lights, card highlights and scaling share a six-second cycle.
  // Pause offscreen and in hidden tabs; respect the reduced-motion preference.
  function bindFlow() {
    const flow = document.querySelector(".lp-flow");
    if (!flow || !("IntersectionObserver" in window)) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let inView = false;
    const update = () => {
      flow.classList.toggle("lp-flow-ready", !reducedMotion.matches);
      flow.classList.toggle("lp-flow-running",
        inView && !document.hidden && !reducedMotion.matches);
    };
    const observer = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      update();
    }, { threshold: 0 });
    observer.observe(flow);
    document.addEventListener("visibilitychange", update);
    reducedMotion.addEventListener("change", update);
    update();
  }

  /* ---------------------------------------------------------------- 등장 */

  function observeReveals() {
    const targets = document.querySelectorAll(".reveal, .lp-hold");
    if (!("IntersectionObserver" in window)) {
      showEverything();
      return;
    }
    // 화면에 들어오면 보이고, 완전히 벗어나면 다시 감춘다.
    // 그래서 위로 올렸다가 다시 내리면 효과가 한 번 더 재생된다 (사용자 확인 2026-09-19).
    // 위아래 여백을 두어, 화면 가장자리에 걸친 요소가 깜박이지 않게 한다.
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          entry.target.classList.toggle("is-shown", entry.isIntersecting);
        }
      },
      { rootMargin: "-6% 0px -12% 0px", threshold: 0 },
    );
    targets.forEach((el) => io.observe(el));
  }

  function showEverything() {
    document
      .querySelectorAll(".reveal, .lp-hold, .lp-ladder-panel")
      .forEach((el) => el.classList.add("is-shown"));
  }

  /* ---------------------------------------------------------------- 지역 사다리 */

  function bindLadder() {
    const root = document.querySelector("[data-ladder]");
    if (!root) return;
    const chips = [...root.querySelectorAll("[data-chip]")];
    const panels = [...root.querySelectorAll("[data-panel]")];
    if (!chips.length) return;

    const select = (key) => {
      chips.forEach((chip) => {
        const on = chip.dataset.chip === key;
        chip.classList.toggle("is-on", on);
        chip.setAttribute("aria-selected", on ? "true" : "false");
      });
      panels.forEach((panel) => panel.classList.toggle("is-on", panel.dataset.panel === key));
    };

    root.addEventListener("click", (event) => {
      const chip = event.target.closest("[data-chip]");
      if (chip) select(chip.dataset.chip);
    });

    // 좌우 화살표로도 옮길 수 있게 한다 (탭 목록의 일반적인 동작)
    root.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      const index = chips.indexOf(document.activeElement);
      if (index < 0) return;
      const next = (index + (event.key === "ArrowRight" ? 1 : chips.length - 1)) % chips.length;
      chips[next].focus();
      select(chips[next].dataset.chip);
      event.preventDefault();
    });
  }
})();
