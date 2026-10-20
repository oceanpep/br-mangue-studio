import json

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
from brmangue_lua.sea_level import TRAJECTORY_CSV_EXAMPLE, SeaLevelTrajectory, trajectory_from_project
from brmangue_studio.__main__ import _run_batch


def line_grid(states=(20, 30, 30, 50, 40, 30), elevations=None):
    n = len(states)
    return BrMangueGrid(
        land_cover_state=np.array(states, dtype=np.uint16),
        relative_elevation=np.array(elevations if elevations is not None else np.linspace(0.01, 0.06, n)),
        soil_class=np.full(n, -999, dtype=np.int16),
        column=np.arange(n), row=np.zeros(n, dtype=int),
        neighbors=tuple(tuple(j for j in (i - 1, i + 1) if 0 <= j < n) for i in range(n)),
        model_state_catalog=build_model_state_catalog([
            {"code": 20, "name": "Mangrove", "behavior": "mangrove", "color": "#006d2c"},
            {"code": 30, "name": "Forest", "behavior": "natural_vegetation", "color": "#55aa33"},
            {"code": 40, "name": "Flat", "behavior": "bare_soil", "color": "#aaaaaa"},
            {"code": 50, "name": "Ocean", "behavior": "water", "color": "#3333ff"},
        ]),
    )


def test_decadal_interpolation_rebases_at_initial_year_and_preserves_endpoint():
    curve = SeaLevelTrajectory((2020, 2030, 2040), (100, 140, 220))
    params = ModelParameters(final_time=15, sea_level_trajectory=curve, sea_level_reference_year=2025)
    assert curve.level_mm(2025) == 120
    assert params.sea_level_at(0) == (0, 0)
    assert params.sea_level_at(1) == pytest.approx((0.004, 0.004))
    assert params.sea_level_at(5) == pytest.approx((0.020, 0.004))
    assert params.sea_level_at(6) == pytest.approx((0.028, 0.008))
    assert params.sea_level_at(15) == pytest.approx((0.100, 0.008))
    assert sum(params.sea_level_at(i)[1] for i in range(1, 16)) == pytest.approx(0.100)


def test_rates_can_decelerate_without_forcing_a_monotone_acceleration():
    params = ModelParameters(final_time=3, sea_level_trajectory=SeaLevelTrajectory((2025, 2026, 2027, 2028), (0, 4, 6, 11)))
    assert [params.sea_level_at(i)[1] * 1000 for i in range(1, 4)] == pytest.approx([4, 2, 5])


@pytest.mark.parametrize("constant_accretion", [None, 2.4])
def test_linear_curve_reproduces_constant_rate_states_elevation_and_maturation(constant_accretion):
    common = dict(final_time=5, tide_height=0.02, allow_migration_without_soil=True, accretion_rate_mm=constant_accretion)
    fixed = ModelParameters(**common, sea_level_rise_rate=0.005)
    curve = ModelParameters(**common, sea_level_trajectory=SeaLevelTrajectory((2020, 2040), (500, 600)))
    a, b = line_grid(), line_grid()
    a.run(fixed)
    b.run(curve)
    np.testing.assert_array_equal(a.land_cover_state, b.land_cover_state)
    np.testing.assert_array_equal(a.migration_age, b.migration_age)
    np.testing.assert_allclose(a.relative_elevation, b.relative_elevation, atol=1e-12)


def test_nonlinear_increments_are_not_double_accumulated_or_replaced_by_legacy_rate():
    curve = SeaLevelTrajectory((2025, 2026, 2027, 2028, 2029), (500, 501, 503, 507, 515))
    params = ModelParameters(final_time=4, sea_level_rise_rate=999, sea_level_trajectory=curve)
    water = line_grid((50,), (1.0,))
    water.run(params)
    assert water.relative_elevation[0] == pytest.approx(1.015)
    mangrove = line_grid((20,), (1.0,))
    mangrove.run(params)
    assert mangrove.relative_elevation[0] == pytest.approx(1 + (4 * 1.693 + 0.939 * 15) / 1000)


