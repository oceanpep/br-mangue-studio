import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from brmangue_lua.engine import BrMangueGrid, ModelParameters
from brmangue_lua.model_states import build_model_state_catalog
from brmangue_lua.persistent_blocks import PersistentBlockRunner
from brmangue_lua.raster_inputs import load_raster_inputs
from brmangue_lua.raster_runner import run_raster_simulation
from brmangue_studio.__main__ import _run_batch
from brmangue_studio.app import (
    BRMangueStudio,
    UNASSIGNED_ROLE,
    _model_colormap,
    _validate_class_assignments,
    _validate_class_coverage,
    _write_simulation_spreadsheet,
    _write_transition_report,
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
    ) as destination:
        destination.write(data, 1)


def _grid(state_codes, classes, elevations=None, soil=None):
    values = np.asarray(state_codes, dtype=np.uint16)
    catalog = build_model_state_catalog(classes)
    elevations = np.asarray(elevations if elevations is not None else np.ones(values.size), dtype=float)
    soil = np.asarray(soil if soil is not None else np.full(values.size, -999), dtype=np.int16)
    neighbors = tuple(
        tuple(neighbor for neighbor in (index - 1, index + 1) if 0 <= neighbor < values.size)
        for index in range(values.size)
    )
    return BrMangueGrid(
        land_cover_state=values,
        relative_elevation=elevations,
        soil_class=soil,
        column=np.arange(values.size),
        row=np.zeros(values.size, dtype=int),
        neighbors=neighbors,
        model_state_catalog=catalog,
    )


