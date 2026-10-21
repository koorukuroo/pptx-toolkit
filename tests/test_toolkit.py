"""pptx-toolkit 회귀 테스트 — 예제 5종을 빌드해 게이트·추정기·감사·편집·팔레트·상속을 검증한다.

실행: python3 -m unittest discover -s tests -v   (Node.js + node_modules/pptxgenjs 필요)
렌더(LibreOffice)가 필요한 테스트는 soffice가 없으면 건너뛴다.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import audit, check, edit, extract, fontmetrics, inherit, inspect, lint, palette, specio, template  # noqa: E402
from core.render import find_soffice  # noqa: E402

EXAMPLES = {
    "consulting": ("examples/consulting-kiosk-strategy.spec.json", []),
    "gov": ("examples/gov-ai-platform-briefing.spec.json", []),
    "proposal": ("examples/proposal-shipyard-ax.spec.json", ["--hooks", "examples/proposal-hooks.js"]),
    "showcase": ("examples/archetype-showcase.spec.json", []),
    "rfp": ("examples/proposal-rfp.spec.json", []),
    "rnd": ("examples/rnd-plan.spec.json", []),
    "cards": ("examples/solution-cards.spec.json", []),
    "brief": ("examples/briefing-mono.spec.json", []),
    "lecture": ("examples/lecture-story.spec.json", []),
}

_TMP = Path(tempfile.mkdtemp(prefix="pptx-toolkit-test-"))
_BUILT: dict[str, Path] = {}


def build(name: str, profile: str | None = None) -> Path:
    key = f"{name}:{profile or ''}"
    if key in _BUILT:
        return _BUILT[key]
    spec_path, extra = EXAMPLES[name]
    src = ROOT / spec_path
    if profile:
        spec = json.loads(src.read_text(encoding="utf-8"))
        spec["route"]["style_profile"] = profile
        for k, v in list((spec.get("assets", {}).get("images") or {}).items()):
            spec["assets"]["images"][k] = str((src.parent / v).resolve())
        src = _TMP / f"{name}-{profile}.spec.json"
        src.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    out = _TMP / f"{name}-{profile or 'default'}.pptx"
    r = subprocess.run(["node", str(ROOT / "scripts" / "build.js"), str(src), "-o", str(out), *extra], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    summary = json.loads(r.stdout.strip().splitlines()[-1])
    assert summary["ok"], summary
    _BUILT[key] = out
    return out


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


class SpecAndLint(unittest.TestCase):
    def test_examples_pass_lint(self):
        for name, (spec_path, _) in EXAMPLES.items():
            spec, errs = specio.load_spec(str(ROOT / spec_path))
            self.assertEqual(errs, [], name)
            r = lint.lint_spec(spec, errs)
            self.assertTrue(r["ok"], (name, [f for f in r["findings"] if f["level"] == "error"]))
            self.assertEqual(len(r["ghost_deck"]), len(spec["slides"]))

    def test_lint_catches_topic_title_and_thanks(self):
        spec, _ = specio.load_spec(str(ROOT / EXAMPLES["consulting"][0]))
        spec["slides"][1]["title"] = "시장 현황"
        spec["slides"][-1] = {"number": 99, "archetype": "statement", "title": "감사합니다", "content": {"statement": "감사합니다"}}
        r = lint.lint_spec(spec, specio.validate_spec(spec))
        codes = {f["code"] for f in r["findings"] if f["level"] == "error"}
        self.assertIn("title-topic-label", codes)
        self.assertIn("thank-you-ending", codes)
        self.assertFalse(r["ok"])

    def test_lint_contrast(self):
        spec, _ = specio.load_spec(str(ROOT / EXAMPLES["gov"][0]))
        spec["design_tokens"] = {"colors": {"ink": "CCCCCC"}}
        r = lint.lint_spec(spec, specio.validate_spec(spec))
        self.assertIn("contrast-low", {f["code"] for f in r["findings"]})

    def test_lint_anti_slop_and_roles(self):
        spec, _ = specio.load_spec(str(ROOT / EXAMPLES["consulting"][0]))
        s = spec["slides"][2]
        s["content"]["context"] = "🚀 압도적 10배 빠른 성능 (p.3)"
        s["content"]["metrics"][0]["label"] = "- 수동 글머리"
        s.pop("evidence_ids", None)
        spec["slides"][1]["role"] = "takeaway"  # proof·hook 없음
        spec["design_tokens"] = {"fonts": {"weights": {"title": "italic"}}}
        r = lint.lint_spec(spec, specio.validate_spec(spec))
        codes = {f["code"] for f in r["findings"]}
        for c in ("emoji-in-text", "hype-claim", "page-number-in-text", "role-coverage", "hangul-italic"):
            self.assertIn(c, codes)
        self.assertFalse(r["ok"])  # hangul-italic 은 error

    def test_schema_rejects_unknown_archetype(self):
        spec, _ = specio.load_spec(str(ROOT / EXAMPLES["gov"][0]))
        spec["slides"][0]["archetype"] = "nope"
        self.assertTrue(any("archetype" in e for e in specio.validate_spec(spec)))


class Estimator(unittest.TestCase):
    def test_word_wrap_korean(self):
        text = "행사마다 새로 만들던 AI 체험을 4개 층의 플랫폼으로 제품화하면 개발 기간은 절반, 운영 장애는 1/3로 줄일 수 있습니다"
        lines_wide, _ = inspect.estimate_lines([(text, 22.0, None, False)], 12.0)
        lines_narrow, h = inspect.estimate_lines([(text, 22.0, None, False)], 4.3)
        self.assertLess(lines_wide, lines_narrow)
        self.assertGreaterEqual(lines_narrow, 4)
        self.assertGreater(h, 1.0)
        # 어절 단위: 한 어절이 폭보다 짧으면 쪼개지지 않는다 → 긴 어절 하나 + 짧은 폭에서만 글자 단위
        one, _ = inspect.estimate_lines([("가나다라마바사아자차카타파하", 20.0, None, False)], 1.0)
        self.assertGreater(one, 1)

    def test_js_and_python_estimates_match(self):
        fam = next((f for f in ("Paperlogy", "Pretendard", "Apple SD Gothic Neo") if fontmetrics.find(f)), None)
        if not fam:
            self.skipTest("한글 폰트 없음")
        text = "운영 장애의 62%가 행사별로 새로 짠 결제·인쇄 코드에서 발생했다 Platform 2026"
        js = subprocess.run(["node", "-e", f"const t=require('{ROOT}/scripts/lib/text.js');console.log(JSON.stringify([t.linesFor({json.dumps(text)},16,3.2,{{face:{json.dumps(fam)}}}),t.textWidthIn({json.dumps(text)},16,{json.dumps(fam)})]))"], capture_output=True, text=True, cwd=ROOT)
        js_lines, js_w = json.loads(js.stdout.strip())
        py_lines, _ = inspect.estimate_lines([(text, 16.0, fam, False)], 3.2)
        py_w = fontmetrics.text_width_in(text, 16, fam)
        self.assertEqual(js_lines, py_lines)
        self.assertAlmostEqual(js_w, py_w, places=3)

    def test_fontmetrics_reads_installed_font(self):
        fam = next((f for f in ("Paperlogy", "Pretendard", "Apple SD Gothic Neo", "Arial") if fontmetrics.find(f)), None)
        if not fam:
            self.skipTest("폰트 없음")
        ft = fontmetrics.load(fam)
        self.assertIsNotNone(ft)
        self.assertTrue(0.8 <= ft.line_height_em() <= 2.5)
        self.assertTrue(0.2 < (ft.glyph_width_em("a") or 0.5) < 1.0)


class BuildAndGates(unittest.TestCase):
    def test_build_check_inspect(self):
        for name in EXAMPLES:
            out = build(name)
            c = check.check(str(out))
            self.assertTrue(c["ok"], (name, c["errors"]))
            spec, _ = specio.load_spec(str(ROOT / EXAMPLES[name][0]))
            tok = specio.resolve_tokens(spec)
            mode = spec["metadata"]["delivery_mode"]
            tkey = mode if mode in ("live", "pre_read") else "hybrid"
            i = inspect.inspect_file(str(out), min_font=tok["type"][tkey]["body_min"], note_font=9, margin=0.33)
            self.assertTrue(i["ok"], (name, [f for f in i["findings"] if f["level"] == "error"]))
            self.assertEqual(i["summary"]["slides"], len(spec["slides"]))

    def test_new_profiles_build(self):
        for prof in ("editorial_report", "research_dense", "two_font_consulting", "institutional_pitch"):
            out = build("showcase", prof)
            self.assertTrue(check.check(str(out))["ok"], prof)
            i = inspect.inspect_file(str(out), min_font=11, note_font=8, margin=0.3)
            self.assertTrue(i["ok"], (prof, [f for f in i["findings"] if f["level"] == "error"]))

    def test_text_verify_against_spec(self):
        for name in ("consulting", "showcase", "rfp"):
            out = build(name)
            spec, _ = specio.load_spec(str(ROOT / EXAMPLES[name][0]))
            v = audit.verify_text(spec, str(out))
            self.assertTrue(v["ok"], (name, v["findings"][:5]))
            self.assertGreater(v["checked"], 50)
        # 누락 감지: 명세에만 있는 문장
        spec["slides"][2]["content"]["note"] = "이 문장은 파일에 없다 — 손실 감지 테스트"
        v2 = audit.verify_text(spec, str(out))
        self.assertIn("text-missing", {f["code"] for f in v2["findings"]})

    def test_extract_has_titles_and_notes(self):
        out = build("consulting")
        slides = extract.extract(str(out))
        self.assertEqual(slides[1]["title"], "반복 개발을 플랫폼화하면 납기와 품질을 동시에 통제할 수 있습니다")
        self.assertTrue(any(s["notes"] for s in slides))
        self.assertTrue(any(s["charts"] for s in slides))
        self.assertTrue(any(s["tables"] for s in slides))

    def test_audit_total_mismatch(self):
        spec, _ = specio.load_spec(str(ROOT / EXAMPLES["consulting"][0]))
        r = audit.audit_slides(audit._slide_texts_from_spec(spec))
        self.assertTrue(r["ok"], [f for f in r["findings"] if f["level"] == "error"])
        spec["slides"][7]["content"]["total"] = "500"  # 480이어야 함
        r2 = audit.audit_slides(audit._slide_texts_from_spec(spec))
        self.assertIn("total-mismatch", {f["code"] for f in r2["findings"]})
        self.assertFalse(r2["ok"])

    def test_template_contract(self):
        out = build("gov")
        c = template.analyze(str(out))
        self.assertEqual(c["aspect"], "16:9")
        self.assertTrue(c["layouts"])
        self.assertIn("fonts", c["derived_tokens"])
        self.assertIn("safe_area_in", c)

    def test_only_subset(self):
        out = _TMP / "subset.pptx"
        r = subprocess.run(["node", str(ROOT / "scripts/build.js"), str(ROOT / EXAMPLES["consulting"][0]), "-o", str(out), "--only", "1-3"], capture_output=True, text=True, cwd=ROOT)
        s = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(s["slides"], 3)


class ProposalFrame(unittest.TestCase):
    """제안서형 프로파일: 요구·대응·검증·태그 블록이 그려지고, 표지는 쪽번호 없이, 본문은 바닥 안전구역 밖."""

    def test_proposal_frame_blocks_rendered(self):
        out = build("rfp")
        ex = extract.extract(str(out))
        s4 = ex[3]
        blob = json.dumps(s4, ensure_ascii=False)
        for needle in ("요구사항", "대응방안", "검증 기준", "산출물", "SFR-003", "관련 조견표", "전환의 기준"):
            self.assertIn(needle, blob, needle)
        # 표지엔 쪽번호 placeholder 가 없고, 본문 장엔 있다
        from core.package import Package, q
        with Package.open(str(out)) as pkg:
            refs = pkg.slides()
            def has_sldnum(ref):
                lay = pkg.rels(ref.part)
                for r in lay.values():
                    if "slideLayout" in r.rtype:
                        root = pkg.xml(pkg.resolve(ref.part, r.target))
                        return any(ph.get("type") == "sldNum" for ph in root.iter(q("p:ph")))
                return False
            self.assertFalse(has_sldnum(refs[0]))
            self.assertTrue(has_sldnum(refs[3]))

    def test_proposal_lint_rules(self):
        spec, _ = specio.load_spec(str(ROOT / EXAMPLES["rfp"][0]))
        r = lint.lint_spec(spec, [])
        self.assertTrue(r["ok"], r["findings"][:5])
        bad = json.loads(json.dumps(spec))
        bad["slides"][3]["brief"]["response"] = "하나의 행사 흐름"  # 서술어 없음
        del bad["slides"][5]["tags"]
        del bad["slides"][6]["brief"]
        codes = {f["code"] for f in lint.lint_spec(bad, [])["findings"]}
        for c in ("response-no-verb", "tags-missing", "brief-missing"):
            self.assertIn(c, codes)

    def test_proposal_profile_tokens(self):
        spec, _ = specio.load_spec(str(ROOT / EXAMPLES["rfp"][0]))
        tok = specio.resolve_tokens(spec)
        self.assertEqual(tok["title"]["max_lines"], 1)
        self.assertTrue(tok["frame"]["brief"])
        self.assertEqual(tok["table"]["header_fill"], "secondary")


class Palette(unittest.TestCase):
    def test_derive_and_check(self):
        r = palette.derive(["003764", "E4032E"])
        self.assertTrue(r["ok"], r["checks"])
        c = r["design_tokens"]["colors"]
        self.assertEqual(c["primary"], "003764")
        self.assertGreaterEqual(palette.contrast(c["ink"], c["background"]), 4.5)
        self.assertGreaterEqual(palette.hex_to_lch(c["accent"])[1], 0.12)
        self.assertIn("rationale", r)

    def test_profiles_pass_palette_rules(self):
        for name, prof in specio.load_profiles().items():
            checks = palette.check_tokens(prof["tokens"]["colors"])
            self.assertTrue(all(c["ok"] or c["level"] != "error" for c in checks), (name, [c for c in checks if not c["ok"]]))

    def test_png_sampling(self):
        cols = palette.sample_colors(str(ROOT / "examples/assets/sample-kiosk.png"))
        self.assertTrue(1 <= len(cols) <= 3)
        self.assertTrue(all(len(c) == 6 for c in cols))


class Editing(unittest.TestCase):
    def test_inventory_replace_and_reject(self):
        src = build("consulting")
        inv = edit.inventory(str(src))
        s2 = next(s for s in inv["slides"] if s["number"] == 2)
        title_shape = next(sh for sh in s2["shapes"] if sh.get("placeholder") == "title")
        dst = _TMP / "replaced.pptx"
        r = edit.replace(str(src), str(dst), {"slides": {"2": {"shapes": {title_shape["id"]: {"paragraphs": [{"text": "교체된 액션 타이틀입니다"}]}}}}})
        self.assertTrue(r["ok"], r)
        self.assertEqual(extract.extract(str(dst))[1]["title"], "교체된 액션 타이틀입니다")
        dst2 = _TMP / "overflow.pptx"
        r2 = edit.replace(str(src), str(dst2), {"slides": {"2": {"shapes": {title_shape["id"]: {"paragraphs": [{"text": "아주 " * 80}]}}}}})
        self.assertFalse(r2["ok"])
        self.assertTrue(r2["overflow_worsened"])
        self.assertFalse(dst2.exists())

    def test_slides_duplicate_delete_reorder(self):
        src = build("gov")
        dst = _TMP / "reordered.pptx"
        r = edit.reorder_slides(str(src), str(dst), [1, 4, 4, 2])
        self.assertTrue(r["ok"], r)
        slides = extract.extract(str(dst))
        self.assertEqual(len(slides), 4)
        self.assertEqual(slides[1]["title"], slides[2]["title"])
        self.assertTrue(check.check(str(dst))["ok"])

    def test_inherit_into_template(self):
        # 다른 프로파일로 만든 덱을 '양식'으로 삼아 상속 — 마스터는 양식 것, 슬라이드·차트·노트는 생성 덱 것
        gen = build("showcase")
        tpl = build("gov")
        out = _TMP / "inherited.pptx"
        r = inherit.inherit(str(gen), str(tpl), str(out), layout=None, cover_layout=None)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["slides"], 10)
        slides = extract.extract(str(out))
        self.assertEqual(len(slides), 10)
        self.assertTrue(any(s["charts"] for s in slides))
        self.assertTrue(any(s["notes"] for s in slides))
        self.assertTrue(check.check(str(out))["ok"])
        # 크기 불일치 거부
        spec = json.loads((ROOT / EXAMPLES["gov"][0]).read_text(encoding="utf-8"))
        spec["design_tokens"] = {"canvas": {"layout": "LAYOUT_16x9", "width": 10, "height": 5.625}}
        small_spec = _TMP / "small.spec.json"
        small_spec.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        small = _TMP / "small.pptx"
        subprocess.run(["node", str(ROOT / "scripts/build.js"), str(small_spec), "-o", str(small), "--only", "1-2"], capture_output=True, text=True, cwd=ROOT)
        r2 = inherit.inherit(str(gen), str(small), str(_TMP / "bad.pptx"))
        self.assertFalse(r2["ok"])


@unittest.skipUnless(find_soffice() and shutil.which("pdftoppm"), "LibreOffice/pdftoppm 없음")
class Rendering(unittest.TestCase):
    def test_render_probe_and_bleed(self):
        from core import bleed, render

        out = build("proposal")
        r = render.render(str(out), str(_TMP / "render"), dpi=50, contact=True)
        self.assertEqual(r["count"], 12)
        self.assertTrue(Path(r["contact"]).exists())
        self.assertIn("font_environment", r)
        b = bleed.bleed_check(str(out))
        self.assertTrue(b["ok"], b["overflowing"])

    def test_variety_and_directions(self):
        from core import directions, variety

        out = build("showcase")
        from core import render

        r = render.render(str(out), str(_TMP / "render-sc"), dpi=40, contact=False, check_fonts=False)
        v = variety.variety(r["pdf"], str(ROOT / EXAMPLES["showcase"][0]), ledger=False)
        self.assertEqual(v["slides"], 10)
        self.assertIn("mean_layout_corr", v)
        d = directions.directions(str(ROOT / EXAMPLES["showcase"][0]), ["paperlogy_business", "editorial_report"], str(_TMP / "dir"))
        self.assertTrue(d["ok"], d)
        self.assertTrue(Path(d["sheet"]).exists())
        self.assertEqual(len(d["columns"]), 2)
        a = directions.approve(str(_TMP / "dir" / "spec-copy.json") if False else str(ROOT / EXAMPLES["showcase"][0]), str(_TMP / "dir"), "editorial_report", "테스트", apply_to_spec=False)
        self.assertTrue(Path(a["record"]).exists())


if __name__ == "__main__":
    unittest.main()
