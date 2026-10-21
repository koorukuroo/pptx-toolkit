# deck-spec.json 작성 안내 (스키마: `schemas/deck-spec.schema.json`)

Director(스킬)가 쓰는 중간 명세. 내용·논리·시각 의도를 담고, 디자인은 프로파일 토큰이 처리한다.
같은 spec을 `style_profile`만 바꿔 다시 빌드하면 정부형·컨설팅형·키노트형으로 재렌더된다.

```json
{
  "version": "0.3",
  "metadata": {
    "title": "…", "subtitle": "…", "organization": "…", "presenter": "…", "date": "2026. 10.",
    "audience": "누가·직급", "success_condition": "이 자료 후 청중이 이해·결정할 것",
    "delivery_mode": "live | pre_read | hybrid", "duration_minutes": 20,
    "language": "ko-KR", "confidentiality": "대외비", "sticker": "DRAFT",
    "audience_state": { "initial": "지금 청중이 믿는 것", "desired": "자료를 본 뒤 믿고 결정할 것" }
  },
  "route": { "deck_type": "consulting_executive", "style_profile": "consulting_grade", "brand_mode": "neutral", "communication_mode": "pyramid" },
  "design_tokens": {},
  "assets": { "logo": "path.png", "images": { "site": "assets/photo.jpg" } },
  "evidence": [ { "id": "E1", "claim": "…", "kind": "fact|estimate|interpretation|recommendation|user_provided", "confidence": "high|medium|low", "source": "…", "period": "…" } ],
  "slides": [ { "number": 1, "section": "…", "archetype": "…", "role": "hook|context|tension|method|proof|takeaway", "title": "…", "takeaway": "…", "content": { }, "evidence_ids": ["E1"], "source_note": "…", "speaker_notes": "…", "exhibit": 1, "sticker": "…", "background": "light|dark|surface", "appendix": false } ]
}
```

## 슬라이드 공통 필드

| 필드 | 뜻 |
|---|---|
| `number` | 1부터, 유일. 빌드 순서 |
| `section` | 섹션 이름. 등장 순서대로 섹션·트래커·로마 숫자 칩 번호가 매겨진다 |
| `archetype` | `pptx.py archetypes`로 목록·content 계약 확인 |
| `title` | 본문 슬라이드는 액션 타이틀(문장). 표지·구분·부록은 토픽 가능 |
| `takeaway` | 한 문장 요지. speaker_notes가 없으면 노트로 들어간다 |
| `content` | 아키타입별 계약 (`slide-archetypes.json`의 `content`) |
| `evidence_ids` | 근거 참조. 존재해야 함 |
| `source_note` | 출처·기간·단위·가정. 차트·표·숫자 슬라이드 필수 |
| `speaker_notes` | 발표자 노트 (live/hybrid 권장) |
| `exhibit` | 전시물 번호 (consulting, footer.exhibit_numbers) |
| `sticker` | 이 슬라이드만 DRAFT/예시 표시 |
| `background` | 기본값을 덮어쓰기 (예: 강조 슬라이드를 dark로) |
| `appendix` | true면 lint의 본문 규칙 완화 |
| `role` | 서사 역할. 하나라도 쓰면 lint가 hook(왜 지금)·proof(근거)·takeaway(남길 것) 커버리지를 검사한다 (pre_read는 context·proof·takeaway) |
| `brief` | 제목 아래 **요구사항·대응방안** 블록 `{requirement, response}` (제안서형, `references/proposal-rfp-rules.md`) |
| `verification` | 본문 아래 **검증 기준·산출물** 블록 `{criteria, deliverables}` |
| `tags` | 푸터 요구 ID 태그 띠 `{label: "RFP", ids: ["SFR-003"]}` |
| `xref` | 푸터 오른쪽 참조 (`기능 조견표 · 32쪽`) |
| `summary` | 본문 아래 요약 한 줄 `{label, text, style: line|band}` |
| `footer_left` | 이 슬라이드의 왼쪽 푸터 글자 (기본 문서 제목·기관) |

## 아키타입별 content 요약 (전체는 `slide-archetypes.json`)

