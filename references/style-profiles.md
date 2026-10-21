# 스타일 프로파일과 디자인 토큰

프로파일은 `references/style-profiles.json`에 있고 `scripts/build.js`와 `core/lint.py`가 같은 파일을 읽는다. 프로파일은 **출발점**이며 `deck-spec.design_tokens`로 부분 재정의한다 (deep merge). 특정 기관·회사의 브랜드가 아니다.

## 프로파일 선택 (10종)

| 프로파일 | 용도 | 글꼴 (제목/본문) | 주조 | 강조 | 배경·특징 |
|---|---|---|---|---|---|
| `government_kr` | 부처·지자체·의회 보고, 공공기관 제안·심의 | Paperlogy / Paperlogy | 정부청색 `003764` | 정부적색 `E4032E` | 흰색, 로마 숫자 칩, □ ○ - |
| `public_policy` | 연구·정책 보고서, pre-read | Paperlogy / Pretendard | `173F5F` | `C65A3A` | 흰색, 읽기 밀도 |
| `consulting_grade` | 임원·이사회·전략·사업계획 | Paperlogy / Pretendard | `0B3558` | `C77B30` | 흰색, 트래커·Exhibit |
| `paperlogy_business` | 제안서·영업·내부 보고·교육 | Paperlogy / Paperlogy | `1E3A5F` | `FF5A3D` | 흰색, 표지는 이미지/어두움 |
| `executive_keynote` | 키노트·강연·비전·제품 공개 | Paperlogy / Paperlogy | `47C8FF` | `FFB13B` | 어두움 `0C1824` |
| `editorial_report` | 연차보고·백서·문화기관·에세이형 보고 | Nanum Myeongjo / Pretendard | 먹색 `3C3A36` | 주사 `C8372D` | 종이색 `F4EFE4`, 강조 한 번 |
| `research_dense` | 조사·분석 리포트, 부록 많은 pre_read | Pretendard / Pretendard | `23405F` | `B4532C` | 흰색, 고밀도, 하한 11pt |
| `two_font_consulting` | 자문·법률·금융 임원 보고 | Nanum Myeongjo / Pretendard | `0D2E55` | `A46E00` | consulting_grade 구조 + 명조 제목 |
| `institutional_pitch` | IR·지원사업 심사·신사업 심의 | Paperlogy / Pretendard | `0F2A47` | `B8862B` | 흰색, 트래커, TAM·2×2·큰 숫자 |
| `proposal_rfp_kr` | 나라장터·공공 시스템 구축 제안서, 정성평가 | Paperlogy / Pretendard | 파랑 `1D63C8` (남색 `112B50` 표 머리글) | 청록 `008C9A` | 흰색, 빵부스러기 킥커, 요구→대응→검증→산출물 고정 블록, 요구 ID 태그, 큰 쪽번호 |

`pptx.py profiles`로 요약과 `meta`를 본다. `--match "occasion=투자"`, `--match "density=high,formality>=4"` 로 거를 수 있다.

### meta (라우팅용)

```
mood        분위기 한 줄 (신뢰·절제 / 극적·비전 / 따뜻·정제 …)
occasion    보고·심의 / 읽기용 보고서 / 무대 / 투자·심사 …
formality   1(캐주얼) ~ 5(공식)
density     low | medium | high
best_for[]  avoid_for[]
```

Director 는 브리프의 청중·자리·밀도를 meta 와 맞춰 후보 2~3개를 고르고, `directions` 게이트로 사용자가 확정하게 한다.

## 토큰 구조

```
canvas      layout(LAYOUT_WIDE 13.333×7.5in) · margin{left,right,top,bottom} · grid_columns · gutter
fonts       display · body · numeral · fallback[] · weights{title,body,emphasis}
type        {live|pre_read|hybrid}: cover_title · section_title · title · subtitle · body · body_min · caption · source · hero_number · kicker · table
typography  line_height{title,heading,body,body_long,caption,hero} (절대 em) · tracking_em{display,body,kicker,numeral} · line_length_chars{min,max} · italic_hangul(false)
colors      background · surface · surface_strong · ink · ink_strong(제목·헤딩, 기본 ink) · ink_muted · ink_faint · line · line_faint
            primary · primary_soft · secondary · accent · accent_soft · positive · warning · negative · info
            on_primary · dark_background · on_dark (· light_background · light_ink: 어두운 기본 배경용)
ratios      background 0.6 · secondary 0.3 · accent 0.1 · point_max 0.05   (KRDS 60-30-10, 강조 ≤5%)
chart       palette[5] · highlight · muted · positive · negative · gridline · label_pt · direct_labels
geometry    radius(pt) · line_width · shadow(false) · divider
title       style(plain|chip) · chip_numerals(roman) · align · max_lines(2 | 1: 한 줄 제목) · kicker(section|tracker|breadcrumb|none)
footer      left(organization|document_title|none) · right(page_number|none) · page_number_style(display: 크고 굵은 주조색) · bottom_inset · color · source_above_footer · confidentiality · exhibit_numbers
frame       top_rule · top_rule_accent_w · title_rule · brief · verification · tags · label_w · labels{requirement,response,criteria,deliverables} · footer_rule   (제안서형 고정 블록, references/proposal-rfp-rules.md)
table       header_fill · header_color · first_col_fill · zebra · grid(rows|all)   (색 이름은 colors 키)
imagery     treatment · scrim · scrim_transparency · avoid[]
cover       variant(light-left|dark-left|dark-center|image-or-dark|image-light) · band_color(결론 띠에도 쓰임)
list        markers[] (□ ○ - · / • – · / —) · numbering[] ("1." "가." … / "01" "02")
backgrounds cover · section_divider · statement · default (light|dark|surface) · all (키노트처럼 전부 어두울 때)
```

