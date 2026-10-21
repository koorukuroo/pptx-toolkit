---
name: pptx-toolkit
description: "전문가 수준의 편집 가능한 PPTX를 설계·생성·편집·검수하는 스킬. 정부·공공기관 보고(정부상징·KRDS 규범), 컨설팅 그레이드 임원 보고(액션 타이틀·전시물), 한국형 제안서·영업자료, 공공 RFP 제안서(요구→대응→검증 고정 블록), 국가 R&D 연구개발계획(단계별 목표·네이티브 간트), 기술·솔루션 제안(카드형·코드 블록), 데이터 브리핑(종이색·모노), 강연 스토리형, 강의 교안, 전시·이벤트 제안, 철학·비전 선언문, 회사소개서, 에디토리얼 백서, 고밀도 리포트, IR 피치, 키노트 — 18개 스타일 프로파일·32개 아키타입. deck-spec.json(내용·논리·시각 의도) → 네이티브 PPTX(pptxgenjs) → 자동 게이트(명세 lint·패키지·기하·픽셀 넘침·숫자 감사·텍스트 손실·변주) → 렌더 시각 검수. 방향 비교 시트(directions), 브랜드 색 팔레트 도출(palette), 기존 PPTX·기관 양식 채우기(inventory→replace)와 양식 상속(inherit), 슬라이드 복제·재배열, 템플릿 분석도 담당. '.pptx', 'PPT', '발표자료', '보고서 장표', '제안서 슬라이드', '덱' 요청 시 사용."
allowed-tools: Bash(python3 *), Bash(node *), Read, Write, Glob, Grep
---

# pptx-toolkit

PPTX는 ZIP + OOXML이다. 이 스킬은 **Director(내용·논리·디자인 결정)** 와 **Renderer/Gates(파일 생성·검증)** 를 나눈다.
Director는 이 문서와 `references/`를 읽고 `deck-spec.json`을 쓴다. Renderer는 `scripts/build.js`(pptxgenjs), 게이트는 `scripts/pptx.py`(Python 표준 라이브러리)다.
결과물은 항상 **텍스트·표·차트가 PowerPoint 객체인 편집 가능한 PPTX**다. 이미지 슬라이드로 대신하지 않는다.

## 워크플로우 선택

    사용자 요청
     ├─ "새 발표자료/보고서/제안서 만들어줘"     → Phase 0~5 (아래) : new-spec → spec 작성 → lint → directions(방향 확정) → 전체 build → qa → render 검수
     ├─ "이 PPTX 읽어줘/요약해줘"               → extract [--format json]
     ├─ "기존 PPTX/기관 양식에 내용 채워줘"       → template → render(썸네일) → slides(구조) → inventory → replace → qa   (references/template-workflow.md A)
     ├─ "슬라이드 순서 바꿔/복제/삭제"           → slides --keep 1,3,3,5
     ├─ "기관 양식 스타일로 새로 만들어줘"         → template --tokens-only → design_tokens에 붙여 brand_mode=derived → Phase 2~5   (B)
     ├─ "기관 양식 틀에 우리 장표를 넣어줘"        → template → canvas·margin 맞춰 build → inherit out.pptx 양식.pptx → qa → render   (C)
     ├─ "우리 브랜드 색으로"                     → palette <hex…> | --image logo.png → design_tokens.colors 에 붙임 (근거 문장 함께 보고)
     ├─ "이 PPT 검수해줘/문제 찾아줘"             → qa deck.pptx [--spec] [--bleed] + render 후 PNG 확인 + references/quality-rubric.md 채점
     ├─ "숫자 맞는지 봐줘"                       → audit deck.pptx | audit deck-spec.json
     ├─ "어떻게 보이는지"                        → render → contact.png·slide-NN.png를 Read로 본다
     ├─ "폰트 되나"                              → fonts Paperlogy Pretendard …
     └─ "XML 직접 고쳐야" (표 셀·차트 데이터)     → unpack → 편집 → pack(자동 check)

