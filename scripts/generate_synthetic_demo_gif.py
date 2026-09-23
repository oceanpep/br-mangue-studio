"""Generate the small, real-model animation used on the project website.

The grid is intentionally compact so that visitors can see individual cells.
It includes the five source land-cover classes and the transition rules can
create migrated and flooded states during the short run.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import PillowWriter
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np

from brmangue_lua.engine import (
    AREA_ANTROPIZADA,
    MAR,
    MANGUE,
    ModelParameters,
    SOLO_DESCOBERTO,
    SOLO_MANGUE,
    VEGETACAO_TERRESTRE,
    BrMangueGrid,
    _build_moore_neighbors,
)


def build_grid() -> BrMangueGrid:
    """Create a 28 x 18 coastal grid with all five source classes."""
    rows, cols = 18, 28
    usos = np.full((rows, cols), VEGETACAO_TERRESTRE, dtype=np.int64)

    # Water channel and tidal edge.
    usos[:2, :] = MAR
    usos[2, :5] = MAR
    usos[2, 22:] = MAR

    # A mangrove fringe, an exposed sand/mud flat, and an inland settlement.
    usos[2:5, 5:22] = MANGUE
    usos[3, 20:22] = AREA_ANTROPIZADA  # low-lying built cells that can flood
    usos[5:9, 3:8] = SOLO_DESCOBERTO
    usos[8:13, 21:27] = AREA_ANTROPIZADA
    usos[13:, :4] = AREA_ANTROPIZADA

    # Elevation decreases toward the water. The stepped values make flooding
    # visible while leaving higher cells available for migration.
    alt2 = np.zeros((rows, cols), dtype=np.float64)
    for row in range(rows):
        alt2[row, :] = 1.0 + (row * 0.34)
    alt2[:2, :] = 2.0
    alt2[2, :] = 1.75
    alt2[3, :] = 1.45
    alt2[4, :] = 1.25

    # Mangrove soil at the fringe; other cells start as non-mangrove soil.
    classe_solos = np.ones((rows, cols), dtype=np.int64)
    classe_solos[2:5, 5:22] = SOLO_MANGUE

    lin, col = np.indices((rows, cols))
    lin = lin.ravel()
    col = col.ravel()
    return BrMangueGrid(
        usos=usos.ravel(),
        alt2=alt2.ravel(),
        classe_solos=classe_solos.ravel(),
        col=col,
        lin=lin,
        neighbors=_build_moore_neighbors(col, lin),
        source_path="synthetic_demo_28x18",
    )


def run_states(grid: BrMangueGrid, years: int = 10) -> tuple[list[np.ndarray], list[int]]:
    """Run the actual Python cellular rules and retain each annual state."""
    parameters = ModelParameters(
        start=1,
        final_time=years,
        tide_height=1.55,
        sea_level_rise_rate=0.16,
        accretion_rate_mm=0.0,
        allow_migration_without_soil=False,
        legacy_lua_accretion_typo=True,
    )
    states = [grid.usos.copy()]
    years_out = [2024]
    for time in range(parameters.start, parameters.final_time + 1):
        grid.step(time, parameters)
        states.append(grid.usos.copy())
        years_out.append(2024 + time)
    return states, years_out


def write_gif(destination: Path) -> None:
    grid = build_grid()
    states, years = run_states(grid)
    destination.parent.mkdir(parents=True, exist_ok=True)

    colors = [
        "#0b7a3b",  # mangrove
        "#a9db82",  # natural vegetation
        "#2f91bd",  # water
        "#f2a65a",  # anthropized / blocked
        "#e9c46a",  # bare soil
        "#d98b4b",  # flooded bare soil
        "#d97745",  # flooded anthropized
        "#7e3f98",  # migrated mangrove
        "#e84c3d",  # flooded mangrove
        "#5e9d5a",  # flooded natural vegetation
    ]
    labels = [
        "Mangrove", "Natural vegetation", "Water", "Anthropized / blocked",
        "Bare soil", "Flooded bare soil", "Flooded anthropized",
        "Migrated mangrove", "Flooded mangrove", "Flooded natural vegetation",
    ]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(np.arange(0.5, 10.5, 1), cmap.N)

    fig, ax = plt.subplots(figsize=(8.6, 5.8), dpi=120)
    fig.patch.set_facecolor("#f7fcfc")
    ax.set_facecolor("#f7fcfc")
    writer = PillowWriter(fps=1.4)
    with writer.saving(fig, str(destination), dpi=120):
        for state, year in zip(states, years):
            ax.clear()
            image = ax.imshow(
                state.reshape(18, 28), cmap=cmap, norm=norm,
                interpolation="none", aspect="equal",
            )
            ax.set_xticks(np.arange(-.5, 28, 1), minor=True)
            ax.set_yticks(np.arange(-.5, 18, 1), minor=True)
            ax.grid(which="minor", color="#ffffff", linewidth=.65, alpha=.78)
            ax.tick_params(which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
            for spine in ax.spines.values():
                spine.set_color("#b7d4d6")
                spine.set_linewidth(1.2)
            counts = {label: int(np.count_nonzero(state == code)) for code, label in enumerate(labels, 1)}
            active = [label for label in labels if counts[label] > 0]
            ax.set_title("BR-MANGUE Studio · annual cellular transition", loc="left", pad=15, color="#16425a", fontsize=15, fontweight="bold")
            ax.text(1.0, 1.02, f"Year {year}", transform=ax.transAxes, ha="right", va="bottom", color="#167d87", fontsize=13, fontweight="bold")
            ax.text(0.01, -0.075, f"{state.size:,} cells · {len(active)} active states", transform=ax.transAxes, ha="left", va="top", color="#5b7b86", fontsize=8.5)
            handles = [plt.Line2D([0], [0], marker="s", linestyle="", markersize=8, markerfacecolor=colors[i], markeredgecolor="none", label=labels[i]) for i in range(len(labels)) if labels[i] in active]
            ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, -.11), ncol=3, frameon=False, fontsize=7.2, handletextpad=.35, columnspacing=1.3)
            fig.tight_layout(pad=1.3)
            writer.grab_frame()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    write_gif(root / "docs" / "assets" / "BR-MANGUE_synthetic-cellular-transition.gif")
