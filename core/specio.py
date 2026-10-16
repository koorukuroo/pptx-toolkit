"""deck-spec.json 로드·프로파일 병합·경량 스키마 검증 (jsonschema 없이)."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = ROOT / "references" / "style-profiles.json"
ARCHETYPES_PATH = ROOT / "references" / "slide-archetypes.json"
SCHEMA_PATH = ROOT / "schemas" / "deck-spec.schema.json"


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_profiles() -> Dict[str, Any]:
    return load_json(PROFILES_PATH)["profiles"]


def load_archetypes() -> Dict[str, Any]:
    return load_json(ARCHETYPES_PATH)["archetypes"]


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def resolve_tokens(spec: Dict[str, Any]) -> Dict[str, Any]:
    """route.style_profile 토큰 위에 spec.design_tokens(부분 재정의)를 얹은 최종 토큰."""
    profiles = load_profiles()
    name = spec.get("route", {}).get("style_profile")
    if name not in profiles:
        raise ValueError(f"알 수 없는 style_profile: {name} (가능: {', '.join(profiles)})")
    tokens = deepcopy(profiles[name]["tokens"])
    tokens = deep_merge(tokens, spec.get("design_tokens") or {})
    tokens["_profile"] = name
    return tokens


# --- 경량 스키마 검증 ----------------------------------------------------------

def _type_ok(value: Any, t: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(t, True)


def validate_against(schema: Dict[str, Any], value: Any, path: str, errors: List[str], root: Dict[str, Any]) -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/"):
            node: Any = root
            for part in ref[2:].split("/"):
                node = node[part]
            validate_against(node, value, path, errors, root)
        return
    t = schema.get("type")
    if t:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, x) for x in types):
            errors.append(f"{path}: 타입 {types} 이어야 함 (현재 {type(value).__name__})")
            return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: 허용값 {schema['enum']} 중 하나여야 함 (현재 {value!r})")
    if isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}.{req}: 필수 항목 누락")
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                validate_against(props[k], v, f"{path}.{k}", errors, root)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{k}: 허용되지 않는 항목")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: 최소 {schema['minItems']}개 필요")
        items = schema.get("items")
        if items:
            for i, item in enumerate(value):
                validate_against(items, item, f"{path}[{i}]", errors, root)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {schema['minimum']} 이상이어야 함")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {schema['maximum']} 이하여야 함")
    if isinstance(value, str):
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: {schema['maxLength']}자 이하여야 함")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: 패턴 {schema['pattern']} 불일치")


def validate_spec(spec: Dict[str, Any]) -> List[str]:
    schema = load_json(SCHEMA_PATH)
    errors: List[str] = []
    validate_against(schema, spec, "$", errors, schema)
    # 의미 검증
    archetypes = load_archetypes()
    profiles = load_profiles()
    sp = spec.get("route", {}).get("style_profile")
    if sp and sp not in profiles:
        errors.append(f"$.route.style_profile: 알 수 없는 프로파일 {sp!r}")
    seen_numbers = set()
    for i, s in enumerate(spec.get("slides", [])):
        a = s.get("archetype")
        if a and a not in archetypes:
            errors.append(f"$.slides[{i}].archetype: 알 수 없는 아키타입 {a!r}")
        n = s.get("number")
        if n in seen_numbers:
            errors.append(f"$.slides[{i}].number: 번호 {n} 중복")
        seen_numbers.add(n)
    ev_ids = {e.get("id") for e in spec.get("evidence", [])}
    for i, s in enumerate(spec.get("slides", [])):
        for eid in s.get("evidence_ids", []) or []:
            if eid not in ev_ids:
                errors.append(f"$.slides[{i}].evidence_ids: 존재하지 않는 evidence {eid!r}")
    return errors


def load_spec(path: str) -> Tuple[Dict[str, Any], List[str]]:
    spec = load_json(Path(path))
    return spec, validate_spec(spec)
