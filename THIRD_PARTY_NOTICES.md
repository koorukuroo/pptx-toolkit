# Third-Party Notices

pptx-toolkit 자체 코드(core/, scripts/, references/, examples/, tests/)는 MIT (LICENSE 참조).

## 런타임 의존성 (저장소에 동봉하지 않음 — `npm install`로 설치)

- **PptxGenJS** — MIT. `scripts/build.js`가 PPTX 생성에 사용한다. 함께 설치되는 **JSZip**(MIT/GPLv3 dual)은 테마 후처리(`scripts/lib/theme.js`)에 사용한다.

## 선택 의존성 (시스템에 설치된 것을 호출만 함)

- **LibreOffice** — MPL 2.0. `render`·`bleed`의 PDF 변환 엔진.
- **Poppler (`pdftoppm`)** — GPL. PDF → PNG.
- **Microsoft PowerPoint** — macOS에서 `render --engine powerpoint`로 호출. 사용자 보유 라이선스.

## 폰트

폰트 파일을 동봉하지 않는다. Paperlogy(SIL OFL), Pretendard(SIL OFL), Nanum Myeongjo(SIL OFL), Noto Sans/Serif KR(SIL OFL)은 사용자가 설치한다.
`fontmetrics` 는 설치된 폰트 파일의 폭·행간 테이블을 읽기만 하며(캐시에는 파일 경로·가족 이름·굵기만 저장) 글꼴 데이터를 복사·배포하지 않는다.
대한민국정부상징체·HY 계열 등 사용 조건이 제한된 글꼴은 기본 폰트로 지정하지 않는다 (references/government-rules.md).

## 예제 자산

`examples/assets/sample-kiosk.png`와 `docs/samples/*.png`는 이 툴킷으로 생성한 결과물이다 (저작권 문제 없음).
예제 명세의 기관명·수치는 모두 가상이다.
