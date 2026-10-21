"""내용 감사 — 장표 간 숫자·단위·합계·기간·추정 표기를 검사해 '예쁜데 틀린' 자료를 막는다.

PPTX(추출 텍스트) 또는 deck-spec 을 대상으로:
  number-conflict     같은 지표 문구 뒤에 서로 다른 숫자 (예: '개발 기간 6.5주' vs '개발 기간 7주')
  unit-mix            금액 단위 혼용 (억원·백만원·만원·원) — 덱 전체에서 2종 이상
  total-mismatch      표의 '합계/총계/계' 행 값 ≠ 열 합 (수치 열마다 검사, 0.5% 허용)
  percent-over        100% 초과 비율, 합이 100%가 돼야 할 구성비가 아닌 경우 (경고)
  estimate-unmarked   '추정·예상·목표·(E)·약' 표기 없는 미래 연도 수치 (경고)
  vat-unclear         금액이 있는데 '부가세' 포함/별도 표기가 덱 어디에도 없음 (정보)
  period-missing      통계 슬라이드에 기간(연도·월) 표기 없음 (경고)
  source-missing      숫자가 3개 이상인 슬라이드에 출처 줄 없음 (경고; lint와 중복되지만 pptx 대상에서도 동작)
  currency-format     천 단위 구분 누락 (5자리 이상 숫자) (정보)
  text-missing        (--spec) deck-spec 의 문자열이 PPTX 어디에도 없음 — 렌더러가 내용을 떨어뜨렸거나 잘랐다 (제목·핵심 문장은 오류, 나머지 경고)
  chart-data-missing  (--spec) 차트 범주·시리즈 이름이 차트 XML에 없음 (오류)

수치 추출은 휴리스틱이다. 결과는 사람이 판단한다 (자동 수정 없음). text-missing 은 spec→pptx 독립 검증으로,
렌더 경고(warnings)와 별개로 '명세의 글자가 실제 파일에 들어갔는가'를 확인한다.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .extract import extract
from .package import NS, Package, q, text_of

NUM = r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
UNIT_MONEY = ["조원", "억원", "백만원", "천만원", "만원", "원", "억 원", "백만 원"]
ESTIMATE_MARK = re.compile(r"(추정|예상|목표|전망|약\s*\d|\(E\)|E\b|안\)|계획)")
TOTAL_ROW = re.compile(r"^(합계|총계|계|총\s*합|total)\s*$", re.IGNORECASE)
YEAR = re.compile(r"(20\d{2})\s*(?:년|\.|–|-|~|$)")
PERIOD = re.compile(r"(20\d{2}\s*[.년]|\d{4}\s*[–\-~]\s*\d{2,4}|상반기|하반기|분기|월\b|\b[1-9]\d?월)")


def _slide_texts_from_pptx(path: str) -> List[Dict[str, Any]]:
    slides = extract(path)
    out = []
    for s in slides:
        texts = [s["title"]] + [p for t in s["texts"] for p in t["paragraphs"]]
        out.append({"number": s["number"], "title": s["title"], "texts": texts, "tables": s["tables"], "source": next((t for t in texts if re.match(r"^\s*(출처|Source|※|자료)", t)), "")})
    return out


def _slide_texts_from_spec(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for s in spec.get("slides", []):
        texts: List[str] = [s.get("title", "")]
        tables: List[List[List[str]]] = []

        def walk(v):
            if isinstance(v, str):
                texts.append(v)
            elif isinstance(v, dict):
                if "columns" in v and "rows" in v and isinstance(v["rows"], list):
                    tables.append([list(map(str, v["columns"]))] + [[str(c) for c in r] for r in v["rows"]])
                for vv in v.values():
                    walk(vv)
            elif isinstance(v, list):
                for vv in v:
                    walk(vv)
        walk(s.get("content") or {})
        walk(s.get("body") or [])
        c = s.get("content") or {}
        if c.get("items") and c.get("total") and isinstance(c["items"], list) and all(isinstance(i, dict) and "amount" in i for i in c["items"]):
            tables.append([["항목", "금액"]] + [[i.get("label", ""), str(i.get("amount", ""))] for i in c["items"]] + [["합계", str(c["total"])]])
        out.append({"number": s.get("number"), "title": s.get("title", ""), "texts": texts, "tables": tables, "source": s.get("source_note", "")})
    return out


# ----------------------------------------------------------------------------
# spec ↔ pptx 텍스트 손실 검증
# ----------------------------------------------------------------------------

_ZW = re.compile(r"[\u200b\u200c\u200d\ufeff]")


def _norm_text(s: str) -> str:
    s = _ZW.sub("", str(s))
    s = s.replace("\u00a0", " ")
    return re.sub(r"\s+", "", s).lower()


KEY_FIELDS = {"title", "answer", "statement", "recommendation", "decision", "insight", "verdict", "implication", "caption", "subtitle"}
SKIP_KEYS = {"image", "layout", "style", "type", "col_widths", "image_ratio", "row_h", "emphasis_row", "highlight_col", "accent_col", "numbered", "frame", "sizing", "subtitle_above", "trend", "tone", "kind", "secondary", "x", "y", "emphasis", "winner", "highlight", "highlight_rows", "align", "value_format", "show_values", "show_percent", "y_max", "y_min", "hide_value_axis", "hide_unit", "relation", "columns_per_row", "shared_y", "variant", "background", "number", "evidence_ids", "speaker_notes", "takeaway", "qa", "appendix", "role", "logo", "logos", "label_pt"}


def _spec_strings(slide: Dict[str, Any]) -> List[Tuple[str, str, bool]]:
    """(경로, 문자열, 핵심 여부) — 슬라이드에 그려져야 하는 모든 문자열."""
    out: List[Tuple[str, str, bool]] = []

    def walk(v, path, key):
        if key in SKIP_KEYS:
            return
        if isinstance(v, str):
            if len(_norm_text(v)) >= 2:
                out.append((path, v, key in KEY_FIELDS))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append((path, str(v), False))
        elif isinstance(v, dict):
            for k, vv in v.items():
                walk(vv, f"{path}.{k}", k)
        elif isinstance(v, list):
            for i, vv in enumerate(v):
                walk(vv, f"{path}[{i}]", key)
    if slide.get("archetype") not in ("custom",):
        if slide.get("archetype") != "statement" or not (slide.get("content") or {}).get("statement"):
            walk(slide.get("title", ""), "title", "title")
        walk(slide.get("content") or {}, "content", "content")
        walk(slide.get("body") or [], "body", "body")
        if slide.get("source_note"):
            walk(slide["source_note"], "source_note", "source_note")
    return out


def _pptx_blobs(path: str) -> List[Dict[str, Any]]:
    """슬라이드별 정규화 텍스트 덩어리 — 도형 텍스트 + 표 셀 + 차트 범주·시리즈명·제목."""
    out: List[Dict[str, Any]] = []
    with Package.open(path) as pkg:
        for ref in pkg.slides():
            if not pkg.has(ref.part):
                continue
            root = pkg.xml(ref.part)
            parts: List[str] = []
            for para in root.iter(q("a:p")):
                parts.append(text_of(para))  # 문단 안의 run 은 이어 붙이고 문단 사이는 구분자
            chart_parts: List[str] = []
            for cp in pkg.chart_parts(ref.part):
                if not pkg.has(cp):
                    continue
                croot = pkg.xml(cp)
                for v in croot.iter(q("c:v")):
                    chart_parts.append(v.text or "")
                for para in croot.iter(q("a:p")):
                    chart_parts.append(text_of(para))
            title = ""
            for sp in root.iter(q("p:sp")):
                ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
                if ph is not None and ph.get("type") in ("title", "ctrTitle"):
                    title = " ".join(text_of(p) for p in sp.findall(".//a:p", NS))
                    break
            out.append({"number": ref.index, "title": title, "blob": _norm_text("|".join(parts)), "chart": _norm_text("|".join(chart_parts))})
    return out


def verify_text(spec: Dict[str, Any], pptx: str) -> Dict[str, Any]:
    blobs = _pptx_blobs(pptx)
    by_title = {_norm_text(b["title"]): b for b in blobs if b["title"]}
    by_index = {b["number"]: b for b in blobs}
    findings: List[Dict[str, Any]] = []
    checked = 0
    for s in spec.get("slides", []):
        b = by_title.get(_norm_text(s.get("title", ""))) or by_index.get(s.get("number"))
        if b is None:
            findings.append({"code": "text-missing", "level": "error", "slide": s.get("number"), "message": "PPTX에서 대응 슬라이드를 찾지 못함 (--only 빌드면 정상)"})
            continue
        chart_blob = b["blob"] + b["chart"]
        for path, text, key in _spec_strings(s):
            checked += 1
            n = _norm_text(text)
            if n in b["blob"]:
                continue
            # 줄바꿈(\n)이 든 문자열은 문단 단위로 들어가므로 조각별로 확인
            if "\n" in str(text):
                pieces = [_norm_text(x) for x in str(text).split("\n") if _norm_text(x)]
                if pieces and all(x in b["blob"] for x in pieces):
                    continue
            is_chart = path.startswith("content.chart") or ".chart." in path or path.startswith("content.charts")
            if is_chart and n in b["chart"]:
                continue
            # 숫자는 표기 차이(6.0 vs 6, 1,200 vs 1200)를 허용해 값으로 비교 (차트 XML 포함)
            if re.fullmatch(r"[\d.,+\-]+", n):
                try:
                    val = float(n.replace(",", ""))
                    if any(abs(float(m.replace(",", "")) - val) < 1e-9 for m in re.findall(r"\d[\d,]*\.?\d*", b["blob"] + b["chart"])):
                        continue
                except ValueError:
                    pass
            if is_chart:
                findings.append({"code": "chart-data-missing", "level": "error", "slide": s.get("number"), "path": path, "message": f"차트 데이터 '{text[:40]}' 가 차트 XML에 없음"})
                continue
            findings.append({"code": "text-missing", "level": "error" if key else "warning", "slide": s.get("number"), "path": path, "message": f"'{text[:50]}' 가 PPTX 슬라이드 텍스트에 없음"})
    errors = [f for f in findings if f["level"] == "error"]
    return {"ok": not errors, "checked": checked, "errors": len(errors), "warnings": len(findings) - len(errors), "findings": findings}


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


def audit_slides(slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []

    def add(code, level, msg, slide=None, **kw):
        d = {"code": code, "level": level, "message": msg}
        if slide is not None:
            d["slide"] = slide
        d.update(kw)
        findings.append(d)

    all_text = "\n".join(t for s in slides for t in s["texts"])
    # 단위 혼용
    units_found = {u for u in UNIT_MONEY if re.search(r"\d\s*" + re.escape(u), all_text)}
    money_units = {u.replace(" ", "") for u in units_found} - {"원"}
    if len(money_units) >= 2:
        add("unit-mix", "warning", f"금액 단위 혼용: {sorted(money_units)} — 덱 전체 단위를 하나로 통일하거나 표마다 '단위:' 명시")
    if money_units and not re.search(r"부가세|VAT", all_text):
        add("vat-unclear", "info", "금액이 있으나 부가세 포함/별도 표기가 없음")
    # 지표-숫자 충돌: '한글 지표 문구 + 숫자 + 단위' 패턴
    metric_re = re.compile(r"([가-힣A-Za-z][가-힣A-Za-z ·]{1,14}?)\s*(?:은|는|이|가|을|를|:|：)?\s*" + NUM + r"\s*(%|주|건|명|개|억원|백만원|만원|원|초|분|시간|일|년|개월|%p)")
    seen: Dict[Tuple[str, str], Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
    for s in slides:
        for t in s["texts"]:
            for m in metric_re.finditer(t):
                key = (re.sub(r"\s+", "", m.group(1)), m.group(3))
                seen[key][m.group(2)].append(s["number"])
    for (label, unit), vals in seen.items():
        if len(vals) >= 2 and len(label) >= 2:
            # 목표/현행처럼 의도적 차이가 많으므로 info
            add("number-conflict", "info", f"'{label}' + {unit}: 값이 여러 개 {dict((k, sorted(set(v))) for k, v in vals.items())} — 같은 지표라면 통일, 다른 시점이면 시점을 함께 적는다")
    # 표 합계 검증 / 기간 / 출처 / 추정 표기
    for s in slides:
        for tbl in s["tables"]:
            if len(tbl) < 3:
                continue
            total_rows = [i for i, r in enumerate(tbl) if r and TOTAL_ROW.match(str(r[0]).strip())]
            for ti in total_rows:
                for ci in range(1, max(len(r) for r in tbl)):
                    vals = []
                    for r in tbl[1:ti]:
                        cell = r[ci] if ci < len(r) else ""
                        m = re.fullmatch(r"\s*" + NUM + r"\s*[%a-zA-Z가-힣]*\s*", str(cell))
                        if m:
                            vals.append(_to_float(m.group(1)))
                        elif str(cell).strip():
                            vals = []
                            break
                    tcell = tbl[ti][ci] if ci < len(tbl[ti]) else ""
                    mt = re.fullmatch(r"\s*" + NUM + r"\s*[%a-zA-Z가-힣]*\s*", str(tcell))
                    if vals and mt and len(vals) >= 2:
                        total = _to_float(mt.group(1))
                        ssum = sum(vals)
                        if abs(ssum - total) > max(0.005 * max(abs(total), 1), 0.01):
                            add("total-mismatch", "error", f"표 '{tbl[0][ci] if ci < len(tbl[0]) else ci}' 열: 행 합 {ssum:g} ≠ 합계 {total:g}", s["number"])
        joined = " ".join(s["texts"])
        # 연도·한 자리 번호(단계·순번)는 '통계 수치'로 세지 않는다
        # 요구 ID(SFR-003)·쪽수 참조(32쪽, 02–05)·일자(2027.03.31)는 통계 수치가 아니다
        stat_text = re.sub(r"\b[A-Z]{2,4}-\d{2,4}\b|\d{1,3}(?:\s*[–\-~,]\s*\d{1,3})*\s*쪽|\d{1,3}\s*[–\-~]\s*\d{1,3}(?=[\s,·)]|$)|20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}", " ", joined)
        nums = [n for n in re.findall(NUM, stat_text) if not re.fullmatch(r"(19|20)\d{2}", n) and not re.fullmatch(r"\d", n)]
        pct = [float(p) for p in re.findall(r"(\d+(?:\.\d+)?)\s*%", joined)]
        if any(p > 100 for p in pct):
            add("percent-over", "warning", f"100% 초과 비율 표기 {[p for p in pct if p > 100]} — 증가율이면 '배'나 '%p'를 검토", s["number"])
        if len(nums) >= 3 and not s.get("source"):
            add("source-missing", "warning", f"숫자 {len(nums)}개가 있는데 출처 줄이 없음", s["number"])
        if len(nums) >= 3 and s.get("source") and not PERIOD.search(s["source"] + " " + joined):
            add("period-missing", "warning", "통계가 있으나 기간(연도·월·분기) 표기가 없음", s["number"])
        for y in set(YEAR.findall(joined)):
            if int(y) >= 2027 and not ESTIMATE_MARK.search(joined):
                add("estimate-unmarked", "warning", f"미래 연도 {y} 수치에 추정·목표·계획 표기가 없음", s["number"])
                break
        for n in re.findall(r"(?<![\d,.])\d{5,}(?![\d,])", joined):
            add("currency-format", "info", f"천 단위 구분 없는 숫자 {n}", s["number"])
            break
    errors = [f for f in findings if f["level"] == "error"]
    return {"ok": not errors, "errors": len(errors), "warnings": len([f for f in findings if f["level"] == "warning"]), "findings": findings}


def audit(path: str, spec_path: Optional[str] = None) -> Dict[str, Any]:
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
        r = audit_slides(_slide_texts_from_spec(spec))
    else:
        r = audit_slides(_slide_texts_from_pptx(path))
        if spec_path:
            with open(spec_path, encoding="utf-8") as f:
                spec = json.load(f)
            v = verify_text(spec, path)
            r["text_verify"] = {"ok": v["ok"], "checked": v["checked"], "errors": v["errors"], "warnings": v["warnings"]}
            r["findings"].extend(v["findings"])
            r["errors"] += v["errors"]
            r["warnings"] += v["warnings"]
            r["ok"] = r["ok"] and v["ok"]
    r["file"] = path
    return r


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py audit")
    ap.add_argument("target", help="deck.pptx 또는 deck-spec.json")
    ap.add_argument("--spec", default=None, help="deck.pptx 대상일 때 명세와 대조해 텍스트 손실(text-missing)을 검사")
    a = ap.parse_args(argv)
    r = audit(a.target, a.spec)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1
