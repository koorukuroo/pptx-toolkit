"""단조로움·변주 감사 — 렌더 결과(PDF)에서 슬라이드 지문을 뽑아 '같은 장이 반복되는 덱'과 '전에 만든 덱과 똑같은 덱'을 잡는다.

지문(슬라이드당):
  bg          배경 분류 light | dark | surface (가장자리 픽셀 밝기 중앙값)
  hues        유채색 픽셀의 색상 히스토그램 12칸 (채도 > 0.25) → 상위 2개 색상 칸
  layout      32×20 격자의 잉크 밀도 벡터 (배경과 40 이상 차이 나는 픽셀 비율)

검사:
  layout-repeat       인접 슬라이드의 본문 영역 레이아웃 상관 > 0.6 이면서 배경이 같음 — warning (사람이 판단)
  layout-monotone     덱 전체 평균 쌍 상관 > 0.5 — warning
  no-contrast-slide   8장 이상인데 비(非)밝은 배경이 한 장도 없음 — info (표지·구분·강조 한 장은 어둡게)
  palette-drift       한 슬라이드의 상위 색상이 덱 공통 색상과 다름 (한 장만 튀는 색) — warning
  archetype-monotone  (--spec) 한 아키타입이 본문의 50% 초과 — warning / 종류 7개 초과 — info
장부(--record/--ledger): 덱 지문을 ~/.cache/pptx-toolkit/ledger.json 에 남기고, 새 덱이 이전 덱과 상관 > 0.9·팔레트 동일이면 info.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .render import _read_ppm, find_soffice, to_pdf_libreoffice, to_pdf_powerpoint

CACHE_DIR = Path(os.environ.get("PPTX_TOOLKIT_CACHE", Path.home() / ".cache" / "pptx-toolkit"))
LEDGER = CACHE_DIR / "ledger.json"
GX, GY = 32, 20


def _rgb_to_hsl(r: int, g: int, b: int) -> Tuple[float, float, float]:
    r1, g1, b1 = r / 255, g / 255, b / 255
    mx, mn = max(r1, g1, b1), min(r1, g1, b1)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r1:
        h = ((g1 - b1) / d) % 6
    elif mx == g1:
        h = (b1 - r1) / d + 2
    else:
        h = (r1 - g1) / d + 4
    return h * 60, s, l


def fingerprint_page(W: int, H: int, px: bytes) -> Dict[str, Any]:
    # 배경: 가장자리 2px 띠의 밝기 중앙값
    edge: List[int] = []
    for y in list(range(0, min(2, H))) + list(range(max(0, H - 2), H)):
        row = px[y * W * 3:(y + 1) * W * 3]
        for x in range(W):
            edge.append((row[x * 3] + row[x * 3 + 1] + row[x * 3 + 2]) // 3)
    for y in range(H):
        row = px[y * W * 3:(y + 1) * W * 3]
        for x in list(range(0, min(2, W))) + list(range(max(0, W - 2), W)):
            edge.append((row[x * 3] + row[x * 3 + 1] + row[x * 3 + 2]) // 3)
    edge.sort()
    bgl = edge[len(edge) // 2] if edge else 255
    bg = "light" if bgl > 215 else "dark" if bgl < 90 else "surface"
    hues: Counter = Counter()
    grid = [0.0] * (GX * GY)
    counts = [0] * (GX * GY)
    for y in range(H):
        row = px[y * W * 3:(y + 1) * W * 3]
        gy = min(GY - 1, y * GY // H)
        for x in range(W):
            r, g, b = row[x * 3], row[x * 3 + 1], row[x * 3 + 2]
            lum = (r + g + b) // 3
            gi = gy * GX + min(GX - 1, x * GX // W)
            counts[gi] += 1
            if abs(lum - bgl) > 40:
                grid[gi] += 1
            h, s, l = _rgb_to_hsl(r, g, b)
            if s > 0.25 and 0.15 < l < 0.85:
                hues[int(h // 30) % 12] += 1
    layout = [grid[i] / counts[i] if counts[i] else 0.0 for i in range(GX * GY)]
    # 본문 영역만(제목 띠 위 20%·푸터 띠 아래 10% 제외) — 제목·푸터는 모든 장에 같으므로 상관을 부풀린다
    body = [v for row in range(4, 18) for v in layout[row * GX:(row + 1) * GX]]
    top = [h for h, _ in hues.most_common(2)]
    ink = sum(grid) / max(1, sum(counts))
    return {"bg": bg, "hues": top, "layout": layout, "layout_body": body, "ink": round(ink, 4), "chroma": round(sum(hues.values()) / max(1, W * H), 4)}


def _corr(a: List[float], b: List[float]) -> float:
    n = len(a)
    if n == 0 or n != len(b):
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    if sa < 1e-9 or sb < 1e-9:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def fingerprint_pdf(pdf: Path, dpi: int = 24) -> List[Dict[str, Any]]:
    if not shutil.which("pdftoppm"):
        raise RuntimeError("pdftoppm(poppler) 필요")
    tmp = Path(tempfile.mkdtemp(prefix="pptx-variety-"))
    try:
        subprocess.run(["pdftoppm", "-r", str(dpi), str(pdf), str(tmp / "v")], check=True, capture_output=True)
        files = sorted(tmp.glob("v-*.ppm"), key=lambda p: int(p.stem.split("-")[-1]))
        out = []
        for i, f in enumerate(files, start=1):
            W, H, px = _read_ppm(f)
            fp = fingerprint_page(W, H, px)
            fp["slide"] = i
            out.append(fp)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def analyze(fps: List[Dict[str, Any]], spec: Optional[Dict[str, Any]] = None, corr_threshold: float = 0.6) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []

    def add(code, level, msg, slide=None, **kw):
        d = {"code": code, "level": level, "message": msg}
        if slide is not None:
            d["slide"] = slide
        d.update(kw)
        findings.append(d)

    n = len(fps)
    pair_corrs: List[float] = []
    for i in range(1, n):
        a, b = fps[i - 1], fps[i]
        c = _corr(a["layout_body"], b["layout_body"])
        pair_corrs.append(c)
        if c > corr_threshold and a["bg"] == b["bg"] and a["ink"] > 0.01 and b["ink"] > 0.01:
            add("layout-repeat", "warning", f"슬라이드 {i}·{i + 1} 레이아웃 상관 {c:.2f} > {corr_threshold} — 연속된 같은 구성. 형식을 바꾸거나 합친다", i + 1, corr=round(c, 3))
    all_corrs = [_corr(fps[i]["layout_body"], fps[j]["layout_body"]) for i in range(n) for j in range(i + 1, n)]
    mean_corr = sum(all_corrs) / len(all_corrs) if all_corrs else 0.0
    if n >= 6 and mean_corr > 0.5:
        add("layout-monotone", "warning", f"덱 평균 레이아웃 상관 {mean_corr:.2f} > 0.5 — 거의 모든 장이 같은 구성")
    bgs = Counter(f["bg"] for f in fps)
    if n >= 8 and bgs.get("light", 0) == n:
        add("no-contrast-slide", "info", "8장 이상인데 어두운·면 배경 슬라이드가 없음 — 표지·구분·핵심 한 장은 배경을 바꿔 리듬을 준다")
    deck_hues = Counter(h for f in fps for h in f["hues"])
    common = {h for h, _ in deck_hues.most_common(3)}
    for f in fps:
        if f["hues"] and f["chroma"] > 0.02 and not (set(f["hues"]) & common):
            add("palette-drift", "warning", f"슬라이드 {f['slide']} 의 주요 색상(칸 {f['hues']})이 덱 공통 색상(칸 {sorted(common)})과 다름 — 한 장만 튀는 색", f["slide"])
    if spec:
        body = [s for s in spec.get("slides", []) if s.get("archetype") not in ("cover", "section_divider", "agenda", "appendix") and not s.get("appendix")]
        ac = Counter(s.get("archetype") for s in body)
        if body and len(body) >= 6:
            top, cnt = ac.most_common(1)[0]
            if cnt / len(body) > 0.5:
                add("archetype-monotone", "warning", f"본문 {len(body)}장 중 '{top}' {cnt}장 (>50%) — 데이터는 evidence_chart, 선택은 comparison, 순서는 process 로 나눈다")
        if len(ac) > 7:
            add("archetype-monotone", "info", f"아키타입 종류 {len(ac)}개 — 한 덱은 4~6종이면 충분하다 (일관성)")
    warnings = [f for f in findings if f["level"] == "warning"]
    return {"ok": True, "slides": n, "mean_layout_corr": round(mean_corr, 3), "backgrounds": dict(bgs), "hue_bins": {str(k): v for k, v in deck_hues.most_common(5)}, "warnings": len(warnings), "findings": findings}


def deck_signature(fps: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(fps) or 1
    mean_layout = [sum(f["layout"][i] for f in fps) / n for i in range(GX * GY)] if fps else []
    hues = Counter(h for f in fps for h in f["hues"])
    return {"layout": mean_layout, "hues": sorted(h for h, _ in hues.most_common(3)), "slides": len(fps)}


def ledger_compare(sig: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not LEDGER.exists():
        return []
    try:
        entries = json.loads(LEDGER.read_text(encoding="utf-8")).get("decks", [])
    except Exception:  # noqa: BLE001
        return []
    out = []
    for e in entries:
        c = _corr(sig["layout"], e.get("layout", []))
        if c > 0.9 and set(sig["hues"]) == set(e.get("hues", [])):
            out.append({"code": "looks-like-previous", "level": "info", "message": f"이전 덱 '{e.get('name')}'({e.get('at', '')[:10]}) 과 구성·팔레트가 거의 같음 (상관 {c:.2f}) — 같은 고객·같은 양식이 아니라면 변주를 준다", "name": e.get("name"), "corr": round(c, 3)})
    return out


def ledger_record(name: str, sig: Dict[str, Any]) -> None:
    data = {"decks": []}
    if LEDGER.exists():
        try:
            data = json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {"decks": []}
    data["decks"] = [e for e in data["decks"] if e.get("name") != name][-49:] + [dict(sig, name=name, at=time.strftime("%Y-%m-%dT%H:%M:%S"))]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def variety(target: str, spec_path: Optional[str] = None, engine: str = "libreoffice", record: Optional[str] = None, ledger: bool = True) -> Dict[str, Any]:
    p = Path(target)
    work: Optional[Path] = None
    try:
        if p.suffix.lower() == ".pdf":
            pdf = p
        elif p.suffix.lower() == ".pptx":
            work = Path(tempfile.mkdtemp(prefix="pptx-variety-"))
            pdf = to_pdf_powerpoint(p.resolve(), work) if engine == "powerpoint" else to_pdf_libreoffice(p.resolve(), work)
        else:
            raise ValueError("대상은 .pptx 또는 render 가 만든 .pdf")
        fps = fingerprint_pdf(pdf)
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)
    spec = None
    if spec_path:
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    r = analyze(fps, spec)
    sig = deck_signature(fps)
    if ledger:
        r["findings"].extend(ledger_compare(sig))
    if record:
        ledger_record(record, sig)
        r["recorded"] = record
    r["file"] = target
    r["per_slide"] = [{"slide": f["slide"], "bg": f["bg"], "hues": f["hues"], "ink": f["ink"]} for f in fps]
    return r


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py variety")
    ap.add_argument("target", help="deck.pptx 또는 render 출력의 .pdf")
    ap.add_argument("--spec", default=None)
    ap.add_argument("--engine", choices=["libreoffice", "powerpoint"], default="libreoffice")
    ap.add_argument("--record", default=None, help="이 덱의 지문을 장부에 '이름'으로 기록 (납품 시)")
    ap.add_argument("--no-ledger", action="store_true", help="이전 덱과 비교하지 않음")
    a = ap.parse_args(argv)
    try:
        r = variety(a.target, a.spec, a.engine, a.record, not a.no_ledger)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0