## 커맨드

    S="${CLAUDE_SKILL_DIR}/scripts/pptx.py"
    python3 "$S" profiles [--match "occasion=투자,density=high"]   # 스타일 프로파일 18종 요약 + meta 라우팅
    python3 "$S" archetypes                                 # 아키타입 32종과 content 계약
    python3 "$S" new-spec -o deck-spec.json --profile consulting_grade --deck-type consulting_executive --mode hybrid --title "…"
    python3 "$S" lint deck-spec.json --ghost                # 스키마+내용 규칙+AI 티 검사, 고스트덱(제목만) 출력
    python3 "$S" palette 0F4C81 E4572E [-o tokens.json] | --image logo.png [--paper] | --check deck-spec.json   # 색 도출·검사
    python3 "$S" directions deck-spec.json [--profiles a,b,c] -o build/directions        # 방향 비교 시트 (표지·요약·데이터)
    python3 "$S" directions deck-spec.json --approve b --note "사용자 발언" -o build/directions --apply-to-spec
    python3 "$S" build deck-spec.json -o out.pptx [--only 1-3] [--hooks hooks.js]   # lint → node build.js → check → inspect
    python3 "$S" render out.pptx [-o dir] [--engine libreoffice|powerpoint] [--dpi 110]   # 글꼴 프로브 → PDF→PNG + contact.png
    python3 "$S" qa out.pptx --spec deck-spec.json [--bleed] [-o qa-report.json]   # check+inspect+audit(--spec 텍스트 손실 포함)+lint(+bleed)
    python3 "$S" variety out.render/out.pdf --spec deck-spec.json [--record 이름]   # 레이아웃 반복·색 튐·배경 리듬·이전 덱과 유사
    python3 "$S" check out.pptx                             # 패키지 무결성 (PowerPoint 거부 패턴)
    python3 "$S" inspect out.pptx [--min-font 14]           # 경계·겹침·넘침 추정(실제 폰트 폭·어절 줄바꿈)·글자 하한·바닥 안전구역·이미지
    python3 "$S" bleed out.pptx [--engine powerpoint]       # 렌더 픽셀 기준 슬라이드 밖 그림 검출
    python3 "$S" audit out.pptx [--spec deck-spec.json] | deck-spec.json   # 합계·단위·기간·추정 표기·출처 (+ text-missing)
    python3 "$S" probe [--engine powerpoint] [--refresh]    # 이 환경에서 한글이 그려지는 글꼴 확인
    python3 "$S" fontmetrics Paperlogy Pretendard           # 설치 폰트의 실제 글자 폭·행간
    python3 "$S" extract deck.pptx [--format json]
    python3 "$S" template 양식.pptx -o template-contract.json [--tokens-only]
    python3 "$S" inherit out.pptx 양식.pptx -o 결과.pptx [--layout "제목만"] [--cover-layout "표지"] [--footer "문구"]
    python3 "$S" inventory deck.pptx [--slide N]
    python3 "$S" replace in.pptx out.pptx --map map.json [--allow-overflow]
    python3 "$S" slides in.pptx out.pptx --keep 1,3,3,5
    python3 "$S" fonts [family …]
    python3 "$S" unpack deck.pptx dir/   ·   python3 "$S" pack dir/ out.pptx

처음 한 번: `cd "${CLAUDE_SKILL_DIR}" && npm install` (pptxgenjs). 렌더는 LibreOffice + pdftoppm(poppler); macOS에선 `--engine powerpoint`도 가능.

## 제작 단계 (게이트는 건너뛰지 않는다)

**Phase 0 — 브리프.** 청중·직급, 요청하는 결정, 전달 모드(`live`/`pre_read`/`hybrid`), 시간·분량, 기관 자산(로고·양식) 유무, 기밀 표시, 근거 수준을 확인한다. 성공 조건 한 문장: "이 자료를 본 뒤 **[청중]** 은 **[핵심 결론]** 을 이해하고 **[행동]** 을 결정한다". 빠진 것이 결과를 크게 바꾸면 질문하고, 아니면 가정을 적고 진행한다.

