"""Raster execution for the cellular model.

The runner uses a compact list of valid pixels and can optionally persist two
state arrays on disk for large domains.
"""

from __future__ import annotations

from pathlib import Path
import json
import shutil
import time
import gc
import threading
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


def _safe_process_io(process: Any | None) -> dict[str, int] | None:
    """Return process I/O counters when the operating system exposes them."""
    if process is None:
        return None
    try:
        counters = process.io_counters()
    except Exception:
        return None
    return {
        "read_bytes": int(getattr(counters, "read_bytes", 0)),
        "write_bytes": int(getattr(counters, "write_bytes", 0)),
    }


def _safe_cpu_times(process: Any | None) -> dict[str, float] | None:
    """Return user and system CPU seconds when available."""
    if process is None:
        return None
    try:
        times = process.cpu_times()
    except Exception:
        return None
    return {
        "user_seconds": float(getattr(times, "user", 0.0)),
        "system_seconds": float(getattr(times, "system", 0.0)),
    }


def _safe_virtual_memory() -> dict[str, int] | None:
    """Return system memory counters without making psutil mandatory."""
    if psutil is None:
        return None
    try:
        memory = psutil.virtual_memory()
    except (AttributeError, OSError, psutil.Error):
        return None
    return {
        "total_bytes": int(memory.total),
        "available_bytes": int(memory.available),
        "used_bytes": int(memory.used),
        "percent": float(memory.percent),
    }


