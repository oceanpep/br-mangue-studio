from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from brmangue_lua.raster_inputs import _map_land_cover_classes
from brmangue_studio.figure_exports import save_state_map
from brmangue_studio.app import _display_values_for_inputs, _write_gif


def test_many_long_legend_labels_stay_outside_map(tmp_path: Path) -> None:
    catalog = {"states": {
        str(code): {"name": f"Flooded very long example land-cover category {code}",
                    "kind": "flooded", "color": "#006d2c"}
        for code in range(1, 41)
    }}
    result = save_state_map(np.arange(1, 41).reshape(5, 8), catalog, 2026,
                            tmp_path / "state.png", language="pt-BR")
    assert result["legend_states"] == 40
    assert result["legend_overlaps_map"] is False
    mx, my, mw, mh = result["map_bbox_pixels"]
    lx, ly, lw, lh = result["legend_bbox_pixels"]
    assert ly + lh < my
    with Image.open(tmp_path / "state.png") as image:
        assert list(image.size) == result["image_pixels"]


def test_legend_uses_full_raster_presence_not_preview_sampling(tmp_path: Path) -> None:
    catalog = {"states": {str(code): {"name": f"Class {code}", "color": "#336699"}
                           for code in range(1, 4)}}
    result = save_state_map(np.array([[1, 1]]), catalog, 2026, tmp_path / "state.png",
                            present_codes={1, 2})
    assert result["legend_codes"] == [1, 2]
    assert 3 not in result["legend_codes"]


def test_standard_bare_soil_and_fixed_profiles_are_distinct() -> None:
    values, _, catalog = _map_land_cover_classes(
        np.array([5, 23, 33, 50, 24, 99]),
        {"mangrove": [5], "bare_soil": [23], "water": [33],
         "natural_accommodation_candidate": [50], "managed_land_use_candidate": [24],
         "fixed": [99]}, {}, [],
    )
    profiles = [catalog["states"][str(int(value))]["behavior"] for value in values]
    assert profiles == ["mangrove", "bare_soil", "water", "natural_vegetation", "anthropized", "fixed"]


def test_compact_preview_matches_full_raster_sampling() -> None:
    mask = np.zeros((1500, 2200), dtype=bool)
    mask[35:1490:3, 6:2190:2] = True
    rows, cols = np.where(mask)
    inputs = SimpleNamespace(raster_shape=mask.shape, valid_rows=rows, valid_cols=cols)
    values = np.arange(rows.size, dtype=np.float64) / 100
    full = np.full(mask.shape, np.nan)
    full[rows, cols] = values
    crop = full[max(rows.min()-10, 0):min(rows.max()+11, mask.shape[0]),
                max(cols.min()-10, 0):min(cols.max()+11, mask.shape[1])]
    stride = max(1, int(max(crop.shape) / 700))
    expected = crop[::stride, ::stride]
    actual = _display_values_for_inputs(inputs, values, dtype=np.float64, fill_value=np.nan)
    np.testing.assert_equal(actual, expected)
    lookup = inputs._display_lookup
    again = _display_values_for_inputs(inputs, values + 1, dtype=np.float64, fill_value=np.nan)
    np.testing.assert_equal(again, expected + 1)
    assert inputs._display_lookup is lookup


def test_animation_keeps_taller_legend_frames(tmp_path: Path) -> None:
    small, tall = tmp_path / "small.png", tmp_path / "tall.png"
    Image.new("RGB", (100, 100), "red").save(small)
    Image.new("RGB", (100, 160), "blue").save(tall)
    destination = _write_gif([small, tall], tmp_path / "state.gif")
    with Image.open(destination) as image:
        assert image.size == (100, 160)
        assert image.n_frames == 2
        image.seek(1)
        assert image.convert("RGB").getpixel((50, 150)) == (0, 0, 255)
