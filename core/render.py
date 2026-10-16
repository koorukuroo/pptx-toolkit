"""PPTX → PDF → PNG 렌더와 콘택트 시트.

엔진:
  libreoffice (기본) — 전용 사용자 프로필(-env:UserInstallation)을 만들고
      그 안의 user/fonts 에 시스템 폰트 디렉터리를 심링크한다. macOS 헤드리스 LibreOffice는
      시스템 폰트를 열거하지 못해 한글이 빈 칸으로 렌더되는 문제를 이렇게 우회한다.
  powerpoint  — macOS Microsoft PowerPoint를 AppleScript로 구동해 PDF 저장 (실제 폰트·레이아웃, 가장 정확)

출력: <out>/slide-01.png … 와 <out>/contact.png (전체 몽타주, 4열)
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .fonts import font_dirs

SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/opt/homebrew/bin/soffice",
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
    "C:/Program Files/LibreOffice/program/soffice.exe",
]


def find_soffice() -> Optional[str]:
    env = os.environ.get("SOFFICE")
    if env and Path(env).exists():
        return env
    for c in SOFFICE_CANDIDATES:
        w = shutil.which(c) if not os.path.isabs(c) else (c if Path(c).exists() else None)
        if w:
            return w
    return None


def lo_profile_dir() -> Path:
    base = Path(os.environ.get("PPTX_TOOLKIT_CACHE", Path.home() / ".cache" / "pptx-toolkit"))
    prof = base / "lo-profile"
    fonts = prof / "user" / "fonts"
    fonts.mkdir(parents=True, exist_ok=True)
    # 폰트 디렉터리 심링크 (LibreOffice는 user/fonts를 재귀 탐색한다)
    for i, d in enumerate(font_dirs()):
        link = fonts / f"sys{i}"
        try:
            if link.is_symlink() or link.exists():
                if link.is_symlink() and os.readlink(link) == str(d):
                    continue
                if link.is_symlink():
                    link.unlink()
                else:
                    continue
            os.symlink(str(d), str(link), target_is_directory=True)
        except OSError:
            pass
    return prof


def to_pdf_libreoffice(pptx: Path, out_dir: Path, timeout: int = 240) -> Path:
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError("LibreOffice(soffice)를 찾을 수 없다. 설치하거나 SOFFICE 환경변수로 경로를 지정한다. macOS에선 --engine powerpoint 도 가능")
    prof = lo_profile_dir()
    cmd = [soffice, f"-env:UserInstallation={prof.as_uri()}", "--headless", "--norestore", "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    pdf = out_dir / (pptx.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError(f"PDF 변환 실패: {r.stdout}\n{r.stderr}")
    return pdf


APPLESCRIPT = '''
on run argv
  set inPath to POSIX file (item 1 of argv)
  set outPath to (item 2 of argv)
  tell application "Microsoft PowerPoint"
    open inPath
    set thePres to active presentation
    save thePres in (POSIX file outPath) as save as PDF
    close thePres saving no
  end tell
  return "ok"
end run
'''


def to_pdf_powerpoint(pptx: Path, out_dir: Path, timeout: int = 180) -> Path:
    if platform.system() != "Darwin":
        raise RuntimeError("powerpoint 엔진은 macOS에서만 지원")
    pdf = out_dir / (pptx.stem + ".pdf")
    if pdf.exists():
        pdf.unlink()
    with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False) as f:
        f.write(APPLESCRIPT)
        script = f.name
    try:
        r = subprocess.run(["osascript", script, str(pptx.resolve()), str(pdf.resolve())], capture_output=True, text=True, timeout=timeout)
    finally:
        os.unlink(script)
    if not pdf.exists():
        raise RuntimeError(f"PowerPoint 내보내기 실패: {r.stderr or r.stdout}")
    return pdf


def pdf_to_png(pdf: Path, out_dir: Path, dpi: int = 110, prefix: str = "slide") -> List[Path]:
    if not shutil.which("pdftoppm"):
        raise RuntimeError("pdftoppm(poppler)이 필요하다: brew install poppler / apt install poppler-utils")
    for old in out_dir.glob(f"{prefix}-*.png"):
        old.unlink()
    subprocess.run(["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(out_dir / prefix)], check=True, capture_output=True)
    files = sorted(out_dir.glob(f"{prefix}-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
    # 자릿수 통일: slide-01.png
    width = max(2, len(str(len(files))))
    renamed: List[Path] = []
    for p in files:
        n = int(p.stem.split("-")[-1])
        target = out_dir / f"{prefix}-{n:0{width}d}.png"
        if target != p:
            p.rename(target)
        renamed.append(target)
    return renamed


# --- 콘택트 시트 (PPM → PNG, 외부 라이브러리 없음) --------------------------

def _read_ppm(path: Path) -> Tuple[int, int, bytes]:
    data = path.read_bytes()
    # P6\n<w> <h>\n255\n
    parts: List[bytes] = []
    i = 0
    while len(parts) < 4:
        while data[i:i + 1].isspace():
            i += 1
        if data[i:i + 1] == b"#":
            while data[i:i + 1] not in (b"\n", b""):
                i += 1
            continue
        j = i
        while not data[j:j + 1].isspace():
            j += 1
        parts.append(data[i:j])
        i = j
    i += 1
    w, h = int(parts[1]), int(parts[2])
    return w, h, data[i:i + w * h * 3]


def _write_png(path: Path, w: int, h: int, rgb: bytearray) -> None:
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
    path.write_bytes(png)


_DIGITS = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"], "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"], "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "001", "001", "001"], "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
}


def _blit_label(canvas: bytearray, cw: int, x: int, y: int, text: str, scale: int = 3) -> None:
    for ch in text:
        glyph = _DIGITS.get(ch)
        if glyph is None:
            x += 4 * scale
            continue
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    for dy in range(scale):
                        for dx in range(scale):
                            px, py = x + gx * scale + dx, y + gy * scale + dy
                            idx = (py * cw + px) * 3
                            canvas[idx:idx + 3] = b"\xd6\x27\x27"
        x += 4 * scale


def contact_sheet(pdf: Path, out_png: Path, cols: int = 4, thumb_w: int = 320, dpi: int = 36) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="pptx-contact-"))
    try:
        subprocess.run(["pdftoppm", "-r", str(dpi), str(pdf), str(tmp / "t")], check=True, capture_output=True)
        files = sorted(tmp.glob("t-*.ppm"), key=lambda p: int(p.stem.split("-")[-1]))
        if not files:
            raise RuntimeError("콘택트 시트용 PPM 생성 실패")
        pages = [_read_ppm(f) for f in files]
        # 최근접 리사이즈
        thumbs: List[Tuple[int, int, bytes]] = []
        for w, h, px in pages:
            tw = thumb_w
            th = max(1, round(h * tw / w))
            buf = bytearray(tw * th * 3)
            for ty in range(th):
                sy = min(h - 1, ty * h // th)
                row = px[sy * w * 3:(sy + 1) * w * 3]
                for tx in range(tw):
                    sx = min(w - 1, tx * w // tw)
                    buf[(ty * tw + tx) * 3:(ty * tw + tx) * 3 + 3] = row[sx * 3:sx * 3 + 3]
            thumbs.append((tw, th, bytes(buf)))
        gap, label_h = 14, 20
        th_max = max(t[1] for t in thumbs)
        rows = (len(thumbs) + cols - 1) // cols
        CW = cols * thumb_w + (cols + 1) * gap
        CH = rows * (th_max + label_h) + (rows + 1) * gap
        canvas = bytearray(b"\xee\xee\xee" * (CW * CH))
        for i, (tw, th, px) in enumerate(thumbs):
            r, c = divmod(i, cols)
            x0 = gap + c * (thumb_w + gap)
            y0 = gap + r * (th_max + label_h + gap) + label_h
            # 테두리
            for yy in range(y0 - 1, y0 + th + 1):
                for xx in (x0 - 1, x0 + tw):
                    if 0 <= yy < CH and 0 <= xx < CW:
                        canvas[(yy * CW + xx) * 3:(yy * CW + xx) * 3 + 3] = b"\x99\x99\x99"
            for ty in range(th):
                dst = ((y0 + ty) * CW + x0) * 3
                canvas[dst:dst + tw * 3] = px[ty * tw * 3:(ty + 1) * tw * 3]
            _blit_label(canvas, CW, x0, y0 - label_h + 2, str(i + 1))
        _write_png(out_png, CW, CH, canvas)
        return out_png
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def render(pptx: str, out_dir: str, engine: str = "libreoffice", dpi: int = 110, contact: bool = True, keep_pdf: bool = True) -> Dict[str, object]:
    src = Path(pptx).resolve()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if engine == "powerpoint":
        pdf = to_pdf_powerpoint(src, out)
    elif engine == "libreoffice":
        pdf = to_pdf_libreoffice(src, out)
    else:
        raise ValueError("engine은 libreoffice | powerpoint")
    pngs = pdf_to_png(pdf, out, dpi)
    result: Dict[str, object] = {"engine": engine, "pdf": str(pdf), "slides": [str(p) for p in pngs], "count": len(pngs)}
    if contact:
        result["contact"] = str(contact_sheet(pdf, out / "contact.png"))
    if not keep_pdf:
        pdf.unlink()
        result.pop("pdf")
    if engine == "libreoffice":
        result["note"] = "LibreOffice 렌더는 근사치다(줄바꿈·자간). 폰트가 설치돼 있으면 폭은 거의 정확하다. 최종 확인은 PowerPoint/Keynote에서."
    return result


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py render")
    ap.add_argument("pptx")
    ap.add_argument("-o", "--out", default=None, help="출력 디렉터리 (기본: <pptx>.render/)")
    ap.add_argument("--engine", choices=["libreoffice", "powerpoint"], default="libreoffice")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--no-contact", action="store_true")
    a = ap.parse_args(argv)
    out = a.out or (str(Path(a.pptx).with_suffix("")) + ".render")
    try:
        r = render(a.pptx, out, a.engine, a.dpi, not a.no_contact)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    r["ok"] = True
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0
