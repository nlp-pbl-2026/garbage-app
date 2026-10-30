import json

import pytest

from app.services.region_registry_service import RegionRegistry, RegionResolutionError


def registry(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({
        "municipality_id": "38201", "version": "test", "valid_from": "2026-04-01",
        "valid_to": "2027-03-31",
        "collection_areas": [
            {"id": "a", "name": "地区A", "calendar_id": "shared", "rule_profile_id": "matsuyama_hojo"},
            {"id": "b", "name": "地区B", "calendar_id": "shared", "rule_profile_id": "matsuyama_hojo"},
            {"id": "island", "name": "地区C", "calendar_id": "other", "rule_profile_id": "nakajima"},
        ],
        "calendars": [{"id": "shared", "rule_profile_id": "matsuyama_hojo"},
                      {"id": "other", "rule_profile_id": "nakajima"}],
        "legacy_district_candidates": {"old": ["a", "b"], "unique": ["a"]},
    }), encoding="utf-8")
    return RegionRegistry(path)


def test_legacy_alias_and_shared_calendar(tmp_path):
    r = registry(tmp_path)
    assert r.resolve("38201", "unique").area_id == "a"
    assert r.resolve("38201", "a").calendar_id == r.resolve("38201", "b").calendar_id


def test_ambiguous_alias_requires_selection(tmp_path):
    with pytest.raises(RegionResolutionError) as error:
        registry(tmp_path).resolve("38201", "old")
    assert error.value.candidates == ("a", "b")


def test_profile_specific_categories_and_unknown_region(tmp_path):
    r = registry(tmp_path)
    assert "缶" not in r.resolve("38201", "a").category_codes
    assert "缶" in r.resolve("38201", "island").category_codes
    with pytest.raises(RegionResolutionError):
        r.resolve("other", "a")
    with pytest.raises(RegionResolutionError):
        r.resolve("38201", "unknown")
