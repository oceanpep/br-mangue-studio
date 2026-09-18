import numpy as np
import rasterio
from rasterio.transform import from_origin

from brmangue_lua.engine import ModelParameters
from brmangue_lua.raster_inputs import load_raster_inputs
from brmangue_lua.raster_runner import run_raster_simulation


def _write_raster(path, data, *, dtype, nodata=0):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=dtype,
        crs="EPSG:5880",
        transform=from_origin(500000, 9700000, 30, 30),
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)


def test_block_runner_releases_and_restores_materialized_grid(tmp_path):
    land_cover = tmp_path / "land_cover.tif"
    elevation = tmp_path / "elevation.tif"
    _write_raster(land_cover, np.array([[5, 33], [6, 24]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation, np.ones((2, 2), dtype=np.float32), dtype="float32", nodata=-9999)

    inputs = load_raster_inputs(land_cover, elevation, soil_enabled=False)
    trajectory = run_raster_simulation(
        inputs,
        tmp_path / "run",
        ModelParameters(final_time=1, tide_height=6, sea_level_rise_rate=0.5),
        initial_year=2025,
        engine="blocks",
        block_size=2,
        save_annual_states=False,
    )

    assert len(trajectory) == 1
    assert inputs.grid is None
    assert inputs.n_cells == 4
    metadata = (tmp_path / "run" / "metadata.json").read_text(encoding="utf-8")
    assert "input_grid_released_after_persistent_copy" in metadata
