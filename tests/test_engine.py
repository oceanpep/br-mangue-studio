import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon

from brmangue_lua.engine import (
    BrMangueGrid,
    MANGUE,
    MANGUE_INUNDADO,
    MANGUE_MIGRADO,
    SOLO_DESCOBERTO,
    SOLO_MANGUE,
    SOLO_MANGUE_MIGRADO,
    VEGETACAO_TERRESTRE,
    ModelParameters,
    mangrove_extent_metrics,
)
from brmangue_lua.persistent_blocks import PersistentBlockRunner


def make_frame():
    rows = []
    for col in range(3):
        for lin in range(3):
            uso = VEGETACAO_TERRESTRE
            solo = 2
            alt = 2.0
            if (col, lin) == (0, 1):
                # The water cell is intentionally higher than the mangrove so
                # the legacy flooding rule is exercised.
                uso, solo, alt = 3, 0, 2.0
            if (col, lin) == (1, 1):
                uso, solo, alt = MANGUE, SOLO_MANGUE, 1.0
            if (col, lin) == (2, 1):
                uso, solo, alt = SOLO_DESCOBERTO, 2, 0.5
            rows.append(
                {
                    "Col": col,
                    "Lin": lin,
                    "Usos": uso,
                    "Alt2": alt,
                    "ClaseSolos": solo,
                    "geometry": Polygon(
                        [(col, lin), (col + 1, lin), (col + 1, lin + 1), (col, lin + 1)]
                    ),
                }
            )
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def test_moore_neighbors_and_flood_transition():
    grid = BrMangueGrid.from_geodataframe(make_frame())
    params = ModelParameters(final_time=1, sea_level_rise_rate=0.5)
    grid.step(1, params)
    assert (grid.usos == MANGUE_INUNDADO).any()


def test_soil_migration_and_mangrove_migration():
    grid = BrMangueGrid.from_geodataframe(make_frame())
    # Keep the water cell below the mangrove so this test isolates migration
    # instead of triggering the flooding rule first.
    grid.alt2[(grid.col == 0) & (grid.lin == 1)] = 0.0
    params = ModelParameters(final_time=1, tide_height=6, sea_level_rise_rate=0.0)
    grid.step(1, params)
    # The mangrove cell marks eligible neighbours as migrated soil and then
    # converts the eligible bare/terrestrial neighbour to migrated mangrove.
    assert (grid.classe_solos == SOLO_MANGUE_MIGRADO).any()
    assert (grid.usos == MANGUE_MIGRADO).any()


def test_migration_without_soil_uses_natural_land_cover():
    grid = BrMangueGrid.from_geodataframe(make_frame())
    grid.alt2[(grid.col == 0) & (grid.lin == 1)] = 0.0
    # Remove all soil information, as in a raster assembled without a soil
    # provider, and explicitly activate the land-cover fallback.
    grid.classe_solos.fill(-999)
    params = ModelParameters(
        final_time=1,
        tide_height=6,
        sea_level_rise_rate=0.0,
        allow_migration_without_soil=True,
    )
    grid.step(1, params)
    assert (grid.usos == MANGUE_MIGRADO).any()


def test_migrated_mangrove_becomes_source_only_after_maturity_delay():
    rows = []
    for col in range(5):
        rows.append(
            {
                "Col": col,
                "Lin": 0,
                "Usos": MANGUE if col == 0 else VEGETACAO_TERRESTRE,
                "Alt2": 1.0,
                "ClaseSolos": -999,
                "geometry": Polygon(
                    [(col, 0), (col + 1, 0), (col + 1, 1), (col, 1)]
                ),
            }
        )
    grid = BrMangueGrid.from_geodataframe(gpd.GeoDataFrame(rows, crs="EPSG:4326"))
    params = ModelParameters(
        final_time=4,
        tide_height=6,
        sea_level_rise_rate=0.0,
        allow_migration_without_soil=True,
        migration_maturity_years=3,
    )

    trajectory = grid.run(params)
    # The original mangrove reaches only the first neighbour in one step.
    assert grid.usos.tolist()[:3] == [MANGUE, MANGUE_MIGRADO, MANGUE_MIGRADO]
    # The first migrated cell becomes a source after three complete years,
    # allowing the second front cell to appear at the fourth step.
    assert grid.usos.tolist()[2] == MANGUE_MIGRADO
    assert trajectory.loc[0, "migrated_mangrove"] == 1
    assert trajectory.loc[1, "migrated_mangrove"] == 1
    assert trajectory.loc[2, "migrated_mangrove"] == 1
    assert trajectory.loc[3, "migrated_mangrove"] == 2


