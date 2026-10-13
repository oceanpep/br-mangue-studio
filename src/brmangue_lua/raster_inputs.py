"""Raster loading and validation for aligned model inputs.

The loader converts land-cover, elevation, and optional mask rasters into a
compact cell grid with a Moore-neighbour table. Geometry remains in the raster
domain, so only valid pixels are processed. Soil suitability is optional; when
disabled, a sentinel value is stored and soil-dependent transitions remain
inactive while the other rules continue to run.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re

import numpy as np
import rasterio

from .engine import (
    BrMangueGrid,
)
from .model_states import CLASS_BEHAVIORS, STANDARD_CLASS_STYLES, build_model_state_catalog


SOIL_DISABLED_SENTINEL = -999
MAX_CUSTOM_MODEL_CLASS_CODE = 32767

# Default numeric mapping for the built-in demonstration. Users can replace
# every code through the interface; the core is provider-agnostic.
DEFAULT_LAND_COVER_MAPPING: dict[str, list[int]] = {
    "mangrove": [5],
    "water": [33],
    "natural_accommodation_candidate": [6, 11, 12, 23, 32, 49, 50],
    "managed_land_use_candidate": [14, 15, 18, 19, 20, 21, 35, 36, 39, 40, 41, 46, 47, 48, 62],
    "explicit_restriction": [24, 25, 30],
}
# Backward-compatible alias for older API callers.
DEFAULT_MAPBIOMAS_MAPPING = DEFAULT_LAND_COVER_MAPPING


@dataclass
class RasterInputSet:
    """Compact grid and spatial metadata used for exports."""

    # The compact grid is normally materialized for the interface.  The
    # persistent block runner may temporarily release it after copying the
    # arrays to disk, so the raster metadata remains usable while ``grid`` is
    # absent.
    grid: BrMangueGrid | None
    raster_shape: tuple[int, int]
    valid_rows: np.ndarray
    valid_cols: np.ndarray
    valid_mask: np.ndarray
    profile: dict[str, Any]
    metadata: dict[str, Any]
    n_cells_cached: int | None = None

    def __post_init__(self) -> None:
        if self.n_cells_cached is None:
            if self.grid is None:
                raise ValueError("n_cells_cached is required when grid is unavailable.")
            self.n_cells_cached = int(self.grid.size)

    @property
    def n_cells(self) -> int:
        return int(self.n_cells_cached or 0)

    @property
    def cell_area_km2(self) -> float | None:
        """Return the area of one input cell in km² when the CRS is metric."""
        resolution = self.metadata.get("land_cover", {}).get("resolution", [])
        if len(resolution) < 2:
            return None
        try:
            crs = rasterio.crs.CRS.from_user_input(self.profile.get("crs"))
            if not crs.is_projected:
                return None
            factor = float(crs.linear_units_factor[1])
            width = abs(float(resolution[0])) * factor
            height = abs(float(resolution[1])) * factor
            return (width * height) / 1_000_000.0
        except (TypeError, ValueError, rasterio.errors.CRSError):
            return None

    @property
    def cell_area_m2(self) -> float | None:
        """Return the area of one input cell in square metres."""
        area_km2 = self.cell_area_km2
        return area_km2 * 1_000_000.0 if area_km2 is not None else None

    def write_state_raster(self, state_values: np.ndarray, path: str | Path, *, year: int) -> Path:
        """Write model state codes back to the source raster grid."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if len(state_values) != self.n_cells:
            raise ValueError("The state vector does not match the loaded raster grid.")
        values = np.asarray(state_values)
        if values.size and (
            int(values.min()) < 0 or int(values.max()) > np.iinfo(np.uint16).max
        ):
            raise ValueError("Model state codes must fit in a UInt16 raster.")
        output_dtype = (
            np.uint8
            if not values.size or int(values.max()) <= np.iinfo(np.uint8).max
            else np.uint16
        )
        full = np.zeros(self.raster_shape, dtype=output_dtype)
        full[self.valid_rows, self.valid_cols] = values.astype(output_dtype, copy=False)
        profile = dict(self.profile)
        profile.update(
            count=1,
            dtype=np.dtype(output_dtype).name,
            nodata=0,
            compress="lzw",
            tiled=False,
        )
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(full, 1)
            dst.set_band_description(1, f"land_use_state_{year}")
            dst.update_tags(
                model="BRMANGUE cellular model",
                year=str(year),
                nodata_description="0 = outside valid input envelope",
                model_state_catalog=json.dumps(
                    self.metadata.get("model_state_catalog", {}),
                    ensure_ascii=False,
                ),
                custom_model_classes=json.dumps(
                    self.metadata.get("custom_model_classes", []),
                    ensure_ascii=False,
                ),
            )
        return path


