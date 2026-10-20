"""Disk-backed block execution for large cellular grids."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import gc
import json
import time
from typing import Any

import numpy as np
import pandas as pd

try:
    import psutil
except ImportError:  # pragma: no cover - optional diagnostics
    psutil = None

from .engine import ModelParameters, SOIL_PROFILE_CODES, is_sea_or_flooded, mangrove_extent_metrics
from .model_states import (
    count_model_states,
    flooded_state_code,
    migrated_mangrove_code,
    mangrove_accretion_codes,
    state_kind,
)


STATE_DTYPES: dict[str, np.dtype[Any]] = {
    "land_cover_state": np.dtype("uint16"),
    "relative_elevation": np.dtype("float64"),
    "soil_class": np.dtype("int16"),
    "migration_age": np.dtype("int16"),
}


def _memmap(path: Path, dtype: np.dtype[Any], shape: tuple[int, ...], mode: str) -> np.memmap:
    return np.memmap(path, dtype=dtype, mode=mode, shape=shape)


@dataclass
class PersistentBlockRunner:
    """Run annual transitions over disk-backed arrays in cell order."""

    root: Path
    n_cells: int
    block_size: int
    neighbors: np.memmap
    state_a: dict[str, np.memmap]
    state_b: dict[str, np.memmap]
    model_state_catalog: dict[str, Any] = field(default_factory=dict)
    migration_candidate_states: frozenset[int] = field(default_factory=frozenset, repr=False)
    migration_source_states: frozenset[int] = field(default_factory=frozenset, repr=False)
    current_slot: str = "a"
    years_completed: int = 0
    last_transition_metrics: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def create_from_shapefile(
        cls,
        input_path: str | Path,
        root: str | Path,
        *,
        block_size: int = 10_000,
        strict_lua_schema: bool = False,
    ) -> "PersistentBlockRunner":
        import geopandas as gpd
        from .engine import BrMangueGrid

        frame = gpd.read_file(input_path)
        grid = BrMangueGrid.from_geodataframe(
            frame,
            source_path=str(Path(input_path).resolve()),
            strict_lua_schema=strict_lua_schema,
        )
        return cls.create_from_grid(
            grid,
            root,
            block_size=block_size,
            source_path=str(Path(input_path).resolve()),
            strict_lua_schema=strict_lua_schema,
        )

    @classmethod
    def create_from_grid(
        cls,
        grid: "BrMangueGrid",
        root: str | Path,
        *,
        block_size: int = 10_000,
        source_path: str | None = None,
        strict_lua_schema: bool = False,
    ) -> "PersistentBlockRunner":
        """Create persistent state files from an in-memory grid."""
        root = Path(root).resolve()
        if root.exists() and any(root.iterdir()):
            raise FileExistsError(f"Workspace folder is not empty: {root}")
        root.mkdir(parents=True, exist_ok=True)
        if block_size < 1:
            raise ValueError("block_size must be greater than or equal to 1.")

        cell_count = grid.size
        slots: dict[str, dict[str, np.memmap]] = {}
        source_arrays = {
            "land_cover_state": grid.land_cover_state,
            "relative_elevation": grid.relative_elevation,
            "soil_class": grid.soil_class,
            "migration_age": grid.migration_age,
        }
        for slot in ("a", "b"):
            slot_dir = root / f"state_{slot}"
            slot_dir.mkdir()
            slots[slot] = {}
            for name, dtype in STATE_DTYPES.items():
                target = _memmap(slot_dir / f"{name}.dat", dtype, (cell_count,), "w+")
                target[:] = source_arrays[name]
                target.flush()
                slots[slot][name] = target

        neighbors = _memmap(root / "neighbors.dat", np.dtype("int32"), (cell_count, 8), "w+")
        neighbors[:] = -1
        for index, values in enumerate(grid.neighbors):
            values_array = np.asarray(values, dtype=np.int32)
            if values_array.size:
                neighbors[index, : min(values_array.size, 8)] = values_array[:8]
        neighbors.flush()

        catalog = json.loads(json.dumps(grid.model_state_catalog))
        metadata = {
            "engine": "python_persistent_blocks",
            "input": source_path or grid.source_path,
            "cells": cell_count,
            "block_size": int(block_size),
            "neighbor_count": 8,
            "strict_lua_schema": bool(strict_lua_schema),
            "state_dtypes": {name: str(dtype) for name, dtype in STATE_DTYPES.items()},
            "model_state_catalog": catalog,
        }
        (root / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        migration_candidates = grid._migration_candidate_states
        migration_sources = grid._migration_source_states
        del grid
        gc.collect()
        return cls(
            root=root,
            n_cells=cell_count,
            block_size=int(block_size),
            neighbors=neighbors,
            state_a=slots["a"],
            state_b=slots["b"],
            model_state_catalog=catalog,
            migration_candidate_states=migration_candidates,
            migration_source_states=migration_sources,
        )

    @property
    def current(self) -> dict[str, np.memmap]:
        return self.state_a if self.current_slot == "a" else self.state_b

    @property
    def inactive(self) -> dict[str, np.memmap]:
        return self.state_b if self.current_slot == "a" else self.state_a

    def summary(self) -> dict[str, int | float]:
        current = self.current
        result: dict[str, int | float] = count_model_states(
            current["land_cover_state"], self.model_state_catalog
        )
        elevation = current["relative_elevation"]
        result["min_elevation"] = float(np.nanmin(elevation))
        result["max_elevation"] = float(np.nanmax(elevation))
        return result

    def _apply_flooding(self, current_states: np.memmap, previous_states: np.memmap, index: int) -> None:
        previous_code = int(previous_states[index])
        if state_kind(self.model_state_catalog, previous_code) != "class":
            return
        target_code = flooded_state_code(self.model_state_catalog, previous_code)
        if target_code is not None:
            current_states[index] = target_code

    def step(self, time_index: int, parameters: ModelParameters) -> dict[str, int | float]:
        """Apply one transition while preserving the shared previous-state snapshot."""
        previous = self.current
        current = self.inactive
        for name in STATE_DTYPES:
            np.copyto(current[name], previous[name])

        previous_states = previous["land_cover_state"]
        previous_elevation = previous["relative_elevation"]
        previous_migration_age = previous["migration_age"]
        states = current["land_cover_state"]
        elevation = current["relative_elevation"]
        soil = current["soil_class"]
        migration_age = current["migration_age"]
        migrated_code = migrated_mangrove_code(self.model_state_catalog)
        accretion_eligible_states = frozenset(mangrove_accretion_codes(self.model_state_catalog))

        sea_level, annual_sea_level_increment = parameters.sea_level_at(time_index)
        accretion_mm = (
            parameters.accretion_rate_mm
            if parameters.accretion_rate_mm is not None
            else 1.693 + (0.939 * annual_sea_level_increment * 1000)
        )
        accretion_m = accretion_mm / 1000
        tidal_zone = parameters.tide_height + sea_level

        for block_start in range(0, self.n_cells, self.block_size):
            block_stop = min(block_start + self.block_size, self.n_cells)
            for index in range(block_start, block_stop):
                if migrated_code is not None and int(previous_states[index]) == migrated_code:
                    age = min(int(previous_migration_age[index]) + 1, np.iinfo(np.int16).max)
                    migration_age[index] = age
                elif migrated_code is not None and int(states[index]) == migrated_code:
                    age = -1
                else:
                    age = -1
                    migration_age[index] = -1

                if is_sea_or_flooded(int(previous_states[index]), self.model_state_catalog) and previous_elevation[index] >= 0:
                    lower_neighbors = [
                        int(neighbor)
                        for neighbor in self.neighbors[index]
                        if neighbor >= 0 and previous_elevation[neighbor] < previous_elevation[index]
                    ]
                    flow = annual_sea_level_increment / (1 + len(lower_neighbors))
                    elevation[index] += flow
                    for neighbor in lower_neighbors:
                        elevation[neighbor] += flow
                        if not is_sea_or_flooded(int(previous_states[neighbor]), self.model_state_catalog):
                            self._apply_flooding(states, previous_states, neighbor)

                soil_source = int(soil[index]) in (
                    SOIL_PROFILE_CODES["mangrove_soil"],
                    SOIL_PROFILE_CODES["channel"],
                )
                established_soil_source = (
                    migrated_code is not None
                    and int(states[index]) == migrated_code
                    and age >= parameters.migration_maturity_years
                    and int(soil[index]) == SOIL_PROFILE_CODES["migrated_mangrove_soil"]
                )
                if soil_source or established_soil_source:
                    for neighbor in self.neighbors[index]:
                        if neighbor < 0:
                            continue
                        if (
                            int(states[neighbor]) in self.migration_candidate_states
                            and int(soil[neighbor]) != SOIL_PROFILE_CODES["mangrove_soil"]
                            and elevation[neighbor] <= tidal_zone
                        ):
                            soil[neighbor] = SOIL_PROFILE_CODES["migrated_mangrove_soil"]

                is_source = int(states[index]) in self.migration_source_states or (
                    migrated_code is not None
                    and int(states[index]) == migrated_code
                    and age >= parameters.migration_maturity_years
                )
                if is_source and migrated_code is not None:
                    for neighbor in self.neighbors[index]:
                        if neighbor < 0:
                            continue
                        soil_eligible = parameters.allow_migration_without_soil or int(soil[neighbor]) in (
                            SOIL_PROFILE_CODES["migrated_mangrove_soil"],
                            SOIL_PROFILE_CODES["mangrove_soil"],
                        )
                        if (
                            int(states[neighbor]) in self.migration_candidate_states
                            and elevation[neighbor] <= tidal_zone
                            and soil_eligible
                        ):
                            states[neighbor] = migrated_code
                            migration_age[neighbor] = 0

                if parameters.legacy_lua_accretion_typo:
                    apply_accretion = int(soil[index]) == SOIL_PROFILE_CODES["mangrove_soil"]
                else:
                    apply_accretion = int(states[index]) in accretion_eligible_states
                if apply_accretion:
                    elevation[index] += accretion_m

        for array in current.values():
            array.flush()
        self.last_transition_metrics = mangrove_extent_metrics(
            previous_states, states, self.model_state_catalog
        )
        self.current_slot = "b" if self.current_slot == "a" else "a"
        self.years_completed += 1
        return self.summary()

    def run(self, parameters: ModelParameters) -> pd.DataFrame:
        started = time.perf_counter()
        process = psutil.Process() if psutil is not None else None
        self.rss_before_bytes = process.memory_info().rss if process else None
        self.peak_rss_bytes = self.rss_before_bytes or 0
        rows: list[dict[str, int | float]] = []
        for time_index in range(parameters.start, parameters.final_time + 1):
            row = {"year": time_index, **parameters.sea_level_record(time_index), **self.step(time_index, parameters)}
            rows.append(row)
            if process is not None:
                self.peak_rss_bytes = max(self.peak_rss_bytes, process.memory_info().rss)
        self.elapsed_seconds = time.perf_counter() - started
        return pd.DataFrame(rows)

    def close(self) -> None:
        self.neighbors.flush()
        for state in (self.state_a, self.state_b):
            for array in state.values():
                array.flush()


def run_persistent_shapefile(
    input_path: str | Path,
    output_dir: str | Path,
    parameters: ModelParameters,
    *,
    block_size: int = 10_000,
    strict_lua_schema: bool = False,
) -> pd.DataFrame:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = PersistentBlockRunner.create_from_shapefile(
        input_path,
        output_dir / "workspace",
        block_size=block_size,
        strict_lua_schema=strict_lua_schema,
    )
    try:
        trajectory = runner.run(parameters)
        trajectory.to_csv(output_dir / "trajectory.csv", index=False)
        metadata = {
            "engine": "python_persistent_blocks",
            "input": str(Path(input_path).resolve()),
            "cells": runner.n_cells,
            "block_size": block_size,
            "model_state_catalog": runner.model_state_catalog,
            "parameters": {
                "start": parameters.start,
                "final_time": parameters.final_time,
                "area_cell": parameters.area_cell,
                "tide_height": parameters.tide_height,
                "sea_level_rise_rate": parameters.sea_level_rise_rate if parameters.sea_level_trajectory is None else None,
                "sea_level_forcing": parameters.sea_level_metadata(),
                "legacy_lua_accretion_typo": parameters.legacy_lua_accretion_typo,
                "allow_migration_without_soil": parameters.allow_migration_without_soil,
                "accretion_rate_mm": parameters.accretion_rate_mm,
                "migration_maturity_years": parameters.migration_maturity_years,
            },
        }
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return trajectory
    finally:
        runner.close()
