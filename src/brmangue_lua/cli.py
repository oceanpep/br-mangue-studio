"""Command-line interface for running the parity model."""

from __future__ import annotations

import argparse
from pathlib import Path

from .engine import ModelParameters, run_shapefile
from .sea_level import SeaLevelTrajectory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BRMANGUE Lua-parity model in Python")
    parser.add_argument("--input", required=True, help="Cell-grid shapefile")
    parser.add_argument("--output", default="outputs", help="Results folder")
    parser.add_argument("--final-time", type=int, default=100)
    parser.add_argument("--tide-height", type=float, default=6.0)
    forcing = parser.add_mutually_exclusive_group()
    forcing.add_argument("--sea-level-rise-rate", type=float, default=0.5, help="Constant rise in metres per annual step (legacy CLI units).")
    forcing.add_argument("--sea-level-trajectory", type=Path, help="CSV with year and cumulative sea_level_mm columns.")
    parser.add_argument("--initial-year", type=int, default=2025, help="Reference year for a sea-level trajectory.")
    parser.add_argument(
        "--accretion-rate-mm",
        type=float,
        default=None,
        help="Constant accretion rate in mm per step; omit it to preserve the Lua formula.",
    )
    parser.add_argument(
        "--engine",
        choices=("continuous", "blocks", "blocks-memory", "dissmodel"),
        default="continuous",
        help="Grid processing mode.",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=10_000,
        help="Number of cells per block in blocks mode.",
    )
    parser.add_argument(
        "--dissmodel-runner",
        choices=("continuous", "blocks"),
        default="continuous",
        help="Executor used when --engine dissmodel is selected.",
    )
    parser.add_argument(
        "--show-chart",
        action="store_true",
        help="Open the live DissModel chart.",
    )
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
        "--strict-lua-schema",
        action="store_true",
        help="Reproduce the missing SoilClass field when the shapefile only contains ClaseSolos.",
    )
    parser.add_argument(
        "--allow-migration-without-soil",
        action="store_true",
        help="Use vegetation and bare soil as migration candidates when no soil layer is available.",
    )
    parser.add_argument(
        "--migration-maturity-years",
        type=int,
        default=3,
        help="Complete years before a migrated cell can propagate (default: 3; 0 enables it on the next step).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = ModelParameters(
        final_time=args.final_time,
        tide_height=args.tide_height,
        sea_level_rise_rate=args.sea_level_rise_rate,
        legacy_lua_accretion_typo=args.legacy_lua_accretion_typo,
        allow_migration_without_soil=args.allow_migration_without_soil,
        accretion_rate_mm=args.accretion_rate_mm,
        migration_maturity_years=args.migration_maturity_years,
        sea_level_trajectory=SeaLevelTrajectory.from_csv(args.sea_level_trajectory) if args.sea_level_trajectory else None,
        sea_level_reference_year=args.initial_year,
    )
    trajectory = run_shapefile(
        args.input,
        args.output,
        params,
        strict_lua_schema=args.strict_lua_schema,
        engine=args.engine,
        block_size=args.block_size,
        dm_runner=args.dissmodel_runner,
        show_dissmodel_chart=args.show_chart,
    )
    print(trajectory.to_string(index=False))
    print(f"Results saved to: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