def _same_grid(reference: rasterio.io.DatasetReader, other: rasterio.io.DatasetReader, name: str) -> None:
    if other.shape != reference.shape:
        raise ValueError(f"{name} has dimensions {other.shape}; expected {reference.shape}.")
    if other.crs != reference.crs:
        raise ValueError(f"{name} has CRS {other.crs}; expected {reference.crs}.")
    if not other.transform.almost_equals(reference.transform):
        raise ValueError(f"{name} is not aligned with the land-cover raster.")


def _read_mask(path: str | Path | None, reference: rasterio.io.DatasetReader) -> np.ndarray:
    if path is None:
        return np.ones(reference.shape, dtype=bool)
    with rasterio.open(path) as src:
        _same_grid(reference, src, "Mask")
        data = src.read(1, masked=True)
        return (~np.ma.getmaskarray(data)) & (np.asarray(data.filled(0)) != 0)


def _build_raster_neighbors(index_grid: np.ndarray, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    """Build compact Moore-neighbour indices without Python objects."""
    height, width = index_grid.shape
    result = np.full((rows.size, 8), -1, dtype=np.int32)
    offsets = (
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1), (0, 1),
        (1, -1), (1, 0), (1, 1),
    )
    # Read the eight shifted positions directly from the index grid.  The
    # previous implementation created a full-size temporary array for every
    # direction, which unnecessarily doubled the peak memory of large rasters.
    for k, (dr, dc) in enumerate(offsets):
        source_rows = rows - dr
        source_cols = cols - dc
        inside = (
            (source_rows >= 0) & (source_rows < height)
            & (source_cols >= 0) & (source_cols < width)
        )
        result[inside, k] = index_grid[source_rows[inside], source_cols[inside]]
    return result


