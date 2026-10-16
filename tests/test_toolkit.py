"""pptx-toolkit 회귀 테스트 — 예제 3종을 빌드해 게이트·편집·감사를 검증한다.

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

from core import audit, check, edit, extract, inspect, lint, specio, template  # noqa: E402
from core.render import find_soffice  # noqa: E402

EXAMPLES = {
    "consulting": ("examples/consulting-kiosk-strategy.spec.json", []),
    "gov": ("examples/gov-ai-platform-briefing.spec.json", []),
    "proposal": ("examples/proposal-shipyard-ax.spec.json", ["--hooks", "examples/proposal-hooks.js"]),
}

_TMP = Path(tempfile.mkdtemp(prefix="pptx-toolkit-test-"))
_BUILT: dict[str, Path] = {}


def build(name: str) -> Path:
    if name in _BUILT:
        return _BUILT[name]
    spec, extra = EXAMPLES[name]
    out = _TMP / f"{name}.pptx"
    r = subprocess.run(["node", str(ROOT / "scripts" / "build.js"), str(ROOT / spec), "-o", str(out), *extra], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    summary = json.loads(r.stdout.strip().splitlines()[-1])
    assert summary["ok"], summary
    _BUILT[name] = out
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

    def test_schema_rejects_unknown_archetype(self):
        spec, _ = specio.load_spec(str(ROOT / EXAMPLES["gov"][0]))
        spec["slides"][0]["archetype"] = "nope"
        self.assertTrue(any("archetype" in e for e in specio.validate_spec(spec)))


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
        # 넘침 악화 → 거부
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


@unittest.skipUnless(find_soffice() and shutil.which("pdftoppm"), "LibreOffice/pdftoppm 없음")
class Rendering(unittest.TestCase):
    def test_render_and_bleed(self):
        from core import bleed, render

        out = build("proposal")
        r = render.render(str(out), str(_TMP / "render"), dpi=50, contact=True)
        self.assertEqual(r["count"], 12)
        self.assertTrue(Path(r["contact"]).exists())
        b = bleed.bleed_check(str(out))
        self.assertTrue(b["ok"], b["overflowing"])


if __name__ == "__main__":
    unittest.main()
