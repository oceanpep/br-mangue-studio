"""Convert a TerraLib Access database cell layer to BR-MANGUE Studio rasters.

The converter is intentionally provider-specific only at the import boundary.
It reads the Cell and Cells2 tables, writes aligned GeoTIFFs, and creates a
portable Studio project without changing the source MDB.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyodbc
import rasterio
from rasterio.transform import from_origin
from pyproj import Geod


DB_DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"

# Source codes observed in Banco_2023.mdb and their BR-MANGUE state codes.
# 0=water, 1=mangrove, 2=terrestrial vegetation, 3=anthropized,
# 4=bare soil. The mapping is recorded in metadata for auditability.
LAND_COVER_STATE_MAP = {0: 3, 1: 1, 2: 2, 3: 4, 4: 5}


def _read_tables(
    database: Path,
    cell_table: str,
    geometry_table: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    connection_string = f"DRIVER={{{DB_DRIVER}}};DBQ={database};"
    with pyodbc.connect(connection_string, readonly=True) as connection:
        def fetch_dataframe(query: str) -> pd.DataFrame:
            cursor = connection.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [item[0] for item in cursor.description]
            return pd.DataFrame.from_records(rows, columns=columns)

        cells = fetch_dataframe(
            f"SELECT object_id0, Col, Lin, Usos, ClasseSolos, Alt2 FROM [{cell_table}]"
        )
        geometry = fetch_dataframe(
            f"SELECT object_id, lower_x, lower_y, upper_x, upper_y, col_number, row_number FROM [{geometry_table}]"
        )
        try:
            reference_result = fetch_dataframe(
                "SELECT object_id_, Usos FROM [result79]"
            )
        except pyodbc.Error:
            reference_result = None
    merged = geometry.merge(cells, left_on="object_id", right_on="object_id0", how="inner", validate="one_to_one")
    if len(merged) != len(cells) or len(merged) != len(geometry):
        raise ValueError("Cell and geometry tables do not have a one-to-one join.")
    if not np.array_equal(merged["col_number"].to_numpy(), merged["Col"].to_numpy()):
        raise ValueError("Cell.Col and Cells2.col_number are inconsistent.")
    if not np.array_equal(merged["row_number"].to_numpy(), merged["Lin"].to_numpy()):
        raise ValueError("Cell.Lin and Cells2.row_number are inconsistent.")
    return merged, cells, reference_result


def _write_raster(path: Path, array: np.ndarray, profile: dict, *, description: str, nodata: int | float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output_profile = dict(profile)
    output_profile.update(count=1, dtype=str(array.dtype), nodata=nodata, compress="deflate", tiled=False)
    with rasterio.open(path, "w", **output_profile) as destination:
        destination.write(array, 1)
        destination.set_band_description(1, description)
        destination.update_tags(source="Banco_2023.mdb", converter="import_access_mdb.py")


def convert(database: Path, output_dir: Path, *, cell_table: str = "Cell", geometry_table: str = "Cells2") -> Path:
    database = database.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    merged, cells, reference_result = _read_tables(database, cell_table, geometry_table)

    width = int(merged["col_number"].max()) + 1
    height = int(merged["row_number"].max())
    min_x = float(merged["lower_x"].min())
    max_y = float(merged["upper_y"].max())
    dx = float(np.median(merged["upper_x"] - merged["lower_x"]))
    dy = float(np.median(merged["upper_y"] - merged["lower_y"]))
    if not np.allclose(merged["upper_x"] - merged["lower_x"], dx, rtol=0, atol=1e-9):
        raise ValueError("Cells2 has non-uniform horizontal cell size.")
    if not np.allclose(merged["upper_y"] - merged["lower_y"], dy, rtol=0, atol=1e-9):
        raise ValueError("Cells2 has non-uniform vertical cell size.")

    transform = from_origin(min_x, max_y, dx, dy)
    geod = Geod(ellps="WGS84")
    center_lat = float((merged["lower_y"].min() + merged["upper_y"].max()) / 2.0)
    corners_lon = [min_x, min_x + dx, min_x + dx, min_x]
    corners_lat = [center_lat, center_lat, center_lat + dy, center_lat + dy]
    cell_area_m2, _ = geod.polygon_area_perimeter(corners_lon, corners_lat)
    cell_area_ha = abs(float(cell_area_m2)) / 10_000.0
    land_cover = np.zeros((height, width), dtype=np.uint8)
    elevation = np.full((height, width), -9999.0, dtype=np.float32)
    soil_raw = np.full((height, width), -9999, dtype=np.int16)
    mask = np.zeros((height, width), dtype=np.uint8)
    rows = merged["row_number"].to_numpy(dtype=np.int64) - 1
    cols = merged["col_number"].to_numpy(dtype=np.int64)
    source_land_cover = pd.to_numeric(merged["Usos"], errors="raise").round().astype(int).to_numpy()
    unknown = sorted(set(source_land_cover).difference(LAND_COVER_STATE_MAP))
    if unknown:
        raise ValueError(f"Unsupported Usos codes: {unknown}")
    land_cover[rows, cols] = np.asarray([LAND_COVER_STATE_MAP[int(v)] for v in source_land_cover], dtype=np.uint8)
    elevation[rows, cols] = pd.to_numeric(merged["Alt2"], errors="raise").to_numpy(dtype=np.float32)
    soil_raw[rows, cols] = pd.to_numeric(merged["ClasseSolos"], errors="raise").to_numpy(dtype=np.int16)
    mask[rows, cols] = 1

    attributes = merged[
        [
            "object_id0",
            "col_number",
            "row_number",
            "Usos",
            "ClasseSolos",
            "Alt2",
        ]
    ].copy()
    attributes.insert(
        attributes.columns.get_loc("Usos") + 1,
        "model_land_cover_code",
        [LAND_COVER_STATE_MAP[int(value)] for value in source_land_cover],
    )
    attributes.rename(
        columns={
            "object_id0": "object_id",
            "col_number": "col",
            "row_number": "row",
            "Usos": "source_land_cover_code",
            "ClasseSolos": "source_soil_code",
            "Alt2": "elevation_alt2",
        },
        inplace=True,
    )
    attributes.to_csv(output_dir / "cell_attributes.csv", index=False)
    if reference_result is not None:
        reference_result.to_csv(output_dir / "source_result79.csv", index=False)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "crs": "EPSG:4326",
        "transform": transform,
    }
    land_path = output_dir / "land_cover_model_codes.tif"
    elevation_path = output_dir / "elevation_alt2.tif"
    soil_path = output_dir / "soil_classes_raw.tif"
    mask_path = output_dir / "study_mask.tif"
    _write_raster(land_path, land_cover, profile, description="BR-MANGUE source land-cover state", nodata=0)
    _write_raster(elevation_path, elevation, profile, description="Alt2 elevation from MDB", nodata=-9999.0)
    _write_raster(soil_path, soil_raw, profile, description="Raw ClasseSolos code from MDB", nodata=-9999)
    _write_raster(mask_path, mask, profile, description="Valid Cell/Cells2 domain", nodata=0)

    roles = {
        "1": "Mangrove",
        "2": "Natural vegetation",
        "3": "Water",
        "4": "Anthropized / blocked",
        "5": "Anthropized / blocked",
    }
    project = {
        "format": "brmangue-studio-project-v1",
        "inputs": {
            "land_cover": land_path.name,
            "elevation": elevation_path.name,
            "mask": mask_path.name,
            "soil": soil_path.name,
        },
        "land_cover": {"band": 1, "reference_year": 2023},
        "class_roles": roles,
        "parameters": {
            "initial_year": 2023,
            "final_year": 2033,
            "tide_height_m": 6.0,
            "sea_level_rise_mm_per_year": 100.0,
            "sea_level_rise_m_per_model_step": 0.1,
            "soil_enabled": False,
            "allow_migration_without_soil": True,
            "engine": "blocks",
            "block_size": 10000,
        },
    }
    project_path = output_dir / "Banco_2023_BR_MANGUE_Studio.json"
    project_path.write_text(json.dumps(project, indent=2, ensure_ascii=False), encoding="utf-8")
    metadata = {
        "source_database": str(database),
        "source_tables": {"cell": cell_table, "geometry": geometry_table},
        "source_rows": int(len(cells)),
        "grid_shape": [height, width],
        "resolution_degrees": [dx, dy],
        "cell_size_approx": {
            "width_degrees": dx,
            "height_degrees": dy,
            "area_ha_at_domain_center": cell_area_ha,
            "note": "The MDB grid is approximately 1 km cells; it is not the 30 m MapBiomas grid or the 1 ha grid reported in Bezerra et al. (2014).",
        },
        "crs_exported": "EPSG:4326",
        "source_srs_note": "MDB metadata stores WGS84 / srs_id 4979; exported rasters use 2D EPSG:4326.",
        "land_cover_source_to_model": {str(k): int(v) for k, v in LAND_COVER_STATE_MAP.items()},
        "source_land_cover_counts": {str(int(k)): int(v) for k, v in zip(*np.unique(source_land_cover, return_counts=True))},
        "soil": {
            "exported": str(soil_path),
            "enabled_in_project": False,
            "note": "Raw classes are preserved; no suitability interpretation is activated automatically.",
        },
        "reference_result79": {
            "exported": str(output_dir / "source_result79.csv") if reference_result is not None else None,
            "rows": int(len(reference_result)) if reference_result is not None else 0,
            "note": "Original result table copied for audit; it is not used as an input to the Studio simulation.",
        },
        "files": {
            "land_cover": str(land_path),
            "elevation": str(elevation_path),
            "mask": str(mask_path),
            "soil_raw": str(soil_path),
            "cell_attributes": str(output_dir / "cell_attributes.csv"),
            "project": str(project_path),
        },
    }
    (output_dir / "conversion_metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return project_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Banco_2023.mdb Cell/Cells2 tables for BR-MANGUE Studio.")
    parser.add_argument("--input", type=Path, required=True, help="Path to the original MDB file.")
    parser.add_argument("--output", type=Path, required=True, help="Directory for exported rasters and project.")
    parser.add_argument("--cell-table", default="Cell")
    parser.add_argument("--geometry-table", default="Cells2")
    args = parser.parse_args()
    project = convert(args.input, args.output, cell_table=args.cell_table, geometry_table=args.geometry_table)
    print(project)


if __name__ == "__main__":
    main()
