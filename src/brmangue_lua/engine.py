"""Core cellular automaton and state-transition rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
import json

import numpy as np
import pandas as pd
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import geopandas as gpd

from .model_states import (
    active_mangrove_codes,
    build_model_state_catalog,
    count_model_states,
    flooded_state_code,
    mangrove_accretion_codes,
    migrated_mangrove_code as get_migrated_mangrove_code,
    state_entry,
    state_kind,
)


SOIL_PROFILE_CODES = {
    "channel": 0,
    "mangrove_soil": 3,
    "migrated_mangrove_soil": 9,
}


def mangrove_extent_metrics(
    previous_states: np.ndarray,
    current_states: np.ndarray,
    state_catalog: dict[str, Any],
) -> dict[str, int]:
    """Measure annual change in mangrove states from the project catalog."""
    active_codes = active_mangrove_codes(state_catalog)
    previous_active = np.isin(previous_states, active_codes)
    current_active = np.isin(current_states, active_codes)
    gain = int(np.count_nonzero(~previous_active & current_active))
    loss = int(np.count_nonzero(previous_active & ~current_active))
    return {
        "mangrove_extent": int(np.count_nonzero(current_active)),
        "annual_gain": gain,
        "annual_loss": loss,
        "annual_net_change": gain - loss,
    }


@dataclass(frozen=True)
class ModelParameters:
    """Parameters controlling one model run."""

    start: int = 1
    final_time: int = 100
    area_cell: float = 0.09
    tide_height: float = 6.0
    sea_level_rise_rate: float = 0.5
    # Keep the historical soil-gated behavior available for reproducibility.
    # The default applies accretion to all states with mangrove behavior.
    legacy_lua_accretion_typo: bool = False
    # Allow land-cover classes to supply migration candidates when soil data
    # are unavailable. The default keeps soil-dependent migration disabled.
    allow_migration_without_soil: bool = False
    # Optional constant accretion rate in millimetres per time step.
    accretion_rate_mm: float | None = None
    # Complete annual steps before a migrated cell can act as a source.
    # Zero is available for sensitivity tests that reproduce immediate
    # source activation; the Studio default is three years.
    migration_maturity_years: int = 3

    def __post_init__(self) -> None:
        if int(self.migration_maturity_years) != self.migration_maturity_years:
            raise ValueError("migration_maturity_years must be an integer.")
        if self.migration_maturity_years < 0:
            raise ValueError("migration_maturity_years must be greater than or equal to zero.")


@dataclass
class BrMangueGrid:
    """Cell grid and current simulation state."""

    land_cover_state: np.ndarray
    relative_elevation: np.ndarray
    soil_class: np.ndarray
    column: np.ndarray
    row: np.ndarray
    neighbors: tuple[tuple[int, ...], ...] | np.ndarray
    source_path: str | None = None
    crs_wkt: str | None = None
    model_state_catalog: dict[str, Any] = field(default_factory=dict)
    migration_age: np.ndarray | None = None
    _migration_candidate_states: frozenset[int] = field(default=frozenset(), init=False, repr=False)
    _migration_source_states: frozenset[int] = field(default=frozenset(), init=False, repr=False)
    flooded_state_codes: dict[int, int] = field(default_factory=dict, init=False, repr=False)
    migrated_state_code: int | None = field(default=None, init=False)
    last_transition_metrics: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.migration_age is None:
            self.migration_age = np.full(self.land_cover_state.shape, -1, dtype=np.int16)
        elif self.migration_age.shape != self.land_cover_state.shape:
            raise ValueError("migration_age must have the same shape as land_cover_state.")
        else:
            self.migration_age = np.asarray(self.migration_age, dtype=np.int16)
        if not self.model_state_catalog:
            base_codes = np.unique(self.land_cover_state)
            self.model_state_catalog = build_model_state_catalog([
                {
                    "code": int(code),
                    "name": f"Class {int(code)}",
                    "behavior": "fixed",
                    "color": "#8c6bb1",
                }
                for code in base_codes
                if int(code) > 0
            ])
        self.model_state_catalog = {
            **self.model_state_catalog,
            "states": {
                str(int(code)): dict(value)
                for code, value in self.model_state_catalog.get("states", {}).items()
            },
            "flooded_codes": {
                str(int(code)): int(value)
                for code, value in self.model_state_catalog.get("flooded_codes", {}).items()
            },
        }
        self.flooded_state_codes = {
            int(code): int(value)
            for code, value in self.model_state_catalog.get("flooded_codes", {}).items()
        }
        self.migrated_state_code = get_migrated_mangrove_code(self.model_state_catalog)
        self._migration_candidate_states = frozenset(
            int(code)
            for code, definition in self.model_state_catalog.get("states", {}).items()
            if definition.get("kind") == "class"
            and definition.get("behavior") in {"natural_vegetation", "bare_soil"}
        )
        self._migration_source_states = frozenset(
            int(code)
            for code, definition in self.model_state_catalog.get("states", {}).items()
            if definition.get("kind") == "class" and definition.get("behavior") == "mangrove"
        )
        self._accretion_eligible_states = frozenset(
            mangrove_accretion_codes(self.model_state_catalog)
        )

    @classmethod
    def from_geodataframe(
        cls,
        frame: "gpd.GeoDataFrame",
        source_path: str | None = None,
        *,
        model_state_catalog: dict[str, Any] | None = None,
        strict_lua_schema: bool = False,
    ) -> "BrMangueGrid":
        columns = {
            "land_cover_state": "LandCoverState" if "LandCoverState" in frame else "Usos",
            "relative_elevation": "RelativeElevation" if "RelativeElevation" in frame else "Alt2",
            "column": "Column" if "Column" in frame else "Col",
            "row": "Row" if "Row" in frame else "Lin",
        }
        missing = [name for name in columns.values() if name not in frame]
        if missing:
            raise ValueError(f"The grid is missing required fields: {sorted(missing)}.")

        soil_name = next(
            (name for name in ("SoilClass", "ClasseSolos", "ClaseSolos") if name in frame),
            None,
        )
        if soil_name is None:
            if strict_lua_schema:
                raise ValueError("The strict grid schema requires the SoilClass field.")
            raise ValueError("The grid requires a SoilClass field.")

        column = frame[columns["column"]].to_numpy(dtype=np.int64)
        row = frame[columns["row"]].to_numpy(dtype=np.int64)
        neighbors = _build_moore_neighbors(column, row)
        soil_values = frame[soil_name].to_numpy(dtype=np.int64, copy=True)
        if strict_lua_schema and "ClasseSolos" not in frame.columns:
            soil_values.fill(-999)

        return cls(
            land_cover_state=frame[columns["land_cover_state"]].to_numpy(dtype=np.uint16, copy=True),
            relative_elevation=frame[columns["relative_elevation"]].to_numpy(dtype=np.float64, copy=True),
            soil_class=soil_values,
            column=column,
            row=row,
            neighbors=neighbors,
            source_path=source_path,
            crs_wkt=frame.crs.to_wkt() if frame.crs is not None else None,
            model_state_catalog=model_state_catalog or {},
        )

    @classmethod
    def from_shapefile(
        cls,
        path: str | Path,
        *,
        model_state_catalog: dict[str, Any] | None = None,
        strict_lua_schema: bool = False,
    ) -> "BrMangueGrid":
        import geopandas as gpd

        path = Path(path)
        frame = gpd.read_file(path)
        return cls.from_geodataframe(
            frame,
            source_path=str(path),
            model_state_catalog=model_state_catalog,
            strict_lua_schema=strict_lua_schema,
        )

    @property
    def size(self) -> int:
        return int(self.land_cover_state.size)

    def copy(self) -> "BrMangueGrid":
        return BrMangueGrid(
            land_cover_state=self.land_cover_state.copy(),
            relative_elevation=self.relative_elevation.copy(),
            soil_class=self.soil_class.copy(),
            column=self.column.copy(),
            row=self.row.copy(),
            neighbors=self.neighbors,
            source_path=self.source_path,
            crs_wkt=self.crs_wkt,
            model_state_catalog=self.model_state_catalog,
            migration_age=self.migration_age.copy(),
        )

    def class_counts(self) -> dict[str, int]:
        return count_model_states(self.land_cover_state, self.model_state_catalog)

    def _apply_flooding(self, index: int, previous_states: np.ndarray) -> None:
        """Replace a base class with its catalog-defined flooded state."""
        previous = int(previous_states[index])
        if state_kind(self.model_state_catalog, previous) != "class":
            return
        flooded_code = flooded_state_code(self.model_state_catalog, previous)
        if flooded_code is not None:
            self.land_cover_state[index] = flooded_code

    def step(
        self,
        time: int,
        parameters: ModelParameters,
        *,
        indices: Iterable[int] | None = None,
        _past_states: np.ndarray | None = None,
        _past_elevation: np.ndarray | None = None,
        _past_migration_age: np.ndarray | None = None,
    ) -> None:
        """Advance the grid by one time step."""
        full_step = indices is None and _past_states is None
        past_states = self.land_cover_state.copy() if _past_states is None else _past_states
        past_elevation = self.relative_elevation.copy() if _past_elevation is None else _past_elevation
        past_migration_age = (
            self.migration_age.copy()
            if _past_migration_age is None
            else _past_migration_age
        )
        if indices is None:
            indices = range(self.size)

        nmrm = time * parameters.sea_level_rise_rate
        # Alongi (2008)'s regression relates annual sediment-accretion rate
        # (mm/year) to annual mean sea-level-rise rate (mm/year). Use the
        # scenario rate, not its accumulated rise at this step.
        accretion_rate_mm = (
            parameters.accretion_rate_mm
            if parameters.accretion_rate_mm is not None
            else 1.693 + (0.939 * parameters.sea_level_rise_rate * 1000)
        )
        accretion_rate_m = accretion_rate_mm / 1000
        tidal_influence_zone = parameters.tide_height + nmrm

        # Keep previous-state arrays immutable while the current state updates.
        for index in indices:
            # Age advances at the beginning of the annual step. A cell that
            # becomes migrated during this step is reset to zero below and
            # therefore cannot propagate immediately in the next step when a
            # positive maturation delay is configured.
            if self.migrated_state_code is not None and int(past_states[index]) == self.migrated_state_code:
                age = min(int(past_migration_age[index]) + 1, np.iinfo(np.int16).max)
                self.migration_age[index] = age
            elif self.migrated_state_code is not None and int(self.land_cover_state[index]) == self.migrated_state_code:
                # The cell was converted earlier in this same step. Keep the
                # zero assigned by the source cell; it is not mature yet.
                age = -1
            else:
                age = -1
                self.migration_age[index] = -1

            if is_sea_or_flooded(int(past_states[index]), self.model_state_catalog) and past_elevation[index] >= 0:
                lower = [
                    neighbor
                    for neighbor in self.neighbors[index]
                    if int(neighbor) >= 0 and past_elevation[int(neighbor)] < past_elevation[index]
                ]
                neighbor_count = 1 + len(lower)
                flow = parameters.sea_level_rise_rate / neighbor_count
                self.relative_elevation[index] += flow

                for neighbor in lower:
                    self.relative_elevation[neighbor] += flow
                    if not is_sea_or_flooded(int(past_states[neighbor]), self.model_state_catalog):
                        self._apply_flooding(neighbor, past_states)

            # Migration uses the current soil, land-cover, and elevation values.
            soil_source = int(self.soil_class[index]) in (
                SOIL_PROFILE_CODES["mangrove_soil"],
                SOIL_PROFILE_CODES["channel"],
            )
            mature_migrated_soil_source = (
                self.migrated_state_code is not None
                and int(self.land_cover_state[index]) == self.migrated_state_code
                and age >= parameters.migration_maturity_years
                and int(self.soil_class[index]) == SOIL_PROFILE_CODES["migrated_mangrove_soil"]
            )
            if soil_source or mature_migrated_soil_source:
                for neighbor in self.neighbors[index]:
                    if int(neighbor) < 0:
                        continue
                    if (
                        int(self.land_cover_state[neighbor]) in self._migration_candidate_states
                        and int(self.soil_class[neighbor]) != SOIL_PROFILE_CODES["mangrove_soil"]
                        and self.relative_elevation[neighbor] <= tidal_influence_zone
                    ):
                        self.soil_class[neighbor] = SOIL_PROFILE_CODES["migrated_mangrove_soil"]

            # Original mangrove is an immediate source. A migrated cell only
            # becomes a source after the configured establishment period.
            migration_source = int(self.land_cover_state[index]) in self._migration_source_states or (
                self.migrated_state_code is not None
                and int(self.land_cover_state[index]) == self.migrated_state_code
                and age >= parameters.migration_maturity_years
            )
            if migration_source and self.migrated_state_code is not None:
                for neighbor in self.neighbors[index]:
                    if int(neighbor) < 0:
                        continue
                    soil_or_landcover_eligible = parameters.allow_migration_without_soil or (
                        int(self.soil_class[neighbor])
                        in (
                            SOIL_PROFILE_CODES["migrated_mangrove_soil"],
                            SOIL_PROFILE_CODES["mangrove_soil"],
                        )
                    )
                    if (
                        int(self.land_cover_state[neighbor]) in self._migration_candidate_states
                        and self.relative_elevation[neighbor] <= tidal_influence_zone
                        and soil_or_landcover_eligible
                    ):
                        self.land_cover_state[neighbor] = self.migrated_state_code
                        self.migration_age[neighbor] = 0

            if parameters.legacy_lua_accretion_typo:
                # Historical option retained for reproducing earlier runs.
                apply_accretion = int(self.soil_class[index]) == SOIL_PROFILE_CODES["mangrove_soil"]
            else:
                apply_accretion = int(self.land_cover_state[index]) in self._accretion_eligible_states
            if apply_accretion:
                self.relative_elevation[index] += accretion_rate_m

        # ``run_blocks`` supplies one shared previous-state snapshot and calls
        # this method once per block.  The complete transition is assembled by
        # that caller; only a full-grid step can record it here directly.
        if full_step:
            self.last_transition_metrics = mangrove_extent_metrics(
                past_states, self.land_cover_state, self.model_state_catalog
            )
        # The current arrays become the previous state at the next time step.

    def run(self, parameters: ModelParameters) -> pd.DataFrame:
        rows: list[dict[str, float | int]] = []
        for time in range(parameters.start, parameters.final_time + 1):
            self.step(time, parameters)
            row: dict[str, float | int] = {"year": time}
            row.update(self.class_counts())
            row["min_elevation"] = float(np.nanmin(self.relative_elevation))
            row["max_elevation"] = float(np.nanmax(self.relative_elevation))
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
            raise ValueError("block_size must be greater than or equal to 1.")

        rows: list[dict[str, float | int]] = []
        for time in range(parameters.start, parameters.final_time + 1):
            past_states = self.land_cover_state.copy()
            past_elevation = self.relative_elevation.copy()
            past_migration_age = self.migration_age.copy()
            for start in range(0, self.size, block_size):
                stop = min(start + block_size, self.size)
                self.step(
                    time,
                    parameters,
                    indices=range(start, stop),
                    _past_states=past_states,
                    _past_elevation=past_elevation,
                    _past_migration_age=past_migration_age,
                )
            self.last_transition_metrics = mangrove_extent_metrics(
                past_states, self.land_cover_state, self.model_state_catalog
            )
            row: dict[str, float | int] = {"year": time}
            row.update(self.class_counts())
            row["min_elevation"] = float(np.nanmin(self.relative_elevation))
            row["max_elevation"] = float(np.nanmax(self.relative_elevation))
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
            "model_state_catalog": self.model_state_catalog,
            "parameters": {
                "start": parameters.start,
                "final_time": parameters.final_time,
                "area_cell": parameters.area_cell,
                "tide_height": parameters.tide_height,
                "sea_level_rise_rate": parameters.sea_level_rise_rate,
                "legacy_lua_accretion_typo": parameters.legacy_lua_accretion_typo,
                "allow_migration_without_soil": parameters.allow_migration_without_soil,
                "accretion_rate_mm": parameters.accretion_rate_mm,
                "migration_maturity_years": parameters.migration_maturity_years,
            },
        }


def is_sea_or_flooded(
    state_code: int,
    state_catalog: dict[str, Any],
) -> bool:
    entry = state_entry(state_catalog, state_code)
    return bool(
        entry
        and (
            entry.get("kind") == "flooded"
            or entry.get("behavior") == "water"
        )
    )


def _build_moore_neighbors(column: np.ndarray, row: np.ndarray) -> tuple[tuple[int, ...], ...]:
    index_by_position = {
        (int(column_value), int(row_value)): index
        for index, (column_value, row_value) in enumerate(zip(column, row))
    }
    offsets: tuple[tuple[int, int], ...] = (
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1), (0, 1),
        (1, -1), (1, 0), (1, 1),
    )
    result: list[tuple[int, ...]] = []
    for column_value, row_value in zip(column, row):
        result.append(
            tuple(
                index_by_position[(int(column_value) + dc, int(row_value) + dr)]
                for dc, dr in offsets
                if (int(column_value) + dc, int(row_value) + dr) in index_by_position
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
        raise ValueError("engine must be 'continuous', 'blocks', or 'blocks-memory'.")
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
