import sys

sys.path.insert(0, "src")

from brmangue_studio.app import (  # noqa: E402
    DEFAULT_TARGET_CRS_LABEL,
    _epsg_crs_choices,
    _crs_equivalent,
    _resolve_target_crs,
)


def test_default_albers_choice_uses_the_supplied_wkt():
    crs = _resolve_target_crs(DEFAULT_TARGET_CRS_LABEL)

    assert "Conica_Equivalente_de_Albers_Brasil" in crs.to_wkt()
    assert crs.to_epsg() is None


def test_search_catalog_contains_common_brazilian_crs():
    choices = dict(_epsg_crs_choices())

    assert choices["EPSG:5880 — SIRGAS 2000 / Brazil Polyconic"] == "EPSG:5880"


def test_typed_epsg_value_is_resolved_without_the_display_label():
    assert _resolve_target_crs("EPSG:31983").to_epsg() == 31983


def test_equivalence_ignores_wkt_metadata_normalization():
    normalized = _resolve_target_crs(DEFAULT_TARGET_CRS_LABEL).to_string()

    assert _crs_equivalent(DEFAULT_TARGET_CRS_LABEL, normalized)
