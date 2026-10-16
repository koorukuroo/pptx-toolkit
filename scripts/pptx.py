#!/usr/bin/env python3
"""pptx-toolkit CLI — 모든 커맨드는 JSON을 출력하고 실패 시 0이 아닌 코드로 끝난다.

  spec-check  deck-spec.json                      스키마·참조 검증 + 내용 규칙 lint (+ --ghost 고스트덱)
  lint        deck-spec.json                      (= spec-check)
  build       deck-spec.json -o out.pptx          deck-spec → pptx (node scripts/build.js) → check·inspect 자동
  check       deck.pptx                           패키지 무결성 게이트
  inspect     deck.pptx                           기하 검사 (경계·겹침·넘침 추정·글자 크기·이미지)
  render      deck.pptx [-o dir] [--engine]       PDF → PNG + contact.png
  bleed       deck.pptx                           렌더 픽셀 기반 넘침 검출 (여백 띠 오염)
  extract     deck.pptx [--format json]           텍스트 덤프
  inventory   deck.pptx                           편집 가능한 텍스트 도형 목록 (템플릿 채우기 1단계)
  replace     in.pptx out.pptx --map map.json     inventory 기반 텍스트 교체 (넘침 악화 시 거부)
  slides      in.pptx out.pptx --keep 1,3,3,5     슬라이드 복제·삭제·재배열 (1-based 순서 목록)
  fonts       [family ...]                        설치 폰트 확인·대체 제안
  unpack / pack                                   OOXML 직접 편집용
  profiles / archetypes                           사용 가능한 프로파일·아키타입 요약
  new-spec    -o deck-spec.json --profile X       빈 명세 스캐폴드
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import check as _check  # noqa: E402
from core import extract as _extract  # noqa: E402
from core import fonts as _fonts  # noqa: E402
from core import inspect as _inspect  # noqa: E402
from core import lint as _lint  # noqa: E402
from core import render as _render  # noqa: E402
from core import specio  # noqa: E402
from core.package import pack, unpack  # noqa: E402

USAGE = __doc__


def cmd_spec_check(argv):
    return _lint.main(argv)


def cmd_build(argv):
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py build")
    ap.add_argument("spec")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--hooks", default=None, help="커스텀 슬라이드용 JS 훅 파일")
    ap.add_argument("--only", default=None, help="일부 슬라이드만 (예: 1-3,7) — 샘플 게이트용")
    ap.add_argument("--no-lint", action="store_true")
    ap.add_argument("--min-font", type=float, default=None)
    a = ap.parse_args(argv)
    spec, errs = specio.load_spec(a.spec)
    if not a.no_lint:
        r = _lint.lint_spec(spec, errs)
        if not r["ok"]:
            print(json.dumps({"ok": False, "stage": "lint", "lint": r}, ensure_ascii=False, indent=2))
            return 1
    node = os.environ.get("NODE", "node")
    cmd = [node, str(ROOT / "scripts" / "build.js"), a.spec, "-o", a.out]
    if a.hooks:
        cmd += ["--hooks", a.hooks]
    if a.only:
        cmd += ["--only", a.only]
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        build = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    except json.JSONDecodeError:
        build = {"raw": p.stdout}
    if p.returncode != 0 or not Path(a.out).exists():
        print(json.dumps({"ok": False, "stage": "build", "build": build, "stderr": p.stderr[-4000:]}, ensure_ascii=False, indent=2))
        return 1
    chk = _check.check(a.out)
    mode = spec["metadata"]["delivery_mode"]
    tokens = specio.resolve_tokens(spec)
    tkey = "live" if mode == "live" else ("pre_read" if mode == "pre_read" else "hybrid")
    min_font = a.min_font if a.min_font is not None else tokens["type"][tkey]["body_min"]
    ins = _inspect.inspect_file(a.out, min_font=min_font, note_font=min(tokens["type"][tkey]["source"], 9), margin=min(tokens["canvas"]["margin"]["left"], tokens["canvas"]["margin"]["right"]) * 0.6)
    out = {"ok": chk["ok"] and ins["ok"], "output": a.out, "build": build, "check": chk, "inspect": {"ok": ins["ok"], "errors": ins["errors"], "warnings": ins["warnings"], "findings": ins["findings"]}}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 1


def cmd_bleed(argv):
    from core import bleed

    return bleed.main(argv)


def cmd_inventory(argv):
    from core import edit

    return edit.main_inventory(argv)


def cmd_replace(argv):
    from core import edit

    return edit.main_replace(argv)


def cmd_slides(argv):
    from core import edit

    return edit.main_slides(argv)


def cmd_template(argv):
    from core import template

    return template.main(argv)


def cmd_audit(argv):
    from core import audit

    return audit.main(argv)


def cmd_qa(argv):
    """check + inspect + bleed(선택) + audit 를 한 번에 → qa-report.json"""
    import argparse

    from core import audit

    ap = argparse.ArgumentParser(prog="pptx.py qa")
    ap.add_argument("pptx")
    ap.add_argument("--spec", default=None, help="deck-spec.json (있으면 lint 포함, 최소 글자 크기도 프로파일에서)")
    ap.add_argument("-o", "--out", default=None, help="qa-report.json 경로")
    ap.add_argument("--bleed", action="store_true", help="렌더 픽셀 넘침 검사 포함 (LibreOffice 필요, 느림)")
    ap.add_argument("--engine", default="libreoffice")
    ap.add_argument("--min-font", type=float, default=None)
    a = ap.parse_args(argv)
    report = {"file": a.pptx, "gates": {}}
    min_font, note_font, margin = a.min_font or 12.0, 9.0, 0.35
    if a.spec:
        spec, errs = specio.load_spec(a.spec)
        report["gates"]["lint"] = _lint.lint_spec(spec, errs)
        tokens = specio.resolve_tokens(spec)
        tkey = {"live": "live", "pre_read": "pre_read"}.get(spec["metadata"]["delivery_mode"], "hybrid")
        if a.min_font is None:
            min_font = tokens["type"][tkey]["body_min"]
        note_font = min(tokens["type"][tkey]["source"], 9)
        margin = min(tokens["canvas"]["margin"]["left"], tokens["canvas"]["margin"]["right"]) * 0.6
    report["gates"]["check"] = _check.check(a.pptx)
    report["gates"]["inspect"] = _inspect.inspect_file(a.pptx, min_font=min_font, note_font=note_font, margin=margin)
    report["gates"]["audit"] = audit.audit(a.pptx)
    if a.bleed:
        from core import bleed

        try:
            report["gates"]["bleed"] = bleed.bleed_check(a.pptx, a.engine)
        except Exception as e:  # noqa: BLE001
            report["gates"]["bleed"] = {"ok": None, "error": str(e)}
    hard = ["check", "inspect"] + (["lint"] if a.spec else []) + (["bleed"] if a.bleed and report["gates"]["bleed"].get("ok") is not None else [])
    report["ok"] = all(report["gates"][g]["ok"] for g in hard)
    report["summary"] = {g: {"ok": v.get("ok"), "errors": v.get("errors") if isinstance(v.get("errors"), int) else len(v.get("errors") or []), "warnings": v.get("warnings") if isinstance(v.get("warnings"), int) else len(v.get("warnings") or [])} for g, v in report["gates"].items()}
    report["rubric_hint"] = "기술 무결성(check·inspect·bleed)과 신뢰성(audit·lint 출처)은 자동 게이트. 전략·스토리라인·시각 위계는 render 결과를 보고 references/quality-rubric.md 로 채점한다"
    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "summary": report["summary"], "report": a.out} if a.out else report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def cmd_unpack(argv):
    if len(argv) != 2:
        print("usage: pptx.py unpack deck.pptx out_dir/")
        return 2
    out = unpack(argv[0], argv[1])
    print(json.dumps({"ok": True, "dir": str(out)}))
    return 0


def cmd_pack(argv):
    if len(argv) != 2:
        print("usage: pptx.py pack src_dir/ out.pptx")
        return 2
    out = pack(argv[0], argv[1])
    r = _check.check(str(out))
    print(json.dumps({"ok": r["ok"], "file": str(out), "check": r}, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1


def cmd_profiles(argv):
    profs = specio.load_profiles()
    out = {k: {"label": v["label"], "intent": v["intent"], "use_when": v["use_when"], "fonts": v["tokens"]["fonts"]["display"] + " / " + v["tokens"]["fonts"]["body"], "primary": v["tokens"]["colors"]["primary"], "accent": v["tokens"]["colors"]["accent"]} for k, v in profs.items()}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_archetypes(argv):
    arch = specio.load_archetypes()
    out = {k: {"purpose": v["purpose"], "title_required": v.get("title_required"), "max_items": v.get("max_items"), "max_chars": v.get("max_chars"), "content": v.get("content")} for k, v in arch.items()}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_new_spec(argv):
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py new-spec")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--profile", default="consulting_grade")
    ap.add_argument("--deck-type", default="consulting_executive")
    ap.add_argument("--mode", default="hybrid", choices=["live", "pre_read", "hybrid"])
    ap.add_argument("--title", default="(제목)")
    a = ap.parse_args(argv)
    spec = {
        "version": "0.2",
        "metadata": {"title": a.title, "subtitle": "", "organization": "", "presenter": "", "date": "", "audience": "(누가 보는가·직급)", "success_condition": "(이 자료를 본 뒤 청중이 이해하고 결정해야 할 것)", "delivery_mode": a.mode, "duration_minutes": 20, "language": "ko-KR", "confidentiality": ""},
        "route": {"deck_type": a.deck_type, "style_profile": a.profile, "brand_mode": "neutral", "communication_mode": "pyramid"},
        "design_tokens": {},
        "assets": {"images": {}},
        "evidence": [{"id": "E1", "claim": "(주장)", "kind": "fact", "confidence": "high", "source": "(출처·기간)"}],
        "slides": [
            {"number": 1, "archetype": "cover", "title": a.title, "content": {"subtitle": "", "organization": "", "date": ""}},
            {"number": 2, "archetype": "executive_summary", "title": "(핵심 결론을 문장으로)", "takeaway": "", "content": {"answer": "", "points": [{"heading": "", "detail": ""}], "decision": ""}, "speaker_notes": ""},
            {"number": 3, "archetype": "conclusion", "title": "(최종 답과 요청하는 결정)", "content": {"statement": "", "takeaways": [], "next_steps": [{"label": "", "owner": "", "when": ""}]}},
        ],
    }
    Path(a.out).write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "spec": a.out}))
    return 0


COMMANDS = {
    "spec-check": cmd_spec_check,
    "lint": cmd_spec_check,
    "build": cmd_build,
    "check": _check.main,
    "inspect": _inspect.main,
    "render": _render.main,
    "bleed": cmd_bleed,
    "extract": _extract.main,
    "inventory": cmd_inventory,
    "replace": cmd_replace,
    "slides": cmd_slides,
    "fonts": _fonts.main,
    "template": cmd_template,
    "audit": cmd_audit,
    "qa": cmd_qa,
    "unpack": cmd_unpack,
    "pack": cmd_pack,
    "profiles": cmd_profiles,
    "archetypes": cmd_archetypes,
    "new-spec": cmd_new_spec,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    cmd = sys.argv[1]
    fn = COMMANDS.get(cmd)
    if fn is None:
        print(json.dumps({"ok": False, "error": f"알 수 없는 커맨드 {cmd}", "commands": sorted(COMMANDS)}, ensure_ascii=False))
        return 2
    try:
        return fn(sys.argv[2:]) or 0
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "command": cmd, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
