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
"""

__version__ = "0.2.0"
