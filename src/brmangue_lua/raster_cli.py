"""Linha de comando para simulações sobre rasters alinhados."""

from __future__ import annotations

import argparse
from pathlib import Path

from .engine import ModelParameters
from .raster_runner import load_and_run_raster_simulation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Executa a tradução BRMANGUE Lua-parity sobre rasters alinhados."
    )
    parser.add_argument(
        "--land-cover", "--mapbiomas", dest="land_cover", required=True,
        help="Raster categórico de uso/cobertura; a forma antiga --mapbiomas é aceita por compatibilidade.",
    )
    parser.add_argument(
        "--elevation", "--terrain", dest="elevation", required=True,
        help="Raster de elevação alinhado ao raster categórico.",
    )
    parser.add_argument("--mask", help="Máscara binária da área de estudo.")
    parser.add_argument("--soil", help="Raster opcional de classes de solo.")
    parser.add_argument(
        "--disable-soil",
        action="store_true",
        help="Ignora a camada de solo mesmo se --soil for informado.",
    )
    parser.add_argument(
        "--no-migration-without-soil",
        action="store_true",
        help="Mantém a migração dependente de solo; por padrão ela usa o uso/cobertura quando o solo está ausente.",
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
        help="Executor: contínuo, blocos persistentes ou DissModel.",
    )
    parser.add_argument("--block-size", type=int, default=10_000)
    parser.add_argument(
        "--dissmodel-runner",
        choices=("continuous", "blocks"),
        default="blocks",
        help="Executor de regras usado pelo DissModel.",
    )
    parser.add_argument("--tide-height", type=float, default=6.0)
    parser.add_argument("--sea-level-rise-rate", type=float, default=0.5)
    parser.add_argument(
        "--fix-accretion-typo",
        action="store_true",
        help="Ativa a regra pretendida de acreção para solo migrado.",
    )
    parser.add_argument(
        "--migration-maturity-years",
        type=int,
        default=3,
        help="Anos completos antes de uma célula migrada poder propagar (padrão: 3; 0 ativa no passo seguinte).",
    )
    parser.add_argument("--show-chart", action="store_true")
    parser.add_argument(
        "--no-annual-states",
        action="store_true",
        help="Não grava um GeoTIFF para cada ano (reduz espaço em disco).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.final_year < args.initial_year:
        raise SystemExit("--final-year deve ser maior ou igual a --initial-year.")
    steps = args.final_year - args.initial_year
    soil_enabled = False if args.disable_soil else (args.soil is not None)
    parameters = ModelParameters(
        start=1,
        final_time=steps,
        tide_height=args.tide_height,
        sea_level_rise_rate=args.sea_level_rise_rate,
        legacy_lua_accretion_typo=not args.fix_accretion_typo,
        allow_migration_without_soil=(not soil_enabled) and (not args.no_migration_without_soil),
        migration_maturity_years=args.migration_maturity_years,
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
    print(f"Resultados salvos em: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
