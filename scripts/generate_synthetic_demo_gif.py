"""Generate the compact model animation used on the project website."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import PillowWriter
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np

from brmangue_lua.engine import BrMangueGrid, ModelParameters, SOIL_PROFILE_CODES, _build_moore_neighbors
from brmangue_lua.model_states import build_model_state_catalog


def build_grid() -> BrMangueGrid:
    """Create a 28 by 18 coastal grid with five configurable classes."""
    row_count, column_count = 18, 28
    classes = [
        {"code": 101, "name": "Mangrove", "behavior": "mangrove", "color": "#0b7a3b"},
        {"code": 205, "name": "Natural vegetation", "behavior": "natural_vegetation", "color": "#a9db82"},
        {"code": 309, "name": "Water", "behavior": "water", "color": "#2f91bd"},
        {"code": 412, "name": "Anthropized / blocked", "behavior": "anthropized", "color": "#f2a65a"},
        {"code": 518, "name": "Bare soil", "behavior": "bare_soil", "color": "#e9c46a"},
    ]
    catalog = build_model_state_catalog(classes)
    state_by_behavior = {item["behavior"]: item["code"] for item in classes}
    state = np.full((row_count, column_count), state_by_behavior["natural_vegetation"], dtype=np.uint16)
    state[:2, :] = state_by_behavior["water"]
    state[2, :5] = state_by_behavior["water"]
    state[2, 22:] = state_by_behavior["water"]
    state[2:5, 5:22] = state_by_behavior["mangrove"]
    state[3, 20:22] = state_by_behavior["anthropized"]
    state[5:9, 3:8] = state_by_behavior["bare_soil"]
    state[8:13, 21:27] = state_by_behavior["anthropized"]
    state[13:, :4] = state_by_behavior["anthropized"]

    elevation = np.zeros((row_count, column_count), dtype=np.float64)
    for row in range(row_count):
        elevation[row, :] = 1.0 + (row * 0.34)
    elevation[:2, :] = 2.0
    elevation[2, :] = 1.75
    elevation[3, :] = 1.45
    elevation[4, :] = 1.25

    soil_class = np.full((row_count, column_count), 2, dtype=np.int16)
    soil_class[state == state_by_behavior["water"]] = SOIL_PROFILE_CODES["channel"]
    soil_class[state == state_by_behavior["mangrove"]] = SOIL_PROFILE_CODES["mangrove_soil"]
    row, column = np.indices((row_count, column_count))
    flat_row = row.ravel()
    flat_column = column.ravel()
    return BrMangueGrid(
        land_cover_state=state.ravel(),
        relative_elevation=elevation.ravel(),
        soil_class=soil_class.ravel(),
        column=flat_column,
        row=flat_row,
        neighbors=_build_moore_neighbors(flat_column, flat_row),
        source_path="synthetic_demo_28x18",
        model_state_catalog=catalog,
    )


def run_states(grid: BrMangueGrid, years: int = 10) -> tuple[list[np.ndarray], list[int]]:
    """Run the model rules and retain each annual state."""
    parameters = ModelParameters(
        start=1,
        final_time=years,
        tide_height=1.55,
        sea_level_rise_rate=0.16,
        accretion_rate_mm=0.0,
        allow_migration_without_soil=False,
        legacy_lua_accretion_typo=True,
    )
    states = [grid.land_cover_state.copy()]
    years_out = [2024]
    for time_index in range(parameters.start, parameters.final_time + 1):
        grid.step(time_index, parameters)
        states.append(grid.land_cover_state.copy())
        years_out.append(2024 + time_index)
    return states, years_out


def write_gif(destination: Path) -> None:
    grid = build_grid()
    states, years = run_states(grid)
    destination.parent.mkdir(parents=True, exist_ok=True)
    catalog = grid.model_state_catalog
    state_entries = catalog["states"]
    highest_code = max(int(code) for code in state_entries)
    colors = ["#ffffff"] + ["#b8c2cc"] * highest_code
    for raw_code, item in state_entries.items():
        colors[int(raw_code)] = str(item["color"])
    labels = {int(code): str(item["name"]) for code, item in state_entries.items()}
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(np.arange(-0.5, highest_code + 1.5, 1), cmap.N)

    fig, ax = plt.subplots(figsize=(8.6, 5.8), dpi=120)
    fig.patch.set_facecolor("#f7fcfc")
    ax.set_facecolor("#f7fcfc")
    writer = PillowWriter(fps=1.4)
    with writer.saving(fig, str(destination), dpi=120):
        for state, year in zip(states, years):
            ax.clear()
            ax.imshow(state.reshape(18, 28), cmap=cmap, norm=norm, interpolation="none", aspect="equal")
            ax.set_xticks(np.arange(-.5, 28, 1), minor=True)
            ax.set_yticks(np.arange(-.5, 18, 1), minor=True)
            ax.grid(which="minor", color="#ffffff", linewidth=.65, alpha=.78)
            ax.tick_params(which="both", bottom=False, left=False, labelbottom=False, labelleft=False)
            for spine in ax.spines.values():
                spine.set_color("#b7d4d6")
                spine.set_linewidth(1.2)
            active_codes = [int(code) for code in np.unique(state) if int(code) in labels]
            ax.set_title("BR-MANGUE Studio · annual cellular transition", loc="left", pad=15, color="#16425a", fontsize=15, fontweight="bold")
            ax.text(1.0, 1.02, f"Year {year}", transform=ax.transAxes, ha="right", va="bottom", color="#167d87", fontsize=13, fontweight="bold")
            ax.text(0.01, -0.075, f"{state.size:,} cells · {len(active_codes)} active states", transform=ax.transAxes, ha="left", va="top", color="#5b7b86", fontsize=8.5)
            handles = [
                plt.Line2D([0], [0], marker="s", linestyle="", markersize=8, markerfacecolor=colors[code], markeredgecolor="none", label=labels[code])
                for code in active_codes
            ]
            ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, -.11), ncol=3, frameon=False, fontsize=7.2, handletextpad=.35, columnspacing=1.3)
            fig.tight_layout(pad=1.3)
            writer.grab_frame()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    write_gif(root / "docs" / "assets" / "synthetic_transition.gif")