def test_block_runner_releases_input_grid_and_reports_performance(tmp_path):
    land_cover_path = tmp_path / "land_cover.tif"
    elevation_path = tmp_path / "dem.tif"
    _write_raster(land_cover_path, np.array([[5, 33], [6, 24]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation_path, np.ones((2, 2), dtype=np.float32), dtype="float32", nodata=-9999)
    inputs = load_raster_inputs(land_cover_path, elevation_path, soil_enabled=False)
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
    assert {"mangrove_extent", "annual_gain", "annual_loss", "annual_net_change", "cell_area_km2"}.issubset(trajectory.columns)
    assert int(trajectory.loc[0, "annual_net_change"]) == int(trajectory.loc[0, "annual_gain"] - trajectory.loc[0, "annual_loss"])
    assert inputs.grid is None
    assert inputs.n_cells == 4
    metadata = json.loads((tmp_path / "run" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["block_input_materialization"]["input_grid_released_after_persistent_copy"] is True
    assert metadata["performance"]["annual_steps"] == 1
    assert metadata["performance"]["cell_updates"] == 4
    assert metadata["performance"]["peak_rss_bytes"] >= metadata["rss_before_bytes"]
    assert metadata["performance"]["output_size_bytes"] > 0
    assert (tmp_path / "run" / "initial_state_2025.tif").exists()


def test_peak_memory_includes_sampler_spikes_between_annual_checkpoints(tmp_path, monkeypatch):
    import threading
    import brmangue_lua.raster_runner as module
    if module.psutil is None:
        pytest.skip('psutil is required for the resource sampler.')
    real_process = module.psutil.Process()
    sampled = threading.Event()

    class SampleSpikeProcess:
        def memory_info(self):
            if threading.current_thread().name == 'brmangue-resource-sampler':
                sampled.set()
                return SimpleNamespace(rss=9_000_000_000)
            return SimpleNamespace(rss=100_000_000)

        def __getattr__(self, name):
            return getattr(real_process, name)

    monkeypatch.setattr(module.psutil, 'Process', lambda: SampleSpikeProcess())
    original_step = BrMangueGrid.step

    def wait_for_sample(self, *args, **kwargs):
        assert sampled.wait(timeout=2)
        return original_step(self, *args, **kwargs)

    monkeypatch.setattr(BrMangueGrid, 'step', wait_for_sample)
    _write_raster(tmp_path/'cover.tif', np.array([[5]], dtype=np.uint8), dtype='uint8')
    _write_raster(tmp_path/'dem.tif', np.ones((1, 1), dtype=np.float32), dtype='float32', nodata=-9999)
    inputs = load_raster_inputs(tmp_path/'cover.tif', tmp_path/'dem.tif', soil_enabled=False)
    run_raster_simulation(inputs, tmp_path/'run', ModelParameters(final_time=1), engine='continuous')
    metadata = json.loads((tmp_path/'run/metadata.json').read_text())
    samples = pd.read_csv(tmp_path/'run/resource_samples.csv')
    assert samples.rss_bytes.max() == 9_000_000_000
    assert metadata['peak_rss_bytes'] == 9_000_000_000
    assert metadata['performance']['peak_rss_bytes'] == 9_000_000_000


@pytest.mark.parametrize("engine", ["continuous", "blocks"])
def test_raster_accretion_uses_mangrove_behavior_without_soil_raster(tmp_path, engine):
    land_cover_path = tmp_path / f"land_cover_{engine}.tif"
    elevation_path = tmp_path / f"dem_{engine}.tif"
    _write_raster(land_cover_path, np.array([[90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation_path, np.array([[1.0]], dtype=np.float32), dtype="float32", nodata=-9999)
    classes = [{
        "code": 300,
        "name": "Mangrove stand",
        "color": "#006d2c",
        "behavior": "mangrove",
    }]
    inputs = load_raster_inputs(
        land_cover_path,
        elevation_path,
        soil_enabled=False,
        custom_class_mapping={300: [90]},
        custom_classes=classes,
        class_mapping_mode="custom",
    )
    output_dir = tmp_path / f"accretion_without_soil_{engine}"
    trajectory = run_raster_simulation(
        inputs,
        output_dir,
        ModelParameters(final_time=1, tide_height=0, sea_level_rise_rate=0.0034),
        initial_year=2025,
        engine=engine,
        block_size=1,
        save_annual_states=False,
    )

    expected_accretion_m = (1.693 + 0.939 * 3.4) / 1000
    assert trajectory.loc[0, "min_elevation"] == pytest.approx(1.0 + expected_accretion_m)
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["soil_enabled"] is False
    assert metadata["parameters"]["legacy_lua_accretion_typo"] is False
    assert "mangrove accretion follows land-cover behavior" in metadata["soil_behavior_when_disabled"]


@pytest.mark.parametrize("engine", ["continuous", "blocks"])
def test_custom_class_code_survives_run_and_export(tmp_path, engine):
    land_cover_path = tmp_path / f"land_cover_{engine}.tif"
    elevation_path = tmp_path / f"dem_{engine}.tif"
    _write_raster(land_cover_path, np.array([[90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation_path, np.array([[50]], dtype=np.float32), dtype="float32", nodata=-9999)
    custom_classes = [{"code": 300, "name": "Agriculture", "color": "#c08020", "behavior": "fixed"}]
    inputs = load_raster_inputs(
        land_cover_path,
        elevation_path,
        soil_enabled=False,
        custom_class_mapping={300: [90]},
        custom_classes=custom_classes,
        class_mapping_mode="custom",
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
    assert trajectory["class_300"].tolist() == [1, 1]
    with rasterio.open(output_dir / "final_state_2027.tif") as source:
        assert source.dtypes == ("uint16",)
        assert source.read(1).tolist() == [[300]]
        exported_catalog = json.loads(source.tags()["model_state_catalog"])
    assert exported_catalog["states"]["300"]["name"] == "Agriculture"
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["custom_model_classes"] == custom_classes
    assert metadata["final_class_counts"]["class_300"] == 1
    table = pd.read_csv(_write_simulation_spreadsheet(inputs, output_dir, trajectory))
    assert table.loc[table.calendar_year == 2027, "state_300_agriculture_cells"].item() == 1


@pytest.mark.parametrize("engine", ["continuous", "blocks"])
def test_custom_behavior_flood_transition_uses_catalog(tmp_path, engine):
    land_cover_path = tmp_path / f"land_cover_{engine}.tif"
    elevation_path = tmp_path / f"dem_{engine}.tif"
    _write_raster(land_cover_path, np.array([[33, 90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation_path, np.array([[2, 1]], dtype=np.float32), dtype="float32", nodata=-9999)
    custom_classes = [
        {"code": 300, "name": "Waterbody", "color": "#2b8cbe", "behavior": "water"},
        {"code": 301, "name": "Intertidal flats", "color": "#c08020", "behavior": "bare_soil"},
    ]
    inputs = load_raster_inputs(
        land_cover_path,
        elevation_path,
        soil_enabled=False,
        custom_class_mapping={300: [33], 301: [90]},
        custom_classes=custom_classes,
        class_mapping_mode="custom",
    )
    output_dir = tmp_path / f"run_{engine}"
    trajectory = run_raster_simulation(
        inputs,
        output_dir,
        ModelParameters(final_time=1, tide_height=0, sea_level_rise_rate=0),
        initial_year=2025,
        engine=engine,
        block_size=1,
        save_annual_states=True,
    )
    assert trajectory.loc[0, "class_301"] == 0
    assert trajectory.loc[0, "flooded_bare"] == 1
    with rasterio.open(output_dir / "final_state_2026.tif") as source:
        assert source.read(1).tolist() == [[300, 302]]
    derived = _write_transition_report(
        land_cover_path,
        1,
        inputs,
        np.array([300, 302]),
        {33: "custom:300", 90: "custom:301"},
        output_dir / "transitions.csv",
    )
    transitions = pd.read_csv(derived)
    item = transitions.loc[transitions.source_land_cover_code == 90].iloc[0]
    assert item.source_custom_class == "Intertidal flats"
    assert item.destination_model_state == "Flooded Intertidal flats"


@pytest.mark.parametrize("engine", ["continuous", "blocks"])
def test_derived_codes_above_int16_remain_unsigned_in_outputs(tmp_path, engine):
    land_cover_path = tmp_path / f"land_cover_{engine}.tif"
    elevation_path = tmp_path / f"dem_{engine}.tif"
    _write_raster(land_cover_path, np.array([[33, 90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation_path, np.array([[2, 1]], dtype=np.float32), dtype="float32", nodata=-9999)
    classes = [
        {"code": 32766, "name": "Waterbody", "color": "#2b8cbe", "behavior": "water"},
        {"code": 32767, "name": "Wetland", "color": "#99bb77", "behavior": "natural_vegetation"},
    ]
    inputs = load_raster_inputs(
        land_cover_path,
        elevation_path,
        soil_enabled=False,
        custom_class_mapping={32766: [33], 32767: [90]},
        custom_classes=classes,
        class_mapping_mode="custom",
    )
    callback_states = []
    output_dir = tmp_path / f"high_code_{engine}"
    run_raster_simulation(
        inputs,
        output_dir,
        ModelParameters(final_time=1, tide_height=0, sea_level_rise_rate=0),
        initial_year=2025,
        engine=engine,
        block_size=1,
        step_callback=lambda event: callback_states.append(event["land_cover_state"]),
    )
    with rasterio.open(output_dir / "final_state_2026.tif") as source:
        assert source.dtypes == ("uint16",)
        assert source.read(1).tolist() == [[32766, 32768]]
    assert callback_states[0].dtype == np.uint16
    assert callback_states[0].tolist() == [32766, 32768]


@pytest.mark.parametrize(
    "behavior",
    ["mangrove", "natural_vegetation", "bare_soil", "anthropized", "fixed", "water"],
)
def test_flood_rules_follow_each_configured_class_behavior(behavior):
    classes = [
        {"code": 300, "name": "Target class", "behavior": behavior, "color": "#556677"},
        {"code": 301, "name": "Water body", "behavior": "water", "color": "#2b8cbe"},
    ]
    grid = _grid([301, 300], classes, elevations=[2.0, 1.0])
    expected = grid.model_state_catalog["flooded_codes"].get("300", 300)
    grid.step(1, ModelParameters(final_time=1, sea_level_rise_rate=0))
    assert int(grid.land_cover_state[1]) == expected


def test_custom_water_class_drives_flooding_for_another_class():
    catalog = build_model_state_catalog([
        {"code": 300, "name": "Waterbody", "behavior": "water", "color": "#2b8cbe"},
        {"code": 301, "name": "Seasonal wetland", "behavior": "natural_vegetation", "color": "#99bb77"},
    ])
    grid = BrMangueGrid(
        land_cover_state=np.array([300, 301], dtype=np.uint16),
        relative_elevation=np.array([2.0, 1.0]),
        soil_class=np.array([-999, -999], dtype=np.int16),
        column=np.array([0, 1]),
        row=np.array([0, 0]),
        neighbors=((1,), (0,)),
        model_state_catalog=catalog,
    )
    grid.step(1, ModelParameters(final_time=1, sea_level_rise_rate=0))
    assert grid.land_cover_state.tolist() == [300, catalog["flooded_codes"]["301"]]


def test_mangrove_migration_uses_one_generic_derived_state():
    classes = [
        {"code": 300, "name": "Mangrove patch", "behavior": "mangrove", "color": "#006d2c"},
        {"code": 301, "name": "Freshwater vegetation", "behavior": "natural_vegetation", "color": "#99bb77"},
        {"code": 302, "name": "Bare area", "behavior": "bare_soil", "color": "#777777"},
    ]
    grid = _grid([300, 301, 302], classes, elevations=[1.0, 1.0, 1.0])
    trajectory = grid.run(ModelParameters(
        final_time=2,
        sea_level_rise_rate=0,
        allow_migration_without_soil=True,
        migration_maturity_years=1,
    ))
    migrated_code = grid.model_state_catalog["migrated_mangrove_code"]
    assert grid.land_cover_state.tolist() == [300, migrated_code, migrated_code]
    assert grid.model_state_catalog["states"][str(migrated_code)]["name"] == "Migrated mangrove"
    assert trajectory.loc[1, "migrated_mangrove"] == 2
    assert grid.last_transition_metrics["mangrove_extent"] == 3


def test_continuous_and_persistent_block_engines_match(tmp_path):
    classes = [
        {"code": 300, "name": "Waterbody", "behavior": "water", "color": "#2b8cbe"},
        {"code": 301, "name": "Natural vegetation", "behavior": "natural_vegetation", "color": "#99bb77"},
        {"code": 302, "name": "Bare area", "behavior": "bare_soil", "color": "#777777"},
        {"code": 303, "name": "Mangrove patch", "behavior": "mangrove", "color": "#006d2c"},
    ]
    make_grid = lambda: _grid([303, 301, 302, 300], classes, elevations=[2.0, 1.5, 1.0, 0.5])
    params = ModelParameters(
        final_time=4,
        tide_height=6,
        sea_level_rise_rate=0.2,
        allow_migration_without_soil=True,
        migration_maturity_years=1,
    )
    continuous = make_grid()
    expected = continuous.run(params)
    runner = PersistentBlockRunner.create_from_grid(
        make_grid(), tmp_path / "block_workspace", block_size=1
    )
    try:
        assert expected.equals(runner.run(params))
        assert np.array_equal(continuous.land_cover_state, runner.current["land_cover_state"][:])
        assert np.array_equal(continuous.relative_elevation, runner.current["relative_elevation"][:])
        assert np.array_equal(continuous.soil_class, runner.current["soil_class"][:])
        metadata = json.loads((runner.root / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["model_state_catalog"] == runner.model_state_catalog
    finally:
        runner.close()


def test_project_palette_uses_catalog_colors():
    catalog = build_model_state_catalog([
        {"code": 300, "name": "Agriculture", "behavior": "fixed", "color": "#c08020"},
    ])
    palette, norm = _model_colormap(catalog)
    assert palette.colors[300] == "#c08020"
    assert norm(300) == 300


def test_transition_report_names_derived_states_from_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr("brmangue_studio.app.TRANSITION_REPORT_CHUNK_CELLS", 1)
    land_cover_path = tmp_path / "land_cover.tif"
    elevation_path = tmp_path / "dem.tif"
    _write_raster(land_cover_path, np.array([[90, 90, 90, 90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation_path, np.ones((1, 4), dtype=np.float32), dtype="float32", nodata=-9999)
    inputs = load_raster_inputs(
        land_cover_path,
        elevation_path,
        soil_enabled=False,
        custom_class_mapping={300: [90]},
        custom_classes=[{
            "code": 300,
            "name": "Seasonal wetland",
            "color": "#2299aa",
            "behavior": "natural_vegetation",
        }],
        class_mapping_mode="custom",
    )
    flooded_code = inputs.metadata["model_state_catalog"]["flooded_codes"]["300"]
    report = _write_transition_report(
        land_cover_path,
        1,
        inputs,
        np.array([flooded_code, 300, flooded_code, 300]),
        {90: "custom:300"},
        tmp_path / "transitions.csv",
    )
    rows = pd.read_csv(report)
    assert rows.source_custom_class.tolist() == ["Seasonal wetland"] * 2
    assert rows.destination_model_state.tolist() == ["Seasonal wetland", "Flooded Seasonal wetland"]
    assert rows.cells.tolist() == [2, 2]


def test_custom_class_mapping_accepts_portuguese_display_labels():
    classes = [{"code": 300, "name": "Agricultura", "color": "#c08020"}]
    studio = SimpleNamespace(
        language_code="pt-BR",
        custom_model_classes=classes,
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
    studio._canonical_custom_behavior = lambda value: BRMangueStudio._canonical_custom_behavior(studio, value)
    assert studio._canonical_custom_behavior("Vegetação natural") == "natural_vegetation"
    assert BRMangueStudio._display_custom_behavior(studio, "mangrove") == "Fonte de mangue"


def test_custom_mapping_mode_starts_blank_and_hides_standard_roles():
    studio = SimpleNamespace(
        language_code="en",
        custom_model_classes=[{"code": 300, "name": "Waterbody", "color": "#2299aa", "behavior": "water"}],
        class_mapping_mode_var=SimpleNamespace(get=lambda: "custom"),
        _custom_role_label=lambda item: f"Custom class: {item['name']}",
        _display_role=lambda role: translate(role, "en"),
    )
    assert BRMangueStudio._role_options(studio) == ("Unassigned", "Exclude", "Custom class: Waterbody")
    assert BRMangueStudio._initial_source_role(studio, 33) == "Unassigned"


def test_custom_mapping_mode_requires_explicit_assignments():
    with pytest.raises(ValueError, match="Unassigned codes: 5, 33"):
        _validate_class_assignments(
            {33: UNASSIGNED_ROLE, 5: UNASSIGNED_ROLE},
            mode="custom",
            custom_classes=[{"code": 300, "name": "Aquatic", "color": "#2299aa"}],
        )
    _validate_class_assignments(
        {33: "custom:300", 5: "Exclude"},
        mode="custom",
        custom_classes=[{"code": 300, "name": "Aquatic", "color": "#2299aa"}],
    )
    with pytest.raises(ValueError, match="not inspected.*24"):
        _validate_class_coverage({33: "custom:300"}, {"33": 2, "24": 4}, mode="custom")
    _validate_class_coverage({33: "custom:300", 24: "Exclude"}, {"33": 2}, mode="custom")


def test_saved_standard_project_can_mix_standard_and_custom_classes(tmp_path, capsys):
    land_cover_path = tmp_path / "land_cover.tif"
    elevation_path = tmp_path / "dem.tif"
    _write_raster(land_cover_path, np.array([[5, 90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation_path, np.ones((1, 2), dtype=np.float32), dtype="float32", nodata=-9999)
    project_path = tmp_path / "project.json"
    project_path.write_text(json.dumps({
        "format": "brmangue-studio-project",
        "version": "0.3.0",
        "inputs": {"land_cover": land_cover_path.name, "elevation": elevation_path.name, "mask": "", "soil": ""},
        "land_cover": {"band": 1, "reference_year": 2025},
        "class_roles": {"5": "Mangrove", "90": "custom:300"},
        "custom_model_classes": [{
            "code": 300, "name": "Agriculture", "color": "#c08020", "behavior": "natural_vegetation"
        }],
        "parameters": {
            "initial_year": 2025, "final_year": 2026, "tide_height_m": 0,
            "sea_level_rise_mm_per_year": 0, "engine": "blocks", "block_size": 1,
            "soil_enabled": False, "allow_migration_without_soil": False,
        },
    }), encoding="utf-8")
    output_dir = tmp_path / "batch_output"
    assert _run_batch(project_path, output_dir) == 0
    capsys.readouterr()
    trajectory = pd.read_csv(output_dir / "trajectory.csv")
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    table = pd.read_csv(output_dir / "simulation_data.csv")
    assert trajectory.loc[0, "class_300"] == 1
    assert metadata["model_state_catalog"]["states"]["300"]["name"] == "Agriculture"
    assert table.loc[table.calendar_year == 2026, "state_300_agriculture_cells"].item() == 1
    with rasterio.open(output_dir / "final_state_2026.tif") as source:
        assert source.read(1).tolist() == [[1, 300]]


def test_saved_custom_mode_project_runs_without_standard_assignments(tmp_path, capsys):
    land_cover_path = tmp_path / "land_cover_custom.tif"
    elevation_path = tmp_path / "dem_custom.tif"
    _write_raster(land_cover_path, np.array([[90, 5]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation_path, np.ones((1, 2), dtype=np.float32), dtype="float32", nodata=-9999)
    project_path = tmp_path / "custom_project.json"
    project_path.write_text(json.dumps({
        "format": "brmangue-studio-project",
        "version": "0.3.0",
        "inputs": {"land_cover": land_cover_path.name, "elevation": elevation_path.name, "mask": "", "soil": ""},
        "land_cover": {"band": 1, "reference_year": 2025},
        "class_mapping_mode": "custom",
        "class_roles": {"90": "custom:300", "5": "Exclude"},
        "custom_model_classes": [{"code": 300, "name": "Surface water", "color": "#2299aa", "behavior": "water"}],
        "parameters": {
            "initial_year": 2025, "final_year": 2026, "tide_height_m": 0,
            "sea_level_rise_mm_per_year": 0, "engine": "continuous", "soil_enabled": False,
        },
    }), encoding="utf-8")
    output_dir = tmp_path / "custom_output"
    assert _run_batch(project_path, output_dir) == 0
    capsys.readouterr()
    with rasterio.open(output_dir / "final_state_2026.tif") as source:
        assert source.read(1).tolist() == [[300, 0]]
