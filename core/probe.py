"""렌더 환경 프로브 — '한글이 실제로 그려지는가'를 덱과 독립적으로 확인한다 (렌더러 신뢰 프로토콜).

LibreOffice 헤드리스(특히 macOS·컨테이너)는 폰트를 못 찾으면 한글을 빈 칸으로 그린다. 그 상태의 렌더를 보고
'텍스트가 없다/넘치지 않는다'고 판단하면 검수가 통째로 틀린다. 그래서 render·bleed 는 먼저 작은 프로브 PPTX
(표준 라이브러리로 직접 만든 OPC 패키지)를 같은 엔진으로 렌더해 글꼴별 잉크 비율을 재고, 한글이 비면
font_environment=failed 로 분리 보고한다. 결과는 엔진 경로·수정시각 기준으로 캐시한다.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CACHE_DIR = Path(os.environ.get("PPTX_TOOLKIT_CACHE", Path.home() / ".cache" / "pptx-toolkit"))
PROBE_FAMILIES = ["Paperlogy", "Pretendard", "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", "Arial"]
HANGUL_SAMPLE = "한글 렌더 확인 가나다라마바사 — 글꼴이 없으면 이 줄은 비어 보입니다"

_CT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""

_PRES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
<p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst>
<p:sldSz cx="12192000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""

_PRES_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>"""

_MASTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
<p:txStyles><p:titleStyle><a:lvl1pPr><a:defRPr sz="4400"/></a:lvl1pPr></p:titleStyle><p:bodyStyle><a:lvl1pPr><a:defRPr sz="1800"/></a:lvl1pPr></p:bodyStyle><p:otherStyle><a:lvl1pPr><a:defRPr sz="1800"/></a:lvl1pPr></p:otherStyle></p:txStyles>
</p:sldMaster>"""

_MASTER_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""

_LAYOUT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""

_LAYOUT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""

_THEME = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="probe">
<a:themeElements>
<a:clrScheme name="probe"><a:dk1><a:srgbClr val="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="1F2937"/></a:dk2><a:lt2><a:srgbClr val="F3F4F6"/></a:lt2><a:accent1><a:srgbClr val="003764"/></a:accent1><a:accent2><a:srgbClr val="E4032E"/></a:accent2><a:accent3><a:srgbClr val="346FB2"/></a:accent3><a:accent4><a:srgbClr val="228738"/></a:accent4><a:accent5><a:srgbClr val="9E6A00"/></a:accent5><a:accent6><a:srgbClr val="DE3412"/></a:accent6><a:hlink><a:srgbClr val="0B78CB"/></a:hlink><a:folHlink><a:srgbClr val="8A949E"/></a:folHlink></a:clrScheme>
<a:fontScheme name="probe"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>
<a:fmtScheme name="probe"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
</a:themeElements>
</a:theme>"""

_SLIDE_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""

EMU = 914400


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _slide_xml(families: List[str]) -> Tuple[str, List[Tuple[str, Tuple[float, float, float, float]]]]:
    """글꼴별로 한 행씩 한글 문장을 쓴다. 반환: (xml, [(family, box_in)])"""
    rows = []
    shapes = []
    n = len(families)
    row_h = 7.5 / (n + 1)
    for i, fam in enumerate(families):
        x, y, w, h = 0.4, 0.3 + i * row_h, 12.5, row_h - 0.1
        rows.append((fam, (x, y, w, h)))
        shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i + 2}" name="probe-{_esc(fam)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{int(x * EMU)}" y="{int(y * EMU)}"/><a:ext cx="{int(w * EMU)}" cy="{int(h * EMU)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"/><a:lstStyle/><a:p>'
            f'<a:r><a:rPr lang="ko-KR" altLang="en-US" sz="3600" b="1" dirty="0"><a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:latin typeface="{_esc(fam)}"/><a:ea typeface="{_esc(fam)}"/><a:cs typeface="{_esc(fam)}"/></a:rPr><a:t>{_esc(fam)}: {_esc(HANGUL_SAMPLE)}</a:t></a:r>'
            f'</a:p></p:txBody></p:sp>'
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        + "".join(shapes)
        + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
    )
    return xml, rows


def make_probe_pptx(path: Path, families: Optional[List[str]] = None) -> List[Tuple[str, Tuple[float, float, float, float]]]:
    fams = families or PROBE_FAMILIES
    slide_xml, rows = _slide_xml(fams)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _ROOT_RELS)
        z.writestr("ppt/presentation.xml", _PRES)
        z.writestr("ppt/_rels/presentation.xml.rels", _PRES_RELS)
        z.writestr("ppt/slideMasters/slideMaster1.xml", _MASTER)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _MASTER_RELS)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", _LAYOUT)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _LAYOUT_RELS)
        z.writestr("ppt/theme/theme1.xml", _THEME)
        z.writestr("ppt/slides/slide1.xml", slide_xml)
        z.writestr("ppt/slides/_rels/slide1.xml.rels", _SLIDE_RELS)
    return rows


