---
name: pptx-toolkit
description: "전문가 수준의 편집 가능한 PPTX를 설계·생성·편집·검수하는 스킬. 정부·공공기관 보고(정부상징·KRDS 규범), 컨설팅 그레이드 임원 보고(액션 타이틀·전시물), 한국형 제안서·영업자료(페이퍼로지식 숫자·기준선), 키노트. deck-spec.json(내용·논리·시각 의도) → 네이티브 PPTX(pptxgenjs) → 자동 게이트(패키지·기하·픽셀 넘침·숫자 감사) → 렌더 시각 검수. 기존 PPTX·기관 템플릿 채우기(inventory→replace), 슬라이드 복제·재배열, 템플릿 분석도 담당. '.pptx', 'PPT', '발표자료', '보고서 장표', '제안서 슬라이드', '덱' 요청 시 사용."
allowed-tools: Bash(python3 *), Bash(node *), Read, Write, Glob, Grep
---

# pptx-toolkit

PPTX는 ZIP + OOXML이다. 이 스킬은 **Director(내용·논리·디자인 결정)** 와 **Renderer/Gates(파일 생성·검증)** 를 나눈다.
Director는 이 문서와 `references/`를 읽고 `deck-spec.json`을 쓴다. Renderer는 `scripts/build.js`(pptxgenjs), 게이트는 `scripts/pptx.py`(Python 표준 라이브러리)다.
결과물은 항상 **텍스트·표·차트가 PowerPoint 객체인 편집 가능한 PPTX**다. 이미지 슬라이드로 대신하지 않는다.

## 워크플로우 선택

    사용자 요청
     ├─ "새 발표자료/보고서/제안서 만들어줘"     → Phase 0~5 (아래) : new-spec → spec 작성 → lint → build --only → 전체 build → qa → render 검수
     ├─ "이 PPTX 읽어줘/요약해줘"               → extract [--format json]
     ├─ "기존 PPTX/기관 양식에 내용 채워줘"       → template → render(썸네일) → slides(구조) → inventory → replace → qa   (references/template-workflow.md)
     ├─ "슬라이드 순서 바꿔/복제/삭제"           → slides --keep 1,3,3,5
     ├─ "기관 양식 스타일로 새로 만들어줘"         → template --tokens-only → design_tokens에 붙여 brand_mode=derived → Phase 2~5
     ├─ "이 PPT 검수해줘/문제 찾아줘"             → qa deck.pptx [--spec] [--bleed] + render 후 PNG 확인 + references/quality-rubric.md 채점
     ├─ "숫자 맞는지 봐줘"                       → audit deck.pptx | audit deck-spec.json
     ├─ "어떻게 보이는지"                        → render → contact.png·slide-NN.png를 Read로 본다
     ├─ "폰트 되나"                              → fonts Paperlogy Pretendard …
     └─ "XML 직접 고쳐야" (표 셀·차트 데이터)     → unpack → 편집 → pack(자동 check)

## 커맨드

    S="${CLAUDE_SKILL_DIR}/scripts/pptx.py"
    python3 "$S" profiles                                   # 스타일 프로파일 5종 요약
    python3 "$S" archetypes                                 # 아키타입 22종과 content 계약
    python3 "$S" new-spec -o deck-spec.json --profile consulting_grade --deck-type consulting_executive --mode hybrid --title "…"
    python3 "$S" lint deck-spec.json --ghost                # 스키마+내용 규칙 검사, 고스트덱(제목만) 출력
    python3 "$S" build deck-spec.json -o out.pptx [--only 1-3] [--hooks hooks.js]   # lint → node build.js → check → inspect
    python3 "$S" render out.pptx [-o dir] [--engine libreoffice|powerpoint] [--dpi 110]   # PDF→PNG + contact.png
    python3 "$S" qa out.pptx --spec deck-spec.json [--bleed] [-o qa-report.json]   # check+inspect+audit(+lint,+bleed)
    python3 "$S" check out.pptx                             # 패키지 무결성 (PowerPoint 거부 패턴)
    python3 "$S" inspect out.pptx [--min-font 14]           # 경계·겹침·넘침 추정·글자 하한·이미지
    python3 "$S" bleed out.pptx [--engine powerpoint]       # 렌더 픽셀 기준 슬라이드 밖 그림 검출
    python3 "$S" audit out.pptx | deck-spec.json            # 합계·단위·기간·추정 표기·출처
    python3 "$S" extract deck.pptx [--format json]
    python3 "$S" template 양식.pptx -o template-contract.json [--tokens-only]
    python3 "$S" inventory deck.pptx [--slide N]
    python3 "$S" replace in.pptx out.pptx --map map.json [--allow-overflow]
    python3 "$S" slides in.pptx out.pptx --keep 1,3,3,5
    python3 "$S" fonts [family …]
    python3 "$S" unpack deck.pptx dir/   ·   python3 "$S" pack dir/ out.pptx

