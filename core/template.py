"""기관 템플릿 분석 (Template Compiler 1단계) — 승인된 PPTX/POTX에서 계약(template-contract.json)을 뽑는다.

추출 항목
- 슬라이드 크기, 테마 글꼴(major/minor latin·ea), 테마 색 스킴(dk1/lt1/dk2/lt2/accent1–6)
- 마스터·레이아웃 목록: 이름, 자리표시자(type/idx/이름/위치·크기/기본 글자 크기), 고정 요소(푸터·쪽번호·로고 추정)
- 샘플 슬라이드(선택): 제목 위치·크기, 본문 영역 추정(제목 아래 ~ 푸터 위)
- 파생 토큰(derive): style-profiles 토큰 형태로 매핑한 design_tokens (deck-spec에 붙여 '기관 유사 스타일'로 새 덱을 만들 때)

템플릿을 '채우는' 작업은 inventory → replace → slides 로 하고, 이 계약은 Director가 안전영역·글자 크기·금지 사항을 지키게 하는 참고 문서다.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .package import NS, Package, emu_to_in, q, text_of


def _theme(pkg: Package, theme_part: str) -> Dict[str, Any]:
    root = pkg.xml(theme_part)
    out: Dict[str, Any] = {"part": theme_part, "fonts": {}, "colors": {}}
    fs = root.find(".//a:fontScheme", NS)
    if fs is not None:
        for kind in ("majorFont", "minorFont"):
            el = fs.find(f"a:{kind}", NS)
            if el is not None:
                out["fonts"][kind] = {k: (el.find(f"a:{k}", NS).get("typeface") if el.find(f"a:{k}", NS) is not None else "") for k in ("latin", "ea", "cs")}
    cs = root.find(".//a:clrScheme", NS)
    if cs is not None:
        out["colors"]["scheme_name"] = cs.get("name", "")
        for child in cs:
            tag = child.tag.split("}")[-1]
            clr = list(child)[0] if len(child) else None
            if clr is None:
                continue
            if clr.tag == q("a:srgbClr"):
                out["colors"][tag] = clr.get("val", "").upper()
            elif clr.tag == q("a:sysClr"):
                out["colors"][tag] = (clr.get("lastClr") or "000000").upper()
    return out


def _placeholders(root, pkg: Package, part: str) -> List[Dict[str, Any]]:
    out = []
    for sp in root.iter(q("p:sp")):
        ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
        cnv = sp.find("p:nvSpPr/p:cNvPr", NS)
        xf = sp.find("p:spPr/a:xfrm", NS)
        box = None
        if xf is not None and xf.find("a:off", NS) is not None and xf.find("a:ext", NS) is not None:
            o, e = xf.find("a:off", NS), xf.find("a:ext", NS)
            box = [round(emu_to_in(int(o.get("x"))), 2), round(emu_to_in(int(o.get("y"))), 2), round(emu_to_in(int(e.get("cx"))), 2), round(emu_to_in(int(e.get("cy"))), 2)]
        sizes = sorted({int(r.get("sz")) / 100 for r in sp.iter(q("a:rPr")) if r.get("sz")} | {int(r.get("sz")) / 100 for r in sp.iter(q("a:defRPr")) if r.get("sz")})
        txt = " ".join(text_of(p).strip() for p in sp.findall(".//a:p", NS)).strip()
        item = {"id": cnv.get("id") if cnv is not None else None, "name": cnv.get("name", "") if cnv is not None else "", "box_in": box, "font_pt": sizes, "text": txt[:80]}
        if ph is not None:
            item["placeholder"] = {"type": ph.get("type", "body"), "idx": ph.get("idx"), "sz": ph.get("sz")}
        else:
            item["fixed"] = True
            lt = txt.lower()
            if re.search(r"slidenum|‹#›|<#>", txt) or sp.find(".//a:fld[@type='slidenum']", NS) is not None:
                item["role"] = "page_number"
            elif box and box[1] > 6.0:
                item["role"] = "footer"
        out.append(item)
    for pic in root.iter(q("p:pic")):
        cnv = pic.find("p:nvPicPr/p:cNvPr", NS)
        xf = pic.find("p:spPr/a:xfrm", NS)
        box = None
        if xf is not None and xf.find("a:off", NS) is not None:
            o, e = xf.find("a:off", NS), xf.find("a:ext", NS)
            box = [round(emu_to_in(int(o.get("x"))), 2), round(emu_to_in(int(o.get("y"))), 2), round(emu_to_in(int(e.get("cx"))), 2), round(emu_to_in(int(e.get("cy"))), 2)]
        out.append({"id": cnv.get("id") if cnv is not None else None, "name": cnv.get("name", "") if cnv is not None else "", "box_in": box, "fixed": True, "role": "logo_or_image"})
    return out


def analyze(path: str, sample_slides: int = 3) -> Dict[str, Any]:
    with Package.open(path) as pkg:
        cx, cy = pkg.slide_size()
        W, H = emu_to_in(cx), emu_to_in(cy)
        contract: Dict[str, Any] = {"file": path, "slide_size_in": [round(W, 3), round(H, 3)], "aspect": "16:9" if abs(W / H - 16 / 9) < 0.02 else ("4:3" if abs(W / H - 4 / 3) < 0.02 else f"{W:.2f}:{H:.2f}"), "themes": [], "masters": [], "layouts": [], "sample_slides": []}
        for t in sorted(n for n in pkg.names if re.match(r"ppt/theme/theme\d+\.xml$", n)):
            contract["themes"].append(_theme(pkg, t))
        for m in sorted(n for n in pkg.names if re.match(r"ppt/slideMasters/slideMaster\d+\.xml$", n)):
            root = pkg.xml(m)
            contract["masters"].append({"part": m, "elements": _placeholders(root, pkg, m)})
        for lay in sorted((n for n in pkg.names if re.match(r"ppt/slideLayouts/slideLayout\d+\.xml$", n)), key=lambda s: int(re.search(r"(\d+)", s.rsplit("/", 1)[1]).group(1))):
            root = pkg.xml(lay)
            csld = root.find("p:cSld", NS)
            contract["layouts"].append({"part": lay, "name": csld.get("name", "") if csld is not None else "", "type": root.get("type", ""), "elements": _placeholders(root, pkg, lay)})
        for ref in pkg.slides()[:sample_slides]:
            if not pkg.has(ref.part):
                continue
            root = pkg.xml(ref.part)
            els = _placeholders(root, pkg, ref.part)
            title = next((e for e in els if e.get("placeholder", {}).get("type") in ("title", "ctrTitle")), None)
            contract["sample_slides"].append({"number": ref.index, "layout": pkg.layout_part(ref.part), "title": title, "elements": els})
        # 안전영역 추정: 레이아웃의 제목 아래 ~ 푸터 위
        title_boxes = [e["box_in"] for l in contract["layouts"] for e in l["elements"] if e.get("placeholder", {}).get("type") in ("title",) and e.get("box_in")]
        footer_tops = [e["box_in"][1] for l in contract["layouts"] + contract["masters"] for e in l["elements"] if e.get("role") in ("footer", "page_number") and e.get("box_in")] or [e["box_in"][1] for l in contract["layouts"] for e in l["elements"] if e.get("placeholder", {}).get("type") in ("ftr", "sldNum", "dt") and e.get("box_in")]
        if title_boxes:
            tb = title_boxes[0]
            contract["safe_area_in"] = {"x": tb[0], "y": round(tb[1] + tb[3] + 0.2, 2), "w": tb[2], "h": round((min(footer_tops) if footer_tops else H - 0.5) - (tb[1] + tb[3] + 0.2) - 0.15, 2), "title_box": tb}
        contract["derived_tokens"] = derive_tokens(contract)
        return contract


def derive_tokens(contract: Dict[str, Any]) -> Dict[str, Any]:
    """테마에서 style-profiles 토큰 형태의 부분 재정의를 만든다 (brand_mode=derived)."""
    th = contract["themes"][0] if contract.get("themes") else {"fonts": {}, "colors": {}}
    c = th.get("colors", {})
    f = th.get("fonts", {})
    major = f.get("majorFont", {})
    minor = f.get("minorFont", {})
    disp = major.get("ea") or major.get("latin") or "Paperlogy"
    body = minor.get("ea") or minor.get("latin") or "Pretendard"
    tokens: Dict[str, Any] = {"fonts": {"display": disp, "body": body}, "colors": {}}
    if c.get("dk1"):
        tokens["colors"]["ink"] = c["dk1"]
    if c.get("lt1"):
        tokens["colors"]["background"] = c["lt1"]
    if c.get("accent1"):
        tokens["colors"]["primary"] = c["accent1"]
    if c.get("accent2"):
        tokens["colors"]["accent"] = c["accent2"]
    if c.get("dk2"):
        tokens["colors"]["dark_background"] = c["dk2"]
    if c.get("lt2"):
        tokens["colors"]["surface"] = c["lt2"]
    W, H = contract.get("slide_size_in", [13.333, 7.5])
    if abs(W - 10) < 0.05 and abs(H - 5.625) < 0.05:
        tokens["canvas"] = {"layout": "LAYOUT_16x9", "width": 10, "height": 5.625}
    elif abs(W - 10) < 0.05 and abs(H - 7.5) < 0.05:
        tokens["canvas"] = {"layout": "LAYOUT_4x3", "width": 10, "height": 7.5}
    sa = contract.get("safe_area_in")
    if sa:
        tokens["canvas"] = dict(tokens.get("canvas", {}), margin={"left": round(sa["x"], 2), "right": round(W - sa["x"] - sa["w"], 2), "top": round(sa["title_box"][1], 2), "bottom": round(H - (sa["y"] + sa["h"]), 2)})
    tokens["_note"] = "테마에서 파생한 추정값. 기관 지침(색·글꼴·여백)이 있으면 그 값으로 덮어쓴다. 로고·상징은 승인 자산만 사용"
    return tokens


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py template")
    ap.add_argument("pptx", help="기관 템플릿 .pptx / .potx")
    ap.add_argument("-o", "--out", default=None, help="template-contract.json 저장 경로")
    ap.add_argument("--tokens-only", action="store_true", help="design_tokens 부분만 출력")
    a = ap.parse_args(argv)
    c = analyze(a.pptx)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=2)
    print(json.dumps(c["derived_tokens"] if a.tokens_only else ({"ok": True, "contract": a.out, "layouts": [(l["name"], len(l["elements"])) for l in c["layouts"]], "safe_area_in": c.get("safe_area_in"), "derived_tokens": c["derived_tokens"]} if a.out else c), ensure_ascii=False, indent=2))
    return 0
