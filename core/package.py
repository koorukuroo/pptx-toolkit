"""PPTX 패키지(OPC ZIP) 접근 유틸리티.

ElementTree는 읽기 전용으로만 쓴다. 쓰기(round-trip)는 네임스페이스 접두사를
재작성하므로, XML을 고칠 때는 문자열 치환 후 원본 바이트를 그대로 zip에 넣는다.
"""
from __future__ import annotations

import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple
from xml.etree import ElementTree as ET

EMU_PER_INCH = 914400
EMU_PER_PT = 12700

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}


def emu_to_in(v: int | float) -> float:
    return float(v) / EMU_PER_INCH


def emu_to_pt(v: int | float) -> float:
    return float(v) / EMU_PER_PT


def q(tag: str) -> str:
    """'p:sp' → '{ns}sp'"""
    prefix, local = tag.split(":")
    return "{%s}%s" % (NS[prefix], local)


def parse_xml(data: bytes) -> ET.Element:
    # 외부 엔티티는 ElementTree 기본 파서가 해석하지 않는다(확장 없음).
    return ET.fromstring(data)


@dataclass
class Rel:
    rid: str
    rtype: str
    target: str
    mode: str = "Internal"


@dataclass
class SlideRef:
    index: int          # 1-based 표시 순서
    part: str           # 'ppt/slides/slide3.xml'
    rid: str
    sld_id: str


@dataclass
class Package:
    path: Path
    zf: zipfile.ZipFile
    names: List[str] = field(default_factory=list)

    @classmethod
    def open(cls, path: str | os.PathLike) -> "Package":
        p = Path(path)
        zf = zipfile.ZipFile(p, "r")
        return cls(path=p, zf=zf, names=zf.namelist())

    def close(self) -> None:
        self.zf.close()

    def __enter__(self) -> "Package":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- 파트 접근 -------------------------------------------------------
    def has(self, name: str) -> bool:
        return name in self.names

    def read(self, name: str) -> bytes:
        return self.zf.read(name)

    def xml(self, name: str) -> ET.Element:
        return parse_xml(self.read(name))

    def rels_name(self, part: str) -> str:
        d, f = os.path.split(part)
        return f"{d}/_rels/{f}.rels" if d else f"_rels/{f}.rels"

    def rels(self, part: str) -> Dict[str, Rel]:
        rn = self.rels_name(part)
        out: Dict[str, Rel] = {}
        if not self.has(rn):
            return out
        root = self.xml(rn)
        for el in root.findall("rel:Relationship", NS):
            rid = el.get("Id", "")
            out[rid] = Rel(
                rid=rid,
                rtype=el.get("Type", "").rsplit("/", 1)[-1],
                target=el.get("Target", ""),
                mode=el.get("TargetMode", "Internal"),
            )
        return out

    @staticmethod
    def resolve(part: str, target: str) -> str:
        """rels Target(상대 경로) → 패키지 절대 파트명"""
        if target.startswith("/"):
            return target.lstrip("/")
        base = os.path.dirname(part)
        return os.path.normpath(os.path.join(base, target)).replace("\\", "/")

    # --- 프레젠테이션 구조 ------------------------------------------------
    def slide_size(self) -> Tuple[int, int]:
        root = self.xml("ppt/presentation.xml")
        sz = root.find("p:sldSz", NS)
        if sz is None:
            return (12192000, 6858000)
        return (int(sz.get("cx")), int(sz.get("cy")))

    def slides(self) -> List[SlideRef]:
        root = self.xml("ppt/presentation.xml")
        rels = self.rels("ppt/presentation.xml")
        out: List[SlideRef] = []
        lst = root.find("p:sldIdLst", NS)
        if lst is None:
            return out
        for i, el in enumerate(lst.findall("p:sldId", NS), start=1):
            rid = el.get(q("r:id"))
            rel = rels.get(rid)
            part = self.resolve("ppt/presentation.xml", rel.target) if rel else ""
            out.append(SlideRef(index=i, part=part, rid=rid or "", sld_id=el.get("id", "")))
        return out

    def notes_part(self, slide_part: str) -> Optional[str]:
        for rel in self.rels(slide_part).values():
            if rel.rtype == "notesSlide":
                return self.resolve(slide_part, rel.target)
        return None

    def layout_part(self, slide_part: str) -> Optional[str]:
        for rel in self.rels(slide_part).values():
            if rel.rtype == "slideLayout":
                return self.resolve(slide_part, rel.target)
        return None

    def master_part(self, layout_part: str) -> Optional[str]:
        for rel in self.rels(layout_part).values():
            if rel.rtype == "slideMaster":
                return self.resolve(layout_part, rel.target)
        return None

    def chart_parts(self, slide_part: str) -> List[str]:
        return [self.resolve(slide_part, r.target) for r in self.rels(slide_part).values() if r.rtype == "chart"]

    def image_targets(self, slide_part: str) -> Dict[str, str]:
        return {rid: self.resolve(slide_part, r.target) for rid, r in self.rels(slide_part).items() if r.rtype == "image"}

    def content_types(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """(defaults by extension, overrides by partname)"""
        root = self.xml("[Content_Types].xml")
        defaults = {el.get("Extension", "").lower(): el.get("ContentType", "") for el in root.findall("ct:Default", NS)}
        overrides = {el.get("PartName", "").lstrip("/"): el.get("ContentType", "") for el in root.findall("ct:Override", NS)}
        return defaults, overrides


# --- unpack / pack ---------------------------------------------------------

def unpack(pptx: str | os.PathLike, out_dir: str | os.PathLike) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pptx) as zf:
        for info in zf.infolist():
            # zip-slip 방지
            dest = (out / info.filename).resolve()
            if not str(dest).startswith(str(out.resolve())):
                raise ValueError(f"unsafe path in zip: {info.filename}")
            zf.extract(info, out)
    return out


def pack(src_dir: str | os.PathLike, out_pptx: str | os.PathLike) -> Path:
    """디렉터리 → pptx. [Content_Types].xml을 첫 엔트리로, mimetype 순서 규칙 준수."""
    src = Path(src_dir)
    out = Path(out_pptx)
    if out.exists():
        out.unlink()
    files: List[Path] = [p for p in src.rglob("*") if p.is_file()]
    files.sort(key=lambda p: (0 if p.name == "[Content_Types].xml" else 1, str(p)))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, p.relative_to(src).as_posix())
    return out


def image_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """PNG/JPEG/GIF 픽셀 크기 (PIL 없이)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if data[:2] == b"\xff\xd8":
        i = 2
        n = len(data)
        while i + 9 < n:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg_len = int.from_bytes(data[i + 2:i + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h = int.from_bytes(data[i + 5:i + 7], "big")
                w = int.from_bytes(data[i + 7:i + 9], "big")
                return w, h
            i += 2 + seg_len
    return None


def text_of(el: ET.Element) -> str:
    """<a:p> 하나의 텍스트 (a:t, a:br, a:fld 처리)"""
    parts: List[str] = []
    for node in el.iter():
        if node.tag == q("a:t"):
            parts.append(node.text or "")
        elif node.tag == q("a:br"):
            parts.append("\n")
    return "".join(parts)
