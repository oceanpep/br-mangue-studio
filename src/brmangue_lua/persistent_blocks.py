"""Motor em blocos persistente para a tradução Lua/TerraME.

O estado fica em ``numpy.memmap`` e apenas o intervalo de células do bloco é
percorrido por vez. A vizinhança é materializada como índices de até oito
vizinhos, o que preserva a ordem e a semântica de ``cell.past`` do TerraME
sem carregar uma lista de objetos por célula.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time
import gc
from typing import Any

import numpy as np
import pandas as pd

try:
    import psutil
except ImportError:  # pragma: no cover - optional diagnostic only
    psutil = None

from .engine import (
    AREA_ANTROPIZADA,
    AREA_ANTROPIZADA_INUNDADO,
    CANAL_FLUVIAL,
    MANGUE,
    MANGUE_INUNDADO,
    MANGUE_MIGRADO,
    MAR,
    ModelParameters,
    SOLO_DESCOBERTO,
    SOLO_DESCOBERTO_INUNDADO,
    SOLO_MANGUE,
    SOLO_MANGUE_MIGRADO,
    VEGETACAO_TERRESTRE,
    VEGETACAO_TERRESTRE_INUNDADO,
    is_sea_or_flooded,
)


STATE_DTYPES: dict[str, np.dtype[Any]] = {
    "usos": np.dtype("int16"),
    "alt2": np.dtype("float64"),
    "classe_solos": np.dtype("int16"),
}


def _memmap(path: Path, dtype: np.dtype[Any], shape: tuple[int, ...], mode: str) -> np.memmap:
    return np.memmap(path, dtype=dtype, mode=mode, shape=shape)


@dataclass
class PersistentBlockRunner:
    """Executor com dois estados alternados persistidos em disco."""

    root: Path
    n_cells: int
    block_size: int
    neighbors: np.memmap
    state_a: dict[str, np.memmap]
    state_b: dict[str, np.memmap]
    current_slot: str = "a"
    years_completed: int = 0

    @classmethod
    def create_from_shapefile(
        cls,
        input_path: str | Path,
        root: str | Path,
        *,
        block_size: int = 10_000,
        strict_lua_schema: bool = False,
    ) -> "PersistentBlockRunner":
        import geopandas as gpd
        from .engine import BrMangueGrid

        frame = gpd.read_file(input_path)
        grid = BrMangueGrid.from_geodataframe(
            frame,
            source_path=str(Path(input_path).resolve()),
            strict_lua_schema=strict_lua_schema,
        )
        return cls.create_from_grid(
            grid,
            root,
            block_size=block_size,
            source_path=str(Path(input_path).resolve()),
            strict_lua_schema=strict_lua_schema,
        )

    @classmethod
    def create_from_grid(
        cls,
        grid: "BrMangueGrid",
        root: str | Path,
        *,
        block_size: int = 10_000,
        source_path: str | None = None,
        strict_lua_schema: bool = False,
    ) -> "PersistentBlockRunner":
        """Cria workspace a partir de uma grade já carregada em arrays."""
        root = Path(root).resolve()
        if root.exists() and any(root.iterdir()):
            raise FileExistsError(f"A pasta de workspace não está vazia: {root}")
        root.mkdir(parents=True, exist_ok=True)
        if block_size < 1:
            raise ValueError("block_size deve ser maior ou igual a 1.")

        n = grid.size

        state: dict[str, dict[str, np.memmap]] = {}
        for slot in ("a", "b"):
            slot_dir = root / f"estado_{slot}"
            slot_dir.mkdir()
            state[slot] = {}
            for name, dtype in STATE_DTYPES.items():
                state[slot][name] = _memmap(
                    slot_dir / f"{name}.dat", dtype, (n,), "w+"
                )
                source = {
                    "usos": grid.usos,
                    "alt2": grid.alt2,
                    "classe_solos": grid.classe_solos,
                }[name]
                state[slot][name][:] = source
                state[slot][name].flush()

        neighbors = _memmap(root / "neighbors.dat", np.dtype("int32"), (n, 8), "w+")
        neighbors[:] = -1
        for i, values in enumerate(grid.neighbors):
            values_array = np.asarray(values, dtype=np.int32)
            if values_array.size:
                neighbors[i, : min(values_array.size, 8)] = values_array[:8]
        neighbors.flush()

        metadata = {
            "engine": "python_lua_parity_persistent_blocks",
            "input": source_path or grid.source_path,
            "cells": n,
            "block_size": int(block_size),
            "neighbor_count": 8,
            "strict_lua_schema": bool(strict_lua_schema),
            "state_dtype": {name: str(dtype) for name, dtype in STATE_DTYPES.items()},
        }
        (root / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # A geometria e os vetores temporários usados para construir o
        # workspace não permanecem vivos durante a simulação.
        del grid
        gc.collect()
        return cls(
            root=root,
            n_cells=n,
            block_size=int(block_size),
            neighbors=neighbors,
            state_a=state["a"],
            state_b=state["b"],
        )

    @property
    def current(self) -> dict[str, np.memmap]:
        return self.state_a if self.current_slot == "a" else self.state_b

    @property
    def inactive(self) -> dict[str, np.memmap]:
        return self.state_b if self.current_slot == "a" else self.state_a

    def summary(self) -> dict[str, int | float]:
        usos = self.current["usos"]
        alt2 = self.current["alt2"]
        return {
            "mangrove": int(np.count_nonzero(usos == MANGUE)),
            "vegetation": int(np.count_nonzero(usos == VEGETACAO_TERRESTRE)),
            "sea": int(np.count_nonzero(usos == MAR)),
            "anthropized": int(np.count_nonzero(usos == AREA_ANTROPIZADA)),
            "bare": int(np.count_nonzero(usos == SOLO_DESCOBERTO)),
            "flooded_bare": int(np.count_nonzero(usos == SOLO_DESCOBERTO_INUNDADO)),
            "flooded_anthropized": int(np.count_nonzero(usos == AREA_ANTROPIZADA_INUNDADO)),
            "migrated_mangrove": int(np.count_nonzero(usos == MANGUE_MIGRADO)),
            "flooded_mangrove": int(np.count_nonzero(usos == MANGUE_INUNDADO)),
            "flooded_natural": int(np.count_nonzero(usos == VEGETACAO_TERRESTRE_INUNDADO)),
            "min_alt2": float(np.nanmin(alt2)),
            "max_alt2": float(np.nanmax(alt2)),
        }

    @staticmethod
    def _apply_flooding(current_usos: np.memmap, past_usos: np.memmap, index: int) -> None:
        previous = int(past_usos[index])
        current_usos[index] = {
            MANGUE: MANGUE_INUNDADO,
            VEGETACAO_TERRESTRE: VEGETACAO_TERRESTRE_INUNDADO,
            AREA_ANTROPIZADA: AREA_ANTROPIZADA_INUNDADO,
            SOLO_DESCOBERTO: SOLO_DESCOBERTO_INUNDADO,
        }.get(previous, int(current_usos[index]))

    def step(self, time_index: int, parameters: ModelParameters) -> dict[str, int | float]:
        """Executa um passo, mantendo apenas os arrays persistentes e um bloco.

        Os dois estados alternados implementam a fotografia ``past``. O estado
        inativo começa como cópia do estado anterior e recebe as atualizações
        correntes. Os blocos são percorridos na ordem original das células.
        """
        past = self.current
        current = self.inactive
        for name in STATE_DTYPES:
            np.copyto(current[name], past[name])

        nmrm = time_index * parameters.sea_level_rise_rate
        nmrm_m = nmrm * 1000
        accretion_rate_mm = (
            parameters.accretion_rate_mm
            if parameters.accretion_rate_mm is not None
            else 1.693 + (0.939 * nmrm_m)
        )
        accretion_rate_m = accretion_rate_mm / 1000
        tidal_influence_zone = parameters.tide_height + nmrm

        past_usos = past["usos"]
        past_alt2 = past["alt2"]
        usos = current["usos"]
        alt2 = current["alt2"]
        solos = current["classe_solos"]

        for start in range(0, self.n_cells, self.block_size):
            stop = min(start + self.block_size, self.n_cells)
            for index in range(start, stop):
                if is_sea_or_flooded(int(past_usos[index])) and past_alt2[index] >= 0:
                    lower: list[int] = []
                    for neighbor in self.neighbors[index]:
                        if neighbor >= 0 and past_alt2[neighbor] < past_alt2[index]:
                            lower.append(int(neighbor))
                    neighbor_count = 1 + len(lower)
                    flow = parameters.sea_level_rise_rate / neighbor_count
                    alt2[index] += flow
                    for neighbor in lower:
                        alt2[neighbor] += flow
                        if not is_sea_or_flooded(int(past_usos[neighbor])):
                            self._apply_flooding(usos, past_usos, neighbor)

                if int(solos[index]) in (SOLO_MANGUE, CANAL_FLUVIAL):
                    for neighbor in self.neighbors[index]:
                        if neighbor >= 0 and (
                            int(usos[neighbor]) in (VEGETACAO_TERRESTRE, SOLO_DESCOBERTO)
                            and int(solos[neighbor]) != SOLO_MANGUE
                            and alt2[neighbor] <= tidal_influence_zone
                        ):
                            solos[neighbor] = SOLO_MANGUE_MIGRADO

                if int(usos[index]) == MANGUE:
                    for neighbor in self.neighbors[index]:
                        if neighbor >= 0 and (
                            int(usos[neighbor]) in (VEGETACAO_TERRESTRE, SOLO_DESCOBERTO)
                            and alt2[neighbor] <= tidal_influence_zone
                            and (
                                parameters.allow_migration_without_soil
                                or int(solos[neighbor])
                                in (SOLO_MANGUE_MIGRADO, SOLO_MANGUE)
                            )
                        ):
                            usos[neighbor] = MANGUE_MIGRADO

                migrated_soil = (
                    not parameters.legacy_lua_accretion_typo
                    and int(solos[index]) == SOLO_MANGUE_MIGRADO
                )
                if (int(solos[index]) == SOLO_MANGUE) or (
                    migrated_soil and not is_sea_or_flooded(int(usos[index]))
                ):
                    alt2[index] += accretion_rate_m

        current["usos"].flush()
        current["alt2"].flush()
        current["classe_solos"].flush()
        self.current_slot = "b" if self.current_slot == "a" else "a"
        self.years_completed += 1
        return self.summary()

    def run(self, parameters: ModelParameters) -> pd.DataFrame:
        started = time.perf_counter()
        process = psutil.Process() if psutil is not None else None
        self.rss_before_bytes = process.memory_info().rss if process else None
        self.peak_rss_bytes = self.rss_before_bytes or 0
        rows: list[dict[str, int | float]] = []
        for time_index in range(parameters.start, parameters.final_time + 1):
            row = {"year": time_index, **self.step(time_index, parameters)}
            rows.append(row)
            if process is not None:
                self.peak_rss_bytes = max(
                    self.peak_rss_bytes, process.memory_info().rss
                )
        self.elapsed_seconds = time.perf_counter() - started
        return pd.DataFrame(rows)

    def close(self) -> None:
        self.neighbors.flush()
        for state in (self.state_a, self.state_b):
            for array in state.values():
                array.flush()


def run_persistent_shapefile(
    input_path: str | Path,
    output_dir: str | Path,
    parameters: ModelParameters,
    *,
    block_size: int = 10_000,
    strict_lua_schema: bool = False,
) -> pd.DataFrame:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace = output_dir / "workspace"
    runner = PersistentBlockRunner.create_from_shapefile(
        input_path,
        workspace,
        block_size=block_size,
        strict_lua_schema=strict_lua_schema,
    )
    try:
        trajectory = runner.run(parameters)
        trajectory.to_csv(output_dir / "trajectory.csv", index=False)
        metadata = json.loads((workspace / "metadata.json").read_text(encoding="utf-8"))
        metadata.update(
            {
                "processing_mode": "blocks_persistent",
                "final_time": parameters.final_time,
                "parameters": {
                    "start": parameters.start,
                    "final_time": parameters.final_time,
                    "area_cell": parameters.area_cell,
                    "tide_height": parameters.tide_height,
                    "sea_level_rise_rate": parameters.sea_level_rise_rate,
                    "legacy_lua_accretion_typo": parameters.legacy_lua_accretion_typo,
                    "allow_migration_without_soil": parameters.allow_migration_without_soil,
                    "accretion_rate_mm": parameters.accretion_rate_mm,
                },
                "elapsed_seconds": getattr(runner, "elapsed_seconds", None),
                "rss_before_bytes": getattr(runner, "rss_before_bytes", None),
                "peak_rss_bytes": getattr(runner, "peak_rss_bytes", None),
            }
        )
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return trajectory
    finally:
        runner.close()
