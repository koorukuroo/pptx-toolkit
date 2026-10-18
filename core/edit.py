"""기존 PPTX·기관 템플릿 편집: inventory → replace, 슬라이드 복제·삭제·재배열.

설계 원칙
- XML은 ElementTree로 다시 직렬화하지 않는다(네임스페이스 접두사 재작성 위험). 문자열 단위로
  해당 <p:txBody> 구간만 교체하고 나머지 바이트는 그대로 둔다.
- replace는 교체 전후 '넘침 추정'을 비교해 악화되면 저장을 거부한다(inspect.estimate_lines).
- slides는 1-based 순서 목록으로 복제·삭제·재배열을 한 번에 처리하고, 노트·rels·Content_Types를 함께 정리한다.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from .check import check
from .inspect import Shape, _collect, estimate_lines
from .package import NS, Package, q

# ----------------------------------------------------------------------------
# inventory
# ----------------------------------------------------------------------------

def inventory(path: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"file": path, "slides": []}
    with Package.open(path) as pkg:
        cx, cy = pkg.slide_size()
        for ref in pkg.slides():
            if not pkg.has(ref.part):
                continue
            root = pkg.xml(ref.part)
            tree = root.find("p:cSld/p:spTree", NS)
            shapes: List[Shape] = []
            if tree is not None:
                _collect(tree, pkg, ref.part, shapes)
            layout = pkg.layout_part(ref.part)
            lname = ""
            if layout and pkg.has(layout):
                lr = pkg.xml(layout).find("p:cSld", NS)
                lname = lr.get("name", "") if lr is not None else ""
            items = []
            for s in shapes:
                if s.kind not in ("text", "shape", "table", "pic", "chart"):
                    continue
                if s.kind == "shape" and not s.runs:
                    continue
                inner_w = s.w - s.insets[0] - s.insets[2]
                inner_h = s.h - s.insets[1] - s.insets[3]
                lines, need = estimate_lines(s.runs, inner_w, s.para_spacing) if s.runs else (0, 0.0)
                sizes = sorted({r[1] for r in s.runs if r[0].strip()})
                paras = [p for p in s.text.split("\n")]
                items.append({
                    "id": s.sid, "name": s.name, "kind": s.kind, "placeholder": s.is_placeholder or None,
                    "box_in": [round(s.x, 2), round(s.y, 2), round(s.w, 2), round(s.h, 2)],
                    "font_pt": sizes, "paragraphs": paras if s.kind in ("text", "shape") else None,
                    "capacity": {"lines_now": lines, "height_needed_in": round(need, 2), "height_in": round(inner_h, 2), "overflow_in": round(max(0.0, need - inner_h), 2)} if s.runs else None,
                })
            out["slides"].append({"number": ref.index, "part": ref.part, "layout": lname, "shapes": items})
    return out


# ----------------------------------------------------------------------------
# replace
# ----------------------------------------------------------------------------

def _find_sp_span(xml: str, shape_id: str) -> Optional[Tuple[int, int]]:
    """cNvPr id=shape_id 를 가진 <p:sp>…</p:sp> 구간 (문자열 인덱스)."""
    m = re.search(r'<p:cNvPr\s+id="%s"[\s>]' % re.escape(shape_id), xml)
    if not m:
        return None
    start = xml.rfind("<p:sp>", 0, m.start())
    start2 = xml.rfind("<p:sp ", 0, m.start())
    start = max(start, start2)
    if start == -1:
        return None
    end = xml.find("</p:sp>", m.end())
    if end == -1:
        return None
    return start, end + len("</p:sp>")


def _build_txbody(old_txbody: str, paragraphs: List[Dict[str, Any]]) -> str:
    """기존 txBody의 bodyPr/lstStyle, 첫 문단의 pPr, 첫 run의 rPr을 템플릿으로 새 문단 생성."""
    bodypr = re.search(r"<a:bodyPr\b[^>]*/>|<a:bodyPr\b.*?</a:bodyPr>", old_txbody, re.S)
    lst = re.search(r"<a:lstStyle\b[^>]*/>|<a:lstStyle\b.*?</a:lstStyle>", old_txbody, re.S)
    first_p = re.search(r"<a:p\b.*?</a:p>", old_txbody, re.S)
    ppr_tpl = ""
    rpr_tpl = '<a:rPr lang="ko-KR" altLang="en-US" dirty="0"/>'
    if first_p:
        mp = re.search(r"<a:pPr\b[^>]*/>|<a:pPr\b.*?</a:pPr>", first_p.group(0), re.S)
        if mp:
            ppr_tpl = mp.group(0)
        mr = re.search(r"<a:rPr\b[^>]*/>|<a:rPr\b.*?</a:rPr>", first_p.group(0), re.S)
        if mr:
            rpr_tpl = mr.group(0)
    paras_xml = []
    for p in paragraphs:
        text = p.get("text", "")
        ppr = ppr_tpl
        # level / bullet 지정
        if p.get("level") is not None:
            lvl = int(p["level"])
            if ppr:
                ppr = re.sub(r'\slvl="\d+"', "", ppr)
                ppr = ppr.replace("<a:pPr", f'<a:pPr lvl="{lvl}"', 1) if lvl else ppr
            elif lvl:
                ppr = f'<a:pPr lvl="{lvl}"/>'
        if p.get("bullet") is False:
            if ppr and "<a:buNone" not in ppr:
                ppr = re.sub(r"<a:bu\w+\b[^>]*/>", "", ppr)
                ppr = ppr.replace("/>", "><a:buNone/></a:pPr>", 1) if ppr.endswith("/>") else ppr.replace("</a:pPr>", "<a:buNone/></a:pPr>")
            elif not ppr:
                ppr = "<a:pPr><a:buNone/></a:pPr>"
        rpr = rpr_tpl
        if p.get("bold") is not None:
            rpr = re.sub(r'\sb="[01]"', "", rpr)
            rpr = rpr.replace("<a:rPr", '<a:rPr b="%d"' % (1 if p["bold"] else 0), 1)
        if p.get("size"):
            rpr = re.sub(r'\ssz="\d+"', "", rpr)
            rpr = rpr.replace("<a:rPr", '<a:rPr sz="%d"' % int(round(float(p["size"]) * 100)), 1)
        if p.get("color"):
            rpr = re.sub(r"<a:solidFill>.*?</a:solidFill>", "", rpr, flags=re.S)
            fill = '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>' % p["color"].lstrip("#").upper()
            rpr = rpr.replace("/>", ">" + fill + "</a:rPr>", 1) if rpr.endswith("/>") else rpr.replace("</a:rPr>", fill + "</a:rPr>")
        runs = []
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if i:
                runs.append("<a:br>%s</a:br>" % rpr.replace("<a:rPr", "<a:rPr", 1) if False else "<a:br/>")
            t = escape(line)
            space = ' xml:space="preserve"' if line != line.strip() or "  " in line else ""
            runs.append(f"<a:r>{rpr}<a:t{space}>{t}</a:t></a:r>")
        paras_xml.append(f"<a:p>{ppr}{''.join(runs)}</a:p>")
    if not paras_xml:
        paras_xml.append(f"<a:p>{ppr_tpl}<a:endParaRPr lang=\"ko-KR\"/></a:p>")
    return "<p:txBody>" + (bodypr.group(0) if bodypr else "<a:bodyPr/>") + (lst.group(0) if lst else "<a:lstStyle/>") + "".join(paras_xml) + "</p:txBody>"


def replace(src: str, dst: str, mapping: Dict[str, Any], allow_overflow: bool = False) -> Dict[str, Any]:
    """mapping = {"slides": {"3": {"shapes": {"5": {"paragraphs": [{"text": "...", "bullet": true, "level": 0, "bold": false, "size": 14}]}, "7": {"clear": true}}}}}"""
    before = inventory(src)
    cap_before = {(s["number"], sh["id"]): sh["capacity"]["overflow_in"] for s in before["slides"] for sh in s["shapes"] if sh.get("capacity")}
    part_by_num = {s["number"]: s["part"] for s in before["slides"]}
    shape_ids = {(s["number"], sh["id"]) for s in before["slides"] for sh in s["shapes"]}
    errors: List[str] = []
    plan: Dict[str, Dict[str, Any]] = {}
    for snum, sdef in (mapping.get("slides") or {}).items():
        n = int(snum)
        if n not in part_by_num:
            errors.append(f"슬라이드 {n} 없음")
            continue
        for sid, sh in (sdef.get("shapes") or {}).items():
            if (n, str(sid)) not in shape_ids:
                errors.append(f"슬라이드 {n} 도형 id {sid} 없음 (inventory로 확인)")
                continue
            plan.setdefault(part_by_num[n], {})[str(sid)] = sh
    if errors:
        return {"ok": False, "errors": errors}
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename in plan:
                xml = data.decode("utf-8")
                for sid, sh in plan[info.filename].items():
                    span = _find_sp_span(xml, sid)
                    if not span:
                        errors.append(f"{info.filename}: id {sid} 의 <p:sp> 구간을 찾지 못함")
                        continue
                    sp = xml[span[0]:span[1]]
                    m = re.search(r"<p:txBody>.*?</p:txBody>", sp, re.S)
                    if not m:
                        errors.append(f"{info.filename}: id {sid} 에 txBody 없음")
                        continue
                    if sh.get("clear"):
                        new_tx = _build_txbody(m.group(0), [])
                    else:
                        new_tx = _build_txbody(m.group(0), sh.get("paragraphs") or [])
                    sp2 = sp[:m.start()] + new_tx + sp[m.end():]
                    xml = xml[:span[0]] + sp2 + xml[span[1]:]
                data = xml.encode("utf-8")
            zout.writestr(info, data)
    if errors:
        Path(dst).unlink(missing_ok=True)
        return {"ok": False, "errors": errors}
    after = inventory(dst)
    worsened = []
    for s in after["slides"]:
        for sh in s["shapes"]:
            if sh.get("capacity"):
                b = cap_before.get((s["number"], sh["id"]), 0.0)
                a = sh["capacity"]["overflow_in"]
                if a > b + 0.01:
                    worsened.append({"slide": s["number"], "shape": sh["id"], "overflow_before_in": b, "overflow_after_in": a, "text": (sh.get("paragraphs") or [""])[0][:40]})
    chk = check(dst)
    ok = chk["ok"] and (allow_overflow or not worsened)
    if not ok:
        rejected = Path(dst).with_suffix(".rejected.pptx")
        Path(dst).replace(rejected)
        return {"ok": False, "output": None, "rejected_output": str(rejected), "overflow_worsened": worsened, "check": chk, "fix": "글자를 줄이거나 size를 낮추거나(하한 준수) --allow-overflow 로 강제"}
    return {"ok": True, "output": dst, "overflow_worsened": worsened, "check": {"ok": chk["ok"], "warnings": chk["warnings"]}}


# ----------------------------------------------------------------------------
# slides: duplicate / delete / reorder
# ----------------------------------------------------------------------------

def reorder_slides(src: str, dst: str, keep: List[int]) -> Dict[str, Any]:
    """keep = 1-based 원본 슬라이드 번호의 새 순서 (중복 = 복제, 누락 = 삭제)."""
    with Package.open(src) as pkg:
        refs = pkg.slides()
        names = set(pkg.names)
        if any(k < 1 or k > len(refs) for k in keep):
            return {"ok": False, "errors": [f"슬라이드 번호 범위 1..{len(refs)}"]}
        pres_xml = pkg.read("ppt/presentation.xml").decode("utf-8")
        pres_rels = pkg.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
        ct = pkg.read("[Content_Types].xml").decode("utf-8")
        existing_nums = [int(re.search(r"slide(\d+)\.xml", n).group(1)) for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)]
        next_slide = max(existing_nums or [0]) + 1
        notes_nums = [int(re.search(r"notesSlide(\d+)\.xml", n).group(1)) for n in names if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n)]
        next_notes = max(notes_nums or [0]) + 1
        rid_nums = [int(x) for x in re.findall(r'Id="rId(\d+)"', pres_rels)]
        next_rid = max(rid_nums or [0]) + 1
        sld_ids = [int(x) for x in re.findall(r'<p:sldId id="(\d+)"', pres_xml)]
        next_sld = max(sld_ids + [255]) + 1

        new_parts: Dict[str, bytes] = {}
        used_src: Dict[int, int] = {}
        new_order: List[Tuple[str, str]] = []  # (sldId, rId)
        rels_add: List[str] = []
        ct_add: List[str] = []
        for k in keep:
            ref = refs[k - 1]
            used_src[k] = used_src.get(k, 0) + 1
            if used_src[k] == 1:
                new_order.append((ref.sld_id, ref.rid))
                continue
            # 복제
            new_name = f"ppt/slides/slide{next_slide}.xml"
            next_slide += 1
            slide_xml = pkg.read(ref.part)
            new_parts[new_name] = slide_xml
            rels_name = pkg.rels_name(ref.part)
            rels_xml = pkg.read(rels_name).decode("utf-8") if pkg.has(rels_name) else '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
            # 노트 복제
            np_ = pkg.notes_part(ref.part)
            if np_ and pkg.has(np_):
                new_notes = f"ppt/notesSlides/notesSlide{next_notes}.xml"
                next_notes += 1
                new_parts[new_notes] = pkg.read(np_)
                nrels_name = pkg.rels_name(np_)
                nrels = pkg.read(nrels_name).decode("utf-8")
                nrels = re.sub(r'Target="\.\./slides/slide\d+\.xml"', f'Target="../slides/slide{new_name.rsplit("slide",1)[1].split(".")[0]}.xml"', nrels)
                new_parts[pkg.rels_name(new_notes)] = nrels.encode("utf-8")
                rels_xml = rels_xml.replace(f'Target="../notesSlides/{Path(np_).name}"', f'Target="../notesSlides/{Path(new_notes).name}"')
                ct_add.append(f'<Override PartName="/{new_notes}" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>')
            new_parts[pkg.rels_name(new_name)] = rels_xml.encode("utf-8")
            rid = f"rId{next_rid}"
            next_rid += 1
            rels_add.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/{Path(new_name).name}"/>')
            ct_add.append(f'<Override PartName="/{new_name}" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
            new_order.append((str(next_sld), rid))
            next_sld += 1
        # 삭제 대상
        removed = [r for i, r in enumerate(refs, start=1) if i not in used_src]
        drop_parts = set()
        for r in removed:
            drop_parts.add(r.part)
            drop_parts.add(pkg.rels_name(r.part))
            np_ = pkg.notes_part(r.part)
            if np_:
                drop_parts.add(np_)
                drop_parts.add(pkg.rels_name(np_))
            pres_rels = re.sub(r'<Relationship Id="%s"[^>]*/>' % re.escape(r.rid), "", pres_rels)
            ct = ct.replace(f'<Override PartName="/{r.part}" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>', "")
            if np_:
                ct = ct.replace(f'<Override PartName="/{np_}" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>', "")
        # sldIdLst 재작성
        lst = "".join(f'<p:sldId id="{sid}" r:id="{rid}"/>' for sid, rid in new_order)
        pres_xml = re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>", f"<p:sldIdLst>{lst}</p:sldIdLst>", pres_xml, flags=re.S)
        pres_rels = pres_rels.replace("</Relationships>", "".join(rels_add) + "</Relationships>")
        ct = ct.replace("</Types>", "".join(ct_add) + "</Types>")
        # 쓰기
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename in drop_parts:
                    continue
                data = zin.read(info.filename)
                if info.filename == "ppt/presentation.xml":
                    data = pres_xml.encode("utf-8")
                elif info.filename == "ppt/_rels/presentation.xml.rels":
                    data = pres_rels.encode("utf-8")
                elif info.filename == "[Content_Types].xml":
                    data = ct.encode("utf-8")
                zout.writestr(info, data)
            for name, data in new_parts.items():
                zout.writestr(name, data)
    chk = check(dst)
    if not chk["ok"]:
        rejected = Path(dst).with_suffix(".rejected.pptx")
        Path(dst).replace(rejected)
        return {"ok": False, "output": None, "rejected_output": str(rejected), "check": chk}
    return {"ok": True, "output": dst, "order": keep, "duplicated": [k for k, c in used_src.items() if c > 1], "deleted": [i for i in range(1, len(refs) + 1) if i not in used_src], "note": "복제된 슬라이드는 차트·미디어 파트를 원본과 공유한다(한쪽 차트 데이터 수정 시 양쪽 변경)."}


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main_inventory(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py inventory")
    ap.add_argument("pptx")
    ap.add_argument("--slide", type=int, default=None)
    a = ap.parse_args(argv)
    inv = inventory(a.pptx)
    if a.slide:
        inv["slides"] = [s for s in inv["slides"] if s["number"] == a.slide]
    print(json.dumps(inv, ensure_ascii=False, indent=2))
    return 0


def main_replace(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py replace")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--map", required=True, help='{"slides": {"2": {"shapes": {"4": {"paragraphs": [{"text": "..."}]}}}}}')
    ap.add_argument("--allow-overflow", action="store_true")
    a = ap.parse_args(argv)
    mapping = json.loads(Path(a.map).read_text(encoding="utf-8"))
    r = replace(a.src, a.dst, mapping, a.allow_overflow)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1


def main_slides(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py slides")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--keep", required=True, help="새 순서의 원본 슬라이드 번호 (1-based, 콤마 구분; 중복=복제, 누락=삭제) 예: 1,3,3,5")
    a = ap.parse_args(argv)
    keep = [int(x) for x in a.keep.split(",") if x.strip()]
    r = reorder_slides(a.src, a.dst, keep)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1
