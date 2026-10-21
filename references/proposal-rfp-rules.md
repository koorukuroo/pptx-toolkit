# 공공 제안서·정성평가 규칙 (`proposal_rfp_kr`)

나라장터·공공기관 시스템 구축 제안서처럼 **심사위원이 요구사항 ID 를 들고 읽는** 자료의 규칙이다. 설득의 단위는 슬라이드가 아니라 **요구 → 대응 → 검증 → 산출물** 한 세트이며, 프로파일 `proposal_rfp_kr` 은 그 세트를 모든 본문 장에 같은 자리로 고정한다.

## 1. 장표의 다섯 층 (프레임이 그린다)

```
┌ 상단 괘선 (왼쪽 1.35in 주조색)
│ Ⅰ. 사업 이해도 및 추진전략   /   1. 사업 이해도          ← section / kicker (빵부스러기, 주조색)
│ 액션 타이틀 (한 줄, 28~30pt)                                 ← title (max_lines 1)
│ ─────────────────────────────────────────── 제목 괘선
│ ▌요구사항   …해야 합니다.                                   ← brief.requirement (연한 띠, 청록 세로선)
│ ▌대응방안   …합니다.  (굵게)                                 ← brief.response
│
│   본문 (아키타입)                                            ← content
│
│ 요약 줄 / 띠                                                 ← summary {label, text, style}
│ 출처·주석 (회색 10pt)                                        ← source_note
│ ─────────────────────────────────────────── 주조색 괘선
│ 검증 기준   …확인합니다.                                     ← verification.criteria
│ 산출물      … · 관련 요구번호 SFR-003                        ← verification.deliverables (회색)
│ [RFP  SFR-003 · SFR-007]            기능 조견표 · 66쪽   04  ← tags · xref · 쪽번호(큰 주조색)
└
```

명세에서는 슬라이드 공통 필드 `brief`·`verification`·`tags`·`xref`·`summary`·`footer_left` 로 쓴다. 다른 프로파일에서도 이 필드를 쓰면 같은 블록이 그려진다(토큰 색으로).

## 2. 문장 규칙

| 자리 | 형식 | 예 |
|---|---|---|
| `title` | 명사구 한 줄 ≤ 30자. 주장은 대응방안이 맡는다 | 같은 기준으로 공간 비교 |
| `brief.requirement` | 제안요청서 원문 요약, **"~해야 합니다"** 로 끝남. 요구 ID 의 핵심 동사를 살린다 | 날짜·인원·면적·공간으로 검색하고 장소명·금액으로 정렬해야 합니다. |
| `brief.response` | 우리가 하는 일, **"~합니다"** 로 끝나는 한 문장(≤ 55자). lint `response-no-verb` | 동일한 사용 기간에 공간별 면적·수용인원·이용조건·가견적을 나란히 비교하도록 합니다. |
| `verification.criteria` | 검수에서 **무엇을 어떻게 확인**하는지 한 문장 | 검색·정렬 결과와 공간 기준정보를 대조하고 … 확인합니다. |
| `verification.deliverables` | 산출물 이름 + `관련 요구번호 …` | 검색·비교 화면과 시험서 · 관련 요구번호 SFR-003 |
| `tags` | 요구 ID 2~8개, 접두어로 분류(SFR 기능·PER 성능·SIR 보안·GER 일반·PMR 관리·TER 시험·QUR 품질) | {"label":"RFP","ids":["SFR-003","SIR-001"]} |
| `xref` | 조견표 위치 | 기능 조견표 · 32쪽 |
| `summary` | 본문을 한 줄로 닫는 결론 — `line`(라벨 + 굵은 문장) 또는 `band`(띠) | {"label":"전환의 기준","text":"하나의 행사번호 · …"} |

## 3. 아키타입 조합 (심사 흐름 순서)

| 장 | 아키타입 | 내용 |
|---|---|---|
| 표지 | `cover` (`image-light`) | 기관명 \| 공고번호 → 정식 문서명 → 큰 제목(핵심 구절 `emphasis` 주조색) → 청록 대시 + 부제 |
| 목차 | `agenda` `layout: table` | 구분(로마 숫자)·목차·주요 내용·페이지 — 페이지 범위는 실제 쪽수 |
| 사업 이해 | `points` (`kicker` 4열) + `table`(평가항목·배점·쪽) | 과제 / 방식 / 근거 / 효과 |
| 현행·목표 | `data_table` `highlight_col`(TO-BE)·`accent_col`(기대 변화) + `summary` | 주체별 AS-IS / TO-BE |
| 업무 흐름 | `process` `swimlane` (이용자 / 운영자) + `summary band` | 단계 6~8 |
| 기능 증명 | `screen_walkthrough` (`image-left` 화면 + 번호 포인트 3) | 실제 개발 화면·예시 데이터 캡션 |
| 기능 묶음 | `screen_walkthrough` (`image-top` + 4열) + `summary band` | 알림·사이트 운영 등 |
| 일정 | `data_table` `lead`(완료일) | 단계·산출물·진입 조건 |
| 성능·시험 | `big_number_stage` (`3초` + 오른쪽 표 + 왼쪽 `note`) | 요구 수치 하나를 크게 |
| 맺음 | `conclusion` (`intro` + 객체 `takeaways` 4 + `band`) | 선택 근거 4가지 + 약속 한 문장 |
| 별첨 | `appendix` 표 | 요구사항 조견표 (ID·요구사항명·대응 요약·본문 쪽) |

그 밖에 `architecture`(구성도), `roadmap`(일정), `team`(수행조직), `comparison`(대안 비교), `evidence_chart`(수요·실적)는 그대로 쓴다.

## 4. 하지 않는 것

- 요구 ID 없이 "충실히 수행하겠습니다" 류의 대응. 모든 대응은 **검증 방법**과 **산출물**을 가진다.
- 제안요청서 문장을 그대로 복붙한 대응방안. 요구는 원문 요약, 대응은 우리의 설계.
- 존재하지 않는 인증·실적·파트너 등급. `conclusion.logo` 는 승인 자산 1개만.
- 미래 일정·수치에 `(안)`·`(목표)`·`계획안` 표기 누락 (`audit` `estimate-unmarked`).
- 한 장에 요구 ID 10개 이상 태그 — 장을 나눈다.
- 화면 캡처를 여러 장 썸네일로 — `screen_walkthrough` 한 장 + 포인트.

## 5. 검수 추가 항목

- lint: `brief-missing`·`verification-missing`·`tags-missing`(info), `response-no-verb`(warning). 제목 한 줄 상한 30자.
- `audit --spec`: `brief`·`verification`·`summary`·`tags` 글자도 손실 검사 대상이다.
- 렌더 검수에서 볼 것: 검증 블록이 바닥 안전구역(0.5in)에 걸치는 것은 허용(작은 글자), 본문 글자(>12pt)는 안 된다. 쪽번호와 태그 띠가 겹치지 않는지, 조견표 쪽수가 실제와 맞는지.
