# 랜딩 히어로 배경

- 현재 적용 파일: `landing-hero-bare-hand.png` (장갑 제거본, 이전 이미지 캐시와 분리)
- 원본 시안: `프론트_예시/랜딩 페이지 히어로 섹션.png`
- 제작: 내장 image_gen 도구로 시안의 웹 UI를 제거한 배경 생성.
- 제목, 내비게이션, 버튼, 다섯 단계는 `templates/landing.html`의 실제 HTML이며, 배치는 `css/landing-hero.css`에서 관리한다.
- 생성 이미지이므로 원본 문서 그림의 글자 등 세부 묘사는 시안과 차이가 있다.

## 랜딩 서비스 화면

- `screenshot-evidence-region.png`: 랜딩 아래쪽에 보여 주는 2단계 합성 화면. 원본은
  `docs/screenshots/02_evidence_region.png`이며 `scripts/capture_screenshots.py`가 캡처를 마친 뒤 이 파일도 갱신한다.

## 사용한 프롬프트

### 후속 수정: 장갑 제거 (내장 image_gen)

Precise local edit of the supplied website hero background. Remove ONLY the black/blue artist drawing glove, wrist strap and all glove-covered finger portions on the right hand. Replace those covered areas with natural bare skin matching the existing hand and forearm. The entire hand and wrist must be bare with no glove, strap, bracelet or accessory. Preserve exactly the hand's size, location, anatomy, pen grip and pose; keep the pen unchanged. Preserve all other pixels/composition as closely as possible: all documents, their lines and highlights, blue data ribbon and icons, lighting, shadows, pale gray empty background, framing and original aspect ratio. Do not add text or any new objects. Change only the glove to natural bare skin.

### 최초 배경 제작

Use case: precise-object-edit. Edit target: supplied landing page screenshot. Create its clean background plate for a real HTML website. Preserve exact composition, framing and 1338:800 aspect ratio: pale cool gray background, right-hand 3D documents, hand holding pen, blue curling translucent data ribbon, cloud/dashboard icons, desk edge at bottom right. Keep the document text and artwork on the right unchanged. REMOVE all website UI overlays: entire top navigation logo, links and button and horizontal divider; all left-side heading, eyebrow, paragraph, buttons and note; lower section heading; all five glass circles, numbers, labels and connecting blue lines and their shadows. Fill removed areas seamlessly with the same pale gray background surface. Do not move, resize, redraw or recompose the document/hand/data ribbon illustration. Empty left side and empty bottom area for live HTML text and circles. Return only the clean background plate.
