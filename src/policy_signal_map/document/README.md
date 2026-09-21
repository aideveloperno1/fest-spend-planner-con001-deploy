# `document/` — 보완 기획안 문서 만들기

5단계 보완 기획안의 데이터 구조와 Word 문서 생성을 담당한다. 담당자가 입력한 원안과 선택한 보완 방법만 사용하며, 없는 값은 추측하지 않고 `추가 확정 필요`로 남긴다.

| 파일 | 역할 |
|---|---|
| `models.py` | 1~8장, 문장 상태, 변경 기록, 근거, 요청서 데이터 구조 |
| `describe.py` | 기획 입력을 사람이 읽는 문장으로 변환 |
| `builder.py` | 원안에 선택한 보완 문장을 적용하고 변경·근거 기록 조립 |
| `docx.py` | A4 Word 문서 생성. 본문, 변경 전후 대조표, 근거·한계, 조건부 요청서 포함 |
| `filename.py` | `보완기획안_사업명_날짜.docx`와 요청서 파일명 생성 |

`render_docx()`는 편집 가능한 보완 기획안 전체를 만들고, `render_request_docx()`는 정밀 분석 요청서가 있을 때 별도 DOCX를 만든다. 두 함수 모두 `bytes`를 반환하므로 서버에 임시 파일을 남기지 않는다.

출력 순서는 문서 헤더와 요약, 본문 1~8장, 부록 1 변경 전후 대조표, 부록 2 데이터 분석 근거 및 한계, 조건부 부록 3 정밀 분석 요청서다. 변경·추가 문장은 파란 강조선과 변경 번호를 사용하고, 미정 값은 `추가 확정 필요`로 표시한다.

문서 생성은 AI나 웹 계층에 의존하지 않는다. `python-docx`를 사용하며 `web/routes/draft.py`가 결과를 DOCX 응답으로 제공한다.

관련 테스트는 `test_document_describe.py`, `test_document_builder.py`, `test_document_docx.py`, `test_document_filename.py`, `test_draft_routes.py`다.
