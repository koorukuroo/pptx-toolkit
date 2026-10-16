# pptx-toolkit

**내용과 논리를 적은 JSON 명세에서, 고객이 다음 날 직접 고칠 수 있는 전문가 수준의 PPTX를 만들고 검증하는 도구 모음이자 Claude 스킬입니다.**
정부·공공기관 보고, 컨설팅 그레이드 임원 보고, 한국형 제안서·영업자료, 키노트를 위한 스타일 프로파일을 내장했습니다.

> Build editable, professional-grade PowerPoint decks from a `deck-spec.json` — Korean government briefings, consulting-style executive decks, proposals and keynotes — with automated quality gates (lint · package · geometry · pixel-bleed · number audit) and render-based visual review. Python stdlib + PptxGenJS. MIT.

| 컨설팅형 (임원 보고, hybrid) | 정부형 (추진계획 보고, pre-read) | 제안형 (영업 제안, live) |
|---|---|---|
| ![consulting](docs/samples/consulting-contact.png) | ![gov](docs/samples/gov-contact.png) | ![proposal](docs/samples/proposal-contact.png) |

<p align="center">
<img src="docs/samples/consulting-02.png" width="49%" alt="executive summary"> <img src="docs/samples/gov-05.png" width="49%" alt="combo chart">
<img src="docs/samples/consulting-09.png" width="49%" alt="2x2 matrix"> <img src="docs/samples/proposal-06.png" width="49%" alt="chevron process">
</p>

위 이미지는 모두 `examples/`의 명세에서 자동 생성한 PPTX를 렌더한 것입니다. 수정 없이 나온 결과물입니다.

---

## 왜 만들었나

AI가 만든 PPT는 두 가지 이유로 실무에 못 씁니다. **편집이 안 되거나**(이미지 슬라이드, 깨진 차트), **예쁜데 틀립니다**(출처 없는 숫자, 합계 불일치, 토픽만 적힌 제목, 장표마다 다른 스타일). pptx-toolkit은 이 둘을 구조로 막습니다.

- **네이티브 PPTX** — 텍스트·표·차트가 PowerPoint 객체입니다. 차트 데이터를 PowerPoint에서 바로 고칠 수 있습니다.
- **내용과 디자인의 분리** — 사람(또는 Claude)은 `deck-spec.json`에 *무엇을 말할지*만 씁니다. 색·글꼴·여백·글자 크기는 **스타일 프로파일 토큰**이, 슬라이드 구성은 **22개 아키타입**(요약·핵심 숫자·근거 차트·비교·프로세스·로드맵·아키텍처·2×2·사례·권고·결론…)이 결정합니다. 같은 명세를 프로파일만 바꿔 정부형·컨설팅형으로 다시 만들 수 있습니다.
- **다섯 겹의 자동 게이트** — 명세 lint(액션 타이틀·글자량·출처·색 대비) → 패키지 검사(PowerPoint가 거부하는 패턴) → 기하 검사(경계 이탈·겹침·넘침·글자 하한·이미지 해상도) → 렌더 픽셀 넘침 검출 → 내용 감사(합계·단위 혼용·기간·추정 표기). 하나라도 실패하면 종료 코드가 0이 아닙니다.
- **한국 실무 규범 내장** — 정부상징 색상·보호공간·상징체 사용 제한, KRDS 60-30-10과 명도 대비 기준, 행정업무운영 편람의 항목 기호(□ ○ -, Ⅰ·Ⅱ 장 번호), 컨설팅 장표 문법(액션 타이틀·Exhibit·출처 줄·트래커), 페이퍼로지식 숫자 중심 타이포그래피. 모두 Paperlogy·Pretendard(SIL OFL) 폰트 체계 위에서 동작합니다.
- **기존 PPTX·기관 양식 편집** — 양식 분석(안전영역·글꼴·색 계약 추출), 슬라이드 복제·삭제·재배열, 텍스트 교체(넘침이 악화되면 저장을 거부), 텍스트 추출.

---

## 빠른 시작

```bash
git clone https://github.com/koorukuroo/pptx-toolkit.git && cd pptx-toolkit
npm install                                   # PptxGenJS 하나만 설치됩니다
python3 scripts/pptx.py profiles              # 동작 확인 (Python 3.9+, 표준 라이브러리만)
```