def _directory_size_bytes(path: Path) -> int:
    """Sum completed output files, ignoring files that disappear mid-scan."""
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += int(item.stat().st_size)
        except OSError:
            continue
    return total


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

    run_started = time.perf_counter()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    states_dir = output_dir / "states"
    if save_annual_states:
        states_dir.mkdir(parents=True, exist_ok=True)
    write_input_metadata(inputs, output_dir / "input_metadata.json")
    if inputs.grid is None:
        raise ValueError("Os rasters precisam ser carregados antes de iniciar a simulação.")
    inputs.write_state_raster(inputs.grid.usos, output_dir / f"initial_usos_{initial_year}.tif", year=initial_year)
    initial_class_counts = dict(inputs.grid.class_counts())

    runner: Any
    workspace: Path | None = None
    input_grid_released = False
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
        # The persistent runner now owns the state and neighbourhood arrays.
        # Drop the full materialized grid during the simulation so its arrays
        # are not kept alongside the two on-disk state slots.
        inputs.grid = None
        input_grid_released = True
        gc.collect()
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
            inputs.grid = None
            input_grid_released = True
            gc.collect()

    # Start performance and memory accounting after the persistent runner has
    # been created and the full materialized input grid has been released.
    # This reports the cost of the simulation itself instead of counting the
    # one-time setup copy as resident state for every block step.
    started = time.perf_counter()
    process = psutil.Process() if psutil is not None else None
    rss_before = process.memory_info().rss if process else None
    peak_rss = rss_before or 0
    memory_before = _safe_virtual_memory()
    disk_free_before = int(shutil.disk_usage(output_dir).free)
    io_before = _safe_process_io(process)
    cpu_before = _safe_cpu_times(process)
    last_step_mark = started
    resource_samples: list[dict[str, Any]] = []
    sampling_stop = threading.Event()
    sampler_thread: threading.Thread | None = None

    def _sample_resources() -> None:
        if process is None or psutil is None:
            return
        while True:
            sample_time = time.perf_counter()
            try:
                memory = psutil.virtual_memory()
                disk_free = shutil.disk_usage(output_dir).free
                resource_samples.append(
                    {
                        "elapsed_seconds": round(sample_time - started, 6),
                        "rss_bytes": int(process.memory_info().rss),
                        "system_memory_available_bytes": int(memory.available),
                        "system_memory_used_bytes": int(memory.used),
                        "system_memory_percent": float(memory.percent),
                        "cpu_percent": float(psutil.cpu_percent(None)),
                        "disk_free_bytes": int(disk_free),
                    }
                )
            except Exception:
                pass
            if sampling_stop.wait(1.0):
                return

    if process is not None:
        sampler_thread = threading.Thread(
            target=_sample_resources,
            name="brmangue-resource-sampler",
            daemon=True,
        )
        sampler_thread.start()

    rows: list[dict[str, Any]] = []
    # Compare the first annual loss with the initial state rather than with a
    # state that has already been updated in the current run.
    previous_mangrove: int | None = int(initial_class_counts.get("mangrove", 0))
    try:
        if engine == "dissmodel":
            from .dissmodel_adapter import run_dissmodel

            def _handle_dissmodel_step(record: dict[str, Any]) -> None:
                """Forward each DissModel event to annual outputs and GUI."""
                nonlocal last_step_mark, peak_rss
                year_index = int(record["year"])
                calendar_year = int(initial_year + year_index)
                step_elapsed = max(time.perf_counter() - last_step_mark, 0.0)
                last_step_mark = time.perf_counter()
                step_rss = process.memory_info().rss if process else None
                if step_rss is not None:
                    peak_rss = max(peak_rss, step_rss)
                summary = dict(record)
                row: dict[str, Any] = {
                    "year": year_index,
                    "calendar_year": calendar_year,
                    **summary,
                    "annual_gain": int(record.get("gain", 0)),
                    "annual_loss": int(record.get("loss", 0)),
                    "step_elapsed_seconds": round(step_elapsed, 6),
                    "step_rss_bytes": step_rss,
                    "step_cells_per_second": round(inputs.n_cells / step_elapsed, 3)
                    if step_elapsed > 0
                    else None,
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
                previous = int(initial_class_counts.get("mangrove", 0))
                gains: list[int] = []
                losses: list[int] = []
                for value in trajectory["mangrove"].astype(int):
                    gains.append(max(int(value) - previous, 0))
                    losses.append(max(previous - int(value), 0))
                    previous = int(value)
                trajectory["gain"] = gains
                trajectory["loss"] = losses
            step_metrics = pd.DataFrame(rows)
            if not step_metrics.empty:
                metric_columns = [
                    "year",
                    "step_elapsed_seconds",
                    "step_rss_bytes",
                    "step_cells_per_second",
                ]
                trajectory = trajectory.merge(
                    step_metrics[metric_columns], on="year", how="left"
                )
            trajectory.to_csv(output_dir / "trajectory.csv", index=False)
            _write_state(inputs, runner, output_dir / f"final_usos_{initial_year + parameters.final_time}.tif", initial_year + parameters.final_time)
            rows = trajectory.to_dict(orient="records")
        else:
            for time_index in range(parameters.start, parameters.final_time + 1):
                step_started = time.perf_counter()
                if engine == "continuous":
                    runner.step(time_index, parameters)
                    summary = _summary_grid(runner)
                else:
                    summary = runner.step(time_index, parameters)
                mangrove = int(summary["mangrove"])
                previous = mangrove if previous_mangrove is None else previous_mangrove
                calendar_year = int(initial_year + time_index)
                step_elapsed = max(time.perf_counter() - step_started, 0.0)
                step_rss = process.memory_info().rss if process else None
                row: dict[str, Any] = {
                    "year": int(time_index),
                    "calendar_year": calendar_year,
                    **summary,
                    "annual_gain": max(mangrove - previous, 0),
                    "annual_loss": max(previous - mangrove, 0),
                    "step_elapsed_seconds": round(step_elapsed, 6),
                    "step_rss_bytes": step_rss,
                    "step_cells_per_second": round(inputs.n_cells / step_elapsed, 3)
                    if step_elapsed > 0
                    else None,
                }
                rows.append(row)
                previous_mangrove = mangrove
                if step_rss is not None:
                    peak_rss = max(peak_rss, step_rss)
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
        sampling_stop.set()
        if sampler_thread is not None:
            sampler_thread.join(timeout=2.0)
        if hasattr(runner, "close"):
            runner.close()

    final_year = int(initial_year + parameters.final_time)
    final_path = output_dir / f"final_usos_{final_year}.tif"
    if save_annual_states and (states_dir / f"usos_{final_year}.tif").exists():
        shutil.copy2(states_dir / f"usos_{final_year}.tif", final_path)
    elif not final_path.exists():
        _write_state(inputs, runner, final_path, final_year)

    # Close and release persistent memmaps before post-processing.  The full
    # input grid remains released; the GUI reads only a downsampled elevation
    # preview when it generates figures.
    if hasattr(runner, "close"):
        runner.close()
    runner_to_release = runner
    runner = None
    del runner_to_release
    gc.collect()

    if process is not None:
        peak_rss = max(peak_rss, process.memory_info().rss)
    simulation_finished = time.perf_counter()
    rss_after = process.memory_info().rss if process else None
    memory_after = _safe_virtual_memory()
    io_after = _safe_process_io(process)
    cpu_after = _safe_cpu_times(process)
    disk_free_after = int(shutil.disk_usage(output_dir).free)
    simulation_elapsed = simulation_finished - started
    steps_completed = len(rows)
    total_cell_updates = int(inputs.n_cells) * steps_completed
    output_size_before_metadata = _directory_size_bytes(output_dir)
    resource_trace_path = output_dir / "resource_samples.csv"
    if resource_samples:
        pd.DataFrame(resource_samples).to_csv(resource_trace_path, index=False)

    def _delta_counter(
        before: dict[str, int] | None, after: dict[str, int] | None, key: str
    ) -> int | None:
        if before is None or after is None:
            return None
        return int(after.get(key, 0) - before.get(key, 0))

    io_delta = None
    if io_before is not None and io_after is not None:
        io_delta = {
            "read_bytes": _delta_counter(io_before, io_after, "read_bytes"),
            "write_bytes": _delta_counter(io_before, io_after, "write_bytes"),
        }
    cpu_delta = None
    if cpu_before is not None and cpu_after is not None:
        cpu_delta = {
            "user_seconds": round(
                cpu_after["user_seconds"] - cpu_before["user_seconds"], 6
            ),
            "system_seconds": round(
                cpu_after["system_seconds"] - cpu_before["system_seconds"], 6
            ),
        }
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
        # ``elapsed_seconds`` is retained for compatibility and refers to the
        # simulation interval only. The detailed timing block distinguishes
        # preparation, simulation, and output/post-processing work.
        "elapsed_seconds": round(simulation_elapsed, 6),
        "rss_before_bytes": rss_before,
        "peak_rss_bytes": peak_rss,
        "performance": {
            "preparation_elapsed_seconds": round(started - run_started, 6),
            "simulation_elapsed_seconds": round(simulation_elapsed, 6),
            "postprocessing_elapsed_seconds": None,
            "total_run_elapsed_seconds": None,
            "annual_steps": steps_completed,
            "cell_updates": total_cell_updates,
            "cell_updates_per_second": round(total_cell_updates / simulation_elapsed, 3)
            if simulation_elapsed > 0
            else None,
            "rss_before_bytes": rss_before,
            "rss_after_bytes": rss_after,
            "peak_rss_bytes": peak_rss,
            "peak_rss_gib": round(peak_rss / 1024**3, 6),
            "system_memory_before": memory_before,
            "system_memory_after": memory_after,
            "disk_free_before_bytes": disk_free_before,
            "disk_free_after_bytes": disk_free_after,
            "output_size_bytes": output_size_before_metadata,
            "process_io_before": io_before,
            "process_io_after": io_after,
            "process_io_delta": io_delta,
            "process_cpu_before": cpu_before,
            "process_cpu_after": cpu_after,
            "process_cpu_delta": cpu_delta,
            "resource_trace": resource_trace_path.name if resource_samples else None,
            "resource_sample_count": len(resource_samples),
            "resource_sampling_interval_seconds": 1.0 if resource_samples else None,
            "measurement_scope": (
                "Simulation starts after input validation, raster loading, and "
                "persistent block workspace creation. Output files are included "
                "in total run timing but not in the simulation timing."
            ),
        },
        "block_input_materialization": {
            "input_grid_released_after_persistent_copy": bool(input_grid_released),
            "reopened_for_postprocessing": False,
            "memory_note": (
                "The full input grid is released while persistent blocks run; "
                "post-run figures use raster metadata and a downsampled elevation preview."
            ) if input_grid_released else None,
        },
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
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    postprocessing_elapsed = max(time.perf_counter() - simulation_finished, 0.0)
    metadata["performance"]["postprocessing_elapsed_seconds"] = round(
        postprocessing_elapsed, 6
    )
    metadata["performance"]["total_run_elapsed_seconds"] = round(
        time.perf_counter() - run_started, 6
    )
    metadata["performance"]["output_size_bytes"] = _directory_size_bytes(output_dir)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
