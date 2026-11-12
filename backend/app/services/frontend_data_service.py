"""Project existing municipality registries into offline Flutter assets."""

from pathlib import Path
import os
from .frontend_data_contract import (
    REGISTRY_FIELDS,
    AREA_FIELDS,
    CALENDAR_FIELDS,
    encode,
    decode,
    descriptors,
    dataset_version,
    validate_assets,
    require,
)
from .region_registry_service import MunicipalityCatalog, RegionRegistry, data_path


def default_catalog_path():
    return Path(
        os.getenv(
            "MUNICIPALITY_CATALOG_PATH", str(data_path("data/regions/catalog.json"))
        )
    )


def project_bulky(value):
    result = {
        k: v
        for k, v in value.items()
        if k in {"category_code", "collection_type_id", "config"}
    }
    if "config" in value:
        allowed = {
            "municipality_id",
            "municipality_name",
            "collection_frequency",
            "reception_hours",
            "collection_rules",
            "fee_structure_type",
            "application_method",
            "web_form_url",
            "information_url",
            "phone_number",
            "steps",
            "source_urls",
        }
        config = {k: v for k, v in value["config"].items() if k in allowed}
        config["steps"] = [
            {
                k: v
                for k, v in step.items()
                if k in {"step_number", "title", "description", "notes"}
            }
            for step in config.get("steps", [])
        ]
        result["config"] = config
    return result


def project_city(registry, addresses_path=None):
    raw = registry.data
    identifier = raw["municipality_id"]
    legacy = identifier == "38201"
    name = (
        "municipality_registry.json"
        if legacy
        else f"municipality_{identifier}_registry.json"
    )
    ui = {k: v for k, v in raw.items() if k in REGISTRY_FIELDS}
    ui["collection_areas"] = [
        {k: v for k, v in a.items() if k in AREA_FIELDS}
        for a in raw["collection_areas"]
    ]
    ui["calendars"] = [
        {k: v for k, v in c.items() if k in CALENDAR_FIELDS} for c in raw["calendars"]
    ]
    files = {name: encode(ui)}
    entry = {
        "id": identifier,
        "version": raw["version"],
        "name": raw.get("municipality_name", "松山市" if legacy else identifier),
        "prefecture_id": raw.get("prefecture_id", identifier[:2]),
        "prefecture_name": raw.get(
            "prefecture_name", "愛媛県" if identifier.startswith("38") else ""
        ),
        "registry_asset": f"assets/data/{name}",
        "profiles": {},
    }
    copied = {}
    for pid, profile in registry.profiles.items():
        calendar = copied.setdefault(
            profile.calendar_path,
            (
                "municipality_calendar.json"
                if legacy
                else f"municipality_{identifier}_{len(copied)}_calendar.json"
            ),
        )
        files[calendar] = (
            profile.calendar_path.read_bytes()
        )  # Preserve original reviewed bytes.
        config = raw.get("rule_profiles", {}).get(pid, {})
        entry["profiles"][pid] = {
            "calendar_asset": f"assets/data/{calendar}",
            "categories": {
                code: {
                    "name": cat.name,
                    **(
                        {
                            "collection_type_id": cat.collection_type_id,
                            **(
                                {"cutoff": cat.cutoff.strftime("%H:%M")}
                                if cat.cutoff
                                else {"cutoff_status": "unverified"}
                            ),
                        }
                        if cat.collection_type_id
                        else {}
                    ),
                    **(
                        {"start_time": cat.start_time.strftime("%H:%M")}
                        if cat.start_time
                        else {}
                    ),
                    **({"time_note": cat.time_note} if cat.time_note else {}),
                    **{
                        k: config["categories"][code][k]
                        for k in ("collection_name", "color")
                        if k in config.get("categories", {}).get(code, {})
                    },
                }
                for code, cat in profile.categories.items()
            },
            **(
                {"bulky_waste": project_bulky(config["bulky_waste"])}
                if "bulky_waste" in config
                else {}
            ),
        }
    if addresses_path is not None:
        address = (
            "municipality_addresses.json"
            if legacy
            else f"municipality_{identifier}_addresses.json"
        )
        # Whitelist address data; never expose local source paths or OCR records.
        source = decode(addresses_path.read_bytes())
        files[address] = encode(
            {
                **{
                    k: source[k]
                    for k in ("schema_version", "verification_status", "source_url")
                    if k in source
                },
                "municipality_id": source["municipality_id"],
                "version": source["version"],
                "entries": [
                    {k: row[k] for k in ("town", "lookup_town", "area_id")}
                    for row in source["entries"]
                ],
            }
        )
        entry["addresses_asset"] = f"assets/data/{address}"
    return entry, files


def declared_addresses(catalog, identifier, *, strict=False):
    entry = catalog.entries[identifier]
    if "addresses_path" not in entry:
        require(not strict, f"Declare address availability for {identifier}")
        legacy = (
            catalog.path.parent / entry["registry_path"]
        ).parent / "generated/addresses.json"
        return legacy if legacy.is_file() else None
    if entry["addresses_path"] is None:
        return None
    path = (catalog.path.parent / entry["addresses_path"]).resolve()
    city_root = (catalog.path.parent / entry["registry_path"]).resolve().parent
    require(
        path.is_relative_to(city_root), "Address data must stay within its municipality"
    )
    require(path.is_file(), f"Declared official address data is missing: {identifier}")
    return path


def policy_path(catalog_path):
    raw = decode(catalog_path.read_bytes())["frontend_export_policy_path"]
    require(
        isinstance(raw, str) and not Path(raw).is_absolute(),
        "Invalid export policy reference",
    )
    path = (catalog_path.parent / raw).resolve()
    require(
        path.is_relative_to(catalog_path.parent.resolve()) and path.is_file(),
        "Missing/out-of-directory export policy",
    )
    return path


def build_snapshot(catalog_path):
    catalog = MunicipalityCatalog(Path(catalog_path))
    entries, files = [], {}
    for identifier, config in catalog.entries.items():
        registry = RegionRegistry(catalog.path.parent / config["registry_path"])
        require(
            registry.data["municipality_id"] == identifier,
            "Catalog/registry identity mismatch",
        )
        entry, assets = project_city(
            registry, declared_addresses(catalog, identifier, strict=True)
        )
        require(not set(files) & set(assets), "Duplicate exported asset")
        entries.append(entry)
        files.update(assets)
    ui_catalog = {"schema_version": 1, "municipalities": entries}
    files["municipality_catalog.json"] = encode(ui_catalog)
    validate_assets(ui_catalog, files)
    description = descriptors(ui_catalog, files)
    manifest = {
        "schema_version": 1,
        "dataset_version": dataset_version(description),
        "catalog": ui_catalog,
        "files": description,
    }
    return manifest, files