```bash
# 1) 명세 스캐폴드 → 내용 작성 → 검사 (--ghost: 제목만 모아 읽는 '고스트덱')
python3 scripts/pptx.py new-spec -o deck-spec.json --profile consulting_grade --mode hybrid --title "플랫폼 구축 전략"
python3 scripts/pptx.py lint deck-spec.json --ghost

# 2) 생성 — lint → PptxGenJS → 패키지 검사 → 기하 검사가 한 번에 실행됩니다
python3 scripts/pptx.py build deck-spec.json -o out.pptx          # 먼저 --only 1-3 으로 샘플 3장만 확인해도 됩니다

# 3) 검수 — 자동 게이트 묶음 + 렌더 이미지
python3 scripts/pptx.py qa out.pptx --spec deck-spec.json --bleed -o qa-report.json
python3 scripts/pptx.py render out.pptx                            # out.render/contact.png, slide-NN.png
```

예제 세 종을 바로 만들어 보려면:

```bash
npm run build:examples        # build/consulting.pptx, build/gov.pptx, build/proposal.pptx
npm test                      # 회귀 테스트 12개 (빌드·게이트·편집·렌더)
```

### 선택 의존성

| 용도 | 필요 | 비고 |
|---|---|---|
| `render`, `bleed` (PDF → PNG) | LibreOffice + poppler(`pdftoppm`) | macOS는 `/Applications/LibreOffice.app` 자동 탐지, 다른 경로는 `SOFFICE=` 환경변수. `brew install poppler` |
| 실제 PowerPoint 렌더 | Microsoft PowerPoint (macOS) | `render --engine powerpoint` |
| 한글 글꼴 | Paperlogy, Pretendard, Noto Sans KR 중 하나 이상 | `brew install --cask font-paperlogy`. 없으면 대체 글꼴로 생성하고 경고 |

macOS 헤드리스 LibreOffice가 시스템 글꼴을 찾지 못해 한글이 빈 칸으로 렌더되는 문제는 도구가 전용 프로필(`~/.cache/pptx-toolkit/lo-profile`)에 글꼴 디렉터리를 연결해 자동으로 우회합니다.

### Claude 스킬로 쓰기

```bash
ln -s "$(pwd)" ~/.claude/skills/pptx-toolkit
```

`SKILL.md`가 진입점입니다. Claude는 브리프 → 근거표 → 명세 → 샘플 3장 → 전체 생성 → 게이트 → 렌더 검수 순서로 작업하며, 게이트를 통과하고 렌더 이미지를 직접 본 뒤에만 완료를 보고하도록 규칙이 정해져 있습니다.

---

## 어떻게 동작하나

```
브리프 → 근거표 → deck-spec.json ──lint──▶ build.js (PptxGenJS) ──check · inspect──▶ out.pptx
                      │                      프로파일 토큰 × 아키타입                     │
                      │                                                   qa (bleed · audit) → render → PNG 검수 → 명세 수정 → 재빌드
기관 양식 ──template──▶ template-contract.json ─┬─ 파생 토큰으로 새 덱
                                              └─ slides → inventory → replace → qa   (양식 보존)
```

### deck-spec.json

```json
{
  "metadata": { "title": "AI 아르스 키오스크 플랫폼 구축 전략", "audience": "대표이사 및 제품개발팀장",
                "success_condition": "1차 개발 범위와 6개월 일정을 승인한다", "delivery_mode": "hybrid" },
  "route": { "deck_type": "consulting_executive", "style_profile": "consulting_grade", "brand_mode": "neutral" },
  "evidence": [ { "id": "E2", "claim": "행사당 평균 개발 기간은 6.5주", "kind": "estimate", "confidence": "medium",
                  "source": "프로젝트 타임시트 집계 (8건)", "period": "2025.9–2026.9" } ],
  "slides": [
    { "number": 4, "section": "현황 진단", "archetype": "evidence_chart", "exhibit": 1,
      "title": "플랫폼화 이후 행사당 개발 기간은 6.5주에서 3주 이내로 줄어듭니다",
      "content": { "chart": { "type": "column", "categories": ["2025 하반기", "2026 상반기", "현재", "목표"],
                              "series": [ { "name": "개발 기간(주)", "values": [7.5, 6.5, 6.0, 2.8] } ], "highlight": 3 },
                   "insight": "템플릿으로 시작하면 행사별 작업은 브랜드 교체·문구 조정만 남습니다",
                   "callouts": ["공통 런타임이 결제·인쇄·동의를 흡수", "운영 콘솔에서 문구·브랜딩 교체"] },
      "source_note": "출처: 내부 타임시트 (실적), 목표치는 내부 추정", "evidence_ids": ["E2"] }
  ]
}
```

