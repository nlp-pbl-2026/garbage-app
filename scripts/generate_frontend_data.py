#!/usr/bin/env python3
"""Build Flutter's offline catalog from the backend registry contract (no API calls)."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.services.region_registry_service import MunicipalityCatalog
from backend.app.services.frontend_data_service import project_city, declared_addresses


def generate(
    catalog_path: Path,
    output: Path,
    municipality_ids=None,
    merge_existing: bool = False,
):
    catalog = MunicipalityCatalog(catalog_path)
    output.mkdir(parents=True, exist_ok=True)
    selected = list(municipality_ids or catalog.entries)
    unknown = [
        identifier for identifier in selected if identifier not in catalog.entries
    ]
    if unknown:
        raise ValueError(f"Unknown municipality IDs: {', '.join(unknown)}")
    municipalities = []
    for identifier in selected:
        registry = catalog.registry(identifier)
        entry, files = project_city(registry, declared_addresses(catalog, identifier))
        for name, body in files.items():
            (output / name).write_bytes(body)
        municipalities.append(entry)
    if merge_existing:
        current_path = output / "municipality_catalog.json"
        current = (
            json.loads(current_path.read_text(encoding="utf-8"))
            if current_path.is_file()
            else {
                "schema_version": 1,
                "municipalities": [],
            }
        )
        replacements = {entry["id"]: entry for entry in municipalities}
        merged = []
        seen = set()
        for entry in current.get("municipalities", []):
            identifier = str(entry.get("id", ""))
            merged.append(replacements.get(identifier, entry))
            seen.add(identifier)
        merged.extend(entry for entry in municipalities if entry["id"] not in seen)
        municipalities = merged
    result = {"schema_version": 1, "municipalities": municipalities}
    (output / "municipality_catalog.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog", type=Path, default=ROOT / "data/regions/catalog.json"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "frontend/assets/data")
    parser.add_argument(
        "--municipality-id",
        action="append",
        dest="municipality_ids",
        help="Generate only this municipality (repeatable)",
    )
    parser.add_argument(
        "--merge-existing",
        action="store_true",
        help="Preserve unselected entries in the existing Flutter catalog",
    )
    args = parser.parse_args()
    generate(args.catalog, args.output, args.municipality_ids, args.merge_existing)