def normalize_custom_model_classes(
    custom_classes: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Validate project-defined model states and their built-in behavior profile."""
    result: list[dict[str, Any]] = []
    used_codes: set[int] = set()
    used_names: set[str] = set()
    for item in custom_classes or []:
        try:
            raw_code = item["code"]
            raw_name = item["name"]
            raw_color = item["color"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Each custom class requires a code, name, and color.") from exc
        try:
            code = int(raw_code)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("A custom class code must be an integer.") from exc
        if isinstance(raw_code, bool):
            raise ValueError("A custom class code must be an integer.")
        if not isinstance(raw_code, str) and raw_code != code:
            raise ValueError("A custom class code must be an integer.")
        if not isinstance(raw_name, str) or not isinstance(raw_color, str):
            raise ValueError("Custom class name and color must be strings.")
        name = raw_name.strip()
        color = raw_color.strip()
        behavior = str(item.get("behavior", "fixed")).strip()
        if code < 1 or code > MAX_CUSTOM_MODEL_CLASS_CODE:
            raise ValueError(
                f"A custom class code must be between 1 and {MAX_CUSTOM_MODEL_CLASS_CODE}."
            )
        if code in used_codes:
            raise ValueError(f"Custom model class code {code} is duplicated.")
        if not name or len(name) > 80:
            raise ValueError("A class name must contain between 1 and 80 characters.")
        if name.casefold() in used_names:
            raise ValueError(f"Custom class name '{name}' is duplicated.")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError(
                f"Class color for '{name}' must use hexadecimal #RRGGBB format."
            )
        if behavior not in CLASS_BEHAVIORS:
            raise ValueError(
                f"Behavior profile for class '{name}' is not valid."
            )
        used_codes.add(code)
        used_names.add(name.casefold())
        result.append({
            "code": code,
            "name": name,
            "color": color.lower(),
            "behavior": behavior,
        })
    return sorted(result, key=lambda item: item["code"])


def _map_land_cover_classes(
    values: np.ndarray,
    mapping: dict[str, list[int]] | None = None,
    custom_class_mapping: dict[int, list[int]] | None = None,
    custom_classes: list[dict[str, Any]] | None = None,
    *,
    custom_mapping_mode: bool = False,
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    custom_class_mapping = custom_class_mapping or {}
    class_definitions: list[dict[str, Any]] = []
    source_to_model: dict[str, list[int]] = {}
    state_values = np.zeros(values.shape, dtype=np.uint16)

    if custom_mapping_mode:
        classes_by_code = {int(item["code"]): item for item in custom_classes or []}
        if not classes_by_code:
            raise ValueError("Custom mapping mode requires at least one model class.")
        source_assignments: dict[int, int] = {}
        for class_code, source_codes in custom_class_mapping.items():
            if int(class_code) not in classes_by_code:
                raise ValueError(f"Custom class {class_code} has no class definition.")
            for source_code in source_codes:
                source_code = int(source_code)
                previous = source_assignments.get(source_code)
                if previous is not None:
                    raise ValueError(
                        f"Raster code {source_code} is assigned to more than one custom class."
                    )
                source_assignments[source_code] = int(class_code)
        for source_code in np.unique(values):
            if int(source_code) not in source_assignments:
                raise ValueError(
                    f"Raster code {int(source_code)} has no custom class assignment."
                )
        for source_code, class_code in source_assignments.items():
            state_values[values == source_code] = class_code
        class_definitions = [dict(item) for item in custom_classes or []]
        source_to_model = {
            f"custom_{int(code)}": [int(value) for value in codes]
            for code, codes in custom_class_mapping.items()
        }
        unknown_source_policy = "Every included raster code must have a custom class assignment."
    else:
        effective_mapping = mapping or DEFAULT_LAND_COVER_MAPPING
        behavior_by_source: dict[int, str] = {}
        source_profile_map = {
            "mangrove": "mangrove",
            "water": "water",
            "natural_accommodation_candidate": "natural_vegetation",
            "bare_soil": "bare_soil",
            "natural_vegetation": "natural_vegetation",
            "anthropized": "anthropized",
            "managed_land_use_candidate": "anthropized",
            "explicit_restriction": "anthropized",
        }
        for role, source_codes in effective_mapping.items():
            behavior = source_profile_map.get(str(role), "anthropized")
            for source_code in source_codes:
                source_code = int(source_code)
                previous = behavior_by_source.get(source_code)
                if previous is not None and previous != behavior:
                    raise ValueError(
                        f"Raster code {source_code} belongs to multiple model profiles."
                    )
                behavior_by_source[source_code] = behavior
        observed_codes = {int(code) for code in np.unique(values)}
        custom_source_codes = {
            int(source_code)
            for source_codes in custom_class_mapping.values()
            for source_code in source_codes
        }
        for source_code in observed_codes:
            if source_code in custom_source_codes:
                continue
            behavior_by_source.setdefault(source_code, "anthropized")
        behaviors = sorted(set(behavior_by_source.values()))
        reserved_codes = {int(item["code"]) for item in custom_classes or []}
        available_codes = (code for code in range(1, MAX_CUSTOM_MODEL_CLASS_CODE + 1) if code not in reserved_codes)
        state_code_by_behavior = {
            behavior: next(available_codes) for behavior in behaviors
        }
        for source_code, behavior in behavior_by_source.items():
            state_values[values == source_code] = state_code_by_behavior[behavior]
        for behavior, code in sorted(state_code_by_behavior.items(), key=lambda item: item[1]):
            name, color = STANDARD_CLASS_STYLES[behavior]
            class_definitions.append({
                "code": code,
                "name": name,
                "color": color,
                "behavior": behavior,
            })
        for custom_code, source_codes in custom_class_mapping.items():
            if int(custom_code) not in reserved_codes:
                raise ValueError(f"Custom class {custom_code} has no class definition.")
            for source_code in source_codes:
                source_code = int(source_code)
                if source_code in behavior_by_source:
                    raise ValueError(
                        f"Raster code {source_code} is assigned to both a standard and a custom class."
                    )
                state_values[values == source_code] = int(custom_code)
        class_definitions.extend(dict(item) for item in custom_classes or [])
        source_to_model = {str(key): [int(value) for value in vals] for key, vals in effective_mapping.items()}
        source_to_model.update({
            f"custom_{int(code)}": [int(value) for value in vals]
            for code, vals in custom_class_mapping.items()
        })
        unknown_source_policy = "anthropized"

    model_state_catalog = build_model_state_catalog(class_definitions)
    classes_seen, counts = np.unique(values, return_counts=True)
    return state_values, {
        "source_to_model": source_to_model,
        "unknown_source_codes_policy": unknown_source_policy,
        "source_code_counts_valid": {str(int(code)): int(count) for code, count in zip(classes_seen, counts)},
    }, model_state_catalog


def load_raster_inputs(
    mapbiomas_path: str | Path | None = None,
    elevation_path: str | Path | None = None,
    *,
    land_cover_path: str | Path | None = None,
    terrain_path: str | Path | None = None,
    mask_path: str | Path | None = None,
    soil_path: str | Path | None = None,
    soil_enabled: bool | None = None,
    mapbiomas_band: int = 1,
    mapbiomas_year: int | None = None,
    land_cover_band: int | None = None,
    land_cover_year: int | None = None,
    mapping: dict[str, list[int]] | None = None,
    custom_class_mapping: dict[int, list[int]] | None = None,
    custom_classes: list[dict[str, Any]] | None = None,
    class_mapping_mode: str = "standard",
    exclude_source_codes: list[int] | None = None,
) -> RasterInputSet:
    """Load aligned land-cover and elevation rasters.

    The ``mapbiomas_*`` names remain accepted as legacy aliases. New projects
    should prefer ``land_cover_*``. Band numbers are one-based; the year is
    optional metadata. No particular data provider or product is required.
    """
    if land_cover_path is not None:
        if mapbiomas_path is not None:
            raise ValueError("Provide only one of land_cover_path or mapbiomas_path.")
        mapbiomas_path = land_cover_path
    if terrain_path is not None:
        if elevation_path is not None:
            raise ValueError("Provide only one of terrain_path or elevation_path.")
        elevation_path = terrain_path
    if mapbiomas_path is None or elevation_path is None:
        raise ValueError("Land-cover and elevation rasters are required.")
    if land_cover_band is not None:
        mapbiomas_band = int(land_cover_band)
    if land_cover_year is not None:
        mapbiomas_year = int(land_cover_year)
    mapbiomas_path = Path(mapbiomas_path).resolve()
    elevation_path = Path(elevation_path).resolve()
    if not mapbiomas_path.exists():
        raise FileNotFoundError(mapbiomas_path)
    if not elevation_path.exists():
        raise FileNotFoundError(elevation_path)
    if mapbiomas_band < 1:
        raise ValueError("mapbiomas_band must be positive.")
    if soil_enabled is None:
        soil_enabled = soil_path is not None
    if soil_enabled and soil_path is None:
        raise ValueError("soil_enabled=True requires soil_path.")

    custom_definitions = normalize_custom_model_classes(custom_classes)
    custom_class_codes = {int(item["code"]) for item in custom_definitions}
    normalized_custom_mapping = {
        int(code): [int(source_code) for source_code in source_codes]
        for code, source_codes in (custom_class_mapping or {}).items()
    }
    unknown_custom_codes = set(normalized_custom_mapping).difference(custom_class_codes)
    if unknown_custom_codes:
        raise ValueError(
            "The mapping contains custom classes without definitions: "
            f"{sorted(unknown_custom_codes)}."
        )
    if class_mapping_mode not in {"standard", "custom"}:
        raise ValueError("class_mapping_mode must be 'standard' or 'custom'.")
    effective_mapping = {} if class_mapping_mode == "custom" else (mapping or DEFAULT_LAND_COVER_MAPPING)
    source_assignments: dict[int, str] = {}
    for role, source_codes in effective_mapping.items():
        for source_code in source_codes:
            source_assignments[int(source_code)] = role
    for custom_code, source_codes in normalized_custom_mapping.items():
        for source_code in source_codes:
            previous_role = source_assignments.get(source_code)
            if previous_role is not None:
                raise ValueError(
                    f"Source code {source_code} is assigned to more than one class "
                    f"({previous_role} and custom_{custom_code})."
                )
            source_assignments[source_code] = f"custom_{custom_code}"

    with rasterio.open(mapbiomas_path) as mb, rasterio.open(elevation_path) as dem:
        if mapbiomas_band > mb.count:
            raise ValueError(f"The land-cover raster has {mb.count} bands; requested band: {mapbiomas_band}.")
        _same_grid(mb, dem, "Elevation")
        mapbiomas = mb.read(mapbiomas_band, masked=True)
        elevation = dem.read(1, masked=True)
        map_mask = ~np.ma.getmaskarray(mapbiomas)
        dem_mask = ~np.ma.getmaskarray(elevation)
        spatial_mask = _read_mask(mask_path, mb)
        mb_values = np.asarray(mapbiomas.filled(0))
        # Some categorical GeoTIFFs contain IEEE NaN values even when their
        # declared nodata value is -9999.  NaN is not masked by rasterio in
        # that case and would later reach ``int(code)`` while building the
        # class-count metadata.  Treat non-finite categorical pixels as
        # invalid input cells before any class mapping or integer conversion.
        if np.issubdtype(mb_values.dtype, np.floating):
            finite_map = np.isfinite(mb_values)
            map_mask &= finite_map
            mb_values = np.where(finite_map, mb_values, 0)
        dem_values = np.asarray(elevation.filled(np.nan), dtype=np.float64)
        excluded = np.asarray(exclude_source_codes or [], dtype=mb_values.dtype)
        valid = (
            spatial_mask
            & map_mask
            & dem_mask
            & (mb_values != 0)
            & np.isfinite(dem_values)
            & (~np.isin(mb_values, excluded) if excluded.size else True)
        )
        rows, cols = np.where(valid)
        if rows.size == 0:
            raise ValueError("The valid intersection of the rasters and mask is empty.")
        land_cover_state, mapping_meta, model_state_catalog = _map_land_cover_classes(
            mb_values[valid],
            mapping,
            normalized_custom_mapping,
            custom_definitions,
            custom_mapping_mode=class_mapping_mode == "custom",
        )
        relative_elevation = dem_values[valid]

        # Raster dimensions are safely below the int32 limit and compact
        # coordinates substantially reduce the setup footprint for large
        # domains.  Rasterio and NumPy accept these arrays for indexing.
        rows = rows.astype(np.int32, copy=False)
        cols = cols.astype(np.int32, copy=False)

        soil_values = np.full(rows.size, SOIL_DISABLED_SENTINEL, dtype=np.int16)
        soil_meta: dict[str, Any] = {
            "enabled": bool(soil_enabled),
            "path": str(Path(soil_path).resolve()) if soil_path else None,
            "disabled_sentinel": SOIL_DISABLED_SENTINEL,
        }
        if soil_enabled and soil_path is not None:
            with rasterio.open(soil_path) as soil:
                _same_grid(mb, soil, "Mangrove suitability")
                soil_raw = soil.read(1, masked=True)
                soil_valid = ~np.ma.getmaskarray(soil_raw)
                soil_array = np.asarray(soil_raw.filled(SOIL_DISABLED_SENTINEL), dtype=np.float64)
                selected = soil_array[valid]
                selected_valid = soil_valid[valid] & np.isfinite(selected)
                if np.any(selected_valid & (selected != np.round(selected))):
                    raise ValueError("The soil layer contains non-integer values.")
                soil_values[selected_valid] = np.round(selected[selected_valid]).astype(np.int16)
                soil_meta.update({
                    "nodata_cells_on_model_domain": int(np.count_nonzero(~selected_valid)),
                    "class_counts": {
                        str(int(code)): int(count)
                        for code, count in zip(*np.unique(soil_values[selected_valid], return_counts=True))
                    },
                })

        # Release masked full-raster temporaries before constructing the
        # neighbour table.  Only the compact state vectors and valid mask are
        # needed from this point onward.
        del mapbiomas, elevation, map_mask, dem_mask, mb_values, dem_values

        index_grid = np.full(mb.shape, -1, dtype=np.int32)
        index_grid[rows, cols] = np.arange(rows.size, dtype=np.int32)
        neighbors = _build_raster_neighbors(index_grid, rows, cols)
        profile = mb.profile.copy()
        profile.update(count=1, dtype="uint8", nodata=0)
        # A VRT can be used as an input mosaic, but it is read-only. Outputs
        # must always be materialized as GeoTIFFs regardless of input driver.
        profile["driver"] = "GTiff"
        grid = BrMangueGrid(
            land_cover_state=land_cover_state,
            relative_elevation=relative_elevation,
            soil_class=soil_values,
            column=cols,
            row=rows,
            neighbors=neighbors,
            source_path=str(mapbiomas_path),
            crs_wkt=mb.crs.to_wkt() if mb.crs else None,
            model_state_catalog=model_state_catalog,
        )
        metadata = {
            "land_cover": {
                "path": str(mapbiomas_path),
                "reference_year": int(mapbiomas_year) if mapbiomas_year is not None else None,
                "band": int(mapbiomas_band),
                "shape": [int(mb.height), int(mb.width)],
                "crs": mb.crs.to_string() if mb.crs else None,
                "resolution": [float(mb.res[0]), float(mb.res[1])],
                "mapping": mapping_meta,
            },
            "custom_model_classes": custom_definitions,
            "model_state_catalog": model_state_catalog,
            "elevation": {
                "path": str(elevation_path),
                "nodata": dem.nodata,
                "min_valid_m": float(np.nanmin(relative_elevation)),
                "max_valid_m": float(np.nanmax(relative_elevation)),
            },
            "mask": {
                "path": str(Path(mask_path).resolve()) if mask_path else None,
                "valid_cells": int(np.count_nonzero(valid)),
                "excluded_source_codes": [int(code) for code in excluded.tolist()],
            },
            "soil": soil_meta,
            "grid": {
                "cells": int(rows.size),
                "neighbor_type": "Moore-8 compact index table",
                "cell_width_map_units": float(abs(mb.res[0])),
                "cell_height_map_units": float(abs(mb.res[1])),
                "cell_area_m2": (
                    float(abs(mb.res[0]) * abs(mb.res[1]) * float(mb.crs.linear_units_factor[1]))
                    if mb.crs is not None and mb.crs.is_projected
                    else None
                ),
                "cell_area_km2": (
                    float(
                        abs(mb.res[0])
                        * abs(mb.res[1])
                        * float(mb.crs.linear_units_factor[1]) ** 2
                        / 1_000_000.0
                    )
                    if mb.crs is not None and mb.crs.is_projected
                    else None
                ),
                "valid_row_min": int(rows.min()),
                "valid_row_max": int(rows.max()),
                "valid_col_min": int(cols.min()),
                "valid_col_max": int(cols.max()),
            },
        }
        return RasterInputSet(
            grid=grid,
            raster_shape=mb.shape,
            valid_rows=rows,
            valid_cols=cols,
            valid_mask=valid,
            profile=profile,
            metadata=metadata,
        )


def write_input_metadata(inputs: RasterInputSet, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inputs.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
