"""Command-line interface for simulations over aligned rasters."""

from __future__ import annotations

import argparse
from pathlib import Path

from .engine import ModelParameters
from .sea_level import SeaLevelTrajectory
from .raster_runner import load_and_run_raster_simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the BRMANGUE Lua-parity model over aligned rasters."
    )
    parser.add_argument(
        "--land-cover", "--mapbiomas", dest="land_cover", required=True,
        help="Categorical land-cover raster; the legacy --mapbiomas option remains supported.",
    )
    parser.add_argument(
        "--elevation", "--terrain", dest="elevation", required=True,
        help="Elevation raster aligned with the categorical raster.",
    )
    parser.add_argument("--mask", help="Binary study-area mask.")
    parser.add_argument("--soil", help="Optional soil-class raster.")
    parser.add_argument(
        "--disable-soil",
        action="store_true",
        help="Ignore the soil layer even when --soil is provided.",
    )
    parser.add_argument(
        "--no-migration-without-soil",
        action="store_true",
        help="Keep migration soil-dependent; by default, land-cover classes are used when soil is unavailable.",
    )
    parser.add_argument("--land-cover-band", "--mapbiomas-band", dest="land_cover_band", type=int, default=1)
    parser.add_argument("--land-cover-year", "--mapbiomas-year", dest="land_cover_year", type=int, default=None)
    parser.add_argument("--initial-year", type=int, default=2025)
    parser.add_argument("--final-year", type=int, default=2035)
    parser.add_argument("--output", default="outputs/brmangue_run")
    parser.add_argument(
        "--engine",
        choices=("continuous", "blocks", "dissmodel"),
        default="blocks",
        help="Executor: continuous, persistent blocks, or DissModel.",
    )
    parser.add_argument("--block-size", type=int, default=10_000)
    parser.add_argument(
        "--dissmodel-runner",
        choices=("continuous", "blocks"),
        default="blocks",
        help="Rule executor used by DissModel.",
    )
    parser.add_argument("--tide-height", type=float, default=6.0)
    forcing = parser.add_mutually_exclusive_group()
    forcing.add_argument("--sea-level-rise-rate", type=float, default=0.5, help="Constant rise in metres per annual step (legacy CLI units).")
    forcing.add_argument("--sea-level-trajectory", type=Path, help="CSV with year and cumulative sea_level_mm columns; linearly interpolated and rebased to --initial-year.")
    parser.add_argument("--accretion-rate-mm", type=float, default=None, help="Constant surface accretion in mm/year; omit to use the Alongi regression.")
    parser.add_argument(
        "--fix-accretion-typo",
        action="store_true",
        help="Deprecated compatibility flag; current state-based accretion is already the default.",
    )
    parser.add_argument(
        "--legacy-lua-accretion-typo",
        action="store_true",
        help="Reproduce the earlier soil-gated accretion behavior for comparison with old runs.",
    )
    parser.add_argument(
        "--migration-maturity-years",
        type=int,
        default=3,
        help="Complete years before a migrated cell can propagate (default: 3; 0 enables it on the next step).",
    )
    parser.add_argument("--show-chart", action="store_true")
    parser.add_argument(
        "--no-annual-states",
        action="store_true",
        help="Do not write one GeoTIFF per year (reduces disk use).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.final_year < args.initial_year:
        raise SystemExit("--final-year must be greater than or equal to --initial-year.")
    steps = args.final_year - args.initial_year
    soil_enabled = False if args.disable_soil else (args.soil is not None)
    parameters = ModelParameters(
        start=1,
        final_time=steps,
        tide_height=args.tide_height,
        sea_level_rise_rate=args.sea_level_rise_rate,
        legacy_lua_accretion_typo=args.legacy_lua_accretion_typo,
        allow_migration_without_soil=(not soil_enabled) and (not args.no_migration_without_soil),
        migration_maturity_years=args.migration_maturity_years,
        accretion_rate_mm=args.accretion_rate_mm,
        sea_level_trajectory=SeaLevelTrajectory.from_csv(args.sea_level_trajectory) if args.sea_level_trajectory else None,
        sea_level_reference_year=args.initial_year,
    )
    trajectory = load_and_run_raster_simulation(
        args.land_cover,
        args.elevation,
        args.output,
        parameters,
        mask_path=args.mask,
        soil_path=args.soil,
        soil_enabled=soil_enabled,
        mapbiomas_band=args.land_cover_band,
        mapbiomas_year=args.land_cover_year,
        initial_year=args.initial_year,
        engine=args.engine,
        block_size=args.block_size,
        dissmodel_runner=args.dissmodel_runner,
        show_dissmodel_chart=args.show_chart,
        save_annual_states=not args.no_annual_states,
    )
    print(trajectory.to_string(index=False))
    print(f"Results saved to: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
