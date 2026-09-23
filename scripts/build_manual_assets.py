"""Prepare figures and interface captures for the BR-MANGUE user manual."""

from __future__ import annotations

from pathlib import Path
import shutil

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import FancyArrowPatch, Rectangle
import numpy as np
import pandas as pd
from PIL import Image
import rasterio


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "tmp" / "pdfs" / "brmangue_manual_assets"
ASSETS.mkdir(parents=True, exist_ok=True)
RUN = ROOT / "outputs" / "site_island_real_demo_50steps_60x60" / "run_2025_2075_updated"

GREEN = "#087a3b"
NATURAL = "#a9d982"
WATER = "#2f91bd"
ORANGE = "#f2a65a"
PURPLE = "#7b3f98"
RED = "#e5483f"
MUTED = "#5b7480"


def copy_interface_captures() -> None:
    source_dir = Path(r"C:\Users\felly\AppData\Local\Temp")
    captures = {
        "ui_project_visualization.png": "codex-clipboard-9da5154b-273a-4a9a-8892-edfc62ac4132.png",
        "ui_simulation_parameters.png": "codex-clipboard-d2e3c5bd-4606-40e2-ba09-666bcff560d8.png",
        "ui_class_mapping.png": "codex-clipboard-66b75eeb-fbda-48cc-92f3-f3397d84b773.png",
        "ui_crs.png": "codex-clipboard-0ec45982-7a0c-4626-b963-3d7a5595a0bc.png",
        "ui_animation_panels.png": "codex-clipboard-3d00948c-18c4-4045-aca8-6ca64c580746.png",
        "ui_net_change.png": "codex-clipboard-840677b8-089a-4847-99b4-1797509380ff.png",
        "ui_trajectory.png": "codex-clipboard-d766e2e6-b6c0-462b-b179-9896abf14dbb.png",
    }
    for destination, name in captures.items():
        source = source_dir / name
        if source.exists():
            shutil.copy2(source, ASSETS / destination)


def copy_logo() -> None:
    source = ROOT / "docs" / "assets" / "BR-MANGUE_STUDIO_preview_original.png"
    if not source.exists():
        return
    with Image.open(source).convert("RGBA") as image:
        background = Image.new("RGBA", image.size, "white")
        diff = Image.alpha_composite(background, image)
        bbox = diff.convert("RGB").point(lambda p: 0 if p < 244 else 255).getbbox()
        if bbox:
            image.crop(bbox).save(ASSETS / "logo_cropped.png")
        else:
            image.save(ASSETS / "logo_cropped.png")


def make_neighborhood() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.3), dpi=170)
    ax.set_xlim(-3.2, 3.2)
    ax.set_ylim(-2.4, 2.4)
    ax.axis("off")
    for y in range(-1, 2):
        for x in range(-1, 2):
            if x == 0 and y == 0:
                color, label = GREEN, "cell"
            else:
                color, label = NATURAL, "neighbour"
            ax.add_patch(Rectangle((x - .43, y - .43), .86, .86, facecolor=color, edgecolor="#ffffff", linewidth=2.2))
            ax.text(x, y, label if x == 0 and y == 0 else "", ha="center", va="center", fontsize=10, color="white", weight="bold")
    for y in range(-1, 2):
        for x in range(-1, 2):
            if (x, y) != (0, 0):
                ax.add_patch(FancyArrowPatch((x * .65, y * .65), (x * .28, y * .28), arrowstyle="-", linewidth=1, color="#4f8f78", alpha=.65))
    ax.text(0, -1.65, "Vizinhança de Moore: a célula central consulta até oito vizinhas", ha="center", color="#16425a", fontsize=12, weight="bold")
    fig.tight_layout(pad=.3)
    fig.savefig(ASSETS / "moore_neighborhood.png", transparent=False, facecolor="#f7fbf8", bbox_inches="tight")
    plt.close(fig)


