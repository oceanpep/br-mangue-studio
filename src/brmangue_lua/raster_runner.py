"""Raster execution for the cellular model.

The runner uses a compact list of valid pixels and can optionally persist two
state arrays on disk for large domains.
"""

from __future__ import annotations

from pathlib import Path
import json
import shutil
import time
from typing import Any, Callable

import numpy as np
import pandas as pd

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

from .engine import BrMangueGrid, ModelParameters
from .persistent_blocks import PersistentBlockRunner
from .raster_inputs import RasterInputSet, load_raster_inputs, write_input_metadata


def _summary_grid(grid: BrMangueGrid) -> dict[str, int | float]:
    result: dict[str, int | float] = grid.class_counts()
    result["min_alt2"] = float(np.nanmin(grid.alt2))
    result["max_alt2"] = float(np.nanmax(grid.alt2))
    return result


def _state_arrays(runner: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if isinstance(runner, PersistentBlockRunner):
        current = runner.current
        return current["usos"], current["alt2"], current["classe_solos"]
    return runner.usos, runner.alt2, runner.classe_solos


def _parameters_metadata(parameters: ModelParameters) -> dict[str, Any]:
    return {
        "start": int(parameters.start),
        "final_time": int(parameters.final_time),
        "area_cell": float(parameters.area_cell),
        "tide_height": float(parameters.tide_height),
        "sea_level_rise_rate": float(parameters.sea_level_rise_rate),
        "legacy_lua_accretion_typo": bool(parameters.legacy_lua_accretion_typo),
        "allow_migration_without_soil": bool(parameters.allow_migration_without_soil),
        "accretion_rate_mm": parameters.accretion_rate_mm,
    }


def _write_state(inputs: RasterInputSet, runner: Any, path: Path, year: int) -> None:
    usos, _, _ = _state_arrays(runner)
    inputs.write_state_raster(np.asarray(usos), path, year=year)


def run_raster_simulation(
    inputs: RasterInputSet,
    output_dir: str | Path,
    parameters: ModelParameters,
    *,
    initial_year: int = 2025,
    engine: str = "blocks",
    block_size: int = 10_000,
    dissmodel_runner: str = "blocks",
    show_dissmodel_chart: bool = False,
    save_annual_states: bool = True,
    step_callback: Callable[[dict[str, Any]], None] | None = None,
) -> pd.DataFrame:
    """Run a raster simulation and save trajectory, states, and metadata.

    The input state represents ``initial_year``. The first update is therefore
    written to the following calendar year.
    """
    if parameters.final_time < parameters.start:
        raise ValueError("final_time deve ser maior ou igual a start.")
    if engine not in {"continuous", "blocks", "dissmodel"}:
        raise ValueError("engine deve ser continuous, blocks ou dissmodel.")
    if dissmodel_runner not in {"continuous", "blocks"}:
        raise ValueError("dissmodel_runner deve ser continuous ou blocks.")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    states_dir = output_dir / "states"
    if save_annual_states:
        states_dir.mkdir(parents=True, exist_ok=True)
    write_input_metadata(inputs, output_dir / "input_metadata.json")
    inputs.write_state_raster(inputs.grid.usos, output_dir / f"initial_usos_{initial_year}.tif", year=initial_year)
    initial_class_counts = dict(inputs.grid.class_counts())

    started = time.perf_counter()
    process = psutil.Process() if psutil is not None else None
    rss_before = process.memory_info().rss if process else None
    peak_rss = rss_before or 0

    runner: Any
    workspace: Path | None = None
    if engine == "continuous":
        runner = inputs.grid
    elif engine == "blocks":
        workspace = output_dir / "workspace"
        runner = PersistentBlockRunner.create_from_grid(
            inputs.grid,
            workspace,
            block_size=block_size,
            source_path=str(Path(inputs.metadata["land_cover"]["path"]).resolve()),
        )
    else:
        if dissmodel_runner == "continuous":
            runner = inputs.grid
        else:
            workspace = output_dir / "workspace"
            runner = PersistentBlockRunner.create_from_grid(
                inputs.grid,
                workspace,
                block_size=block_size,
                source_path=str(Path(inputs.metadata["land_cover"]["path"]).resolve()),
            )

    rows: list[dict[str, Any]] = []
    # Compare the first annual loss with the initial state rather than with a
    # state that has already been updated in the current run.
    previous_mangrove: int | None = int(inputs.grid.class_counts()["mangrove"])
    try:
        if engine == "dissmodel":
            from .dissmodel_adapter import run_dissmodel

            def _handle_dissmodel_step(record: dict[str, Any]) -> None:
                """Forward each DissModel event to annual outputs and GUI."""
                year_index = int(record["year"])
                calendar_year = int(initial_year + year_index)
                summary = dict(record)
                row: dict[str, Any] = {
                    "year": year_index,
                    "calendar_year": calendar_year,
                    **summary,
                    "annual_gain": int(record.get("gain", 0)),
                    "annual_loss": int(record.get("loss", 0)),
                }
                rows.append(row)
                if save_annual_states:
                    _write_state(inputs, runner, states_dir / f"usos_{calendar_year}.tif", calendar_year)
                if step_callback is not None:
                    usos, _, _ = _state_arrays(runner)
                    step_callback(
                        {
                            "calendar_year": calendar_year,
                            "summary": dict(row),
                            "usos": np.asarray(usos, dtype=np.int16).copy(),
                            "processed_cells": int(len(rows) * inputs.n_cells),
                        }
                    )

            trajectory = run_dissmodel(
                runner,
                parameters,
                show_chart=show_dissmodel_chart,
                step_callback=_handle_dissmodel_step,
            )
            trajectory["calendar_year"] = trajectory["year"].astype(int) + int(initial_year)
            if "mangrove" in trajectory.columns and not trajectory.empty:
                previous = int(inputs.grid.class_counts()["mangrove"])
                gains: list[int] = []
                losses: list[int] = []
                for value in trajectory["mangrove"].astype(int):
                    gains.append(max(int(value) - previous, 0))
                    losses.append(max(previous - int(value), 0))
                    previous = int(value)
                trajectory["gain"] = gains
                trajectory["loss"] = losses
            trajectory.to_csv(output_dir / "trajectory.csv", index=False)
            _write_state(inputs, runner, output_dir / f"final_usos_{initial_year + parameters.final_time}.tif", initial_year + parameters.final_time)
            rows = trajectory.to_dict(orient="records")
        else:
            for time_index in range(parameters.start, parameters.final_time + 1):
                if engine == "continuous":
                    runner.step(time_index, parameters)
                    summary = _summary_grid(runner)
                else:
                    summary = runner.step(time_index, parameters)
                mangrove = int(summary["mangrove"])
                previous = mangrove if previous_mangrove is None else previous_mangrove
                calendar_year = int(initial_year + time_index)
                row: dict[str, Any] = {
                    "year": int(time_index),
                    "calendar_year": calendar_year,
                    **summary,
                    "annual_gain": max(mangrove - previous, 0),
                    "annual_loss": max(previous - mangrove, 0),
                }
                rows.append(row)
                previous_mangrove = mangrove
                if process is not None:
                    peak_rss = max(peak_rss, process.memory_info().rss)
                if save_annual_states:
                    _write_state(inputs, runner, states_dir / f"usos_{calendar_year}.tif", calendar_year)
                if step_callback is not None:
                    usos, _, _ = _state_arrays(runner)
                    step_callback(
                        {
                            "calendar_year": calendar_year,
                            "summary": dict(row),
                            "usos": np.asarray(usos, dtype=np.int16).copy(),
                            "processed_cells": int(len(rows) * inputs.n_cells),
                        }
                    )
            trajectory = pd.DataFrame(rows)
            trajectory.to_csv(output_dir / "trajectory.csv", index=False)
    finally:
        if hasattr(runner, "close"):
            runner.close()

    final_year = int(initial_year + parameters.final_time)
    final_path = output_dir / f"final_usos_{final_year}.tif"
    if save_annual_states and (states_dir / f"usos_{final_year}.tif").exists():
        shutil.copy2(states_dir / f"usos_{final_year}.tif", final_path)
    elif not final_path.exists():
        _write_state(inputs, runner, final_path, final_year)

    if process is not None:
        peak_rss = max(peak_rss, process.memory_info().rss)
    final_class_counts = {
        key: int(rows[-1].get(key, 0))
        for key in initial_class_counts
    } if rows else dict(initial_class_counts)
    metadata = {
        "model": "BRMANGUE raster runner",
        "status": "computational_demonstration_without_predictive_validity",
        "initial_calendar_year": int(initial_year),
        "final_calendar_year": final_year,
        "engine": engine,
        "dissmodel_runner": dissmodel_runner if engine == "dissmodel" else None,
        "block_size": int(block_size) if engine in {"blocks", "dissmodel"} and (engine == "blocks" or dissmodel_runner == "blocks") else None,
        "save_annual_states": bool(save_annual_states),
        "parameters": _parameters_metadata(parameters),
        "cells": inputs.n_cells,
        "initial_class_counts": initial_class_counts,
        "final_class_counts": final_class_counts,
        "elapsed_seconds": time.perf_counter() - started,
        "rss_before_bytes": rss_before,
        "peak_rss_bytes": peak_rss,
        "soil_enabled": bool(inputs.metadata["soil"]["enabled"]),
        "migration_without_soil": bool(parameters.allow_migration_without_soil),
        "soil_behavior_when_disabled": (
            "land-cover fallback enables migration to vegetation or bare soil; "
            "soil-dependent accretion remains inactive; flooding remains active"
            if parameters.allow_migration_without_soil
            else "soil-dependent migration and accretion rules are inactive; flooding remains active"
        ),
        "input_metadata": "input_metadata.json",
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return trajectory


def load_and_run_raster_simulation(
    mapbiomas_path: str | Path | None = None,
    elevation_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    parameters: ModelParameters | None = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """Load aligned rasters and run a simulation with one call.

    ``mapbiomas_path`` and ``elevation_path`` remain accepted as positional
    aliases. New projects can use ``land_cover_path`` and ``terrain_path``.
    """
    land_cover_path = kwargs.pop("land_cover_path", None)
    terrain_path = kwargs.pop("terrain_path", None)
    if land_cover_path is not None:
        mapbiomas_path = land_cover_path
    if terrain_path is not None:
        elevation_path = terrain_path
    if mapbiomas_path is None or elevation_path is None or output_dir is None or parameters is None:
        raise ValueError("Informe os rasters de uso/cobertura, elevação, output_dir e parameters.")
    load_kwargs = {
        key: kwargs.pop(key)
        for key in (
            "mask_path", "soil_path", "soil_enabled", "mapbiomas_band", "mapbiomas_year",
            "land_cover_path", "terrain_path", "land_cover_band", "land_cover_year", "mapping",
        )
        if key in kwargs
    }
    inputs = load_raster_inputs(mapbiomas_path, elevation_path, **load_kwargs)
    return run_raster_simulation(inputs, output_dir, parameters, **kwargs)
