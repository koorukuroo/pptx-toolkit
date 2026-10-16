# pptxgenjs 4.x 주의 사항 — 이 툴킷이 직접 재현·검증한 항목

`scripts/lib/*`가 모두 처리하므로 `custom` 훅이나 직접 스크립트를 쓸 때만 신경 쓰면 된다.

## 파일을 손상시키는 것 (PowerPoint가 열지 못하거나 차트를 버림)

- 색은 **6자리 hex, `#` 없이**. `#RRGGBB`나 8자리(알파)는 손상. 투명도는 `fill: { color, transparency: 0~100 }`.
- 누적 막대(`barGrouping: 'stacked'`)의 `dataLabelPosition`은 `ctr | inEnd | inBase`만. `outEnd`는 손상 → `check`의 `chart-dlbl-stacked`.
- 보조축 콤보: `secondaryValAxis`·`secondaryCatAxis`를 쓰면 `valAxes`와 `catAxes`를 **둘 다 2개씩** 선언. 하나만 주면 PowerPoint가 차트를 통째로 버린다 → `check`의 `chart-axis-undeclared` (2D 막대의 세 번째 axId는 정상이므로 허용).
- 그림자 `offset`은 0 이상. 위쪽 그림자는 `angle: 270`.
- 옵션 객체는 호출마다 새로 만든다 (pptxgenjs가 in-place로 EMU 변환해 재사용 시 값이 깨진다).
- `pres.company`와 `defineSlideMaster.title`에 `&`를 넣으면 XML이 깨진다 → `&amp;`로 (build.js가 company는 처리).
- `<p:presentation>` 자식 순서를 손으로 바꾸지 않는다. pptxgenjs는 `sldIdLst` 뒤에 `notesMasterIdLst`를 쓰며 PowerPoint가 연다 (`check`는 이 순서를 허용).

## 조용히 무시되거나 다르게 동작하는 것

- `letterSpacing` 없음 → `charSpacing`.
- `rectRadius`는 `roundRect`에만.
- 그라데이션 채우기 없음 → 이미지 배경으로.
- `addText`에 `placeholder`를 주면 위치·크기는 placeholder가 이기지만 **fontSize는 호출 쪽 값이 적용**된다 (제목 자동 축소에 이용).
- 텍스트 상자는 기본 내부 여백이 있다 → 도형과 정렬할 때 `margin: 0`.
- `bullet: true`에 `•`를 또 쓰면 이중 글머리. 글머리 문자는 `bullet: { code: '25A1' }`(□) 처럼 코드로. 단계는 `indentLevel`.
- 줄 간격: 글머리 문단 간격은 `paraSpaceAfter`로, `lineSpacing`은 전체 줄 간격.
- `addNotes`는 슬라이드당 한 번, 문자열.
- 표 `autoPage: false`로 두고 행 수를 명세에서 제한한다. 자동 페이징은 레이아웃을 무너뜨린다.
- `line: { type: 'none' }`으로 외곽선 제거. 선 옵션을 아예 생략해도 외곽선은 그려지지 않는다.
- 값이 `null`인 데이터 포인트는 `<c:v></c:v>`로 기록되며 PowerPoint·LibreOffice 모두 빈 점으로 처리한다 → 단일 시리즈 강조에 '기타/강조' 두 시리즈 + `barOverlapPct: 100` 기법 사용 (charts.js).
- 표(graphicFrame) id가 다른 도형과 겹치는 경우가 있다(`check` 경고). PowerPoint는 연다.
- 슬라이드 수만큼 존재하지 않는 `slideMasterN` Override가 `[Content_Types].xml`에 남는다(`check` 경고, 무해).

## 한글

- 테마 글꼴의 `ea`(동아시아) 슬롯을 pptxgenjs가 비워 둔다 → `scripts/lib/theme.js`가 작성 후 `latin/ea/cs`를 모두 지정. 직접 스크립트에서도 `applyTheme`를 호출한다.
- 모든 `addText`에 `fontFace`와 `lang: 'ko-KR'`를 명시한다 (프리미티브가 기본 적용).
- 차트 텍스트는 `*FontFace: '+mn-lt'`로 테마 본문 글꼴을 따르게 한다.
- 글자 폭 추정 계수(text.js / inspect.py): 한글 1.0em, 대문자 0.68, 숫자 0.58, 소문자 0.55, 공백 0.3. 줄높이 1.2~1.25em. Paperlogy·Pretendard 기준 ±10%.

## 렌더(LibreOffice) 특성

- macOS 헤드리스 LibreOffice는 시스템 글꼴을 열거하지 못해 한글이 빈 칸으로 나온다 → `core/render.py`가 전용 프로필 `~/.cache/pptx-toolkit/lo-profile/user/fonts/`에 시스템 글꼴 디렉터리를 심링크한다.
- LibreOffice는 PowerPoint보다 제목을 조금 넓게 그린다(1줄이 2줄로 보일 수 있음). 넘침 판단은 보수적으로 맞고, 최종은 `--engine powerpoint`(macOS) 또는 실제 PowerPoint에서 확인.
- 첫 렌더는 프로필 생성으로 몇 초 더 걸린다.
