# 데이터 시각화 규칙 (`evidence_chart`, `small_multiples`, `data_table`, `hero_metric`, `big_number_stage`, `kpi_bento`)

## 1. 관계(relation)로 차트를 고른다

`chart.relation` 을 적으면 `type` 을 생략해도 렌더러가 유형을 고른다 (`type` 이 있으면 그것이 우선).

| `relation` | 질문 | 기본 유형 | 비고 |
|---|---|---|---|
| `change` | 시간에 따라 어떻게 변했나 | 범주 ≤ 6 · 시리즈 1 → `column`, 그 외 `line` | 선은 `highlight: "시리즈명"`, 범례는 오른쪽(선 끝 가까이) |
| `comparison` | 어느 범주가 큰가 | 범주 ≤ 5 → `column`, 그 외 `bar` | 크기순 정렬, `highlight: index` |
| `composition` | 전체는 어떻게 구성되나 | 시리즈 > 1 → `stacked_column`, 조각 ≤ 5 → `doughnut`, 그 외 `bar` | 100% 구성은 stacked 권장 |
| `ratio` | 비율 하나 | `doughnut` | 조각 ≤ 3이면 `hero_metric`·`big_number_stage` 가 낫다 |
| `magnitude` | 규모 순위 | `bar` | 라벨이 길 때 |
| `correlation` | 두 지표가 같이 움직이나 | `scatter` | 점 ≤ 50 |
| `deviation` | 기준 대비 편차 (음수 포함) | `column` | 음수는 `negative` 색, 0 기준선 표시, 축 숨기지 않음 |
| `distribution` | 분포 | `column` | 구간 라벨 명시 |

그 밖에: 두 지표 동시(`combo`, 보조축 1개만), 증감 분해(워터폴 → `custom` 훅), 두 축 우선순위(`matrix` 아키타입), 같은 지표의 부문별 비교(`small_multiples`).

## 2. 목표선·기준선

`chart.target: { "label": "목표 120", "value": 120 }` → 점선(negative 색)으로 얹는다. 막대·선 차트에서 동작하며 내부적으로 콤보로 변환된다. 목표가 범주마다 다르면 `series` 에 `kind: "line", dashed: true` 로 직접 넣는다.

## 3. 작은 차트 격자 (`small_multiples`)

- 같은 지표를 부문·지역·연도별로 비교할 때 2~6개. `shared_y: true`(기본)로 세로축 최대를 공유해야 비교가 성립한다.
- 각 차트는 값 라벨만, 축 숨김. 단위는 격자 위에 한 번. 차트별 제목은 짧게(부문 이름).
- 격자 전체에 결론 한 문장(`note`)을 붙이고, 슬라이드 제목이 차트들이 공통으로 증명하는 주장을 말한다.

## 4. 메시지 우선

- 차트 제목은 슬라이드 제목(액션 타이틀)이 한다. 차트 안 제목은 끄고 `(단위: )` 라벨만.
- 강조는 한 곳: `highlight`. 나머지는 `chart.muted` 회색. 강조색은 프로파일 `chart.highlight`.
- 직접 라벨(`show_values: true`)이 기본. 범례는 시리즈 2개 이상인 선·콤보에서만 — 선 차트는 오른쪽(`legend_pos: "r"`, 선 끝 가까이), 콤보는 아래.
- 해석은 `insight`(콜아웃 1문장) + `callouts`(≤ 3). 차트 안에 긴 텍스트 박스를 올리지 않는다.
- `layout: chart-left`(기본) / `chart-right` / `chart-full`(해석이 제목에 다 들어갈 때).

## 5. 정직성

- 막대는 0에서 시작 (`y_min` 지정 금지, 선 차트만 예외 가능하고 축 라벨을 보여준다).
- 추정·전망·진행 중 기간은 범주 라벨에 `(추정)`, `(목표)`, `E`로 표시하고 출처에 기준을 적는다.
- 축 자르기·면적 과장·3D 금지. 같은 지표는 덱 전체에서 같은 스케일·단위·소수 자릿수. 중첩 시장(`tam_nested`)은 원이 아니라 사각형(면적 왜곡 방지)이며 산출 방법을 적는다.
- 표본 크기(n), 집계 기준, 기간은 `source_note`에. `audit`가 출처·기간·추정 표기 누락을 잡는다. `audit --spec` 은 명세의 범주·시리즈 이름·값이 차트 XML에 실제로 들어갔는지(`chart-data-missing`)도 확인한다.
- 숫자는 천 단위 구분(`#,##0`), 비율은 소수 1자리까지. 눈금·라벨 글자는 9pt 이상.

## 6. 표 (`data_table`, `comparison`, `pricing_or_budget`)

- 머리글 아래 굵은 선, 행 사이 가는 선, 세로선 없음. 숫자 열은 오른쪽 정렬(자동).
- 본문 슬라이드는 10행 이하. 넘으면 부록으로 나누거나 상위 항목만.
- 합계 행은 `highlight_rows`로 강조하고 실제 합과 일치해야 한다 (`audit` `total-mismatch`).
- 단위는 표 위 `(단위: 억원, 부가세 포함)` 라벨에 한 번.

## 7. 네이티브 유지

- 표준 차트는 모두 pptxgenjs 네이티브(`addChart`) — 사용자가 PowerPoint에서 데이터 편집 가능.
- 네이티브가 없는 형태(생키·네트워크·지도)만 이미지로 넣고, 데이터는 부록 표로 함께 제공.
- 차트 이미지 캡처를 본문에 붙이지 않는다.

## 8. 핵심 숫자 (`hero_metric`, `big_number_stage`, `kpi_bento`)

- 기억시킬 숫자가 하나면 `big_number_stage`(화면 절반), 1~3개면 `hero_metric`, 핵심 하나 + 보조 2~5개면 `kpi_bento`(불균등 격자, 카드 테두리 없음).
- 각 숫자에 라벨(무엇의 값인지)과 분모·기준(`delta`에 "8건 평균", "전체의 62%").
- 증감 방향은 `trend: up|down`으로 색을 준다 (좋은 방향이 up). 색만으로 의미를 전하지 않도록 `delta` 문구에 방향을 쓴다.
- `context` 1~2문장으로 왜 중요한지.
