"""Linha de comando para executar a tradução de paridade."""

from __future__ import annotations

import argparse
from pathlib import Path

from .engine import ModelParameters, run_shapefile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BRMANGUE Lua-parity em Python")
    parser.add_argument("--input", required=True, help="Shapefile da grade celular")
    parser.add_argument("--output", default="outputs", help="Pasta de resultados")
    parser.add_argument("--final-time", type=int, default=100)
    parser.add_argument("--tide-height", type=float, default=6.0)
    parser.add_argument("--sea-level-rise-rate", type=float, default=0.5)
    parser.add_argument(
        "--accretion-rate-mm",
        type=float,
        default=None,
        help="Taxa constante de acreção em mm por passo; omitida preserva a fórmula Lua.",
    )
    parser.add_argument(
        "--engine",
        choices=("continuous", "blocks", "blocks-memory", "dissmodel"),
        default="continuous",
        help="Modo de processamento da grade.",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=10_000,
        help="Número de células por bloco no modo blocks.",
    )
    parser.add_argument(
        "--dissmodel-runner",
        choices=("continuous", "blocks"),
        default="continuous",
        help="Executor usado quando --engine dissmodel é selecionado.",
    )
    parser.add_argument(
        "--show-chart",
        action="store_true",
        help="Abre o gráfico ao vivo do DissModel.",
    )
    parser.add_argument(
        "--fix-accretion-typo",
        action="store_true",
        help="Usa ClasseSolos migrado na acreção, em vez de reproduzir o erro Lua.",
    )
    parser.add_argument(
        "--strict-lua-schema",
        action="store_true",
        help="Reproduz a ausência de ClasseSolos quando o shapefile só possui ClaseSolos.",
    )
    parser.add_argument(
        "--allow-migration-without-soil",
        action="store_true",
        help="Usa vegetação/solo exposto como candidatos à migração sem camada de solo.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    params = ModelParameters(
        final_time=args.final_time,
        tide_height=args.tide_height,
        sea_level_rise_rate=args.sea_level_rise_rate,
        legacy_lua_accretion_typo=not args.fix_accretion_typo,
        allow_migration_without_soil=args.allow_migration_without_soil,
        accretion_rate_mm=args.accretion_rate_mm,
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
    print(f"Resultados salvos em: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
