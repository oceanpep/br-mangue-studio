from types import SimpleNamespace

import pytest

import numpy as np
from matplotlib.colors import to_hex

from brmangue_lua.model_states import STANDARD_CLASS_STYLES, STANDARD_DISPLAY_STYLES, build_model_state_catalog
from brmangue_lua.raster_inputs import _map_land_cover_classes
from brmangue_studio import app
from brmangue_studio.figure_exports import save_state_map
from brmangue_studio.localization import translate


STANDARD_NAMES = (
    'Mangrove', 'Natural vegetation', 'Water', 'Anthropized area', 'Blocked area',
)
DISPLAY_NAMES = (*STANDARD_NAMES, 'Migrated mangrove', 'Flooded mangrove')


@pytest.mark.parametrize('language', ['en', 'pt-BR'])
@pytest.mark.parametrize('catalog', [None, {}, {'states': {}}])
def test_unloaded_plot_legend_uses_standard_palette_and_derived_states(language, catalog):
    expected = [translate(name, language) for name in DISPLAY_NAMES]
    assert [item[0] for item in STANDARD_CLASS_STYLES.values()] == list(STANDARD_NAMES)
    assert [handle.get_label() for handle in app._model_legend_handles(catalog, language)] == expected


@pytest.mark.parametrize('language', ['en', 'pt-BR'])
def test_startup_widget_legend_restores_migrated_and_flooded_mangrove(monkeypatch, language):
    """Exercise the actual widget-building method without a display server."""
    labels = []

    class Widget:
        def __init__(self, *args, **kwargs):
            if 'text' in kwargs:
                labels.append(kwargs['text'])

        def pack(self, **kwargs):
            pass

    monkeypatch.setattr(app.ttk, 'Frame', Widget)
    monkeypatch.setattr(app.ttk, 'Label', Widget)
    monkeypatch.setattr(app.tk, 'Label', Widget)
    legend_frame = SimpleNamespace(winfo_children=lambda: [])
    instance = SimpleNamespace(model_legend_items=legend_frame, inputs=None, language_code=language)
    app.BRMangueStudio._refresh_model_legend(instance)
    assert labels == [translate(name, language) for name in DISPLAY_NAMES]


def test_loaded_legend_uses_explicit_project_states():
    catalog = build_model_state_catalog([
        {'code': 20, 'name': 'Protected wetland', 'behavior': 'fixed', 'color': '#8c6bb1'},
    ])
    assert [handle.get_label() for handle in app._model_legend_handles(catalog)] == ['Protected wetland']


@pytest.mark.parametrize('language', ['en', 'pt-BR'])
def test_custom_behavior_selector_has_no_bare_soil(language):
    instance = SimpleNamespace(language_code=language)
    options = app.BRMangueStudio._custom_behavior_options(instance)
    assert 'Bare soil' not in options and 'Solo descoberto' not in options
    assert 'bare_soil' not in app.CUSTOM_BEHAVIOR_LABELS
    assert translate('Blocked area', language) in options


def test_standard_loaded_maps_and_legend_restore_original_colors(tmp_path):
    _, _, catalog = _map_land_cover_classes(
        np.array([5, 6, 33, 24, 23]),
        {'mangrove': [5], 'natural_vegetation': [6], 'water': [33],
         'anthropized': [24], 'blocked': [23]}, {}, [],
    )
    assert catalog['display_mode'] == 'standard'
    assert len(catalog['states']) == 10
    handles = app._model_legend_handles(catalog)
    assert [handle.get_label() for handle in handles] == list(DISPLAY_NAMES)
    colors = {handle.get_label(): to_hex(handle.get_facecolor()) for handle in handles}
    assert colors == {
        'Mangrove': '#006d2c', 'Natural vegetation': '#b2df8a', 'Water': '#2b8cbe',
        'Anthropized area': '#fdae61', 'Blocked area': '#777777',
        'Migrated mangrove': '#7b3294', 'Flooded mangrove': '#e34a33',
    }
    cmap, norm = app._model_colormap(catalog)
    for code, item in catalog['states'].items():
        assert to_hex(cmap(norm(int(code)))) == STANDARD_DISPLAY_STYLES[item['display_group']][1]
    present = {int(code) for code in catalog['states']}
    result = save_state_map(np.array(sorted(present)).reshape(2, 5), catalog, 2026,
                            tmp_path/'standard.png', present_codes=present)
    assert result['legend_states'] == 7
    assert result['legend_overlaps_map'] is False
    plain = build_model_state_catalog([
        {k: item[k] for k in ('code', 'name', 'behavior', 'color')}
        for item in catalog['states'].values() if item['kind'] == 'class'
    ])
    assert plain['base_codes'] == catalog['base_codes']
    assert plain['flooded_codes'] == catalog['flooded_codes']
    assert plain['migrated_mangrove_code'] == catalog['migrated_mangrove_code']
