from pathlib import Path
import sys

sys.path.insert(0, "src")

from brmangue_studio.geospatial_runtime import configure_geospatial_runtime


def test_frozen_app_prefers_rasterio_proj_data_over_host_gis_settings(tmp_path: Path):
    rasterio_proj = tmp_path / "rasterio" / "proj_data"
    rasterio_proj.mkdir(parents=True)
    (rasterio_proj / "proj.db").touch()
    rasterio_gdal = tmp_path / "rasterio" / "gdal_data"
    rasterio_gdal.mkdir()
    pyproj_proj = tmp_path / "pyproj" / "proj_dir" / "share" / "proj"
    pyproj_proj.mkdir(parents=True)
    (pyproj_proj / "proj.db").touch()

    environment = {
        "PROJ_DATA": "C:/old-gis/proj",
        "PROJ_LIB": "C:/old-gis/proj",
        "GDAL_DATA": "C:/old-gis/gdal",
    }

    configure_geospatial_runtime(tmp_path, environ=environment)

    assert environment["PROJ_DATA"] == str(rasterio_proj)
    assert environment["PROJ_LIB"] == str(rasterio_proj)
    assert environment["GDAL_DATA"] == str(rasterio_gdal)


def test_frozen_app_uses_bundled_pyproj_data_as_fallback(tmp_path: Path):
    pyproj_proj = tmp_path / "pyproj" / "proj_dir" / "share" / "proj"
    pyproj_proj.mkdir(parents=True)
    (pyproj_proj / "proj.db").touch()
    environment = {"PROJ_DATA": "C:/old-gis/proj", "PROJ_LIB": "C:/old-gis/proj"}

    configure_geospatial_runtime(tmp_path, environ=environment)

    assert environment["PROJ_DATA"] == str(pyproj_proj)
    assert environment["PROJ_LIB"] == str(pyproj_proj)


def test_missing_bundled_geospatial_data_does_not_keep_host_overrides(tmp_path: Path):
    environment = {
        "PROJ_DATA": "C:/old-gis/proj",
        "PROJ_LIB": "C:/old-gis/proj",
        "GDAL_DATA": "C:/old-gis/gdal",
    }

    configure_geospatial_runtime(tmp_path, environ=environment)

    assert "PROJ_DATA" not in environment
    assert "PROJ_LIB" not in environment
    assert "GDAL_DATA" not in environment
