// Word 문서를 서버에서 받은 뒤 사용자가 고른 위치 또는 내려받기 폴더에 저장한다.
(function () {
  "use strict";

  var DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  var RECHECK_MESSAGE = "기획 또는 근거 자료가 바뀌어 보완 선택을 다시 확인해야 합니다. 4단계 보완 선택으로 가서 확인한 뒤 저장해 주세요.";

  function note(message) {
    var box = document.querySelector("[data-save-note]");
    if (!box) return;
    box.textContent = message;
    box.hidden = !message;
  }

  function downloadBlob(blob, filename) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  async function save(button) {
    var url = button.dataset.url;
    var filename = button.dataset.filename || "보완기획안.docx";
    button.disabled = true;
    try {
      // 파일 선택 창은 클릭 직후 열어 사용자 활성화가 만료되지 않게 한다.
      var handle = null;
      if (typeof window.showSaveFilePicker === "function") {
        try {
          handle = await window.showSaveFilePicker({
            suggestedName: filename,
            types: [{ description: "Word 문서", accept: { [DOCX_TYPE]: [".docx"] } }],
          });
        } catch (error) {
          note("저장을 취소했습니다.");
          return;
        }
      }

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
      var blob = await response.blob();
      if (!handle) {
        downloadBlob(blob, filename);
        note("저장 위치 선택을 지원하지 않는 브라우저라 내려받기 폴더에 저장했습니다.");
        return;
      }
      try {
        var stream = await handle.createWritable();
        await stream.write(blob);
        await stream.close();
        note("저장했습니다: " + handle.name);
      } catch (error) {
        downloadBlob(blob, filename);
        note("고른 위치에 쓰지 못해 내려받기 폴더에 저장했습니다.");
      }
    } finally {
      button.disabled = false;
    }
  }

  document.querySelectorAll("[data-save-button]").forEach(function (button) {
    button.addEventListener("click", function () { save(button); });
  });
})();