def test_variable_forcing_matches_memory_and_persistent_blocks(tmp_path):
    params = ModelParameters(
        final_time=5, tide_height=0.02, allow_migration_without_soil=True,
        sea_level_trajectory=SeaLevelTrajectory((2025, 2027, 2030), (100, 120, 200)),
    )
    reference, memory = line_grid(), line_grid()
    reference.run(params)
    memory.run_blocks(params, block_size=2)
    persistent = PersistentBlockRunner.create_from_grid(line_grid(), tmp_path / "workspace", block_size=2)
    try:
        persistent.run(params)
        for values in (memory.land_cover_state, persistent.current["land_cover_state"]):
            np.testing.assert_array_equal(reference.land_cover_state, values)
        np.testing.assert_array_equal(reference.migration_age, persistent.current["migration_age"])
        np.testing.assert_array_equal(reference.soil_class, persistent.current["soil_class"])
        np.testing.assert_allclose(reference.relative_elevation, memory.relative_elevation, atol=1e-12)
        np.testing.assert_allclose(reference.relative_elevation, persistent.current["relative_elevation"], atol=1e-12)
    finally:
        persistent.close()


@pytest.mark.parametrize("years,levels", [((2025,), (0,)), ((2025, 2025), (0, 1)), ((2026, 2025), (0, 1)), ((2025.5, 2026), (0, 1)), ((2025, 2026), (0, float("nan"))), ((2025, 2026), (0, float("inf"))), ((2025, 2026), (0,))])
def test_invalid_samples_are_rejected(years, levels):
    with pytest.raises(ValueError):
        SeaLevelTrajectory(years, levels)


def test_no_extrapolation_and_full_period_required():
    curve = SeaLevelTrajectory((2030, 2040), (0, 40))
    for year in (2025, 2041):
        with pytest.raises(ValueError, match="outside"):
            curve.level_mm(year)
    with pytest.raises(ValueError, match="outside"):
        ModelParameters(final_time=5, sea_level_trajectory=curve)
    with pytest.raises(ValueError, match="outside"):
        ModelParameters(final_time=15, sea_level_reference_year=2030, sea_level_trajectory=curve)


def test_downloadable_example_matches_app_example_and_covers_2025_to_2100(tmp_path):
    from pathlib import Path
    path = tmp_path / 'example.csv'
    path.write_text(TRAJECTORY_CSV_EXAMPLE, encoding='utf-8')
    curve = SeaLevelTrajectory.from_csv(path)
    curve.validate_period(2025, 2100)
    assert 'SYNTHETIC' in TRAJECTORY_CSV_EXAMPLE
    assert (Path(__file__).parents[1] / 'examples/sea_level_SYNTHETIC_example.csv').read_text() == TRAJECTORY_CSV_EXAMPLE


@pytest.mark.parametrize("text", ["year,sea_level_mm\n2025,100\n2030,125\n", "\ufeff# Synthetic test\nyear;sea_level_mm\n2025;100,0\n2030;125,0\n"])
def test_csv_loading_and_embedded_project_survive_removal_of_source(tmp_path, text):
    path = tmp_path / "curve.csv"
    path.write_text(text, encoding="utf-8")
    curve = SeaLevelTrajectory.from_csv(path)
    assert curve.level_mm(2027) == 110
    assert len(curve.source_sha256) == 64
    config = {"sea_level_mode": "trajectory", "sea_level_trajectory": curve.to_dict(), "sea_level_trajectory_file": path.name}
    path.unlink()
    assert trajectory_from_project(config, tmp_path) == curve
    assert trajectory_from_project({}, tmp_path) is None


@pytest.mark.parametrize("text", ["year,rate\n2025,4", "year,sea_level_mm\n2025.5,4\n2026,5", "year,sea_level_mm\n2025,\n2026,2", "year,sea_level_mm\n2025,nan\n2026,2", ""])
def test_invalid_csv_rejected(tmp_path, text):
    path = tmp_path / "bad.csv"
    path.write_text(text)
    with pytest.raises(ValueError):
        SeaLevelTrajectory.from_csv(path)


@pytest.mark.parametrize("engine", ["continuous", "blocks"])
def test_saved_batch_project_exports_exact_annual_forcing_and_metadata(tmp_path, capsys, engine):
    for name, values, nodata in [("cover.tif", [[5, 6], [33, 24]], 0), ("dem.tif", [[1, 2], [3, 4]], -9999)]:
        with rasterio.open(tmp_path / name, "w", driver="GTiff", height=2, width=2, count=1,
                           dtype="float32", nodata=nodata, crs="EPSG:5880", transform=from_origin(500000, 9700000, 30, 30)) as dst:
            dst.write(np.array(values, dtype=np.float32), 1)
    curve = SeaLevelTrajectory((2020, 2030), (100, 150))
    config = {
        "inputs": {"land_cover": "cover.tif", "elevation": "dem.tif"},
        "class_roles": {"5": "Mangrove", "6": "Natural vegetation", "33": "Water", "24": "Anthropized / blocked"},
        "parameters": {"initial_year": 2025, "final_year": 2028, "engine": engine,
                       "sea_level_mode": "trajectory", "sea_level_trajectory": curve.to_dict(), "accretion_rate_mm": 2.4},
    }
    project = tmp_path / "project.json"
    project.write_text(json.dumps(config))
    output = tmp_path / "output"
    assert _run_batch(project, output) == 0
    capsys.readouterr()
    forcing = pd.read_csv(output / "sea_level_forcing.csv")
    assert forcing.calendar_year.tolist() == [2025, 2026, 2027, 2028]
    assert forcing.sea_level_change_mm.tolist() == pytest.approx([0, 5, 10, 15])
    assert forcing.sea_level_increment_mm.tolist() == pytest.approx([0, 5, 5, 5])
    trajectory = pd.read_csv(output / "trajectory.csv")
    assert trajectory.sea_level_change_mm.tolist() == pytest.approx([5, 10, 15])
    assert len(list((output / "states").glob("*.tif"))) == 3
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["parameters"]["sea_level_rise_rate"] is None
    assert metadata["parameters"]["sea_level_forcing"]["subtracted_initial_level_mm"] == 125