def test_persistent_blocks_preserve_migration_age(tmp_path):
    rows = []
    for col in range(5):
        rows.append(
            {
                "Col": col,
                "Lin": 0,
                "Usos": MANGUE if col == 0 else VEGETACAO_TERRESTRE,
                "Alt2": 1.0,
                "ClaseSolos": -999,
                "geometry": Polygon(
                    [(col, 0), (col + 1, 0), (col + 1, 1), (col, 1)]
                ),
            }
        )
    frame = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    params = ModelParameters(
        final_time=4,
        tide_height=6,
        sea_level_rise_rate=0.0,
        allow_migration_without_soil=True,
        migration_maturity_years=3,
    )
    continuous = BrMangueGrid.from_geodataframe(frame)
    expected = continuous.run(params)
    runner = PersistentBlockRunner.create_from_grid(
        BrMangueGrid.from_geodataframe(frame), tmp_path / "workspace", block_size=1
    )
    try:
        actual = runner.run(params)
        assert expected.equals(actual)
        assert runner.current["migration_age"].tolist() == [-1, 3, 0, -1, -1]
    finally:
        runner.close()


def test_mangrove_extent_metrics_counts_migration_as_active_gain():
    previous = np.array([MANGUE, VEGETACAO_TERRESTRE, MANGUE_MIGRADO, 3, 2])
    current = np.array([MANGUE_INUNDADO, MANGUE_MIGRADO, MANGUE_MIGRADO, MANGUE, 2])

    metrics = mangrove_extent_metrics(previous, current)

    # One original cell is lost to flooding; two previously non-mangrove
    # cells become active mangrove (one by migration and one by reoccupation).
    assert metrics == {
        "mangrove_extent": 3,
        "annual_gain": 2,
        "annual_loss": 1,
        "annual_net_change": 1,
    }


def test_continuous_and_block_engines_are_identical():
    continuous = BrMangueGrid.from_geodataframe(make_frame())
    blocks = BrMangueGrid.from_geodataframe(make_frame())
    params = ModelParameters(final_time=4, tide_height=6, sea_level_rise_rate=0.5)

    continuous_trajectory = continuous.run(params)
    blocks_trajectory = blocks.run_blocks(params, block_size=2)

    assert continuous_trajectory.equals(blocks_trajectory)
    assert (continuous.usos == blocks.usos).all()
    assert (continuous.classe_solos == blocks.classe_solos).all()
    assert (continuous.alt2 == blocks.alt2).all()


def test_persistent_blocks_match_continuous(tmp_path):
    frame = make_frame()
    source = tmp_path / "grid.shp"
    frame.to_file(source)
    params = ModelParameters(final_time=4, tide_height=6, sea_level_rise_rate=0.5)

    continuous = BrMangueGrid.from_geodataframe(frame)
    trajectory_continuous = continuous.run(params)

    runner = PersistentBlockRunner.create_from_shapefile(
        source, tmp_path / "workspace", block_size=2
    )
    try:
        trajectory_blocks = runner.run(params)
        assert trajectory_continuous.equals(trajectory_blocks)
        current = runner.current
        assert (continuous.usos == current["usos"][:]).all()
        assert (continuous.classe_solos == current["classe_solos"][:]).all()
        assert (continuous.alt2 == current["alt2"][:]).all()
    finally:
        runner.close()


def test_dissmodel_adapter_runs_without_charts():
    pytest = __import__("pytest")
    pytest.importorskip("dissmodel")
    from brmangue_lua.dissmodel_adapter import run_dissmodel

    grid = BrMangueGrid.from_geodataframe(make_frame())
    result = run_dissmodel(
        grid,
        ModelParameters(final_time=2, tide_height=6, sea_level_rise_rate=0.5),
        show_chart=False,
    )
    assert list(result["year"]) == [1, 2]
    assert list(result["mangrove"]) == [0, 0]
