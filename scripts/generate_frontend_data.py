#!/usr/bin/env python3
"""Build Flutter's offline catalog from the backend registry contract (no API calls)."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.services.region_registry_service import MunicipalityCatalog


def generate(catalog_path: Path, output: Path):
    catalog = MunicipalityCatalog(catalog_path)
    output.mkdir(parents=True, exist_ok=True)
    municipalities = []
    for identifier in catalog.entries:
        registry = catalog.registry(identifier)
        raw = registry.data
        legacy = identifier == "38201"
        registry_name = "municipality_registry.json" if legacy else f"municipality_{identifier}_registry.json"
        # Only UI metadata is shipped; CSV/index paths and classification prompts stay on the backend.
        ui_registry = {key: value for key, value in raw.items() if key != "rule_profiles"}
        (output / registry_name).write_text(json.dumps(ui_registry, ensure_ascii=False, indent=2) + "\n")
        entry = {
            "id": identifier, "version": raw["version"], "name": raw.get("municipality_name", "松山市" if legacy else identifier),
            "prefecture_id": raw.get("prefecture_id", identifier[:2]),
            "prefecture_name": raw.get("prefecture_name", "愛媛県" if identifier.startswith("38") else ""),
            "registry_asset": f"assets/data/{registry_name}", "profiles": {},
        }
        copied = {}
        for profile_id, profile in registry.profiles.items():
            calendar_name = copied.setdefault(profile.calendar_path,
                "municipality_calendar.json" if legacy else f"municipality_{identifier}_{len(copied)}_calendar.json")
            if profile.calendar_path.is_file():
                shutil.copyfile(profile.calendar_path, output / calendar_name)
            else:
                raise FileNotFoundError(profile.calendar_path)
            ui = raw.get("rule_profiles", {}).get(profile_id, {})
            entry["profiles"][profile_id] = {
                "calendar_asset": f"assets/data/{calendar_name}",
                "categories": {code: {
                    "name": category.name,
                    **({"collection_type_id": category.collection_type_id,
                        "cutoff": category.cutoff.strftime("%H:%M")} if category.collection_type_id else {}),
                    **({"collection_name": ui["categories"][code]["collection_name"]}
                       if "collection_name" in ui.get("categories", {}).get(code, {}) else {}),
                    **({"color": ui["categories"][code]["color"]}
                       if "color" in ui.get("categories", {}).get(code, {}) else {}),
                } for code, category in profile.categories.items()},
                **({"bulky_waste": ui["bulky_waste"]} if "bulky_waste" in ui else {}),
            }
        addresses = registry.path.parent / "generated/addresses.json"
        if addresses.is_file():
            address_name = "municipality_addresses.json" if legacy else f"municipality_{identifier}_addresses.json"
            shutil.copyfile(addresses, output / address_name)
            entry["addresses_asset"] = f"assets/data/{address_name}"
        municipalities.append(entry)
    result = {"schema_version": 1, "municipalities": municipalities}
    (output / "municipality_catalog.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/regions/catalog.json")
    parser.add_argument("--output", type=Path, default=ROOT / "frontend/assets/data")
    args = parser.parse_args()
    generate(args.catalog, args.output)
