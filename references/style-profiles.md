# 스타일 프로파일과 디자인 토큰

프로파일은 `references/style-profiles.json`에 있고 `scripts/build.js`와 `core/lint.py`가 같은 파일을 읽는다. 프로파일은 **출발점**이며 `deck-spec.design_tokens`로 부분 재정의한다 (deep merge). 특정 기관·회사의 브랜드가 아니다.

## 프로파일 선택

| 프로파일 | 용도 | 글꼴 (제목/본문) | 주조 | 강조 | 배경 |
|---|---|---|---|---|---|
| `government_kr` | 부처·지자체·의회 보고, 공공기관 제안·심의 | Paperlogy / Paperlogy | 정부청색 `003764` | 정부적색 `E4032E` | 흰색, 로마 숫자 칩 |
| `public_policy` | 연구·정책 보고서, pre-read | Paperlogy / Pretendard | `173F5F` | `C65A3A` | 흰색 |
| `consulting_grade` | 임원·이사회·전략·사업계획 | Paperlogy / Pretendard | `0B3558` | `C77B30` | 흰색, 트래커·Exhibit |
| `paperlogy_business` | 제안서·영업·내부 보고·교육 | Paperlogy / Paperlogy | `1E3A5F` | `FF5A3D` | 흰색, 표지는 이미지/어두움 |
| `executive_keynote` | 키노트·강연·비전·제품 공개 | Paperlogy / Paperlogy | `47C8FF` | `FFB13B` | 어두움 `0C1824` |

`pptx.py profiles`로 요약을 본다.

## 토큰 구조

```
canvas    layout(LAYOUT_WIDE 13.333×7.5in) · margin{left,right,top,bottom} · grid_columns · gutter
fonts     display · body · numeral · fallback[] · weights{title,body,emphasis}
type      {live|pre_read|hybrid}: cover_title · section_title · title · subtitle · body · body_min · caption · source · hero_number · kicker · table
colors    background · surface · surface_strong · ink · ink_muted · ink_faint · line · line_faint
          primary · primary_soft · secondary · accent · accent_soft · positive · warning · negative · info
          on_primary · dark_background · on_dark (· light_background · light_ink: 키노트)
ratios    background 0.6 · secondary 0.3 · accent 0.1 · point_max 0.05   (KRDS 60-30-10, 강조 ≤5%)
chart     palette[5] · highlight · muted · positive · negative · gridline · label_pt · direct_labels
geometry  radius(pt) · line_width · shadow(false) · divider
title     style(plain|chip) · chip_numerals(roman) · align · max_lines(2) · kicker(section|tracker|none)
footer    left(organization|document_title|none) · right(page_number|none) · source_above_footer · confidentiality · exhibit_numbers
imagery   treatment · scrim · scrim_transparency · avoid[]
cover     variant(light-left|dark-left|dark-center|image-or-dark) · band_color
list      markers[] (□ ○ - · / • – ·) · numbering[] ("1." "가." … / "01" "02")
```

## 재정의 예

기관 색(파랑 `0F4C81`)과 영문 본문 폰트만 바꾸고 나머지는 정부형 유지:

```json
"design_tokens": { "colors": { "primary": "0F4C81", "primary_soft": "DCE8F3" }, "fonts": { "body": "Pretendard" } }
```

승인 템플릿에서 뽑은 토큰 사용: `pptx.py template 기관양식.pptx --tokens-only` 출력을 `design_tokens`에 붙이고 `brand_mode: "derived"`.

## 글자 크기 (type)

모드별 스케일이 다르다. `body_min`은 자동 맞춤의 하한이며 그 아래로 줄이지 않는다 — 넘치면 build가 경고하고 inspect가 막는다. 내용을 줄이거나 슬라이드를 나눈다.

| 요소 | live | hybrid | pre_read |
|---|---|---|---|
| 제목 | 26~30 | 24~27 | 22~24 |
| 본문 | 17~18 (min 14) | 15~16 (min 12~13) | 14~15 (min 11~12) |
| 출처 | 10 | 9 | 8~9 |
| 핵심 숫자 | 72~84 | 64~72 | 56~64 |

## 팔레트 (배경 변형)

슬라이드 `background: light|dark|surface`. 어두운 배경에서는 `ink→on_dark`, `primary→흰색`, `surface`는 밝게 보정된다 (`frame.palette`). 키노트 프로파일은 기본 dark, `light` 요청 시 밝은 팔레트.

## 새 프로파일 추가

1. `style-profiles.json`에 항목 추가 (모든 토큰 키 필수).
2. lint의 대비 검사(`ink/background ≥ 4.5`, `on_primary/primary ≥ 4.5`, `primary/background ≥ 3`) 통과 확인.
3. 세 아키타입(cover, evidence_chart, conclusion)만 담은 spec으로 빌드·렌더해 확인한 뒤 사용.
