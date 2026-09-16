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

import numpy as np
import rasterio

from .engine import (
    AREA_ANTROPIZADA,
    BrMangueGrid,
    MAR,
    MANGUE,
    VEGETACAO_TERRESTRE,
)


SOIL_DISABLED_SENTINEL = -999

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

    grid: BrMangueGrid
    raster_shape: tuple[int, int]
    valid_rows: np.ndarray
    valid_cols: np.ndarray
    valid_mask: np.ndarray
    profile: dict[str, Any]
    metadata: dict[str, Any]

    @property
    def n_cells(self) -> int:
        return int(self.grid.size)

    def write_state_raster(self, usos: np.ndarray, path: str | Path, *, year: int) -> Path:
        """Escreve um vetor de estados de volta à grade raster original."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        full = np.zeros(self.raster_shape, dtype=np.uint8)
        if len(usos) != self.n_cells:
            raise ValueError("O vetor de estados não corresponde à grade carregada.")
        full[self.valid_rows, self.valid_cols] = np.asarray(usos, dtype=np.uint8)
        profile = dict(self.profile)
        profile.update(
            count=1,
            dtype="uint8",
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
            )
        return path


def _same_grid(reference: rasterio.io.DatasetReader, other: rasterio.io.DatasetReader, name: str) -> None:
    if other.shape != reference.shape:
        raise ValueError(f"{name} possui dimensões {other.shape}; esperado {reference.shape}.")
    if other.crs != reference.crs:
        raise ValueError(f"{name} possui CRS {other.crs}; esperado {reference.crs}.")
    if not other.transform.almost_equals(reference.transform):
        raise ValueError(f"{name} não está alinhado ao raster de uso e cobertura da terra.")


def _read_mask(path: str | Path | None, reference: rasterio.io.DatasetReader) -> np.ndarray:
    if path is None:
        return np.ones(reference.shape, dtype=bool)
    with rasterio.open(path) as src:
        _same_grid(reference, src, "Máscara")
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
    for k, (dr, dc) in enumerate(offsets):
        src_r0 = max(0, -dr)
        src_r1 = min(height, height - dr)
        src_c0 = max(0, -dc)
        src_c1 = min(width, width - dc)
        dst_r0 = max(0, dr)
        dst_r1 = min(height, height + dr)
        dst_c0 = max(0, dc)
        dst_c1 = min(width, width + dc)
        shifted = np.full_like(index_grid, -1)
        shifted[dst_r0:dst_r1, dst_c0:dst_c1] = index_grid[src_r0:src_r1, src_c0:src_c1]
        result[:, k] = shifted[rows, cols]
    return result


def _map_land_cover_classes(values: np.ndarray, mapping: dict[str, list[int]] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    mapping = mapping or DEFAULT_LAND_COVER_MAPPING
    usos = np.full(values.shape, AREA_ANTROPIZADA, dtype=np.int16)
    usos[np.isin(values, mapping["mangrove"])] = MANGUE
    usos[np.isin(values, mapping["water"])] = MAR
    usos[np.isin(values, mapping["natural_accommodation_candidate"])] = VEGETACAO_TERRESTRE
    # Managed-use and explicit-restriction classes use the blocked state in
    # the current rule set.
    classes_seen, counts = np.unique(values, return_counts=True)
    return usos, {
        "source_to_model": {key: list(vals) for key, vals in mapping.items()},
        "unknown_source_codes_policy": "AREA_ANTROPIZADA",
        "source_code_counts_valid": {str(int(code)): int(count) for code, count in zip(classes_seen, counts)},
    }


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
    exclude_source_codes: list[int] | None = None,
) -> RasterInputSet:
    """Load aligned land-cover and elevation rasters.

    The ``mapbiomas_*`` names remain accepted as legacy aliases. New projects
    should prefer ``land_cover_*``. Band numbers are one-based; the year is
    optional metadata. No particular data provider or product is required.
    """
    if land_cover_path is not None:
        if mapbiomas_path is not None:
            raise ValueError("Informe apenas land_cover_path ou mapbiomas_path.")
        mapbiomas_path = land_cover_path
    if terrain_path is not None:
        if elevation_path is not None:
            raise ValueError("Informe apenas terrain_path ou elevation_path.")
        elevation_path = terrain_path
    if mapbiomas_path is None or elevation_path is None:
        raise ValueError("Os rasters de uso/cobertura e elevação são obrigatórios.")
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
        raise ValueError("mapbiomas_band deve ser positivo.")
    if soil_enabled is None:
        soil_enabled = soil_path is not None
    if soil_enabled and soil_path is None:
        raise ValueError("soil_enabled=True exige soil_path.")

    with rasterio.open(mapbiomas_path) as mb, rasterio.open(elevation_path) as dem:
        if mapbiomas_band > mb.count:
            raise ValueError(f"O raster de uso/cobertura tem {mb.count} bandas; banda solicitada: {mapbiomas_band}.")
        _same_grid(mb, dem, "Elevação")
        mapbiomas = mb.read(mapbiomas_band, masked=True)
        elevation = dem.read(1, masked=True)
        map_mask = ~np.ma.getmaskarray(mapbiomas)
        dem_mask = ~np.ma.getmaskarray(elevation)
        spatial_mask = _read_mask(mask_path, mb)
        mb_values = np.asarray(mapbiomas.filled(0))
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
            raise ValueError("A interseção válida entre os rasters e a máscara está vazia.")
        usos, mapping_meta = _map_land_cover_classes(mb_values[valid], mapping)
        alt2 = dem_values[valid]

        soil_values = np.full(rows.size, SOIL_DISABLED_SENTINEL, dtype=np.int16)
        soil_meta: dict[str, Any] = {
            "enabled": bool(soil_enabled),
            "path": str(Path(soil_path).resolve()) if soil_path else None,
            "disabled_sentinel": SOIL_DISABLED_SENTINEL,
        }
        if soil_enabled and soil_path is not None:
            with rasterio.open(soil_path) as soil:
                _same_grid(mb, soil, "Aptidão de mangue")
                soil_raw = soil.read(1, masked=True)
                soil_valid = ~np.ma.getmaskarray(soil_raw)
                soil_array = np.asarray(soil_raw.filled(SOIL_DISABLED_SENTINEL), dtype=np.float64)
                selected = soil_array[valid]
                selected_valid = soil_valid[valid] & np.isfinite(selected)
                if np.any(selected_valid & (selected != np.round(selected))):
                    raise ValueError("A camada de solo contém valores não inteiros.")
                soil_values[selected_valid] = np.round(selected[selected_valid]).astype(np.int16)
                soil_meta.update({
                    "nodata_cells_on_model_domain": int(np.count_nonzero(~selected_valid)),
                    "class_counts": {
                        str(int(code)): int(count)
                        for code, count in zip(*np.unique(soil_values[selected_valid], return_counts=True))
                    },
                })

        index_grid = np.full(mb.shape, -1, dtype=np.int32)
        index_grid[rows, cols] = np.arange(rows.size, dtype=np.int32)
        neighbors = _build_raster_neighbors(index_grid, rows, cols)
        profile = mb.profile.copy()
        profile.update(count=1, dtype="uint8", nodata=0)
        grid = BrMangueGrid(
            usos=usos,
            alt2=alt2,
            classe_solos=soil_values,
            col=cols.astype(np.int64),
            lin=rows.astype(np.int64),
            neighbors=neighbors,
            source_path=str(mapbiomas_path),
            crs_wkt=mb.crs.to_wkt() if mb.crs else None,
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
            "elevation": {
                "path": str(elevation_path),
                "nodata": dem.nodata,
                "min_valid_m": float(np.nanmin(alt2)),
                "max_valid_m": float(np.nanmax(alt2)),
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
                "valid_row_min": int(rows.min()),
                "valid_row_max": int(rows.max()),
                "valid_col_min": int(cols.min()),
                "valid_col_max": int(cols.max()),
            },
            "model_class_codes": {
                "MANGUE": MANGUE,
                "VEGETACAO_TERRESTRE": VEGETACAO_TERRESTRE,
                "MAR": MAR,
                "AREA_ANTROPIZADA": AREA_ANTROPIZADA,
            },
        }
        return RasterInputSet(
            grid=grid,
            raster_shape=mb.shape,
            valid_rows=rows.astype(np.int64),
            valid_cols=cols.astype(np.int64),
            valid_mask=valid,
            profile=profile,
            metadata=metadata,
        )


def write_input_metadata(inputs: RasterInputSet, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inputs.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
