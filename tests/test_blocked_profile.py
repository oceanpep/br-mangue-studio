import numpy as np
import pytest

from brmangue_lua.engine import BrMangueGrid, ModelParameters
from brmangue_lua.model_states import build_model_state_catalog
from brmangue_lua.persistent_blocks import PersistentBlockRunner
from brmangue_lua.raster_inputs import _map_land_cover_classes
from brmangue_studio.app import ROLE_LABELS, ROLE_TO_MODEL
from brmangue_studio.localization import translate


def make_grid(definitions, elevations):
    count = len(definitions)
    catalog = build_model_state_catalog(definitions)
    return BrMangueGrid(
        land_cover_state=np.array([d['code'] for d in definitions], dtype=np.uint16),
        relative_elevation=np.array(elevations, dtype=np.float64),
        soil_class=np.full(count, -999, dtype=np.int16),
        row=np.zeros(count, dtype=np.int32), column=np.arange(count, dtype=np.int32),
        neighbors=tuple(tuple(j for j in range(count) if j != i) for i in range(count)),
        model_state_catalog=catalog,
    )


@pytest.mark.parametrize('engine', ['continuous', 'persistent'])
def test_blocked_and_anthropized_stay_outside_migration(tmp_path, engine):
    definitions = [
        {'code': 1, 'name': 'Mangrove', 'behavior': 'mangrove', 'color': '#006d2c'},
        {'code': 2, 'name': 'Blocked area', 'behavior': 'blocked', 'color': '#777777'},
        {'code': 3, 'name': 'Natural vegetation', 'behavior': 'natural_vegetation', 'color': '#b2df8a'},
        {'code': 4, 'name': 'Anthropized area', 'behavior': 'anthropized', 'color': '#fdae61'},
    ]
    grid = make_grid(definitions, [1, 1, 1, 1])
    params = ModelParameters(final_time=1, tide_height=6, sea_level_rise_rate=0,
                             accretion_rate_mm=0, allow_migration_without_soil=True)
    if engine == 'continuous':
        grid.step(1, params)
        values = grid.land_cover_state
    else:
        runner = PersistentBlockRunner.create_from_grid(grid, tmp_path/'blocks', block_size=2)
        runner.step(1, params)
        values = runner.current['land_cover_state']
    assert int(values[1]) == 2
    assert int(values[3]) == 4
    assert int(values[2]) == grid.model_state_catalog['migrated_mangrove_code']


@pytest.mark.parametrize('engine', ['continuous', 'persistent'])
def test_blocked_area_can_flood_without_becoming_mangrove(tmp_path, engine):
    grid = make_grid([
        {'code': 1, 'name': 'Water', 'behavior': 'water', 'color': '#2b8cbe'},
        {'code': 2, 'name': 'Blocked area', 'behavior': 'blocked', 'color': '#777777'},
    ], [2, 1])
    params = ModelParameters(final_time=1, sea_level_rise_rate=0.1)
    if engine == 'continuous':
        grid.step(1, params)
        values, counts = grid.land_cover_state, grid.class_counts()
    else:
        runner = PersistentBlockRunner.create_from_grid(grid, tmp_path/'blocks', block_size=1)
        runner.step(1, params)
        values, counts = runner.current['land_cover_state'], runner.summary()
    assert int(values[1]) == grid.model_state_catalog['flooded_codes']['2']
    assert counts['blocked'] == 0
    assert counts['flooded_blocked'] == 1
    assert counts['migrated_mangrove'] == 0


def test_standard_selector_separates_blocked_and_anthropized():
    assert 'Blocked area' in ROLE_LABELS
    assert 'Anthropized area' in ROLE_LABELS
    assert 'Bare soil' not in ROLE_LABELS
    assert translate('Blocked area', 'pt-BR') == 'Área bloqueada'
    assert ROLE_TO_MODEL['Blocked area'] == 'blocked'
    values, _, catalog = _map_land_cover_classes(
        np.array([23, 24]), {'blocked': [23], 'anthropized': [24]}, {}, [])
    assert values[0] != values[1]
    assert catalog['states'][str(int(values[0]))]['behavior'] == 'blocked'
    assert catalog['states'][str(int(values[1]))]['behavior'] == 'anthropized'
