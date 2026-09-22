"""Compare two BR-MANGUE Studio run directories.

Usage:
    python scripts/compare_runs.py results/run_continuous results/run_blocks

The report separates state equivalence from timing differences. It is intended
for benchmark evidence, not for ecological validation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


def _final_raster(run_dir: Path) -> Path | None:
    candidates = sorted(run_dir.glob("final_usos_*.tif"))
    return candidates[-1] if candidates else None


def compare(run_a: Path, run_b: Path) -> dict[str, object]:
    trajectory_a = pd.read_csv(run_a / "trajectory.csv")
    trajectory_b = pd.read_csv(run_b / "trajectory.csv")
    common_years = sorted(
        set(trajectory_a.get("calendar_year", []))
        & set(trajectory_b.get("calendar_year", []))
    )
    state_columns = [
        column
        for column in ("mangrove", "migrated_mangrove", "flooded_mangrove")
        if column in trajectory_a.columns and column in trajectory_b.columns
    ]
    left = trajectory_a.set_index("calendar_year").loc[common_years, state_columns]
    right = trajectory_b.set_index("calendar_year").loc[common_years, state_columns]
    trajectory_delta = (left - right).abs()

    raster_report: dict[str, object] = {"available": False}
    raster_a = _final_raster(run_a)
    raster_b = _final_raster(run_b)
    if raster_a is not None and raster_b is not None:
        with rasterio.open(raster_a) as source_a, rasterio.open(raster_b) as source_b:
            array_a = source_a.read(1)
            array_b = source_b.read(1)
        if array_a.shape != array_b.shape:
            raster_report = {
                "available": True,
                "same_shape": False,
                "shape_a": list(array_a.shape),
                "shape_b": list(array_b.shape),
            }
        else:
            difference = np.asarray(array_a) != np.asarray(array_b)
            raster_report = {
                "available": True,
                "same_shape": True,
                "differing_cells": int(np.count_nonzero(difference)),
                "max_absolute_difference": float(
                    np.max(np.abs(array_a.astype(np.int64) - array_b.astype(np.int64)))
                )
                if array_a.size
                else 0.0,
            }

    return {
        "run_a": str(run_a),
        "run_b": str(run_b),
        "common_years": len(common_years),
        "trajectory_state_columns": state_columns,
        "trajectory_max_absolute_difference": float(trajectory_delta.to_numpy().max())
        if not trajectory_delta.empty
        else None,
        "trajectory_differing_values": int(np.count_nonzero(trajectory_delta.to_numpy()))
        if not trajectory_delta.empty
        else 0,
        "final_raster": raster_report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_a", type=Path)
    parser.add_argument("run_b", type=Path)
    args = parser.parse_args()
    report = compare(args.run_a, args.run_b)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

