# 한글(CJK) 타이포그래피 규칙 — 토큰과 추정기가 공유하는 수치

렌더러(`scripts/lib/text.js`)와 검사기(`core/inspect.py`)는 같은 알고리즘으로 줄 수를 추정한다. 이 문서는 그 전제와 프로파일 `typography` 토큰의 근거다.

## 1. 글자 폭 — 설치 폰트의 실제 값

- 추정기는 설치된 TTF/OTF/TTC의 `hmtx` 폭을 읽는다 (`core/fontmetrics.py`, `scripts/lib/fontmetrics.js`; 색인은 `~/.cache/pptx-toolkit/font-index.json`). 폰트가 없으면 평균 계수(한글 1.0em, 대문자 0.68, 숫자 0.58, 소문자 0.55, 공백 0.3)로 대체한다.
- 실측 예 (Regular, em 단위): Paperlogy 한글 0.88 · 소문자 0.58, Pretendard 한글 0.86 · 소문자 0.51, Nanum Myeongjo 한글 0.95. "한글 = 1em" 가정은 10% 이상 과대 추정이다.
- `pptx.py fontmetrics Paperlogy Pretendard` 로 환경의 값을 확인한다.

## 2. 줄바꿈 — 어절 단위

- PowerPoint·LibreOffice 모두 한글을 **어절(공백) 단위**로 줄바꿈한다. 글자 단위 추정은 줄 수를 과소평가한다. 추정기는 `\S+` 토큰을 쪼개지 않고, 한 어절이 상자보다 길 때만 글자 단위로 끊는다.
- 폭에 **2% 안전 여유**를 둔다(마지막 글자 한 개가 다음 줄로 떨어지는 사고 방지).
- 한 줄짜리 라벨(킥커·단위·캡션 한 줄)은 `wrap:false`(`singleLine`)로 그려 폭이 조금 모자라도 줄이 늘지 않게 한다.

## 3. 행간 — 절대 em 으로 지정하고 폰트 고유값으로 환산

- PowerPoint 의 `lnSpc spcPct` 는 폰트 고유 행간(hhea ascender−descender+lineGap, 또는 OS/2 win 합)에 곱해진다. Paperlogy 1.18, Pretendard 1.19, Nanum Myeongjo 1.15, Noto Sans KR 계열 ≈ 1.45. 그래서 토큰은 **절대 em**(글자 크기 대비)으로 두고, 렌더러가 `lineSpacingMultiple = 원하는 em ÷ 폰트 고유 em` 으로 환산한다.
- 기본값(`typography.line_height`): 제목 1.2 · 헤딩 1.25 · 본문 1.4 (pre_read 1.45~1.5) · 긴 본문 1.5~1.6 · 캡션 1.3 · 큰 숫자 0.95. 라틴 관행(1.15~1.2)보다 넓어야 한글 획이 숨 쉰다.

## 4. 자간

- `typography.tracking_em`: display −0.01~−0.02 (−0.02 아래로 내리지 않는다 — 한글 자소가 붙는다), 본문 0, 킥커·소제목 +0.06~0.1, 큰 숫자 −0.02~−0.03.
- pptxgenjs 옵션은 `charSpacing`(pt). 렌더러가 em × 글자 크기로 환산한다.

## 5. 기울임 금지

- 한글 글꼴에는 이탤릭이 없다. 합성 기울임은 품질을 떨어뜨린다. 렌더러는 한글 run 의 `italic` 을 제거하고(info), lint 는 `design_tokens.fonts.weights` 의 italic 을 오류로, inspect 는 기존 PPTX 의 한글 기울임을 `hangul-italic` 경고로 잡는다.
- 강조는 굵기(Bold/ExtraBold)·색(`primary`/`accent`)·크기 순서로.

## 6. 한 줄 글자 수와 열 폭

- 한글 본문 한 줄 22~38자. 16pt 본문에서 38자 ≈ 7.6in → 전폭(12in) 한 줄 문단은 피하고 두 열로 나누거나 폭을 60%로 줄인다.
- 제목은 2줄 45자(live) / 52자(hybrid) / 60자(pre_read) 상한(lint `title-too-long`).

## 7. 글꼴 조합

- 한글·라틴 분리 지정: 테마 `latin`·`ea`·`cs` 를 모두 채운다(`theme.js`). 숫자는 `fonts.numeral`(기본 Paperlogy)로 통일해 표·큰 숫자의 폭이 흔들리지 않게 한다.
- 가족은 2개까지(제목·본문). 명조 제목 + 고딕 본문(`editorial_report`, `two_font_consulting`)은 허용, 세 가족 이상은 금지.
- 기본 글꼴은 모두 SIL OFL: Paperlogy, Pretendard, Nanum Myeongjo(명조), Noto Sans/Serif KR. 폰트 파일은 동봉하지 않는다.

## 8. 바닥 안전구역과 하한 환산

- 12pt 초과 본문은 슬라이드 바닥 0.5in 안에 두지 않는다(inspect `bottom-zone`): 발표 UI·투사 마스킹에 가린다. 출처·푸터(≤11pt)는 예외.
- 픽셀 기준 하한을 pt 로 환산할 때: 1920px 폭 기준 24px = 12pt(13.333in 캔버스), 18px = 9pt. 차트 눈금·라벨 ≥ 9pt, 본문 ≥ 모드별 `body_min`.
