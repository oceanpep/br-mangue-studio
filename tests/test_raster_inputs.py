import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from brmangue_lua.raster_inputs import load_raster_inputs, normalize_custom_model_classes


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
    ) as destination:
        destination.write(data, 1)


def test_raster_loader_without_soil_keeps_flooding_inputs(tmp_path):
    land_cover = np.array([[5, 33], [6, 24]], dtype=np.uint8)
    elevation = np.ones((2, 2), dtype=np.float32)
    mask = np.ones((2, 2), dtype=np.uint8)
    land_cover_path = tmp_path / "land_cover.tif"
    elevation_path = tmp_path / "dem.tif"
    mask_path = tmp_path / "mask.tif"
    _write_raster(land_cover_path, land_cover, dtype="uint8")
    _write_raster(elevation_path, elevation, dtype="float32", nodata=-9999)
    _write_raster(mask_path, mask, dtype="uint8")

    inputs = load_raster_inputs(
        land_cover_path, elevation_path, mask_path=mask_path, soil_enabled=False
    )
    assert inputs.n_cells == 4
    assert inputs.grid.class_counts()["mangrove"] == 1
    assert inputs.grid.class_counts()["water"] == 1
    assert np.all(inputs.grid.soil_class == -999)
    assert inputs.metadata["soil"]["enabled"] is False


def test_raster_loader_accepts_aligned_optional_soil(tmp_path):
    land_cover = np.array([[5, 33], [6, 24]], dtype=np.uint8)
    elevation = np.ones((2, 2), dtype=np.float32)
    mask = np.ones((2, 2), dtype=np.uint8)
    soil = np.array([[3, 0], [2, 9]], dtype=np.int16)
    paths = {name: tmp_path / f"{name}.tif" for name in ("land_cover", "dem", "mask", "soil")}
    _write_raster(paths["land_cover"], land_cover, dtype="uint8")
    _write_raster(paths["dem"], elevation, dtype="float32", nodata=-9999)
    _write_raster(paths["mask"], mask, dtype="uint8")
    _write_raster(paths["soil"], soil, dtype="int16", nodata=-999)

    inputs = load_raster_inputs(
        paths["land_cover"], paths["dem"], mask_path=paths["mask"],
        soil_path=paths["soil"], soil_enabled=True,
    )
    assert inputs.metadata["soil"]["enabled"] is True
    assert inputs.grid.soil_class.tolist() == [3, 0, 2, 9]


def test_raster_loader_ignores_unmasked_nan_in_categorical_raster(tmp_path):
    land_cover = np.array([[5.0, np.nan], [33.0, 6.0]], dtype=np.float32)
    elevation = np.ones((2, 2), dtype=np.float32)
    land_cover_path = tmp_path / "land_cover_nan.tif"
    elevation_path = tmp_path / "dem.tif"
    _write_raster(land_cover_path, land_cover, dtype="float32", nodata=-9999)
    _write_raster(elevation_path, elevation, dtype="float32", nodata=-9999)

    inputs = load_raster_inputs(land_cover_path, elevation_path, soil_enabled=False)
    assert inputs.n_cells == 3
    assert "nan" not in inputs.metadata["land_cover"]["mapping"]["source_code_counts_valid"]
    assert inputs.grid.class_counts()["mangrove"] == 1
    assert inputs.grid.class_counts()["water"] == 1


def test_custom_class_mapping_preserves_class_code_and_exports_catalog(tmp_path):
    land_cover_path = tmp_path / "land_cover.tif"
    elevation_path = tmp_path / "dem.tif"
    _write_raster(land_cover_path, np.array([[90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation_path, np.array([[50]], dtype=np.float32), dtype="float32", nodata=-9999)
    custom_classes = [{"code": 300, "name": "Agriculture", "color": "#C08020", "behavior": "fixed"}]

    inputs = load_raster_inputs(
        land_cover_path,
        elevation_path,
        soil_enabled=False,
        custom_class_mapping={300: [90]},
        custom_classes=custom_classes,
    )

    assert inputs.grid.land_cover_state.tolist() == [300]
    assert inputs.grid.class_counts()["class_300"] == 1
    assert inputs.metadata["custom_model_classes"] == [
        {"code": 300, "name": "Agriculture", "color": "#c08020", "behavior": "fixed"}
    ]
    assert inputs.metadata["land_cover"]["mapping"]["source_to_model"]["custom_300"] == [90]
    output = inputs.write_state_raster(inputs.grid.land_cover_state, tmp_path / "state.tif", year=2025)
    with rasterio.open(output) as source:
        assert source.dtypes == ("uint16",)
        assert source.read(1).tolist() == [[300]]
        assert source.tags()["model_state_catalog"] == json.dumps(
            inputs.metadata["model_state_catalog"], ensure_ascii=False
        )


def test_custom_class_validation_accepts_codes_from_one_and_checks_values():
    normalized = normalize_custom_model_classes([
        {"code": 1, "name": " Wetland ", "color": "#AABBCC"},
    ])
    assert normalized == [{
        "code": 1,
        "name": "Wetland",
        "color": "#aabbcc",
        "behavior": "fixed",
    }]
    with pytest.raises(ValueError, match="duplicated"):
        normalize_custom_model_classes([
            {"code": 11, "name": "Forest", "color": "#112233"},
            {"code": 12, "name": "forest", "color": "#445566"},
        ])
    with pytest.raises(ValueError, match="hexadecimal #RRGGBB"):
        normalize_custom_model_classes([{"code": 11, "name": "Forest", "color": "green"}])
    with pytest.raises(ValueError, match="between 1"):
        normalize_custom_model_classes([{"code": 0, "name": "Forest", "color": "#112233"}])
    with pytest.raises(ValueError, match="must be an integer"):
        normalize_custom_model_classes([{"code": 11.5, "name": "Forest", "color": "#112233"}])
    with pytest.raises(ValueError, match="Behavior profile"):
        normalize_custom_model_classes([{
            "code": 11, "name": "Forest", "color": "#112233", "behavior": "unknown"
        }])


def test_custom_mapping_requires_every_source_code_and_rejects_duplicate_assignments(tmp_path):
    land_cover_path = tmp_path / "land_cover.tif"
    elevation_path = tmp_path / "dem.tif"
    _write_raster(land_cover_path, np.array([[5]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation_path, np.array([[50]], dtype=np.float32), dtype="float32", nodata=-9999)
    classes = [
        {"code": 300, "name": "First", "color": "#112233"},
        {"code": 301, "name": "Second", "color": "#445566"},
    ]
    with pytest.raises(ValueError, match="assigned to more than one class"):
        load_raster_inputs(
            land_cover_path,
            elevation_path,
            soil_enabled=False,
            custom_class_mapping={300: [5], 301: [5]},
            custom_classes=classes,
            class_mapping_mode="custom",
        )