**Phase 1 — 라우팅.** `deck_type`, `style_profile`(`profiles --match` 로 meta(mood·occasion·formality·density)와 맞춘다: 정부 `government_kr`, 정책 pre-read `public_policy`, 임원 `consulting_grade`, 자문·금융 `two_font_consulting`, 제안·영업 `paperlogy_business`, 공공 RFP 제안서·정성평가 `proposal_rfp_kr`, 국가 R&D 과제 발표 `rnd_plan_kr`, 기술·솔루션·협력 제안 `solution_cards_kr`, 데이터 브리핑 `briefing_paper_mono`, 대중 강연 `lecture_story`, 강의 교안·실습 안내 `course_material_kr`, 전시·이벤트 제안 `expo_neon_dark`, 철학·비전 선언 `manifesto_navy`, 회사소개서 `company_profile_gold`, IR·심사 `institutional_pitch`, 백서·연차보고 `editorial_report`, 고밀도 조사 리포트 `research_dense`, 무대 키노트 `executive_keynote`), `brand_mode`(`provided`=기관 양식 직접 채움 / `derived`=양식 토큰 차용 / `neutral`), `communication_mode`(`pyramid`·`briefing`·`narrative`·`instructional`·`showcase`). 브랜드 색이 주어지면 `palette` 로 토큰을 도출하고 근거 문장을 함께 보고한다. 읽을 참조: 전 경로 `references/storyline-rules.md`·`deck-spec-guide.md`·`typography-cjk.md`; 정부·공공 `government-rules.md`; 임원·컨설팅·제안 `consulting-rules.md`; 한국형 제안·영업 `paperlogy-rules.md`; 공공 RFP 제안서 `proposal-rfp-rules.md`(요구·대응·검증·태그 블록, 아키타입 조합); R&D 계획·기술 제안·브리핑·강연·교안·전시·선언문·소개서 `profile-playbooks.md`(프로파일별 전용 요소·장 구성); 데이터 슬라이드 `data-visualization.md`; 기관 양식 `template-workflow.md`.

**Phase 2 — 근거표.** `evidence[]`에 주장·종류(fact/estimate/interpretation/recommendation/user_provided)·신뢰도·출처·기간. **수치·출처·사례를 지어내지 않는다.** 사용자 제공 사실과 외부 조사 사실을 구분한다. 없는 숫자는 쓰지 않거나 `(추정)`과 근거를 쓴다.

**Phase 3 — 스토리라인 → deck-spec.** `new-spec`으로 시작. `metadata.audience_state`(시작 상태 → 목표 상태)를 적고 슬라이드마다 `role`(hook·context·tension·method·proof·takeaway)을 단다. 2번째 슬라이드에 답(`executive_summary`). 본문 제목은 모두 액션 타이틀(결론 문장, 2줄). 슬라이드당 결론 하나·전시물 하나. 아키타입은 `archetypes`에서 고른다 (`points` 남용 금지, 데이터는 `evidence_chart`(`relation` 으로 유형 선택, `target` 목표선), 부문별 같은 지표는 `small_multiples`, 숫자 하나는 `big_number_stage`, 핵심+보조 지표는 `kpi_bento`, 전후는 `before_after`, 시장 규모는 `tam_nested`, 선택은 `comparison`, 순서는 `process`(주체별이면 `swimlane`), 화면 증명은 `screen_walkthrough`, 코드·설정은 `code_block`, 단계·연차 목표는 `phase_columns`, 추진 일정표는 `gantt`, 시간은 `roadmap`, 구조는 `architecture`). 마지막은 `conclusion`/`recommendation`. 10장 초과면 `agenda`·`section_divider`. 상세는 `appendix`. 통계 슬라이드엔 `source_note` 필수. 발표자 노트는 200~400자(큐 + 전환). `lint --ghost`로 제목만 읽어 이야기가 되는지 확인하고 오류 0까지 고친다 (경고 중 AI 티 항목 — 이모지·수동 글머리·과장 표현·강조 남발 — 은 고친다).

