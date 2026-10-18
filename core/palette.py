"""색 도출 프로토콜 — 브랜드 색(hex) 또는 PNG(로고·사진)에서 OKLCH 로 팔레트를 수렴시키고 근거를 남긴다.

  채색   입력 색을 OKLCH 로 변환. PNG면 유채색 픽셀의 색상 히스토그램에서 대표색 2~3개를 뽑는다
  수렴   유채색 2~3개(primary · secondary · accent) + 중성 명도 램프(L 0.15 / 0.35 / 0.65 / 0.92 / 0.98, primary 색상으로 아주 약하게 물들임)
         규칙: 유채색끼리 ΔH ≥ 60° 또는 ΔL ≥ 0.3 · 채도 밴드 배경 0.01–0.04 / 주조 0.08–0.15 / 강조 0.15–0.22 (밴드 밖이면 밀어 넣는다)
  논증   대비(ink/background ≥ 4.5, on_primary/primary ≥ 4.5, primary/background ≥ 3) 검사 결과와 한 문장 근거(rationale)

출력은 deck-spec 의 design_tokens.colors(+chart.palette) 로 바로 붙일 수 있다. 특정 기관·회사의 색을 '정답'으로 두지 않으며
사용자가 준 색을 출발점으로 쓴다 (brand_mode=derived).
"""
from __future__ import annotations

import json
import math
import struct
import zlib
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ----------------------------------------------------------------------------
# 색 공간
# ----------------------------------------------------------------------------

