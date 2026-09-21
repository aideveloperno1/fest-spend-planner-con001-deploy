// 사용자가 요청할 때만 AI 참고 의견을 받는다. 받은 문장은 HTML로 해석하지 않는다.
(function () {
  "use strict";

  var box = document.querySelector("[data-ai-box]");
  if (!box) return;

  var list = box.querySelector("[data-ai-list]");
  var message = box.querySelector("[data-ai-message]");
  var source = box.querySelector("[data-ai-source]");
  var button = box.querySelector("[data-ai-generate]");

  function show(text) {
    message.textContent = text;
    message.hidden = false;
  }

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

  function finish() {
    button.disabled = false;
    button.textContent = "AI 의견 생성";
  }

  button.addEventListener("click", function () {
    button.disabled = true;
    button.textContent = "생성 중…";
    list.replaceChildren();
    source.textContent = "";
    show("AI 의견을 생성하고 있습니다…");

    fetch("/step/3/opinions", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Accept": "application/json" }
    })
      .then(function (response) {
        if (!response.ok) throw new Error(String(response.status));
        return response.json();
      })
      .then(function (data) {
        if (data.state === "off") {
          box.hidden = true;
          return;
        }
        if (data.state !== "ok") {
          show("AI 의견을 불러오지 못했습니다. 잠시 뒤 다시 시도해 주세요.");
          return;
        }
        if (!data.opinions.length) {
          show("이번에는 표시할 참고 의견이 없습니다. 다른 모델을 선택해 보세요.");
          return;
        }
        data.opinions.forEach(addOpinion);
        message.hidden = true;
        source.textContent = (data.model_label || data.model || "Google AI") + " · " + data.created_at;
      })
      .catch(function () {
        show("AI 의견을 불러오지 못했습니다. 잠시 뒤 다시 시도해 주세요.");
      })
      .finally(finish);
  });
})();
