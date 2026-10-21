"""State-map exports with a separate, measured legend area."""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
import textwrap
from typing import Any

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window

from .localization import translate


def state_colormap(catalog: dict[str, Any]) -> tuple[ListedColormap, BoundaryNorm]:
    colors = {0: "#ffffff"}
    colors.update({int(code): str(item.get("color", "#b8c2cc"))
                   for code, item in catalog.get("states", {}).items()})
    highest = max(colors)
    cmap = ListedColormap([colors.get(code, "#b8c2cc") for code in range(highest + 1)])
    return cmap, BoundaryNorm(np.arange(-0.5, highest + 1.5, 1), cmap.N)


def state_display_name(item: dict[str, Any], language: str) -> str:
    name = str(item.get("name", "Class"))
    translated = translate(name, language)
    if translated == name and language == "pt-BR" and item.get("kind") == "flooded" and name.startswith("Flooded "):
        return translate("Flooded area: {name}", language).format(name=translate(name[8:], language))
    return translated


def preview_geometry(profile: dict[str, Any], bounds: tuple[int, int, int, int]) -> dict[str, Any]:
    r0, r1, c0, c1 = bounds
    transform = profile.get("transform")
    crs = profile.get("crs")
    if transform is not None and crs is not None and transform.b == 0 and transform.d == 0:
        x0, y0 = transform * (c0, r0)
        x1, y1 = transform * (c1, r1)
        if crs.is_projected:
            factor = float(crs.linear_units_factor[1]) / 1000
            return {"extent": (x0 * factor, x1 * factor, y1 * factor, y0 * factor),
                    "xlabel": "Easting (km)", "ylabel": "Northing (km)"}
        if crs.is_geographic:
            return {"extent": (x0, x1, y1, y0), "xlabel": "Longitude", "ylabel": "Latitude"}
    return {"extent": (c0 - 0.5, c1 - 0.5, r1 - 0.5, r0 - 0.5),
            "xlabel": "Raster columns", "ylabel": "Raster rows"}


def read_state_preview(path: Path, grid: dict[str, Any], max_side: int = 1400) -> tuple[np.ndarray, dict[str, Any]]:
    """Read a display-sized raster without materializing the simulation grid."""
    with rasterio.open(path) as source:
        r0 = max(0, int(grid.get("valid_row_min", 0)) - 10)
        r1 = min(source.height, int(grid.get("valid_row_max", source.height - 1)) + 11)
        c0 = max(0, int(grid.get("valid_col_min", 0)) - 10)
        c1 = min(source.width, int(grid.get("valid_col_max", source.width - 1)) + 11)
        ratio = min(1.0, max_side / max(r1 - r0, c1 - c0))
        shape = (max(1, round((r1 - r0) * ratio)), max(1, round((c1 - c0) * ratio)))
        image = source.read(1, window=Window(c0, r0, c1 - c0, r1 - r0),
                            out_shape=shape, resampling=Resampling.nearest)
        geometry = preview_geometry(source.profile, (r0, r1, c0, c1))
    return image, geometry


@lru_cache(maxsize=128)
def _legend_layout(entries: tuple[tuple[int, str, str], ...], title: str) -> tuple[int, tuple[str, ...], float]:
    columns = 1 if len(entries) <= 4 else 2 if len(entries) <= 12 else 3
    wrap = 52 if columns == 1 else 38 if columns == 2 else 28
    for _ in range(12):
        labels = tuple(textwrap.fill(name, width=wrap, break_long_words=True,
                                     break_on_hyphens=False) for _, name, _ in entries)
        figure = Figure(figsize=(10.4, 2), dpi=100)
        canvas = FigureCanvasAgg(figure)
        legend = figure.legend(handles=[Patch(facecolor=color, label=label)
                                       for (_, _, color), label in zip(entries, labels)],
                               loc="upper center", ncol=columns, fontsize=8.5,
                               title=title, title_fontsize=10, frameon=False,
                               borderaxespad=0, columnspacing=1.5, labelspacing=0.6)
        canvas.draw()
        box = legend.get_window_extent(canvas.get_renderer())
        width, height = box.width / 100, box.height / 100
        if width <= 9.8:
            return columns, labels, height
        wrap = max(8, wrap - 4)
    raise ValueError("The state legend cannot fit the output width.")


def save_state_map(image: np.ndarray, catalog: dict[str, Any], year: int,
                   destination: Path, *, language: str = "en",
                   present_codes: set[int] | None = None,
                   geometry: dict[str, Any] | None = None) -> dict[str, Any]:
    """Keep the complete visible legend outside the map and its coordinate labels."""
    if present_codes is None:
        present_codes = {int(code) for code in np.unique(image) if int(code) != 0}
    entries = [(int(code), state_display_name(item, language), str(item.get("color", "#b8c2cc")))
               for code, item in sorted(catalog.get("states", {}).items(), key=lambda pair: int(pair[0]))
               if int(code) in present_codes]
    duplicates = Counter(name for _, name, _ in entries)
    entries = tuple((code, name if duplicates[name] == 1 else f"{name} [{code}]", color)
                    for code, name, color in entries)
    title = translate("Model states", language)
    columns, labels, legend_height = _legend_layout(entries, title) if entries else (1, (), 0)
    width, map_height, gap, bottom, top = 10.4, 6.0, 0.65, 0.18, 0.42
    height = top + map_height + gap + legend_height + bottom
    figure = Figure(figsize=(width, height), dpi=150, facecolor="white")
    axis = figure.add_axes((0.72 / width, (bottom + legend_height + gap) / height,
                            (width - 1.0) / width, map_height / height))
    cmap, norm = state_colormap(catalog)
    geometry = geometry or {"xlabel": "Raster columns", "ylabel": "Raster rows"}
    axis.imshow(image, cmap=cmap, norm=norm, interpolation="nearest", extent=geometry.get("extent"))
    axis.set_title(str(year), loc="right", fontsize=12, fontweight="bold", pad=8)
    axis.set_xlabel(translate(geometry["xlabel"], language))
    axis.set_ylabel(translate(geometry["ylabel"], language))
    axis.tick_params(labelsize=9)
    axis.ticklabel_format(axis="both", style="plain", useOffset=False)
    legend = None
    if entries:
        legend = figure.legend(handles=[Patch(facecolor=color, label=label)
                                       for (_, _, color), label in zip(entries, labels)],
                               loc="upper center", bbox_to_anchor=(0.5, (bottom + legend_height) / height),
                               ncol=columns, fontsize=8.5, title=title, title_fontsize=10,
                               frameon=False, borderaxespad=0, columnspacing=1.5, labelspacing=0.6)
    canvas = FigureCanvasAgg(figure)
    canvas.draw()
    renderer = canvas.get_renderer()
    map_box = axis.get_tightbbox(renderer)
    legend_box = legend.get_window_extent(renderer) if legend is not None else None
    if legend_box is not None and legend_box.y1 > map_box.y0:
        raise ValueError("The state legend overlaps the map labels.")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_figure(destination, dpi=150)
    return {"year": int(year), "catalog_states": len(catalog.get("states", {})),
            "legend_states": len(entries), "legend_codes": [code for code, _, _ in entries],
            "map_bbox_pixels": list(map_box.bounds),
            "legend_bbox_pixels": list(legend_box.bounds) if legend_box is not None else None,
            "legend_overlaps_map": False, "image_pixels": list(canvas.get_width_height())}