def make_results() -> None:
    trajectory = pd.read_csv(RUN / "trajectory.csv")
    years = trajectory["calendar_year"].astype(int).to_numpy()

    fig, ax = plt.subplots(figsize=(8.8, 4.8), dpi=160)
    ax.plot(years, trajectory["mangrove"], color=GREEN, linewidth=2.8, label="Mangrove")
    ax.plot(years, trajectory["migrated_mangrove"], color=PURPLE, linewidth=2.2, label="Migrated mangrove")
    ax.plot(years, trajectory["flooded_mangrove"], color=RED, linewidth=2.2, label="Flooded mangrove")
    ax.set_title("Mangrove trajectory - real 60 × 60 Ilha do Maranhão cutout", color="#16425a", weight="bold")
    ax.set_xlabel("Calendar year")
    ax.set_ylabel("Cells")
    ax.grid(alpha=.22)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(.5, -.17))
    fig.tight_layout()
    fig.savefig(ASSETS / "real_trajectory.png", facecolor="white", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.8, 4.2), dpi=160)
    if "annual_net_change" in trajectory:
        net_change = trajectory["annual_net_change"].fillna(0).to_numpy()
    else:
        gain = trajectory.get("annual_gain", pd.Series(np.zeros(len(trajectory)))).to_numpy()
        loss = trajectory.get("annual_loss", pd.Series(np.zeros(len(trajectory)))).to_numpy()
        net_change = gain - loss
    ax.bar(years, np.maximum(net_change, 0), color="#72b66b", width=.78, label="Net annual gain")
    ax.bar(years, np.minimum(net_change, 0), color="#ef3b2c", width=.78, label="Net annual loss")
    ax.axhline(0, color="#33434a", linewidth=.8)
    ax.set_title("Annual mangrove change", color="#16425a", weight="bold")
    ax.set_xlabel("Calendar year")
    ax.set_ylabel("Net annual change (cells)")
    ax.grid(alpha=.18, axis="y")
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(.5, -.17))
    fig.tight_layout()
    fig.savefig(ASSETS / "real_annual_change.png", facecolor="white", bbox_inches="tight")
    plt.close(fig)

    colors = ["#00000000", GREEN, NATURAL, WATER, ORANGE, ORANGE, "#d98b4b", "#d97745", PURPLE, RED, "#5e9d5a"]
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(np.arange(-.5, 10.5, 1), cmap.N)
    paths = [RUN / "initial_usos_2025.tif", RUN / "states" / "usos_2075.tif"]
    labels = ["Initial state · 2025", "Final state · 2075"]
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 4.6), dpi=160)
    for ax, path, label in zip(axes, paths, labels):
        with rasterio.open(path) as src:
            arr = src.read(1)
        ax.imshow(arr, cmap=cmap, norm=norm, interpolation="nearest")
        ax.set_title(label, color="#16425a", weight="bold")
        ax.set_xlabel("Raster columns")
        ax.set_ylabel("Raster rows")
    fig.suptitle("Real model states - 3,600 cells at 30 m", color="#16425a", weight="bold", y=.99)
    fig.tight_layout()
    fig.savefig(ASSETS / "real_initial_final_maps.png", facecolor="white", bbox_inches="tight")
    plt.close(fig)

    dem_path = RUN.parent / "ilha_maranhao_anadem_30m_cutout.tif"
    with rasterio.open(dem_path) as src:
        dem = src.read(1)
    fig, ax = plt.subplots(figsize=(7.8, 4.8), dpi=160)
    image = ax.imshow(dem, cmap="terrain", interpolation="nearest")
    fig.colorbar(image, ax=ax, fraction=.046, pad=.04, label="Elevation (m)")
    ax.set_title("ANADEM digital terrain model - same cutout", color="#16425a", weight="bold")
    ax.set_xlabel("Raster columns")
    ax.set_ylabel("Raster rows")
    fig.tight_layout()
    fig.savefig(ASSETS / "real_dem_cutout.png", facecolor="white", bbox_inches="tight")
    plt.close(fig)

    gif_path = ROOT / "docs" / "assets" / "BR-MANGUE_island-real-transition-50steps.gif"
    if gif_path.exists():
        with Image.open(gif_path) as gif:
            gif.seek(0)
            gif.convert("RGB").save(ASSETS / "real_gif_first_frame.png")
            gif.seek(gif.n_frames - 1)
            gif.convert("RGB").save(ASSETS / "real_gif_last_frame.png")


def main() -> None:
    copy_interface_captures()
    copy_logo()
    make_neighborhood()
    make_results()
    print(ASSETS)


if __name__ == "__main__":
    main()