전체 필드는 `references/deck-spec-guide.md`, 아키타입별 `content` 계약은 `python3 scripts/pptx.py archetypes`로 확인합니다.

### 스타일 프로파일

| 프로파일 | 용도 | 특징 |
|---|---|---|
| `government_kr` | 부처·지자체·의회 보고, 공공기관 제안 | 정부청색 주조, 빨강은 경고에만, 로마 숫자 장 번호 칩, □ ○ - 기호, 흰 배경·넓은 여백 |
| `public_policy` | 연구·정책 보고서, 사전 배포 자료 | 읽기용 밀도, 완결 문장 제목, 출처 철저 |
| `consulting_grade` | 임원·이사회·전략·사업계획 | 액션 타이틀, 전시물 하나·결론 하나, Exhibit 번호, 섹션 트래커, DRAFT 스티커 |
| `paperlogy_business` | 제안서·영업·내부 보고·교육 | 큰 숫자, 간결한 카피, 과감한 이미지 크롭, 이미지·어두운 표지 |
| `executive_keynote` | 키노트·비전·제품 공개 | 어두운 배경, 장당 메시지 하나, 큰 글자 |

토큰(색·글꼴·글자 크기·여백·차트 팔레트·푸터·목록 기호)은 `references/style-profiles.json`에 있고, 명세의 `design_tokens`로 일부만 덮어쓸 수 있습니다. 전달 모드(`live` / `pre_read` / `hybrid`)에 따라 글자 크기와 허용 글자량이 달라집니다.

### 품질 게이트

| 게이트 | 커맨드 | 잡는 것 |
|---|---|---|
| 명세 | `lint` | 토픽 라벨 제목("현황", "전략"), 2줄 초과 제목, 글자량 초과, 출처 누락, 같은 레이아웃 3연속, "감사합니다" 마무리, 토큰 색 대비 < 4.5:1 |
| 패키지 | `check` | XML 손상, 관계·콘텐츠 타입 누락, 차트 축 미선언(차트가 통째로 사라지는 원인), 8자리 색상값, 자리표시 문구 잔재 |
| 기하 | `inspect` | 슬라이드 밖 요소, 텍스트 겹침, 글자량 기반 넘침 추정, 본문 글자 하한, 이미지 110 DPI 미만·비율 왜곡 |
| 픽셀 | `bleed` | 슬라이드를 사방으로 키우고 회색 띠를 깐 뒤 렌더 → 띠가 오염되면 실제로 그려진 넘침 |
| 내용 | `audit` | 표 합계 ≠ 행 합(오류), 억원·백만원 혼용, 부가세 표기 없음, 기간 없는 통계, 추정 표기 없는 미래 연도 수치 |

`qa`가 이들을 묶어 `qa-report.json`을 만듭니다. 그 뒤 `render`한 PNG를 사람이(또는 Claude가) `references/quality-rubric.md`의 100점 루브릭으로 채점합니다. 결함은 생성된 파일을 손으로 고치지 않고 **명세를 고쳐 다시 빌드**합니다.

### 기존 PPTX와 기관 양식

```bash
python3 scripts/pptx.py template 양식.pptx -o template-contract.json   # 크기·글꼴·색·레이아웃·자리표시자·안전영역
python3 scripts/pptx.py slides 양식.pptx 작업.pptx --keep 1,3,3,5       # 1-based 새 순서 (중복=복제, 누락=삭제)
python3 scripts/pptx.py inventory 작업.pptx                             # 슬라이드별 텍스트 도형 id·박스·글자 크기·수용량
python3 scripts/pptx.py replace 작업.pptx 결과.pptx --map map.json      # 서식 유지 교체; 넘침 악화 시 .rejected.pptx
```

기관이 승인한 양식은 이 도구의 디자인 선호보다 우선합니다. 양식의 마스터·푸터·로고는 건드리지 않고 내용만 채웁니다. 절차는 `references/template-workflow.md`.

---

## 커맨드 요약

