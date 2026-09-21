// 4단계 보완 선택: 고른 결정·대안에 따라 입력칸을 보여준다. 검증은 서버가 한다.
(() => {
  const forms = document.querySelectorAll(".choice-form");
  if (!forms.length) return;

  const sync = (form) => {
    const decision = form.querySelector('input[name="decision"]:checked')?.value ?? "";
    const option = form.querySelector('input[name="option_id"]:checked');
    const usesOption = decision === "adopt" || decision === "modify";

    form.querySelectorAll(".option-card").forEach((card) => {
      const input = card.querySelector('input[name="option_id"]');
      card.classList.toggle("option-card-on", usesOption && input.checked);
      card.classList.toggle("option-card-off", !usesOption);
    });

    const modify = form.querySelector('textarea[name="modified_text"]')?.closest(".field");
    if (modify) modify.hidden = decision !== "modify";

    const execution = form.querySelector(".execution-box");
    if (execution) {
      const needed = usesOption && option?.dataset.hasExecution === "1";
      execution.hidden = !needed;
    }
  };

  forms.forEach((form) => {
    sync(form);
    form.addEventListener("change", () => sync(form));
  });

  // 저장에 실패해 다시 그렸으면 오류 자리로 화면을 옮긴다.
  // 맨 위에서 다시 시작하면 "저장을 눌러도 아무 일도 없다"로 보인다 (1단계 input.js와 같은 처리).
  const firstError = document.querySelector(".choice-form .error");
  if (firstError) {
    (firstError.closest(".choice-card") ?? firstError).scrollIntoView({ block: "center" });
  }
})();
