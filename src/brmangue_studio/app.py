"""BR-MANGUE Studio desktop application.

The interface builds projects from user-selected GeoTIFFs and calls the
public functions in ``brmangue_lua``. Input rasters remain unchanged; all
products are written to the project's results folder.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from PIL import Image, ImageTk
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import calculate_default_transform
from rasterio.windows import Window

try:
    from pyproj.database import query_crs_info
except ImportError:  # pragma: no cover - available in source and packaged builds
    query_crs_info = None

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

from brmangue_lua.engine import ModelParameters
from brmangue_lua.sea_level import TRAJECTORY_CSV_EXAMPLE, SeaLevelTrajectory, trajectory_from_project
from brmangue_lua.model_states import STANDARD_CLASS_STYLES, state_entry
from brmangue_lua.raster_inputs import (
    DEFAULT_LAND_COVER_MAPPING,
    MAX_CUSTOM_MODEL_CLASS_CODE,
    RasterInputSet,
    load_raster_inputs,
    normalize_custom_model_classes,
)
from brmangue_lua.raster_runner import run_raster_simulation
from brmangue_studio.localization import (
    LANGUAGES,
    LANGUAGE_CODES,
    CODE_TO_LANGUAGE,
    load_language,
    save_language,
    translate,
    translate_runtime,
)

try:
    from brmangue_lua.dissmodel_adapter import DISSMODEL_AVAILABLE
except ImportError:  # pragma: no cover - used by the compact frozen build
    DISSMODEL_AVAILABLE = False


ROLE_LABELS = [
    "Exclude",
    "Mangrove",
    "Natural vegetation",
    "Water",
    "Anthropized / blocked",
]
UNASSIGNED_ROLE = "Unassigned"
ROLE_TO_MODEL = {
    "Mangrove": "mangrove",
    "Natural vegetation": "natural_accommodation_candidate",
    "Water": "water",
    "Anthropized / blocked": "managed_land_use_candidate",
}
TRANSITION_REPORT_CHUNK_CELLS = 1_000_000
CUSTOM_BEHAVIOR_LABELS = {
    "fixed": "Fixed class",
    "mangrove": "Mangrove source",
    "natural_vegetation": "Natural vegetation",
    "bare_soil": "Bare soil",
    "anthropized": "Anthropized area",
    "water": "Water body",
}
CHART_BEHAVIOR_COLORS = {
    "mangrove": STANDARD_CLASS_STYLES["mangrove"][1],
    "migrated_mangrove": "#7b3294",
    "flooded_mangrove": "#e34a33",
    "natural_vegetation": STANDARD_CLASS_STYLES["natural_vegetation"][1],
    "water": STANDARD_CLASS_STYLES["water"][1],
    "anthropized": STANDARD_CLASS_STYLES["anthropized"][1],
}
DEFAULT_CUSTOM_COLORS = (
    "#8c6bb1", "#d95f0e", "#1b9e77", "#e7298a", "#7570b3", "#66a61e",
    "#e6ab02", "#a6761d", "#1f78b4", "#b15928", "#6a3d9a", "#b2df8a",
)
FIGURE_COMPONENTS = ("state", "elevation", "trajectory", "change")
FIGURE_COMPONENT_LABELS = {
    "state": "Cell state",
    "elevation": "Elevation / relative surface",
    "trajectory": "Mangrove trajectory",
    "change": "Net annual change",
}


def _model_colormap(state_catalog: dict[str, Any] | None = None) -> tuple[ListedColormap, BoundaryNorm]:
    """Build a discrete palette from the active project's state catalog."""
    colors = {0: "#ffffff"}
    for raw_code, item in (state_catalog or {}).get("states", {}).items():
        try:
            colors[int(raw_code)] = str(item["color"])
        except (KeyError, TypeError, ValueError):
            continue
    highest_code = max(colors)
    palette = ListedColormap(
        [colors.get(code, "#b8c2cc") for code in range(highest_code + 1)]
    )
    norm = BoundaryNorm(np.arange(-0.5, highest_code + 1.5, 1), palette.N)
    return palette, norm


def _model_legend_handles(
    state_catalog: dict[str, Any] | None = None,
    language_code: str = "en",
) -> list[Patch]:
    """Create legend entries for every class and derived state in the catalog."""
    states = (state_catalog or {}).get("states", {})
    if states:
        return [
            Patch(facecolor=str(item.get("color", "#b8c2cc")), label=translate(str(item.get("name", "Class")), language_code))
            for _code, item in sorted(states.items(), key=lambda pair: int(pair[0]))
        ]
    return [
        Patch(facecolor=color, label=translate(name, language_code))
        for name, color in (value for value in STANDARD_CLASS_STYLES.values())
    ]

APP_VERSION = "1.4.0"
APP_COPYRIGHT = "Copyright © 2026 BR-MANGUE Project"
SPLASH_DURATION_MS = 4000
UI_COLORS = {
    "window": "#f3f8fb",
    "surface": "#ffffff",
    "panel": "#eaf4f7",
    "panel_active": "#d9edf2",
    "border": "#c4d9e2",
    "text": "#253746",
    "muted": "#536b79",
    "blue": "#1976a8",
    "blue_dark": "#125b82",
    "green": "#2d7f52",
}

# This is the user-provided local definition for the Albers projection used as
# the first suggestion. PROJ does not register 10857 as an EPSG code, so the
# Studio keeps the label and applies the supplied WKT definition directly.
DEFAULT_ALBERS_WKT = '''PROJCS["Conica_Equivalente_de_Albers_Brasil",
  GEOGCS["GCS_SIRGAS2000",
    DATUM["D_SIRGAS2000",
      SPHEROID["Geodetic_Reference_System_of_1980",6378137,298.2572221009113]],
    PRIMEM["Greenwich",0],
    UNIT["Degree",0.017453292519943295]],
  PROJECTION["Albers"],
  PARAMETER["standard_parallel_1",-2],
  PARAMETER["standard_parallel_2",-22],
  PARAMETER["latitude_of_origin",-12],
  PARAMETER["central_meridian",-54],
  PARAMETER["false_easting",5000000],
  PARAMETER["false_northing",10000000],
  UNIT["Meter",1]]'''
DEFAULT_TARGET_CRS_LABEL = "10857 — Albers Brasil (SIRGAS 2000)"
CRS_PRESET_VALUES = {
    DEFAULT_TARGET_CRS_LABEL: DEFAULT_ALBERS_WKT,
    "EPSG:5880 — SIRGAS 2000 / Brazil Polyconic": "EPSG:5880",
    "EPSG:31982 — SIRGAS 2000 / UTM zone 22S": "EPSG:31982",
    "EPSG:31983 — SIRGAS 2000 / UTM zone 23S": "EPSG:31983",
    "EPSG:31984 — SIRGAS 2000 / UTM zone 24S": "EPSG:31984",
    "EPSG:4674 — SIRGAS 2000 (geographic)": "EPSG:4674",
    "EPSG:4326 — WGS 84 (geographic)": "EPSG:4326",
}


def _resolve_target_crs(value: str) -> CRS:
    """Resolve a displayed CRS choice, EPSG code, or full WKT definition."""
    text = value.strip()
    if not text:
        raise ValueError("Choose a target CRS or enter an EPSG code.")
    if text in CRS_PRESET_VALUES:
        definition = CRS_PRESET_VALUES[text]
        return CRS.from_wkt(definition) if definition.lstrip().startswith(("PROJCS[", "GEOGCS[")) else CRS.from_user_input(definition)
    if text == "10857" or text.lower().startswith("10857 "):
        return CRS.from_wkt(DEFAULT_ALBERS_WKT)
    match = re.match(r"^(EPSG|ESRI):\d+", text, flags=re.IGNORECASE)
    if match:
        return CRS.from_user_input(match.group(0))
    return CRS.from_user_input(text)


def _crs_equivalent(left: str, right: str) -> bool:
    """Compare CRS definitions semantically instead of comparing WKT text."""
    try:
        return _resolve_target_crs(left) == _resolve_target_crs(right)
    except Exception:
        return left.strip().casefold() == right.strip().casefold()


@lru_cache(maxsize=1)
def _epsg_crs_choices() -> tuple[tuple[str, str], ...]:
    """Return searchable EPSG CRS labels without blocking the interface repeatedly."""
    if query_crs_info is None:
        return ()
    choices: list[tuple[str, str]] = []
    try:
        infos = query_crs_info(
            auth_name="EPSG",
            pj_types=["PROJECTED_CRS", "GEOGRAPHIC_2D_CRS"],
            allow_deprecated=False,
        )
        for info in infos:
            code = str(info.code)
            choices.append((f"EPSG:{code} — {info.name}", f"EPSG:{code}"))
    except Exception:
        return ()
    return tuple(choices)