처음 한 번: `cd "${CLAUDE_SKILL_DIR}" && npm install` (pptxgenjs). 렌더는 LibreOffice + pdftoppm(poppler); macOS에선 `--engine powerpoint`도 가능.

## 제작 단계 (게이트는 건너뛰지 않는다)

**Phase 0 — 브리프.** 청중·직급, 요청하는 결정, 전달 모드(`live`/`pre_read`/`hybrid`), 시간·분량, 기관 자산(로고·양식) 유무, 기밀 표시, 근거 수준을 확인한다. 성공 조건 한 문장: "이 자료를 본 뒤 **[청중]** 은 **[핵심 결론]** 을 이해하고 **[행동]** 을 결정한다". 빠진 것이 결과를 크게 바꾸면 질문하고, 아니면 가정을 적고 진행한다.

**Phase 1 — 라우팅.** `deck_type`, `style_profile`(`profiles` 참고: 정부 `government_kr`, 정책 pre-read `public_policy`, 임원 `consulting_grade`, 제안·영업 `paperlogy_business`, 강연 `executive_keynote`), `brand_mode`(`provided`=기관 양식 직접 채움 / `derived`=양식 토큰 차용 / `neutral`), `communication_mode`(`pyramid`·`briefing`·`narrative`·`instructional`·`showcase`). 읽을 참조: 전 경로 `references/storyline-rules.md`·`deck-spec-guide.md`; 정부·공공 `government-rules.md`; 임원·컨설팅·제안 `consulting-rules.md`; 한국형 제안·영업 `paperlogy-rules.md`; 데이터 슬라이드 `data-visualization.md`; 기관 양식 `template-workflow.md`.

**Phase 2 — 근거표.** `evidence[]`에 주장·종류(fact/estimate/interpretation/recommendation/user_provided)·신뢰도·출처·기간. **수치·출처·사례를 지어내지 않는다.** 사용자 제공 사실과 외부 조사 사실을 구분한다. 없는 숫자는 쓰지 않거나 `(추정)`과 근거를 쓴다.

**Phase 3 — 스토리라인 → deck-spec.** `new-spec`으로 시작. 2번째 슬라이드에 답(`executive_summary`). 본문 제목은 모두 액션 타이틀(결론 문장, 2줄). 슬라이드당 결론 하나·전시물 하나. 아키타입은 `archetypes`에서 고른다 (`points` 남용 금지, 데이터는 `evidence_chart`, 선택은 `comparison`, 순서는 `process`, 시간은 `roadmap`, 구조는 `architecture`). 마지막은 `conclusion`/`recommendation`. 10장 초과면 `agenda`·`section_divider`. 상세는 `appendix`. 통계 슬라이드엔 `source_note` 필수. `lint --ghost`로 제목만 읽어 이야기가 되는지 확인하고 오류 0까지 고친다 (경고는 판단).

**Phase 4 — 샘플 게이트 → 전체 빌드.** `build … --only 1-3`(표지·요약·데이터 1장)을 렌더해 방향·밀도를 본다. 괜찮으면 전체 `build`. build 출력의 `warnings`(텍스트 넘침 추정, 폰트 대체, 이미지 없음)를 모두 처리한다. **넘치면 글자를 줄이지 말고 내용을 줄이거나 슬라이드를 나눈다** (하한 `body_min` 아래로 내려가지 않는다). 스타일 후보가 갈리면 프로파일 2~3개로 `--only 1-3`을 각각 만들어 사용자가 고르게 한다.

**Phase 5 — QA.** `qa out.pptx --spec deck-spec.json --bleed`가 `ok: true`여야 전달한다. 그다음 `render`로 `contact.png`와 **모든** `slide-NN.png`를 Read로 보고 `references/quality-rubric.md`로 채점한다(85점 이상 + 신뢰성·가독성·기술 각 8 이상). 결함은 spec을 고쳐 **재빌드**한다. 생성된 pptx를 손으로 고치지 않는다. 사용자에게는 산출물 경로, 프로파일·모드, 경고 요약, 대체 폰트 여부, 남은 판단 사항(출처 확인 필요 등)을 보고한다.

## 필수 규칙

