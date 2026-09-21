// 결과 저장: 저장 위치를 고르는 창을 띄우고, 지원하지 않는 브라우저에서는 내려받기로 대신한다.
// 서버에는 파일을 남기지 않는다 (최종기획서 4-5).
(function () {
  "use strict";

  // 이 화면을 연 뒤 다른 탭에서 기획을 바꾸거나 근거 버전이 달라지면 서버가 409로 문서 생성을 막는다 (6-5a).
  // 그때 오류 문장을 .md 파일로 내려받지 않도록 먼저 문서를 받아 확인한다 (6-5d).
  var RECHECK_MESSAGE = "기획 또는 근거 자료가 바뀌어 보완 선택을 다시 확인해야 합니다. 4단계 보완 선택으로 가서 확인한 뒤 저장해 주세요.";

  function note(message) {
    var box = document.querySelector("[data-save-note]");
    if (!box) return;
    box.textContent = message;
    box.hidden = !message;
  }

  function downloadText(text, filename) {
    var url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 1000);
  }

  async function save(button) {
    var url = button.dataset.url;
    var filename = button.dataset.filename || "보완기획안.md";

    button.disabled = true;
    try {
      var response;
      try {
        response = await fetch(url, { credentials: "same-origin" });
      } catch (error) {
        note("서버에 연결하지 못해 저장하지 못했습니다.");
        return;
      }
      if (response.status === 409) {
        note(RECHECK_MESSAGE);
        return;
      }
      if (!response.ok) {
        note("문서를 받지 못해 저장하지 못했습니다. 화면을 새로 고친 뒤 다시 시도해 주세요.");
        return;
      }
      var text = await response.text();

      if (typeof window.showSaveFilePicker !== "function") {
        downloadText(text, filename);
        note("저장 위치 선택을 지원하지 않는 브라우저라 내려받기 폴더에 저장했습니다.");
        return;
      }

      var handle;
      try {
        handle = await window.showSaveFilePicker({
          suggestedName: filename,
          types: [{ description: "Markdown 문서", accept: { "text/markdown": [".md"] } }],
        });
      } catch (error) {
        note("저장을 취소했습니다.");
        return;
      }

      try {
        var stream = await handle.createWritable();
        await stream.write(text);
        await stream.close();
        note("저장했습니다: " + handle.name);
      } catch (error) {
        downloadText(text, filename);
        note("고른 위치에 쓰지 못해 내려받기 폴더에 저장했습니다.");
      }
    } finally {
      button.disabled = false;
    }
  }

  document.querySelectorAll("[data-save-button]").forEach(function (button) {
    button.addEventListener("click", function () {
      save(button);
    });
  });
})();
