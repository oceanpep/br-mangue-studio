"""Configure bundled GDAL/PROJ data for frozen desktop builds."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import MutableMapping


def configure_geospatial_runtime(
    bundle_root: str | Path | None = None,
    *,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    """Make a frozen app use its own compatible GDAL and PROJ databases.

    GIS software installed on a user's computer can leave ``PROJ_DATA``,
    ``PROJ_LIB``, or ``GDAL_DATA`` pointing at a different PROJ/GDAL version.
    Rasterio's bundled GDAL may then fail to resolve valid GeoTIFF EPSG codes.
    The desktop bundle includes Rasterio's data directories; prefer those over
    inherited machine-wide settings. Source installations are left untouched.
    """
    if environ is None:
        environ = os.environ

    if bundle_root is None:
        if not getattr(sys, "frozen", False):
            return
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root is None:
            return

    root = Path(bundle_root)
    rasterio_root = root / "rasterio"
    proj_candidates = (
        rasterio_root / "proj_data",
        root / "pyproj" / "proj_dir" / "share" / "proj",
    )
    proj_data = next(
        (path for path in proj_candidates if (path / "proj.db").is_file()),
        None,
    )
    if proj_data is None:
        # Do not let a host GIS database silently override the bundled library's
        # compiled-in search path when the data were not collected correctly.
        environ.pop("PROJ_DATA", None)
        environ.pop("PROJ_LIB", None)
    else:
        # PROJ_DATA is used by recent PROJ; PROJ_LIB is retained for older
        # versions used by some Windows and Linux binary wheels.
        environ["PROJ_DATA"] = str(proj_data)
        environ["PROJ_LIB"] = str(proj_data)

    gdal_data = rasterio_root / "gdal_data"
    if gdal_data.is_dir():
        environ["GDAL_DATA"] = str(gdal_data)
    else:
        environ.pop("GDAL_DATA", None)
