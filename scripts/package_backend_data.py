#!/usr/bin/env python3
"""Stage only catalog-declared runtime data; never include source PDFs or logs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.calendar_service import CalendarService
from app.services.region_registry_service import MunicipalityCatalog, RegionRegistry


def runtime_files(catalog_path: Path) -> set[Path]:
    """Validate every registered dataset before copying any files."""
    catalog = MunicipalityCatalog(catalog_path)
    files = {catalog_path.resolve()}
    for municipality_id, entry in catalog.entries.items():
        path = (catalog_path.parent / entry["registry_path"]).resolve()
        if not path.is_relative_to(catalog_path.parent.resolve()):
            raise ValueError("Registry must be inside the catalog directory")
        # Packaging uses the declared files, not runtime environment overrides.
        registry = RegionRegistry(path)
        if registry.data["municipality_id"] != municipality_id:
            raise ValueError("Catalog/registry municipality mismatch")
        files.add(path)
        for profile_id, profile in registry.profiles.items():
            manifest_path = profile.items_path.parent / "index_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for source, key in [(profile.items_path, "source_sha256"),
                                (profile.embedding_index_path, "index_sha256")]:
                if hashlib.sha256(source.read_bytes()).hexdigest() != manifest[key]:
                    raise ValueError(f"Dataset hash mismatch: {source}")
            with profile.items_path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            ids = [row["item_id"] for row in rows]
            if len(ids) != manifest["item_count"] or len(ids) != len(set(ids)):
                raise ValueError("Item count or ID mismatch")
            if municipality_id != "38201" and any(
                    row.get("category") and row["category"] not in profile.categories for row in rows):
                raise ValueError("Unknown regional item category")
            if municipality_id != "38201":
                for row in rows:
                    options = json.loads(row.get("category_options") or "[]")
                    if not isinstance(options, list) or any(code not in profile.categories for code in options):
                        raise ValueError("Unknown conditional item category")
            if municipality_id != "38201" and (
                    manifest.get("municipality_id") != municipality_id
                    or manifest.get("profile_id") != profile.index_profile_id):
                raise ValueError("Embedding manifest municipality/profile mismatch")
            files.update((profile.items_path, profile.embedding_index_path, manifest_path, profile.calendar_path))
        for area in registry.areas.values():
            region = registry.resolve(municipality_id, area["id"])
            calendar = CalendarService(calendar_path=region.rules.calendar_path, region=region)
            if calendar.availability not in {"available", "partially_available"}:
                raise ValueError(f"Calendar is not verified: {municipality_id}/{area['id']}")
        if municipality_id == "38201" and "nakajima" in registry.profiles:
            files.add(path.parent / "generated/nakajima_items.csv")
    for source in files:
        if not source.is_file() or not source.resolve().is_relative_to(catalog_path.parent.resolve()):
            raise ValueError(f"Missing or out-of-directory runtime data: {source}")
    return files


def stage_data(destination: Path, catalog_path: Path | None = None) -> list[Path]:
    catalog_path = (catalog_path or ROOT / "data/regions/catalog.json").resolve()
    files = runtime_files(catalog_path)
    targets = []
    for source in sorted(files):
        relative = Path("catalog.json") if source == catalog_path else source.relative_to(catalog_path.parent)
        target = destination / "data/regions" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        targets.append(target)
    return targets


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(f"Staged {len(stage_data(args.destination))} runtime data files")
