// 근거 칩 → 근거 추적 항목으로 이동하고 잠시 표시한다. 스크립트가 없어도 앵커 이동은 그대로 동작한다.
(function () {
  "use strict";

  function highlight(evidenceId) {
    document.querySelectorAll("[data-trace]").forEach(function (item) {
      item.classList.toggle("trace-on", item.dataset.trace === evidenceId);
    });
  }

  document.querySelectorAll("[data-trace-link]").forEach(function (link) {
    link.addEventListener("click", function () {
      highlight(link.dataset.traceLink);
    });
  });
})();