`typography` 수치의 근거는 `references/typography-cjk.md`.

## 색 도출 (`palette`)

브랜드 색이나 로고 PNG 에서 토큰을 만든다. 채색 → OKLCH 수렴 → 논증 순서이며 결과에 한 문장 근거(`rationale`)가 붙는다.

```bash
python3 scripts/pptx.py palette 0F4C81 E4572E -o tokens.json      # 주조·강조 hex → design_tokens 조각
python3 scripts/pptx.py palette --image logo.png --paper            # PNG 대표색 + 종이색 배경
python3 scripts/pptx.py palette --check deck-spec.json              # 기존 토큰을 규칙으로 검사
```

규칙: 유채색 2~3개는 서로 ΔH ≥ 60° 또는 ΔL ≥ 0.3 · 채도 밴드 배경 ≤ 0.04 / 주조 0.08–0.15 / 강조 0.15–0.22 · 중성 램프 L 0.15/0.35/0.65/0.92/0.98 을 주조 색상으로 아주 약하게 물들임 · 대비 ink/background ≥ 4.5, on_primary/primary ≥ 4.5, primary/background ≥ 3. 먹색 주조(에디토리얼)는 채도 밴드 예외. lint 는 같은 규칙을 info 로 보고한다.

## 재정의 예

기관 색(파랑 `0F4C81`)과 영문 본문 폰트만 바꾸고 나머지는 정부형 유지:

```json
"design_tokens": { "colors": { "primary": "0F4C81", "primary_soft": "DCE8F3" }, "fonts": { "body": "Pretendard" } }
```

승인 템플릿에서 뽑은 토큰 사용: `pptx.py template 기관양식.pptx --tokens-only` 출력을 `design_tokens`에 붙이고 `brand_mode: "derived"`. 양식 자체를 물려받으려면 `inherit` (`references/template-workflow.md` C 경로).

## 글자 크기 (type)

모드별 스케일이 다르다. `body_min`은 자동 맞춤의 하한이며 그 아래로 줄이지 않는다 — 넘치면 build가 경고하고 inspect가 막는다. 내용을 줄이거나 슬라이드를 나눈다.

| 요소 | live | hybrid | pre_read |
|---|---|---|---|
| 제목 | 26~30 | 24~27 | 21~24 |
| 본문 | 17~18 (min 14) | 15~16 (min 12~13) | 13~15 (min 11~12) |
| 출처 | 10 | 9 | 8~9 |
| 핵심 숫자 | 72~84 | 64~72 | 48~64 |

## 팔레트 (배경 변형)

슬라이드 `background: light|dark|surface`. 어두운 배경에서는 `ink→on_dark`, `primary→흰색`, `surface`는 밝게 보정된다 (`frame.palette`). 아키타입별 기본 배경은 `backgrounds` 토큰이 정한다(표지·구분·선언). 8장 이상 덱에 비(非)밝은 배경이 한 장도 없으면 `variety` 가 알려 준다.

## 방향 확정 (`directions`)

전체 빌드 전에 프로파일 2~3개 × (표지 + 요약 + 데이터 장)을 한 장의 비교 시트로 만든다.

```bash
python3 scripts/pptx.py directions deck-spec.json --profiles consulting_grade,two_font_consulting,paperlogy_business -o build/directions
# → build/directions/directions.png (열 = 프로파일), directions.json
python3 scripts/pptx.py directions deck-spec.json --approve two_font_consulting --note "제목이 더 권위 있어 보임" -o build/directions --apply-to-spec
# → direction-approved.md 기록 + spec 의 route.style_profile 갱신
```

## 새 프로파일 추가

1. `style-profiles.json`에 항목 추가 (모든 토큰 키 + `meta` + `typography` + `backgrounds`).
2. `pptx.py palette --check <이름>` 과 lint 대비 검사 통과 확인.
3. `examples/archetype-showcase.spec.json` 의 `style_profile` 만 바꿔 빌드·렌더해 아키타입 전부를 확인한 뒤 사용.
