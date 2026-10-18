"""도형 기하 검사 — 렌더 없이 XML만으로 잡을 수 있는 레이아웃 결함.

  out-of-bounds     도형이 슬라이드 밖으로 나감 (허용 오차 0.02in)
  text-overlap      텍스트 도형끼리 겹침 (둘 다 글자가 있고, 교집합이 작은 쪽 면적의 15% 초과)
  text-overflow     글자량 추정으로 텍스트 상자 넘침 (설치 폰트의 실제 글자 폭·행간, 어절 단위 줄바꿈; 폰트 없으면 평균 계수)
  bottom-zone       12pt 초과 본문 텍스트가 슬라이드 바닥 0.5in 안에 걸침 (발표 UI·프로젝터 마스킹 영역) (경고)
  hangul-italic     한글 run 에 기울임 (CJK 글꼴은 합성 기울임이라 품질 저하) (경고)
  font-too-small    본문 글자 크기 하한 미만 (기본 12pt, --min-font로 조정; 출처/각주 9pt 허용 --note-font)
  image-low-res     표시 크기 대비 유효 DPI < 110
  image-stretched   원본 비율과 표시 비율 차이 > 8% (크롭 srcRect 없음)
  margin-violation  안전 여백(기본 0.4in) 침범 — 배경 전면 이미지/도형은 제외 (경고)
  title-two-lines+  제목 자리표시자 추정 줄 수 ≥ 3 (경고)
  empty-text        글자 없는 텍스트 상자 (경고)
  no-notes          발표자 노트 없음 (--require-notes 시 경고)

렌더 기반 시각 검수(render 후 PNG 확인)를 대체하지 않는다. 추정치는 폰트에 따라 ±15% 오차가 있다.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import fontmetrics as FM
from .package import NS, Package, emu_to_in, emu_to_pt, image_dimensions, q, text_of

TOL_IN = 0.02
SAFETY = 0.98  # 줄바꿈 폭 안전 여유 (scripts/lib/text.js 와 동일)
BOTTOM_ZONE_IN = 0.5


@dataclass
class Shape:
    sid: str
    name: str
    kind: str  # text | pic | graphic | shape | group
    x: float
    y: float
    w: float
    h: float
    text: str = ""
    runs: List[Tuple] = field(default_factory=list)  # (text, pt, face, bold)
    para_spacing: List[float] = field(default_factory=list)  # 문단별 lnSpc 배수 (spcPct/100000), 기본 1.0
    italic_hangul: bool = False
    is_placeholder: str = ""
    insets: Tuple[float, float, float, float] = (0.1, 0.05, 0.1, 0.05)  # l,t,r,b in
    autofit: str = ""
    wrap: bool = True
    filled: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def area(self) -> float:
        return max(self.w, 0) * max(self.h, 0)


def _xfrm(el) -> Optional[Tuple[float, float, float, float]]:
    x = el.find(".//a:xfrm", NS)
    if x is None:
        x = el.find(".//p:xfrm", NS)
    if x is None:
        return None
    off = x.find("a:off", NS)
    ext = x.find("a:ext", NS)
    if off is None or ext is None:
        return None
    bx, by, bw, bh = emu_to_in(int(off.get("x", 0))), emu_to_in(int(off.get("y", 0))), emu_to_in(int(ext.get("cx", 0))), emu_to_in(int(ext.get("cy", 0)))
    # 90/270도 회전은 중심 기준으로 폭·높이를 바꿔 실제 차지하는 영역을 돌려준다
    try:
        rot = int(x.get("rot", "0")) / 60000.0
    except ValueError:
        rot = 0.0
    if abs((rot % 180) - 90) < 1:
        cx, cy = bx + bw / 2, by + bh / 2
        return (cx - bh / 2, cy - bw / 2, bh, bw)
    return (bx, by, bw, bh)


def _run_face(rpr, default_face: str) -> str:
    if rpr is None:
        return default_face
    for tag in ("a:ea", "a:latin"):
        el = rpr.find(tag, NS)
        if el is not None and el.get("typeface") and not el.get("typeface").startswith("+"):
            return el.get("typeface")
    return default_face


def _runs(txbody, default_pt: float, default_face: str = "", shape: Optional["Shape"] = None) -> List[Tuple]:
    """(text, pt, face, bold) 목록. 문단 경계는 ("\n", pt, face, False). shape 가 있으면 문단 행간·한글 기울임도 기록."""
    runs: List[Tuple] = []
    lst_face = default_face
    lst = txbody.find("a:lstStyle", NS)
    if lst is not None:
        d = lst.find(".//a:defRPr", NS)
        if d is not None:
            lst_face = _run_face(d, default_face)
    for p in txbody.findall("a:p", NS):
        ppr = p.find("a:pPr", NS)
        spc = 1.0
        p_face = lst_face
        if ppr is not None:
            ln = ppr.find("a:lnSpc/a:spcPct", NS)
            if ln is not None and ln.get("val"):
                spc = int(ln.get("val")) / 100000.0
            d = ppr.find("a:defRPr", NS)
            if d is not None:
                p_face = _run_face(d, lst_face)
        if shape is not None:
            shape.para_spacing.append(spc)
        for node in p:
            if node.tag == q("a:r"):
                rpr = node.find("a:rPr", NS)
                sz = rpr.get("sz") if rpr is not None else None
                pt = int(sz) / 100 if sz else default_pt
                t = node.find("a:t", NS)
                text = (t.text or "") if t is not None else ""
                bold = rpr is not None and rpr.get("b") == "1"
                if shape is not None and rpr is not None and rpr.get("i") == "1" and re.search(r"[가-힣]", text):
                    shape.italic_hangul = True
                runs.append((text, pt, _run_face(rpr, p_face), bold))
            elif node.tag == q("a:br"):
                runs.append(("\n", default_pt, p_face, False))
            elif node.tag == q("a:fld"):
                t = node.find("a:t", NS)
                rpr = node.find("a:rPr", NS)
                sz = rpr.get("sz") if rpr is not None else None
                runs.append(((t.text or "") if t is not None else "", int(sz) / 100 if sz else default_pt, _run_face(rpr, p_face), False))
        runs.append(("\n", default_pt, p_face, False))
    if runs and runs[-1][0] == "\n":
        runs.pop()
    return runs


def _char_em(ch: str, face: Optional[str] = None, bold: bool = False) -> float:
    return FM.width_em(ch, face, bold)


def estimate_lines(runs: List[Tuple], width_in: float, para_spacing: Optional[List[float]] = None) -> Tuple[int, float]:
    """(총 줄 수, 필요한 높이 in). 어절(공백) 단위 줄바꿈, 폭 2% 여유, 행간 = 글자 크기 × 폰트 고유 행간 × 문단 spcPct.
    runs 항목은 (text, pt) 또는 (text, pt, face, bold)."""
    if width_in <= 0:
        return (0, 0.0)
    W = width_in * SAFETY
    total_lines = 0
    height = 0.0
    paras: List[List[Tuple[str, float, Optional[str], bool]]] = [[]]
    for r in runs:
        text, pt = r[0], r[1]
        face = r[2] if len(r) > 2 else None
        bold = bool(r[3]) if len(r) > 3 else False
        pieces = text.split("\n")
        for i, piece in enumerate(pieces):
            if i > 0:
                paras.append([])
            if piece:
                paras[-1].append((piece, pt, face, bold))
    for pi, para in enumerate(paras):
        spc = para_spacing[pi] if para_spacing and pi < len(para_spacing) else 1.0
        if not para:
            pt = runs[0][1] if runs else 12
            face = runs[0][2] if runs and len(runs[0]) > 2 else None
            total_lines += 1
            height += pt * FM.line_height_em(face) * spc / 72
            continue
        max_pt = max(pt for _, pt, _, _ in para)
        lh_em = max(FM.line_height_em(face, bold) for _, _, face, bold in para)
        line_w = 0.0
        lines = 1
        for text, pt, face, bold in para:
            em_in = pt / 72
            for tok in re.findall(r"\s+|\S+", text):
                tw = sum(_char_em(c, face, bold) for c in tok) * em_in
                if tok.isspace():
                    if line_w > 0:
                        line_w += tw
                    continue
                if line_w + tw > W and line_w > 0:
                    lines += 1
                    line_w = 0.0
                if tw > W:
                    for c in tok:
                        cw = _char_em(c, face, bold) * em_in
                        if line_w + cw > W and line_w > 0:
                            lines += 1
                            line_w = 0.0
                        line_w += cw
                    continue
                line_w += tw
        total_lines += lines
        height += lines * max_pt * lh_em * spc / 72
    return total_lines, height


def theme_fonts(pkg: Package) -> Tuple[str, str]:
    """(major latin, minor latin) — 테마 글꼴. 없으면 ('', '')."""
    for n in pkg.names:
        if re.match(r"ppt/theme/theme\d+\.xml$", n):
            try:
                root = pkg.xml(n)
            except Exception:  # noqa: BLE001
                continue
            fs = root.find(".//a:fontScheme", NS)
            if fs is None:
                continue
            def pick(kind):
                el = fs.find(f"a:{kind}", NS)
                if el is None:
                    return ""
                for t in ("a:ea", "a:latin"):
                    x = el.find(t, NS)
                    if x is not None and x.get("typeface"):
                        return x.get("typeface")
                return ""
            return pick("majorFont"), pick("minorFont")
    return "", ""


def _collect(container, pkg: Package, part: str, out: List[Shape], offset=(0.0, 0.0), scale=(1.0, 1.0), default_pt=18.0, fonts: Tuple[str, str] = ("", "")) -> None:
    for child in list(container):
        tag = child.tag.split("}")[-1]
        if tag == "grpSp":
            gx = child.find("p:grpSpPr/a:xfrm", NS)
            o2, s2 = offset, scale
            if gx is not None:
                off = gx.find("a:off", NS)
                ext = gx.find("a:ext", NS)
                choff = gx.find("a:chOff", NS)
                chext = gx.find("a:chExt", NS)
                if off is not None and ext is not None and choff is not None and chext is not None:
                    cx, cy = int(chext.get("cx", 1)) or 1, int(chext.get("cy", 1)) or 1
                    sx = int(ext.get("cx", 0)) / cx * scale[0]
                    sy = int(ext.get("cy", 0)) / cy * scale[1]
                    ox = offset[0] + emu_to_in(int(off.get("x", 0))) * scale[0] - emu_to_in(int(choff.get("x", 0))) * sx
                    oy = offset[1] + emu_to_in(int(off.get("y", 0))) * scale[1] - emu_to_in(int(choff.get("y", 0))) * sy
                    o2, s2 = (ox, oy), (sx, sy)
            _collect(child, pkg, part, out, o2, s2, default_pt, fonts)
            continue
        if tag not in ("sp", "pic", "graphicFrame", "cxnSp"):
            continue
        xf = _xfrm(child)
        if xf is None:
            continue
        x, y, w, h = xf
        x, y, w, h = offset[0] + x * scale[0], offset[1] + y * scale[1], w * scale[0], h * scale[1]
        cnv = child.find(".//p:cNvPr", NS)
        sid = cnv.get("id", "?") if cnv is not None else "?"
        name = cnv.get("name", "") if cnv is not None else ""
        ph = child.find(".//p:nvPr/p:ph", NS)
        phtype = (ph.get("type", "body") if ph is not None else "")
        if tag == "pic":
            s = Shape(sid, name, "pic", x, y, w, h, is_placeholder=phtype)
            blip = child.find(".//a:blip", NS)
            if blip is not None:
                rid = blip.get(q("r:embed"))
                target = pkg.image_targets(part).get(rid)
                if target and pkg.has(target):
                    dims = image_dimensions(pkg.read(target))
                    if dims:
                        s.extra["px"] = dims
                s.extra["srcRect"] = child.find(".//a:srcRect", NS) is not None
            out.append(s)
            continue
        if tag == "graphicFrame":
            kind = "table" if child.find(".//a:tbl", NS) is not None else ("chart" if child.find(".//c:chart", NS) is not None else "graphic")
            out.append(Shape(sid, name, kind, x, y, w, h, is_placeholder=phtype))
            continue
        if tag == "cxnSp":
            out.append(Shape(sid, name, "line", x, y, w, h))
            continue
        # sp
        txb = child.find("p:txBody", NS)
        sppr = child.find("p:spPr", NS)
        filled = sppr is not None and sppr.find("a:solidFill", NS) is not None
        s = Shape(sid, name, "shape", x, y, w, h, is_placeholder=phtype, filled=filled)
        if txb is not None:
            runs = _runs(txb, default_pt, fonts[0] if phtype in ("title", "ctrTitle") else fonts[1], s)
            text = "".join(r[0] for r in runs)
            s.runs = runs
            s.text = text
            if text.strip():
                s.kind = "text"
            flds = txb.findall(".//a:fld", NS)
            if flds and all(f.get("type") in ("slidenum", "datetime", "datetime1") for f in flds) and len(text.strip()) <= 12:
                s.kind = "field"  # 슬라이드 번호·날짜 필드: 넘침·글자 크기 검사 제외
            bp = txb.find("a:bodyPr", NS)
            if bp is not None:
                ins = [bp.get(k) for k in ("lIns", "tIns", "rIns", "bIns")]
                dflt = (91440, 45720, 91440, 45720)
                s.insets = tuple(emu_to_in(int(v)) if v is not None else emu_to_in(d) for v, d in zip(ins, dflt))  # type: ignore
                s.wrap = bp.get("wrap", "square") != "none"
                if bp.find("a:normAutofit", NS) is not None:
                    s.autofit = "shrink"
                elif bp.find("a:spAutoFit", NS) is not None:
                    s.autofit = "resize"
        out.append(s)


def inspect_file(path: str, min_font: float = 12.0, note_font: float = 9.0, margin: float = 0.4, require_notes: bool = False) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {}
    with Package.open(path) as pkg:
        cx, cy = pkg.slide_size()
        W, H = emu_to_in(cx), emu_to_in(cy)
        summary["slide_size_in"] = [round(W, 3), round(H, 3)]
        slides = pkg.slides()
        summary["slides"] = len(slides)
        fonts = theme_fonts(pkg)
        summary["theme_fonts"] = {"major": fonts[0], "minor": fonts[1], "metrics": {f: (FM.find(f) is not None) for f in set(fonts) if f}}
        min_font_seen = 999.0
        for ref in slides:
            if not pkg.has(ref.part):
                continue
            root = pkg.xml(ref.part)
            tree = root.find("p:cSld/p:spTree", NS)
            shapes: List[Shape] = []
            if tree is not None:
                _collect(tree, pkg, ref.part, shapes, fonts=fonts)
            n = ref.index

            def add(code: str, s: Optional[Shape], msg: str, level: str = "error", **kw) -> None:
                d = {"slide": n, "code": code, "level": level, "message": msg}
                if s is not None:
                    d["shape"] = {"id": s.sid, "name": s.name, "box": [round(s.x, 2), round(s.y, 2), round(s.w, 2), round(s.h, 2)], "text": s.text[:60]}
                d.update(kw)
                findings.append(d)

            for s in shapes:
                full_bleed = s.w >= W - 0.05 and s.h >= H - 0.05
                # bounds
                if s.x < -TOL_IN or s.y < -TOL_IN or s.x2 > W + TOL_IN or s.y2 > H + TOL_IN:
                    if not (full_bleed and s.x >= -0.05 and s.y >= -0.05):
                        add("out-of-bounds", s, f"슬라이드 밖으로 {max(0, -s.x, -s.y, s.x2 - W, s.y2 - H):.2f}in 이탈")
                elif margin > 0 and s.kind in ("text", "table", "chart") and not full_bleed:
                    small = s.kind == "text" and max([r[1] for r in s.runs if r[0].strip()] or [99]) <= 11  # 푸터·출처는 여백 안에 둘 수 있다
                    if not small and (s.x < margin - TOL_IN or s.x2 > W - margin + TOL_IN or s.y < margin * 0.6 - TOL_IN or s.y2 > H - margin * 0.6 + TOL_IN):
                        add("margin-violation", s, f"안전 여백 {margin}in 침범", level="warning")
                # fonts
                if s.kind == "text":
                    sizes = [r[1] for r in s.runs if r[0].strip()]
                    if s.italic_hangul:
                        add("hangul-italic", s, "한글에 기울임 — CJK 글꼴은 합성 기울임이라 품질이 떨어진다. 굵기·색으로 강조", level="warning")
                    if sizes and max(sizes) > 12 and s.y2 > H - BOTTOM_ZONE_IN + TOL_IN and s.y < H - BOTTOM_ZONE_IN and not full_bleed:
                        add("bottom-zone", s, f"본문 텍스트가 바닥 {BOTTOM_ZONE_IN}in 안에 걸침 (발표 UI·투사 마스킹 영역)", level="warning")
                    if sizes:
                        mn = min(sizes)
                        min_font_seen = min(min_font_seen, mn)
                        is_note = s.y > H - 1.0 or re.match(r"^\s*(출처|Source|주\s*[:：]|Note|※)", s.text) is not None
                        # 짧은 라벨(킥커·축 라벨·스티커·캡션 한 줄)은 본문 하한이 아니라 주석 하한을 적용한다
                        is_label = len(s.text.strip()) <= 20 and "\n" not in s.text.strip()
                        floor = note_font if (is_note or is_label) else min_font
                        if mn < floor - 0.01:
                            add("font-too-small", s, f"{mn:g}pt < 하한 {floor:g}pt", level="error" if mn < floor - 2 else "warning")
                    # overflow estimate
                    if s.wrap and s.autofit != "resize":
                        inner_w = s.w - s.insets[0] - s.insets[2]
                        inner_h = s.h - s.insets[1] - s.insets[3]
                        lines, need_h = estimate_lines(s.runs, inner_w, s.para_spacing)
                        if inner_h > 0 and need_h > inner_h * 1.08 + 0.02:
                            add("text-overflow", s, f"추정 {lines}줄·{need_h:.2f}in 필요, 상자 {inner_h:.2f}in", level="error" if need_h > inner_h * 1.3 else "warning", estimate=True)
                        if s.is_placeholder in ("title", "ctrTitle") and lines >= 3:
                            add("title-three-lines", s, f"제목이 {lines}줄로 추정", level="warning")
                elif s.kind == "shape" and not s.filled and s.runs == [] and s.w > 0 and s.h > 0:
                    pass
                if s.kind == "shape" and s.text == "" and s.runs and not s.filled:
                    add("empty-text", s, "글자 없는 텍스트 상자", level="warning")
                # images
                if s.kind == "pic" and "px" in s.extra:
                    pw, ph_ = s.extra["px"]
                    if s.w > 0 and s.h > 0:
                        dpi = min(pw / s.w, ph_ / s.h)
                        if dpi < 110:
                            add("image-low-res", s, f"유효 {dpi:.0f} DPI ({pw}×{ph_}px를 {s.w:.1f}×{s.h:.1f}in에 표시)", level="warning" if dpi >= 80 else "error")
                        if not s.extra.get("srcRect") and pw and ph_:
                            r_img, r_box = pw / ph_, s.w / s.h
                            if abs(r_img - r_box) / r_img > 0.08:
                                add("image-stretched", s, f"원본 비율 {r_img:.2f} vs 표시 {r_box:.2f}", level="error")
            # overlaps (text vs text/table/chart)
            cands = [s for s in shapes if s.kind in ("text", "table", "chart") and s.area > 0]
            for i in range(len(cands)):
                for j in range(i + 1, len(cands)):
                    a, b = cands[i], cands[j]
                    ix = max(0.0, min(a.x2, b.x2) - max(a.x, b.x))
                    iy = max(0.0, min(a.y2, b.y2) - max(a.y, b.y))
                    inter = ix * iy
                    if inter <= 0:
                        continue
                    small = min(a.area, b.area)
                    if inter > small * 0.15 and ix > 0.1 and iy > 0.1:
                        add("text-overlap", a, f"'{a.text[:20]}' ↔ '{b.text[:20]}' 겹침 {inter / small:.0%}", level="error" if inter > small * 0.4 else "warning", other={"id": b.sid, "box": [round(b.x, 2), round(b.y, 2), round(b.w, 2), round(b.h, 2)]})
            if require_notes and not pkg.notes_part(ref.part):
                add("no-notes", None, "발표자 노트 없음", level="warning")
        summary["min_font_pt"] = None if min_font_seen == 999.0 else min_font_seen
    errors = [f for f in findings if f["level"] == "error"]
    return {"file": path, "ok": not errors, "summary": summary, "errors": len(errors), "warnings": len(findings) - len(errors), "findings": findings}


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py inspect")
    ap.add_argument("pptx")
    ap.add_argument("--min-font", type=float, default=12.0, help="본문 최소 글자 크기 pt (발표용 14 권장)")
    ap.add_argument("--note-font", type=float, default=9.0, help="출처·각주 최소 글자 크기 pt")
    ap.add_argument("--margin", type=float, default=0.4, help="안전 여백 in (0이면 검사 안 함)")
    ap.add_argument("--require-notes", action="store_true")
    a = ap.parse_args(argv)
    r = inspect_file(a.pptx, a.min_font, a.note_font, a.margin, a.require_notes)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1