- `cover` {subtitle, organization, presenter, date, image, tagline, emphasis(제목 강조 구절, image-light), document_title, document_id}
- `agenda` {items:[{label, detail, pages?, numeral?}], layout: list|table, subtitle} (≤7)
- `screen_walkthrough` {image, label, caption, points:[{heading, detail}] (≤5), layout: image-left|image-right|image-top, image_ratio} — 화면 한 장 + 번호 포인트
- `executive_summary` {answer, points:[{heading, detail}] (3~5), decision}
- `section_divider` {number, subtitle, image}
- `hero_metric` {metrics:[{value, unit, label, delta, trend}] (≤3), context, comparison}
- `evidence_chart` {chart:{type?, relation?, categories, series:[{name, values, kind?, secondary?, dashed?}], unit, highlight, target:{label,value}?, value_format, show_values, y_max, legend_pos?}, insight, callouts (≤3), layout} — `relation` 이 있으면 type 생략 가능 (`data-visualization.md`)
- `small_multiples` {charts:[{title, chart}] (2~6), columns?, shared_y (true), y_max?, note?}
- `big_number_stage` {value, unit, label | [label 2줄], delta?, trend?, context, comparison?, note:{heading, text}?, table:{columns, rows}? | points?}
- `kpi_bento` {hero:{value, unit, label, delta, trend}, cells:[…] (2~5), note?}
- `tam_nested` {rings:[{label, value, note}] (3~4, 바깥→안), method?, implication?}
- `before_after` {before:{label, metric?, metric_unit?, metric_label?, points[]}, after:{…}, arrow_label?}
- `logo_wall` {logos:[asset id | {image, label}] (≤12), columns?, caption?}
- `comparison` {columns, rows:[{criterion, cells}], winner, verdict}
- `process` {steps:[{title, detail, owner}] (≤6), style: numbered|chevron|timeline|swimlane, lanes:[{label, detail, steps:[{title, detail}]}] (swimlane ≤3 레인)}
- `roadmap` {phases:[{name, period, items, milestone}] (≤4), horizon}
- `architecture` {layers:[{name, components:[{name, note}], tone}] (≤5), flows, legend}
- `matrix` {x_axis:{label, low, high}, y_axis, quadrants[4], items:[{label, x, y, emphasis}], implication}
- `case_study` {context, intervention, result, evidence, image, client}
- `recommendation` {recommendation, reasons:[{heading, detail}] (≤4), next_action, owner, timing}
- `points` {points:[{heading, detail, metric | kicker}] (≤4), layout: rows|columns, table:{title, columns, rows, emphasis_row}?}
- `statement` {statement, attribution, image}
- `data_table` {columns, rows, highlight_rows, unit, align, lead:{value, label, note}?, highlight_col?, accent_col?, col_widths?, row_h?}
- `image_focus` {image, caption, points (≤3), layout: image-left|image-right|full-bleed}
- `team` {members:[{role, name, responsibility, proof}] (≤6)}
- `pricing_or_budget` {items:[{label, amount, note}], total, unit, assumptions, exclusions}
- `conclusion` {statement | intro, takeaways (≤4; 문자열 또는 {heading, detail, note, link}), next_steps:[{label, owner, when}], contact, band?, logo?}
- `appendix` {paragraphs, table:{columns, rows}, items}
- `custom` — hooks.js의 `[number]` 핸들러가 그린다 (`examples/proposal-hooks.js`)

## 서사 역할 (`role`)과 발표자 노트

- hook(왜 지금 이 이야기인가) → context(배경·현재 상태) → tension(문제·격차) → method(어떻게) → proof(근거) → takeaway(남길 것·결정). `executive_summary` 는 takeaway 를 앞에 두는 예외다.
- `metadata.audience_state` 에 청중의 시작 상태와 목표 상태를 적으면 Director 가 hook·takeaway 문장을 그 간격으로 쓴다.
- `speaker_notes` 는 live/hybrid 에서 200~400자: 첫 문장은 큐(이 장에서 말할 한 가지), 마지막 문장은 다음 장으로의 전환. lint `notes-length` 가 범위를 알려 준다.

## 글자량 가이드

lint가 아키타입·모드별 `max_chars`로 검사한다(한글 글자 수 기준, hybrid는 중간값). 상한을 넘으면 글자 크기를 줄이지 말고 **내용을 줄이거나 슬라이드를 나눈다**. 열 레이아웃(points columns, process, recommendation reasons)은 열마다 글자 수를 비슷하게 맞춰야 바닥이 가지런하다.

## 자산

- 이미지는 PNG/JPEG, spec 파일 기준 상대 경로 또는 절대 경로. 표시 크기 대비 110 DPI 이상 (inspect `image-low-res`).
- 로고는 승인 파일만. 표지에만 자동 배치(`light-left` 변형).
- 이미지가 없으면 회색 자리표시가 그려지고 build 경고가 난다 — 전달 전에 반드시 교체.
