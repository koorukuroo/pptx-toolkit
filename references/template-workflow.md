# 기관 템플릿 워크플로우 (Template Compiler) — 승인 양식이 디자인 선호보다 우선한다

두 가지 경로가 있다.

## A. 기관 파일을 **직접 채우기** (`deck_type: template_fill`) — 양식·마스터·푸터를 그대로 보존

```
1. 분석      pptx.py template 양식.pptx -o template-contract.json
             → 슬라이드 크기, 테마 글꼴·색, 레이아웃별 자리표시자(위치·크기·글자), 안전영역, 파생 토큰
2. 썸네일    pptx.py render 양식.pptx -o 양식.render   → contact.png 로 레이아웃 고르기
3. 구조 편집 pptx.py slides 양식.pptx 작업.pptx --keep 1,3,3,3,5,8
             (1-based 원본 번호의 새 순서; 중복=복제, 누락=삭제. 노트·rels·Content_Types 자동 정리)
             ※ 구조 편집은 내용 편집보다 먼저. 복제본은 차트·미디어 파트를 원본과 공유한다.
4. 목록      pptx.py inventory 작업.pptx [--slide N]
             → 슬라이드별 텍스트 도형 id·이름·박스·글자 크기·현재 문단·수용량(capacity)
5. 교체 맵   map.json 작성:
             {"slides": {"2": {"shapes": {"4": {"paragraphs": [{"text": "…", "bullet": true, "level": 0, "bold": false, "size": 14}]},
                                             "7": {"clear": true}}}}}
             - 템플릿 슬롯 수 > 내용 수 이면 남는 도형은 clear (빈 자리표시 금지)
             - 첫 문단의 pPr/rPr을 템플릿으로 삼아 서식이 유지된다. 줄바꿈은 "\n"
6. 교체      pptx.py replace 작업.pptx 결과.pptx --map map.json
             - 어떤 도형이든 넘침 추정이 0.01in 이상 **악화되면 저장 거부**(.rejected.pptx) → 글자를 줄이거나 size 조정
             - check 자동 실행
7. 게이트    pptx.py qa 결과.pptx --bleed  →  render 로 PNG 확인 (자리표시 잔재 grep: check의 placeholder-text)
```

제약: 표 셀 안 텍스트·차트 데이터 교체는 `replace`가 다루지 않는다. 표는 `unpack` → `ppt/slides/slideN.xml`의 `<a:tbl>`을 직접 고치고 `pack`(자동 check). 차트 데이터는 `ppt/charts/chartN.xml`의 `<c:numCache>`와 `<c:strCache>`를 함께 고치고, 가능하면 내장 xlsx(`ppt/embeddings/`)도 맞춘다.

## B. 기관 **스타일로 새 덱** (`brand_mode: derived`) — 양식의 색·글꼴·여백만 빌려 spec으로 생성

```
1. pptx.py template 양식.pptx --tokens-only   → design_tokens 조각
2. deck-spec.json 의 route.brand_mode = "derived", design_tokens 에 붙여 넣기
   (테마 accent1→primary, dk1→ink, 제목 자리표시자 위치→margin.top, 안전영역→margin)
3. assets.logo 에 승인 로고 파일 (표지에만 배치됨)
4. 평소처럼 build → qa → render
```

기관 지침서에 색상 값·글꼴·여백이 명시돼 있으면 파생값 대신 지침 값을 쓴다.

## 계약(template-contract.json)에서 Director가 읽어야 할 것

| 필드 | 쓰임 |
|---|---|
| `slide_size_in`, `aspect` | 4:3 양식이면 글자량 상한을 20% 줄인다 |
| `layouts[].elements[].placeholder.type / box_in / font_pt` | 어떤 레이아웃에 제목·본문·그림 자리가 몇 개 있는지 → 슬라이드 배정 |
| `safe_area_in` | 본문이 들어갈 영역. 이 밖에 요소를 두지 않는다 |
| `masters[].elements[role=footer|page_number|logo_or_image]` | 고정 요소 — 건드리지 않는다 |
| `themes[].fonts` | 양식 글꼴. 대체 폰트가 필요한지 `fonts` 커맨드로 확인 |
| `derived_tokens` | B 경로용 |

## 원칙

- 기관이 "이 양식으로"라고 했으면 A. 디자인 개선 제안은 별도 덱으로.
- 승인 양식의 강조선·제목 바·로고 위치는 **우리 안티패턴 목록보다 우선**한다. 양식은 바꾸지 않는다.
- 양식 슬라이드의 자리표시 문구("제목을 입력하세요", "Click to add")가 남지 않게 `check`의 `placeholder-text` 경고를 0으로.
- 쪽수를 유지해야 하는 공식 양식은 글자가 넘치면 공백을 지우거나 글자를 줄이지 말고 사용자에게 알린다.
