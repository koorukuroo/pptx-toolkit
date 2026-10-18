# 금지 패턴 — "AI가 만든 PPT" 티

렌더러가 구조적으로 막는 것, lint 가 잡는 것, 명세를 쓸 때(Director) 피해야 할 것을 나눈다.

## 렌더러가 막는 것

| 패턴 | 처리 |
|---|---|
| 동일 크기 둥근 카드 3개 벽지 | `points`·`kpi_bento`는 번호·헤어라인·열 분할로만 구성, 카드 배경·테두리 없음 |
| 문장마다 아이콘, 이모지 | 아이콘 프리미티브 없음. 숫자·단어·선으로 위계. 이모지는 lint `emoji-in-text` |
| 무지개 차트, 3D, 그라데이션, 그림자 | 팔레트 5색 + 강조 1색, `shadow:false`, 3D 타입 미지원 |
| 제목 밑 강조선·헤더 바·사이드 스트라이프 | 프레임에 없음. 선은 표 머리글·콜아웃·구분에만 |
| 본문 글자 축소로 넘침 해결 | `body_min` 하한, 넘치면 경고 + inspect 실패 |
| 한글 기울임 | 렌더러가 제거, lint `hangul-italic` 오류, inspect 경고 |
| 차트를 이미지로 | 모든 표준 차트 네이티브 |
| 감사합니다 마무리 | lint 차단, `conclusion` 아키타입 |
| 제목이 '현황/전략/기대효과' | lint `title-topic-label` 차단 |
| 장표마다 다른 글꼴·색 | 토큰 밖 값 없음 (hooks도 ctx.pal만 사용 권장) |
| 출처 없는 통계 | lint `source-missing`, audit `source-missing` |
| 소수 둘째 자리 정밀도 흉내 | lint `fake-precision` |
| 명세에 쓴 글자가 사라짐 | `audit --spec` `text-missing` / `chart-data-missing` |

## lint 가 잡는 'AI 티' (`pptx.py lint`)

| 코드 | 수준 | 뜻 |
|---|---|---|
| `emoji-in-text` | warning | 이모지 — 숫자·단어·선으로 |
| `manual-bullet` | warning | 문자열 앞 `•`, `-`, `□`, `1.` — 렌더러가 글머리를 그리므로 이중 표기 |
| `hype-claim` | warning | 근거(evidence_ids) 없는 "10배 빠른", "99.9%", "획기적", "세계 최초", "무한", "게임 체인저" |
| `page-number-in-text` | info | 본문에 "3/12", "p.3" — 푸터가 처리 |
| `emphasis-overuse` | warning | 한 슬라이드에 강조(emphasis·highlight_rows·bold) 4곳 이상 |
| `sequence-nonsequential` | info | `points` 헤딩이 01/02/03 으로 시작 — 순서면 `process`, 아니면 번호 제거 |
| `notes-length` | info | live/hybrid 발표자 노트 80자 미만·600자 초과 (권장 200~400자: 큐 단어 + 전환 문장) |
| `role-coverage` | warning | `role` 을 쓰는 덱에 hook/proof/takeaway 가 비어 있음 |
| `layout-streak` | warning | 같은 아키타입 3장 연속 |

렌더 후에는 `variety` 가 인접 슬라이드 레이아웃 반복(`layout-repeat`), 한 장만 튀는 색(`palette-drift`), 8장 이상인데 배경 변화 없음(`no-contrast-slide`), 이전에 만든 덱과 똑같은 구성(`looks-like-previous`)을 잡는다.

## 명세를 쓸 때 피할 것

- **한 슬라이드에 결론 둘.** 나눈다.
- **모든 슬라이드를 같은 아키타입으로.** 데이터 → 차트, 선택 → 비교, 순서 → 프로세스, 시간 → 로드맵, 구조 → 아키텍처, 숫자 하나 → 큰 숫자(`big_number_stage`), 부문별 같은 지표 → `small_multiples`, 전후 → `before_after`.
- **존재하지 않는 수치·출처·벤치마크.** 모르면 `(추정)`과 근거를 쓰고, 없으면 쓰지 않는다. evidence `confidence: low`는 본문에 올리지 않는다.
- **배경 설명부터 시작.** 2번째 슬라이드에 답.
- **영문 약어 남발.** 첫 등장에 풀이 (lint info).
- **사진 여러 장 썸네일.** 한 장 크롭 (`image_focus`). 로고는 `logo_wall`(승인 자산만, ≤12).
- **텍스트 벽.** pre_read라도 헤딩+설명 두 층, 문단은 3줄 이내. 한 줄 38자 넘는 전폭 문단은 두 열로.
- **컨설팅 펌·기관 로고·색 모방.** 토큰은 중립. 로고는 승인 자산만.
- **정부 자료에 홍보물 톤**(스톡 사진·과장 수치), 컨설팅 자료에 대시보드 UI 톤(타일·배지·게이지).
- **"대략" 숫자를 정확한 듯 표기.** 반올림 자릿수를 결정 수준에 맞춘다.
- **하나의 덱에 발표용·읽기용 혼재.** 모드를 정하고 부록으로 분리.
- **기본 색 조합의 관성.** 어두운 남색 + 네온, 보라 그라데이션, 왼쪽 색 띠 카드, 이모지 아이콘은 쓰지 않는다. 브랜드 색이 있으면 `palette` 로 도출한다.

## 검수에서 자주 보이는 Soft 결함

- 열 3개 중 한 열만 글이 길어 바닥이 들쭉날쭉 → 글자 수 맞추기
- 제목 둘째 줄에 한두 글자 → 문장 다듬기 (추정기는 어절 단위라 사전에 경고한다)
- 차트 범주 라벨 줄바꿈(괄호가 따로 떨어짐) → 라벨 짧게, 단위는 `(단위:)`로
- 숫자와 단위 분리("4.8" / "억원") → 한 run에 쓰기 (`hero_metric.value` + `unit`)
- 출처 줄이 두 줄로 → 상세는 부록 표로
