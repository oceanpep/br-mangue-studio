import numpy as np
import json
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from types import SimpleNamespace

from brmangue_lua.engine import (
    AREA_ANTROPIZADA_INUNDADO,
    BrMangueGrid,
    MANGUE,
    MANGUE_INUNDADO,
    MANGUE_MIGRADO,
    MAR,
    ModelParameters,
    SOLO_DESCOBERTO_INUNDADO,
    VEGETACAO_TERRESTRE_INUNDADO,
)
from brmangue_lua.raster_inputs import load_raster_inputs
from brmangue_lua.raster_runner import run_raster_simulation
from brmangue_lua.persistent_blocks import PersistentBlockRunner
from brmangue_studio.__main__ import _run_batch
from brmangue_studio.app import (
    BRMangueStudio,
    UNASSIGNED_ROLE,
    _validate_class_assignments,
    _validate_class_coverage,
    _model_colormap,
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
    custom_classes = [{
        "code": 300,
        "name": "Agriculture",
        "color": "#c08020",
        "behavior": "fixed",
    }]
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


@pytest.mark.parametrize("engine", ["continuous", "blocks"])
def test_raster_workflow_applies_custom_behavior_and_exports_provenance(tmp_path, engine):
    land_cover = tmp_path / f"land_cover_profile_{engine}.tif"
    elevation = tmp_path / f"elevation_profile_{engine}.tif"
    _write_raster(land_cover, np.array([[33, 90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation, np.array([[2, 1]], dtype=np.float32), dtype="float32", nodata=-9999)
    custom_classes = [{
        "code": 300,
        "name": "Intertidal flats",
        "color": "#c08020",
        "behavior": "bare_soil",
    }]
    inputs = load_raster_inputs(
        land_cover,
        elevation,
        soil_enabled=False,
        custom_class_mapping={300: [90]},
        custom_classes=custom_classes,
    )
    output_dir = tmp_path / f"profile_run_{engine}"

    trajectory = run_raster_simulation(
        inputs,
        output_dir,
        ModelParameters(final_time=1, tide_height=0, sea_level_rise_rate=0),
        initial_year=2025,
        engine=engine,
        block_size=1,
        save_annual_states=True,
    )

    assert trajectory.loc[0, "custom_300"] == 0
    assert trajectory.loc[0, "flooded_bare"] == 1
    with rasterio.open(output_dir / "final_usos_2026.tif") as src:
        assert src.read(1).tolist() == [[3, SOLO_DESCOBERTO_INUNDADO]]
    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["custom_model_classes"] == custom_classes
    report = _write_transition_report(
        land_cover,
        1,
        inputs,
        np.array([3, SOLO_DESCOBERTO_INUNDADO]),
        {33: "Water", 90: "custom:300"},
        output_dir / "transition_by_land_cover_code.csv",
    )
    transitions = pd.read_csv(report)
    custom_transition = transitions.loc[
        transitions.source_land_cover_code == 90
    ].iloc[0]
    assert custom_transition.source_custom_class == "Intertidal flats"
    assert custom_transition.destination_model_state == "SOLO_DESCOBERTO_INUNDADO"


@pytest.mark.parametrize(
    ("behavior", "expected"),
    [
        ("mangrove", MANGUE_INUNDADO),
        ("natural_vegetation", VEGETACAO_TERRESTRE_INUNDADO),
        ("bare_soil", SOLO_DESCOBERTO_INUNDADO),
        ("anthropized", AREA_ANTROPIZADA_INUNDADO),
        ("fixed", 300),
        ("water", 300),
    ],
)
def test_custom_behavior_profiles_apply_existing_flood_rules(behavior, expected):
    grid = BrMangueGrid(
        usos=np.array([MAR, 300], dtype=np.int16),
        alt2=np.array([2.0, 1.0]),
        classe_solos=np.array([-999, -999], dtype=np.int16),
        col=np.array([0, 1]),
        lin=np.array([0, 0]),
        neighbors=((1,), (0,)),
        custom_state_codes=(300,),
        custom_state_behaviors={300: behavior},
    )

    grid.step(1, ModelParameters(final_time=1, sea_level_rise_rate=0))

    assert int(grid.usos[1]) == expected


def test_custom_water_profile_acts_as_a_flooding_source():
    grid = BrMangueGrid(
        usos=np.array([300, 301], dtype=np.int16),
        alt2=np.array([2.0, 1.0]),
        classe_solos=np.array([-999, -999], dtype=np.int16),
        col=np.array([0, 1]),
        lin=np.array([0, 0]),
        neighbors=((1,), (0,)),
        custom_state_codes=(300, 301),
        custom_state_behaviors={300: "water", 301: "bare_soil"},
    )

    grid.step(1, ModelParameters(final_time=1, sea_level_rise_rate=0))

    assert grid.usos.tolist() == [300, SOLO_DESCOBERTO_INUNDADO]


def test_custom_mangrove_profile_seeds_migration_and_counts_as_active_extent():
    grid = BrMangueGrid(
        usos=np.array([300, 301, 302], dtype=np.int16),
        alt2=np.array([1.0, 1.0, 1.0]),
        classe_solos=np.array([-999, -999, -999], dtype=np.int16),
        col=np.array([0, 1, 2]),
        lin=np.array([0, 0, 0]),
        neighbors=((1,), (0, 2), (1,)),
        custom_state_codes=(300, 301, 302),
        custom_state_behaviors={
            300: "mangrove",
            301: "natural_vegetation",
            302: "bare_soil",
        },
    )

    grid.run(ModelParameters(
        final_time=2,
        sea_level_rise_rate=0,
        allow_migration_without_soil=True,
        migration_maturity_years=1,
    ))

    assert grid.usos.tolist() == [300, MANGUE_MIGRADO, MANGUE_MIGRADO]
    assert grid.last_transition_metrics["mangrove_extent"] == 3
    assert grid.last_transition_metrics["annual_gain"] == 1


def test_custom_profiles_match_continuous_and_persistent_block_engines(tmp_path):
    def custom_grid():
        return BrMangueGrid(
            usos=np.array([300, 301, 302, MANGUE], dtype=np.int16),
            alt2=np.array([2.0, 1.5, 1.0, 0.5]),
            classe_solos=np.array([-999, -999, -999, -999], dtype=np.int16),
            col=np.array([0, 1, 2, 3]),
            lin=np.array([0, 0, 0, 0]),
            neighbors=((1,), (0, 2), (1, 3), (2,)),
            custom_state_codes=(300, 301, 302),
            custom_state_behaviors={
                300: "water",
                301: "natural_vegetation",
                302: "bare_soil",
            },
        )

    params = ModelParameters(
        final_time=4,
        tide_height=6,
        sea_level_rise_rate=0.2,
        allow_migration_without_soil=True,
        migration_maturity_years=1,
    )
    continuous = custom_grid()
    expected = continuous.run(params)
    runner = PersistentBlockRunner.create_from_grid(
        custom_grid(), tmp_path / "custom-profile-workspace", block_size=1
    )
    try:
        actual = runner.run(params)
        assert expected.equals(actual)
        assert continuous.usos.tolist() == runner.current["usos"].tolist()
        assert continuous.alt2.tolist() == runner.current["alt2"].tolist()
        assert continuous.classe_solos.tolist() == runner.current["classe_solos"].tolist()
        assert json.loads((runner.root / "metadata.json").read_text())[
            "custom_model_state_behaviors"
        ] == {"300": "water", "301": "natural_vegetation", "302": "bare_soil"}
    finally:
        runner.close()


def test_custom_model_color_is_used_in_map_palette():
    palette, norm = _model_colormap([
        {"code": 300, "name": "Agriculture", "color": "#c08020"},
    ])

    assert palette.colors[300] == "#c08020"
    assert norm(300) == 300


def test_transition_report_keeps_custom_source_identity_for_derived_states(tmp_path, monkeypatch):
    monkeypatch.setattr("brmangue_studio.app.TRANSITION_REPORT_CHUNK_CELLS", 1)
    land_cover = tmp_path / "land_cover.tif"
    elevation = tmp_path / "elevation.tif"
    _write_raster(land_cover, np.array([[90, 90, 90, 90]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation, np.array([[1, 1, 1, 1]], dtype=np.float32), dtype="float32", nodata=-9999)
    inputs = load_raster_inputs(
        land_cover,
        elevation,
        soil_enabled=False,
        custom_class_mapping={300: [90]},
        custom_classes=[{
            "code": 300,
            "name": "Seasonal wetland",
            "color": "#2299aa",
            "behavior": "natural_vegetation",
        }],
    )

    report = _write_transition_report(
        land_cover,
        1,
        inputs,
        np.array([VEGETACAO_TERRESTRE_INUNDADO, 8, VEGETACAO_TERRESTRE_INUNDADO, 8]),
        {90: "custom:300"},
        tmp_path / "transition.csv",
    )

    table = pd.read_csv(report)
    custom_rows = table.loc[table.source_land_cover_code == 90]
    assert custom_rows.source_custom_class.tolist() == ["Seasonal wetland"] * 2
    assert custom_rows.behavior_profile.tolist() == ["natural_vegetation"] * 2
    assert custom_rows.destination_model_code.tolist() == [8, VEGETACAO_TERRESTRE_INUNDADO]
    assert custom_rows.cells.tolist() == [2, 2]


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

    studio._canonical_custom_behavior = lambda value: BRMangueStudio._canonical_custom_behavior(studio, value)
    assert studio._canonical_custom_behavior("Vegetação natural") == "natural_vegetation"
    assert BRMangueStudio._display_custom_behavior(studio, "mangrove") == "Fonte de mangue"


def test_custom_mapping_mode_starts_blank_and_hides_standard_model_roles():
    custom_classes = [{"code": 300, "name": "Waterbody", "color": "#2299aa", "behavior": "water"}]
    studio = SimpleNamespace(
        language_code="en",
        custom_model_classes=custom_classes,
        class_mapping_mode_var=SimpleNamespace(get=lambda: "custom"),
        _custom_role_label=lambda item: f"Custom class: {item['name']}",
        _display_role=lambda role: translate(role, "en"),
    )

    options = BRMangueStudio._role_options(studio)
    initial_role = BRMangueStudio._initial_source_role(studio, 33)

    assert options == ("Unassigned", "Exclude", "Custom class: Waterbody")
    assert initial_role == "Unassigned"
    assert "Water" not in options
    assert "Mangrove" not in options


def test_custom_mapping_mode_rejects_unassigned_codes_and_accepts_explicit_mapping():
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
        _validate_class_coverage(
            {33: "custom:300"},
            {"33": 2, "24": 4},
            mode="custom",
        )
    _validate_class_coverage(
        {33: "custom:300", 24: "Exclude"},
        {"33": 2},
        mode="custom",
    )


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
            {
                "code": 300,
                "name": "Agriculture",
                "color": "#c08020",
                "behavior": "natural_vegetation",
            }
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
    assert metadata["custom_model_classes"][0]["behavior"] == "natural_vegetation"
    assert table.loc[table.calendar_year == 2026, "state_300_agriculture_cells"].item() == 1
    with rasterio.open(output_dir / "final_usos_2026.tif") as src:
        assert src.read(1).tolist() == [[1, 300]]


def test_saved_custom_mode_project_runs_without_standard_class_assignments(tmp_path, capsys):
    land_cover = tmp_path / "land_cover_custom_mode.tif"
    elevation = tmp_path / "elevation_custom_mode.tif"
    _write_raster(land_cover, np.array([[90, 5]], dtype=np.uint8), dtype="uint8")
    _write_raster(elevation, np.array([[50, 50]], dtype=np.float32), dtype="float32", nodata=-9999)
    project_path = tmp_path / "custom_mode_project.json"
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
        "class_mapping_mode": "custom",
        "class_roles": {"90": "custom:300", "5": "Exclude"},
        "custom_model_classes": [
            {
                "code": 300,
                "name": "Surface water",
                "color": "#2299aa",
                "behavior": "water",
            }
        ],
        "parameters": {
            "initial_year": 2025,
            "final_year": 2026,
            "tide_height_m": 0,
            "sea_level_rise_mm_per_year": 0,
            "engine": "continuous",
            "soil_enabled": False,
            "allow_migration_without_soil": False,
        },
    }), encoding="utf-8")
    output_dir = tmp_path / "custom_mode_output"

    assert _run_batch(project_path, output_dir) == 0
    capsys.readouterr()

    with rasterio.open(output_dir / "final_usos_2026.tif") as src:
        assert src.read(1).tolist() == [[300, 0]]
