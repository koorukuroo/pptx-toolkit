# 프로파일별 플레이북 (v0.5 추가 8종)

각 프로파일이 **왜 그렇게 생겼는지**, 어떤 장을 어떤 아키타입으로 짜는지, 전용 필드·토큰은 무엇인지. 공통 규칙(`storyline-rules.md`·`deck-spec-guide.md`)은 그대로 적용된다. 공공 RFP 제안서는 `proposal-rfp-rules.md`.

## 1. `rnd_plan_kr` — 국가 R&D 연구개발계획 발표

평가위원은 **목표 → 단계별 목표 → 연차 계획 → 추진 일정 → 지표 → 수행 역량** 순서로 읽고, 연차마다 산출물과 검증 지표가 있는지 본다.

| 장 | 아키타입 | 비고 |
|---|---|---|
| 표지 | `cover` (light-left) | 과제명 두 줄, 부제에 "무엇을 어디까지" |
| 플랫폼 구조 | `architecture` + `lead` | 범례(`legend`)에 "파란색: 핵심 구현 / 청록: 인계 모델"처럼 색 의미 |
| 최종 목표 | `points` columns 4 | 목표마다 산출물이 떠오르는 헤딩 |
| 단계별 목표 | `phase_columns` × 과제 수 | `band.number`는 과제 번호, 열은 연차. 열마다 항목 3개 내외로 맞춘다 |
| 추진 일정 | `gantt` | 행 = 과제(팔레트 순환), 열 = 연차. 마지막 과업은 `final: true`. `bands`에 공통 기반, `milestones`에 누적 산출물, `effects`에 기대효과 |
| 성능 지표 | `data_table` + `highlight_col` | 연차 열 + "목표 근거" 열. `source_note`에 측정 방법·시점 |
| 수행 역량 | `team` | role·responsibility·proof |
| 결론 | `conclusion` (`intro` + 객체 takeaways + `band`) | 인계 약속 한 문장 |

- 제목은 명사구 한 줄(≤30자), 주장은 `lead`가 맡는다("…합니다"). lint는 lead가 서술어로 끝나면 제목 규칙을 완화한다.
- 단계 색은 `list.step_colors: palette`로 순환(파랑·청록·보라·주황·남색). 한 과제가 한 색을 유지하도록 `gantt.rows` 순서와 `phase_columns` 순서를 맞춘다.
- 쪽번호는 `footer.page_number_style: prefix` — `design_tokens.footer.page_prefix: "C"`처럼 기관 코드가 있으면 넣는다.
- 미래 수치·일정은 `(안)`을 붙인다(`audit estimate-unmarked`).

## 2. `solution_cards_kr` — 기술·솔루션·협력 제안

제목이 주장을 담고(한 줄), `lead`가 차별화 포인트를 한 줄로 받친다. 근거는 **카드**로 나란히, 섹션은 **어두운 사진 구분 장**으로 끊는다.

| 장 | 아키타입 | 비고 |
|---|---|---|
| 표지 | `cover` (image-or-dark) | 사진 + 어두운 스크림, `tagline`에 "기관 · 문서 종류" |
| 개요 | `points` columns 3 + `summary band` | 카드 3장(윗단 파란 띠) + 아래 연한 띠 |
| 구분 | `section_divider` + `image` + `items` + `chips` | 큰 번호(흰색) + 짧은 밑줄 + 제목 + 오른쪽 CONTENTS + 키워드 칩 |
| 원칙·절차 | `process` numbered + `summary dark` | 둥근 번호(`list.numeral_style: circle`), 아래 남색 '핵심 원칙' 띠 |
| 구성 증명 | `code_block` (code-left) | 로그 스키마·설정·API 예시 + 오른쪽 지표 카드 |
| 계층 | `architecture` | 화면·앱·관문·백엔드 4계층 |
| 지표 | `hero_metric` 3 (카드) | delta에 현행 대비 |
| 단계 | `data_table` | 단계·기간·범위·산출물·진입 조건 |
| 맺음 | `conclusion` | takeaways 4 + next_steps |

- 카드는 `card` 토큰이 그린다(윗단 띠·그림자·테두리). `design_tokens.card.accent: "left"`로 왼쪽 띠로 바꿀 수 있다.
- 쪽번호 `02 / 25`는 왼쪽 아래(`footer.page_number_style: fraction`, `page_position: left`), 로고는 `assets.logo`가 있을 때 오른쪽 위(`footer.logo: top-right`).
- 어두운 구분 장의 `items`는 그 섹션에서 다룰 장 제목 3~4개. `chips`는 심사위원이 찾을 키워드.

## 3. `briefing_paper_mono` — 데이터 브리핑

종이색 바탕에 세리프 제목, 모노스페이스 라벨·숫자. **사실을 담담하게** 보고한다. 강조는 형광펜 마커 한 번.

| 장 | 아키타입 | 비고 |
|---|---|---|
| 표지 | `cover` (light-left) | 제목은 "무엇을 바꾼다" 문장 |
| 문제 | `statement` (dark) + `emphasis` | 어두운 장에서는 강조가 주황 글자, 밝은 장에서는 형광펜 |
| 현황 숫자 | `kpi_bento` | note에 집계 출처 |
| 화면 | `screen_walkthrough` | `label`에 "(예시 데이터)" |
| 효과 | `evidence_chart` | 두 막대 비교, `highlight` |
| 구조 | `data_table` | 용어 정의표 |
| 제안 | `statement` + `conclusion` | 30일 시범 같은 작은 다음 단계 |

