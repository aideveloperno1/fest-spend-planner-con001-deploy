// PDF로 저장: 브라우저 인쇄 대화상자를 연다. 사용자가 대상에서 "PDF로 저장"을 고른다.
// 서버에서 PDF를 만들지 않는다 (한글 글꼴·브라우저 설치 부담을 배포에 더하지 않기 위해).
(function () {
  "use strict";

  document.querySelectorAll("[data-print-button]").forEach(function (button) {
    button.addEventListener("click", function () {
      window.print();
    });
  });
})();
