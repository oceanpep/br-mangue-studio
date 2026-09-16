"""Application entry point for the desktop interface and batch diagnostics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys


def _resolve_input(project_dir: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else project_dir / path


def _run_batch(project_path: Path, output_dir: Path | None = None) -> int:
    """Run a project without opening the graphical interface."""
    from brmangue_lua.engine import ModelParameters
    from brmangue_lua.raster_inputs import DEFAULT_LAND_COVER_MAPPING, load_raster_inputs
    from brmangue_lua.raster_runner import run_raster_simulation
    from brmangue_studio.app import (
        _generate_annual_figures,
        _generate_animation,
        _generate_component_animations,
        _write_simulation_spreadsheet,
        _write_transition_report,
    )

    project_path = project_path.resolve()
    project_dir = project_path.parent
    config = json.loads(project_path.read_text(encoding="utf-8"))
    inputs_config = config["inputs"]
    land_cover_path = _resolve_input(project_dir, inputs_config.get("land_cover"))
    elevation_path = _resolve_input(project_dir, inputs_config.get("elevation"))
    mask_path = _resolve_input(project_dir, inputs_config.get("mask"))
    soil_path = _resolve_input(project_dir, inputs_config.get("soil"))
    if land_cover_path is None or elevation_path is None:
        raise ValueError("The project must define land-cover and elevation rasters.")

    mapping = {key: [] for key in DEFAULT_LAND_COVER_MAPPING}
    excluded: list[int] = []
    roles = {int(code): role for code, role in config.get("class_roles", {}).items()}
    role_to_mapping = {
        "Mangrove": "mangrove",
        "Natural vegetation": "natural_accommodation_candidate",
        "Water": "water",
        "Anthropized / blocked": "managed_land_use_candidate",
    }
    for code, role in roles.items():
        if role == "Exclude":
            excluded.append(code)
        elif role in role_to_mapping:
            mapping[role_to_mapping[role]].append(code)

    params_config = config.get("parameters", {})
    initial_year = int(params_config.get("initial_year", 2025))
    final_year = int(params_config.get("final_year", 2100))
    accretion_text = str(params_config.get("accretion_rate_mm", "")).strip()
    accretion = float(accretion_text) if accretion_text else None
    soil_enabled = bool(params_config.get("soil_enabled", False) and soil_path is not None)
    inputs = load_raster_inputs(
        land_cover_path,
        elevation_path,
        mask_path=mask_path,
        soil_path=soil_path,
        soil_enabled=soil_enabled,
        land_cover_band=int(config.get("land_cover", {}).get("band", 1)),
        land_cover_year=config.get("land_cover", {}).get("reference_year"),
        mapping=mapping,
        exclude_source_codes=excluded,
    )
    parameters = ModelParameters(
        start=1,
        final_time=final_year - initial_year,
        tide_height=float(params_config.get("tide_height_m", 6.0)),
        sea_level_rise_rate=float(
            params_config.get(
                "sea_level_rise_m_per_model_step",
                float(params_config.get("sea_level_rise_mm_per_year", 0.0)) / 1000.0,
            )
        ),
        allow_migration_without_soil=bool(params_config.get("allow_migration_without_soil", False)),
        accretion_rate_mm=accretion,
    )
    engine = str(params_config.get("engine", "blocks"))
    block_size = int(params_config.get("block_size", 10_000))
    if output_dir is None:
        output_dir = project_dir / "results" / f"run_batch_{datetime.now():%Y%m%dT%H%M%S}"
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    trajectory = run_raster_simulation(
        inputs,
        output_dir,
        parameters,
        initial_year=initial_year,
        engine=engine,
        block_size=block_size,
        dissmodel_runner="blocks",
        show_dissmodel_chart=False,
        save_annual_states=True,
    )
    final_path = output_dir / f"final_usos_{final_year}.tif"
    if final_path.exists():
        import rasterio

        with rasterio.open(final_path) as src:
            final_state = src.read(1)[inputs.valid_rows, inputs.valid_cols]
        _write_transition_report(
            str(land_cover_path),
            int(config.get("land_cover", {}).get("band", 1)),
            inputs,
            final_state,
            roles,
            output_dir / "transition_by_land_cover_code.csv",
        )
    figures = _generate_annual_figures(inputs, output_dir, trajectory)
    gif = _generate_animation(figures, output_dir)
    animations = _generate_component_animations(output_dir, figures)
    spreadsheet = _write_simulation_spreadsheet(inputs, output_dir, trajectory)
    print(json.dumps({
        "output_dir": str(output_dir),
        "years": len(trajectory),
        "final_year": int(trajectory["calendar_year"].iloc[-1]),
        "annual_figures": len(figures),
        "gif": str(gif) if gif else None,
        "animations": {key: str(path) for key, path in animations.items()},
        "spreadsheet": str(spreadsheet),
        "cells": inputs.n_cells,
    }, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--batch-project", type=Path, help="Run a project without opening the GUI.")
    parser.add_argument("--output-dir", type=Path, help="Output directory for batch execution.")
    args = parser.parse_args()
    if args.batch_project:
        try:
            return _run_batch(args.batch_project, args.output_dir)
        except Exception as exc:
            log_root = args.output_dir.parent if args.output_dir else Path(sys.executable).parent
            log_root.mkdir(parents=True, exist_ok=True)
            log_path = log_root / "brmangue_batch_error.log"
            log_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
            return 2
    from brmangue_studio.app import main as gui_main

    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
