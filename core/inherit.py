"""기관 양식 상속 — 생성한 덱의 슬라이드를 기관 PPTX/POTX 패키지에 이식해 그 마스터·레이아웃(로고·배경·푸터 그래픽)을 물려받는다.

  pptx.py inherit generated.pptx 기관양식.pptx -o out.pptx [--layout "제목만"] [--cover-layout "표지"] [--keep-template-slides] [--footer "문구"]

동작
  1. 양식에서 대상 레이아웃을 고른다 (--layout 이름/번호; 기본: '제목만·Title Only' → 'blank·빈 화면' → 첫 레이아웃)
  2. 생성 덱의 각 슬라이드 XML을 새 파트로 복사하고 rels 의 slideLayout 을 양식 레이아웃으로 바꾼다
     - 차트·임베디드 xlsx·이미지·노트는 이름을 바꿔 함께 복사한다 (충돌 없음)
     - 생성 덱 레이아웃의 배경색이 흰색이 아니면(어두운 표지·구분) 슬라이드 배경으로 옮겨 적는다
     - 양식 레이아웃에 쪽번호 자리표시자가 있으면 각 슬라이드에 쪽번호 자리표시자를 넣어 양식 위치·서식을 따른다
  3. 양식의 기존 슬라이드는 제거(기본) 또는 앞에 유지(--keep-template-slides)
  4. check 게이트를 통과한 결과만 저장한다 (실패 시 .rejected.pptx)

제약
  - 슬라이드 크기가 다르면 중단한다 — `template 양식.pptx --tokens-only` 의 canvas 를 design_tokens 에 넣어 다시 빌드한 뒤 상속한다
  - 생성 덱의 글꼴·색은 run 수준에 명시돼 있어 유지된다. 양식 마스터의 글꼴로 바꾸려면 design_tokens.fonts 를 양식 값으로 두고 빌드한다
  - 양식 마스터의 제목 자리표시자 서식(위치·크기)은 생성 덱의 제목이 자체 좌표를 가지므로 적용되지 않는다. 양식 위치를 따르려면
    template-contract 의 safe_area_in 을 canvas.margin 으로 넣어 빌드한다
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .check import check
from .package import NS, Package, q

REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
CT = {
    "slide": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
    "notesSlide": "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml",
    "chart": "application/vnd.openxmlformats-officedocument.drawingml.chart+xml",
    "notesMaster": "application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml",
    "theme": "application/vnd.openxmlformats-officedocument.theme+xml",
}
DEFAULT_EXT = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "png": "image/png", "jpeg": "image/jpeg", "jpg": "image/jpeg", "gif": "image/gif", "svg": "image/svg+xml", "emf": "image/x-emf", "wmf": "image/x-wmf", "bin": "application/vnd.openxmlformats-officedocument.oleObject"}


def _layout_name(pkg: Package, part: str) -> str:
    try:
        root = pkg.xml(part)
    except Exception:  # noqa: BLE001
        return ""
    c = root.find("p:cSld", NS)
    return (c.get("name", "") if c is not None else "") or ""


def pick_layout(pkg: Package, want: Optional[str] = None) -> Tuple[str, str]:
    layouts = sorted((n for n in pkg.names if re.match(r"ppt/slideLayouts/slideLayout\d+\.xml$", n)), key=lambda s: int(re.search(r"(\d+)", s.rsplit("/", 1)[1]).group(1)))
    if not layouts:
        raise ValueError("양식에 slideLayout 이 없다")
    names = {l: _layout_name(pkg, l) for l in layouts}
    types = {}
    for l in layouts:
        try:
            types[l] = pkg.xml(l).get("type", "")
        except Exception:  # noqa: BLE001
            types[l] = ""
    if want:
        if want.isdigit():
            idx = int(want) - 1
            if 0 <= idx < len(layouts):
                return layouts[idx], names[layouts[idx]]
        for l in layouts:
            if want.lower() in names[l].lower():
                return l, names[l]
        raise ValueError(f"레이아웃 '{want}' 없음. 가능: " + ", ".join(f"{i + 1}:{names[l]}" for i, l in enumerate(layouts)))
    for pat in (r"제목만|title only|titleonly", r"^blank$|빈 화면|빈화면|blank"):
        for l in layouts:
            if re.search(pat, names[l], re.IGNORECASE) or (pat.startswith("제목만") and types[l] == "titleOnly") or (pat.startswith("^blank") and types[l] == "blank"):
                return l, names[l]
    return layouts[0], names[layouts[0]]


def _bg_color(pkg: Package, part: str) -> Optional[str]:
    """레이아웃/마스터의 단색 배경 hex."""
    if not part or not pkg.has(part):
        return None
    try:
        root = pkg.xml(part)
    except Exception:  # noqa: BLE001
        return None
    bg = root.find("p:cSld/p:bg", NS)
    if bg is None:
        return None
    clr = bg.find(".//a:solidFill/a:srgbClr", NS)
    return clr.get("val", "").upper() if clr is not None else None


def _placeholder_sp(root, ph_type: str) -> Optional[str]:
    for sp in root.iter(q("p:sp")):
        ph = sp.find("p:nvSpPr/p:nvPr/p:ph", NS)
        if ph is not None and ph.get("type") == ph_type:
            return ph.get("idx")
    return None


def inherit(generated: str, template: str, out: str, layout: Optional[str] = None, cover_layout: Optional[str] = None, keep_template_slides: bool = False, footer: Optional[str] = None) -> Dict[str, Any]:
    gen = Package.open(generated)
    tpl = Package.open(template)
    try:
        if gen.slide_size() != tpl.slide_size():
            gw, gh = gen.slide_size()
            tw, th = tpl.slide_size()
            return {"ok": False, "error": f"슬라이드 크기 불일치: 생성 {gw / 914400:.3f}×{gh / 914400:.3f}in vs 양식 {tw / 914400:.3f}×{th / 914400:.3f}in", "fix": "`pptx.py template 양식.pptx --tokens-only` 의 canvas 를 spec.design_tokens 에 넣고 다시 빌드한 뒤 inherit 한다"}
        lay_part, lay_name = pick_layout(tpl, layout)
        cov_part, cov_name = pick_layout(tpl, cover_layout) if cover_layout else (lay_part, lay_name)
        lay_root = tpl.xml(lay_part)
        master_part = tpl.master_part(lay_part) or ""
        lay_has_sldnum = _placeholder_sp(lay_root, "sldNum") is not None or (master_part and _placeholder_sp(tpl.xml(master_part), "sldNum") is not None)
        lay_has_ftr = _placeholder_sp(lay_root, "ftr") is not None or (master_part and _placeholder_sp(tpl.xml(master_part), "ftr") is not None)
        tpl_bg = _bg_color(tpl, lay_part) or _bg_color(tpl, master_part) or "FFFFFF"

        new_parts: Dict[str, bytes] = {}
        ct_overrides: List[Tuple[str, str]] = []
        ct_defaults: Dict[str, str] = {}
        names = set(tpl.names)
        tpl_pres = tpl.read("ppt/presentation.xml").decode("utf-8")
        tpl_pres_rels = tpl.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
        tpl_ct = tpl.read("[Content_Types].xml").decode("utf-8")

        def next_num(prefix: str, pattern: str) -> int:
            nums = [int(m.group(1)) for n in list(names) + list(new_parts) for m in [re.match(pattern, n)] if m]
            return max(nums or [0]) + 1

        # notes master: 양식에 없으면 생성 덱 것을 가져온다
        tpl_notes_master = next((n for n in tpl.names if re.match(r"ppt/notesMasters/notesMaster\d+\.xml$", n)), None)
        gen_notes_master = next((n for n in gen.names if re.match(r"ppt/notesMasters/notesMaster\d+\.xml$", n)), None)
        notes_master_rel_target = None
        pres_rels_add: List[str] = []
        rid_nums = [int(x) for x in re.findall(r'Id="rId(\d+)"', tpl_pres_rels)]
        next_rid = max(rid_nums or [0]) + 1
        if tpl_notes_master:
            notes_master_rel_target = tpl_notes_master
        elif gen_notes_master:
            nm_new = f"ppt/notesMasters/notesMaster{next_num('nm', r'ppt/notesMasters/notesMaster(\d+)\.xml$')}.xml"
            new_parts[nm_new] = gen.read(gen_notes_master)
            nm_rels = gen.read(gen.rels_name(gen_notes_master)).decode("utf-8") if gen.has(gen.rels_name(gen_notes_master)) else ""
            # 테마 복사
            m = re.search(r'Target="\.\./theme/(theme\d+\.xml)"', nm_rels)
            if m:
                th_src = f"ppt/theme/{m.group(1)}"
                th_new = f"ppt/theme/theme{next_num('th', r'ppt/theme/theme(\d+)\.xml$')}.xml"
                new_parts[th_new] = gen.read(th_src)
                ct_overrides.append((th_new, CT["theme"]))
                nm_rels = nm_rels.replace(f'Target="../theme/{m.group(1)}"', f'Target="../theme/{Path(th_new).name}"')
            new_parts[gen.rels_name(nm_new)] = nm_rels.encode("utf-8")
            ct_overrides.append((nm_new, CT["notesMaster"]))
            rid = f"rId{next_rid}"
            next_rid += 1
            pres_rels_add.append(f'<Relationship Id="{rid}" Type="{REL}notesMaster" Target="notesMasters/{Path(nm_new).name}"/>')
            if "<p:notesMasterIdLst>" not in tpl_pres:
                tpl_pres = re.sub(r"(</p:sldMasterIdLst>)", r"\1" + f'<p:notesMasterIdLst><p:notesMasterId r:id="{rid}"/></p:notesMasterIdLst>', tpl_pres, count=1)
            notes_master_rel_target = nm_new

        media_map: Dict[str, str] = {}
        warnings: List[str] = []
        sld_ids = [int(x) for x in re.findall(r'<p:sldId id="(\d+)"', tpl_pres)]
        next_sld = max(sld_ids + [255]) + 1
        new_order: List[Tuple[str, str]] = []

        def copy_media(src_part: str) -> str:
            if src_part in media_map:
                return media_map[src_part]
            data = gen.read(src_part)
            ext = Path(src_part).suffix.lower().lstrip(".")
            h = hashlib.sha1(data).hexdigest()[:10]
            dst = f"ppt/media/tk_{h}.{ext}"
            new_parts[dst] = data
            if ext and ext not in ct_defaults:
                ct_defaults[ext] = DEFAULT_EXT.get(ext, f"image/{ext}")
            media_map[src_part] = dst
            return dst

        def copy_chart(src_part: str) -> str:
            n = next_num("ch", r"ppt/charts/chart(\d+)\.xml$")
            dst = f"ppt/charts/chart{n}.xml"
            new_parts[dst] = gen.read(src_part)
            ct_overrides.append((dst, CT["chart"]))
            rn = gen.rels_name(src_part)
            if gen.has(rn):
                rels = gen.read(rn).decode("utf-8")
                for m in re.finditer(r'Target="([^"]+)"', rels):
                    tgt = m.group(1)
                    if tgt.startswith("http"):
                        continue
                    abs_t = Package.resolve(src_part, tgt)
                    if not gen.has(abs_t):
                        continue
                    data = gen.read(abs_t)
                    ext = Path(abs_t).suffix.lower().lstrip(".")
                    sub = "embeddings" if "/embeddings/" in abs_t else ("charts" if "/charts/" in abs_t else "media")
                    newname = f"ppt/{sub}/tk_{hashlib.sha1(data).hexdigest()[:10]}_{n}.{ext}"
                    new_parts[newname] = data
                    if ext == "xml":
                        # colors/style 파트: 원본 Override 콘텐츠 타입 복사
                        _, ov = gen.content_types()
                        if abs_t in ov:
                            ct_overrides.append((newname, ov[abs_t]))
                    elif ext not in ct_defaults:
                        ct_defaults[ext] = DEFAULT_EXT.get(ext, "application/octet-stream")
                    rels = rels.replace(f'Target="{tgt}"', f'Target="../{sub}/{Path(newname).name}"')
                new_parts[gen.rels_name(dst)] = rels.encode("utf-8")
            return dst

        for ref in gen.slides():
            if not gen.has(ref.part):
                continue
            n = next_num("s", r"ppt/slides/slide(\d+)\.xml$")
            dst = f"ppt/slides/slide{n}.xml"
            xml = gen.read(ref.part).decode("utf-8")
            rels_xml = gen.read(gen.rels_name(ref.part)).decode("utf-8") if gen.has(gen.rels_name(ref.part)) else '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
            target_layout = cov_part if ref.index == 1 and cover_layout else lay_part
            for rid, rel in gen.rels(ref.part).items():
                if rel.mode == "External":
                    continue
                src = Package.resolve(ref.part, rel.target)
                if rel.rtype == "slideLayout":
                    rels_xml = re.sub(r'(<Relationship\b[^>]*Id="%s"[^>]*Target=")[^"]+(")' % re.escape(rid), r"\g<1>../slideLayouts/%s\2" % Path(target_layout).name, rels_xml)
                elif rel.rtype == "notesSlide" and gen.has(src):
                    if not notes_master_rel_target:
                        rels_xml = re.sub(r'<Relationship\b[^>]*Id="%s"[^>]*/>' % re.escape(rid), "", rels_xml)
                        warnings.append(f"슬라이드 {ref.index}: 양식에 notesMaster 가 없어 발표자 노트를 뺐다")
                        continue
                    nn = next_num("n", r"ppt/notesSlides/notesSlide(\d+)\.xml$")
                    ndst = f"ppt/notesSlides/notesSlide{nn}.xml"
                    new_parts[ndst] = gen.read(src)
                    nrels = gen.read(gen.rels_name(src)).decode("utf-8") if gen.has(gen.rels_name(src)) else ""
                    nrels = re.sub(r'Target="\.\./slides/slide\d+\.xml"', f'Target="../slides/{Path(dst).name}"', nrels)
                    nrels = re.sub(r'Target="\.\./notesMasters/notesMaster\d+\.xml"', f'Target="../notesMasters/{Path(notes_master_rel_target).name}"', nrels)
                    new_parts[gen.rels_name(ndst)] = nrels.encode("utf-8")
                    ct_overrides.append((ndst, CT["notesSlide"]))
                    rels_xml = rels_xml.replace(f'Target="{rel.target}"', f'Target="../notesSlides/{Path(ndst).name}"')
                elif rel.rtype == "chart" and gen.has(src):
                    cdst = copy_chart(src)
                    rels_xml = rels_xml.replace(f'Target="{rel.target}"', f'Target="../charts/{Path(cdst).name}"')
                elif rel.rtype == "image" and gen.has(src):
                    mdst = copy_media(src)
                    rels_xml = rels_xml.replace(f'Target="{rel.target}"', f'Target="../media/{Path(mdst).name}"')
                elif rel.rtype in ("slideMaster", "theme"):
                    rels_xml = re.sub(r'<Relationship\b[^>]*Id="%s"[^>]*/>' % re.escape(rid), "", rels_xml)
            # 배경: 생성 덱 레이아웃 배경이 양식 배경과 다르면 슬라이드 배경으로
            gen_lay = gen.layout_part(ref.part) or ""
            gbg = _bg_color(gen, gen_lay) or _bg_color(gen, gen.master_part(gen_lay) or "")
            if gbg and gbg != tpl_bg and "<p:bg>" not in xml:
                xml = xml.replace("<p:cSld>", f'<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="{gbg}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>', 1)
            # 쪽번호·푸터 자리표시자 (양식 위치·서식 상속)
            extra = ""
            ids = [int(x) for x in re.findall(r'<p:cNvPr id="(\d+)"', xml)]
            nid = max(ids or [1]) + 1
            if lay_has_sldnum:
                extra += f'<p:sp><p:nvSpPr><p:cNvPr id="{nid}" name="Slide Number Placeholder"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldNum" sz="quarter" idx="12"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:fld id="{{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}}" type="slidenum"><a:rPr lang="ko-KR" altLang="en-US"/><a:t>‹#›</a:t></a:fld><a:endParaRPr lang="ko-KR" altLang="en-US"/></a:p></p:txBody></p:sp>'
                nid += 1
            if footer and lay_has_ftr:
                ftxt = footer.replace("&", "&amp;").replace("<", "&lt;")
                extra += f'<p:sp><p:nvSpPr><p:cNvPr id="{nid}" name="Footer Placeholder"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="ftr" sz="quarter" idx="11"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="ko-KR" altLang="en-US"/><a:t>{ftxt}</a:t></a:r></a:p></p:txBody></p:sp>'
            if extra:
                xml = xml.replace("</p:spTree>", extra + "</p:spTree>", 1)
            new_parts[dst] = xml.encode("utf-8")
            new_parts[gen.rels_name(dst)] = rels_xml.encode("utf-8")
            ct_overrides.append((dst, CT["slide"]))
            rid = f"rId{next_rid}"
            next_rid += 1
            pres_rels_add.append(f'<Relationship Id="{rid}" Type="{REL}slide" Target="slides/{Path(dst).name}"/>')
            new_order.append((str(next_sld), rid))
            next_sld += 1

        # 양식 기존 슬라이드 처리
        drop_parts: set = set()
        kept: List[Tuple[str, str]] = []
        for r in tpl.slides():
            if keep_template_slides:
                kept.append((r.sld_id, r.rid))
                continue
            drop_parts.add(r.part)
            drop_parts.add(tpl.rels_name(r.part))
            np_ = tpl.notes_part(r.part)
            if np_:
                drop_parts.add(np_)
                drop_parts.add(tpl.rels_name(np_))
            tpl_pres_rels = re.sub(r'<Relationship Id="%s"[^>]*/>' % re.escape(r.rid), "", tpl_pres_rels)
            tpl_ct = tpl_ct.replace(f'<Override PartName="/{r.part}" ContentType="{CT["slide"]}"/>', "")
            if np_:
                tpl_ct = tpl_ct.replace(f'<Override PartName="/{np_}" ContentType="{CT["notesSlide"]}"/>', "")
        lst = "".join(f'<p:sldId id="{sid}" r:id="{rid}"/>' for sid, rid in kept + new_order)
        if "<p:sldIdLst" in tpl_pres:
            tpl_pres = re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>|<p:sldIdLst/>", f"<p:sldIdLst>{lst}</p:sldIdLst>", tpl_pres, flags=re.S)
        else:
            tpl_pres = re.sub(r"(<p:sldSz)", f"<p:sldIdLst>{lst}</p:sldIdLst>" + r"\1", tpl_pres, count=1)
        tpl_pres_rels = tpl_pres_rels.replace("</Relationships>", "".join(pres_rels_add) + "</Relationships>")
        # content types
        defaults, overrides = tpl.content_types()
        add_ct = "".join(f'<Default Extension="{e}" ContentType="{t}"/>' for e, t in ct_defaults.items() if e not in defaults)
        add_ct += "".join(f'<Override PartName="/{p}" ContentType="{t}"/>' for p, t in ct_overrides if p not in overrides)
        tpl_ct = tpl_ct.replace("</Types>", add_ct + "</Types>")
        # 쓰기 (POTX 템플릿이어도 출력은 프레젠테이션 콘텐츠 타입으로)
        tpl_ct = tpl_ct.replace("presentationml.template.main+xml", "presentationml.presentation.main+xml")
        out_p = Path(out)
        with zipfile.ZipFile(template) as zin, zipfile.ZipFile(out_p, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename in drop_parts or info.filename in new_parts:
                    continue
                data = zin.read(info.filename)
                if info.filename == "ppt/presentation.xml":
                    data = tpl_pres.encode("utf-8")
                elif info.filename == "ppt/_rels/presentation.xml.rels":
                    data = tpl_pres_rels.encode("utf-8")
                elif info.filename == "[Content_Types].xml":
                    data = tpl_ct.encode("utf-8")
                zout.writestr(info.filename, data)
            for name, data in new_parts.items():
                zout.writestr(name, data)
    finally:
        gen.close()
        tpl.close()
    chk = check(str(out_p))
    result = {"ok": chk["ok"], "output": str(out_p) if chk["ok"] else None, "layout": lay_name, "cover_layout": cov_name if cover_layout else None, "slides": len(new_order) + len(kept), "kept_template_slides": len(kept), "warnings": warnings, "check": {"ok": chk["ok"], "errors": chk["errors"][:5], "warnings": len(chk["warnings"])},
              "note": "양식 마스터의 로고·배경·푸터 그래픽을 물려받는다. 생성 덱의 글꼴·색은 유지된다. 반드시 render 로 확인한다 (양식 그래픽과 본문이 겹칠 수 있음 → canvas.margin 을 template-contract 의 safe_area_in 으로 맞춰 재빌드)."}
    if not chk["ok"]:
        rejected = out_p.with_suffix(".rejected.pptx")
        out_p.replace(rejected)
        result["rejected_output"] = str(rejected)
    return result


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py inherit")
    ap.add_argument("generated", help="이 툴킷이 만든 deck.pptx")
    ap.add_argument("template", help="기관 양식 .pptx / .potx")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--layout", default=None, help="본문 레이아웃 이름 일부 또는 번호 (기본: 제목만 → 빈 화면 → 첫 레이아웃)")
    ap.add_argument("--cover-layout", default=None, help="1번 슬라이드(표지)에 쓸 레이아웃")
    ap.add_argument("--keep-template-slides", action="store_true", help="양식의 기존 슬라이드를 앞에 유지")
    ap.add_argument("--footer", default=None, help="양식 푸터 자리표시자에 넣을 문구")
    a = ap.parse_args(argv)
    try:
        r = inherit(a.generated, a.template, a.out, a.layout, a.cover_layout, a.keep_template_slides, a.footer)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1
