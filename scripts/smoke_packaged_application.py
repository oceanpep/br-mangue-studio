"""Run a soil-free raster simulation through a packaged desktop executable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin


def _write_raster(path: Path, values: np.ndarray, dtype: str, nodata: int | float) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=values.shape[0],
        width=values.shape[1],
        count=1,
        dtype=dtype,
        crs="EPSG:5880",
        transform=from_origin(500000, 9700000, 30, 30),
        nodata=nodata,
    ) as destination:
        destination.write(values, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True, type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve()

    with tempfile.TemporaryDirectory(prefix="brmangue-packaged-smoke-") as temporary:
        root = Path(temporary)
        land_cover = root / "land_cover.tif"
        elevation = root / "dem.tif"
        _write_raster(land_cover, np.full((3, 3), 90, dtype=np.uint8), "uint8", 0)
        _write_raster(elevation, np.ones((3, 3), dtype=np.float32), "float32", -9999)

        for engine in ("continuous", "blocks"):
            project = root / f"project_{engine}.json"
            project.write_text(json.dumps({
                "format": "brmangue-studio-project",
                "version": "1.3.0",
                "inputs": {
                    "land_cover": land_cover.name,
                    "elevation": elevation.name,
                    "mask": "",
                    "soil": "",
                },
                "land_cover": {"band": 1, "reference_year": 2025},
                "class_mapping_mode": "custom",
                "class_roles": {"90": "custom:300"},
                "custom_model_classes": [{
                    "code": 300,
                    "name": "Mangrove stand",
                    "color": "#006d2c",
                    "behavior": "mangrove",
                }],
                "parameters": {
                    "initial_year": 2025,
                    "final_year": 2026,
                    "tide_height_m": 0,
                    "sea_level_rise_mm_per_year": 3.4,
                    "engine": engine,
                    "block_size": 3,
                    "soil_enabled": False,
                },
            }, indent=2), encoding="utf-8")

            output = root / f"output_{engine}"
            result = subprocess.run(
                [str(executable), "--batch-project", str(project), "--output-dir", str(output)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            if result.returncode != 0:
                error_log = output.parent / "brmangue_batch_error.log"
                detail = error_log.read_text(encoding="utf-8") if error_log.exists() else result.stderr
                raise RuntimeError(f"Packaged {engine} run failed ({result.returncode}): {detail}")

            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            trajectory = pd.read_csv(output / "trajectory.csv")
            expected_minimum = 1.0 + (1.693 + 0.939 * 3.4) / 1000
            if metadata["soil_enabled"] is not False:
                raise AssertionError(f"{engine}: soil suitability should be disabled")
            if metadata["parameters"]["legacy_lua_accretion_typo"] is not False:
                raise AssertionError(f"{engine}: state-based accretion should be the default")
            if not np.isclose(trajectory.loc[0, "min_elevation"], expected_minimum, atol=1e-9):
                raise AssertionError(
                    f"{engine}: expected minimum elevation {expected_minimum}, "
                    f"got {trajectory.loc[0, 'min_elevation']}"
                )
            with rasterio.open(output / "final_state_2026.tif") as final_state:
                if not np.all(final_state.read(1) == 300):
                    raise AssertionError(f"{engine}: unexpected final class state")

    print("Packaged executable passed soil-free accretion smoke test for both engines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
