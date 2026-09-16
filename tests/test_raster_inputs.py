import numpy as np
import rasterio
from rasterio.transform import from_origin

from brmangue_lua.engine import MANGUE, MAR, VEGETACAO_TERRESTRE
from brmangue_lua.raster_inputs import load_raster_inputs


def _write_raster(path, data, *, dtype, nodata=0):
    transform = from_origin(500000, 9700000, 30, 30)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=dtype,
        crs="EPSG:5880",
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data, 1)


def test_raster_loader_without_soil_keeps_flooding_inputs(tmp_path):
    mb = np.array([[5, 33], [6, 24]], dtype=np.uint8)
    dem = np.ones((2, 2), dtype=np.float32)
    mask = np.ones((2, 2), dtype=np.uint8)
    mb_path = tmp_path / "mb.tif"
    dem_path = tmp_path / "dem.tif"
    mask_path = tmp_path / "mask.tif"
    _write_raster(mb_path, mb, dtype="uint8")
    _write_raster(dem_path, dem, dtype="float32", nodata=-9999)
    _write_raster(mask_path, mask, dtype="uint8")

    inputs = load_raster_inputs(mb_path, dem_path, mask_path=mask_path, soil_enabled=False, mapbiomas_band=1)
    assert inputs.n_cells == 4
    assert inputs.grid.class_counts()["mangrove"] == 1
    assert inputs.grid.class_counts()["sea"] == 1
    assert np.all(inputs.grid.classe_solos == -999)
    assert inputs.metadata["soil"]["enabled"] is False


def test_raster_loader_accepts_aligned_optional_soil(tmp_path):
    mb = np.array([[5, 33], [6, 24]], dtype=np.uint8)
    dem = np.ones((2, 2), dtype=np.float32)
    mask = np.ones((2, 2), dtype=np.uint8)
    soil = np.array([[3, 0], [2, 9]], dtype=np.int16)
    mb_path = tmp_path / "mb.tif"
    dem_path = tmp_path / "dem.tif"
    mask_path = tmp_path / "mask.tif"
    soil_path = tmp_path / "soil.tif"
    _write_raster(mb_path, mb, dtype="uint8")
    _write_raster(dem_path, dem, dtype="float32", nodata=-9999)
    _write_raster(mask_path, mask, dtype="uint8")
    _write_raster(soil_path, soil, dtype="int16", nodata=-999)

    inputs = load_raster_inputs(
        mb_path,
        dem_path,
        mask_path=mask_path,
        soil_path=soil_path,
        soil_enabled=True,
        mapbiomas_band=1,
    )
    assert inputs.metadata["soil"]["enabled"] is True
    assert inputs.grid.classe_solos.tolist() == [3, 0, 2, 9]
