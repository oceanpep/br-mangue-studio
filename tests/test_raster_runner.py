import numpy as np
import json
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from types import SimpleNamespace

from brmangue_lua.engine import ModelParameters
from brmangue_lua.raster_inputs import load_raster_inputs
from brmangue_lua.raster_runner import run_raster_simulation
from brmangue_studio.__main__ import _run_batch
from brmangue_studio.app import (
    BRMangueStudio,
    _model_colormap,
    _write_simulation_spreadsheet,
)
from brmangue_studio.localization import translate


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
    assert inputs.cell_area_km2 == 0.0009
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
    assert {
        "mangrove_extent",
        "annual_gain",
        "annual_loss",
        "annual_net_change",
        "cell_area_km2",
        "mangrove_extent_km2",
        "annual_net_change_km2",
    }.issubset(trajectory.columns)
    assert int(trajectory.loc[0, "annual_net_change"]) == int(
        trajectory.loc[0, "annual_gain"] - trajectory.loc[0, "annual_loss"]
    )
    assert inputs.grid is None
    assert inputs.n_cells == 4
    metadata_path = tmp_path / "run" / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["block_input_materialization"][
        "input_grid_released_after_persistent_copy"
    ] is True
    assert metadata["performance"]["annual_steps"] == 1
    assert metadata["performance"]["cell_updates"] == 4
    assert metadata["performance"]["peak_rss_bytes"] >= metadata["rss_before_bytes"]
    assert metadata["performance"]["output_size_bytes"] > 0
    assert metadata["performance"]["resource_trace"] == "resource_samples.csv"
    assert metadata["performance"]["resource_sample_count"] >= 1
    assert (tmp_path / "run" / "resource_samples.csv").exists()
    assert "step_elapsed_seconds" in trajectory.columns
    assert "step_cells_per_second" in trajectory.columns


@pytest.mark.parametrize("engine", ["continuous", "blocks"])
def test_custom_model_classes_survive_simulation_and_are_reported(tmp_path, engine):
    land_cover = tmp_path / f"land_cover_{engine}.tif"
    elevation = tmp_path / f"elevation_{engine}.tif"
    _write_raster(land_cover, np.array([[5, 90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation, np.array([[50, 50]], dtype=np.float32), dtype="float32", nodata=-9999)
    custom_classes = [{"code": 300, "name": "Agriculture", "color": "#c08020"}]
    inputs = load_raster_inputs(
        land_cover,
        elevation,
        soil_enabled=False,
        custom_class_mapping={300: [90]},
        custom_classes=custom_classes,
    )

    output_dir = tmp_path / f"run_{engine}"
    trajectory = run_raster_simulation(
        inputs,
        output_dir,
        ModelParameters(final_time=2, tide_height=0, sea_level_rise_rate=0),
        initial_year=2025,
        engine=engine,
        block_size=1,
        save_annual_states=True,
    )

    assert trajectory["custom_300"].tolist() == [1, 1]
    final_path = output_dir / "final_usos_2027.tif"
    with rasterio.open(final_path) as src:
        assert src.dtypes == ("uint16",)
        assert src.read(1).tolist() == [[1, 300]]
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["custom_model_classes"] == custom_classes
    assert metadata["final_class_counts"]["custom_300"] == 1

    spreadsheet = _write_simulation_spreadsheet(inputs, output_dir, trajectory)
    table = pd.read_csv(spreadsheet)
    assert table.loc[table.calendar_year == 2027, "state_300_agriculture_cells"].item() == 1


def test_custom_model_color_is_used_in_map_palette():
    palette, norm = _model_colormap([
        {"code": 300, "name": "Agriculture", "color": "#c08020"},
    ])

    assert palette.colors[300] == "#c08020"
    assert norm(300) == 300


def test_custom_class_mapping_accepts_portuguese_display_labels():
    custom_classes = [{"code": 300, "name": "Agricultura", "color": "#c08020"}]
    studio = SimpleNamespace(
        language_code="pt-BR",
        custom_model_classes=custom_classes,
        class_vars={
            90: SimpleNamespace(get=lambda: f"{translate('Custom class', 'pt-BR')}: Agricultura"),
            33: SimpleNamespace(get=lambda: translate("Water", "pt-BR")),
            24: SimpleNamespace(get=lambda: translate("Exclude", "pt-BR")),
        },
    )
    studio._canonical_role = lambda value: BRMangueStudio._canonical_role(studio, value)

    mapping, excluded, roles, custom_mapping = BRMangueStudio._mapping_from_ui(studio)

    assert custom_mapping == {300: [90]}
    assert mapping["water"] == [33]
    assert excluded == [24]
    assert roles[90] == "custom:300"


def test_saved_batch_project_runs_with_custom_model_class(tmp_path, capsys):
    land_cover = tmp_path / "land_cover.tif"
    elevation = tmp_path / "elevation.tif"
    _write_raster(land_cover, np.array([[5, 90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation, np.array([[50, 50]], dtype=np.float32), dtype="float32", nodata=-9999)
    project_path = tmp_path / "project.json"
    project_path.write_text(json.dumps({
        "format": "brmangue-studio-project",
        "version": "0.3.0",
        "inputs": {
            "land_cover": land_cover.name,
            "elevation": elevation.name,
            "mask": "",
            "soil": "",
        },
        "land_cover": {"band": 1, "reference_year": 2025},
        "class_roles": {"5": "Mangrove", "90": "custom:300"},
        "custom_model_classes": [
            {"code": 300, "name": "Agriculture", "color": "#c08020"}
        ],
        "parameters": {
            "initial_year": 2025,
            "final_year": 2026,
            "tide_height_m": 0,
            "sea_level_rise_mm_per_year": 0,
            "engine": "blocks",
            "block_size": 1,
            "soil_enabled": False,
            "allow_migration_without_soil": False,
        },
    }), encoding="utf-8")
    output_dir = tmp_path / "batch_output"

    assert _run_batch(project_path, output_dir) == 0
    capsys.readouterr()

    trajectory = pd.read_csv(output_dir / "trajectory.csv")
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    table = pd.read_csv(output_dir / "simulation_data.csv")
    assert trajectory.loc[0, "custom_300"] == 1
    assert metadata["custom_model_classes"][0]["name"] == "Agriculture"
    assert table.loc[table.calendar_year == 2026, "state_300_agriculture_cells"].item() == 1
    with rasterio.open(output_dir / "final_usos_2026.tif") as src:
        assert src.read(1).tolist() == [[1, 300]]