def _ink_ratio(W: int, H: int, px: bytes, box: Tuple[float, float, float, float], slide_w_in: float = 13.333, slide_h_in: float = 7.5) -> float:
    x0 = int(box[0] / slide_w_in * W)
    x1 = int((box[0] + box[2]) / slide_w_in * W)
    y0 = int(box[1] / slide_h_in * H)
    y1 = int((box[1] + box[3]) / slide_h_in * H)
    cnt = tot = 0
    for y in range(max(0, y0), min(H, y1)):
        row = px[y * W * 3:(y + 1) * W * 3]
        for x in range(max(0, x0), min(W, x1)):
            tot += 1
            if row[x * 3] < 128 and row[x * 3 + 1] < 128 and row[x * 3 + 2] < 128:
                cnt += 1
    return cnt / tot if tot else 0.0


def probe(engine: str = "libreoffice", families: Optional[List[str]] = None, refresh: bool = False) -> Dict[str, Any]:
    """글꼴별 한글 잉크 비율. ok = 요청 글꼴 중 하나라도 한글이 그려짐 (실제 사용 글꼴은 families[0] 기준으로 별도 보고)."""
    from .render import _read_ppm, find_soffice, to_pdf_libreoffice, to_pdf_powerpoint

    fams = families or PROBE_FAMILIES
    key_src = find_soffice() if engine == "libreoffice" else "powerpoint"
    try:
        mtime = os.path.getmtime(key_src) if key_src and os.path.exists(key_src) else 0
    except OSError:
        mtime = 0
    cache_file = CACHE_DIR / f"probe-{engine}.json"
    if not refresh and cache_file.exists():
        try:
            c = json.loads(cache_file.read_text(encoding="utf-8"))
            if c.get("engine_path") == key_src and c.get("engine_mtime") == mtime and set(c.get("ink", {})) >= set(fams) and time.time() - c.get("at", 0) < 7 * 86400:
                c["cached"] = True
                return c
        except Exception:  # noqa: BLE001
            pass
    work = Path(tempfile.mkdtemp(prefix="pptx-probe-"))
    try:
        pptx = work / "probe.pptx"
        rows = make_probe_pptx(pptx, fams)
        pdf = to_pdf_powerpoint(pptx, work) if engine == "powerpoint" else to_pdf_libreoffice(pptx, work)
        if not shutil.which("pdftoppm"):
            raise RuntimeError("pdftoppm 필요")
        subprocess.run(["pdftoppm", "-r", "40", "-f", "1", "-l", "1", str(pdf), str(work / "p")], check=True, capture_output=True)
        ppm = next(iter(sorted(work.glob("p-*.ppm"))), None)
        if ppm is None:
            raise RuntimeError("프로브 렌더 실패")
        W, H, px = _read_ppm(ppm)
        ink = {fam: round(_ink_ratio(W, H, px, box), 4) for fam, box in rows}
        drawn = {fam: v >= 0.004 for fam, v in ink.items()}
        res: Dict[str, Any] = {
            "ok": any(drawn.values()),
            "engine": engine, "engine_path": key_src, "engine_mtime": mtime, "at": time.time(),
            "ink": ink, "hangul_drawn": drawn,
            "note": "hangul_drawn=false 인 글꼴은 이 환경에서 한글이 그려지지 않는다(미설치 또는 폰트 열거 실패). 그 글꼴로 만든 덱의 렌더는 신뢰할 수 없다.",
        }
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return res
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py probe")
    ap.add_argument("--engine", choices=["libreoffice", "powerpoint"], default="libreoffice")
    ap.add_argument("--families", default=",".join(PROBE_FAMILIES))
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = probe(a.engine, [f.strip() for f in a.families.split(",") if f.strip()], a.refresh)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1