- `typography.emphasis_style: marker` — `statement.emphasis`·표지 `emphasis` 구절에 `colors.marker` 형광펜이 칠해진다.
- `typography.mono_labels: true` — 킥커·출처·쪽번호가 `fonts.mono`로 찍힌다. 설치돼 있지 않으면 `fallback_body`로 대체되니 `fonts` 명령으로 확인한다.
- 캡처는 많아도 되지만 한 장에 한 캡처. 숫자 슬라이드엔 `source_note` 필수.

## 4. `lecture_story` — 대중 강연

**한 장에 한 생각.** 어두운 문장 장과 종이색 삽화 장을 번갈아 둔다. 글자는 크고 적게(live 본문 20pt).

| 리듬 | 아키타입 | 비고 |
|---|---|---|
| 문장 | `statement` (dark) `emphasis` | 핵심 구절만 주황. `kicker`에 "2부 · 보상" |
| 질문 | `statement` + `label: "Q."` | 빈칸은 `___` |
| 삽화 | `image_focus` image-left/right | 종이색 바탕, 캡션 한 문장 + 포인트 ≤3 |
| 비교 | `points` rows | 질문 3개에 "무엇을 볼지" 한 줄 |
| 마무리 | `statement` + `attribution` | "오늘 가져갈 한 문장" |

- `conclusion`이 없어도 된다(lint `no-conclusion`은 경고). 마지막 `statement`가 결론이다.
- 삽화는 승인 자산만. 스톡 사진·아이콘 나열은 `imagery.avoid`.

## 5. `course_material_kr` — 강의 교안·실습 안내

수십~수백 장이 **같은 틀**을 반복한다: 학습 목표 → 개념 → 실습 → 요약 정리.

| 장 | 아키타입 | 비고 |
|---|---|---|
| 과정 개요 | `agenda` | 차시·주제 |
| 학습 목표 | `points` rows (둥근 번호) | 3~4개 |
| 개념 | `data_table` / `architecture` / `comparison` | 정의표·구조도·비교표 |
| 실습 | `code_block` (code-top + 카드) / `process` | 명령·설정 + 단계 |
| 주의 | `summary` line | 빨강(accent)은 주의 한 곳에만 |
| 요약 정리 | `points` / `conclusion` | 체크리스트 |

- 제목은 연한 띠(`frame.title_band`) 위 한 줄. 본문 14~16pt 고밀도(pre_read 모드 권장).
- 표 머리글 남색, 줄무늬(`table.zebra`). 코드 블록 바탕 `colors.code_background`.

## 6. `expo_neon_dark` — 전시·이벤트 제안

남빛 검정 위 네온. **한 장에 네온 2색 이하**, 번호 원이 단계·구역을 구분한다.

| 장 | 아키타입 | 비고 |
|---|---|---|
| 표지 | `cover` (dark-left) | 현장 사진 + 어두운 스크림 |
| 제안 요지 | `executive_summary` | 답 + 근거 3 |
| 동선 | `process` numbered (팔레트 번호 원) | 4~6단계 |
| 구역 구성 | `points` columns (카드) / `architecture` | 부스 구역·역할 |
| 운영 지표 | `hero_metric` / `kpi_bento` | 체류 시간·처리 인원 |
| 일정·예산 | `roadmap` / `pricing_or_budget` | |
| 맺음 | `conclusion` | 한 문장 약속 |

- 상단 시안 띠는 `frame.top_rule_full`. `list.step_colors: palette`가 번호 원 색을 순환시킨다.
- 밝은 사진·작은 썸네일 금지. 사진은 어두운 스크림 아래 한 장.

## 7. `manifesto_navy` — 철학·비전 선언문

두 줄 **문장 제목**과 작은 번호 킥커(`01 / 섹션`). 장식 없이 글자 위계와 여백으로 말한다.

| 리듬 | 아키타입 | 비고 |
|---|---|---|
| 선언 | `statement` (dark 남색) | 짧은 문장, `emphasis` 시안 |
| 풀이 | `points` columns 2~4 / `executive_summary` | 헤딩은 명사, 설명 두 줄 |
| 대비 | `before_after` / `comparison` | "도구를 배우고 → 목표를 정의하고" |
| 원칙 | `points` rows 번호 | 3~5개 |
| 맺음 | `conclusion` (dark) | "다음 시도를 더 좋게 만드는 순환" |

- 제목은 2줄 허용(`title.max_lines: 2`), 서술어로 끝나는 문장. 리드 문장은 작게(ink_muted).
- 파란 전면 선언 장이 필요하면 그 슬라이드에 `background: dark` + `design_tokens.colors.dark_background`를 주조색으로.

## 8. `company_profile_gold` — 회사소개서

검정 구분 장의 **금빛 큰 번호**가 장을 나누고, 본문은 흰 바탕과 종이색 카드.

| 장 | 아키타입 | 비고 |
|---|---|---|
| 표지 | `cover` (dark-left) | 한 줄 슬로건 + 회사명 |
| 목차 | `agenda` | 01~04 |
| 회사 개요 | `data_table` / `points` | 설립·인원·사업 영역 |
| 연혁 | `process` timeline / `roadmap` | |
| 고객·파트너 | `logo_wall` | 승인 로고만 |
| 제품 | `screen_walkthrough` / `image_focus` | 제품 1개 = 1장 |
| 실적 | `hero_metric` (카드) / `kpi_bento` | 큰 숫자 |
| 맺음 | `conclusion` (dark) | 연락처 |

- 구분 장 번호 색은 `section.numeral_color: accent`(금빛). 상단 금빛 띠는 `frame.top_rule_full` + `top_rule_color: accent`.
- 로고는 `assets.logo` 하나를 오른쪽 위에 자동 배치(`footer.logo: top-right`). 인증·수상은 `logo_wall`이 아니라 `data_table`로(날짜·발급 기관).
