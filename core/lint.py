"""deck-spec.json 내용·디자인 규칙 검사 (빌드 전 게이트 + 고스트덱 출력).

level: error(게이트 차단) / warning(사용자에게 보고) / info
검사 코드:
  spec-invalid            스키마·참조 오류
  title-topic-label       본문 슬라이드 제목이 명사형 토픽 라벨 ('현황', '추진 전략', 'Overview' …)
  title-too-long          제목 글자 수 상한 초과 (live 45자 / pre_read 60자; 2줄 기준)
  title-no-verb           제목에 서술어가 없음 (한국어: ~다/~합니다/~한다/~있다/~된다 … 영어: 동사 추정) — warning
  title-ends-period       제목이 마침표로 끝남 (관행: 마침표 없음) — info
  body-too-long           아키타입·전달모드별 글자량 상한 초과
  items-too-many          아키타입 max_items 초과
  source-missing          차트·표·수치 슬라이드에 source_note 없음
  evidence-low            confidence=low 근거를 본문 슬라이드에 사용 — warning
  layout-streak           같은 아키타입 3장 연속 — warning
  thank-you-ending        마지막 슬라이드가 감사 인사만 — error
  no-conclusion           conclusion/recommendation 아키타입이 없음 — warning
  acronym-unexplained     영문 대문자 약어가 풀이 없이 등장 — info
  fake-precision          소수점 2자리 이상 비율·추정치 표기 — info
  contrast-low            토큰 ink/background, primary/background 대비 < 4.5 — error
  duration-mismatch       발표 시간 대비 슬라이드 수 (1.5~2분/장) — warning
  notes-missing           live/hybrid 인데 speaker_notes 없는 본문 슬라이드 — info
  takeaway-missing        본문 슬라이드에 takeaway 없음 — info
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from .specio import load_archetypes, load_spec, resolve_tokens

TOPIC_LABELS = [
    "현황", "분석", "전략", "기대효과", "기대 효과", "개요", "배경", "추진 배경", "추진배경", "추진 전략", "추진전략", "시스템 구성도", "구성도", "문제점",
    "시장 현황", "시장현황", "추진 계획", "추진계획", "향후 계획", "향후계획", "결론", "요약", "목표", "비전", "일정", "예산", "조직", "팀 소개", "회사 소개",
    "overview", "background", "introduction", "agenda", "summary", "analysis", "strategy", "market overview", "next steps", "conclusion", "roadmap", "architecture", "team", "pricing", "budget", "timeline",
]
VERB_ENDINGS = re.compile(r"(다|요|함|됨|임|음|됩니다|합니다|입니다|있습니다|없습니다|합니다\.|한다|된다|있다|없다|이다|하자|필요|가능|중)\s*[.!?]?$")
NON_CONTENT = {"cover", "section_divider", "agenda", "appendix", "statement", "custom"}
NUMERIC_ARCHETYPES = {"evidence_chart", "data_table", "hero_metric", "pricing_or_budget"}
THANKS = re.compile(r"^(감사합니다|고맙습니다|thank you|thanks|q\s*&\s*a|questions\??|끝)\W*$", re.IGNORECASE)
ACRONYM = re.compile(r"\b[A-Z]{2,6}\b")
COMMON_ACRONYMS = {"AI", "IT", "KPI", "ROI", "PPT", "PDF", "API", "SDK", "UI", "UX", "CEO", "CTO", "R&D", "IoT", "LLM", "GPT", "SaaS", "B2B", "B2C", "OK", "QR", "URL", "TV", "USB", "CPU", "GPU", "ESG", "SNS", "POC", "PoC", "MVP", "TF", "M&A", "KR", "US", "EU", "UN", "OECD", "GDP", "CAGR", "YoY", "QoQ", "FY", "MOU", "RFP", "KRW", "USD"}
FAKE_PRECISION = re.compile(r"\d+\.\d{2,}\s*%")


def _chars(s: Any) -> int:
    if s is None:
        return 0
    if isinstance(s, str):
        return len(s)
    if isinstance(s, dict):
        return sum(_chars(v) for v in s.values())
    if isinstance(s, (list, tuple)):
        return sum(_chars(v) for v in s)
    return len(str(s))


def _hex_to_rgb(h: str):
    h = h.strip().lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _lum(rgb) -> float:
    def ch(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = _lum(_hex_to_rgb(a)), _lum(_hex_to_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _count_items(content: Dict[str, Any]) -> int:
    for key in ("points", "steps", "phases", "layers", "members", "items", "rows", "metrics", "reasons", "columns"):
        v = content.get(key)
        if isinstance(v, list):
            return len(v)
    return 0


def lint_spec(spec: Dict[str, Any], schema_errors: List[str]) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []

    def add(code: str, level: str, msg: str, slide: Any = None, **kw) -> None:
        d = {"code": code, "level": level, "message": msg}
        if slide is not None:
            d["slide"] = slide
        d.update(kw)
        findings.append(d)

    for e in schema_errors:
        add("spec-invalid", "error", e)
    if schema_errors:
        return {"ok": False, "findings": findings, "ghost_deck": []}

    archetypes = load_archetypes()
    mode = spec["metadata"]["delivery_mode"]
    mode_key = "live" if mode == "live" else ("pre_read" if mode == "pre_read" else "live")
    slides = spec["slides"]
    evidence = {e["id"]: e for e in spec.get("evidence", [])}

    # 토큰 대비
    try:
        tokens = resolve_tokens(spec)
        c = tokens["colors"]
        for fg, bg, label in ((c["ink"], c["background"], "ink/background"), (c["ink_muted"], c["background"], "ink_muted/background"), (c["on_primary"], c["primary"], "on_primary/primary")):
            ratio = contrast(fg, bg)
            if ratio < 4.5:
                add("contrast-low", "error", f"{label} 대비 {ratio:.2f}:1 < 4.5", pair=[fg, bg])
        ratio = contrast(c["primary"], c["background"])
        if ratio < 3.0:
            add("contrast-low", "warning", f"primary/background 대비 {ratio:.2f}:1 < 3.0 (큰 글자·도형 기준)", pair=[c["primary"], c["background"]])
    except Exception as e:  # noqa: BLE001
        add("spec-invalid", "error", f"토큰 해석 실패: {e}")

    title_limit = 45 if mode == "live" else (52 if mode == "hybrid" else 60)
    streak_arch, streak_n = None, 0
    ghost: List[str] = []
    has_conclusion = False
    for s in slides:
        n = s.get("number")
        arch = s.get("archetype", "")
        meta = archetypes.get(arch, {})
        title = (s.get("title") or "").strip()
        content = s.get("content") or {}
        is_content = arch not in NON_CONTENT and not s.get("appendix")
        ghost.append(f"{n:>2}. [{arch}] {title}")
        if arch in ("conclusion", "recommendation"):
            has_conclusion = True
        # 제목 규칙
        if meta.get("title_required", False) and is_content:
            t_norm = re.sub(r"[\s\d.:：\-–—()\[\]]+", " ", title).strip().lower()
            if t_norm in {x.lower() for x in TOPIC_LABELS} or len(title) <= 8:
                add("title-topic-label", "error", f"'{title}' — 토픽 라벨이 아니라 결론 문장(액션 타이틀)으로", n)
            elif not VERB_ENDINGS.search(title) and not re.search(r"\b(is|are|will|can|should|must|has|have|drives|reduces|increases|requires|enables|shows|leads|needs)\b", title, re.IGNORECASE):
                add("title-no-verb", "warning", f"'{title}' — 서술어가 없어 보임. 주장을 문장으로", n)
            if len(title) > title_limit:
                add("title-too-long", "error" if len(title) > title_limit * 1.3 else "warning", f"제목 {len(title)}자 > {title_limit}자 (2줄 상한)", n)
            if title.endswith("."):
                add("title-ends-period", "info", "제목 끝 마침표는 관행상 생략", n)
            if not s.get("takeaway") and arch not in ("hero_metric",):
                add("takeaway-missing", "info", "takeaway(한 문장 요지) 없음 — 발표자 노트·검수에 쓰인다", n)
        # 글자량
        mc = meta.get("max_chars") or {}
        limit = mc.get(mode_key)
        if mode == "hybrid" and mc.get("live") and mc.get("pre_read"):
            limit = int((mc["live"] + mc["pre_read"]) / 2)
        total = _chars(content) + _chars(s.get("body")) + len(s.get("takeaway") or "")
        if limit and total > limit:
            add("body-too-long", "error" if total > limit * 1.35 else "warning", f"본문 {total}자 > 상한 {limit}자 ({mode_key}). 줄이거나 슬라이드를 나눈다 (글자 축소 금지)", n, chars=total, limit=limit)
        mi = meta.get("max_items")
        cnt = _count_items(content)
        if mi and cnt > mi:
            add("items-too-many", "warning", f"항목 {cnt}개 > 권장 {mi}개", n)
        # 출처
        if arch in NUMERIC_ARCHETYPES and not (s.get("source_note") or "").strip():
            add("source-missing", "error", f"{arch} 슬라이드에 source_note 없음 (출처·기간·단위)", n)
        for eid in s.get("evidence_ids", []) or []:
            ev = evidence.get(eid)
            if ev and ev.get("confidence") == "low" and is_content:
                add("evidence-low", "warning", f"근거 {eid}(confidence=low) 사용 — 추정임을 표기하거나 부록으로", n)
        # 연속 레이아웃
        if arch == streak_arch:
            streak_n += 1
        else:
            streak_arch, streak_n = arch, 1
        if streak_n == 3 and arch not in ("appendix", "data_table"):
            add("layout-streak", "warning", f"'{arch}' 아키타입 3장 연속 — 형식을 바꾸거나 합친다", n)
        # 약어·정밀도
        text_blob = json.dumps(content, ensure_ascii=False) + " " + title + " " + " ".join(s.get("body") or [])
        for m in set(ACRONYM.findall(text_blob)):
            if m not in COMMON_ACRONYMS and f"{m}(" not in text_blob and f"({m})" not in text_blob and f"{m} (" not in text_blob:
                add("acronym-unexplained", "info", f"약어 {m} 풀이 없음 (첫 등장에 풀이)", n)
        if FAKE_PRECISION.search(text_blob):
            add("fake-precision", "info", "소수점 2자리 이상 비율 — 의사결정에 필요한 자릿수만", n)
        if mode in ("live", "hybrid") and is_content and not (s.get("speaker_notes") or "").strip():
            add("notes-missing", "info", "speaker_notes 없음", n)
    # 마무리
    last = slides[-1]
    last_title = (last.get("title") or "").strip()
    if THANKS.match(last_title) or (last.get("archetype") == "statement" and THANKS.match((last.get("content") or {}).get("statement", ""))):
        add("thank-you-ending", "error", "마지막 슬라이드가 감사 인사뿐 — 결론·결정·다음 단계를 남긴다", last.get("number"))
    if not has_conclusion and len(slides) >= 5:
        add("no-conclusion", "warning", "conclusion 또는 recommendation 아키타입이 없음")
    dur = spec["metadata"].get("duration_minutes")
    if dur and mode in ("live", "hybrid"):
        body_n = len([s for s in slides if s.get("archetype") not in NON_CONTENT and not s.get("appendix")])
        lo, hi = dur / 2.0, dur / 1.2
        if body_n > hi:
            add("duration-mismatch", "warning", f"{dur}분 발표에 본문 {body_n}장 — 장당 1.2~2분 기준 상한 {hi:.0f}장")
        elif body_n < lo * 0.5 and body_n < 4:
            add("duration-mismatch", "info", f"{dur}분 발표에 본문 {body_n}장 — 적다")
    errors = [f for f in findings if f["level"] == "error"]
    return {"ok": not errors, "errors": len(errors), "warnings": len([f for f in findings if f["level"] == "warning"]), "findings": findings, "ghost_deck": ghost}


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py lint")
    ap.add_argument("spec")
    ap.add_argument("--ghost", action="store_true", help="고스트덱(제목만) 출력")
    a = ap.parse_args(argv)
    spec, errs = load_spec(a.spec)
    r = lint_spec(spec, errs)
    if a.ghost:
        print("\n".join(r["ghost_deck"]))
        print()
    print(json.dumps({k: v for k, v in r.items() if k != "ghost_deck"}, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1
