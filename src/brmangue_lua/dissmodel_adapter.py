"""Optional integration of the model engine with the DissModel framework."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Callable

import pandas as pd

from .engine import BrMangueGrid, ModelParameters
from .persistent_blocks import PersistentBlockRunner

try:
    from dissmodel.core import Environment, Model
    from dissmodel.visualization import Chart, track_plot

    DISSMODEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without optional package
    DISSMODEL_AVAILABLE = False
    # The desktop application imports this module only to discover whether the
    # optional integration is available.  A real class is required here so
    # that the decorated adapter can still be defined in the compact build;
    # execution is blocked later by _require_dissmodel().
    Environment = Chart = None  # type: ignore[assignment]
    Model = object  # type: ignore[assignment,misc]

    def track_plot(*args: Any, **kwargs: Any):  # type: ignore[misc]
        def decorator(cls):
            return cls

        return decorator


def _require_dissmodel() -> None:
    if not DISSMODEL_AVAILABLE:
        raise ImportError(
            "DissModel is not installed. Install it from its local repository "
            "before selecting the DissModel execution mode."
        )


def _runner_summary(runner: Any, result: Any) -> dict[str, int | float]:
    if isinstance(result, dict):
        return result
    counts = runner.class_counts()
    counts["min_elevation"] = float(runner.relative_elevation.min())
    counts["max_elevation"] = float(runner.relative_elevation.max())
    return counts


@track_plot(label="Mangrove", color="#006d2c")
@track_plot(label="Flooded mangrove", color="#e41a1c")
@track_plot(label="Migrated mangrove", color="#2ca25f")
@track_plot(label="Annual gain", color="#74c476")
@track_plot(label="Annual loss", color="#fb6a4a")
class BRMangueLuaDissModel(Model):
    """DissModel component that calls the continuous or block executor."""

    def setup(  # type: ignore[override]
        self,
        runner: Any,
        parameters: ModelParameters,
        summaries: list[dict[str, Any]],
        step_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.runner = runner
        self.parameters = parameters
        self.summaries = summaries
        self.step_callback = step_callback

    def execute(self) -> None:
        year = int(round(self.env.now()))
        result = self.runner.step(year, self.parameters)
        summary = _runner_summary(self.runner, result)
        mangrove = int(summary["mangrove"])
        transitions = dict(getattr(self.runner, "last_transition_metrics", {}))
        extent = int(
            transitions.get(
                "mangrove_extent",
                mangrove + int(summary.get("migrated_mangrove", 0)),
            )
        )
        gain = int(transitions.get("annual_gain", 0))
        loss = int(transitions.get("annual_loss", 0))
        net = int(transitions.get("annual_net_change", gain - loss))

        self.mangrove = mangrove
        self.flooded = int(summary["flooded_mangrove"])
        self.migrated = int(summary["migrated_mangrove"])
        self.gain = gain
        self.loss = loss
        record = {
            "year": year,
            **summary,
            "mangrove_extent": extent,
            "annual_gain": gain,
            "annual_loss": loss,
            "annual_net_change": net,
            # Keep the short names used by the optional DissModel chart/API.
            "gain": gain,
            "loss": loss,
        }
        self.summaries.append(record)
        if self.step_callback is not None:
            self.step_callback(record)


def run_dissmodel(
    runner: Any,
    parameters: ModelParameters,
    *,
    show_chart: bool = False,
    step_callback: Callable[[dict[str, Any]], None] | None = None,
) -> pd.DataFrame:
    """Run the model with DissModel's clock and components."""
    _require_dissmodel()
    summaries: list[dict[str, Any]] = []
    environment = Environment(end_time=parameters.final_time + 1)
    BRMangueLuaDissModel(
        runner=runner,
        parameters=parameters,
        summaries=summaries,
        step_callback=step_callback,
        step=1,
        start_time=parameters.start,
        end_time=parameters.final_time + 1,
    )
    if show_chart:
        Chart(
            select=[
                "Mangrove",
                "Flooded mangrove",
                "Migrated mangrove",
                "Annual gain",
                "Annual loss",
            ],
            pause=True,
            show_grid=True,
            title="BRMANGUE Lua-parity — DissModel",
        )
    environment.run()
    return pd.DataFrame(summaries)


def run_dissmodel_shapefile(
    input_path: str | Path,
    output_dir: str | Path,
    parameters: ModelParameters,
    *,
    runner_mode: str = "continuous",
    block_size: int = 10_000,
    strict_lua_schema: bool = False,
    show_chart: bool = False,
) -> pd.DataFrame:
    """Run DissModel with the continuous or persistent block executor."""
    _require_dissmodel()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if runner_mode == "continuous":
        runner: Any = BrMangueGrid.from_shapefile(
            input_path, strict_lua_schema=strict_lua_schema
        )
    elif runner_mode == "blocks":
        runner = PersistentBlockRunner.create_from_shapefile(
            input_path,
            output_dir / "workspace",
            block_size=block_size,
            strict_lua_schema=strict_lua_schema,
        )
    else:
        raise ValueError("runner_mode must be 'continuous' or 'blocks'.")

    try:
        trajectory = run_dissmodel(runner, parameters, show_chart=show_chart)
        trajectory.to_csv(output_dir / "trajectory.csv", index=False)
        metadata = {
            "engine": "dissmodel",
            "runner_mode": runner_mode,
            "input": str(Path(input_path).resolve()),
            "cells": int(runner.size if hasattr(runner, "size") else runner.n_cells),
            "block_size": block_size if runner_mode == "blocks" else None,
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
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return trajectory
    finally:
        if hasattr(runner, "close"):
            runner.close()
