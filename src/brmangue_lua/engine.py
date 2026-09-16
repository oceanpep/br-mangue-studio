"""Core cellular automaton and state-transition rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import json

import numpy as np
import pandas as pd
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import geopandas as gpd


# Land-cover state codes used by the model.
MANGUE = 1
VEGETACAO_TERRESTRE = 2
MAR = 3
AREA_ANTROPIZADA = 4
SOLO_DESCOBERTO = 5
SOLO_DESCOBERTO_INUNDADO = 6
AREA_ANTROPIZADA_INUNDADO = 7
MANGUE_MIGRADO = 8
MANGUE_INUNDADO = 9
VEGETACAO_TERRESTRE_INUNDADO = 10

# Soil-state codes used by the model.
CANAL_FLUVIAL = 0
SOLO_MANGUE = 3
SOLO_MANGUE_MIGRADO = 9

_FLOODED = frozenset(
    {
        MAR,
        SOLO_DESCOBERTO_INUNDADO,
        AREA_ANTROPIZADA_INUNDADO,
        MANGUE_INUNDADO,
        VEGETACAO_TERRESTRE_INUNDADO,
    }
)


@dataclass(frozen=True)
class ModelParameters:
    """Parameters controlling one model run."""

    start: int = 1
    final_time: int = 100
    area_cell: float = 0.09
    tide_height: float = 6.0
    sea_level_rise_rate: float = 0.5
    # Preserve the historical accretion switch for reproducibility.
    legacy_lua_accretion_typo: bool = True
    # Allow land-cover classes to supply migration candidates when soil data
    # are unavailable. The default keeps soil-dependent migration disabled.
    allow_migration_without_soil: bool = False
    # Optional constant accretion rate in millimetres per time step.
    accretion_rate_mm: float | None = None


@dataclass
class BrMangueGrid:
    """Cell grid and current simulation state."""

    usos: np.ndarray
    alt2: np.ndarray
    classe_solos: np.ndarray
    col: np.ndarray
    lin: np.ndarray
    neighbors: tuple[tuple[int, ...], ...] | np.ndarray
    source_path: str | None = None
    crs_wkt: str | None = None

    @classmethod
    def from_geodataframe(
        cls,
        frame: "gpd.GeoDataFrame",
        source_path: str | None = None,
        *,
        strict_lua_schema: bool = False,
    ) -> "BrMangueGrid":
        required = {"Usos", "Alt2", "Col", "Lin"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"A grade não possui os campos obrigatórios: {sorted(missing)}")

        soil_name = "ClasseSolos" if "ClasseSolos" in frame.columns else "ClaseSolos"
        if soil_name not in frame.columns:
            if strict_lua_schema:
                raise ValueError("A grade não possui o campo ClasseSolos exigido pelo modo estrito.")
            raise ValueError("A grade precisa de uma coluna ClasseSolos ou ClaseSolos.")

        col = frame["Col"].to_numpy(dtype=np.int64)
        lin = frame["Lin"].to_numpy(dtype=np.int64)
        neighbors = _build_moore_neighbors(col, lin)
        # Accept the common spelling ``ClaseSolos`` while retaining a strict
        # mode for datasets that require the canonical field name.
        soil_values = frame[soil_name].to_numpy(dtype=np.int64, copy=True)
        if strict_lua_schema and "ClasseSolos" not in frame.columns:
            soil_values.fill(-999)

        return cls(
            usos=frame["Usos"].to_numpy(dtype=np.int64, copy=True),
            alt2=frame["Alt2"].to_numpy(dtype=np.float64, copy=True),
            classe_solos=soil_values,
            col=col,
            lin=lin,
            neighbors=neighbors,
            source_path=source_path,
            crs_wkt=frame.crs.to_wkt() if frame.crs is not None else None,
        )

    @classmethod
    def from_shapefile(
        cls,
        path: str | Path,
        *,
        strict_lua_schema: bool = False,
    ) -> "BrMangueGrid":
        import geopandas as gpd

        path = Path(path)
        frame = gpd.read_file(path)
        return cls.from_geodataframe(
            frame,
            source_path=str(path),
            strict_lua_schema=strict_lua_schema,
        )

    @property
    def size(self) -> int:
        return int(self.usos.size)

    def copy(self) -> "BrMangueGrid":
        return BrMangueGrid(
            usos=self.usos.copy(),
            alt2=self.alt2.copy(),
            classe_solos=self.classe_solos.copy(),
            col=self.col.copy(),
            lin=self.lin.copy(),
            neighbors=self.neighbors,
            source_path=self.source_path,
            crs_wkt=self.crs_wkt,
        )

    def class_counts(self) -> dict[str, int]:
        counts = {"mangrove": int(np.count_nonzero(self.usos == MANGUE))}
        counts.update(
            {
                "vegetation": int(np.count_nonzero(self.usos == VEGETACAO_TERRESTRE)),
                "sea": int(np.count_nonzero(self.usos == MAR)),
                "anthropized": int(np.count_nonzero(self.usos == AREA_ANTROPIZADA)),
                "bare": int(np.count_nonzero(self.usos == SOLO_DESCOBERTO)),
                "migrated_mangrove": int(np.count_nonzero(self.usos == MANGUE_MIGRADO)),
                "flooded_mangrove": int(np.count_nonzero(self.usos == MANGUE_INUNDADO)),
            }
        )
        return counts

    def _apply_flooding(self, index: int, past_usos: np.ndarray) -> None:
        """Apply a flooding transition using the previous land-cover state."""
        previous = int(past_usos[index])
        self.usos[index] = {
            MANGUE: MANGUE_INUNDADO,
            VEGETACAO_TERRESTRE: VEGETACAO_TERRESTRE_INUNDADO,
            AREA_ANTROPIZADA: AREA_ANTROPIZADA_INUNDADO,
            SOLO_DESCOBERTO: SOLO_DESCOBERTO_INUNDADO,
        }.get(previous, int(self.usos[index]))

    def step(
        self,
        time: int,
        parameters: ModelParameters,
        *,
        indices: Iterable[int] | None = None,
        _past_usos: np.ndarray | None = None,
        _past_alt2: np.ndarray | None = None,
    ) -> None:
        """Advance the grid by one time step."""
        past_usos = self.usos.copy() if _past_usos is None else _past_usos
        past_alt2 = self.alt2.copy() if _past_alt2 is None else _past_alt2
        if indices is None:
            indices = range(self.size)

        nmrm = time * parameters.sea_level_rise_rate
        nmrm_m = nmrm * 1000
        accretion_rate_mm = (
            parameters.accretion_rate_mm
            if parameters.accretion_rate_mm is not None
            else 1.693 + (0.939 * nmrm_m)
        )
        accretion_rate_m = accretion_rate_mm / 1000
        tidal_influence_zone = parameters.tide_height + nmrm

        # Keep previous-state arrays immutable while the current state updates.
        for index in indices:
            if is_sea_or_flooded(int(past_usos[index])) and past_alt2[index] >= 0:
                lower = [
                    neighbor
                    for neighbor in self.neighbors[index]
                    if int(neighbor) >= 0 and past_alt2[int(neighbor)] < past_alt2[index]
                ]
                neighbor_count = 1 + len(lower)
                flow = parameters.sea_level_rise_rate / neighbor_count
                self.alt2[index] += flow

                for neighbor in lower:
                    self.alt2[neighbor] += flow
                    if not is_sea_or_flooded(int(past_usos[neighbor])):
                        self._apply_flooding(neighbor, past_usos)

            # Migration uses the current soil, land-cover, and elevation values.
            if int(self.classe_solos[index]) in (SOLO_MANGUE, CANAL_FLUVIAL):
                for neighbor in self.neighbors[index]:
                    if int(neighbor) < 0:
                        continue
                    if (
                        int(self.usos[neighbor]) in (VEGETACAO_TERRESTRE, SOLO_DESCOBERTO)
                        and int(self.classe_solos[neighbor]) != SOLO_MANGUE
                        and self.alt2[neighbor] <= tidal_influence_zone
                    ):
                        self.classe_solos[neighbor] = SOLO_MANGUE_MIGRADO

            if int(self.usos[index]) == MANGUE:
                for neighbor in self.neighbors[index]:
                    if int(neighbor) < 0:
                        continue
                    soil_or_landcover_eligible = parameters.allow_migration_without_soil or (
                        int(self.classe_solos[neighbor])
                        in (SOLO_MANGUE_MIGRADO, SOLO_MANGUE)
                    )
                    if (
                        int(self.usos[neighbor]) in (VEGETACAO_TERRESTRE, SOLO_DESCOBERTO)
                        and self.alt2[neighbor] <= tidal_influence_zone
                        and soil_or_landcover_eligible
                    ):
                        self.usos[neighbor] = MANGUE_MIGRADO

            if parameters.legacy_lua_accretion_typo:
                migrated_soil = False
            else:
                migrated_soil = int(self.classe_solos[index]) == SOLO_MANGUE_MIGRADO

            if (int(self.classe_solos[index]) == SOLO_MANGUE) or (
                migrated_soil and not is_sea_or_flooded(int(self.usos[index]))
            ):
                self.alt2[index] += accretion_rate_m

        # The current arrays become the previous state at the next time step.

    def run(self, parameters: ModelParameters) -> pd.DataFrame:
        rows: list[dict[str, float | int]] = []
        for time in range(parameters.start, parameters.final_time + 1):
            self.step(time, parameters)
            row: dict[str, float | int] = {"year": time}
            row.update(self.class_counts())
            row["min_alt2"] = float(np.nanmin(self.alt2))
            row["max_alt2"] = float(np.nanmax(self.alt2))
            rows.append(row)
        return pd.DataFrame(rows)

    def run_blocks(
        self,
        parameters: ModelParameters,
        *,
        block_size: int = 10_000,
    ) -> pd.DataFrame:
        """Run the same rules in blocks without changing cell order.

        One previous-state snapshot is shared by all blocks in a time step.
        The full state remains in memory in this implementation; block
        partitioning provides the execution path used by large-grid runners.
        """
        if block_size < 1:
            raise ValueError("block_size deve ser maior ou igual a 1.")

        rows: list[dict[str, float | int]] = []
        for time in range(parameters.start, parameters.final_time + 1):
            past_usos = self.usos.copy()
            past_alt2 = self.alt2.copy()
            for start in range(0, self.size, block_size):
                stop = min(start + block_size, self.size)
                self.step(
                    time,
                    parameters,
                    indices=range(start, stop),
                    _past_usos=past_usos,
                    _past_alt2=past_alt2,
                )
            row: dict[str, float | int] = {"year": time}
            row.update(self.class_counts())
            row["min_alt2"] = float(np.nanmin(self.alt2))
            row["max_alt2"] = float(np.nanmax(self.alt2))
            rows.append(row)
        return pd.DataFrame(rows)

    def metadata(
        self,
        parameters: ModelParameters,
        *,
        engine: str = "continuous",
        block_size: int | None = None,
    ) -> dict[str, object]:
        return {
            "engine": "python_cellular_rules",
            "processing_mode": engine,
            "block_size": block_size,
            "source_path": self.source_path,
            "cells": self.size,
            "parameters": {
                "start": parameters.start,
                "final_time": parameters.final_time,
                "area_cell": parameters.area_cell,
                "tide_height": parameters.tide_height,
                "sea_level_rise_rate": parameters.sea_level_rise_rate,
                "legacy_lua_accretion_typo": parameters.legacy_lua_accretion_typo,
                "allow_migration_without_soil": parameters.allow_migration_without_soil,
                "accretion_rate_mm": parameters.accretion_rate_mm,
            },
            "classes": {
                "MANGUE": MANGUE,
                "VEGETACAO_TERRESTRE": VEGETACAO_TERRESTRE,
                "MAR": MAR,
                "AREA_ANTROPIZADA": AREA_ANTROPIZADA,
                "SOLO_DESCOBERTO": SOLO_DESCOBERTO,
                "SOLO_DESCOBERTO_INUNDADO": SOLO_DESCOBERTO_INUNDADO,
                "AREA_ANTROPIZADA_INUNDADO": AREA_ANTROPIZADA_INUNDADO,
                "MANGUE_MIGRADO": MANGUE_MIGRADO,
                "MANGUE_INUNDADO": MANGUE_INUNDADO,
                "VEGETACAO_TERRESTRE_INUNDADO": VEGETACAO_TERRESTRE_INUNDADO,
            },
        }


def is_sea_or_flooded(uso: int) -> bool:
    return uso in _FLOODED


def _build_moore_neighbors(col: np.ndarray, lin: np.ndarray) -> tuple[tuple[int, ...], ...]:
    index_by_position = {(int(c), int(r)): i for i, (c, r) in enumerate(zip(col, lin))}
    offsets: tuple[tuple[int, int], ...] = (
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1), (0, 1),
        (1, -1), (1, 0), (1, 1),
    )
    result: list[tuple[int, ...]] = []
    for c, r in zip(col, lin):
        result.append(
            tuple(
                index_by_position[(int(c) + dc, int(r) + dr)]
                for dc, dr in offsets
                if (int(c) + dc, int(r) + dr) in index_by_position
            )
        )
    return tuple(result)


def run_shapefile(
    input_path: str | Path,
    output_dir: str | Path,
    parameters: ModelParameters | None = None,
    *,
    strict_lua_schema: bool = False,
    engine: str = "continuous",
    block_size: int = 10_000,
    dm_runner: str = "continuous",
    show_dissmodel_chart: bool = False,
) -> pd.DataFrame:
    parameters = parameters or ModelParameters()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if engine == "dissmodel":
        from .dissmodel_adapter import run_dissmodel_shapefile

        return run_dissmodel_shapefile(
            input_path,
            output_dir,
            parameters,
            runner_mode=dm_runner,
            block_size=block_size,
            strict_lua_schema=strict_lua_schema,
            show_chart=show_dissmodel_chart,
        )
    if engine == "blocks":
        from .persistent_blocks import run_persistent_shapefile

        return run_persistent_shapefile(
            input_path,
            output_dir,
            parameters,
            block_size=block_size,
            strict_lua_schema=strict_lua_schema,
        )
    grid = BrMangueGrid.from_shapefile(
        input_path,
        strict_lua_schema=strict_lua_schema,
    )
    if engine == "continuous":
        trajectory = grid.run(parameters)
    elif engine == "blocks-memory":
        trajectory = grid.run_blocks(parameters, block_size=block_size)
    else:
        raise ValueError("engine deve ser 'continuous', 'blocks' ou 'blocks-memory'.")
    trajectory.to_csv(output_dir / "trajectory.csv", index=False)
    (output_dir / "metadata.json").write_text(
        json.dumps(
            grid.metadata(parameters, engine=engine, block_size=block_size if engine == "blocks" else None),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return trajectory
