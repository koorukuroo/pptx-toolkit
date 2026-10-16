"""설치 폰트 탐지와 대체 폰트 제안.

fc-list가 있으면 family 이름으로, 없으면 폰트 디렉터리의 파일명으로 탐지한다.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Set

# 한글 프레젠테이션에 쓰는 폰트의 선호 순서 (상업 이용 가능한 무료 폰트 우선)
KO_FALLBACK = ["Paperlogy", "Pretendard", "Noto Sans KR", "Noto Sans CJK KR", "Apple SD Gothic Neo", "Malgun Gothic", "맑은 고딕", "NanumSquare", "Nanum Gothic", "Arial"]

ALIASES = {
    "paperlogy": ["paperlogy", "페이퍼로지"],
    "pretendard": ["pretendard"],
    "noto sans kr": ["noto sans kr", "notosanskr"],
    "noto sans cjk kr": ["noto sans cjk kr", "notosanscjkkr", "noto sans cjk"],
    "apple sd gothic neo": ["apple sd gothic neo", "applesdgothicneo"],
    "malgun gothic": ["malgun gothic", "맑은 고딕", "malgun"],
    "nanumsquare": ["nanumsquare"],
    "nanum gothic": ["nanum gothic", "nanumgothic"],
}


def font_dirs() -> List[Path]:
    home = Path.home()
    sysname = platform.system()
    dirs: List[Path] = []
    if sysname == "Darwin":
        dirs += [home / "Library/Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts"), Path("/System/Library/Fonts/Supplemental")]
    elif sysname == "Windows":
        dirs += [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts", home / "AppData/Local/Microsoft/Windows/Fonts"]
    else:
        dirs += [home / ".fonts", home / ".local/share/fonts", Path("/usr/share/fonts"), Path("/usr/local/share/fonts")]
    return [d for d in dirs if d.exists()]


def installed_families() -> Set[str]:
    fams: Set[str] = set()
    fc = shutil.which("fc-list")
    if fc:
        try:
            out = subprocess.run([fc, ":", "family"], capture_output=True, text=True, timeout=30).stdout
            for line in out.splitlines():
                for name in line.split(","):
                    name = name.strip()
                    if name:
                        fams.add(name)
        except Exception:
            pass
    for d in font_dirs():
        for p in d.rglob("*"):
            if p.suffix.lower() in (".ttf", ".otf", ".ttc"):
                stem = re.split(r"[-_ ]", p.stem)[0]
                fams.add(stem)
                fams.add(p.stem)
    return fams


def _norm(s: str) -> str:
    return re.sub(r"[\s_-]+", " ", s).strip().lower()


def has_family(family: str, fams: Set[str]) -> bool:
    target = _norm(family)
    keys = ALIASES.get(target, [target])
    normed = {_norm(f) for f in fams}
    compact = {_norm(f).replace(" ", "") for f in fams}
    for k in keys:
        if k in normed or k.replace(" ", "") in compact:
            return True
        if any(f.startswith(k) for f in normed) or any(f.startswith(k.replace(" ", "")) for f in compact):
            return True
    return False


def resolve(requested: List[str]) -> Dict[str, object]:
    fams = installed_families()
    status = {f: has_family(f, fams) for f in requested}
    first = next((f for f in requested if status[f]), None)
    fallback = first or next((f for f in KO_FALLBACK if has_family(f, fams)), "Arial")
    return {"requested": status, "use": fallback, "ko_fallback_available": [f for f in KO_FALLBACK if has_family(f, fams)]}


def main(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pptx.py fonts")
    ap.add_argument("families", nargs="*", default=["Paperlogy", "Pretendard", "Noto Sans KR"])
    a = ap.parse_args(argv)
    print(json.dumps(resolve(a.families), ensure_ascii=False, indent=2))
    return 0