def hex_to_rgb(h: str) -> Tuple[float, float, float]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb: Sequence[float]) -> str:
    return "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def rgb_to_oklab(rgb: Sequence[float]) -> Tuple[float, float, float]:
    r, g, b = (_lin(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklab_to_rgb_linear(lab: Sequence[float]) -> Tuple[float, float, float]:
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def oklab_to_rgb(lab: Sequence[float]) -> Tuple[float, float, float]:
    return tuple(_gam(c) for c in oklab_to_rgb_linear(lab))  # type: ignore[return-value]


def in_gamut(lab: Sequence[float], eps: float = 0.002) -> bool:
    return all(-eps <= c <= 1 + eps for c in oklab_to_rgb_linear(lab))


def lab_to_lch(lab: Sequence[float]) -> Tuple[float, float, float]:
    L, a, b = lab
    c = math.hypot(a, b)
    h = math.degrees(math.atan2(b, a)) % 360
    return L, c, h


def lch_to_lab(lch: Sequence[float]) -> Tuple[float, float, float]:
    L, c, h = lch
    return L, c * math.cos(math.radians(h)), c * math.sin(math.radians(h))


def hex_to_lch(h: str) -> Tuple[float, float, float]:
    return lab_to_lch(rgb_to_oklab(hex_to_rgb(h)))


def lch_to_hex(lch: Sequence[float]) -> str:
    """색역 밖이면 채도를 줄여 밀어 넣는다 (명도·색상 유지)."""
    L, c, h = lch
    L = max(0.0, min(1.0, L))
    lab = lch_to_lab((L, c, h))
    if not in_gamut(lab):
        lo, hi = 0.0, c
        for _ in range(24):
            mid = (lo + hi) / 2
            if in_gamut(lch_to_lab((L, mid, h))):
                lo = mid
            else:
                hi = mid
        lab = lch_to_lab((L, lo, h))
    return rgb_to_hex(oklab_to_rgb(lab))


def hue_diff(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


# ----------------------------------------------------------------------------
# WCAG 대비
# ----------------------------------------------------------------------------

def _lum(rgb: Sequence[float]) -> float:
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = _lum(hex_to_rgb(a)), _lum(hex_to_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ----------------------------------------------------------------------------
# PNG 샘플링 (8bit RGB/RGBA, non-interlaced; 팔레트 PNG 지원)
# ----------------------------------------------------------------------------

def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)


def read_png_rgb(path: str, max_px: int = 40000) -> List[Tuple[int, int, int]]:
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG 가 아님 (JPEG 는 PNG 로 변환해 넣는다: macOS `sips -s format png in.jpg --out in.png`)")
    i = 8
    w = h = 0
    bit = ctype = interlace = 0
    idat = b""
    plte: List[Tuple[int, int, int]] = []
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + ln]
        if typ == b"IHDR":
            w, h, bit, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            plte = [(body[k], body[k + 1], body[k + 2]) for k in range(0, len(body), 3)]
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        i += 12 + ln
    if bit != 8 or interlace != 0:
        raise ValueError("8bit non-interlaced PNG 만 지원")
    ch = {2: 3, 6: 4, 0: 1, 4: 2, 3: 1}[ctype]
    raw = zlib.decompress(idat)
    stride = w * ch
    out: List[Tuple[int, int, int]] = []
    prev = bytearray(stride)
    step = max(1, int(math.sqrt(w * h / max_px)))
    pos = 0
    for y in range(h):
        f = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for x in range(stride):
            a = line[x - ch] if x >= ch else 0
            b = prev[x]
            c = prev[x - ch] if x >= ch else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                line[x] = (line[x] + _paeth(a, b, c)) & 255
        if y % step == 0:
            for x in range(0, w, step):
                k = x * ch
                if ctype == 3:
                    p = plte[line[k]] if line[k] < len(plte) else (0, 0, 0)
                    out.append(p)
                elif ctype in (0, 4):
                    out.append((line[k], line[k], line[k]))
                else:
                    if ch == 4 and line[k + 3] < 128:
                        continue
                    out.append((line[k], line[k + 1], line[k + 2]))
        prev = line
    return out


def sample_colors(path: str, n: int = 3) -> List[str]:
    """PNG 의 유채색 대표 hex (채도 > 0.06, 색상 칸 24개 중 상위 n, 각 칸의 중앙값 OKLCH)."""
    px = read_png_rgb(path)
    bins: Dict[int, List[Tuple[float, float, float]]] = {}
    for r, g, b in px:
        L, c, h = lab_to_lch(rgb_to_oklab((r / 255, g / 255, b / 255)))
        if c < 0.06 or L < 0.12 or L > 0.95:
            continue
        bins.setdefault(int(h // 15) % 24, []).append((L, c, h))
    ranked = sorted(bins.items(), key=lambda kv: -len(kv[1]))
    out: List[str] = []
    for _, vals in ranked[:n]:
        vals.sort(key=lambda v: v[1])
        L = sorted(v[0] for v in vals)[len(vals) // 2]
        c = sorted(v[1] for v in vals)[len(vals) // 2]
        h = sorted(v[2] for v in vals)[len(vals) // 2]
        out.append(lch_to_hex((L, c, h)))
    return out


# ----------------------------------------------------------------------------
# 수렴
# ----------------------------------------------------------------------------

BANDS = {"background": (0.0, 0.04), "neutral": (0.0, 0.02), "primary": (0.08, 0.15), "secondary": (0.06, 0.14), "accent": (0.15, 0.22)}


def _clamp_c(c: float, band: Tuple[float, float]) -> float:
    return max(band[0], min(band[1], c))


def derive(inputs: List[str], mode: str = "light", paper: bool = False) -> Dict[str, Any]:
    """inputs: hex 1~3개. 첫 색이 주조(primary) 후보. mode: light|dark 기본 배경."""
    if not inputs:
        raise ValueError("색이 필요하다 (hex 1~3개 또는 --image)")
    lch = [hex_to_lch(h) for h in inputs]
    notes: List[str] = []
    # primary: 첫 입력. 채도 밴드로 밀어 넣고 명도는 0.35~0.55 (흰 배경에서 글자·면 둘 다 가능)
    L0, c0, h0 = lch[0]
    pL = min(0.55, max(0.32, L0))
    pc = _clamp_c(c0, BANDS["primary"])
    if abs(pL - L0) > 0.02 or abs(pc - c0) > 0.005:
        notes.append(f"주조색 L {L0:.2f}→{pL:.2f}, C {c0:.3f}→{pc:.3f} (주조 밴드 0.08–0.15, 글자·면 겸용 명도)")
    primary = (pL, pc, h0)
    # secondary: 두 번째 입력이 있고 primary 와 충분히 다르면 사용, 아니면 색상 +150° 로 파생
    secondary: Optional[Tuple[float, float, float]] = None
    accent: Optional[Tuple[float, float, float]] = None
    rest = sorted(lch[1:], key=lambda v: -v[1])  # 채도 높은 순
    for L, c, h in rest:
        far = hue_diff(h, h0) >= 60 or abs(L - pL) >= 0.3
        if accent is None and far and c >= 0.12:
            accent = (min(0.72, max(0.45, L)), _clamp_c(c, BANDS["accent"]), h)
        elif secondary is None and far:
            secondary = (min(0.6, max(0.35, L)), _clamp_c(c, BANDS["secondary"]), h)
        else:
            notes.append(f"입력 {lch_to_hex((L, c, h))} 는 주조와 너무 가까워(ΔH {hue_diff(h, h0):.0f}°, ΔL {abs(L - pL):.2f}) 제외")
    if secondary is None:
        secondary = (0.5, 0.1, (h0 + 150) % 360)
        notes.append("보조색은 주조색 색상 +150° 에서 파생")
    if accent is None:
        # 따뜻한 쪽(주황~빨강 30~60°)이 주조와 60° 이상 떨어지면 그쪽, 아니면 보색
        cand = 45.0 if hue_diff(45.0, h0) >= 60 else (h0 + 180) % 360
        accent = (0.62, 0.18, cand)
        notes.append(f"강조색은 색상 {cand:.0f}° 에서 파생 (주조와 ΔH {hue_diff(cand, h0):.0f}°)")
    # 중성 램프: primary 색상으로 C 0.01 물들임
    tint_c = 0.012 if not paper else 0.02
    tint_h = h0 if not paper else 75.0
    ramp = {L: lch_to_hex((L, tint_c, tint_h)) for L in (0.15, 0.35, 0.65, 0.92, 0.98)}
    background = "FFFFFF" if (mode == "light" and not paper) else (lch_to_hex((0.975, 0.02, 75.0)) if paper else lch_to_hex((0.22, 0.03, h0)))
    dark_bg = lch_to_hex((0.24, 0.05, h0))
    colors = {
        "background": background,
        "surface": ramp[0.98] if not paper else lch_to_hex((0.955, 0.022, 75.0)),
        "surface_strong": ramp[0.92],
        "ink": ramp[0.15], "ink_muted": ramp[0.35], "ink_faint": ramp[0.65],
        "line": lch_to_hex((0.86, tint_c, tint_h)), "line_faint": ramp[0.92],
        "primary": lch_to_hex(primary), "primary_soft": lch_to_hex((0.92, min(0.05, pc * 0.4), h0)),
        "secondary": lch_to_hex(secondary),
        "accent": lch_to_hex(accent), "accent_soft": lch_to_hex((0.93, 0.05, accent[2])),
        "positive": lch_to_hex((0.55, 0.13, 150.0)), "warning": lch_to_hex((0.6, 0.14, 75.0)), "negative": lch_to_hex((0.55, 0.18, 25.0)), "info": lch_to_hex((0.55, 0.12, 240.0)),
        "on_primary": "FFFFFF", "dark_background": dark_bg, "on_dark": "FFFFFF",
    }
    if mode == "dark":
        colors.update({"ink": "FFFFFF", "ink_muted": lch_to_hex((0.82, 0.01, h0)), "ink_faint": lch_to_hex((0.65, 0.01, h0)), "surface": lch_to_hex((0.28, 0.03, h0)), "surface_strong": lch_to_hex((0.34, 0.03, h0)), "line": lch_to_hex((0.4, 0.02, h0)), "line_faint": lch_to_hex((0.3, 0.02, h0)), "primary": lch_to_hex((0.78, 0.12, h0)), "primary_soft": lch_to_hex((0.35, 0.06, h0)), "on_primary": lch_to_hex((0.2, 0.03, h0)), "dark_background": background})
    # 차트 팔레트: primary → 밝아지는 5단 (강조는 accent)
    chart = [lch_to_hex((pL, pc, h0)), lch_to_hex(secondary), lch_to_hex((0.68, pc * 0.6, h0)), lch_to_hex((0.8, pc * 0.35, h0)), lch_to_hex((0.88, 0.01, h0))]
    checks = check_tokens(colors)
    rationale = (f"주조 {colors['primary']} (OKLCH L {pL:.2f} C {pc:.3f} H {h0:.0f}°)를 60% 면·글자에, 보조 {colors['secondary']} 를 30% 보조 도형·차트 2번 시리즈에, "
                 f"강조 {colors['accent']} (ΔH {hue_diff(accent[2], h0):.0f}°)는 슬라이드당 한 곳 이하로 쓴다. 중성 램프는 주조 색상을 C {tint_c} 로 물들여 흑백이 아니라 한 가족으로 보이게 했다.")
    return {"ok": all(c["ok"] for c in checks), "inputs": inputs, "mode": mode, "design_tokens": {"colors": colors, "chart": {"palette": chart, "highlight": colors["accent"], "muted": chart[3], "positive": colors["positive"], "negative": colors["negative"], "gridline": colors["line_faint"]}}, "oklch": {"primary": [round(x, 3) for x in primary], "secondary": [round(x, 3) for x in secondary], "accent": [round(x, 3) for x in accent]}, "checks": checks, "notes": notes, "rationale": rationale}


def check_tokens(colors: Dict[str, str]) -> List[Dict[str, Any]]:
    """프로파일·spec 토큰에도 적용하는 팔레트 규칙."""
    out: List[Dict[str, Any]] = []

    def add(code, ok, msg, level="warning"):
        out.append({"code": code, "ok": ok, "level": "info" if ok else level, "message": msg})
    try:
        Lp, cp, hp = hex_to_lch(colors["primary"])
        La, ca, ha = hex_to_lch(colors["accent"])
        Lb, cb, hb = hex_to_lch(colors["background"])
        add("palette-band-accent", ca >= 0.10, f"강조 채도 C {ca:.3f} (밴드 0.15–0.22; 0.10 미만이면 강조가 안 보인다)")
        add("palette-band-background", cb <= 0.045, f"배경 채도 C {cb:.3f} (≤ 0.04)")
        neutral_primary = cp < 0.03  # 먹색 주조(에디토리얼): 색상 차이는 의미 없고 강조색 하나가 유채색이면 충분
        add("palette-band-primary", neutral_primary or BANDS["primary"][0] - 0.02 <= cp <= BANDS["primary"][1] + 0.03, f"주조 채도 C {cp:.3f} (밴드 0.08–0.15; 먹색 주조는 예외)")
        add("palette-distinct", neutral_primary or hue_diff(hp, ha) >= 60 or abs(Lp - La) >= 0.3, f"주조·강조 ΔH {hue_diff(hp, ha):.0f}° / ΔL {abs(Lp - La):.2f} (ΔH ≥ 60° 또는 ΔL ≥ 0.3)")
        for fg, bg, label, th in ((colors["ink"], colors["background"], "ink/background", 4.5), (colors["on_primary"], colors["primary"], "on_primary/primary", 4.5), (colors["primary"], colors["background"], "primary/background", 3.0)):
            r = contrast(fg, bg)
            add("contrast", r >= th, f"{label} {r:.2f}:1 (≥ {th})", level="error")
    except (KeyError, ValueError) as e:
        add("palette-input", False, f"토큰 누락/형식 오류: {e}", level="error")
    return out


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py palette")
    ap.add_argument("colors", nargs="*", help="hex 1~3개 (첫 색이 주조). 예: 003764 E4032E")
    ap.add_argument("--image", default=None, help="로고·사진 PNG 에서 대표색 추출")
    ap.add_argument("--mode", choices=["light", "dark"], default="light")
    ap.add_argument("--paper", action="store_true", help="따뜻한 종이색 배경 (편집·백서용)")
    ap.add_argument("--check", default=None, help="deck-spec.json 또는 프로파일 이름 — 기존 토큰을 규칙으로만 검사")
    ap.add_argument("-o", "--out", default=None, help="design_tokens 조각을 JSON 파일로 저장")
    a = ap.parse_args(argv)
    if a.check:
        from .specio import load_profiles, load_spec, resolve_tokens

        if a.check.endswith(".json"):
            spec, _ = load_spec(a.check)
            tok = resolve_tokens(spec)
        else:
            tok = load_profiles()[a.check]["tokens"]
        r = {"target": a.check, "checks": check_tokens(tok["colors"])}
        r["ok"] = all(c["ok"] or c["level"] != "error" for c in r["checks"])
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1
    inputs = list(a.colors)
    if a.image:
        inputs = sample_colors(a.image) + inputs
    try:
        r = derive(inputs, a.mode, a.paper)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r["design_tokens"], f, ensure_ascii=False, indent=2)
        r["saved"] = a.out
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1