def test_runner_rejects_inconsistent_calendar_reference_before_writing_outputs(tmp_path):
    params = ModelParameters(final_time=1, sea_level_trajectory=SeaLevelTrajectory((2020, 2040), (0, 100)))
    with pytest.raises(ValueError, match="reference year"):
        run_raster_simulation(None, tmp_path, params, initial_year=2020)


def test_studio_modes_languages_and_saved_embedded_curve(tmp_path, monkeypatch):
    import tkinter as tk
    import brmangue_studio.app as module
    monkeypatch.setattr(module, "_center_window", lambda window, *_: window.withdraw())
    try:
        studio = module.BRMangueStudio()
    except tk.TclError:
        pytest.skip("A display is required for the desktop controls test.")
    try:
        studio.withdraw()
        assert str(studio.slr_entry.cget("state")) == "normal"
        assert str(studio.sea_level_browse_button.cget("state")) == "disabled"
        studio.final_year_var.set("2030")
        studio._sea_level_trajectory = SeaLevelTrajectory((2020, 2030), (100, 150))
        studio.sea_level_mode_var.set("trajectory")
        studio._on_sea_level_mode_changed()
        assert str(studio.slr_entry.cget("state")) == "disabled"
        assert str(studio.sea_level_browse_button.cget("state")) == "normal"
        assert studio._parameters().sea_level_at(5) == pytest.approx((0.025, 0.005))
        for language, button, text in [("en", "Preview curve", "annual increments"), ("pt-BR", "Visualizar curva", "acréscimos anuais")]:
            studio.language_code = language
            studio._apply_language()
            assert studio.sea_level_preview_button.cget("text") == button
            assert text in studio.sea_level_summary_var.get()
        assert studio.sea_level_template_button.cget('text') == 'Salvar exemplo CSV'
        assert studio.sea_level_help_button.cget('text') == 'Formato e fontes de dados'
        example = tmp_path / 'example.csv'
        monkeypatch.setattr(module.filedialog, 'asksaveasfilename', lambda **_: str(example))
        monkeypatch.setattr(studio, '_show_message', lambda *args: None)
        studio._save_sea_level_example()
        assert example.read_text() == TRAJECTORY_CSV_EXAMPLE
        SeaLevelTrajectory.from_csv(example).validate_period(2025, 2100)
        studio._show_sea_level_help()
        help_window = next(w for w in studio.winfo_children() if isinstance(w, tk.Toplevel))
        help_text = next(w for w in help_window.winfo_children() if isinstance(w, tk.Text))
        assert 'Crie uma planilha' in help_text.get('1.0', 'end')
        help_window.destroy()
        studio.project_file = tmp_path / "saved.json"
        studio.save_project()
        payload = json.loads(studio.project_file.read_text())
        assert payload["parameters"]["sea_level_mode"] == "trajectory"
        monkeypatch.setattr(module.filedialog, "askopenfilename", lambda **_: str(studio.project_file))
        monkeypatch.setattr(studio, "inspect_mapbiomas", lambda: None)
        monkeypatch.setattr(studio, "load_inputs", lambda: None)
        studio._sea_level_trajectory = None
        studio.open_project()
        assert studio._parameters().sea_level_at(5) == pytest.approx((0.025, 0.005))
        studio.sea_level_mode_var.set("constant")
        studio.slr_var.set("3.4")
        studio._on_sea_level_mode_changed()
        assert studio._parameters().sea_level_trajectory is None
        assert studio._parameters().sea_level_at(5) == pytest.approx((0.017, 0.0034))
    finally:
        studio.destroy()
