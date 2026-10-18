"""설치된 TTF/OTF/TTC에서 실제 글자 폭·행간을 읽는다 (표준 라이브러리만).

넘침 추정이 '한글 1.0em' 같은 평균 계수 대신 폰트의 hmtx 폭을 쓰도록 한다. scripts/lib/fontmetrics.js 와 같은 알고리즘·
같은 캐시 파일(~/.cache/pptx-toolkit/font-index.json)을 쓰므로 빌드(JS)와 inspect(Python)의 추정치가 일치한다.

  index()                     폰트 디렉터리의 파일 → {family, subfamily, weight, italic} 색인 (mtime 캐시)
  find(family, bold)          가족 이름·굵기에 맞는 파일 경로 (없으면 None)
  Font(path, [ttc_index])     unitsPerEm, 글자 폭(em), 행간(em: hhea ascender-descender+lineGap)
  width_em(ch, family, bold)  글자 폭 em (폰트 없거나 글리프 없으면 휴리스틱 계수)
  line_height_em(family, bold)

폰트 파일을 읽기만 하며 복사·동봉하지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import struct
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .fonts import font_dirs

CACHE_DIR = Path(os.environ.get("PPTX_TOOLKIT_CACHE", Path.home() / ".cache" / "pptx-toolkit"))
INDEX_PATH = CACHE_DIR / "font-index.json"
INDEX_VERSION = 1

# 글리프가 없거나 폰트를 못 찾을 때 쓰는 평균 계수 (JS와 동일)
def heuristic_em(ch: str) -> float:
    o = ord(ch)
    if ch == " ":
        return 0.3
    if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F or 0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF:
        return 1.0
    if ch.isdigit():
        return 0.58
    if ch.isupper():
        return 0.68
    if ch in ".,:;'|!il":
        return 0.3
    return 0.55


# ----------------------------------------------------------------------------
# 파일 파서
# ----------------------------------------------------------------------------

def _u16(b: bytes, o: int) -> int:
    return struct.unpack_from(">H", b, o)[0]


def _s16(b: bytes, o: int) -> int:
    return struct.unpack_from(">h", b, o)[0]


def _u32(b: bytes, o: int) -> int:
    return struct.unpack_from(">I", b, o)[0]


def _decode_name(data: bytes, platform_id: int, encoding_id: int) -> str:
    try:
        if platform_id == 3 or (platform_id == 0):
            return data.decode("utf-16-be", errors="ignore")
        return data.decode("latin-1", errors="ignore")
    except Exception:  # noqa: BLE001
        return ""


class Font:
    """단일 폰트(TTC면 index 지정). 필요한 테이블만 읽는다: head, hhea, hmtx, cmap, name, OS/2."""

    def __init__(self, path: str, ttc_index: int = 0):
        self.path = path
        self.ttc_index = ttc_index
        with open(path, "rb") as f:
            self._data = f.read()
        d = self._data
        tag = d[:4]
        offset = 0
        if tag == b"ttcf":
            n = _u32(d, 8)
            if ttc_index >= n:
                raise ValueError("ttc index out of range")
            offset = _u32(d, 12 + 4 * ttc_index)
        num_tables = _u16(d, offset + 4)
        self.tables: Dict[str, Tuple[int, int]] = {}
        for i in range(num_tables):
            rec = offset + 12 + 16 * i
            t = d[rec:rec + 4].decode("latin-1")
            self.tables[t] = (_u32(d, rec + 8), _u32(d, rec + 12))
        if "head" not in self.tables or "hmtx" not in self.tables or "cmap" not in self.tables:
            raise ValueError("필수 테이블 없음")
        ho, _ = self.tables["head"]
        self.units_per_em = _u16(d, ho + 18) or 1000
        self._cmap: Optional[Dict[int, int]] = None
        self._widths: Optional[List[int]] = None
        self._line_height: Optional[float] = None
        self._names: Optional[Dict[int, str]] = None

    # --- name ---------------------------------------------------------------
    def names(self) -> Dict[int, str]:
        if self._names is not None:
            return self._names
        out: Dict[int, str] = {}
        if "name" in self.tables:
            d = self._data
            no, _ = self.tables["name"]
            count = _u16(d, no + 2)
            str_off = no + _u16(d, no + 4)
            best: Dict[int, Tuple[int, str]] = {}
            for i in range(count):
                rec = no + 6 + 12 * i
                pid, eid, lid, nid, ln, so = struct.unpack_from(">HHHHHH", d, rec)
                raw = d[str_off + so:str_off + so + ln]
                s = _decode_name(raw, pid, eid).strip("\x00").strip()
                if not s:
                    continue
                # 우선순위: Windows 영어(3,1,0x409) > 기타 Windows > Mac 영어 > 나머지
                score = 4 if (pid == 3 and lid == 0x409) else 3 if pid == 3 else 2 if (pid == 1 and lid == 0) else 1
                if nid not in best or score > best[nid][0]:
                    best[nid] = (score, s)
            out = {k: v[1] for k, v in best.items()}
        self._names = out
        return out

    @property
    def family(self) -> str:
        n = self.names()
        return n.get(16) or n.get(1) or Path(self.path).stem

    @property
    def subfamily(self) -> str:
        n = self.names()
        return n.get(17) or n.get(2) or "Regular"

    def weight(self) -> int:
        if "OS/2" in self.tables:
            o, _ = self.tables["OS/2"]
            try:
                return _u16(self._data, o + 4)
            except struct.error:
                pass
        return 400

    def italic(self) -> bool:
        if "OS/2" in self.tables:
            o, _ = self.tables["OS/2"]
            try:
                return bool(_u16(self._data, o + 62) & 1)
            except struct.error:
                pass
        ho, _ = self.tables["head"]
        return bool(_u16(self._data, ho + 44) & 2)

    # --- metrics ------------------------------------------------------------
    def _load_widths(self) -> List[int]:
        if self._widths is not None:
            return self._widths
        d = self._data
        hh, _ = self.tables["hhea"]
        n = _u16(d, hh + 34)
        hm, _ = self.tables["hmtx"]
        self._widths = [_u16(d, hm + 4 * i) for i in range(n)]
        return self._widths

    def _load_cmap(self) -> Dict[int, int]:
        if self._cmap is not None:
            return self._cmap
        d = self._data
        co, _ = self.tables["cmap"]
        n = _u16(d, co + 2)
        best: Optional[Tuple[int, int]] = None  # (score, offset)
        for i in range(n):
            rec = co + 4 + 8 * i
            pid, eid, off = _u16(d, rec), _u16(d, rec + 2), _u32(d, rec + 4)
            fmt = _u16(d, co + off)
            score = 0
            if pid == 3 and eid == 10 and fmt == 12:
                score = 5
            elif pid == 0 and fmt == 12:
                score = 4
            elif pid == 3 and eid == 1 and fmt == 4:
                score = 3
            elif pid == 0 and fmt == 4:
                score = 2
            if score and (best is None or score > best[0]):
                best = (score, co + off)
        cmap: Dict[int, int] = {}
        if best:
            o = best[1]
            fmt = _u16(d, o)
            if fmt == 4:
                segx2 = _u16(d, o + 6)
                seg = segx2 // 2
                ends = o + 14
                starts = ends + segx2 + 2
                deltas = starts + segx2
                ranges = deltas + segx2
                for s in range(seg):
                    end = _u16(d, ends + 2 * s)
                    start = _u16(d, starts + 2 * s)
                    delta = _u16(d, deltas + 2 * s)
                    ro = _u16(d, ranges + 2 * s)
                    if start > end or start == 0xFFFF:
                        continue
                    for cp in range(start, end + 1):
                        if ro == 0:
                            g = (cp + delta) & 0xFFFF
                        else:
                            gi = ranges + 2 * s + ro + 2 * (cp - start)
                            if gi + 2 > len(d):
                                continue
                            g = _u16(d, gi)
                            if g:
                                g = (g + delta) & 0xFFFF
                        if g:
                            cmap[cp] = g
            elif fmt == 12:
                ngroups = _u32(d, o + 12)
                for gi in range(ngroups):
                    rec = o + 16 + 12 * gi
                    sc, ec, sg = _u32(d, rec), _u32(d, rec + 4), _u32(d, rec + 8)
                    if ec - sc > 70000:
                        continue
                    for cp in range(sc, ec + 1):
                        cmap[cp] = sg + (cp - sc)
        self._cmap = cmap
        return cmap

    def glyph_width_em(self, ch: str) -> Optional[float]:
        g = self._load_cmap().get(ord(ch))
        if g is None:
            return None
        w = self._load_widths()
        if not w:
            return None
        adv = w[g] if g < len(w) else w[-1]
        return adv / self.units_per_em

    def line_height_em(self) -> float:
        """PowerPoint '1줄' 높이. hhea(ascender - descender + lineGap)와 OS/2 win(ascent+descent) 중 큰 값."""
        if self._line_height is not None:
            return self._line_height
        d = self._data
        hh, _ = self.tables["hhea"]
        asc, desc, gap = _s16(d, hh + 4), _s16(d, hh + 6), _s16(d, hh + 8)
        lh = (asc - desc + gap) / self.units_per_em
        if "OS/2" in self.tables:
            o, _ = self.tables["OS/2"]
            try:
                win_asc, win_desc = _u16(d, o + 74), _u16(d, o + 76)
                lh = max(lh, (win_asc + win_desc) / self.units_per_em)
            except struct.error:
                pass
        self._line_height = lh if 0.8 <= lh <= 2.5 else 1.2
        return self._line_height


# ----------------------------------------------------------------------------
# 색인
# ----------------------------------------------------------------------------

def _scan_file(path: Path) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    try:
        with open(path, "rb") as f:
            head = f.read(16)
        count = 1
        if head[:4] == b"ttcf":
            count = min(_u32(head, 8), 32)
        for i in range(count):
            try:
                ft = Font(str(path), i)
                out.append({"path": str(path), "index": i, "family": ft.family, "subfamily": ft.subfamily, "weight": ft.weight(), "italic": ft.italic()})
            except Exception:  # noqa: BLE001
                continue
    except OSError:
        pass
    return out


def index(refresh: bool = False) -> List[Dict[str, object]]:
    """설치 폰트 색인. 파일 mtime이 같으면 캐시를 재사용한다."""
    cache: Dict[str, object] = {}
    if not refresh and INDEX_PATH.exists():
        try:
            cache = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            if cache.get("version") != INDEX_VERSION:
                cache = {}
        except Exception:  # noqa: BLE001
            cache = {}
    files: Dict[str, Dict[str, object]] = dict(cache.get("files", {}))  # type: ignore[arg-type]
    seen = set()
    changed = False
    for d in font_dirs():
        for p in d.rglob("*"):
            if p.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            key = str(p)
            seen.add(key)
            try:
                mt = p.stat().st_mtime
            except OSError:
                continue
            ent = files.get(key)
            if ent and abs(float(ent.get("mtime", 0)) - mt) < 1e-6:
                continue
            files[key] = {"mtime": mt, "fonts": _scan_file(p)}
            changed = True
    for k in list(files):
        if k not in seen:
            files.pop(k)
            changed = True
    if changed or not cache:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            INDEX_PATH.write_text(json.dumps({"version": INDEX_VERSION, "built": time.time(), "files": files}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    out: List[Dict[str, object]] = []
    for ent in files.values():
        out.extend(ent.get("fonts", []))  # type: ignore[arg-type]
    return out


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(s)).lower()


_FIND_CACHE: Dict[Tuple[str, bool], Optional[Tuple[str, int]]] = {}


def find(family: str, bold: bool = False) -> Optional[Tuple[str, int]]:
    """가족 이름·굵기에 가장 가까운 (path, ttc_index). 굵기: bold → 600~800 중 700에 가까운 것, 아니면 400 근처."""
    key = (family or "", bool(bold))
    if key in _FIND_CACHE:
        return _FIND_CACHE[key]
    want = _norm(family)
    cands = []
    for ent in index():
        fam = _norm(str(ent["family"]))
        if fam == want or fam.startswith(want) or want.startswith(fam) and len(fam) >= 4:
            if ent.get("italic"):
                continue
            cands.append(ent)
    if not cands:
        _FIND_CACHE[key] = None
        return None
    target = 700 if bold else 400
    cands.sort(key=lambda e: (abs(int(e.get("weight", 400)) - target), 0 if _norm(str(e["family"])) == want else 1, str(e["path"])))
    best = cands[0]
    res = (str(best["path"]), int(best.get("index", 0)))
    _FIND_CACHE[key] = res
    return res


_FONT_CACHE: Dict[Tuple[str, int], Optional[Font]] = {}


def load(family: str, bold: bool = False) -> Optional[Font]:
    loc = find(family, bold)
    if not loc:
        return None
    if loc not in _FONT_CACHE:
        try:
            _FONT_CACHE[loc] = Font(loc[0], loc[1])
        except Exception:  # noqa: BLE001
            _FONT_CACHE[loc] = None
    return _FONT_CACHE[loc]


def width_em(ch: str, family: Optional[str], bold: bool = False) -> float:
    if family:
        ft = load(family, bold)
        if ft is not None:
            w = ft.glyph_width_em(ch)
            if w is not None:
                return w
    return heuristic_em(ch)


def line_height_em(family: Optional[str], bold: bool = False) -> float:
    if family:
        ft = load(family, bold)
        if ft is not None:
            return ft.line_height_em()
    return 1.2


def text_width_in(text: str, pt: float, family: Optional[str], bold: bool = False) -> float:
    return sum(width_em(c, family, bold) for c in text) * pt / 72


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py fontmetrics")
    ap.add_argument("families", nargs="*", default=["Paperlogy", "Pretendard"])
    ap.add_argument("--refresh", action="store_true", help="색인 다시 만들기")
    ap.add_argument("--sample", default="행사마다 새로 만들던 AI 체험을 Platform 2026")
    a = ap.parse_args(argv)
    if a.refresh:
        index(refresh=True)
    out = {}
    for fam in a.families:
        for bold in (False, True):
            loc = find(fam, bold)
            ft = load(fam, bold)
            hangul = [ft.glyph_width_em(c) for c in "가나다라마바사아자차" if ft] if ft else []
            latin = [ft.glyph_width_em(c) for c in "abcdefghijklmnopqrstuvwxyz" if ft] if ft else []
            out[f"{fam}{' Bold' if bold else ''}"] = {
                "file": loc[0] if loc else None,
                "line_height_em": round(ft.line_height_em(), 3) if ft else None,
                "hangul_avg_em": round(sum(w for w in hangul if w) / max(1, len([w for w in hangul if w])), 3) if hangul else None,
                "lower_avg_em": round(sum(w for w in latin if w) / max(1, len([w for w in latin if w])), 3) if latin else None,
                "sample_width_in_at_18pt": round(text_width_in(a.sample, 18, fam, bold), 2),
            }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0