def _resource_path(name: str) -> Path:
    """Resolve a bundled resource both from source and from a frozen build."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root) / "brmangue_studio" / "assets" / name
    return Path(__file__).resolve().parent / "assets" / name


def _open_path_with_desktop_application(path: Path) -> None:
    """Open a file or folder with the operating system's default application."""
    target = path.expanduser().resolve()
    if sys.platform == "win32":
        os.startfile(str(target))  # type: ignore[attr-defined]
        return

    opener = "open" if sys.platform == "darwin" else "xdg-open"
    opener_path = shutil.which(opener)
    if opener_path is None:
        raise FileNotFoundError(f"The desktop utility '{opener}' is not installed.")
    subprocess.Popen(
        [opener_path, str(target)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _center_window(window: tk.Misc, width: int, height: int) -> None:
    """Place a window at the center of the active display."""
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max((screen_width - width) // 2, 0)
    y = max((screen_height - height) // 2, 0)
    window.geometry(f"{width}x{height}+{x}+{y}")


def _require_transformable_crs(crs: CRS, raster_name: str) -> None:
    """Reject local engineering CRS metadata with a concise corrective hint."""
    wkt = crs.to_wkt().lstrip().upper()
    if wkt.startswith(("ENGCRS[", "LOCAL_CS[")):
        raise ValueError(
            f"{raster_name} is tagged with a local/engineering CRS ({crs.to_string()}), "
            "which has no geodetic datum or projection definition. Its coordinates "
            "cannot be transformed automatically. Verify the CRS recorded in the "
            "source GeoTIFF and use its authoritative CRS definition."
        )


def _format_duration(seconds: float | int | None) -> str:
    """Format elapsed seconds for the live monitor and final run summary."""
    if seconds is None:
        return "—"
    total = max(0, int(round(float(seconds))))
    hours, remainder = divmod(total, 3600)
    minutes, seconds_value = divmod(remainder, 60)
    if hours:
        return f"{hours} h {minutes:02d} min {seconds_value:02d} s"
    if minutes:
        return f"{minutes} min {seconds_value:02d} s"
    return f"{seconds_value} s"


def _format_bytes(value: int | float | None) -> str:
    """Format a byte count for the final run summary."""
    if value is None:
        return "—"
    amount = max(0.0, float(value))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024.0 or unit == "TiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024.0
    return "—"


def _reproject_raster_to_grid(
    source_path: str | Path,
    destination_path: str | Path,
    *,
    band: int,
    target_crs: CRS,
    target_transform: Any,
    target_width: int,
    target_height: int,
    resampling: Resampling,
    target_nodata: float | int,
) -> Path:
    """Write one raster on a common target grid without changing the source.

    The output is written window by window through a ``WarpedVRT``.  The
    previous implementation materialized both the complete source band and
    the complete destination grid in RAM.  That was especially costly for a
    CMMA-scale grid (hundreds of millions of pixels) and could make an
    otherwise valid Albers reprojection fail before the simulation started.
    """
    source_path = Path(source_path)
    destination_path = Path(destination_path)
    with rasterio.open(source_path) as source:
        if source.crs is None:
            raise ValueError(f"The raster has no CRS metadata: {source_path.name}")
        _require_transformable_crs(source.crs, source_path.name)
        if band < 1 or band > source.count:
            raise ValueError(f"Band {band} is not available in {source_path.name}.")
        source_dtype = np.dtype(source.dtypes[band - 1])
        if np.issubdtype(source_dtype, np.integer):
            target_nodata = int(target_nodata)
            limits = np.iinfo(source_dtype)
            if target_nodata < limits.min or target_nodata > limits.max:
                target_nodata = int(limits.min)
        source_fill = source.nodata if source.nodata is not None else target_nodata
        profile = source.profile.copy()
        profile.update(
            driver="GTiff",
            height=int(target_height),
            width=int(target_width),
            count=1,
            dtype=source_dtype.name,
            crs=target_crs,
            transform=target_transform,
            nodata=target_nodata,
            compress="deflate",
            BIGTIFF="IF_SAFER",
        )
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(destination_path, "w", **profile) as output:
            # WarpedVRT performs the coordinate transformation lazily.  Only
            # one output block is resident at a time, keeping peak memory
            # independent of the total raster area.
            with WarpedVRT(
                source,
                crs=target_crs,
                transform=target_transform,
                width=int(target_width),
                height=int(target_height),
                resampling=resampling,
                src_nodata=source_fill,
                nodata=target_nodata,
            ) as warped:
                for _, window in output.block_windows(1):
                    block = warped.read(1, window=window, masked=True)
                    values = np.asarray(block.filled(target_nodata))
                    # NaNs can be present in floating rasters without being
                    # declared as nodata.  Do not let them propagate into
                    # the prepared GeoTIFFs.
                    if np.issubdtype(values.dtype, np.floating):
                        values = np.where(np.isfinite(values), values, target_nodata)
                    output.write(values.astype(source_dtype, copy=False), 1, window=window)
    return destination_path


def _show_splash(app: tk.Tk) -> tk.Toplevel:
    """Show a compact startup screen while the main workspace becomes ready."""
    splash = tk.Toplevel(app)
    splash.overrideredirect(True)
    splash.resizable(False, False)
    splash.configure(bg="#cbd5df")

    card = tk.Frame(splash, bg="#ffffff", highlightthickness=0, padx=1, pady=1)
    card.pack(fill="both", expand=True)
    content = tk.Frame(card, bg="#ffffff", padx=34, pady=24)
    content.pack(fill="both", expand=True)

    logo_path = _resource_path("BR-MANGUE_STUDIO_preview_original.png")
    logo_photo: ImageTk.PhotoImage | None = None
    if logo_path.exists():
        with Image.open(logo_path) as source:
            logo = source.convert("RGBA")
            logo.thumbnail((560, 190), Image.Resampling.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo, master=splash)
        splash._logo_photo = logo_photo  # type: ignore[attr-defined]
        tk.Label(content, image=logo_photo, bg="#ffffff", borderwidth=0).pack(pady=(0, 8))
    else:
        tk.Label(
            content,
            text="BR-MANGUE Studio",
            font=("Segoe UI", 22, "bold"),
            foreground="#17324d",
            bg="#ffffff",
        ).pack(pady=(10, 24))

    geotam_row = tk.Frame(content, bg="#ffffff")
    geotam_row.pack(pady=(0, 12))
    language_code = getattr(app, "language_code", "en")
    tk.Label(
        geotam_row,
        text=translate("by", language_code),
        font=("Segoe UI", 9),
        foreground="#687786",
        bg="#ffffff",
    ).pack(side="left", padx=(0, 8))
    geotam_path = _resource_path("GEOTAM_logo.jpeg")
    if geotam_path.exists():
        with Image.open(geotam_path) as source:
            geotam_logo = source.convert("RGB")
            geotam_logo.thumbnail((260, 76), Image.Resampling.LANCZOS)
            geotam_photo = ImageTk.PhotoImage(geotam_logo, master=splash)
        splash._geotam_photo = geotam_photo  # type: ignore[attr-defined]
        tk.Label(geotam_row, image=geotam_photo, bg="#ffffff", borderwidth=0).pack(side="left")
    else:
        tk.Label(
            geotam_row,
            text="GEOTAM",
            font=("Segoe UI", 10, "bold"),
            foreground="#2a628d",
            bg="#ffffff",
        ).pack(side="left")

    tk.Label(
        content,
        text=translate("Spatial cellular model for coastal change", language_code),
        font=("Segoe UI", 10),
        foreground="#53616f",
        bg="#ffffff",
    ).pack(pady=(0, 12))
    tk.Label(
        content,
        text=f"{translate('Version', language_code)} {APP_VERSION}",
        font=("Segoe UI", 10, "bold"),
        foreground="#17324d",
        bg="#ffffff",
    ).pack()
    tk.Label(
        content,
        text=APP_COPYRIGHT,
        font=("Segoe UI", 9),
        foreground="#687786",
        bg="#ffffff",
    ).pack(pady=(2, 16))

    progress_style = ttk.Style(splash)
    progress_style.configure(
        "Splash.Horizontal.TProgressbar",
        troughcolor="#e2e8ee",
        background="#2f87b7",
        lightcolor="#2f87b7",
        darkcolor="#2f87b7",
        bordercolor="#e2e8ee",
    )
    progress = ttk.Progressbar(
        content,
        mode="indeterminate",
        length=480,
        style="Splash.Horizontal.TProgressbar",
    )
    progress.pack(fill="x", pady=(0, 8))
    progress.start(9)
    tk.Label(
        content,
        text=translate("Loading workspace…", language_code),
        font=("Segoe UI", 8),
        foreground="#7a8792",
        bg="#ffffff",
    ).pack()

    splash.update_idletasks()
    width = splash.winfo_reqwidth()
    height = splash.winfo_reqheight()
    _center_window(splash, width, height)
    splash.lift()
    splash.focus_force()

    def finish() -> None:
        if not splash.winfo_exists():
            return
        progress.stop()
        splash.destroy()
        app.deiconify()
        app.lift()

    splash.bind("<Escape>", lambda _event: finish())
    splash.after(SPLASH_DURATION_MS, finish)
    return splash


def _default_role(code: int) -> str:
    if code in DEFAULT_LAND_COVER_MAPPING["mangrove"]:
        return "Mangrove"
    if code in DEFAULT_LAND_COVER_MAPPING["water"]:
        return "Water"
    if code in DEFAULT_LAND_COVER_MAPPING["natural_accommodation_candidate"]:
        return "Natural vegetation"
    return "Anthropized / blocked"


def _validate_class_assignments(
    roles: dict[int, str],
    *,
    mode: str,
    custom_classes: list[dict[str, Any]],
    language: str = "en",
) -> None:
    """Reject incomplete custom mappings instead of classifying them implicitly."""
    unassigned = sorted(
        int(code) for code, role in roles.items() if role == UNASSIGNED_ROLE
    )
    if unassigned:
        raise ValueError(translate(
            "Assign each source code to a custom class or choose Exclude before loading inputs. Unassigned codes: {codes}.",
            language,
        ).format(codes=", ".join(map(str, unassigned))))
    if mode == "custom" and not custom_classes:
        raise ValueError(translate(
            "Add at least one custom model class before loading inputs in custom mode.",
            language,
        ))


def _validate_class_coverage(
    roles: dict[int, str],
    source_code_counts: dict[str, int],
    *,
    mode: str,
    language: str = "en",
) -> None:
    """Ensure every valid raster category has an explicit custom-mode choice."""
    if mode != "custom":
        return
    observed = {int(code) for code in source_code_counts}
    missing = sorted(observed.difference(int(code) for code in roles))
    if missing:
        raise ValueError(translate(
            "The raster contains source codes that were not inspected. Inspect the raster again and assign or exclude them: {codes}.",
            language,
        ).format(codes=", ".join(map(str, missing))))


def _write_transition_report(
    land_cover_path: str | Path,
    band: int,
    inputs: RasterInputSet,
    final_state: np.ndarray,
    code_roles: dict[int, str],
    output_path: str | Path,
) -> Path:
    """Relate source classes and final states, retaining custom-class identity."""
    with rasterio.open(land_cover_path) as src:
        source_codes = src.read(band)[inputs.valid_rows, inputs.valid_cols]
    destination_codes = np.asarray(final_state)
    if source_codes.size != destination_codes.size:
        raise ValueError("The source raster and final state must contain the same number of cells.")
    pair_counts: dict[tuple[int, int], int] = {}
    pair_dtype = np.dtype([("source", np.int32), ("destination", np.int32)])
    for start in range(0, source_codes.size, TRANSITION_REPORT_CHUNK_CELLS):
        stop = min(start + TRANSITION_REPORT_CHUNK_CELLS, source_codes.size)
        pair_chunk = np.empty(stop - start, dtype=pair_dtype)
        pair_chunk["source"] = source_codes[start:stop]
        pair_chunk["destination"] = destination_codes[start:stop]
        pairs, counts = np.unique(pair_chunk, return_counts=True)
        for pair, count in zip(pairs, counts):
            key = (int(pair["source"]), int(pair["destination"]))
            pair_counts[key] = pair_counts.get(key, 0) + int(count)
    custom_classes = {
        int(item["code"]): item
        for item in inputs.metadata.get("custom_model_classes", [])
    }
    state_catalog = inputs.metadata.get("model_state_catalog", {})
    rows: list[dict[str, Any]] = []
    for (source_code, destination_code), count in sorted(pair_counts.items()):
        role = code_roles.get(source_code, "Unmapped")
        custom_name = ""
        behavior = ""
        if role.startswith("custom:"):
            try:
                custom_code = int(role.split(":", 1)[1])
            except ValueError:
                custom_code = -1
            custom_definition = custom_classes.get(custom_code, {})
            custom_name = str(custom_definition.get("name", ""))
            behavior = str(custom_definition.get("behavior", "fixed"))
            role = f"Custom class: {custom_name}" if custom_name else role
        destination_entry = state_entry(state_catalog, destination_code)
        destination = (
            str(destination_entry.get("name", f"Class {destination_code}"))
            if destination_entry
            else f"Class {destination_code}"
        )
        rows.append(
            {
                "source_land_cover_code": source_code,
                "source_role": role,
                "source_custom_class": custom_name,
                "behavior_profile": behavior,
                "destination_model_state": destination,
                "destination_model_code": destination_code,
                "cells": count,
            }
        )
    result = pd.DataFrame(
        rows,
        columns=[
            "source_land_cover_code",
            "source_role",
            "source_custom_class",
            "behavior_profile",
            "destination_model_state",
            "destination_model_code",
            "cells",
        ],
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return output_path


def _display_values_for_inputs(
    inputs: RasterInputSet,
    values: np.ndarray,
    *,
    dtype: Any,
    fill_value: float | int,
) -> np.ndarray:
    """Create a cropped, downsampled display array without touching Tk."""
    full = np.full(inputs.raster_shape, fill_value, dtype=dtype)
    full[inputs.valid_rows, inputs.valid_cols] = np.asarray(values, dtype=dtype)
    rows, cols = np.where(inputs.valid_mask)
    pad = 10
    r0 = max(int(rows.min()) - pad, 0)
    r1 = min(int(rows.max()) + pad + 1, full.shape[0])
    c0 = max(int(cols.min()) - pad, 0)
    c1 = min(int(cols.max()) + pad + 1, full.shape[1])
    crop = full[r0:r1, c0:c1]
    stride = max(1, int(max(crop.shape) / 700))
    return crop[::stride, ::stride]


def _display_elevation_for_inputs(inputs: RasterInputSet) -> np.ndarray:
    """Return a display-sized elevation image without requiring the full grid."""
    if inputs.grid is not None:
        return _display_values_for_inputs(inputs, inputs.grid.relative_elevation, dtype=np.float64, fill_value=np.nan)

    grid_meta = inputs.metadata.get("grid", {})
    row_min = int(grid_meta.get("valid_row_min", 0))
    row_max = int(grid_meta.get("valid_row_max", inputs.raster_shape[0] - 1))
    col_min = int(grid_meta.get("valid_col_min", 0))
    col_max = int(grid_meta.get("valid_col_max", inputs.raster_shape[1] - 1))
    height = max(1, row_max - row_min + 1)
    width = max(1, col_max - col_min + 1)
    stride = max(1, int(max(height, width) / 700))
    out_height = max(1, int(np.ceil(height / stride)))
    out_width = max(1, int(np.ceil(width / stride)))
    with rasterio.open(inputs.metadata["elevation"]["path"]) as source:
        values = source.read(
            1,
            window=Window(col_min, row_min, width, height),
            out_shape=(out_height, out_width),
            resampling=Resampling.nearest,
            masked=True,
        )
    return np.asarray(values.filled(np.nan), dtype=np.float64)


def _area_frame(inputs: RasterInputSet, frame: pd.DataFrame) -> pd.DataFrame:
    """Ensure display frames expose km² equivalents when the CRS is metric."""
    area = inputs.cell_area_km2
    if area is None or frame.empty:
        return frame
    result = frame.copy()
    result["cell_area_km2"] = float(area)
    for column in (
        "mangrove",
        "migrated_mangrove",
        "flooded_mangrove",
        "mangrove_extent",
        "annual_gain",
        "annual_loss",
        "annual_net_change",
    ):
        if column in result and f"{column}_km2" not in result:
            result[f"{column}_km2"] = result[column].astype(float) * float(area)
    return result


def _save_annual_figure_file(
    inputs: RasterInputSet,
    run_dir: Path,
    state: np.ndarray,
    trajectory: pd.DataFrame,
    year: int,
    language_code: str = "en",
    state_catalog: dict[str, Any] | None = None,
) -> Path:
    """Write four independent annual figures and return the state-map path."""
    figure_root = run_dir / "figures"
    for component in FIGURE_COMPONENTS:
        (figure_root / component).mkdir(parents=True, exist_ok=True)
    paths = {
        component: figure_root / component / f"{component}_{year}.png"
        for component in FIGURE_COMPONENTS
    }

    display_state = np.asarray(state, dtype=np.int32)
    image = _display_values_for_inputs(inputs, display_state, dtype=np.int32, fill_value=0)
    cmap, norm = _model_colormap(state_catalog)
    state_fig = Figure(figsize=(7.2, 5.6), dpi=120)
    state_ax = state_fig.add_subplot(111)
    state_ax.imshow(image, cmap=cmap, norm=norm, interpolation="nearest")
    state_ax.text(
        0.98, 0.03, str(year), transform=state_ax.transAxes,
        ha="right", va="bottom", fontsize=12, color="#1f2933",
        bbox={"facecolor": "white", "alpha": 0.78, "pad": 2, "edgecolor": "none"},
    )
    state_ax.set_title("")
    state_ax.set_xlabel(translate("Raster columns", language_code))
    state_ax.set_ylabel(translate("Raster rows", language_code))
    state_fig.legend(
        handles=_model_legend_handles(state_catalog, language_code),
        loc="lower center", bbox_to_anchor=(0.5, 0.01), ncol=3, fontsize=8, title=translate("Model states", language_code),
    )
    state_fig.subplots_adjust(left=0.09, right=0.98, top=0.91, bottom=0.24)
    FigureCanvasAgg(state_fig).print_figure(paths["state"], dpi=150, bbox_inches="tight")

    elev_image = _display_elevation_for_inputs(inputs)
    finite = elev_image[np.isfinite(elev_image)]
    elev_fig = Figure(figsize=(7.2, 5.6), dpi=120)
    elev_ax = elev_fig.add_subplot(111)
    if finite.size:
        vmin, vmax = float(np.nanmin(finite)), float(np.nanmax(finite))
        if np.isclose(vmin, vmax):
            vmax = vmin + 1e-9
        elev_im = elev_ax.imshow(elev_image, cmap="terrain", interpolation="nearest", vmin=vmin, vmax=vmax)
        elev_fig.colorbar(elev_im, ax=elev_ax, fraction=0.046, pad=0.04, label=translate("Relative elevation", language_code))
    else:
        elev_ax.imshow(elev_image, cmap="terrain", interpolation="nearest")
    elev_ax.set_title("")
    elev_ax.set_xlabel(translate("Raster columns", language_code))
    elev_ax.set_ylabel(translate("Raster rows", language_code))
    elev_fig.subplots_adjust(left=0.09, right=0.90, top=0.91, bottom=0.14)
    FigureCanvasAgg(elev_fig).print_figure(paths["elevation"], dpi=150, bbox_inches="tight")

    visible = trajectory[trajectory["calendar_year"] <= year] if not trajectory.empty else trajectory
    visible = _area_frame(inputs, visible)
    trajectory_fig = Figure(figsize=(7.2, 4.6), dpi=120)
    trajectory_ax = trajectory_fig.add_subplot(111)
    if not visible.empty:
        for column, label, color in [
            ("mangrove", translate("Mangrove cells", language_code), "#006d2c"),
            ("migrated_mangrove", translate("Migrated mangrove", language_code), "#7b3294"),
            ("flooded_mangrove", translate("Flooded mangrove", language_code), "#e34a33"),
        ]:
            if column in visible:
                trajectory_ax.plot(visible["calendar_year"], visible[column], label=label, color=color, linewidth=2)
        trajectory_ax.legend(loc="best", fontsize=8)
    trajectory_ax.set_title("")
    trajectory_ax.set_xlabel(translate("Calendar year", language_code))
    trajectory_ax.set_ylabel(translate("Cells", language_code))
    trajectory_ax.grid(alpha=0.25)
    trajectory_fig.subplots_adjust(left=0.10, right=0.98, top=0.90, bottom=0.16)
    FigureCanvasAgg(trajectory_fig).print_figure(paths["trajectory"], dpi=150, bbox_inches="tight")

    change_fig = Figure(figsize=(7.2, 4.6), dpi=120)
    change_ax = change_fig.add_subplot(111)
    if not visible.empty:
        if "annual_net_change" in visible:
            net_change = visible["annual_net_change"].fillna(0).to_numpy()
        else:
            gains = visible.get("annual_gain", pd.Series(np.zeros(len(visible)))).to_numpy()
            losses = visible.get("annual_loss", pd.Series(np.zeros(len(visible)))).to_numpy()
            net_change = gains - losses
        years = visible["calendar_year"].to_numpy()
        change_ax.bar(years, np.maximum(net_change, 0), color="#72b66b", label=translate("Net annual gain", language_code), width=0.72)
        change_ax.bar(years, np.minimum(net_change, 0), color="#ef3b2c", label=translate("Net annual loss", language_code), width=0.72)
        change_ax.legend(loc="best", fontsize=8)
    change_ax.axhline(0, color="#333333", linewidth=0.8)
    change_ax.set_title("")
    change_ax.set_xlabel(translate("Calendar year", language_code))
    change_ax.set_ylabel(translate("Net annual change (cells)", language_code))
    change_ax.grid(alpha=0.2, axis="y")
    change_fig.subplots_adjust(left=0.10, right=0.98, top=0.90, bottom=0.16)
    FigureCanvasAgg(change_fig).print_figure(paths["change"], dpi=150, bbox_inches="tight")
    return paths["state"]


def _generate_annual_figures(
    inputs: RasterInputSet,
    run_dir: Path,
    trajectory: pd.DataFrame,
    language_code: str = "en",
) -> list[Path]:
    """Generate annual figures from saved rasters outside the UI thread."""
    states_dir = run_dir / "states"
    state_catalog = inputs.metadata.get("model_state_catalog", {})
    paths: list[Path] = []
    for year in trajectory.get("calendar_year", pd.Series(dtype=int)).astype(int):
        state_path = states_dir / f"state_{int(year)}.tif"
        if not state_path.exists():
            continue
        with rasterio.open(state_path) as src:
            state = src.read(1)[inputs.valid_rows, inputs.valid_cols]
        paths.append(
            _save_annual_figure_file(
                inputs, run_dir, state, trajectory, int(year), language_code,
                state_catalog=state_catalog,
            )
        )
    index = []
    for state_path in paths:
        year = int(state_path.stem.rsplit("_", 1)[-1])
        index.append({
            "calendar_year": year,
            **{
                component: str((run_dir / "figures" / component / f"{component}_{year}.png").relative_to(run_dir))
                for component in FIGURE_COMPONENTS
            },
        })
    (run_dir / "figures" / "annual_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return paths


def _write_gif(frame_paths: list[Path], destination: Path) -> Path | None:
    """Write an animated GIF from a sequence of PNG frames."""
    frames = [path for path in frame_paths if path.exists()]
    if not frames:
        return None
    images: list[Image.Image] = []
    for path in frames:
        with Image.open(path) as image:
            images.append(image.convert("P", palette=Image.Palette.ADAPTIVE))
    destination.parent.mkdir(parents=True, exist_ok=True)
    first, *rest = images
    first.save(destination, save_all=True, append_images=rest, duration=800, loop=0, optimize=False)
    return destination


def _generate_animation(frame_paths: list[Path], run_dir: Path) -> Path | None:
    """Create the state-map GIF outside the UI thread."""
    gif_path = run_dir / "simulation.gif"
    result = _write_gif(frame_paths, gif_path)
    if result is not None:
        _write_gif(frame_paths, run_dir / "animations" / "state.gif")
    return result


def _generate_component_animations(run_dir: Path, state_paths: list[Path]) -> dict[str, Path]:
    """Create one GIF per annual figure component."""
    result: dict[str, Path] = {}
    for component in FIGURE_COMPONENTS:
        paths = [
            run_dir / "figures" / component / f"{component}_{int(path.stem.rsplit('_', 1)[-1])}.png"
            for path in state_paths
        ]
        output = _write_gif(paths, run_dir / "animations" / f"{component}.gif")
        if output is not None:
            result[component] = output
    return result


def _write_simulation_spreadsheet(
    inputs: RasterInputSet,
    run_dir: Path,
    trajectory: pd.DataFrame,
) -> Path:
    """Write a complete, spreadsheet-friendly table for the simulation run."""
    trajectory_frame = trajectory.copy()
    count_rows: list[dict[str, Any]] = []
    state_paths: list[tuple[int, Path]] = []
    initial_path = next(run_dir.glob("initial_state_*.tif"), None)
    if initial_path is not None:
        try:
            initial_year = int(initial_path.stem.rsplit("_", 1)[-1])
            state_paths.append((initial_year, initial_path))
        except ValueError:
            pass
    for path in sorted((run_dir / "states").glob("state_*.tif")):
        try:
            state_paths.append((int(path.stem.rsplit("_", 1)[-1]), path))
        except ValueError:
            continue
    for year, path in state_paths:
        with rasterio.open(path) as src:
            values = np.asarray(src.read(1)[inputs.valid_rows, inputs.valid_cols], dtype=np.int32)
        row: dict[str, Any] = {"calendar_year": year, "valid_cells": int(inputs.n_cells)}
        cell_area_km2 = inputs.cell_area_km2
        if cell_area_km2 is not None:
            row["valid_cells_km2"] = float(inputs.n_cells * cell_area_km2)
        for raw_code, definition in inputs.metadata.get("model_state_catalog", {}).get("states", {}).items():
            code = int(raw_code)
            name = re.sub(r"[^a-z0-9]+", "_", str(definition.get("name", f"class_{code}")).casefold()).strip("_")
            name = name or f"class_{code}"
            class_count = int(np.count_nonzero(values == code))
            row[f"state_{code}_{name}_cells"] = class_count
            if cell_area_km2 is not None:
                row[f"state_{code}_{name}_km2"] = float(class_count * cell_area_km2)
        count_rows.append(row)
    counts_frame = pd.DataFrame(count_rows)
    if trajectory_frame.empty:
        combined = counts_frame
    elif counts_frame.empty:
        combined = trajectory_frame
    else:
        combined = counts_frame.merge(trajectory_frame, on="calendar_year", how="outer", suffixes=("", "_trajectory"))
        combined = combined.sort_values("calendar_year").reset_index(drop=True)
    output_path = run_dir / "simulation_data.csv"
    combined.to_csv(output_path, index=False)
    return output_path


class BRMangueStudio(tk.Tk):
    """Main BR-MANGUE Studio window."""

    def __init__(self) -> None:
        super().__init__()
        self.language_code = load_language()
        self._widget_text_defaults: dict[tk.Misc, str] = {}
        self._notebook_tab_defaults: dict[tuple[ttk.Notebook, str], str] = {}
        self._menu_label_defaults: dict[tuple[tk.Menu, int], str] = {}
        self._class_combos: dict[int, ttk.Combobox] = {}
        self.title("BR-MANGUE Studio")
        self.geometry("1500x930")
        self.minsize(1120, 720)
        _center_window(self, 1500, 930)
        icon_path = _resource_path("BR-MANGUE_BR_icon.ico")
        try:
            if icon_path.exists():
                self.iconbitmap(default=str(icon_path))
        except (OSError, tk.TclError):
            icon_png = _resource_path("BR-MANGUE_BR_icon.png")
            if icon_png.exists():
                with Image.open(icon_png) as source:
                    icon = source.convert("RGBA")
                    icon.thumbnail((64, 64), Image.Resampling.LANCZOS)
                    self._window_icon_photo = ImageTk.PhotoImage(icon, master=self)
                self.iconphoto(True, self._window_icon_photo)
        self.project_file: Path | None = None
        self.inputs: RasterInputSet | None = None
        self.class_vars: dict[int, tk.StringVar] = {}
        self.class_counts: dict[int, int] = {}
        self.custom_model_classes: list[dict[str, Any]] = []
        self.message_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.running = False
        self.last_state: np.ndarray | None = None
        self.trajectory_records: list[dict[str, Any]] = []
        self.initial_class_counts: dict[str, int] = {}
        self.run_dir: Path | None = None
        self.annual_figure_paths: list[Path] = []
        self.animation_frames: list[ImageTk.PhotoImage] = []
        self.animation_component_paths: dict[str, list[Path]] = {}
        self.animation_component_images: dict[str, list[ImageTk.PhotoImage]] = {}
        self.animation_labels: dict[str, ttk.Label] = {}
        self.animation_frame_index = 0
        self.animation_after_id: str | None = None
        self.animation_playing = True
        self.animation_path: Path | None = None
        self.animation_paths: dict[str, Path] = {}
        self.simulation_table_path: Path | None = None
        self.model_elapsed_seconds: float | None = None
        self.total_elapsed_seconds: float | None = None
        self.render_stride = 1
        self.process = psutil.Process() if psutil is not None else None
        self._build_variables()
        self._build_menu()
        self._build_layout()
        self._capture_static_ui_text()
        self._watch_status_variables()
        self._apply_language()
        self.after(100, self._poll_messages)
        self.after(1000, self._update_resources)

    def _build_variables(self) -> None:
        # Generic interface labels are used while legacy aliases remain
        # accepted so version 0.1 projects continue to load.
        self.land_cover_var = tk.StringVar()
        self.elevation_var = tk.StringVar()
        self.mapbiomas_var = self.land_cover_var
        self.mask_var = tk.StringVar()
        self.soil_var = tk.StringVar()
        self.land_cover_band_var = tk.StringVar(value="1")
        self.land_cover_year_var = tk.StringVar(value="")
        self.band_var = self.land_cover_band_var
        self.year_var = self.land_cover_year_var
        self.initial_year_var = tk.StringVar(value="2025")
        self.final_year_var = tk.StringVar(value="2035")
        self.tide_height_var = tk.StringVar(value="6.0")
        self.slr_var = tk.StringVar(value="0.5")
        self.sea_level_mode_var = tk.StringVar(value="constant")
        self.sea_level_trajectory_path_var = tk.StringVar(value="")
        self.sea_level_summary_var = tk.StringVar(value="")
        self._sea_level_trajectory: SeaLevelTrajectory | None = None
        self.accretion_var = tk.StringVar(value="")
        self.migration_maturity_var = tk.StringVar(value="3")
        self.block_size_var = tk.StringVar(value="10000")
        self.engine_var = tk.StringVar(value="blocks")
        self.engine_choice_var = tk.StringVar(value="")
        self.soil_enabled_var = tk.BooleanVar(value=False)
        self.migration_without_soil_var = tk.BooleanVar(value=True)
        self.source_crs_var = tk.StringVar(value="Not loaded")
        self.datum_var = tk.StringVar(value="Not loaded")
        self.vertical_datum_var = tk.StringVar(value="")
        self.custom_class_name_var = tk.StringVar(value="")
        self.class_mapping_mode_var = tk.StringVar(value="standard")
        self.custom_class_color_var = tk.StringVar(value=DEFAULT_CUSTOM_COLORS[0])
        self.custom_class_behavior_var = tk.StringVar(value="Fixed class")
        self.expected_crs_var = tk.StringVar(value="")
        self.target_crs_var = tk.StringVar(value=DEFAULT_TARGET_CRS_LABEL)
        self.target_resolution_var = tk.StringVar(value="")
        self.target_crs_combo: ttk.Combobox | None = None
        self._crs_choice_values: dict[str, str] = dict(CRS_PRESET_VALUES)
        self.project_status_var = tk.StringVar(value="No project open")
        self.run_status_var = tk.StringVar(value="Ready")
        self.resource_var = tk.StringVar(value="CPU — | RAM — | Disk —")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.cells_var = tk.StringVar(value="Cells processed: 0")
        self.speed_var = tk.StringVar(value="Speed: —")
        self.language_var = tk.StringVar(value=CODE_TO_LANGUAGE[self.language_code])

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        self.main_menu = menu
        project = tk.Menu(menu, tearoff=False)
        project.add_command(label="New project", command=self.new_project)
        project.add_command(label="Open project", command=self.open_project)
        project.add_command(label="Save project", command=self.save_project)
        project.add_command(label="Save project as...", command=self.save_project_as)
        project.add_separator()
        project.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="Project", menu=project)
        data = tk.Menu(menu, tearoff=False)
        data.add_command(label="Load / inspect inputs", command=self.load_inputs)
        data.add_command(label="Refresh land-cover classes", command=self.inspect_mapbiomas)
        menu.add_cascade(label="Data", menu=data)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About", command=lambda: self._show_message(
            "showinfo",
            "BR-MANGUE Studio",
            "Desktop interface for the BR-MANGUE cellular model.\n"
            "The model accepts aligned user-provided rasters; inputs are read-only and products are saved in the project results folder.",
        ))
        menu.add_cascade(label="Help", menu=help_menu)
        self._menus = (menu, project, data, help_menu)
        self.config(menu=menu)

    def _build_layout(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.configure(bg=UI_COLORS["window"])
        style.configure(".", background=UI_COLORS["window"], foreground=UI_COLORS["text"])
        style.configure("TFrame", background=UI_COLORS["window"])
        style.configure("TLabel", background=UI_COLORS["window"], foreground=UI_COLORS["text"])
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground=UI_COLORS["blue_dark"])
        style.configure("Subtitle.TLabel", font=("Segoe UI", 9), foreground=UI_COLORS["muted"])
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground=UI_COLORS["blue_dark"])
        style.configure("TLabelframe", background=UI_COLORS["window"], bordercolor=UI_COLORS["border"], lightcolor=UI_COLORS["border"], darkcolor=UI_COLORS["border"])
        style.configure("TLabelframe.Label", background=UI_COLORS["window"], foreground=UI_COLORS["blue_dark"])
        style.configure("TNotebook", background=UI_COLORS["panel"], borderwidth=0)
        style.configure("TNotebook.Tab", background=UI_COLORS["panel"], foreground=UI_COLORS["blue_dark"], padding=(12, 6))
        style.map("TNotebook.Tab", background=[("selected", UI_COLORS["surface"]), ("active", UI_COLORS["panel_active"])], foreground=[("selected", UI_COLORS["blue_dark"])])
        style.configure("TButton", background=UI_COLORS["panel"], foreground=UI_COLORS["blue_dark"], bordercolor=UI_COLORS["border"], padding=(9, 5))
        style.map("TButton", background=[("active", UI_COLORS["panel_active"]), ("pressed", "#c7e5ec")])
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), foreground="#ffffff", background=UI_COLORS["blue"])
        style.map("Accent.TButton", background=[("active", UI_COLORS["blue_dark"]), ("pressed", UI_COLORS["green"])])
        style.configure("TEntry", fieldbackground=UI_COLORS["surface"], foreground=UI_COLORS["text"], bordercolor=UI_COLORS["border"])
        style.configure("TCombobox", fieldbackground=UI_COLORS["surface"], foreground=UI_COLORS["text"], bordercolor=UI_COLORS["border"])
        style.configure("TCheckbutton", background=UI_COLORS["window"], foreground=UI_COLORS["text"])
        style.configure("TSeparator", background=UI_COLORS["border"])
        style.configure("Horizontal.TProgressbar", troughcolor=UI_COLORS["panel"], background=UI_COLORS["blue"], lightcolor=UI_COLORS["blue"], darkcolor=UI_COLORS["blue_dark"])
        self.option_add("*Font", ("Segoe UI", 9))

        header = ttk.Frame(self, padding=(14, 10))
        header.pack(fill="x")
        ttk.Label(header, textvariable=self.project_status_var, style="Subtitle.TLabel").pack(side="left")
        ttk.Label(header, textvariable=self.resource_var, style="Subtitle.TLabel").pack(side="right", padx=(8, 0))
        ttk.Label(header, text="Language").pack(side="right", padx=(10, 5))
        self.language_combo = ttk.Combobox(
            header,
            textvariable=self.language_var,
            values=LANGUAGES,
            state="readonly",
            width=18,
        )
        self.language_combo.pack(side="right")
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_selected)
        ttk.Separator(self).pack(fill="x", padx=10)

        main = ttk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        left = ttk.Frame(main, width=405)
        center = ttk.Frame(main)
        right = ttk.Frame(main, width=300)
        main.add(left, weight=0)
        main.add(center, weight=1)
        main.add(right, weight=0)

        self._build_left(left)
        self._build_center(center)
        self._build_right(right)

    def _capture_static_ui_text(self) -> None:
        """Remember English widget captions so language changes are reversible."""
        def visit(widget: tk.Misc) -> None:
            try:
                caption = str(widget.cget("text"))
                if caption:
                    self._widget_text_defaults.setdefault(widget, caption)
            except (tk.TclError, TypeError):
                pass
            if isinstance(widget, ttk.Notebook):
                for tab_id in widget.tabs():
                    key = (widget, tab_id)
                    self._notebook_tab_defaults.setdefault(key, str(widget.tab(tab_id, "text")))
            for child in widget.winfo_children():
                visit(child)

        visit(self)
        for menu in self._menus:
            try:
                for index in range(menu.index("end") + 1):
                    if menu.type(index) in ("command", "cascade", "checkbutton", "radiobutton"):
                        self._menu_label_defaults.setdefault((menu, index), str(menu.entrycget(index, "label")))
            except tk.TclError:
                continue

    def _watch_status_variables(self) -> None:
        """Keep status text readable in the active language as values change."""
        for variable in (
            self.project_status_var,
            self.run_status_var,
            self.source_crs_var,
            self.datum_var,
            self.resource_var,
            self.cells_var,
            self.speed_var,
            self.result_path_var,
            self.animation_info_var,
            self.animation_year_var,
        ):
            variable.trace_add("write", lambda *_args, var=variable: self._translate_status_variable(var))

    def _translate_status_variable(self, variable: tk.StringVar) -> None:
        value = variable.get()
        translated = translate_runtime(value, self.language_code)
        if translated != value:
            variable.set(translated)

    def _apply_language(self) -> None:
        """Refresh captions and visual labels without changing project values."""
        self.title(translate("BR-MANGUE Studio", self.language_code))
        if hasattr(self, "language_var"):
            self.language_var.set(CODE_TO_LANGUAGE[self.language_code])
        for widget, source in tuple(self._widget_text_defaults.items()):
            try:
                widget.configure(text=translate_runtime(source, self.language_code))
            except tk.TclError:
                self._widget_text_defaults.pop(widget, None)
        for (notebook, tab_id), source in tuple(self._notebook_tab_defaults.items()):
            try:
                notebook.tab(tab_id, text=translate(source, self.language_code))
            except tk.TclError:
                self._notebook_tab_defaults.pop((notebook, tab_id), None)
        for (menu, index), source in tuple(self._menu_label_defaults.items()):
            try:
                menu.entryconfigure(index, label=translate(source, self.language_code))
            except tk.TclError:
                self._menu_label_defaults.pop((menu, index), None)
        for variable in (
            self.project_status_var,
            self.run_status_var,
            self.source_crs_var,
            self.datum_var,
            self.resource_var,
            self.cells_var,
            self.speed_var,
            self.result_path_var,
            self.animation_info_var,
            self.animation_year_var,
        ):
            self._translate_status_variable(variable)
        for code, variable in self.class_vars.items():
            canonical = self._canonical_role(variable.get())
            variable.set(self._display_role(canonical))
            combo = self._class_combos.get(code)
            if combo is not None:
                combo.configure(values=self._role_options())
        if hasattr(self, "custom_behavior_combo"):
            behavior = self._canonical_custom_behavior(
                self.custom_class_behavior_var.get()
            )
            self.custom_behavior_combo.configure(values=self._custom_behavior_options())
            self.custom_class_behavior_var.set(self._display_custom_behavior(behavior))
        self._refresh_custom_class_list()
        self._refresh_model_legend()
        if hasattr(self, "rule_table"):
            for column, heading in (
                ("source_code", "Raster code"),
                ("pixels", "Pixels"),
                ("model_class", "Assigned model class"),
                ("behavior", "Transition profile"),
            ):
                self.rule_table.heading(column, text=translate(heading, self.language_code))
            self._refresh_rule_summary()
        if hasattr(self, "engine_combo"):
            self._sync_engine_choice()
        if hasattr(self, "slr_entry"):
            self._on_sea_level_mode_changed()
        if hasattr(self, "monitor_text"):
            self._set_monitor(self._monitor_text())
        if hasattr(self, "class_chart"):
            self.class_bar_labels = {
                "mangrove": translate("Mangrove", self.language_code),
                "migrated_mangrove": translate("Migrated mangrove", self.language_code),
                "flooded_mangrove": translate("Flooded", self.language_code),
                "vegetation": translate("Vegetation", self.language_code),
                "water": translate("Water", self.language_code),
                "anthropized": translate("Developed", self.language_code),
            }
            self._redraw_class_chart()
        if hasattr(self, "trajectory_records") and self.trajectory_records:
            self._draw_trajectory()
        elif hasattr(self, "inputs") and self.inputs is not None:
            self._draw_input_maps()
        elif hasattr(self, "visual_axes"):
            self._draw_placeholder()

    def _on_language_selected(self, _event: Any = None) -> None:
        selected = self.language_var.get()
        self.language_code = LANGUAGE_CODES.get(selected, "en")
        save_language(self.language_code)
        self._apply_language()

    def _sync_engine_choice(self) -> None:
        engine_labels = {
            "blocks": "Persistent blocks",
            "continuous": "Continuous",
            "dissmodel": "DissModel",
        }
        label = engine_labels.get(self.engine_var.get(), "Persistent blocks")
        self.engine_choice_var.set(translate(label, self.language_code))

    def _on_engine_selected(self, _event: Any = None) -> None:
        label = translate(self.engine_choice_var.get(), "en")
        self.engine_var.set({
            "Persistent blocks": "blocks",
            "Continuous": "continuous",
            "DissModel": "dissmodel",
        }.get(label, "blocks"))

    def _show_message(self, kind: str, title: str, message: Any) -> Any:
        """Show a dialog with localized interface text and unchanged diagnostics."""
        dialog = getattr(messagebox, kind)
        return dialog(
            translate_runtime(title, self.language_code),
            translate_runtime(str(message), self.language_code),
            parent=self,
        )

    def _build_left(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)
        inputs_tab = ttk.Frame(notebook, padding=8)
        classes_tab = ttk.Frame(notebook, padding=8)
        params_tab = ttk.Frame(notebook, padding=8)
        notebook.add(inputs_tab, text="Project data")
        notebook.add(classes_tab, text="Class mapping")
        notebook.add(params_tab, text="Simulation")

        self._build_input_tab(inputs_tab)
        self._build_class_tab(classes_tab)
        self._build_parameter_tab(params_tab)

    def _path_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, *, optional: bool = False) -> None:
        ttk.Label(parent, text=label + (" (optional)" if optional else "")).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable, width=34).grid(row=row + 1, column=0, sticky="ew", pady=(0, 5))
        ttk.Button(parent, text="Browse...", command=lambda: self._browse(variable, label)).grid(row=row + 1, column=1, padx=(5, 0), pady=(0, 5))

    def _build_input_tab(self, parent: ttk.Frame) -> None:
        # Keep the input form fully accessible on smaller screens.
        outer = parent
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas)
        content.columnconfigure(0, weight=1)
        content.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        parent = content
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Input rasters (read-only)", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(parent, text="Choose any aligned categorical raster for land cover and any aligned elevation raster. The model does not require a specific provider.", wraplength=360, foreground="#5d6b78").grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 8))
        self._path_row(parent, 2, "Land-cover / categorical raster (GeoTIFF)", self.land_cover_var)
        self._path_row(parent, 4, "Elevation raster (GeoTIFF)", self.elevation_var)
        self._path_row(parent, 6, "Study-area mask", self.mask_var, optional=True)
        self._path_row(parent, 8, "Mangrove suitability raster", self.soil_var, optional=True)
        ttk.Label(parent, text="Raster band (1-based)").grid(row=10, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.band_var, width=12).grid(row=11, column=0, sticky="w")
        ttk.Label(parent, text="Reference year (optional)").grid(row=10, column=1, sticky="w")
        ttk.Entry(parent, textvariable=self.year_var, width=12).grid(row=11, column=1, sticky="w")
        ttk.Label(parent, text="For a multiband raster, select the band that represents the desired reference date. Leave the year blank when the raster has no date metadata.", wraplength=360, foreground="#5d6b78").grid(row=12, column=0, columnspan=2, sticky="w", pady=(2, 8))
        ttk.Button(parent, text="Inspect land-cover classes", command=self.inspect_mapbiomas).grid(row=13, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        ttk.Button(parent, text="Validate and load inputs", command=self.load_inputs).grid(row=14, column=0, columnspan=2, sticky="ew")
        ttk.Separator(parent).grid(row=15, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Label(parent, text="Coordinate reference", font=("Segoe UI", 10, "bold")).grid(row=16, column=0, columnspan=2, sticky="w")
        ttk.Label(parent, text="Detected CRS").grid(row=17, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.source_crs_var, state="readonly").grid(row=18, column=0, columnspan=2, sticky="ew")
        ttk.Label(parent, text="Datum metadata").grid(row=19, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(parent, textvariable=self.datum_var, state="readonly").grid(row=20, column=0, columnspan=2, sticky="ew")
        ttk.Label(parent, text="Input CRS check (optional)").grid(row=21, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(parent, textvariable=self.expected_crs_var).grid(row=22, column=0, columnspan=2, sticky="ew")
        ttk.Label(parent, text="Reprojection target (search by name or EPSG code)").grid(row=23, column=0, sticky="w", pady=(5, 0))
        self.target_crs_combo = ttk.Combobox(
            parent,
            textvariable=self.target_crs_var,
            state="normal",
            width=42,
        )
        self.target_crs_combo.grid(row=24, column=0, columnspan=2, sticky="ew")
        self.target_crs_combo.bind("<FocusIn>", self._on_crs_focus)
        self.target_crs_combo.bind("<KeyRelease>", self._on_crs_keyrelease)
        self.target_crs_combo.bind("<<ComboboxSelected>>", self._on_crs_selected)
        ttk.Label(
            parent,
            text="Type a name such as SIRGAS 2000 or an EPSG code. The default is 10857, using the supplied Albers Brasil definition.",
            wraplength=360,
            foreground="#5d6b78",
        ).grid(row=25, column=0, columnspan=2, sticky="w", pady=(2, 5))
        ttk.Label(parent, text="Target resolution (map units/pixel, optional)").grid(row=26, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(parent, textvariable=self.target_resolution_var).grid(row=27, column=0, columnspan=2, sticky="ew")
        ttk.Button(parent, text="Reproject and align input rasters", command=self.reproject_inputs).grid(row=28, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Label(parent, text="Declared vertical datum (metadata only)").grid(row=29, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(parent, textvariable=self.vertical_datum_var).grid(row=30, column=0, columnspan=2, sticky="ew")
        ttk.Label(parent, text="Reprojection creates new aligned GeoTIFF copies in the project prepared_inputs folder; original rasters remain unchanged. Vertical datum conversion is not inferred automatically.", wraplength=360, foreground="#5d6b78").grid(row=31, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._update_crs_suggestions()

    def _update_crs_suggestions(self, query: str | None = None) -> None:
        """Update the editable CRS list using the current search text."""
        combo = self.target_crs_combo
        if combo is None:
            return
        text = self.target_crs_var.get().strip() if query is None else query.strip()
        normalized = " ".join(text.casefold().split())
        choices: list[str] = []
        seen: set[str] = set()

        def add(label: str, value: str) -> None:
            if label in seen:
                return
            seen.add(label)
            self._crs_choice_values[label] = value
            choices.append(label)

        for label, value in CRS_PRESET_VALUES.items():
            if not normalized or normalized in label.casefold():
                add(label, value)

        if normalized:
            for label, value in _epsg_crs_choices():
                if normalized in label.casefold():
                    add(label, value)
                    if len(choices) >= 40:
                        break
        combo.configure(values=choices)

    def _on_crs_focus(self, _event: Any = None) -> None:
        self._update_crs_suggestions()

    def _on_crs_keyrelease(self, event: Any) -> None:
        if event.keysym in {"Up", "Down", "Left", "Right", "Return", "Escape", "Tab"}:
            return
        self._update_crs_suggestions(self.target_crs_var.get())

    def _on_crs_selected(self, _event: Any = None) -> None:
        self._update_crs_suggestions(self.target_crs_var.get())

    def _build_class_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Source class → model class", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(parent, text="Choose how each numeric class from the categorical raster is interpreted. Excluded codes become NoData.", wraplength=360, foreground="#5d6b78").pack(anchor="w", pady=(3, 8))
        mode_frame = ttk.LabelFrame(parent, text="Mapping mode", padding=6)
        mode_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(
            mode_frame,
            text="Use standard model classes",
            variable=self.class_mapping_mode_var,
            value="standard",
            command=self._on_class_mapping_mode_changed,
        ).pack(anchor="w")
        ttk.Radiobutton(
            mode_frame,
            text="Define my own classes",
            variable=self.class_mapping_mode_var,
            value="custom",
            command=self._on_class_mapping_mode_changed,
        ).pack(anchor="w")
        ttk.Label(
            mode_frame,
            text="Custom mode starts with no assignments. Add classes below, then assign each raster code to a custom class or choose Exclude.",
            wraplength=360,
            foreground="#5d6b78",
        ).pack(anchor="w", pady=(3, 0))
        custom_frame = ttk.LabelFrame(parent, text="Optional custom classes", padding=6)
        custom_frame.pack(fill="x", pady=(0, 8))
        labels_row = ttk.Frame(custom_frame)
        labels_row.pack(fill="x", pady=(0, 2))
        ttk.Label(labels_row, text="Class name").pack(side="left", fill="x", expand=True)
        ttk.Label(labels_row, text="Behavior profile").pack(side="left", padx=(4, 0))
        custom_form = ttk.Frame(custom_frame)
        custom_form.pack(fill="x")
        ttk.Entry(custom_form, textvariable=self.custom_class_name_var, width=14).pack(side="left", fill="x", expand=True)
        self.custom_behavior_combo = ttk.Combobox(
            custom_form,
            textvariable=self.custom_class_behavior_var,
            values=self._custom_behavior_options(),
            state="readonly",
            width=19,
        )
        self.custom_behavior_combo.pack(side="left", padx=(4, 0))
        self.custom_color_button = tk.Button(
            custom_form,
            text="Color",
            background=self.custom_class_color_var.get(),
            activebackground=self.custom_class_color_var.get(),
            command=self._choose_custom_class_color,
            relief="solid",
            bd=1,
            width=3,
        )
        self.custom_color_button.pack(side="left", padx=4)
        ttk.Button(custom_form, text="Add", command=self._add_custom_class).pack(side="left")
        ttk.Label(
            custom_frame,
            text="Select the existing model rules that this class will follow. Its name and color identify it in the outputs.",
            wraplength=360,
            foreground="#5d6b78",
        ).pack(anchor="w", pady=(4, 5))
        self.custom_class_list = ttk.Frame(custom_frame)
        self.custom_class_list.pack(fill="x")
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        self.class_canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.class_canvas.yview)
        self.class_inner = ttk.Frame(self.class_canvas)
        self.class_inner.bind("<Configure>", lambda _: self.class_canvas.configure(scrollregion=self.class_canvas.bbox("all")))
        self.class_canvas.create_window((0, 0), window=self.class_inner, anchor="nw")
        self.class_canvas.configure(yscrollcommand=scrollbar.set)
        self.class_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        ttk.Label(self.class_inner, text="Inspect the land-cover raster to list its classes.").pack(anchor="w", pady=8)
        self._refresh_custom_class_list()

    def _custom_role_label(self, item: dict[str, Any]) -> str:
        return f"{translate('Custom class', self.language_code)}: {item['name']}"

    def _custom_behavior_options(self) -> tuple[str, ...]:
        return tuple(
            translate(label, self.language_code)
            for label in CUSTOM_BEHAVIOR_LABELS.values()
        )

    def _canonical_custom_behavior(self, displayed: str) -> str:
        for behavior, label in CUSTOM_BEHAVIOR_LABELS.items():
            if displayed in {label, translate(label, "pt-BR")}:
                return behavior
        return "fixed"

    def _display_custom_behavior(self, behavior: str) -> str:
        label = CUSTOM_BEHAVIOR_LABELS.get(behavior, CUSTOM_BEHAVIOR_LABELS["fixed"])
        return translate(label, self.language_code)

    def _role_options(self) -> tuple[str, ...]:
        mode_var = getattr(self, "class_mapping_mode_var", None)
        custom_mode = mode_var is not None and mode_var.get() == "custom"
        roles = [UNASSIGNED_ROLE, "Exclude"] if custom_mode else ROLE_LABELS
        return tuple(
            [translate(role, self.language_code) for role in roles]
            + [self._custom_role_label(item) for item in self.custom_model_classes]
        )

    def _canonical_role(self, displayed_role: str) -> str:
        for role in [UNASSIGNED_ROLE, *ROLE_LABELS]:
            if displayed_role in {role, translate(role, "pt-BR")}:
                return role
        for item in self.custom_model_classes:
            english_label = f"{translate('Custom class', 'en')}: {item['name']}"
            portuguese_label = f"{translate('Custom class', 'pt-BR')}: {item['name']}"
            if displayed_role in {english_label, portuguese_label}:
                return f"custom:{int(item['code'])}"
        return displayed_role

    def _display_role(self, role: str) -> str:
        if role.startswith("custom:"):
            try:
                code = int(role.split(":", 1)[1])
            except ValueError:
                return translate("Anthropized / blocked", self.language_code)
            item = next(
                (item for item in self.custom_model_classes if int(item["code"]) == code),
                None,
            )
            if item is not None:
                return self._custom_role_label(item)
            return translate("Anthropized / blocked", self.language_code)
        return translate(role, self.language_code)

    def _on_class_mapping_mode_changed(self) -> None:
        """Reset source assignments when switching mapping workflows."""
        if self.class_counts:
            self._rebuild_class_rows(preserve_current=False)
        self._refresh_rule_summary()

    def _initial_source_role(self, code: int) -> str:
        if self.class_mapping_mode_var.get() == "custom":
            return self._display_role(UNASSIGNED_ROLE)
        return self._display_role(_default_role(code))

    def _refresh_model_legend(self) -> None:
        frame = getattr(self, "model_legend_items", None)
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        catalog = self.inputs.metadata.get("model_state_catalog", {}) if self.inputs else {}
        items = [
            (int(code), translate(str(item.get("name", f"Class {code}")), self.language_code), str(item.get("color", "#b8c2cc")))
            for code, item in sorted(catalog.get("states", {}).items(), key=lambda pair: int(pair[0]))
        ]
        if not items:
            items = [
                (index, translate(name, self.language_code), color)
                for index, (name, color) in enumerate(STANDARD_CLASS_STYLES.values(), start=1)
            ]
        for code, label, color in items:
            item_frame = ttk.Frame(frame)
            item_frame.pack(side="left", anchor="w", padx=(0, 10), pady=(0, 2))
            swatch = tk.Label(item_frame, background=color, width=2, height=1, relief="solid", bd=1)
            swatch.pack(side="left", padx=(0, 3))
            ttk.Label(item_frame, text=label, foreground="#36454f").pack(side="left")

    def _refresh_custom_class_list(self) -> None:
        frame = getattr(self, "custom_class_list", None)
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        for item in self.custom_model_classes:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=1)
            tk.Label(row, background=item["color"], width=2, relief="solid", bd=1).pack(side="left", padx=(0, 5))
            behavior = self._display_custom_behavior(str(item.get("behavior", "fixed")))
            ttk.Label(
                row,
                text=f"{item['name']}  ·  {behavior}  ·  {translate('State', self.language_code)} {item['code']}",
            ).pack(side="left", fill="x", expand=True)
            ttk.Button(
                row,
                text=translate("Remove", self.language_code),
                command=lambda code=int(item["code"]): self._remove_custom_class(code),
            ).pack(side="right")

    def _choose_custom_class_color(self) -> None:
        _rgb, color = colorchooser.askcolor(
            color=self.custom_class_color_var.get(),
            title=translate("Choose class color", self.language_code),
            parent=self,
        )
        if color:
            self.custom_class_color_var.set(color.lower())
            self.custom_color_button.configure(background=color, activebackground=color)

    def _add_custom_class(self) -> None:
        name = self.custom_class_name_var.get().strip()
        if not name:
            self._show_message("showwarning", "Custom class", "Enter a name for the custom class.")
            return
        if any(str(item["name"]).casefold() == name.casefold() for item in self.custom_model_classes):
            self._show_message("showwarning", "Custom class", "Custom class names must be unique.")
            return
        used_codes = {int(item["code"]) for item in self.custom_model_classes}
        code = 1
        while code in used_codes:
            code += 1
        if code > MAX_CUSTOM_MODEL_CLASS_CODE:
            limit_message = translate(
                "The model supports custom class codes through {limit}.",
                self.language_code,
            ).format(limit=MAX_CUSTOM_MODEL_CLASS_CODE)
            self._show_message(
                "showerror", "Custom class", limit_message,
            )
            return
        candidate = self.custom_model_classes + [{
            "code": code,
            "name": name,
            "color": self.custom_class_color_var.get(),
            "behavior": self._canonical_custom_behavior(
                self.custom_class_behavior_var.get()
            ),
        }]
        try:
            self.custom_model_classes = normalize_custom_model_classes(candidate)
        except ValueError as exc:
            self._show_message("showerror", "Custom class", str(exc))
            return
        self.custom_class_name_var.set("")
        self.custom_class_behavior_var.set(
            self._display_custom_behavior("fixed")
        )
        next_color = DEFAULT_CUSTOM_COLORS[(len(self.custom_model_classes)) % len(DEFAULT_CUSTOM_COLORS)]
        self.custom_class_color_var.set(next_color)
        self.custom_color_button.configure(background=next_color, activebackground=next_color)
        self._refresh_custom_class_list()
        self._refresh_model_legend()
        if self.class_counts:
            self._rebuild_class_rows(preserve_current=True)
        self._refresh_rule_summary()

    def _remove_custom_class(self, code: int) -> None:
        if any(self._canonical_role(variable.get()) == f"custom:{code}" for variable in self.class_vars.values()):
            self._show_message(
                "showinfo", "Custom class",
                "Reassign its source classes before removing this custom class.",
            )
            return
        self.custom_model_classes = [
            item for item in self.custom_model_classes if int(item["code"]) != int(code)
        ]
        self._refresh_custom_class_list()
        self._refresh_model_legend()
        if self.class_counts:
            self._rebuild_class_rows(preserve_current=True)
        self._refresh_rule_summary()

    def _build_parameter_tab(self, parent: ttk.Frame) -> None:
        outer = parent
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        parent = ttk.Frame(canvas)
        parent.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=parent, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        parent.columnconfigure(1, weight=1)
        fields = [
            ("Initial calendar year", self.initial_year_var),
            ("Final calendar year", self.final_year_var),
            ("Tidal influence height (m)", self.tide_height_var),
        ]
        for row, (label, variable) in enumerate(fields):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(parent, textvariable=variable, width=18).grid(row=row, column=1, sticky="ew", pady=4)
        forcing = ttk.LabelFrame(parent, text="Sea-level forcing", padding=6)
        forcing.grid(row=3, column=0, columnspan=2, sticky="ew", pady=6)
        forcing.columnconfigure(0, weight=1)
        ttk.Radiobutton(forcing, text="Constant rate", variable=self.sea_level_mode_var,
                        value="constant", command=self._on_sea_level_mode_changed).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(forcing, text="Year-based trajectory (CSV)", variable=self.sea_level_mode_var,
                        value="trajectory", command=self._on_sea_level_mode_changed).grid(row=1, column=0, sticky="w")
        ttk.Label(forcing, text="Sea-level rise (mm/year)").grid(row=2, column=0, sticky="w", pady=(5, 0))
        self.slr_entry = ttk.Entry(forcing, textvariable=self.slr_var, width=18)
        self.slr_entry.grid(row=3, column=0, sticky="ew", pady=(0, 4))
        self.sea_level_path_entry = ttk.Entry(forcing, textvariable=self.sea_level_trajectory_path_var, state="readonly")
        self.sea_level_path_entry.grid(row=4, column=0, columnspan=2, sticky="ew")
        buttons = ttk.Frame(forcing)
        buttons.grid(row=5, column=0, columnspan=2, sticky="ew", pady=4)
        self.sea_level_browse_button = ttk.Button(buttons, text="Choose trajectory CSV", command=self._browse_sea_level_trajectory)
        self.sea_level_browse_button.pack(side="left")
        self.sea_level_preview_button = ttk.Button(buttons, text="Preview curve", command=self._preview_sea_level_trajectory)
        self.sea_level_preview_button.pack(side="left", padx=4)
        help_buttons = ttk.Frame(forcing)
        help_buttons.grid(row=8, column=0, columnspan=2, sticky="w", pady=4)
        self.sea_level_template_button = ttk.Button(help_buttons, text="Save CSV example", command=self._save_sea_level_example)
        self.sea_level_template_button.pack(side="left")
        self.sea_level_help_button = ttk.Button(help_buttons, text="Format and data sources", command=self._show_sea_level_help)
        self.sea_level_help_button.pack(side="left", padx=4)
        ttk.Label(forcing, text="CSV columns: year, sea_level_mm. Use cumulative levels relative to a common baseline.",
                  wraplength=340, foreground="#5d6b78").grid(row=6, column=0, columnspan=2, sticky="w")
        ttk.Label(forcing, textvariable=self.sea_level_summary_var, wraplength=340).grid(row=7, column=0, columnspan=2, sticky="w", pady=4)
        for row, (label, variable) in enumerate([
            ("Constant surface accretion (mm/year, optional)", self.accretion_var),
            ("Migration maturation delay (years)", self.migration_maturity_var),
            ("Block size (cells)", self.block_size_var),
        ], 4):
            ttk.Label(parent, text=label, wraplength=220).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(parent, textvariable=variable, width=18).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Label(parent, text="Processing engine").grid(row=7, column=0, sticky="w", pady=4)
        choices = ["Persistent blocks", "Continuous"]
        if DISSMODEL_AVAILABLE:
            choices.append("DissModel")
        self.engine_combo = ttk.Combobox(
            parent, textvariable=self.engine_choice_var,
            values=tuple(translate(label, self.language_code) for label in choices),
            state="readonly", width=20,
        )
        self.engine_combo.grid(row=7, column=1, sticky="w", pady=4)
        self.engine_combo.bind("<<ComboboxSelected>>", self._on_engine_selected)
        self._sync_engine_choice()
        ttk.Checkbutton(parent, text="Enable optional mangrove suitability layer", variable=self.soil_enabled_var).grid(row=8, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Checkbutton(parent, text="Allow migration without suitability layer", variable=self.migration_without_soil_var).grid(row=9, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Label(parent, text="A migrated cell becomes a new propagation source only after the maturation delay. Use 0 for a sensitivity test without a biological delay.", wraplength=360, foreground="#5d6b78").grid(row=10, column=0, columnspan=2, sticky="w", pady=(10, 0))
        for variable in (self.initial_year_var, self.final_year_var):
            variable.trace_add("write", lambda *_: self._refresh_sea_level_summary())
        self._on_sea_level_mode_changed()

    def _on_sea_level_mode_changed(self) -> None:
        trajectory_mode = self.sea_level_mode_var.get() == "trajectory"
        self.slr_entry.configure(state="disabled" if trajectory_mode else "normal")
        self.sea_level_path_entry.configure(state="readonly" if trajectory_mode else "disabled")
        for button in (self.sea_level_browse_button, self.sea_level_preview_button):
            button.configure(state="normal" if trajectory_mode else "disabled")
        self._refresh_sea_level_summary()

    def _save_sea_level_example(self) -> None:
        path = filedialog.asksaveasfilename(
            title=translate("Save CSV example", self.language_code),
            initialfile="sea_level_SYNTHETIC_example.csv", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            Path(path).write_text(TRAJECTORY_CSV_EXAMPLE, encoding="utf-8")
        except OSError as exc:
            self._show_message("showerror", "Sea-level forcing", str(exc))
            return
        self._show_message("showinfo", "Sea-level forcing",
                           "Synthetic example saved. Replace its values with documented projections before research use.")

    def _show_sea_level_help(self) -> None:
        window = tk.Toplevel(self)
        window.title(translate("Format and data sources", self.language_code))
        window.geometry("680x600")
        body = translate(
            "Create a spreadsheet with two columns named year and sea_level_mm. Enter calendar years and cumulative sea levels in millimetres, all relative to the same baseline. Save as CSV (UTF-8). Commas or semicolons are accepted as separators; use decimal commas only with semicolons.\n\n"
            "Use at least two different years in increasing order. The file must cover the entire simulation: for 2025–2100, decadal samples from 2020 to 2100 are sufficient. The model interpolates intermediate years and subtracts the initial-year level automatically.\n\n"
            "Data sources: obtain regional projections from the NASA/IPCC AR6 tool, the IPCC AR6 archive, or the Earth Engine catalog. Select one location or documented regional summary, one scenario, and one percentile per file. Copy the years and cumulative total sea-level values into the two required columns. Source downloads may need reformatting. Convert metres to millimetres by multiplying by 1000, or centimetres by 10.\n\n"
            "Use projected cumulative levels, not annual rates. Record the source, location, scenario, percentile, units, and reference period alongside the CSV. An observed annual trend can be entered directly in Constant rate.\n\n"
            "Save CSV example creates a synthetic file for learning the format. Replace all example values before using it in research. Each run exports the actual annual forcing in sea_level_forcing.csv.",
            self.language_code,
        )
        text = tk.Text(window, wrap="word", padx=14, pady=14)
        text.insert("1.0", body)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)
        links = ttk.Frame(window, padding=8)
        links.pack(fill="x")
        for label, url in [
            ("NASA / IPCC AR6", "https://sealevel.nasa.gov/data_tools/17"),
            ("IPCC AR6 archive", "https://doi.org/10.5281/zenodo.6382554"),
            ("Earth Engine", "https://developers.google.com/earth-engine/datasets/catalog/IPCC_AR6_SLP"),
        ]:
            ttk.Button(links, text=translate(label, self.language_code),
                       command=lambda address=url: webbrowser.open(address)).pack(side="left", padx=3)

    def _require_sea_level_trajectory(self) -> SeaLevelTrajectory:
        if self._sea_level_trajectory is None:
            path = self.sea_level_trajectory_path_var.get()
            if not path:
                raise ValueError("Choose a trajectory CSV before running the simulation.")
            self._sea_level_trajectory = SeaLevelTrajectory.from_csv(path)
        self._sea_level_trajectory.validate_period(int(self.initial_year_var.get()), int(self.final_year_var.get()))
        return self._sea_level_trajectory

    def _browse_sea_level_trajectory(self) -> None:
        path = filedialog.askopenfilename(
            title=translate("Choose trajectory CSV", self.language_code),
            filetypes=[("CSV", "*.csv"), (translate("All files", self.language_code), "*.*")],
        )
        if not path:
            return
        try:
            curve = SeaLevelTrajectory.from_csv(path)
        except Exception as exc:
            self._show_message("showerror", "Sea-level forcing", str(exc))
            return
        self._sea_level_trajectory = curve
        self.sea_level_trajectory_path_var.set(path)
        self._refresh_sea_level_summary()

    def _refresh_sea_level_summary(self) -> None:
        if self.sea_level_mode_var.get() != "trajectory":
            self.sea_level_summary_var.set("")
            return
        try:
            curve = self._require_sea_level_trajectory()
            first, last = int(self.initial_year_var.get()), int(self.final_year_var.get())
            levels = [curve.level_mm(year) for year in range(first, last + 1)]
            increments = np.diff(levels)
            template = translate("{first}–{last}: {rise:.1f} mm rise; annual increments {minimum:.2f}–{maximum:.2f} mm/year.", self.language_code)
            self.sea_level_summary_var.set(template.format(
                first=first, last=last, rise=levels[-1] - levels[0],
                minimum=float(increments.min()) if increments.size else 0,
                maximum=float(increments.max()) if increments.size else 0,
            ))
        except (ValueError, OSError) as exc:
            self.sea_level_summary_var.set(translate_runtime(str(exc), self.language_code))

    def _preview_sea_level_trajectory(self) -> None:
        try:
            curve = self._require_sea_level_trajectory()
            first, last = int(self.initial_year_var.get()), int(self.final_year_var.get())
        except (ValueError, OSError) as exc:
            self._show_message("showerror", "Sea-level forcing", str(exc))
            return
        window = tk.Toplevel(self)
        window.title(translate("Sea-level trajectory", self.language_code))
        figure = Figure(figsize=(7, 4), dpi=100, tight_layout=True)
        axis = figure.add_subplot(111)
        years = np.arange(first, last + 1)
        initial = curve.level_mm(first)
        axis.plot(years, [curve.level_mm(int(year)) - initial for year in years])
        axis.set_xlabel(translate("Calendar year", self.language_code))
        axis.set_ylabel(translate("Sea-level change since initial year (mm)", self.language_code))
        axis.grid(alpha=0.3)
        chart = FigureCanvasTkAgg(figure, master=window)
        chart.get_tk_widget().pack(fill="both", expand=True)
        chart.draw()

    def _build_center(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        self.center_notebook = ttk.Notebook(parent)
        self.center_notebook.grid(row=0, column=0, sticky="nsew")
        visual_tab = ttk.Frame(self.center_notebook, padding=(4, 4))
        console_tab = ttk.Frame(self.center_notebook, padding=(8, 8))
        results_tab = ttk.Frame(self.center_notebook, padding=(8, 8))
        trajectory_tab = ttk.Frame(self.center_notebook, padding=(4, 4))
        animation_tab = ttk.Frame(self.center_notebook, padding=(8, 8))
        source_tab = ttk.Frame(self.center_notebook, padding=(8, 8))
        self.center_notebook.add(visual_tab, text="Visualization")
        self.center_notebook.add(console_tab, text="Console")
        self.center_notebook.add(results_tab, text="Results")
        self.center_notebook.add(trajectory_tab, text="Trajectory")
        self.center_notebook.add(animation_tab, text="Animation")
        self.center_notebook.add(source_tab, text="Model rules")
        visual_tab.rowconfigure(0, weight=0)
        visual_tab.columnconfigure(0, weight=1)

        legend_bar = ttk.Frame(visual_tab, padding=(3, 2))
        legend_bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(legend_bar, text="Model states:", foreground="#5d6b78").grid(row=0, column=0, sticky="w", pady=(0, 2))
        legend_items = ttk.Frame(legend_bar)
        legend_items.grid(row=1, column=0, sticky="ew")
        self.model_legend_items = legend_items
        self._refresh_model_legend()

        visual_area = ttk.PanedWindow(visual_tab, orient="vertical")
        visual_area.grid(row=1, column=0, sticky="nsew")
        visual_tab.rowconfigure(1, weight=1)
        self.visual_area = visual_area
        self.visual_top_row = ttk.PanedWindow(visual_area, orient="horizontal")
        self.visual_bottom_row = ttk.PanedWindow(visual_area, orient="horizontal")
        visual_area.add(self.visual_top_row, weight=1)
        visual_area.add(self.visual_bottom_row, weight=1)

        self.visual_figures: dict[str, Figure] = {}
        self.visual_canvases: dict[str, FigureCanvasTkAgg] = {}
        self.visual_axes: dict[str, Any] = {}
        panel_specs = [
            ("initial", "Initial state", self.visual_top_row),
            ("elevation", "Elevation / relative surface", self.visual_top_row),
            ("current", "Current state", self.visual_bottom_row),
            ("trajectory", "Scenario trajectory", self.visual_bottom_row),
        ]
        for key, title, row in panel_specs:
            panel = ttk.LabelFrame(row, text=title, padding=(3, 3), labelanchor="n")
            panel.rowconfigure(0, weight=1)
            panel.columnconfigure(0, weight=1)
            figure = Figure(figsize=(5, 4), dpi=100, constrained_layout=True)
            axis = figure.add_subplot(111)
            canvas = FigureCanvasTkAgg(figure, master=panel)
            canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
            row.add(panel, weight=1)
            self.visual_figures[key] = figure
            self.visual_canvases[key] = canvas
            self.visual_axes[key] = axis

        self.ax_initial = self.visual_axes["initial"]
        self.ax_elevation = self.visual_axes["elevation"]
        self.ax_current = self.visual_axes["current"]
        self.ax_trajectory = self.visual_axes["trajectory"]
        self.ax_trajectory_area = self.ax_trajectory.twinx()
        self.ax_trajectory_area.patch.set_visible(False)
        controls = ttk.Frame(visual_tab, padding=(5, 5))
        controls.grid(row=2, column=0, sticky="ew")
        ttk.Button(controls, text="Run simulation", style="Accent.TButton", command=self.start_run).pack(side="left")
        ttk.Button(controls, text="Open results folder", command=self.open_results_folder).pack(side="left", padx=6)
        ttk.Button(controls, text="Reset layout", command=self._reset_visual_layout).pack(side="left", padx=(0, 6))
        self.progress_bar = ttk.Progressbar(controls, variable=self.progress_var, maximum=1, length=250)
        self.progress_bar.pack(side="left", padx=8)
        ttk.Label(controls, textvariable=self.run_status_var).pack(side="left", padx=5)
        ttk.Label(controls, textvariable=self.cells_var).pack(side="right", padx=5)
        ttk.Label(controls, textvariable=self.speed_var).pack(side="right", padx=5)

        self.console_text = tk.Text(console_tab, state="disabled", wrap="word", background="#f7f9fb", foreground="#243746")
        self.console_text.pack(fill="both", expand=True)
        ttk.Label(console_tab, text="Execution messages and annual summaries appear here while the simulation runs.", foreground="#5d6b78").pack(anchor="w", pady=(8, 0))

        results_tab.columnconfigure(0, weight=1)
        self.result_path_var = tk.StringVar(value="No simulation has been run in this project.")
        ttk.Label(results_tab, text="Project outputs", font=("Segoe UI", 11, "bold"), foreground="#17324d").grid(row=0, column=0, sticky="w")
        ttk.Label(results_tab, textvariable=self.result_path_var, wraplength=650).grid(row=1, column=0, sticky="w", pady=(8, 16))
        ttk.Label(results_tab, text="Each run stores annual state rasters, four independent figure series, a complete simulation table, transition summaries and metadata in its own timestamped folder.", wraplength=650, foreground="#5d6b78").grid(row=2, column=0, sticky="w")
        results_actions = ttk.Frame(results_tab)
        results_actions.grid(row=3, column=0, sticky="w", pady=(14, 0))
        ttk.Button(results_actions, text="Open simulation table", command=self.open_simulation_table).pack(side="left")
        ttk.Button(results_actions, text="Open results folder", command=self.open_results_folder).pack(side="left", padx=6)

        trajectory_tab.rowconfigure(0, weight=1)
        trajectory_tab.columnconfigure(0, weight=1)
        self.trajectory_figure = Figure(figsize=(9, 7), dpi=100)
        self.traj_area_ax = self.trajectory_figure.add_subplot(211)
        self.traj_change_ax = self.trajectory_figure.add_subplot(212, sharex=self.traj_area_ax)
        self.traj_area_km2_ax = self.traj_area_ax.twinx()
        self.traj_change_km2_ax = self.traj_change_ax.twinx()
        self.traj_area_km2_ax.patch.set_visible(False)
        self.traj_change_km2_ax.patch.set_visible(False)
        self.trajectory_figure.subplots_adjust(left=0.08, right=0.98, top=0.96, bottom=0.12, hspace=0.10)
        self.trajectory_canvas = FigureCanvasTkAgg(self.trajectory_figure, master=trajectory_tab)
        self.trajectory_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        animation_tab.rowconfigure(0, weight=1)
        animation_tab.columnconfigure(0, weight=1)
        animation_area = ttk.PanedWindow(animation_tab, orient="vertical")
        animation_area.grid(row=0, column=0, sticky="nsew")
        animation_tab.rowconfigure(0, weight=1)
        animation_top_row = ttk.PanedWindow(animation_area, orient="horizontal")
        animation_bottom_row = ttk.PanedWindow(animation_area, orient="horizontal")
        animation_area.add(animation_top_row, weight=1)
        animation_area.add(animation_bottom_row, weight=1)
        animation_panels = [
            ("state", "Cell state", animation_top_row),
            ("elevation", "Elevation / relative surface", animation_top_row),
            ("trajectory", "Mangrove trajectory", animation_bottom_row),
            ("change", "Net annual change", animation_bottom_row),
        ]
        for key, title, row in animation_panels:
            panel = ttk.LabelFrame(row, text=title, padding=(3, 3), labelanchor="n")
            panel.rowconfigure(0, weight=1)
            panel.columnconfigure(0, weight=1)
            label = ttk.Label(panel, text="Run a simulation to generate the annual preview.", anchor="center", justify="center")
            label.grid(row=0, column=0, sticky="nsew")
            row.add(panel, weight=1)
            self.animation_labels[key] = label
        self.animation_info_var = tk.StringVar(value="No annual figures generated yet.")
        ttk.Label(animation_tab, textvariable=self.animation_info_var, foreground="#5d6b78").grid(row=1, column=0, sticky="w", pady=(8, 4))
        animation_controls = ttk.Frame(animation_tab)
        animation_controls.grid(row=2, column=0, sticky="w")
        self.animation_year_var = tk.StringVar(value="Year —")
        ttk.Label(animation_controls, textvariable=self.animation_year_var, width=12).pack(side="left", padx=(0, 8))
        ttk.Button(animation_controls, text="Play", command=self.play_animation).pack(side="left")
        ttk.Button(animation_controls, text="Pause", command=self.pause_animation).pack(side="left", padx=4)
        ttk.Button(animation_controls, text="Previous", command=self.previous_animation_frame).pack(side="left")
        ttk.Button(animation_controls, text="Next", command=self.next_animation_frame).pack(side="left", padx=4)
        ttk.Button(animation_controls, text="Open state GIF", command=self.open_animation).pack(side="left", padx=(4, 0))
        ttk.Button(animation_controls, text="Export state GIF...", command=self.export_animation).pack(side="left", padx=4)
        ttk.Button(animation_controls, text="Open animations", command=self.open_animations_folder).pack(side="left")
        ttk.Button(animation_controls, text="Open annual figures", command=self.open_figures_folder).pack(side="left", padx=4)

        source_tab.rowconfigure(0, weight=1)
        source_tab.columnconfigure(0, weight=1)
        active_rules_tab = source_tab

        active_rules_tab.columnconfigure(0, weight=1)
        active_rules_tab.rowconfigure(3, weight=1)
        ttk.Label(
            active_rules_tab,
            text="This view lists the raster classes and rule profiles assigned in the current project.",
            wraplength=680,
            foreground="#5d6b78",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.rule_mapping_mode_var = tk.StringVar()
        ttk.Label(
            active_rules_tab,
            textvariable=self.rule_mapping_mode_var,
            font=("Segoe UI", 10, "bold"),
            foreground="#17324d",
        ).grid(row=1, column=0, sticky="w", pady=(0, 4))
        self.rule_summary_status_var = tk.StringVar()
        ttk.Label(
            active_rules_tab,
            textvariable=self.rule_summary_status_var,
            wraplength=680,
            foreground="#5d6b78",
        ).grid(row=2, column=0, sticky="w", pady=(0, 8))
        rule_table_frame = ttk.Frame(active_rules_tab)
        rule_table_frame.grid(row=3, column=0, sticky="nsew")
        rule_table_frame.rowconfigure(0, weight=1)
        rule_table_frame.columnconfigure(0, weight=1)
        self.rule_table = ttk.Treeview(
            rule_table_frame,
            columns=("source_code", "pixels", "model_class", "behavior"),
            show="headings",
            height=18,
        )
        for column, heading, width in (
            ("source_code", "Raster code", 100),
            ("pixels", "Pixels", 110),
            ("model_class", "Assigned model class", 210),
            ("behavior", "Transition profile", 230),
        ):
            self.rule_table.heading(column, text=heading)
            self.rule_table.column(column, width=width, minwidth=70, stretch=True)
        self.rule_table.grid(row=0, column=0, sticky="nsew")
        rule_table_scroll = ttk.Scrollbar(
            rule_table_frame, orient="vertical", command=self.rule_table.yview
        )
        rule_table_scroll.grid(row=0, column=1, sticky="ns")
        self.rule_table.configure(yscrollcommand=rule_table_scroll.set)

        self._refresh_rule_summary()
        self._draw_placeholder()

    def _draw_visual_canvases(self) -> None:
        """Refresh all four independent visualization canvases."""
        for canvas in self.visual_canvases.values():
            canvas.draw_idle()

    def _reset_visual_layout(self) -> None:
        """Restore an even 2x2 distribution after the user drags a divider."""
        def reset() -> None:
            height = max(self.visual_area.winfo_height(), 2)
            width = max(self.visual_top_row.winfo_width(), 2)
            self.visual_area.sashpos(0, height // 2)
            self.visual_top_row.sashpos(0, width // 2)
            self.visual_bottom_row.sashpos(0, width // 2)

        self.after_idle(reset)

    def _legend_handles(self) -> list[Patch]:
        catalog = self.inputs.metadata.get("model_state_catalog", {}) if self.inputs else {}
        return _model_legend_handles(catalog, self.language_code)

    def _refresh_rule_summary(self) -> None:
        """Show the current project's class assignments and behavior profiles."""
        table = getattr(self, "rule_table", None)
        if table is None:
            return
        for row in table.get_children():
            table.delete(row)

        custom_mode = self.class_mapping_mode_var.get() == "custom"
        mode_label = "Custom class mapping" if custom_mode else "Standard class mapping"
        self.rule_mapping_mode_var.set(translate(mode_label, self.language_code))

        custom_by_code = {
            int(item["code"]): item for item in self.custom_model_classes
        }
        used_custom_codes: set[int] = set()
        unassigned_codes: list[int] = []

        for code in sorted(self.class_counts):
            variable = self.class_vars.get(code)
            role = (
                self._canonical_role(variable.get())
                if variable is not None
                else self._canonical_role(self._initial_source_role(code))
            )
            if role == UNASSIGNED_ROLE:
                model_class = translate("Unassigned", self.language_code)
                behavior = translate("No rule assigned", self.language_code)
                unassigned_codes.append(code)
            elif role == "Exclude":
                model_class = translate("Exclude", self.language_code)
                behavior = translate("Excluded from simulation", self.language_code)
            elif role.startswith("custom:"):
                try:
                    custom_code = int(role.split(":", 1)[1])
                except ValueError:
                    custom_code = -1
                item = custom_by_code.get(custom_code)
                if item is None:
                    model_class = translate("Unassigned", self.language_code)
                    behavior = translate("No rule assigned", self.language_code)
                    unassigned_codes.append(code)
                else:
                    used_custom_codes.add(custom_code)
                    model_class = f"{item['name']} · {translate('State', self.language_code)} {custom_code}"
                    behavior = self._display_custom_behavior(
                        str(item.get("behavior", "fixed"))
                    )
            else:
                model_class = self._display_role(role)
                behavior = translate("Built-in rule set", self.language_code)

            table.insert(
                "",
                "end",
                values=(code, f"{self.class_counts[code]:,}", model_class, behavior),
            )

        for code, item in sorted(custom_by_code.items()):
            if code in used_custom_codes:
                continue
            table.insert(
                "",
                "end",
                values=(
                    "—",
                    "—",
                    f"{item['name']} · {translate('State', self.language_code)} {code}",
                    self._display_custom_behavior(str(item.get("behavior", "fixed"))),
                ),
            )

        if not self.class_counts:
            status = "Inspect a categorical raster to see its class assignments here."
            if self.custom_model_classes:
                status = "No raster codes have been inspected yet. The custom classes below are defined and ready for assignment."
        elif custom_mode and unassigned_codes:
            status = "Custom mode starts with no assignments. Assign every raster code to a custom class or choose Exclude before loading inputs."
        elif custom_mode:
            status = "Each raster code follows the behavior profile shown for its assigned custom class."
        else:
            status = "Each raster code follows its assigned standard model class."
        self.rule_summary_status_var.set(translate(status, self.language_code))

    def _build_right(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Live run monitor", font=("Segoe UI", 11, "bold"), anchor="center").grid(row=0, column=0, sticky="ew", pady=(5, 8))
        self.monitor_text = tk.Text(parent, width=34, height=16, state="disabled", wrap="word", background=UI_COLORS["surface"], foreground=UI_COLORS["text"], relief="solid", borderwidth=1, highlightthickness=0)
        self.monitor_text.grid(row=1, column=0, sticky="nsew")
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="Net change by class", font=("Segoe UI", 11, "bold"), anchor="center").grid(row=2, column=0, sticky="ew", pady=(12, 5))
        ttk.Label(parent, text="Loss ↓     0     ↑ Gain", anchor="center", foreground=UI_COLORS["muted"]).grid(row=3, column=0, sticky="ew", pady=(0, 2))
        self.class_chart = tk.Canvas(parent, height=300, background=UI_COLORS["surface"], highlightbackground=UI_COLORS["border"], highlightthickness=1, bd=0)
        self.class_chart.grid(row=4, column=0, sticky="ew")
        self.class_chart.bind("<Configure>", lambda _event: self._redraw_class_chart())
        self.class_bar_colors = {
            "mangrove": CHART_BEHAVIOR_COLORS["mangrove"],
            "migrated_mangrove": CHART_BEHAVIOR_COLORS["migrated_mangrove"],
            "flooded_mangrove": CHART_BEHAVIOR_COLORS["flooded_mangrove"],
            "vegetation": CHART_BEHAVIOR_COLORS["natural_vegetation"],
            "water": CHART_BEHAVIOR_COLORS["water"],
            "anthropized": CHART_BEHAVIOR_COLORS["anthropized"],
        }
        self.class_bar_labels = {
            "mangrove": translate("Mangrove", self.language_code),
            "migrated_mangrove": translate("Migrated mangrove", self.language_code),
            "flooded_mangrove": translate("Flooded", self.language_code),
            "vegetation": translate("Vegetation", self.language_code),
            "water": translate("Water", self.language_code),
            "anthropized": translate("Developed", self.language_code),
        }
        self.class_change_values: dict[str, int] = {key: 0 for key in self.class_bar_colors}
        self.class_current_values: dict[str, int] = {key: 0 for key in self.class_bar_colors}
        ttk.Label(parent, text="Each bar shows the net change from the initial state. Gains rise above zero and losses fall below zero.", wraplength=260, foreground=UI_COLORS["muted"]).grid(row=5, column=0, sticky="w", pady=(8, 0))

    def _draw_placeholder(self) -> None:
        for ax in self.visual_axes.values():
            ax.clear()
            ax.text(0.5, 0.5, translate("Load input rasters to begin", self.language_code), ha="center", va="center", transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
        self.ax_trajectory_area.clear()
        self.ax_trajectory_area.set_visible(False)
        self.ax_trajectory_area.set_yticks([])
        for ax in (self.traj_area_ax, self.traj_change_ax):
            ax.clear()
            ax.text(0.5, 0.5, translate("Run a simulation to build the trajectory", self.language_code), ha="center", va="center", transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
        self.traj_area_km2_ax.clear()
        self.traj_area_km2_ax.set_visible(False)
        self.traj_area_km2_ax.set_yticks([])
        self.traj_change_km2_ax.clear()
        self.traj_change_km2_ax.set_visible(False)
        self.traj_change_km2_ax.set_yticks([])
        self._draw_visual_canvases()
        self.trajectory_canvas.draw_idle()
        if hasattr(self, "animation_labels"):
            self.pause_animation()
            self.animation_component_paths.clear()
            self.animation_component_images.clear()
            self.animation_frame_index = 0
            self.animation_year_var.set("Year —")
            self.animation_info_var.set("No annual figures generated yet.")
            for label in self.animation_labels.values():
                label.configure(image="", text=translate("Run a simulation to generate the annual preview.", self.language_code))
                label.image = None

    def _browse(self, variable: tk.StringVar, label: str) -> None:
        path = filedialog.askopenfilename(
            title=f"{translate('Select', self.language_code)} {translate(label, self.language_code)}",
            filetypes=[(translate("GeoTIFF", self.language_code), "*.tif *.tiff"), (translate("All files", self.language_code), "*.*")],
        )
        if path:
            variable.set(path)
            if variable is self.mapbiomas_var:
                self.inspect_mapbiomas()

    def inspect_mapbiomas(self) -> None:
        path = Path(self.mapbiomas_var.get().strip())
        if not path.exists():
            self._show_message("showerror", "Land-cover inspection", "Select a valid categorical land-cover GeoTIFF first.")
            return
        try:
            band = int(self.band_var.get())
            with rasterio.open(path) as src:
                if band < 1 or band > src.count:
                    raise ValueError(f"Band must be between 1 and {src.count}.")
                data = src.read(band, masked=True)
                mask_path = self.mask_var.get().strip()
                if mask_path:
                    with rasterio.open(mask_path) as mask_src:
                        if mask_src.shape != src.shape or mask_src.crs != src.crs or not mask_src.transform.almost_equals(src.transform):
                            raise ValueError("The study-area mask must share shape, CRS and transform with the land-cover raster.")
                        study_mask = np.asarray(mask_src.read(1, masked=True).filled(0)) != 0
                    values_array = np.asarray(data.filled(0))
                    if np.issubdtype(values_array.dtype, np.floating):
                        values_array = np.where(np.isfinite(values_array), values_array, 0)
                    values_array[~study_mask] = 0
                    values, counts = np.unique(values_array, return_counts=True)
                else:
                    values_array = np.asarray(data.compressed())
                    if np.issubdtype(values_array.dtype, np.floating):
                        values_array = values_array[np.isfinite(values_array)]
                    values, counts = np.unique(values_array, return_counts=True)
            self.class_counts = {int(code): int(count) for code, count in zip(values, counts) if int(code) != 0}
            self._rebuild_class_rows()
            scope = "in study area" if self.mask_var.get().strip() else "in raster"
            self.run_status_var.set(f"Found {len(self.class_counts)} source classes {scope}")
        except Exception as exc:
            self._show_message("showerror", "Land-cover inspection", str(exc))

    def reproject_inputs(self) -> None:
        """Create aligned copies of the selected rasters on a target CRS."""
        try:
            land_cover = Path(self.land_cover_var.get().strip())
            elevation = Path(self.elevation_var.get().strip())
            if not land_cover.exists() or not elevation.exists():
                raise FileNotFoundError("Select valid land-cover and elevation rasters first.")
            target_text = self.target_crs_var.get().strip()
            target_crs = _resolve_target_crs(target_text)
            resolution_text = self.target_resolution_var.get().strip()
            resolution = float(resolution_text) if resolution_text else None
            if resolution is not None and resolution <= 0:
                raise ValueError("Target resolution must be positive.")
            band = int(self.land_cover_band_var.get())

            with rasterio.open(land_cover) as source:
                if source.crs is None:
                    raise ValueError(f"The land-cover raster has no CRS metadata: {land_cover.name}")
                _require_transformable_crs(source.crs, land_cover.name)
                transform_kwargs: dict[str, Any] = {}
                if resolution is not None:
                    transform_kwargs["resolution"] = (resolution, resolution)
                target_transform, target_width, target_height = calculate_default_transform(
                    source.crs,
                    target_crs,
                    source.width,
                    source.height,
                    *source.bounds,
                    **transform_kwargs,
                )
            target_width, target_height = int(target_width), int(target_height)
            if target_width < 1 or target_height < 1:
                raise ValueError("The target CRS produced an empty raster grid.")

            if self.project_file is not None:
                output_dir = self.project_file.parent / "prepared_inputs"
            else:
                chosen = filedialog.askdirectory(title=translate("Choose a folder for prepared input rasters", self.language_code))
                if not chosen:
                    return
                output_dir = Path(chosen) / "prepared_inputs"
            output_dir.mkdir(parents=True, exist_ok=True)
            land_cover_out = _reproject_raster_to_grid(
                land_cover,
                output_dir / f"{land_cover.stem}_reprojected.tif",
                band=band,
                target_crs=target_crs,
                target_transform=target_transform,
                target_width=target_width,
                target_height=target_height,
                resampling=Resampling.nearest,
                target_nodata=0,
            )
            elevation_out = _reproject_raster_to_grid(
                elevation,
                output_dir / f"{elevation.stem}_reprojected.tif",
                band=1,
                target_crs=target_crs,
                target_transform=target_transform,
                target_width=target_width,
                target_height=target_height,
                resampling=Resampling.bilinear,
                target_nodata=-9999.0,
            )
            self.land_cover_var.set(str(land_cover_out))
            self.elevation_var.set(str(elevation_out))
            for variable, label in ((self.mask_var, "mask"), (self.soil_var, "soil")):
                source_path = Path(variable.get().strip()) if variable.get().strip() else None
                if source_path is None:
                    continue
                if not source_path.exists():
                    raise FileNotFoundError(source_path)
                output = _reproject_raster_to_grid(
                    source_path,
                    output_dir / f"{source_path.stem}_reprojected_{label}.tif",
                    band=1,
                    target_crs=target_crs,
                    target_transform=target_transform,
                    target_width=target_width,
                    target_height=target_height,
                    resampling=Resampling.nearest,
                    target_nodata=0,
                )
                variable.set(str(output))
            target_label = target_crs.to_string()
            self.target_crs_var.set(target_text)
            self.expected_crs_var.set(target_label)
            self.run_status_var.set("Prepared aligned rasters; validate and load inputs")
            self.inspect_mapbiomas()
            self._show_message("showinfo",
                "Inputs prepared",
                f"Aligned copies were created in:\n{output_dir}\n\nOriginal rasters were not modified. Review the class mapping and click Validate and load inputs.",
            )
        except Exception as exc:
            self._show_message("showerror", "Reprojection", f"Unable to reproject the inputs: {exc}")

    def _rebuild_class_rows(self, *, preserve_current: bool = False) -> None:
        previous = (
            {code: variable.get() for code, variable in self.class_vars.items()}
            if preserve_current else {}
        )
        for child in self.class_inner.winfo_children():
            child.destroy()
        header = ttk.Frame(self.class_inner)
        header.pack(fill="x")
        ttk.Label(header, text="Code", width=8).pack(side="left")
        ttk.Label(header, text="Pixels", width=12).pack(side="left")
        ttk.Label(header, text="Model class").pack(side="left")
        self.class_vars.clear()
        self._class_combos.clear()
        role_options = self._role_options()
        for code in sorted(self.class_counts):
            row = ttk.Frame(self.class_inner)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=str(code), width=8).pack(side="left")
            ttk.Label(row, text=f"{self.class_counts[code]:,}", width=12).pack(side="left")
            default_role = self._initial_source_role(code)
            saved_role = previous.get(code, default_role)
            if saved_role not in role_options:
                saved_role = default_role
            var = tk.StringVar(value=saved_role)
            var.trace_add("write", lambda *_args: self._refresh_rule_summary())
            self.class_vars[code] = var
            combo = ttk.Combobox(
                row,
                textvariable=var,
                values=role_options,
                state="readonly",
                width=27,
            )
            combo.pack(side="left", fill="x", expand=True)
            self._class_combos[code] = combo
        self._capture_static_ui_text()
        self._apply_language()

    def _mapping_from_ui(
        self,
    ) -> tuple[dict[str, list[int]], list[int], dict[int, str], dict[int, list[int]]]:
        mapping: dict[str, list[int]] = {key: [] for key in DEFAULT_LAND_COVER_MAPPING}
        excluded: list[int] = []
        roles: dict[int, str] = {}
        custom_mapping = {int(item["code"]): [] for item in self.custom_model_classes}
        for code, var in self.class_vars.items():
            role = self._canonical_role(var.get())
            roles[code] = role
            if role == "Exclude":
                excluded.append(code)
            elif role == UNASSIGNED_ROLE:
                continue
            elif role.startswith("custom:"):
                custom_code = int(role.split(":", 1)[1])
                custom_mapping.setdefault(custom_code, []).append(code)
            elif role in ROLE_TO_MODEL:
                mapping[ROLE_TO_MODEL[role]].append(code)
        return mapping, excluded, roles, custom_mapping

    def load_inputs(self) -> None:
        try:
            mb = Path(self.mapbiomas_var.get().strip())
            dem = Path(self.elevation_var.get().strip())
            if not mb.exists() or not dem.exists():
                raise FileNotFoundError("The land-cover and elevation paths must be valid.")
            band = int(self.band_var.get())
            year_text = self.year_var.get().strip()
            year = int(year_text) if year_text else None
            expected = self.expected_crs_var.get().strip()
            mapping, excluded, roles, custom_mapping = self._mapping_from_ui()
            _validate_class_assignments(
                roles,
                mode=self.class_mapping_mode_var.get(),
                custom_classes=self.custom_model_classes,
                language=self.language_code,
            )
            soil = Path(self.soil_var.get().strip()) if self.soil_var.get().strip() else None
            soil_enabled = bool(self.soil_enabled_var.get() and soil is not None)
            inputs = load_raster_inputs(
                mb,
                dem,
                mask_path=self.mask_var.get().strip() or None,
                soil_path=soil,
                soil_enabled=soil_enabled,
                land_cover_band=band,
                land_cover_year=year,
                mapping=mapping,
                custom_class_mapping=custom_mapping,
                custom_classes=self.custom_model_classes,
                class_mapping_mode=self.class_mapping_mode_var.get(),
                exclude_source_codes=excluded,
            )
            _validate_class_coverage(
                roles,
                inputs.metadata["land_cover"]["mapping"]["source_code_counts_valid"],
                mode=self.class_mapping_mode_var.get(),
                language=self.language_code,
            )
            source_crs = str(inputs.metadata["land_cover"]["crs"] or "Unknown")
            if expected and not _crs_equivalent(expected, source_crs):
                raise ValueError(f"Expected CRS {expected} does not match input CRS {source_crs}; reproject inputs before loading.")
            self.inputs = inputs
            self.initial_class_counts = dict(inputs.grid.class_counts())
            self.source_crs_var.set(source_crs)
            self.expected_crs_var.set(source_crs)
            self.datum_var.set("See CRS WKT / source metadata")
            self.project_status_var.set(f"Loaded {inputs.n_cells:,} cells")
            self.run_status_var.set("Inputs validated")
            self._update_class_bars(self.initial_class_counts)
            self._draw_input_maps()
        except Exception as exc:
            self.inputs = None
            self._show_message("showerror", "Input validation", str(exc))

    def _make_display(self, land_cover_state: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        values = np.asarray(land_cover_state, dtype=np.int32)
        return self._make_display_values(values, dtype=np.int32, fill_value=0)

    def _make_display_values(
        self,
        values: np.ndarray,
        *,
        dtype: Any = np.float64,
        fill_value: float | int = np.nan,
    ) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        assert self.inputs is not None
        full = np.full(self.inputs.raster_shape, fill_value, dtype=dtype)
        full[self.inputs.valid_rows, self.inputs.valid_cols] = np.asarray(values, dtype=dtype)
        rows, cols = np.where(self.inputs.valid_mask)
        pad = 10
        r0, r1 = max(int(rows.min()) - pad, 0), min(int(rows.max()) + pad + 1, full.shape[0])
        c0, c1 = max(int(cols.min()) - pad, 0), min(int(cols.max()) + pad + 1, full.shape[1])
        crop = full[r0:r1, c0:c1]
        stride = max(1, int(max(crop.shape) / 700))
        return crop[::stride, ::stride], (r0, r1, c0, c1)

    def _show_map(self, ax: Any, land_cover_state: np.ndarray, title: str) -> None:
        image, _ = self._make_display(land_cover_state)
        state_catalog = self.inputs.metadata.get("model_state_catalog", {}) if self.inputs else {}
        cmap, norm = _model_colormap(state_catalog)
        ax.clear()
        ax.imshow(image, cmap=cmap, norm=norm, interpolation="nearest")
        # The surrounding LabelFrame supplies the panel title.
        ax.set_title("")
        parts = str(title).rsplit("—", 1)
        if len(parts) == 2 and parts[-1].strip().isdigit():
            ax.text(
                0.98, 0.03, parts[-1].strip(), transform=ax.transAxes,
                ha="right", va="bottom", fontsize=10, color="#1f2933",
                bbox={"facecolor": "white", "alpha": 0.78, "pad": 2, "edgecolor": "none"},
            )
        ax.set_xticks([])
        ax.set_yticks([])

    def _show_elevation(self, ax: Any, elevation: np.ndarray, title: str) -> None:
        image, _ = self._make_display_values(elevation, dtype=np.float64, fill_value=np.nan)
        ax.clear()
        finite = image[np.isfinite(image)]
        if finite.size:
            vmin, vmax = float(np.nanmin(finite)), float(np.nanmax(finite))
            if np.isclose(vmin, vmax):
                vmax = vmin + 1e-9
            ax.imshow(image, cmap="terrain", interpolation="nearest", vmin=vmin, vmax=vmax)
            ax.text(
                0.02,
                0.02,
                f"range: {vmin:.3f}–{vmax:.3f}",
                transform=ax.transAxes,
                fontsize=7,
                color="black",
                bbox={"facecolor": "white", "alpha": 0.75, "pad": 2},
            )
        else:
            ax.imshow(image, cmap="terrain", interpolation="nearest")
        # The surrounding LabelFrame supplies the panel title.
        ax.set_title("")
        ax.set_xticks([])
        ax.set_yticks([])

    def _draw_input_maps(self) -> None:
        assert self.inputs is not None
        self._show_map(self.ax_initial, self.inputs.grid.land_cover_state, translate_runtime(f"Initial state — {self.year_var.get()}", self.language_code))
        self._show_elevation(self.ax_elevation, self.inputs.grid.relative_elevation, translate("Elevation / relative surface", self.language_code))
        self._show_map(self.ax_current, self.inputs.grid.land_cover_state, translate_runtime("Current state — not started", self.language_code))
        self.ax_trajectory.clear()
        self.ax_trajectory.set_xlabel(translate("Calendar year", self.language_code))
        self.ax_trajectory.set_ylabel(translate("Cells", self.language_code))
        self.ax_trajectory_area.clear()
        self.ax_trajectory_area.set_visible(False)
        self.ax_trajectory_area.set_ylabel("")
        self.ax_trajectory_area.set_yticks([])
        self._draw_visual_canvases()

    def _parameters(self) -> ModelParameters:
        initial = int(self.initial_year_var.get())
        final = int(self.final_year_var.get())
        if final <= initial:
            raise ValueError("Final calendar year must be greater than initial year.")
        accretion_text = self.accretion_var.get().strip()
        accretion = float(accretion_text) if accretion_text else None
        migration_maturity_years = int(self.migration_maturity_var.get())
        if migration_maturity_years < 0:
            raise ValueError("Migration maturation delay must be zero or greater.")
        soil_enabled = bool(self.soil_enabled_var.get() and self.soil_var.get().strip())
        curve = self._require_sea_level_trajectory() if self.sea_level_mode_var.get() == "trajectory" else None
        return ModelParameters(
            start=1,
            final_time=final - initial,
            tide_height=float(self.tide_height_var.get()),
            # The core preserves the Lua convention (metres per model step).
            # The desktop field is deliberately expressed in mm per year.
            sea_level_rise_rate=float(self.slr_var.get()) / 1000.0 if curve is None else 0.0,
            sea_level_trajectory=curve,
            sea_level_reference_year=initial,
            legacy_lua_accretion_typo=False,
            allow_migration_without_soil=(not soil_enabled) and bool(self.migration_without_soil_var.get()),
            accretion_rate_mm=accretion,
            migration_maturity_years=migration_maturity_years,
        )

    def start_run(self) -> None:
        if self.running:
            self._show_message("showinfo", "Simulation", "A simulation is already running.")
            return
        if self.inputs is None:
            self.load_inputs()
        if self.inputs is None:
            return
        try:
            parameters = self._parameters()
            block_size = int(self.block_size_var.get())
            if block_size < 1:
                raise ValueError("Block size must be positive.")
            if self.engine_var.get() == "dissmodel" and not DISSMODEL_AVAILABLE:
                raise RuntimeError(
                    "This installation was built without DissModel. Use the "
                    "BRMANGUE_Studio_DissModel executable or install DissModel."
                )
            if self.project_file is None:
                chosen = filedialog.askdirectory(title=translate("Choose project folder for results", self.language_code))
                if not chosen:
                    return
                self.project_file = Path(chosen) / "brmangue_project.json"
                self.project_status_var.set(f"Project: {self.project_file.parent}")
            self.save_project()
            run_id = datetime.now().strftime("run_%Y%m%dT%H%M%S")
            self.run_dir = self.project_file.parent / "results" / run_id
            self.run_dir.mkdir(parents=True, exist_ok=True)
            steps = parameters.final_time - parameters.start + 1
            # Refresh the visual panels after every simulated calendar year.
            # Raster outputs are written annually by the runner as before.
            self.render_stride = 1
            self.progress_var.set(0)
            self.trajectory_records.clear()
            self.last_state = None
            self.annual_figure_paths.clear()
            self.animation_component_paths.clear()
            self.animation_component_images.clear()
            self.animation_paths.clear()
            self.simulation_table_path = None
            self.animation_path = None
            self.animation_frames = []
            self.animation_frame_index = 0
            self.animation_playing = True
            if self.animation_after_id is not None:
                self.after_cancel(self.animation_after_id)
                self.animation_after_id = None
            self.animation_info_var.set("Generating annual figures and GIF…")
            for label in self.animation_labels.values():
                label.configure(image="", text=translate("Simulation running…", self.language_code))
                label.image = None
            self.animation_year_var.set("Year —")
            self.running = True
            self.run_started = time.perf_counter()
            self.model_elapsed_seconds = None
            self.total_elapsed_seconds = None
            self.run_status_var.set("Running…")
            self.cells_var.set("Cells processed: 0")
            self.speed_var.set("Speed: —")
            self._set_monitor("Simulation started.\nElapsed: 0 s\n")
            code_roles = {
                code: self._canonical_role(var.get())
                for code, var in self.class_vars.items()
            }
            callback = lambda event: self.message_queue.put(("step", event))
            initial_year = int(self.initial_year_var.get())
            engine = self.engine_var.get()
            land_cover_path = self.land_cover_var.get()
            land_cover_band = int(self.land_cover_band_var.get())
            self.worker = threading.Thread(
                target=self._run_worker,
                args=(parameters, block_size, steps, callback, code_roles, initial_year, engine, land_cover_path, land_cover_band, self.language_code),
                daemon=True,
            )
            self.worker.start()
        except Exception as exc:
            self._show_message("showerror", "Simulation", str(exc))

    def _run_worker(
        self,
        parameters: ModelParameters,
        block_size: int,
        steps: int,
        callback: Any,
        code_roles: dict[int, str],
        initial_year: int,
        engine: str,
        land_cover_path: str,
        land_cover_band: int,
        language_code: str,
    ) -> None:
        assert self.inputs is not None
        assert self.run_dir is not None
        try:
            trajectory = run_raster_simulation(
                self.inputs,
                self.run_dir,
                parameters,
                initial_year=initial_year,
                engine=engine,
                block_size=block_size,
                dissmodel_runner="blocks",
                show_dissmodel_chart=False,
                save_annual_states=True,
                step_callback=callback,
            )
            model_elapsed_seconds: float | None = None
            metadata_path = self.run_dir / "metadata.json"
            if metadata_path.exists():
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    model_elapsed_seconds = float(metadata.get("elapsed_seconds"))
                except (OSError, TypeError, ValueError):
                    model_elapsed_seconds = None
            final_year = int(initial_year + parameters.final_time)
            final_path = self.run_dir / f"final_state_{final_year}.tif"
            final_state = None
            if final_path.exists():
                with rasterio.open(final_path) as src:
                    final_state = src.read(1)[self.inputs.valid_rows, self.inputs.valid_cols]
            if final_state is not None:
                _write_transition_report(
                    land_cover_path,
                    land_cover_band,
                    self.inputs,
                    final_state,
                    code_roles,
                    self.run_dir / "transition_by_land_cover_code.csv",
                )
            self.message_queue.put(("postprocess", "Simulation complete. Generating annual figures and GIF in the background…"))
            annual_paths = _generate_annual_figures(self.inputs, self.run_dir, trajectory, language_code)
            animation_path = _generate_animation(annual_paths, self.run_dir)
            animation_paths = _generate_component_animations(self.run_dir, annual_paths)
            spreadsheet_path = _write_simulation_spreadsheet(self.inputs, self.run_dir, trajectory)
            self.message_queue.put(
                (
                    "done",
                    {
                        "trajectory": trajectory,
                        "annual_figure_paths": annual_paths,
                        "animation_path": animation_path,
                        "animation_paths": animation_paths,
                        "spreadsheet_path": spreadsheet_path,
                        "model_elapsed_seconds": model_elapsed_seconds,
                        "total_elapsed_seconds": time.perf_counter() - self.run_started,
                    },
                )
            )
        except Exception as exc:
            self.message_queue.put(("error", f"{type(exc).__name__}: {exc}"))

    def _poll_messages(self) -> None:
        # Process one simulation event per UI turn.  Draining the entire queue
        # in one callback made rapid runs appear to jump between years because
        # Tk could not repaint the map until all queued frames were handled.
        try:
            kind, payload = self.message_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if kind == "step":
                self._handle_step(payload)
            elif kind == "postprocess":
                self.run_status_var.set(str(payload))
                elapsed = time.perf_counter() - getattr(self, "run_started", time.perf_counter())
                self._set_monitor(f"{payload}\nElapsed: {_format_duration(elapsed)}")
            elif kind == "done":
                self.running = False
                result = payload if isinstance(payload, dict) else {"trajectory": payload}
                trajectory = result.get("trajectory")
                if isinstance(trajectory, pd.DataFrame):
                    self.trajectory_records = trajectory.to_dict(orient="records")
                self.annual_figure_paths = [Path(path) for path in result.get("annual_figure_paths", [])]
                animation_path = result.get("animation_path")
                self.animation_path = Path(animation_path) if animation_path else None
                self.animation_paths = {
                    str(component): Path(path)
                    for component, path in result.get("animation_paths", {}).items()
                    if path
                }
                spreadsheet_path = result.get("spreadsheet_path")
                self.simulation_table_path = Path(spreadsheet_path) if spreadsheet_path else None
                self.model_elapsed_seconds = result.get("model_elapsed_seconds")
                self.total_elapsed_seconds = result.get("total_elapsed_seconds")
                self.run_status_var.set(f"Finished — {self.run_dir}")
                if hasattr(self, "result_path_var") and self.run_dir is not None:
                    self.result_path_var.set(str(self.run_dir))
                self._draw_trajectory()
                if self.animation_path is not None:
                    self.animation_info_var.set(
                        f"Four independent animations and figures saved  |  {len(self.annual_figure_paths)} annual frames"
                    )
                self._load_animation()
                model_time = _format_duration(self.model_elapsed_seconds)
                total_time = _format_duration(self.total_elapsed_seconds)
                performance_text = ""
                if self.run_dir is not None:
                    metadata_path = self.run_dir / "metadata.json"
                    try:
                        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                        performance = metadata.get("performance", {})
                        performance_text = (
                            f"Peak process RAM: {_format_bytes(performance.get('peak_rss_bytes'))}\n"
                            f"Throughput: {float(performance.get('cell_updates_per_second', 0.0)) / 1_000_000:.3f}M cell-updates/s\n"
                            f"Output size: {_format_bytes(performance.get('output_size_bytes'))}\n"
                        )
                    except (OSError, TypeError, ValueError, json.JSONDecodeError):
                        performance_text = ""
                self._set_monitor(
                    self._monitor_text()
                    + "\nSimulation finished.\n"
                    + f"Model time: {model_time}\n"
                    + f"Total run time: {total_time}\n"
                    + performance_text
                )
            elif kind == "error":
                self.running = False
                self.run_status_var.set("Failed")
                elapsed = time.perf_counter() - getattr(self, "run_started", time.perf_counter())
                self._set_monitor(f"Simulation failed after {_format_duration(elapsed)}.\n")
                self._show_message("showerror", "Simulation", payload)
        self.after(40, self._poll_messages)

    def _handle_step(self, event: dict[str, Any]) -> None:
        summary = dict(event["summary"])
        self.last_state = np.asarray(event["land_cover_state"], dtype=np.uint16)
        self.trajectory_records.append(summary)
        completed = len(self.trajectory_records)
        total = max(int(self._parameters().final_time), 1)
        self.progress_bar.configure(maximum=total)
        self.progress_var.set(completed)
        self.cells_var.set(f"Cells processed: {int(event['processed_cells']):,}")
        elapsed = max((time.perf_counter() - getattr(self, "run_started", time.perf_counter())), 1e-6)
        self.speed_var.set(f"Speed: {int(event['processed_cells'] / elapsed):,} cells/s")
        self._update_class_bars(summary)
        self._set_monitor(self._format_monitor(summary))
        total = max(int(self._parameters().final_time), 1)
        if completed % self.render_stride == 0 or completed >= total:
            self._show_map(self.ax_current, self.last_state, f"Current state — {event['calendar_year']}")
            self._draw_trajectory()
            self._draw_visual_canvases()

    def _draw_trajectory(self) -> None:
        if not self.trajectory_records:
            return
        frame = _area_frame(self.inputs, pd.DataFrame(self.trajectory_records)) if self.inputs is not None else pd.DataFrame(self.trajectory_records)
        self.ax_trajectory.clear()
        self.ax_trajectory_area.clear()
        self.ax_trajectory_area.set_visible(False)
        for column, label, color in [
            ("mangrove", translate("Mangrove", self.language_code), "#006d2c"),
            ("migrated_mangrove", translate("Migrated mangrove", self.language_code), "#7b3294"),
            ("flooded_mangrove", translate("Flooded mangrove", self.language_code), "#e34a33"),
        ]:
            if column in frame:
                self.ax_trajectory.plot(frame["calendar_year"], frame[column], label=label, color=color, linewidth=2)
        self.ax_trajectory.set_xlabel(translate("Calendar year", self.language_code))
        self.ax_trajectory.set_ylabel(translate("Cells", self.language_code))
        self.ax_trajectory.grid(alpha=0.25)
        self.ax_trajectory.legend(fontsize=8)
        # Area equivalents remain available in trajectory.csv and the monitor,
        # but are intentionally omitted from the chart to keep the figure clear.

        self.traj_area_ax.clear()
        self.traj_area_km2_ax.clear()
        for column, label, color in [
            ("mangrove", translate("Mangrove cells", self.language_code), "#006d2c"),
            ("migrated_mangrove", translate("Migrated mangrove", self.language_code), "#7b3294"),
            ("flooded_mangrove", translate("Flooded mangrove", self.language_code), "#e34a33"),
        ]:
            if column in frame:
                self.traj_area_ax.plot(frame["calendar_year"], frame[column], label=label, color=color, linewidth=2)
        self.traj_area_ax.set_title(translate("Mangrove trajectory", self.language_code))
        self.traj_area_ax.set_ylabel(translate("Cells", self.language_code))
        self.traj_area_ax.grid(alpha=0.25)
        self.traj_area_ax.legend(loc="best", fontsize=8)
        self.traj_area_ax.tick_params(labelbottom=False)
        self.traj_area_km2_ax.set_visible(False)

        self.traj_change_ax.clear()
        self.traj_change_km2_ax.clear()
        years = frame["calendar_year"].to_numpy()
        if "annual_net_change" in frame:
            net_change = frame["annual_net_change"].fillna(0).to_numpy()
        else:
            gains = frame.get("annual_gain", pd.Series(np.zeros(len(frame)))).to_numpy()
            losses = frame.get("annual_loss", pd.Series(np.zeros(len(frame)))).to_numpy()
            net_change = gains - losses
        self.traj_change_ax.bar(years, np.maximum(net_change, 0), color="#72b66b", label=translate("Net annual gain", self.language_code), width=0.72)
        self.traj_change_ax.bar(years, np.minimum(net_change, 0), color="#ef3b2c", label=translate("Net annual loss", self.language_code), width=0.72)
        self.traj_change_km2_ax.set_visible(False)
        self.traj_change_ax.axhline(0, color="#333333", linewidth=0.8)
        self.traj_change_ax.set_xlabel(translate("Calendar year", self.language_code))
        self.traj_change_ax.set_ylabel(translate("Net annual change (cells)", self.language_code))
        self.traj_change_ax.grid(alpha=0.2, axis="y")
        self.traj_change_ax.legend(loc="best", fontsize=8, ncol=2)
        self.trajectory_canvas.draw_idle()

    def _save_annual_figure(self, summary: dict[str, Any]) -> None:
        """Save the current year as four independent figure files."""
        if self.run_dir is None or self.inputs is None or self.last_state is None:
            return
        year = int(summary.get("calendar_year", 0))
        frame = pd.DataFrame(self.trajectory_records)
        path = _save_annual_figure_file(
            self.inputs,
            self.run_dir,
            self.last_state,
            frame,
            year,
            self.language_code,
            state_catalog=self.inputs.metadata.get("model_state_catalog", {}),
        )
        self.annual_figure_paths.append(path)

    def _create_animation(self) -> None:
        if self.run_dir is None:
            return
        frames = [path for path in self.annual_figure_paths if path.exists()]
        if not frames:
            self.animation_info_var.set("No annual figures were generated.")
            return
        self.animation_path = _generate_animation(frames, self.run_dir)
        self.animation_paths = _generate_component_animations(self.run_dir, frames)
        self.animation_info_var.set(f"Four independent animations and figures saved  |  {len(frames)} annual frames")
        self._load_animation()

    def _load_animation(self) -> None:
        if self.run_dir is None:
            return
        if self.animation_after_id is not None:
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None
        self.animation_component_paths = {}
        for component in FIGURE_COMPONENTS:
            folder = self.run_dir / "figures" / component
            paths = sorted(
                folder.glob(f"{component}_*.png"),
                key=lambda path: int(path.stem.rsplit("_", 1)[-1]) if path.stem.rsplit("_", 1)[-1].isdigit() else -1,
            )
            if paths:
                self.animation_component_paths[component] = paths
        frame_counts = [len(paths) for paths in self.animation_component_paths.values()]
        if not frame_counts:
            self.animation_info_var.set("No annual figures generated yet.")
            return
        try:
            self.animation_component_images = {}
            for component, paths in self.animation_component_paths.items():
                images: list[ImageTk.PhotoImage] = []
                for path in paths:
                    with Image.open(path) as image:
                        preview = image.convert("RGB")
                        preview.thumbnail((680, 420), Image.Resampling.LANCZOS)
                        images.append(ImageTk.PhotoImage(preview, master=self))
                self.animation_component_images[component] = images
            self.animation_frame_index = 0
            self.animation_playing = True
            self._show_animation_frame()
            self.animation_after_id = self.after(800, self._animate_components)
        except Exception as exc:
            self.animation_info_var.set(f"Unable to display annual figures: {exc}")

    def _show_animation_frame(self) -> None:
        if not self.animation_component_images:
            return
        frame_count = max(len(images) for images in self.animation_component_images.values())
        if frame_count < 1:
            return
        self.animation_frame_index %= frame_count
        year = None
        for component, label in self.animation_labels.items():
            images = self.animation_component_images.get(component, [])
            if images:
                index = min(self.animation_frame_index, len(images) - 1)
                frame = images[index]
                label.configure(image=frame, text="")
                label.image = frame
                if year is None:
                    path = self.animation_component_paths.get(component, [])[index]
                    token = path.stem.rsplit("_", 1)[-1]
                    year = token if token.isdigit() else None
            else:
                label.configure(image="", text=translate("No figure available for this component.", self.language_code))
                label.image = None
        self.animation_year_var.set(f"Year {year}" if year else "Year —")

    def _animate_components(self) -> None:
        if not self.animation_component_images:
            return
        self._show_animation_frame()
        if self.animation_playing:
            frame_count = max(len(images) for images in self.animation_component_images.values())
            self.animation_frame_index = (self.animation_frame_index + 1) % max(frame_count, 1)
            self.animation_after_id = self.after(800, self._animate_components)

    def play_animation(self) -> None:
        if not self.animation_component_images:
            self._load_animation()
            return
        self.animation_playing = True
        if self.animation_after_id is None:
            self.animation_after_id = self.after(50, self._animate_components)

    def pause_animation(self) -> None:
        self.animation_playing = False
        if self.animation_after_id is not None:
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None

    def previous_animation_frame(self) -> None:
        if not self.animation_component_images:
            return
        self.pause_animation()
        frame_count = max(len(images) for images in self.animation_component_images.values())
        self.animation_frame_index = (self.animation_frame_index - 1) % max(frame_count, 1)
        self._show_animation_frame()

    def next_animation_frame(self) -> None:
        if not self.animation_component_images:
            return
        self.pause_animation()
        frame_count = max(len(images) for images in self.animation_component_images.values())
        self.animation_frame_index = (self.animation_frame_index + 1) % max(frame_count, 1)
        self._show_animation_frame()

    def open_animation(self) -> None:
        if self.animation_path is None or not self.animation_path.exists():
            self._show_message("showinfo", "Animation", "Run a simulation first to generate the GIF.")
            return
        self._open_desktop_path(self.animation_path, "Animation")

    def export_animation(self) -> None:
        if self.animation_path is None or not self.animation_path.exists():
            self._show_message("showinfo", "Animation", "Run a simulation first to generate the GIF.")
            return
        destination = filedialog.asksaveasfilename(
            title=translate("Export simulation GIF", self.language_code),
            defaultextension=".gif",
            filetypes=[(translate("Animated GIF", self.language_code), "*.gif")],
        )
        if destination:
            shutil.copy2(self.animation_path, destination)

    def open_animations_folder(self) -> None:
        folder = self.run_dir / "animations" if self.run_dir else None
        if folder is None or not folder.exists():
            self._show_message("showinfo", "Animations", "Run a simulation first to generate the animations.")
            return
        self._open_desktop_path(folder, "Animations")

    def open_figures_folder(self) -> None:
        folder = self.run_dir / "figures" if self.run_dir else None
        if folder is None or not folder.exists():
            self._show_message("showinfo", "Annual figures", "Run a simulation first to generate annual figures.")
            return
        self._open_desktop_path(folder, "Annual figures")

    def open_simulation_table(self) -> None:
        path = self.simulation_table_path
        if path is None and self.run_dir is not None:
            candidate = self.run_dir / "simulation_data.csv"
            path = candidate if candidate.exists() else None
        if path is None or not path.exists():
            self._show_message("showinfo", "Simulation table", "Run a simulation first to generate the simulation table.")
            return
        self._open_desktop_path(path, "Simulation table")

    def _open_desktop_path(self, path: Path, purpose: str) -> None:
        try:
            _open_path_with_desktop_application(path)
        except Exception as exc:
            self._show_message("showerror", purpose, f"Unable to open {path}:\n{exc}")

    def _redraw_class_chart(self) -> None:
        """Draw a compact vertical gain/loss chart with one bar per class."""
        if not hasattr(self, "class_chart"):
            return
        chart = self.class_chart
        width = max(int(chart.winfo_width()), 280)
        height = max(int(chart.winfo_height()), 220)
        chart.delete("all")
        left, right, top, bottom = 38, 10, 16, 54
        plot_height = max(height - top - bottom, 80)
        zero_y = top + plot_height / 2.0
        max_abs = max(max((abs(value) for value in self.class_change_values.values()), default=0), 1)
        chart.create_line(left, zero_y, width - right, zero_y, fill="#647986", width=1)
        chart.create_text(left - 5, top, text=f"+{max_abs:,}", anchor="e", fill=UI_COLORS["muted"], font=("Segoe UI", 8))
        chart.create_text(left - 5, zero_y, text="0", anchor="e", fill=UI_COLORS["muted"], font=("Segoe UI", 8))
        chart.create_text(left - 5, top + plot_height, text=f"−{max_abs:,}", anchor="e", fill=UI_COLORS["muted"], font=("Segoe UI", 8))
        keys = list(self.class_bar_colors)
        slot = (width - left - right) / max(len(keys), 1)
        bar_width = min(34.0, slot * 0.58)
        for index, key in enumerate(keys):
            center_x = left + slot * (index + 0.5)
            delta = int(self.class_change_values.get(key, 0))
            extent = (abs(delta) / max_abs) * (plot_height / 2.0 - 4.0)
            if delta > 0:
                y0, y1 = zero_y - extent, zero_y
            elif delta < 0:
                y0, y1 = zero_y, zero_y + extent
            else:
                y0 = y1 = zero_y
            if delta:
                chart.create_rectangle(center_x - bar_width / 2, y0, center_x + bar_width / 2, y1, outline="", fill=self.class_bar_colors[key])
                value_label = f"+{delta:,}" if delta > 0 else f"−{abs(delta):,}"
                chart.create_text(center_x, y0 - 4 if delta > 0 else y1 + 4, text=value_label, anchor="s" if delta > 0 else "n", fill=UI_COLORS["text"], font=("Segoe UI", 8))
            chart.create_text(center_x, height - bottom + 10, text=self.class_bar_labels[key], anchor="n", fill=UI_COLORS["text"], font=("Segoe UI", 8))

    def _update_class_bars(self, summary: dict[str, Any]) -> None:
        keys = tuple(self.class_bar_colors)
        current_values = {key: int(summary.get(key, 0)) for key in keys}
        baseline = self.initial_class_counts or {key: 0 for key in keys}
        deltas = {key: current_values[key] - int(baseline.get(key, 0)) for key in keys}
        self.class_current_values = current_values
        self.class_change_values = deltas
        self._redraw_class_chart()

    def _format_monitor(self, summary: dict[str, Any]) -> str:
        elapsed = time.perf_counter() - getattr(self, "run_started", time.perf_counter())
        extent = int(summary.get("mangrove_extent", 0))
        if not extent:
            extent = int(summary.get("mangrove", 0)) + int(summary.get("migrated_mangrove", 0))
        gain = int(summary.get("annual_gain", 0))
        loss = int(summary.get("annual_loss", 0))
        net = int(summary.get("annual_net_change", gain - loss))
        area = self.inputs.cell_area_km2 if self.inputs is not None else None
        extent_area = summary.get("mangrove_extent_km2")
        gain_area = summary.get("annual_gain_km2")
        loss_area = summary.get("annual_loss_km2")
        net_area = summary.get("annual_net_change_km2")
        if area is not None:
            extent_area = extent * area if extent_area is None else float(extent_area)
            gain_area = gain * area if gain_area is None else float(gain_area)
            loss_area = loss * area if loss_area is None else float(loss_area)
            net_area = net * area if net_area is None else float(net_area)
        extent_text = f"{extent:,} cells"
        if extent_area is not None:
            extent_text += f" ({float(extent_area):,.3f} km²)"
        return (
            f"Calendar year: {summary.get('calendar_year', '—')}\n"
            f"Mangrove: {int(summary.get('mangrove', 0)):,}\n"
            f"Migrated mangrove: {int(summary.get('migrated_mangrove', 0)):,}\n"
            f"Active mangrove extent: {extent_text}\n"
            f"Flooded mangrove: {int(summary.get('flooded_mangrove', 0)):,}\n"
            f"Flooded natural vegetation: {int(summary.get('flooded_natural', 0)):,}\n"
            f"Flooded anthropized / blocked: {int(summary.get('flooded_anthropized', 0)):,}\n"
            f"Gross annual gain: {gain:,} cells"
            + (f" ({float(gain_area):,.4f} km²)\n" if gain_area is not None else "\n")
            + f"Gross annual loss: {loss:,} cells"
            + (f" ({float(loss_area):,.4f} km²)\n" if loss_area is not None else "\n")
            + f"Net annual change: {net:+,} cells"
            + (f" ({float(net_area):+,.4f} km²)\n" if net_area is not None else "\n")
            + f"Elevation range: {float(summary.get('min_elevation', 0)):.3f}–{float(summary.get('max_elevation', 0)):.3f}\n"
            + f"Elapsed: {_format_duration(elapsed)}"
        )

    def _set_monitor(self, text: str) -> None:
        text = translate_runtime(text, self.language_code)
        self.monitor_text.configure(state="normal")
        self.monitor_text.delete("1.0", "end")
        self.monitor_text.insert("1.0", text)
        self.monitor_text.configure(state="disabled")
        if hasattr(self, "console_text"):
            self.console_text.configure(state="normal")
            self.console_text.delete("1.0", "end")
            self.console_text.insert("1.0", text)
            self.console_text.configure(state="disabled")

    def _monitor_text(self) -> str:
        return self.monitor_text.get("1.0", "end").strip()

    def _update_resources(self) -> None:
        cpu = ram = rss = disk = "—"
        if psutil is not None:
            cpu = f"{psutil.cpu_percent(None):.0f}%"
            vm = psutil.virtual_memory()
            ram = f"{vm.percent:.0f}%"
            if self.process is not None:
                rss = f"{self.process.memory_info().rss / 1024**2:.0f} MiB"
        if self.project_file is not None:
            usage = shutil.disk_usage(self.project_file.parent)
            disk = f"{usage.free / 1024**3:.1f} GiB free"
        self.resource_var.set(f"CPU {cpu} | RAM {ram} (process {rss}) | Disk {disk}")
        self.after(1000, self._update_resources)

    def new_project(self) -> None:
        folder = filedialog.askdirectory(title=translate("Choose a new BR-MANGUE project folder", self.language_code))
        if not folder:
            return
        self.project_file = Path(folder) / "brmangue_project.json"
        self.inputs = None
        self.custom_model_classes = []
        self.class_mapping_mode_var.set("standard")
        self.sea_level_mode_var.set("constant")
        self.sea_level_trajectory_path_var.set("")
        self._sea_level_trajectory = None
        self._on_sea_level_mode_changed()
        self.custom_class_behavior_var.set(self._display_custom_behavior("fixed"))
        self.class_counts.clear()
        self.initial_class_counts = {}
        self.class_vars.clear()
        self._class_combos.clear()
        self._rebuild_class_rows()
        self._refresh_custom_class_list()
        self._refresh_model_legend()
        self.source_crs_var.set("Not loaded")
        self.datum_var.set("Not loaded")
        self.vertical_datum_var.set("")
        self.expected_crs_var.set("")
        self.target_crs_var.set(DEFAULT_TARGET_CRS_LABEL)
        self.target_resolution_var.set("")
        self._update_class_bars({})
        self.project_status_var.set(f"New project: {Path(folder)}")
        self.run_status_var.set("New project")
        self._draw_placeholder()

    def save_project_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title=translate("Save BR-MANGUE project", self.language_code),
            defaultextension=".json",
            filetypes=[(translate("BR-MANGUE project", self.language_code), "*.json"), (translate("JSON", self.language_code), "*.json")],
        )
        if path:
            self.project_file = Path(path)
            self.save_project()

    def save_project(self) -> None:
        if self.project_file is None:
            self.save_project_as()
            return
        _mapping, excluded, roles, _custom_mapping = self._mapping_from_ui()
        curve = self._require_sea_level_trajectory() if self.sea_level_mode_var.get() == "trajectory" else None
        constant_rate = float(self.slr_var.get()) if curve is None else 0.0

        def project_path(value: str) -> str:
            """Store paths relative to the project whenever possible."""
            value = value.strip()
            if not value:
                return ""
            try:
                return os.path.relpath(Path(value).resolve(), self.project_file.parent.resolve())
            except ValueError:
                # Windows drives can differ; retain an explicit absolute path
                # rather than silently writing an invalid relative path.
                return str(Path(value).resolve())

        payload = {
            "format": "brmangue-studio-project",
            "version": "0.4.0",
            "inputs": {
                "land_cover": project_path(self.land_cover_var.get()),
                "elevation": project_path(self.elevation_var.get()),
                "mask": project_path(self.mask_var.get()),
                "soil": project_path(self.soil_var.get()),
            },
            "land_cover": {
                "band": int(self.land_cover_band_var.get()),
                "reference_year": int(self.land_cover_year_var.get()) if self.land_cover_year_var.get().strip() else None,
            },
            "class_roles": {str(k): v for k, v in roles.items()},
            "class_mapping_mode": self.class_mapping_mode_var.get(),
            "custom_model_classes": self.custom_model_classes,
            "excluded_source_codes": excluded,
            "spatial_reference": {
                "expected_crs": self.expected_crs_var.get(),
                "target_crs": self.target_crs_var.get(),
                "target_resolution": self.target_resolution_var.get(),
                "source_datum_metadata": translate(self.datum_var.get(), "en"),
                "declared_vertical_datum": self.vertical_datum_var.get(),
            },
            "parameters": {
                "initial_year": int(self.initial_year_var.get()),
                "final_year": int(self.final_year_var.get()),
                "tide_height_m": float(self.tide_height_var.get()),
                "sea_level_mode": self.sea_level_mode_var.get(),
                "sea_level_trajectory": curve.to_dict() if curve else None,
                "sea_level_trajectory_file": project_path(self.sea_level_trajectory_path_var.get()) if curve else "",
                "sea_level_rise_mm_per_year": constant_rate,
                "sea_level_rise_m_per_model_step": constant_rate / 1000.0,
                "accretion_rate_mm": self.accretion_var.get(),
                "migration_maturity_years": int(self.migration_maturity_var.get()),
                "block_size": int(self.block_size_var.get()),
                "engine": self.engine_var.get(),
                "soil_enabled": bool(self.soil_enabled_var.get()),
                "allow_migration_without_soil": bool(self.migration_without_soil_var.get()),
            },
        }
        self.project_file.parent.mkdir(parents=True, exist_ok=True)
        self.project_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.project_status_var.set(f"Project: {self.project_file.parent}")

    def open_project(self) -> None:
        path = filedialog.askopenfilename(
            title=translate("Open BR-MANGUE project", self.language_code),
            filetypes=[(translate("Project JSON", self.language_code), "*.json"), (translate("All files", self.language_code), "*.*")],
        )
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            self.project_file = Path(path)

            def input_path(value: str) -> str:
                if not value:
                    return ""
                candidate = Path(value)
                if not candidate.is_absolute():
                    candidate = self.project_file.parent / candidate
                return str(candidate.resolve())

            saved_inputs = payload.get("inputs", {})
            # Accept version 0.1 projects that still used provider-specific names.
            saved_land_cover = saved_inputs.get("land_cover", saved_inputs.get("mapbiomas", ""))
            for variable, value in [
                (self.land_cover_var, saved_land_cover),
                (self.elevation_var, saved_inputs.get("elevation", "")),
                (self.mask_var, saved_inputs.get("mask", "")),
                (self.soil_var, saved_inputs.get("soil", "")),
            ]:
                variable.set(input_path(value))
            saved_cover_meta = payload.get("land_cover", payload.get("mapbiomas", {}))
            self.land_cover_band_var.set(str(saved_cover_meta.get("band", 1)))
            saved_year = saved_cover_meta.get("reference_year", saved_cover_meta.get("year"))
            self.land_cover_year_var.set("" if saved_year in (None, "") else str(saved_year))
            spatial = payload.get("spatial_reference", {})
            self.expected_crs_var.set(spatial.get("expected_crs", ""))
            self.target_crs_var.set(spatial.get("target_crs", DEFAULT_TARGET_CRS_LABEL) or DEFAULT_TARGET_CRS_LABEL)
            saved_resolution = spatial.get("target_resolution", "")
            self.target_resolution_var.set("" if saved_resolution in (None, "") else str(saved_resolution))
            self.vertical_datum_var.set(spatial.get("declared_vertical_datum", ""))
            self.custom_model_classes = normalize_custom_model_classes(
                payload.get("custom_model_classes", [])
            )
            saved_mapping_mode = payload.get("class_mapping_mode", "standard")
            self.class_mapping_mode_var.set(
                saved_mapping_mode if saved_mapping_mode in {"standard", "custom"} else "standard"
            )
            self._refresh_custom_class_list()
            self._refresh_model_legend()
            parameters = payload.get("parameters", {})
            for var, key, default in [
                (self.initial_year_var, "initial_year", 2025),
                (self.final_year_var, "final_year", 2035),
                (self.tide_height_var, "tide_height_m", 6.0),
                (self.slr_var, "sea_level_rise_mm_per_year", parameters.get("sea_level_rise_per_step", 0.5)),
                (self.accretion_var, "accretion_rate_mm", ""),
                (self.migration_maturity_var, "migration_maturity_years", 3),
                (self.block_size_var, "block_size", 10000),
                (self.engine_var, "engine", "blocks"),
            ]:
                var.set(str(parameters.get(key, default)))
            if self.engine_var.get() == "dissmodel" and not DISSMODEL_AVAILABLE:
                self.engine_var.set("blocks")
            self._sync_engine_choice()
            self.sea_level_mode_var.set(parameters.get("sea_level_mode", "constant"))
            self._sea_level_trajectory = trajectory_from_project(parameters, self.project_file.parent)
            self.sea_level_trajectory_path_var.set(input_path(parameters.get("sea_level_trajectory_file", "")))
            self._on_sea_level_mode_changed()
            self.soil_enabled_var.set(bool(parameters.get("soil_enabled", False)))
            self.migration_without_soil_var.set(bool(parameters.get("allow_migration_without_soil", True)))
            self.project_status_var.set(f"Project: {self.project_file.parent}")
            self.inspect_mapbiomas()
            saved_roles = payload.get("class_roles", {})
            for code, var in self.class_vars.items():
                if str(code) in saved_roles:
                    var.set(self._display_role(str(saved_roles[str(code)])))
            self.load_inputs()
        except Exception as exc:
            self._show_message("showerror", "Open project", str(exc))

    def open_results_folder(self) -> None:
        folder = self.run_dir or (self.project_file.parent / "results" if self.project_file else None)
        if folder is None:
            self._show_message("showinfo", "Results", "No project or simulation output exists yet.")
            return
        folder.mkdir(parents=True, exist_ok=True)
        self._open_desktop_path(folder, "Results")


def main() -> None:
    app = BRMangueStudio()
    app.withdraw()
    _show_splash(app)
    app.mainloop()
