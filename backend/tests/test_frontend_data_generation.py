"""UI bundle generation uses synthetic local datasets, without external API calls."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("generate_frontend_data", ROOT / "scripts/generate_frontend_data.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def make_city(root, city):
    profiles = {}
    for index, profile in enumerate(["standard", "island"]):
        profiles[profile] = {
            "items_path": "items.csv", "embedding_index_path": "items.npz",
            "calendar_path": f"calendar-{index}.json", "classification_rules": "Backend only prompt",
            "categories": {
                "collect": {"name": f"{city}回収物", "collection_type_id": "custom", "cutoff": "08:30", "color": "#123456"},
                "carry": {"name": "持込対象", "answer_note": "搬入案内"},
            },
            "bulky_waste": {"category_code": "carry"},
        }
        write(root / city / f"calendar-{index}.json", {
            "municipality_id": city, "version": city + "-v1", "valid_from": "2026-01-01", "valid_to": "2026-12-31",
            "calendars": {profile: {"verification_status": "checked", "days": {"2026-11-02": ["custom"]}}},
        })
    write(root / city / "registry.json", {
        "municipality_id": city, "municipality_name": city + "試験市", "version": city + "-v1",
        "valid_from": "2026-01-01", "valid_to": "2026-12-31",
        "collection_areas": [{"id": p, "name": p, "calendar_id": p, "rule_profile_id": p} for p in profiles],
        "calendars": [{"id": p, "rule_profile_id": p} for p in profiles], "rule_profiles": profiles,
    })


def test_generate_independent_ui_assets_from_backend_contract(tmp_path):
    source = tmp_path / "source"
    for city in ["90001", "90002"]:
        make_city(source, city)
    write(source / "catalog.json", {"schema_version": 1, "municipalities": [
        {"id": city, "registry_path": f"{city}/registry.json"} for city in ["90001", "90002"]]})
    output = tmp_path / "assets"
    catalog = module.generate(source / "catalog.json", output)
    assert [c["id"] for c in catalog["municipalities"]] == ["90001", "90002"]
    paths = []
    for city in catalog["municipalities"]:
        assert city["version"] == city["id"] + "-v1"
        assert "addresses_asset" not in city
        for profile in city["profiles"].values():
            assert profile["categories"]["collect"]["color"] == "#123456"
            assert profile["categories"]["collect"]["cutoff"] == "08:30"
            assert "collection_type_id" not in profile["categories"]["carry"]
            assert profile["bulky_waste"]["category_code"] == "carry"
            path = output / Path(profile["calendar_asset"]).name
            paths.append(path)
            assert json.loads(path.read_text())["municipality_id"] == city["id"]
        registry = (output / Path(city["registry_asset"]).name).read_text()
        assert "Backend only prompt" not in registry
        assert "items.npz" not in registry
    assert len(set(paths)) == 4
    assert (output / "municipality_catalog.json").is_file()


def test_missing_calendar_stops_generation(tmp_path):
    make_city(tmp_path, "90001")
    write(tmp_path / "catalog.json", {"schema_version": 1, "municipalities": [
        {"id": "90001", "registry_path": "90001/registry.json"}]})
    (tmp_path / "90001/calendar-0.json").unlink()
    with pytest.raises(FileNotFoundError):
        module.generate(tmp_path / "catalog.json", tmp_path / "output")
    assert not (tmp_path / "output/municipality_catalog.json").exists()