**Phase 4 — 방향 게이트 → 전체 빌드.** `directions deck-spec.json -o build/directions`로 프로파일 2~3개 × (표지·요약·데이터 장) 비교 시트(`directions.png`)를 만들어 Read 로 보고 사용자에게 열 번호와 함께 보여 준다. 사용자가 고르면 `directions --approve <profile> --note "사용자 발언" --apply-to-spec` 으로 기록한다(이후 톤·색·밀도는 이 기록 없이 바꾸지 않는다). 방향이 이미 정해진 재작업이면 `build --only 1-3` 샘플로 대신한다. 그다음 전체 `build`. build 출력의 `warnings`(텍스트 넘침 추정, 폰트 대체, 이미지 없음)를 모두 처리한다. **넘치면 글자를 줄이지 말고 내용을 줄이거나 슬라이드를 나눈다** (하한 `body_min` 아래로 내려가지 않는다).

**Phase 5 — QA.** `qa out.pptx --spec deck-spec.json --bleed`가 `ok: true`여야 전달한다(`audit --spec` 의 `text-missing`·`chart-data-missing` 은 명세의 글자가 파일에서 빠진 것이므로 반드시 0). `render` 출력의 `font_environment.ok` 가 false 면 그 렌더로 판단하지 않는다(폰트 설치 또는 `--engine powerpoint`). 그다음 `contact.png`와 **모든** `slide-NN.png`를 Read로 보고 `references/quality-rubric.md`로 채점한다(85점 이상 + 신뢰성·가독성·기술 각 8 이상). `variety out.render/*.pdf --spec` 으로 레이아웃 반복·색 튐을 확인하고, 납품 시 `--record 덱이름` 으로 장부에 남긴다. 결함은 spec을 고쳐 **재빌드**한다. 생성된 pptx를 손으로 고치지 않는다. 사용자에게는 산출물 경로, 프로파일·모드, 경고 요약, 대체 폰트 여부, 남은 판단 사항(출처 확인 필요 등)을 보고한다.

## 필수 규칙

