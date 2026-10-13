"""Dynamic model-state definitions for user-configured land-cover classes."""

from __future__ import annotations

from typing import Any


CLASS_BEHAVIORS = frozenset(
    {"fixed", "mangrove", "natural_vegetation", "bare_soil", "anthropized", "water"}
)
FLOODABLE_BEHAVIORS = frozenset(
    {"mangrove", "natural_vegetation", "bare_soil", "anthropized"}
)
MIGRATION_CANDIDATE_BEHAVIORS = frozenset({"natural_vegetation", "bare_soil"})

STANDARD_CLASS_STYLES: dict[str, tuple[str, str]] = {
    "mangrove": ("Mangrove", "#006d2c"),
    "natural_vegetation": ("Natural vegetation", "#b2df8a"),
    "water": ("Water", "#2b8cbe"),
    "anthropized": ("Anthropized / blocked", "#fdae61"),
    "bare_soil": ("Bare soil", "#777777"),
    "fixed": ("Fixed class", "#8c6bb1"),
}
MIGRATED_MANGROVE_COLOR = "#7b3294"


def _shade_color(color: str, factor: float = 0.72) -> str:
    value = color.lstrip("#")
    red, green, blue = (int(value[offset : offset + 2], 16) for offset in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(
        round(red * factor), round(green * factor), round(blue * factor)
    )


def build_model_state_catalog(
    base_classes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create stable base and derived state codes for one model project.

    Base class codes are supplied by the project. Flooded-state codes and the
    single ``Migrated mangrove`` code are allocated above the largest base code
    and described in the returned catalog. Numeric values carry no fixed class
    meaning; consumers must use this catalog to interpret output rasters.
    """
    normalized: list[dict[str, Any]] = []
    used_codes: set[int] = set()
    for item in base_classes:
        code = int(item["code"])
        name = str(item["name"]).strip()
        behavior = str(item["behavior"])
        color = str(item["color"]).lower()
        if code < 1 or code > 32767:
            raise ValueError("Base class codes must be between 1 and 32767.")
        if code in used_codes:
            raise ValueError(f"Duplicate model class code: {code}.")
        if behavior not in CLASS_BEHAVIORS:
            raise ValueError(f"Unsupported class behavior: {behavior}.")
        if not name:
            raise ValueError(f"Model class {code} needs a name.")
        if len(color) != 7 or not color.startswith("#"):
            raise ValueError(f"Model class {name!r} needs a #RRGGBB color.")
        int(color[1:], 16)
        used_codes.add(code)
        normalized.append({
            "code": code,
            "name": name,
            "behavior": behavior,
            "color": color,
        })

    if not normalized:
        raise ValueError("At least one base model class is required.")

    states: dict[str, dict[str, Any]] = {}
    flooded_codes: dict[str, int] = {}
    next_code = max(used_codes) + 1
    for item in sorted(normalized, key=lambda value: value["code"]):
        code = int(item["code"])
        states[str(code)] = {
            **item,
            "kind": "class",
            "base_code": code,
        }
        if item["behavior"] in FLOODABLE_BEHAVIORS:
            flooded_code = next_code
            next_code += 1
            flooded_codes[str(code)] = flooded_code
            flooded_name = (
                "Flooded mangrove"
                if item["behavior"] == "mangrove"
                else f"Flooded {item['name']}"
            )
            states[str(flooded_code)] = {
                "code": flooded_code,
                "name": flooded_name,
                "behavior": item["behavior"],
                "color": _shade_color(item["color"]),
                "kind": "flooded",
                "base_code": code,
            }

    migrated_code: int | None = None
    if any(item["behavior"] == "mangrove" for item in normalized):
        migrated_code = next_code
        states[str(migrated_code)] = {
            "code": migrated_code,
            "name": "Migrated mangrove",
            "behavior": "mangrove",
            "color": MIGRATED_MANGROVE_COLOR,
            "kind": "migrated",
            "base_code": None,
        }

    if states and max(int(key) for key in states) > 65535:
        raise ValueError("The model state catalog exceeds the UInt16 raster limit.")

    return {
        "schema_version": 2,
        "states": states,
        "base_codes": sorted(used_codes),
        "flooded_codes": flooded_codes,
        "migrated_mangrove_code": migrated_code,
    }


def state_entry(catalog: dict[str, Any], code: int) -> dict[str, Any] | None:
    """Return one state definition using either string or integer JSON keys."""
    states = catalog.get("states", {})
    return states.get(str(int(code)), states.get(int(code)))


def state_behavior(catalog: dict[str, Any], code: int) -> str | None:
    entry = state_entry(catalog, code)
    return str(entry["behavior"]) if entry else None


def state_kind(catalog: dict[str, Any], code: int) -> str | None:
    entry = state_entry(catalog, code)
    return str(entry["kind"]) if entry else None


def flooded_state_code(catalog: dict[str, Any], base_code: int) -> int | None:
    value = catalog.get("flooded_codes", {}).get(str(int(base_code)))
    return int(value) if value is not None else None


def migrated_mangrove_code(catalog: dict[str, Any]) -> int | None:
    value = catalog.get("migrated_mangrove_code")
    return int(value) if value is not None else None


def active_mangrove_codes(catalog: dict[str, Any]) -> tuple[int, ...]:
    codes = [
        int(code)
        for code, item in catalog.get("states", {}).items()
        if item.get("kind") == "class" and item.get("behavior") == "mangrove"
    ]
    migrated = migrated_mangrove_code(catalog)
    if migrated is not None:
        codes.append(migrated)
    return tuple(sorted(codes))


def count_model_states(values: Any, catalog: dict[str, Any]) -> dict[str, int]:
    """Summarize dynamic class and derived-state counts for trajectory tables."""
    import numpy as np

    state_values = np.asarray(values)
    states = catalog.get("states", {})
    result: dict[str, int] = {}
    profile_counts = {
        "mangrove": 0,
        "vegetation": 0,
        "water": 0,
        "anthropized": 0,
        "bare": 0,
        "flooded_bare": 0,
        "flooded_anthropized": 0,
        "migrated_mangrove": 0,
        "flooded_mangrove": 0,
        "flooded_natural": 0,
    }
    for raw_code, item in states.items():
        code = int(raw_code)
        count = int(np.count_nonzero(state_values == code))
        kind = str(item.get("kind", "class"))
        behavior = str(item.get("behavior", "fixed"))
        result[f"class_{code}"] = count
        if kind == "migrated":
            profile_counts["migrated_mangrove"] += count
        elif kind == "flooded":
            if behavior == "mangrove":
                profile_counts["flooded_mangrove"] += count
            elif behavior == "natural_vegetation":
                profile_counts["flooded_natural"] += count
            elif behavior == "bare_soil":
                profile_counts["flooded_bare"] += count
            elif behavior == "anthropized":
                profile_counts["flooded_anthropized"] += count
            result[f"flooded_class_{int(item['base_code'])}"] = count
        elif kind == "class":
            if behavior == "mangrove":
                profile_counts["mangrove"] += count
            elif behavior == "natural_vegetation":
                profile_counts["vegetation"] += count
            elif behavior == "water":
                profile_counts["water"] += count
            elif behavior == "anthropized":
                profile_counts["anthropized"] += count
            elif behavior == "bare_soil":
                profile_counts["bare"] += count

    result.update(profile_counts)
    result["mangrove_extent"] = (
        profile_counts["mangrove"] + profile_counts["migrated_mangrove"]
    )
    return result
