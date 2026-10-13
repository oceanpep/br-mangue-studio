import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from brmangue_lua.engine import MANGUE, MAR, VEGETACAO_TERRESTRE
from brmangue_lua.raster_inputs import (
    load_raster_inputs,
    normalize_custom_model_classes,
)


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


def test_raster_loader_ignores_unmasked_nan_in_categorical_raster(tmp_path):
    # A few MapBiomas/land-cover exports carry NaN cells in addition to their
    # declared nodata value.  Those cells must be excluded before class codes
    # are converted to integers for the mapping metadata.
    mb = np.array([[5.0, np.nan], [33.0, 6.0]], dtype=np.float32)
    dem = np.ones((2, 2), dtype=np.float32)
    mb_path = tmp_path / "mb_nan.tif"
    dem_path = tmp_path / "dem_nan.tif"
    _write_raster(mb_path, mb, dtype="float32", nodata=-9999)
    _write_raster(dem_path, dem, dtype="float32", nodata=-9999)

    inputs = load_raster_inputs(mb_path, dem_path, soil_enabled=False)

    assert inputs.n_cells == 3
    assert "nan" not in inputs.metadata["land_cover"]["mapping"]["source_code_counts_valid"]
    assert inputs.grid.class_counts()["mangrove"] == 1
    assert inputs.grid.class_counts()["sea"] == 1


def test_custom_model_class_maps_source_code_and_exports_wide_state(tmp_path):
    land_cover = tmp_path / "land_cover.tif"
    elevation = tmp_path / "elevation.tif"
    _write_raster(land_cover, np.array([[5, 90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation, np.array([[50, 50]], dtype=np.float32), dtype="float32", nodata=-9999)

    inputs = load_raster_inputs(
        land_cover,
        elevation,
        soil_enabled=False,
        custom_class_mapping={300: [90]},
        custom_classes=[{"code": 300, "name": "Agriculture", "color": "#C08020"}],
    )

    assert inputs.grid.usos.tolist() == [1, 300]
    assert inputs.grid.custom_state_codes == (300,)
    assert inputs.grid.class_counts()["custom_300"] == 1
    assert inputs.metadata["custom_model_classes"] == [
        {"code": 300, "name": "Agriculture", "color": "#c08020"}
    ]
    assert inputs.metadata["land_cover"]["mapping"]["source_to_model"]["custom_300"] == [90]

    output = inputs.write_state_raster(inputs.grid.usos, tmp_path / "state.tif", year=2025)
    with rasterio.open(output) as src:
        assert src.dtypes == ("uint16",)
        assert src.read(1).tolist() == [[1, 300]]
        assert src.tags()["custom_model_classes"] == (
            '[{"code": 300, "name": "Agriculture", "color": "#c08020"}]'
        )


def test_custom_model_classes_validate_codes_names_and_colors():
    normalized = normalize_custom_model_classes([
        {"code": 12, "name": " Wetland ", "color": "#AABBCC"},
    ])
    assert normalized == [{"code": 12, "name": "Wetland", "color": "#aabbcc"}]

    with pytest.raises(ValueError, match="repetido"):
        normalize_custom_model_classes([
            {"code": 11, "name": "Forest", "color": "#112233"},
            {"code": 12, "name": "forest", "color": "#445566"},
        ])
    with pytest.raises(ValueError, match="formato hexadecimal"):
        normalize_custom_model_classes([
            {"code": 11, "name": "Forest", "color": "green"},
        ])
    with pytest.raises(ValueError, match="entre 11"):
        normalize_custom_model_classes([
            {"code": 10, "name": "Forest", "color": "#112233"},
        ])
    with pytest.raises(ValueError, match="número inteiro"):
        normalize_custom_model_classes([
            {"code": 11.5, "name": "Forest", "color": "#112233"},
        ])


def test_custom_source_class_cannot_overlap_default_mapping(tmp_path):
    land_cover = tmp_path / "land_cover.tif"
    elevation = tmp_path / "elevation.tif"
    _write_raster(land_cover, np.array([[5]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation, np.array([[50]], dtype=np.float32), dtype="float32", nodata=-9999)

    with pytest.raises(ValueError, match="atribuído a mais de uma classe"):
        load_raster_inputs(
            land_cover,
            elevation,
            soil_enabled=False,
            custom_class_mapping={300: [5]},
            custom_classes=[{"code": 300, "name": "Custom", "color": "#112233"}],
        )
