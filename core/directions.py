"""3방향 게이트 — 같은 spec 을 프로파일 2~3개로 '표지 + 가장 다른 본문 1~2장'만 빌드·렌더해 한 장의 비교 시트로 만든다.

전체 덱을 만들기 전에 방향(톤·밀도·색)을 사용자와 확정하는 산출물 기반 게이트다.
  pptx.py directions deck-spec.json --profiles consulting_grade,paperlogy_business,government_kr -o build/directions
  → directions.png (열 = 프로파일, 행 = 슬라이드), directions.json (열·행 대응, 파일 경로, 빌드 경고)
  pptx.py directions deck-spec.json --approve paperlogy_business --note "숫자가 크고 여백이 넓은 쪽" -o build/directions [--apply-to-spec]
  → direction-approved.md (선택·근거·사용자 발언·spec 해시) 기록, --apply-to-spec 이면 spec 의 route.style_profile 갱신

슬라이드 선택(--slides auto): cover → executive_summary → 첫 데이터 장(evidence_chart·small_multiples·hero_metric·big_number_stage) 순으로 최대 3장.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .render import _read_ppm, _write_png, _blit_label, to_pdf_libreoffice, to_pdf_powerpoint
from .specio import load_profiles

ROOT = Path(__file__).resolve().parent.parent
DATA_ARCH = ("evidence_chart", "small_multiples", "hero_metric", "big_number_stage", "kpi_bento", "comparison")


def pick_slides(spec: Dict[str, Any]) -> List[int]:
    slides = spec.get("slides", [])
    out: List[int] = []
    for want in (("cover",), ("executive_summary",), ("evidence_chart", "small_multiples"), DATA_ARCH):
        for s in slides:
            if s.get("archetype") in want and s.get("number") not in out:
                out.append(s["number"])
                break
        if len(out) >= 3:
            break
    if len(out) < 2:
        for s in slides:
            if s.get("number") not in out:
                out.append(s["number"])
            if len(out) >= 3:
                break
    return out[:3]


def _build(spec_path: Path, profile: str, only: List[int], out_pptx: Path, hooks: Optional[str]) -> Dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec.setdefault("route", {})["style_profile"] = profile
    tmp_spec = out_pptx.with_suffix(".spec.json")
    # 상대 경로 자산이 깨지지 않게 원본 spec 디렉터리를 기준으로 절대 경로화
    base = spec_path.parent.resolve()
    assets = spec.get("assets") or {}
    for k, v in list((assets.get("images") or {}).items()):
        if isinstance(v, str) and not os.path.isabs(v):
            assets["images"][k] = str((base / v).resolve())
    if isinstance(assets.get("logo"), str) and not os.path.isabs(assets["logo"]):
        assets["logo"] = str((base / assets["logo"]).resolve())
    tmp_spec.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    cmd = [os.environ.get("NODE", "node"), str(ROOT / "scripts" / "build.js"), str(tmp_spec), "-o", str(out_pptx), "--only", ",".join(str(n) for n in only)]
    if hooks:
        cmd += ["--hooks", hooks]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    try:
        r = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {"ok": False, "error": p.stderr[-500:]}
    except json.JSONDecodeError:
        r = {"ok": False, "error": p.stdout[-500:] + p.stderr[-500:]}
    return r


def _ppms(pdf: Path, work: Path, tag: str, dpi: int = 40) -> List[Path]:
    subprocess.run(["pdftoppm", "-r", str(dpi), str(pdf), str(work / f"{tag}")], check=True, capture_output=True)
    return sorted(work.glob(f"{tag}-*.ppm"), key=lambda p: int(p.stem.split("-")[-1]))


def _resize(w: int, h: int, px: bytes, tw: int) -> Tuple[int, int, bytes]:
    th = max(1, round(h * tw / w))
    buf = bytearray(tw * th * 3)
    for ty in range(th):
        sy = min(h - 1, ty * h // th)
        row = px[sy * w * 3:(sy + 1) * w * 3]
        for tx in range(tw):
            sx = min(w - 1, tx * w // tw)
            buf[(ty * tw + tx) * 3:(ty * tw + tx) * 3 + 3] = row[sx * 3:sx * 3 + 3]
    return tw, th, bytes(buf)


def directions(spec_path: str, profiles: List[str], out_dir: str, slides: Optional[List[int]] = None, engine: str = "libreoffice", hooks: Optional[str] = None, thumb_w: int = 420) -> Dict[str, Any]:
    sp = Path(spec_path).resolve()
    spec = json.loads(sp.read_text(encoding="utf-8"))
    known = load_profiles()
    bad = [p for p in profiles if p not in known]
    if bad:
        raise ValueError(f"알 수 없는 프로파일 {bad} (가능: {', '.join(known)})")
    only = slides or pick_slides(spec)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="pptx-directions-"))
    cols: List[Dict[str, Any]] = []
    try:
        for prof in profiles:
            pptx = out / f"{prof}.pptx"
            r = _build(sp, prof, only, pptx, hooks)
            entry: Dict[str, Any] = {"profile": prof, "label": known[prof].get("label"), "pptx": str(pptx) if pptx.exists() else None, "build_ok": r.get("ok", False), "warnings": [w.get("message") for w in r.get("warnings", [])][:6], "error": r.get("error")}
            if pptx.exists():
                pdf = to_pdf_powerpoint(pptx, work) if engine == "powerpoint" else to_pdf_libreoffice(pptx, work)
                entry["thumbs"] = [_resize(*_read_ppm(f), thumb_w) for f in _ppms(pdf, work, prof)]
            else:
                entry["thumbs"] = []
            cols.append(entry)
        nrow = max((len(c["thumbs"]) for c in cols), default=0)
        if not nrow:
            raise RuntimeError("렌더된 슬라이드가 없다 (빌드 실패 — directions.json 의 error 확인)")
        th = max(t[1] for c in cols for t in c["thumbs"])
        gap, label_h = 18, 24
        CW = len(cols) * thumb_w + (len(cols) + 1) * gap
        CH = nrow * (th + gap) + gap + label_h
        canvas = bytearray(b"\xf2\xf2\xf2" * (CW * CH))
        for ci, c in enumerate(cols):
            x0 = gap + ci * (thumb_w + gap)
            _blit_label(canvas, CW, x0, 4, str(ci + 1), scale=4)  # 열 번호 (프로파일 이름은 directions.json 참조)
            for ri, (tw, h, px) in enumerate(c["thumbs"]):
                y0 = label_h + gap + ri * (th + gap)
                for yy in range(y0 - 1, y0 + h + 1):
                    for xx in (x0 - 1, x0 + tw):
                        if 0 <= yy < CH and 0 <= xx < CW:
                            canvas[(yy * CW + xx) * 3:(yy * CW + xx) * 3 + 3] = b"\x99\x99\x99"
                for yy in range(h):
                    dst = ((y0 + yy) * CW + x0) * 3
                    canvas[dst:dst + tw * 3] = px[yy * tw * 3:(yy + 1) * tw * 3]
        sheet = out / "directions.png"
        _write_png(sheet, CW, CH, canvas)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    for c in cols:
        c.pop("thumbs", None)
    result = {
        "ok": all(c["build_ok"] for c in cols), "spec": str(sp), "spec_sha1": hashlib.sha1(sp.read_bytes()).hexdigest()[:12], "slides": only, "sheet": str(sheet),
        "columns": [{"column": i + 1, **c} for i, c in enumerate(cols)],
        "how_to_read": "directions.png 의 열 번호 = columns[].column. 각 열의 프로파일로 표지·요약·데이터 장을 같은 내용으로 만들었다. 사용자가 고르면 `directions --approve <profile> --note '사용자 발언'` 으로 기록한다.",
    }
    (out / "directions.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def approve(spec_path: str, out_dir: str, profile: str, note: str = "", apply_to_spec: bool = False) -> Dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sp = Path(spec_path)
    spec = json.loads(sp.read_text(encoding="utf-8"))
    known = load_profiles()
    if profile not in known:
        raise ValueError(f"알 수 없는 프로파일 {profile}")
    dj = out / "directions.json"
    sheet = ""
    candidates: List[str] = []
    if dj.exists():
        d = json.loads(dj.read_text(encoding="utf-8"))
        sheet = d.get("sheet", "")
        candidates = [c["profile"] for c in d.get("columns", [])]
    md = (
        f"# 방향 확정 (direction-approved)\n\n"
        f"- 일시: {time.strftime('%Y-%m-%d %H:%M')}\n- 명세: `{sp}` (sha1 {hashlib.sha1(sp.read_bytes()).hexdigest()[:12]})\n"
        f"- 후보: {', '.join(candidates) if candidates else '(기록 없음)'}\n- 비교 시트: `{sheet}`\n\n"
        f"## 선택\n\n- 프로파일: **{profile}** — {known[profile].get('label', '')}\n- 사용자 발언/근거: {note or '(없음)'}\n\n"
        f"## 이후 규칙\n\n- 전체 빌드는 이 프로파일로 진행하고, 톤·색·밀도를 바꾸려면 이 문서를 갱신한 뒤 재빌드한다.\n- 검수 단계(Phase 5)에서 토큰·구조를 바꾸지 않는다 (quality-rubric Don't-touch).\n"
    )
    (out / "direction-approved.md").write_text(md, encoding="utf-8")
    r: Dict[str, Any] = {"ok": True, "profile": profile, "record": str(out / "direction-approved.md")}
    if apply_to_spec:
        spec.setdefault("route", {})["style_profile"] = profile
        sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        r["spec_updated"] = str(sp)
    return r


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py directions")
    ap.add_argument("spec")
    ap.add_argument("--profiles", default=None, help="콤마 구분 2~3개 (기본: 현재 프로파일 + 성격이 다른 2개)")
    ap.add_argument("--slides", default="auto", help="auto 또는 1,4,7")
    ap.add_argument("-o", "--out", default="build/directions")
    ap.add_argument("--engine", choices=["libreoffice", "powerpoint"], default="libreoffice")
    ap.add_argument("--hooks", default=None)
    ap.add_argument("--approve", default=None, help="선택한 프로파일을 기록 (direction-approved.md)")
    ap.add_argument("--note", default="", help="사용자 발언·선택 근거")
    ap.add_argument("--apply-to-spec", action="store_true", help="--approve 시 spec 의 route.style_profile 도 갱신")
    a = ap.parse_args(argv)
    try:
        if a.approve:
            r = approve(a.spec, a.out, a.approve, a.note, a.apply_to_spec)
        else:
            spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
            cur = (spec.get("route") or {}).get("style_profile")
            if a.profiles:
                profs = [p.strip() for p in a.profiles.split(",") if p.strip()]
            else:
                alt = {"government_kr": ["public_policy", "editorial_report"], "public_policy": ["government_kr", "research_dense"], "consulting_grade": ["two_font_consulting", "paperlogy_business"], "paperlogy_business": ["consulting_grade", "institutional_pitch"], "executive_keynote": ["paperlogy_business", "two_font_consulting"]}
                profs = [cur] + [p for p in alt.get(cur, ["consulting_grade", "paperlogy_business"]) if p != cur]
                profs = [p for p in profs if p in load_profiles()][:3]
            slides = None if a.slides == "auto" else [int(x) for x in a.slides.split(",") if x.strip()]
            r = directions(a.spec, profs, a.out, slides, a.engine, a.hooks)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r.get("ok") else 1
