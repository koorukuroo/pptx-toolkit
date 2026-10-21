"""pptx-toolkit core — 순수 Python 표준 라이브러리만 사용한다 (pip 불필요).

모듈:
  package  : PPTX(OPC/ZIP) 읽기·쓰기, 슬라이드 순서, EMU 단위 변환
  extract  : 슬라이드별 텍스트·표·노트 추출 (markdown/json)
  check    : 패키지 무결성·알려진 손상 패턴 검사 (게이트)
  inspect  : 도형 기하 검사 — 경계 이탈, 겹침, 최소 글자 크기, 넘침 추정, 이미지 해상도
  render   : LibreOffice/PowerPoint → PDF → PNG, 콘택트 시트
  fonts    : 설치 폰트 탐지와 대체 폰트 제안
  lint     : deck-spec.json 내용·디자인 규칙 검사 (액션 타이틀, 출처, 글자량, 대비)
  specio   : deck-spec 로드, 프로파일 병합, 경량 스키마 검증
  fontmetrics : 설치 폰트의 실제 글자 폭·행간 (추정기 공통)
  probe    : 렌더 환경에서 한글이 그려지는지 확인 (렌더 신뢰 프로토콜)
  audit    : 숫자·단위·합계 감사 + spec↔pptx 텍스트 손실 검증
  variety  : 렌더 지문으로 단조로움·변주 감사, 납품 장부
  palette  : 브랜드 색·PNG → OKLCH 수렴 팔레트
  directions : 프로파일 2~3개 비교 시트 (방향 게이트)
  inherit  : 생성 덱을 기관 양식 패키지에 이식
"""

__version__ = "0.4.0"
