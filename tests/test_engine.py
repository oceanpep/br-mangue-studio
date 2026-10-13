import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon

from brmangue_lua.engine import BrMangueGrid, ModelParameters, SOIL_PROFILE_CODES, mangrove_extent_metrics
from brmangue_lua.model_states import build_model_state_catalog
from brmangue_lua.persistent_blocks import PersistentBlockRunner


def make_catalog():
    return build_model_state_catalog([
        {"code": 20, "name": "Mangrove", "behavior": "mangrove", "color": "#006d2c"},
        {"code": 30, "name": "Natural vegetation", "behavior": "natural_vegetation", "color": "#b2df8a"},
        {"code": 40, "name": "Bare soil", "behavior": "bare_soil", "color": "#777777"},
        {"code": 50, "name": "Water", "behavior": "water", "color": "#2b8cbe"},
    ])


def make_frame():
    rows = []
    for column in range(3):
        for row in range(3):
            class_code, soil_class, elevation = 30, 2, 2.0
            if (column, row) == (0, 1):
                class_code, soil_class, elevation = 50, SOIL_PROFILE_CODES["channel"], 2.0
            if (column, row) == (1, 1):
                class_code, soil_class, elevation = 20, SOIL_PROFILE_CODES["mangrove_soil"], 1.0
            if (column, row) == (2, 1):
                class_code, soil_class, elevation = 40, 2, 0.5
            rows.append({
                "Column": column,
                "Row": row,
                "LandCoverState": class_code,
                "RelativeElevation": elevation,
                "SoilClass": soil_class,
                "geometry": Polygon([
                    (column, row), (column + 1, row),
                    (column + 1, row + 1), (column, row + 1),
                ]),
            })
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def make_grid(frame=None):
    return BrMangueGrid.from_geodataframe(
        frame if frame is not None else make_frame(),
        model_state_catalog=make_catalog(),
    )


def test_moore_neighbors_and_catalog_defined_flood_transition():
    grid = make_grid()
    catalog = grid.model_state_catalog
    flooded_mangrove = int(catalog["flooded_codes"]["20"])
    grid.step(1, ModelParameters(final_time=1, sea_level_rise_rate=0.5))
    assert flooded_mangrove in grid.land_cover_state


def test_soil_migration_creates_generic_migrated_mangrove_state():
    grid = make_grid()
    grid.relative_elevation[(grid.column == 0) & (grid.row == 1)] = 0.0
    params = ModelParameters(final_time=1, tide_height=6, sea_level_rise_rate=0.0)
    grid.step(1, params)
    assert (grid.soil_class == SOIL_PROFILE_CODES["migrated_mangrove_soil"]).any()
    migrated_code = grid.model_state_catalog["migrated_mangrove_code"]
    assert grid.land_cover_state.tolist().count(migrated_code) >= 1
    assert grid.model_state_catalog["states"][str(migrated_code)]["name"] == "Migrated mangrove"


def test_migration_without_soil_uses_configured_candidate_profiles():
    grid = make_grid()
    grid.relative_elevation[(grid.column == 0) & (grid.row == 1)] = 0.0
    grid.soil_class.fill(-999)
    grid.step(1, ModelParameters(
        final_time=1,
        tide_height=6,
        sea_level_rise_rate=0.0,
        allow_migration_without_soil=True,
    ))
    migrated_code = grid.model_state_catalog["migrated_mangrove_code"]
    assert migrated_code in grid.land_cover_state


def test_migrated_mangrove_becomes_source_only_after_maturity_delay():
    rows = []
    for column in range(5):
        rows.append({
            "Column": column,
            "Row": 0,
            "LandCoverState": 20 if column == 0 else 30,
            "RelativeElevation": 1.0,
            "SoilClass": -999,
            "geometry": Polygon([(column, 0), (column + 1, 0), (column + 1, 1), (column, 1)]),
        })
    grid = BrMangueGrid.from_geodataframe(
        gpd.GeoDataFrame(rows, crs="EPSG:4326"), model_state_catalog=make_catalog()
    )
    trajectory = grid.run(ModelParameters(
        final_time=4,
        tide_height=6,
        sea_level_rise_rate=0.0,
        allow_migration_without_soil=True,
        migration_maturity_years=3,
    ))
    migrated_code = grid.model_state_catalog["migrated_mangrove_code"]
    assert grid.land_cover_state.tolist() == [20, migrated_code, migrated_code, 30, 30]
    assert trajectory["migrated_mangrove"].tolist() == [1, 1, 1, 2]


def test_persistent_blocks_preserve_migration_age(tmp_path):
    rows = []
    for column in range(5):
        rows.append({
            "Column": column,
            "Row": 0,
            "LandCoverState": 20 if column == 0 else 30,
            "RelativeElevation": 1.0,
            "SoilClass": -999,
            "geometry": Polygon([(column, 0), (column + 1, 0), (column + 1, 1), (column, 1)]),
        })
    frame = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    params = ModelParameters(
        final_time=4,
        tide_height=6,
        sea_level_rise_rate=0.0,
        allow_migration_without_soil=True,
        migration_maturity_years=3,
    )
    continuous = BrMangueGrid.from_geodataframe(frame, model_state_catalog=make_catalog())
    expected = continuous.run(params)
    runner = PersistentBlockRunner.create_from_grid(
        BrMangueGrid.from_geodataframe(frame, model_state_catalog=make_catalog()),
        tmp_path / "workspace",
        block_size=1,
    )
    try:
        actual = runner.run(params)
        assert expected.equals(actual)
        assert runner.current["migration_age"].tolist() == [-1, 3, 0, -1, -1]
    finally:
        runner.close()


def test_mangrove_extent_metrics_use_catalog_states():
    catalog = make_catalog()
    migrated_code = int(catalog["migrated_mangrove_code"])
    flooded_mangrove = int(catalog["flooded_codes"]["20"])
    previous = np.array([20, 30, migrated_code, 50, 30])
    current = np.array([flooded_mangrove, migrated_code, migrated_code, 20, 30])
    metrics = mangrove_extent_metrics(previous, current, catalog)
    assert metrics == {
        "mangrove_extent": 3,
        "annual_gain": 2,
        "annual_loss": 1,
        "annual_net_change": 1,
    }


def test_continuous_and_in_memory_block_engines_are_identical():
    continuous = make_grid()
    blocks = make_grid()
    params = ModelParameters(final_time=4, tide_height=6, sea_level_rise_rate=0.5)
    assert continuous.run(params).equals(blocks.run_blocks(params, block_size=2))
    assert np.array_equal(continuous.land_cover_state, blocks.land_cover_state)
    assert np.array_equal(continuous.soil_class, blocks.soil_class)
    assert np.array_equal(continuous.relative_elevation, blocks.relative_elevation)


def test_persistent_blocks_match_continuous(tmp_path):
    frame = make_frame()
    params = ModelParameters(final_time=4, tide_height=6, sea_level_rise_rate=0.5)
    continuous = BrMangueGrid.from_geodataframe(frame, model_state_catalog=make_catalog())
    expected = continuous.run(params)
    runner = PersistentBlockRunner.create_from_grid(
        BrMangueGrid.from_geodataframe(frame, model_state_catalog=make_catalog()),
        tmp_path / "workspace",
        block_size=2,
    )
    try:
        actual = runner.run(params)
        assert expected.equals(actual)
        current = runner.current
        assert np.array_equal(continuous.land_cover_state, current["land_cover_state"][:])
        assert np.array_equal(continuous.soil_class, current["soil_class"][:])
        assert np.array_equal(continuous.relative_elevation, current["relative_elevation"][:])
    finally:
        runner.close()
