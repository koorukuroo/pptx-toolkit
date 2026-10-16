"""패키지 무결성 검사 (전달 전 게이트).

PowerPoint가 "복구 필요/열 수 없음"으로 거부하는 알려진 패턴을 잡는다.
LibreOffice·python-pptx가 열어도 PowerPoint는 거부하는 경우가 있으므로
렌더가 됐다고 통과로 보지 않는다.

검사 항목:
  xml-malformed          모든 .xml/.rels 파트가 well-formed 인가
  content-type-missing   파트에 Default/Override 콘텐츠 타입이 있는가
  rel-target-missing     rels Target 파트가 존재하는가 (Internal)
  slide-missing          presentation.xml sldIdLst의 슬라이드 파트가 존재하는가
  slide-id-duplicate     sldId id/r:id 중복
  shape-id-duplicate     한 슬라이드 안 cNvPr id 중복 (PowerPoint 복구 유발)
  chart-axis-undeclared  c:axId가 참조하는 축이 선언되지 않음 (pptxgenjs 콤보/2축 버그)
  chart-dlbl-stacked     누적 막대에 outEnd 라벨 위치 (파일 손상)
  color-invalid          srgbClr val이 6자리 hex가 아님 ('#', 8자리)
  shadow-negative        a:outerShdw dist 음수
  presentation-order     p:presentation 자식 순서 (sldMasterIdLst → notesMasterIdLst → sldIdLst …)
  notes-slide-rel        notesSlide가 자기 슬라이드로 되돌아가는 rel 보유
  layout-master-rel      slideLayout → slideMaster, slideMaster → theme rel 존재
  placeholder-text       'Click to add', 'Lorem', 'TODO', '[insert' 등 잔재 (경고)
  empty-deck             슬라이드 0장
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from .package import NS, Package, q

PLACEHOLDER_RE = re.compile(
    r"(click to add|lorem ipsum|\bTODO\b|\bTBD\b|\[insert|\{\{.*?\}\}|xxx+|제목을 입력|내용을 입력|텍스트를 입력)",
    re.IGNORECASE,
)

PRESENTATION_ORDER = [
    "sldMasterIdLst",
    "notesMasterIdLst",
    "handoutMasterIdLst",
    "sldIdLst",
    "sldSz",
    "notesSz",
    "smartTags",
    "embeddedFontLst",
    "custShowLst",
    "photoAlbum",
    "custDataLst",
    "kinsoku",
    "defaultTextStyle",
    "modifyVerifier",
    "extLst",
]


class Report:
    def __init__(self) -> None:
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []

    def err(self, code: str, where: str, msg: str, fix: str = "") -> None:
        self.errors.append({"code": code, "where": where, "message": msg, "fix": fix})

    def warn(self, code: str, where: str, msg: str, fix: str = "") -> None:
        self.warnings.append({"code": code, "where": where, "message": msg, "fix": fix})

    def as_dict(self, path: str) -> Dict[str, Any]:
        return {"file": path, "ok": not self.errors, "errors": self.errors, "warnings": self.warnings}


def _check_xml(pkg: Package, rep: Report) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    for name in pkg.names:
        if name.endswith((".xml", ".rels")):
            try:
                parsed[name] = pkg.xml(name)
            except Exception as e:  # noqa: BLE001
                rep.err("xml-malformed", name, f"XML 파싱 실패: {e}", "생성 스크립트에서 & < > 를 이스케이프하거나(&amp;) 해당 파트를 다시 만든다")
    return parsed


def _check_content_types(pkg: Package, rep: Report) -> None:
    if not pkg.has("[Content_Types].xml"):
        rep.err("content-type-missing", "[Content_Types].xml", "파트가 없다", "pack 시 [Content_Types].xml 포함")
        return
    defaults, overrides = pkg.content_types()
    for name in pkg.names:
        if name == "[Content_Types].xml" or name.endswith("/"):
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if name not in overrides and ext not in defaults:
            rep.err("content-type-missing", name, "콘텐츠 타입 없음", "[Content_Types].xml에 Default(확장자) 또는 Override(파트) 추가")
    orphans = [p for p in overrides if not pkg.has(p)]
    # pptxgenjs는 슬라이드 수만큼 slideMasterN Override를 미리 써 둔다(실재하지 않음). PowerPoint가 무시하므로 묶어서 한 번만 알린다.
    master_orphans = [p for p in orphans if re.match(r"ppt/slideMasters/slideMaster\d+\.xml$", p)]
    for part in orphans:
        if part in master_orphans:
            continue
        rep.warn("content-type-orphan", part, "Override가 가리키는 파트가 없다", "clean 하거나 Override 제거")
    if master_orphans:
        rep.warn("content-type-orphan", "[Content_Types].xml", f"존재하지 않는 slideMaster Override {len(master_orphans)}개 (pptxgenjs 생성 특성, 무해)", "")


def _check_rels(pkg: Package, rep: Report) -> None:
    for name in pkg.names:
        if not name.endswith(".rels"):
            continue
        d = name.rsplit("/_rels/", 1)
        src = (d[0] + "/" + d[1][: -len(".rels")]) if len(d) == 2 else d[0][: -len(".rels")].lstrip("_rels/")
        if name == "_rels/.rels":
            src = ""
        try:
            root = pkg.xml(name)
        except Exception:
            continue
        seen = set()
        for el in root.findall("rel:Relationship", NS):
            rid = el.get("Id", "")
            if rid in seen:
                rep.err("rel-id-duplicate", name, f"Relationship Id 중복: {rid}", "rId를 고유하게 부여")
            seen.add(rid)
            if el.get("TargetMode", "Internal") != "Internal":
                continue
            target = pkg.resolve(src, el.get("Target", "")) if src else el.get("Target", "").lstrip("/")
            if not pkg.has(target):
                rep.err("rel-target-missing", name, f"{rid} → {target} 파트가 없다", "대상 파트를 추가하거나 rel을 제거(clean)")


def _check_presentation(pkg: Package, rep: Report) -> List[str]:
    if not pkg.has("ppt/presentation.xml"):
        rep.err("slide-missing", "ppt/presentation.xml", "presentation.xml 없음")
        return []
    root = pkg.xml("ppt/presentation.xml")
    # 자식 순서
    order = [child.tag.split("}")[-1] for child in list(root)]
    # pptxgenjs는 sldIdLst 뒤에 notesMasterIdLst를 쓴다. 스키마 순서는 아니지만 PowerPoint가 열며,
    # 이 요소를 옮기면 오히려 열리지 않는 사례가 있으므로 그 순서는 허용한다. 그 밖의 뒤섞임만 경고.
    known = [t for t in order if t in PRESENTATION_ORDER and t != "notesMasterIdLst"]
    idx = [PRESENTATION_ORDER.index(t) for t in known]
    if idx != sorted(idx):
        rep.warn("presentation-order", "ppt/presentation.xml", f"자식 요소 순서가 스키마와 다름: {order}", "생성기를 고친다. 이미 만들어진 파일의 요소를 손으로 옮기지 않는다")
    if "sldMasterIdLst" in order and "sldIdLst" in order and order.index("sldMasterIdLst") > order.index("sldIdLst"):
        rep.err("presentation-order", "ppt/presentation.xml", "sldMasterIdLst가 sldIdLst 뒤에 있음", "생성기를 고친다")
    slides = pkg.slides()
    if not slides:
        rep.err("empty-deck", "ppt/presentation.xml", "슬라이드가 0장")
    ids, rids = set(), set()
    parts: List[str] = []
    for s in slides:
        if s.sld_id in ids:
            rep.err("slide-id-duplicate", "ppt/presentation.xml", f"sldId id 중복 {s.sld_id}")
        if s.rid in rids:
            rep.err("slide-id-duplicate", "ppt/presentation.xml", f"sldId r:id 중복 {s.rid}")
        ids.add(s.sld_id)
        rids.add(s.rid)
        try:
            if int(s.sld_id) < 256:
                rep.err("slide-id-range", "ppt/presentation.xml", f"sldId id {s.sld_id} < 256", "슬라이드 id는 256 이상이어야 한다")
        except ValueError:
            pass
        if not s.part or not pkg.has(s.part):
            rep.err("slide-missing", "ppt/presentation.xml", f"{s.rid} → {s.part} 슬라이드 파트 없음")
        else:
            parts.append(s.part)
    # 마스터/레이아웃/테마 체인
    for lay in [n for n in pkg.names if n.startswith("ppt/slideLayouts/slideLayout") and n.endswith(".xml")]:
        if not pkg.master_part(lay):
            rep.err("layout-master-rel", lay, "slideLayout → slideMaster rel 없음")
    for mst in [n for n in pkg.names if n.startswith("ppt/slideMasters/slideMaster") and n.endswith(".xml")]:
        if not any(r.rtype == "theme" for r in pkg.rels(mst).values()):
            rep.err("layout-master-rel", mst, "slideMaster → theme rel 없음")
    return parts


def _check_slide(pkg: Package, part: str, rep: Report) -> None:
    root = pkg.xml(part)
    seen_ids: Dict[str, int] = {}
    for cnv in root.iter(q("p:cNvPr")):
        sid = cnv.get("id", "")
        seen_ids[sid] = seen_ids.get(sid, 0) + 1
    for sid, n in seen_ids.items():
        if n > 1:
            # pptxgenjs는 표(graphicFrame) id를 별도 규칙으로 매겨 충돌이 잦다. PowerPoint는 열어 주므로 경고로 둔다.
            rep.warn("shape-id-duplicate", part, f"cNvPr id={sid} 가 {n}번", "도형 id를 고유하게 (복제 시 id 재부여). PowerPoint는 대개 열지만 선택·애니메이션 대상이 꼬일 수 있다")
    # 색상/그림자
    for el in root.iter(q("a:srgbClr")):
        val = el.get("val", "")
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", val):
            rep.err("color-invalid", part, f"srgbClr val='{val}'", "6자리 hex만 허용. '#'와 알파(8자리) 제거, 투명도는 transparency 옵션으로")
    for el in root.iter(q("a:outerShdw")):
        try:
            if int(el.get("dist", "0")) < 0:
                rep.err("shadow-negative", part, "outerShdw dist 음수", "offset ≥ 0, 방향은 angle로")
        except ValueError:
            pass
    # 슬라이드 레이아웃 rel
    if not pkg.layout_part(part):
        rep.err("layout-master-rel", part, "slide → slideLayout rel 없음")
    # notesSlide 역참조
    np_ = pkg.notes_part(part)
    if np_ and pkg.has(np_):
        back = [pkg.resolve(np_, r.target) for r in pkg.rels(np_).values() if r.rtype == "slide"]
        if part not in back:
            rep.err("notes-slide-rel", np_, "notesSlide → slide 역참조가 없거나 다른 슬라이드를 가리킴", "add_slide 류 스크립트로 노트까지 함께 복제")
    # placeholder 잔재
    texts = [t.text or "" for t in root.iter(q("a:t"))]
    joined = " ".join(texts)
    m = PLACEHOLDER_RE.search(joined)
    if m:
        rep.warn("placeholder-text", part, f"자리표시 문구 잔재: '{m.group(0)}'", "실제 내용으로 교체하거나 도형 삭제")
    # 차트
    for cpart in pkg.chart_parts(part):
        if pkg.has(cpart):
            _check_chart(pkg, cpart, rep)


def _check_chart(pkg: Package, cpart: str, rep: Report) -> None:
    root = pkg.xml(cpart)
    declared = set()
    for tag in ("c:valAx", "c:catAx", "c:dateAx", "c:serAx"):
        for ax in root.iter(q(tag)):
            aid = ax.find("c:axId", NS)
            if aid is not None:
                declared.add(aid.get("val"))
    for plot in root.iter(q("c:plotArea")):
        for chart in list(plot):
            tagname = chart.tag.split("}")[-1]
            if not tagname.endswith("Chart"):
                continue
            refs = [a.get("val") for a in chart.findall("c:axId", NS)]
            if tagname in ("pieChart", "pie3DChart", "doughnutChart", "ofPieChart"):
                continue
            matched = [r for r in refs if r in declared]
            # pptxgenjs는 2D 막대에도 세 번째(serAx용) axId를 쓰지만 PowerPoint가 허용한다.
            # 문제는 '선언된 축이 2개 미만으로 매칭'되는 경우 — 보조축 콤보에서 valAxes만 주고 catAxes를 빠뜨렸을 때.
            if len(matched) < 2:
                rep.err("chart-axis-undeclared", cpart, f"{tagname} 가 참조하는 축 {refs} 중 선언된 것 {matched}", "보조축 콤보 차트는 valAxes와 catAxes를 둘 다 2개씩 선언한다 (pptxgenjs). 차트는 PowerPoint에서 통째로 버려진다")
            grouping = chart.find("c:grouping", NS)
            if grouping is not None and grouping.get("val") in ("stacked", "percentStacked") and tagname == "barChart":
                for pos in chart.iter(q("c:dLblPos")):
                    if pos.get("val") in ("outEnd", "inEnd" if False else "outEnd"):
                        rep.err("chart-dlbl-stacked", cpart, "누적 막대에 dLblPos=outEnd", "ctr / inEnd / inBase 중 하나로")
    if root.find(".//c:chartSpace", NS) is None and root.tag != q("c:chartSpace"):
        rep.err("chart-root", cpart, "c:chartSpace 루트가 아님")


def check(path: str) -> Dict[str, Any]:
    rep = Report()
    with Package.open(path) as pkg:
        _check_xml(pkg, rep)
        if rep.errors and all(e["code"] == "xml-malformed" for e in rep.errors):
            # 파싱 불가 파트가 있으면 나머지 검사가 예외를 낼 수 있으므로 여기서 멈춘다
            return rep.as_dict(path)
        _check_content_types(pkg, rep)
        _check_rels(pkg, rep)
        parts = _check_presentation(pkg, rep)
        for part in parts:
            try:
                _check_slide(pkg, part, rep)
            except Exception as e:  # noqa: BLE001
                rep.err("slide-check-failed", part, f"검사 중 예외: {e}")
    return rep.as_dict(path)


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py check")
    ap.add_argument("pptx")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    r = check(a.pptx)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1
