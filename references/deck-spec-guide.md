# deck-spec.json 작성 안내 (스키마: `schemas/deck-spec.schema.json`)

Director(스킬)가 쓰는 중간 명세. 내용·논리·시각 의도를 담고, 디자인은 프로파일 토큰이 처리한다.
같은 spec을 `style_profile`만 바꿔 다시 빌드하면 정부형·컨설팅형·키노트형으로 재렌더된다.

```json
{
  "version": "0.2",
  "metadata": {
    "title": "…", "subtitle": "…", "organization": "…", "presenter": "…", "date": "2026. 10.",
    "audience": "누가·직급", "success_condition": "이 자료 후 청중이 이해·결정할 것",
    "delivery_mode": "live | pre_read | hybrid", "duration_minutes": 20,
    "language": "ko-KR", "confidentiality": "대외비", "sticker": "DRAFT"
  },
  "route": { "deck_type": "consulting_executive", "style_profile": "consulting_grade", "brand_mode": "neutral", "communication_mode": "pyramid" },
  "design_tokens": {},
  "assets": { "logo": "path.png", "images": { "site": "assets/photo.jpg" } },
  "evidence": [ { "id": "E1", "claim": "…", "kind": "fact|estimate|interpretation|recommendation|user_provided", "confidence": "high|medium|low", "source": "…", "period": "…" } ],
  "slides": [ { "number": 1, "section": "…", "archetype": "…", "title": "…", "takeaway": "…", "content": { }, "evidence_ids": ["E1"], "source_note": "…", "speaker_notes": "…", "exhibit": 1, "sticker": "…", "background": "light|dark|surface", "appendix": false } ]
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

## 아키타입별 content 요약 (전체는 `slide-archetypes.json`)

- `cover` {subtitle, organization, presenter, date, image, tagline}
- `agenda` {items:[{label, detail}]} (≤7)
- `executive_summary` {answer, points:[{heading, detail}] (3~5), decision}
- `section_divider` {number, subtitle, image}
- `hero_metric` {metrics:[{value, unit, label, delta, trend}] (≤3), context, comparison}
- `evidence_chart` {chart:{type, categories, series:[{name, values, kind?, secondary?}], unit, highlight, value_format, show_values, y_max}, insight, callouts (≤3), layout}
- `comparison` {columns, rows:[{criterion, cells}], winner, verdict}
- `process` {steps:[{title, detail, owner}] (≤6), style: numbered|chevron|timeline}
- `roadmap` {phases:[{name, period, items, milestone}] (≤4), horizon}
- `architecture` {layers:[{name, components:[{name, note}], tone}] (≤5), flows, legend}
- `matrix` {x_axis:{label, low, high}, y_axis, quadrants[4], items:[{label, x, y, emphasis}], implication}
- `case_study` {context, intervention, result, evidence, image, client}
- `recommendation` {recommendation, reasons:[{heading, detail}] (≤4), next_action, owner, timing}
- `points` {points:[{heading, detail, metric}] (≤4), layout: rows|columns}
- `statement` {statement, attribution, image}
- `data_table` {columns, rows, highlight_rows, unit, align}
- `image_focus` {image, caption, points (≤3), layout: image-left|image-right|full-bleed}
- `team` {members:[{role, name, responsibility, proof}] (≤6)}
- `pricing_or_budget` {items:[{label, amount, note}], total, unit, assumptions, exclusions}
- `conclusion` {statement, takeaways (≤3), next_steps:[{label, owner, when}], contact}
- `appendix` {paragraphs, table:{columns, rows}, items}
- `custom` — hooks.js의 `[number]` 핸들러가 그린다 (`examples/proposal-hooks.js`)

## 글자량 가이드

lint가 아키타입·모드별 `max_chars`로 검사한다(한글 글자 수 기준, hybrid는 중간값). 상한을 넘으면 글자 크기를 줄이지 말고 **내용을 줄이거나 슬라이드를 나눈다**. 열 레이아웃(points columns, process, recommendation reasons)은 열마다 글자 수를 비슷하게 맞춰야 바닥이 가지런하다.

## 자산

- 이미지는 PNG/JPEG, spec 파일 기준 상대 경로 또는 절대 경로. 표시 크기 대비 110 DPI 이상 (inspect `image-low-res`).
- 로고는 승인 파일만. 표지에만 자동 배치(`light-left` 변형).
- 이미지가 없으면 회색 자리표시가 그려지고 build 경고가 난다 — 전달 전에 반드시 교체.