1. **게이트 통과 전엔 완료를 보고하지 않는다.** `build`(lint·check·inspect)와 `qa`의 `ok`가 true, 렌더 PNG를 실제로 봤을 때만 전달한다. 실패하면 원인과 다음 조치를 말한다.
2. **편집 가능성.** 표준 차트는 네이티브(`chart` 계약), 표는 표, 텍스트는 텍스트. 이미지는 사진·로고·네이티브가 없는 도식(생키·지도)만. 이미지로 만든 슬라이드를 PPTX라고 전달하지 않는다.
3. **근거.** 모든 통계 슬라이드에 출처·기간·단위. 미래·추정치는 `(추정)`·`(목표)`·`(안)`. `audit`의 `total-mismatch`는 오류, 나머지 경고는 사용자에게 보고한다. 존재하지 않는 출처·벤치마크·고객 성과를 만들지 않는다.
4. **디자인은 토큰에서만.** 색·글꼴·크기는 프로파일 토큰과 `design_tokens` 재정의로만 바꾼다. `custom` 훅에서도 `ctx.pal`·`ctx.scale`·`ctx.font`만 쓴다. 특정 컨설팅 펌·기관의 로고·색·템플릿을 흉내 내지 않는다.
5. **기관 승인 양식이 모든 선호보다 우선한다.** `brand_mode: provided`면 양식의 마스터·푸터·강조선·로고를 그대로 두고 inventory→replace로 채운다. 양식 자리표시 문구가 남지 않게 한다(`check`의 `placeholder-text`). 쪽수를 지켜야 하는 양식에서 글자가 넘치면 임의로 줄이지 말고 사용자에게 알린다.
6. **정부 자산.** 정부상징·기관 로고는 사용자가 준 승인 파일만 `assets.logo`로. 다시 그리지 않는다. 정부상징체·HY 계열 글꼴을 제목·본문 폰트로 지정하지 않는다. 정부청색 `003764`·정부적색 `E4032E`는 `government_kr` 토큰에 이미 있다. 빨강은 경고·핵심 하나에만.
7. **모드에 맞는 밀도.** `live`는 글자 적게·크게(본문 ≥ 14pt)와 발표자 노트, `pre_read`는 완결 문장과 상세 허용(본문 ≥ 11~12pt), `hybrid`는 본문은 발표용·부록은 읽기용. 같은 덱에 두 용도를 섞지 않는다.
8. **금지 패턴**(`references/anti-patterns.md`): 토픽 제목, 동일 카드 3개, 문장마다 아이콘·이모지, 무지개·3D·그라데이션, 장식 스트라이프, 글자 축소로 넘침 해결, 감사합니다 마무리, 소수 둘째 자리 정밀도 흉내, 썸네일 나열, 근거 없는 과장 표현, 수동 글머리 문자, 한글 기울임.
9. **편집 커맨드는 원본을 바꾸지 않는다.** `replace`·`slides`는 새 파일을 만들고 check(와 넘침 악화 비교)를 통과했을 때만 결과 파일명을 준다. 실패하면 `.rejected.pptx`만 남으며 사용자에게 전달하지 않는다. 구조 편집(`slides`)을 내용 편집(`replace`)보다 먼저 한다.
10. **렌더는 근사.** LibreOffice 렌더는 줄바꿈·자간이 PowerPoint와 조금 다르다(제목이 더 넓게 보임). 레이아웃 결함·넘침·겹침·대비·위계를 판단하는 용도이며, 최종 확인은 `--engine powerpoint`(macOS) 또는 PowerPoint에서. LibreOffice가 없으면 render·bleed를 건너뛰고 그 사실을 보고한다.
11. **폰트·타이포.** 기본 Paperlogy(제목·숫자)/Pretendard 또는 Paperlogy(본문), 명조 계열은 Nanum Myeongjo. 미설치면 build가 대체 폰트를 보고한다 — 전달 시 "수신 PC에 Paperlogy가 없으면 Pretendard/맑은 고딕으로 표시됨"을 알린다. 폰트 파일은 동봉·배포하지 않는다. 행간·자간·줄바꿈 수치는 `references/typography-cjk.md`를 따르며(본문 행간 1.4 이상, 한글 기울임 금지, 어절 단위 줄바꿈), 추정기는 설치 폰트의 실제 폭을 쓴다.
12. **보고 형식.** 완료 보고에는 ① 파일 경로 ② 프로파일·모드·슬라이드 수 ③ qa 요약(게이트별 ok/경고 수) ④ 남은 경고와 사용자 판단 사항 ⑤ 다음 단계 제안(예: 실제 수치 확인, 로고 파일 요청). 렌더 PNG를 보지 않았다면 그렇게 말한다.

## 구조

    SKILL.md                 이 문서 (라우팅·단계·규칙)
    scripts/pptx.py          CLI (게이트·편집·렌더·템플릿·감사·팔레트·방향·상속) — Python 3.9+ 표준 라이브러리
    scripts/build.js         deck-spec → pptx (pptxgenjs) ; scripts/lib/{tokens,fontmetrics,text,frame,primitives,charts,archetypes,theme}.js
    core/                    package · check · inspect · fontmetrics · probe · bleed · render · variety · extract · edit · template · inherit · audit · lint · palette · directions · specio · fonts
    references/              style-profiles.json(토큰 18종) · slide-archetypes.json(계약 32종) · *.md 규칙 문서 (typography-cjk.md 포함)
    schemas/deck-spec.schema.json
    examples/                consulting-kiosk-strategy · gov-ai-platform-briefing · proposal-shipyard-ax(+hooks) · archetype-showcase(신규 아키타입·차트 기능) · proposal-rfp · rnd-plan(phase_columns·gantt) · solution-cards(카드·code_block) · briefing-mono · lecture-story — 골든 샘플
    tests/                   python3 -m unittest discover -s tests
