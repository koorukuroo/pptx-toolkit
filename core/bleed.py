"""렌더 픽셀 기반 넘침 검출.

원리: 슬라이드 크기를 사방 PAD 만큼 키우고 모든 최상위 도형(슬라이드·레이아웃·마스터)을 PAD 만큼 이동한 뒤
네 변의 여백 띠에 회색 사각형을 깐다. 렌더 후 띠 영역에 회색이 아닌 픽셀이 threshold 이상이면
원래 슬라이드 경계를 넘어 '실제로 그려진' 글자·도형이 있다는 뜻이다. 상자 경계 계산(inspect)이
놓치는 줄바꿈 넘침을 잡는다.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .package import EMU_PER_INCH, NS, Package
from .render import _read_ppm, find_soffice, lo_profile_dir, to_pdf_libreoffice, to_pdf_powerpoint

PAD_IN = 1.0
GREY = (200, 200, 200)

OFF_RE = re.compile(rb'(<a:off x=")(-?\d+)(" y=")(-?\d+)(")')
SLDSZ_RE = re.compile(rb'<p:sldSz cx="(\d+)" cy="(\d+)"')


def _shift_top_level(xml: bytes, dx: int, dy: int) -> bytes:
    """spTree 바로 아래 도형의 a:off/p:xfrm off 만 이동 (그룹 내부는 상대 좌표이므로 건드리지 않음)."""
    # 간단한 깊이 추적 파서: grpSp 깊이 0인 위치의 <a:off>만 이동
    out = bytearray()
    i = 0
    depth = 0
    in_tree = False
    for m in re.finditer(rb"<(/?)(p:grpSp|p:spTree|a:off)\b([^>]*)>", xml):
        out += xml[i:m.start()]
        closing, tag, attrs = m.group(1), m.group(2), m.group(3)
        if tag == b"p:spTree":
            in_tree = not closing
            out += m.group(0)
        elif tag == b"p:grpSp":
            depth += -1 if closing else 1
            out += m.group(0)
        elif tag == b"a:off" and in_tree and depth <= 1:
            # depth 1 = 최상위 grpSp 자신의 xfrm (이동 대상), depth 0 = 일반 도형
            mm = re.match(rb'x="(-?\d+)"\s+y="(-?\d+)"', attrs.strip())
            if mm:
                x = int(mm.group(1)) + dx
                y = int(mm.group(2)) + dy
                out += b'<a:off x="%d" y="%d"/>' % (x, y) if m.group(0).endswith(b"/>") else b'<a:off x="%d" y="%d">' % (x, y)
            else:
                out += m.group(0)
        else:
            out += m.group(0)
        i = m.end()
        if tag == b"p:grpSp" and not closing:
            pass
    out += xml[i:]
    return bytes(out)


def _grey_rects(w: int, h: int, pad: int, base_id: int = 9000) -> bytes:
    def rect(i: int, x: int, y: int, cx: int, cy: int) -> bytes:
        return (
            b'<p:sp><p:nvSpPr><p:cNvPr id="%d" name="bleed-%d"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            b'<p:spPr><a:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            b'<a:solidFill><a:srgbClr val="C8C8C8"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr></p:sp>' % (base_id + i, i, x, y, cx, cy)
        )
    W, H = w + 2 * pad, h + 2 * pad
    return rect(1, 0, 0, W, pad) + rect(2, 0, H - pad, W, pad) + rect(3, 0, 0, pad, H) + rect(4, W - pad, 0, pad, H)


def make_padded(src: Path, dst: Path, pad_in: float = PAD_IN) -> Tuple[int, int, int]:
    pad = int(pad_in * EMU_PER_INCH)
    with Package.open(src) as pkg:
        w, h = pkg.slide_size()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            name = info.filename
            if name == "ppt/presentation.xml":
                data = SLDSZ_RE.sub(b'<p:sldSz cx="%d" cy="%d"' % (w + 2 * pad, h + 2 * pad), data, count=1)
            elif re.match(r"ppt/(slides|slideLayouts|slideMasters)/[^/]+\.xml$", name):
                data = _shift_top_level(data, pad, pad)
                if name.startswith("ppt/slides/"):
                    # spTree 첫 도형 앞(= grpSpPr 닫힌 직후)에 회색 띠 삽입 → 맨 뒤(z-order 최하단)
                    idx = data.find(b"</p:grpSpPr>")
                    if idx != -1:
                        idx += len(b"</p:grpSpPr>")
                        data = data[:idx] + _grey_rects(w, h, pad) + data[idx:]
            zout.writestr(info, data)
    return w, h, pad


def analyze(pdf: Path, w_emu: int, h_emu: int, pad_emu: int, dpi: int = 50, threshold: float = 0.004) -> List[Dict[str, Any]]:
    tmp = Path(tempfile.mkdtemp(prefix="pptx-bleed-"))
    try:
        subprocess.run(["pdftoppm", "-r", str(dpi), str(pdf), str(tmp / "p")], check=True, capture_output=True)
        files = sorted(tmp.glob("p-*.ppm"), key=lambda p: int(p.stem.split("-")[-1]))
        results = []
        for n, f in enumerate(files, start=1):
            W, H, px = _read_ppm(f)
            total_w = w_emu + 2 * pad_emu
            total_h = h_emu + 2 * pad_emu
            px_pad_x = round(W * pad_emu / total_w)
            px_pad_y = round(H * pad_emu / total_h)
            inset = 3  # 안티앨리어싱 경계 제외

            def dirty(x0, y0, x1, y1) -> Tuple[int, int]:
                cnt = 0
                tot = 0
                for y in range(y0, y1):
                    row = px[y * W * 3:(y + 1) * W * 3]
                    for x in range(x0, x1):
                        r, g, b = row[x * 3], row[x * 3 + 1], row[x * 3 + 2]
                        tot += 1
                        if abs(r - GREY[0]) > 18 or abs(g - GREY[1]) > 18 or abs(b - GREY[2]) > 18:
                            cnt += 1
                return cnt, tot

            strips = {
                "top": dirty(inset, inset, W - inset, px_pad_y - inset),
                "bottom": dirty(inset, H - px_pad_y + inset, W - inset, H - inset),
                "left": dirty(inset, px_pad_y, px_pad_x - inset, H - px_pad_y),
                "right": dirty(W - px_pad_x + inset, px_pad_y, W - inset, H - px_pad_y),
            }
            over = {k: round(c / t, 4) for k, (c, t) in strips.items() if t}
            bad = {k: v for k, v in over.items() if v > threshold}
            results.append({"slide": n, "ok": not bad, "dirty_ratio": over, "overflow_sides": sorted(bad)})
        return results
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def bleed_check(pptx: str, engine: str = "libreoffice", threshold: float = 0.004, keep: str | None = None) -> Dict[str, Any]:
    src = Path(pptx).resolve()
    work = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="pptx-bleed-work-"))
    work.mkdir(parents=True, exist_ok=True)
    padded = work / (src.stem + ".padded.pptx")
    w, h, pad = make_padded(src, padded)
    pdf = to_pdf_powerpoint(padded, work) if engine == "powerpoint" else to_pdf_libreoffice(padded, work)
    res = analyze(pdf, w, h, pad, threshold=threshold)
    if not keep:
        shutil.rmtree(work, ignore_errors=True)
    bad = [r for r in res if not r["ok"]]
    return {"file": str(src), "ok": not bad, "engine": engine, "overflowing": [r["slide"] for r in bad], "slides": res, "note": "overflow_sides는 그 방향으로 실제 픽셀이 슬라이드 밖에 그려졌다는 뜻. 상자 안에서의 넘침(상자가 슬라이드 안에 있을 때)은 inspect/render로 본다."}


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py bleed")
    ap.add_argument("pptx")
    ap.add_argument("--engine", choices=["libreoffice", "powerpoint"], default="libreoffice")
    ap.add_argument("--threshold", type=float, default=0.004)
    ap.add_argument("--keep", default=None, help="패딩본·PDF를 남길 디렉터리")
    a = ap.parse_args(argv)
    r = bleed_check(a.pptx, a.engine, a.threshold, a.keep)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1
