"""Run a real BR-MANGUE raster simulation on a small Maranhão Island cutout.

The source files are not copied into the repository. The script accepts the
prepared Ilha do Maranhão land-cover and ANADEM paths, crops a small aligned
window, runs the raster engine, and uses the Studio figure/GIF pipeline.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import rasterio
from rasterio.windows import Window

from brmangue_lua.engine import ModelParameters
from brmangue_lua.raster_inputs import load_raster_inputs
from brmangue_lua.raster_runner import run_raster_simulation
from brmangue_studio.app import _generate_annual_figures, _generate_animation


MAPPING = {
    "mangrove": [1],
    "water": [3],
    "natural_accommodation_candidate": [2, 5],
    "managed_land_use_candidate": [4],
    "explicit_restriction": [],
}


def crop_aligned_raster(source: Path, destination: Path, window: Window, *, nodata: float | int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(source) as src:
        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            width=int(window.width),
            height=int(window.height),
            count=1,
            compress="lzw",
            tiled=False,
            nodata=nodata,
            transform=src.window_transform(window),
        )
        with rasterio.open(destination, "w", **profile) as dst:
            dst.write(src.read(1, window=window), 1)
            dst.update_tags(source=str(source), window=str(window))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--land-cover", type=Path, required=True)
    parser.add_argument("--elevation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset", type=Path, required=True)
    parser.add_argument("--row", type=int, default=1280)
    parser.add_argument("--col", type=int, default=1180)
    parser.add_argument("--size", type=int, default=60)
    parser.add_argument("--initial-year", type=int, default=2025)
    parser.add_argument("--steps", type=int, default=50)
    args = parser.parse_args()

    if args.size < 20 or args.steps < 1:
        raise ValueError("The cutout must have at least 20 cells per side and one step.")
    window = Window(args.col, args.row, args.size, args.size)
    args.output.mkdir(parents=True, exist_ok=True)
    land_cut = args.output / "ilha_maranhao_land_cover_2025_cutout.tif"
    elev_cut = args.output / "ilha_maranhao_anadem_30m_cutout.tif"
    crop_aligned_raster(args.land_cover, land_cut, window, nodata=255)
    crop_aligned_raster(args.elevation, elev_cut, window, nodata=-9999)

    inputs = load_raster_inputs(
        land_cover_path=land_cut,
        terrain_path=elev_cut,
        mapping=MAPPING,
        soil_enabled=False,
    )
    parameters = ModelParameters(
        start=1,
        final_time=args.steps,
        tide_height=6.0,
        sea_level_rise_rate=0.5,
        accretion_rate_mm=None,
        allow_migration_without_soil=True,
    )
    run_dir = args.output / "run_2025_2075"
    trajectory = run_raster_simulation(
        inputs,
        run_dir,
        parameters,
        initial_year=args.initial_year,
        engine="continuous",
        save_annual_states=True,
    )
    annual_figures = _generate_annual_figures(inputs, run_dir, trajectory)
    gif_path = _generate_animation(annual_figures, run_dir)
    if gif_path is None:
        raise RuntimeError("The raster runner did not generate an animation.")
    args.asset.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(gif_path, args.asset)
    print(f"cells={inputs.n_cells}")
    print(f"steps={len(trajectory)}")
    print(f"gif={args.asset}")
    print(f"run={run_dir}")


if __name__ == "__main__":
    main()
