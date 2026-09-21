// AI 참고 의견을 화면이 뜬 뒤에 받아 채운다. 실패해도 검토 질문 화면은 그대로 둔다.
// 받은 문장은 textContent로만 넣는다 (AI 출력을 HTML로 해석하지 않는다).
(function () {
  "use strict";

  var box = document.querySelector("[data-ai-box]");
  if (!box) return;

  var list = box.querySelector("[data-ai-list]");
  var message = box.querySelector("[data-ai-message]");
  var source = box.querySelector("[data-ai-source]");

  function show(text) {
    message.textContent = text;
    message.hidden = false;
  }

  // 어떤 검토 결과에 붙는 의견인지 먼저 보여 주고, 그 아래에 문장을 둔다
  // (전에는 문장 아래에 있어 무엇에 대한 의견인지 다 읽고 나서야 알았다 — 사용자 확인 2026-09-19)
  function addOpinion(opinion) {
    var item = document.createElement("div");
    item.className = "ai-opinion";

    if (opinion.rule_labels && opinion.rule_labels.length) {
      var badges = document.createElement("div");
      badges.className = "badge-row ai-opinion-about";
      opinion.rule_labels.forEach(function (label) {
        var badge = document.createElement("span");
        badge.className = "scope-badge ai-badge";
        badge.textContent = "근거 " + label;
        badges.appendChild(badge);
      });
      item.appendChild(badges);
    }

    var text = document.createElement("p");
    text.className = "ai-opinion-text";
    text.textContent = opinion.text;
    item.appendChild(text);

    list.appendChild(item);
  }

  fetch("/step/3/opinions", { credentials: "same-origin" })
    .then(function (response) {
      if (!response.ok) throw new Error(String(response.status));
      return response.json();
    })
    .then(function (data) {
      // 설정으로 꺼 둔 경우: 영역을 숨긴다. 켜져 있으면 모델 선택 칸을 기다리는 동안에도 쓸 수 있게 처음부터 보인다
      if (data.state === "off") {
        box.hidden = true;
        return;
      }

      if (data.state !== "ok") {
        show("AI 의견을 불러오지 못했습니다.");
        return;
      }
      if (!data.opinions.length) {
        show("이번에는 참고 의견이 없습니다.");
        return;
      }
      data.opinions.forEach(addOpinion);
      message.hidden = true;
      source.textContent = (data.model_label || data.model || "로컬 모델") + " · " + data.created_at;
    })
    .catch(function () {
      show("AI 의견을 불러오지 못했습니다.");
    });
})();
