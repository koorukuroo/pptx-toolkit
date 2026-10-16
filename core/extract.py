"""슬라이드별 텍스트 추출 — 제목·본문·표·차트 제목·발표자 노트.

출력: markdown(기본) 또는 json. 슬라이드 경계는 `<!-- Slide N -->` 주석으로 구분한다.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .package import NS, Package, q, text_of


def _shape_kind(sp) -> str:
    ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
    if ph is not None:
        return ph.get("type", "body")
    return "text"


def _paragraphs(txbody) -> List[str]:
    out: List[str] = []
    for p in txbody.findall("a:p", NS):
        t = text_of(p).strip()
        if t:
            lvl = int((p.find("a:pPr", NS).get("lvl") if p.find("a:pPr", NS) is not None else 0) or 0)
            out.append(("  " * lvl) + t)
    return out


def _table(gf) -> List[List[str]]:
    tbl = gf.find(".//a:tbl", NS)
    rows: List[List[str]] = []
    if tbl is None:
        return rows
    for tr in tbl.findall("a:tr", NS):
        cells: List[str] = []
        for tc in tr.findall("a:tc", NS):
            txt = " ".join(text_of(p).strip() for p in tc.findall(".//a:p", NS))
            cells.append(txt.strip())
        rows.append(cells)
    return rows


def _walk(container, slide_part: str, pkg: Package, out: Dict[str, Any]) -> None:
    for child in list(container):
        tag = child.tag
        if tag == q("p:sp"):
            txb = child.find("p:txBody", NS)
            if txb is None:
                continue
            paras = _paragraphs(txb)
            if not paras:
                continue
            kind = _shape_kind(child)
            if kind in ("title", "ctrTitle") and not out["title"]:
                out["title"] = " ".join(paras)
            else:
                out["texts"].append({"kind": kind, "paragraphs": paras})
        elif tag == q("p:graphicFrame"):
            rows = _table(child)
            if rows:
                out["tables"].append(rows)
                continue
            # 차트: 제목만 (데이터는 chart xml)
            chart_ref = child.find(".//c:chart", NS)
            if chart_ref is not None:
                rid = chart_ref.get(q("r:id"))
                rel = pkg.rels(slide_part).get(rid)
                title = ""
                if rel is not None:
                    cpart = pkg.resolve(slide_part, rel.target)
                    if pkg.has(cpart):
                        croot = pkg.xml(cpart)
                        t = croot.find(".//c:title", NS)
                        if t is not None:
                            title = " ".join(text_of(p).strip() for p in t.findall(".//a:p", NS)).strip()
                out["charts"].append({"title": title})
        elif tag == q("p:grpSp"):
            _walk(child, slide_part, pkg, out)
        elif tag == q("p:pic"):
            out["pictures"] += 1


def extract(path: str) -> List[Dict[str, Any]]:
    slides: List[Dict[str, Any]] = []
    with Package.open(path) as pkg:
        for ref in pkg.slides():
            if not pkg.has(ref.part):
                continue
            root = pkg.xml(ref.part)
            out: Dict[str, Any] = {"number": ref.index, "part": ref.part, "title": "", "texts": [], "tables": [], "charts": [], "pictures": 0, "notes": ""}
            tree = root.find("p:cSld/p:spTree", NS)
            if tree is not None:
                _walk(tree, ref.part, pkg, out)
            np_ = pkg.notes_part(ref.part)
            if np_ and pkg.has(np_):
                nroot = pkg.xml(np_)
                notes: List[str] = []
                for sp in nroot.iter(q("p:sp")):
                    ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
                    if ph is not None and ph.get("type") == "body":
                        txb = sp.find("p:txBody", NS)
                        if txb is not None:
                            notes += _paragraphs(txb)
                out["notes"] = "\n".join(notes)
            slides.append(out)
    return slides


def to_markdown(slides: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for s in slides:
        lines.append(f"<!-- Slide {s['number']} -->")
        if s["title"]:
            lines.append(f"# {s['title']}")
        for t in s["texts"]:
            for p in t["paragraphs"]:
                lines.append(p)
        for tbl in s["tables"]:
            if not tbl:
                continue
            w = max(len(r) for r in tbl)
            rows = [r + [""] * (w - len(r)) for r in tbl]
            lines.append("| " + " | ".join(rows[0]) + " |")
            lines.append("|" + "---|" * w)
            for r in rows[1:]:
                lines.append("| " + " | ".join(r) + " |")
        for c in s["charts"]:
            lines.append(f"[chart] {c['title'] or '(제목 없음)'}")
        if s["pictures"]:
            lines.append(f"[pictures: {s['pictures']}]")
        if s["notes"]:
            lines.append("")
            lines.append("> notes: " + s["notes"].replace("\n", " / "))
        lines.append("")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py extract")
    ap.add_argument("pptx")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    a = ap.parse_args(argv)
    slides = extract(a.pptx)
    if a.format == "json":
        print(json.dumps(slides, ensure_ascii=False, indent=2))
    else:
        print(to_markdown(slides))
    return 0