1. **게이트 통과 전엔 완료를 보고하지 않는다.** `build`(lint·check·inspect)와 `qa`의 `ok`가 true, 렌더 PNG를 실제로 봤을 때만 전달한다. 실패하면 원인과 다음 조치를 말한다.
2. **편집 가능성.** 표준 차트는 네이티브(`chart` 계약), 표는 표, 텍스트는 텍스트. 이미지는 사진·로고·네이티브가 없는 도식(생키·지도)만. 이미지로 만든 슬라이드를 PPTX라고 전달하지 않는다.
3. **근거.** 모든 통계 슬라이드에 출처·기간·단위. 미래·추정치는 `(추정)`·`(목표)`·`(안)`. `audit`의 `total-mismatch`는 오류, 나머지 경고는 사용자에게 보고한다. 존재하지 않는 출처·벤치마크·고객 성과를 만들지 않는다.
4. **디자인은 토큰에서만.** 색·글꼴·크기는 프로파일 토큰과 `design_tokens` 재정의로만 바꾼다. `custom` 훅에서도 `ctx.pal`·`ctx.scale`·`ctx.font`만 쓴다. 특정 컨설팅 펌·기관의 로고·색·템플릿을 흉내 내지 않는다.
5. **기관 승인 양식이 모든 선호보다 우선한다.** `brand_mode: provided`면 양식의 마스터·푸터·강조선·로고를 그대로 두고 inventory→replace로 채운다. 양식 자리표시 문구가 남지 않게 한다(`check`의 `placeholder-text`). 쪽수를 지켜야 하는 양식에서 글자가 넘치면 임의로 줄이지 말고 사용자에게 알린다.
6. **정부 자산.** 정부상징·기관 로고는 사용자가 준 승인 파일만 `assets.logo`로. 다시 그리지 않는다. 정부상징체·HY 계열 글꼴을 제목·본문 폰트로 지정하지 않는다. 정부청색 `003764`·정부적색 `E4032E`는 `government_kr` 토큰에 이미 있다. 빨강은 경고·핵심 하나에만.
7. **모드에 맞는 밀도.** `live`는 글자 적게·크게(본문 ≥ 14pt)와 발표자 노트, `pre_read`는 완결 문장과 상세 허용(본문 ≥ 11~12pt), `hybrid`는 본문은 발표용·부록은 읽기용. 같은 덱에 두 용도를 섞지 않는다.
8. **금지 패턴**(`references/anti-patterns.md`): 토픽 제목, 동일 카드 3개, 문장마다 아이콘, 무지개·3D·그라데이션, 장식 스트라이프, 글자 축소로 넘침 해결, 감사합니다 마무리, 소수 둘째 자리 정밀도 흉내, 썸네일 나열.
9. **편집 커맨드는 원본을 바꾸지 않는다.** `replace`·`slides`는 새 파일을 만들고 check(와 넘침 악화 비교)를 통과했을 때만 결과 파일명을 준다. 실패하면 `.rejected.pptx`만 남으며 사용자에게 전달하지 않는다. 구조 편집(`slides`)을 내용 편집(`replace`)보다 먼저 한다.
10. **렌더는 근사.** LibreOffice 렌더는 줄바꿈·자간이 PowerPoint와 조금 다르다(제목이 더 넓게 보임). 레이아웃 결함·넘침·겹침·대비·위계를 판단하는 용도이며, 최종 확인은 `--engine powerpoint`(macOS) 또는 PowerPoint에서. LibreOffice가 없으면 render·bleed를 건너뛰고 그 사실을 보고한다.
11. **폰트.** 기본 Paperlogy(제목·숫자)/Pretendard 또는 Paperlogy(본문). 미설치면 build가 대체 폰트를 보고한다 — 전달 시 "수신 PC에 Paperlogy가 없으면 Pretendard/맑은 고딕으로 표시됨"을 알린다. 폰트 파일은 동봉·배포하지 않는다.
12. **보고 형식.** 완료 보고에는 ① 파일 경로 ② 프로파일·모드·슬라이드 수 ③ qa 요약(게이트별 ok/경고 수) ④ 남은 경고와 사용자 판단 사항 ⑤ 다음 단계 제안(예: 실제 수치 확인, 로고 파일 요청). 렌더 PNG를 보지 않았다면 그렇게 말한다.

## 구조

    SKILL.md                 이 문서 (라우팅·단계·규칙)
    scripts/pptx.py          CLI (게이트·편집·렌더·템플릿·감사) — Python 3.9+ 표준 라이브러리
    scripts/build.js         deck-spec → pptx (pptxgenjs) ; scripts/lib/{tokens,text,frame,primitives,charts,archetypes,theme}.js
    core/                    package · check · inspect · bleed · render · extract · edit · template · audit · lint · specio · fonts
    references/              style-profiles.json(토큰) · slide-archetypes.json(계약) · *.md 규칙 문서
    schemas/deck-spec.schema.json
    examples/                consulting-kiosk-strategy · gov-ai-platform-briefing · proposal-shipyard-ax(+hooks) — 세 프로파일의 골든 샘플
    tests/                   python3 -m unittest discover -s tests