| 커맨드 | 역할 |
|---|---|
| `profiles` · `archetypes` | 프로파일 5종, 아키타입 22종과 `content` 계약 |
| `new-spec` | 명세 스캐폴드 |
| `lint spec [--ghost]` | 명세 검사, 고스트덱 출력 |
| `build spec -o out.pptx [--only 1-3] [--hooks hooks.js]` | 생성 + check + inspect |
| `check` · `inspect` · `bleed` · `audit` · `qa` | 게이트 (위 표) |
| `render pptx [--engine libreoffice\|powerpoint]` | PDF → `slide-NN.png` + `contact.png` |
| `extract pptx [--format json]` | 제목·본문·표·차트·노트 추출 |
| `template` · `inventory` · `replace` · `slides` | 양식 분석과 기존 덱 편집 |
| `fonts [family …]` | 설치 글꼴 확인과 대체 제안 |
| `unpack` · `pack` | OOXML 직접 편집 (`pack`은 check 자동) |

모든 커맨드는 JSON을 출력하고 실패 시 0이 아닌 종료 코드를 돌려줍니다. 편집 커맨드는 원본을 바꾸지 않고 새 파일을 만들며, 검사를 통과했을 때만 결과 파일명을 돌려줍니다.

### 커스텀 슬라이드

아키타입으로 표현되지 않는 장표는 `archetype: "custom"`으로 두고 `--hooks hooks.js`에서 PptxGenJS API로 직접 그립니다. 훅은 토큰(`ctx.pal`, `ctx.scale`, `ctx.font`)과 공용 프리미티브를 그대로 쓰므로 덱의 일관성이 유지됩니다. 예: `examples/proposal-hooks.js`(간트 차트).

---

## 저장소 구조

```
SKILL.md                      Claude 스킬 진입점 — 라우팅 · 제작 단계 · 필수 규칙
scripts/pptx.py               CLI (Python 3.9+ 표준 라이브러리)
scripts/build.js, scripts/lib 명세 → PPTX 렌더러 (tokens · text · frame · primitives · charts · archetypes · theme)
core/                         package · check · inspect · bleed · render · extract · edit · template · audit · lint · specio · fonts
references/                   style-profiles.json · slide-archetypes.json · 규칙 문서
  storyline-rules.md          전달 모드, 피라미드 구조, 액션 타이틀, 고스트덱
  government-rules.md         정부상징 · KRDS · 행정업무운영 편람 · 관행 목차
  consulting-rules.md         장표 문법 · 밀도 · 전시물 규칙
  paperlogy-rules.md          숫자 · 기준선 · 덩어리 · 트리밍 원칙의 토큰화
  data-visualization.md       차트 선택 · 정직성 · 표 규칙
  anti-patterns.md            "AI가 만든 PPT" 티를 막는 목록
  quality-rubric.md           100점 루브릭과 시각 검수 절차
  template-workflow.md        기관 양식 채우기 · 파생
  deck-spec-guide.md          명세 작성 안내
  pptxgenjs-notes.md          직접 검증한 생성 라이브러리 주의 사항
schemas/deck-spec.schema.json
examples/                     골든 샘플 3종 (+ 커스텀 훅)
docs/samples/                 예제 렌더 이미지
tests/                        python3 -m unittest discover -s tests
```

## 제약과 알아둘 점

- 렌더 검수는 LibreOffice 기준이라 줄바꿈·자간이 PowerPoint와 조금 다를 수 있습니다(제목이 조금 더 넓게 보임). 최종 확인은 PowerPoint에서 하거나 macOS에서 `--engine powerpoint`를 쓰세요.
- `replace`는 텍스트 도형만 다룹니다. 표 셀·차트 데이터는 `unpack`으로 XML을 직접 고친 뒤 `pack`하세요.
- 폰트 파일은 동봉하지 않습니다. 수신 PC에 Paperlogy가 없으면 대체 글꼴로 표시됩니다.
- 정부상징·기관 로고는 사용자가 제공한 승인 파일만 사용하며, 도구가 그리거나 흉내 내지 않습니다. 예제의 기관명·수치는 모두 가상입니다.

## 기여

이슈와 PR을 환영합니다. 새 아키타입은 `references/slide-archetypes.json`(계약)과 `scripts/lib/archetypes.js`(렌더러)를 함께 추가하고, 예제 명세 중 하나에 넣어 `npm test`가 통과하는지 확인해 주세요. 새 프로파일은 `references/style-profiles.md`의 절차를 따릅니다.

## 라이선스

MIT. 의존성 고지는 `THIRD_PARTY_NOTICES.md`.
