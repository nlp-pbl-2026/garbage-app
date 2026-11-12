"""Dependency-free validation shared by the exporter and clean-clone downloader.

Only explicit, reviewed calendar dates are accepted. No recurrence expansion,
geographic inference, item dictionaries or embedding dependencies belong here.
"""

import hashlib
import json
from datetime import date, time
from pathlib import PurePosixPath
import re

REGISTRY_FIELDS = {
    "schema_version",
    "municipality_id",
    "municipality_name",
    "prefecture_id",
    "prefecture_name",
    "version",
    "fiscal_year",
    "valid_from",
    "valid_to",
    "timezone",
    "source_directory_url",
    "retrieved_on",
    "redistribution_status",
    "collection_areas",
    "calendars",
    "legacy_district_candidates",
    "coverage_notice",
    "partial_address_labels",
}
AREA_FIELDS = {
    "id",
    "name",
    "display_name",
    "municipality_id",
    "calendar_id",
    "rule_profile_id",
    "source_url",
    "needs_local_confirmation",
    "parent_area",
    "address_labels",
    "mapping_note",
    "address_index_source_url",
    # Public district-to-calendar provenance used by existing UI data checks.
    "official_calendar_number",
    "official_calendar_title",
    "official_pdf_area_heading",
}
CALENDAR_FIELDS = {"id", "rule_profile_id", "url", "sha256", "verification_status"}
BUNDLE_FIELDS = {
    "schema_version",
    "municipality_id",
    "version",
    "fiscal_year",
    "valid_from",
    "valid_to",
    "timezone",
    "calendars",
}
RECORD_FIELDS = {
    "id",
    "name",
    "rule_profile_id",
    "verification_status",
    "days",
    "exceptions",
    "source_url",
    "source_sha256",
    "source_month_urls",
    "source_calendar_id",
    "official_area_note",
    "verification_method",
    "collection_type_verification",
    "unverified_dates",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()


def decode(body):
    def pairs(entries):
        result = {}
        for key, value in entries:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    return json.loads(
        body,
        object_pairs_hook=pairs,
        parse_constant=lambda _: require(False, "Non-finite JSON value"),
    )


def digest(body):
    return hashlib.sha256(body).hexdigest()


def asset_name(path):
    require(
        isinstance(path, str) and path.startswith("assets/data/"),
        "Invalid asset prefix",
    )
    name = path.removeprefix("assets/data/")
    require(
        re.fullmatch(r"municipality(?:_[A-Za-z0-9]+)*\.json", name) is not None
        and PurePosixPath(name).name == name,
        "Unsafe asset filename",
    )
    return name


def expected_files(catalog):
    require(catalog.get("schema_version") == 1, "Unsupported UI catalog")
    cities = catalog["municipalities"]
    require(isinstance(cities, list) and cities, "Empty municipality catalog")
    ids = [c["id"] for c in cities]
    require(
        len(ids) == len(set(ids))
        and all(isinstance(i, str) and re.fullmatch(r"\d{5}", i) for i in ids),
        "Invalid/duplicate municipality IDs",
    )
    result = {"municipality_catalog.json": None}
    for city in cities:
        require(
            isinstance(city["version"], str) and city["version"], "Missing data version"
        )
        require(isinstance(city.get("name"), str) and city["name"], "Missing city name")
        profiles = city["profiles"]
        require(isinstance(profiles, dict) and profiles, "Missing rule profiles")
        names = {asset_name(city["registry_asset"])}
        names.update(asset_name(p["calendar_asset"]) for p in profiles.values())
        if city.get("addresses_asset"):
            names.add(asset_name(city["addresses_asset"]))
        for name in names:
            require(name not in result, "Cross-municipality asset reference")
            result[name] = city["id"]
    return result


def day(value):
    parsed = date.fromisoformat(value)
    require(parsed.isoformat() == value, "Non-canonical date")
    return parsed


def validate_city(city, files):
    """Validate UI references and the same partial/unknown-date contract as Flutter."""
    reg = decode(files[asset_name(city["registry_asset"])])
    require(set(reg) <= REGISTRY_FIELDS, "Non-UI registry field")
    require(
        reg["municipality_id"] == city["id"] and reg["version"] == city["version"],
        "Registry identity/version mismatch",
    )
    first, last = day(reg["valid_from"]), day(reg["valid_to"])
    require(first <= last, "Invalid validity period")
    areas = reg["collection_areas"]
    ids = [a["id"] for a in areas]
    require(areas and len(ids) == len(set(ids)), "Invalid/duplicate collection areas")
    calendars = {c["id"]: c for c in reg["calendars"]}
    require(len(calendars) == len(reg["calendars"]), "Duplicate calendar ID")
    profiles = city["profiles"]
    loaded = {}
    for pid, profile in profiles.items():
        require(profile.get("categories"), "Missing classification definitions")
        streams = set()
        cutoffs = {}
        for category in profile["categories"].values():
            require(
                isinstance(category.get("name"), str) and category["name"],
                "Missing category label",
            )
            stream = category.get("collection_type_id")
            if stream:
                require(isinstance(stream, str), "Invalid collection stream")
                cutoff = category.get("cutoff")
                if category.get("cutoff_status") == "unverified":
                    require(
                        cutoff is None and bool(category.get("time_note")),
                        "Invented/undocumented cutoff",
                    )
                else:
                    require(
                        isinstance(cutoff, str)
                        and re.fullmatch(r"\d{2}:\d{2}", cutoff),
                        "Missing cutoff",
                    )
                    time.fromisoformat(cutoff)
                require(
                    stream not in cutoffs or cutoffs[stream] == cutoff,
                    "Conflicting cutoff",
                )
                cutoffs[stream] = cutoff
                if category.get("start_time"):
                    require(
                        cutoff is not None
                        and time.fromisoformat(category["start_time"])
                        < time.fromisoformat(cutoff),
                        "Invalid disposal window",
                    )
                streams.add(stream)
            if category.get("color"):
                require(
                    re.fullmatch(r"#[a-fA-F0-9]{6}", category["color"]),
                    "Invalid category color",
                )
        bundle = decode(files[asset_name(profile["calendar_asset"])])
        require(set(bundle) <= BUNDLE_FIELDS, "Non-UI calendar field")
        require(
            all(
                bundle.get(k) == reg.get(k)
                for k in ("municipality_id", "version", "valid_from", "valid_to")
            ),
            "Calendar identity/version/validity mismatch",
        )
        loaded[pid] = (bundle, streams)
        bulky = profile.get("bulky_waste", {})
        if bulky.get("category_code"):
            require(
                bulky["category_code"] in profile["categories"],
                "Unknown bulky category",
            )
        if bulky.get("collection_type_id"):
            require(
                bulky["collection_type_id"] in streams,
                "Unknown bulky collection stream",
            )
        if "config" in bulky:
            config = bulky["config"]
            require(
                config["municipality_id"] == city["id"],
                "Bulky guide municipality mismatch",
            )
            require(
                config["application_method"]
                in {"none", "guide_only", "web_form", "phone", "both"}
                and config["fee_structure_type"]
                in {"size_based", "weight_based", "fixed"},
                "Invalid bulky guide method",
            )
            require(
                all(
                    isinstance(config.get(k), str)
                    for k in (
                        "municipality_name",
                        "collection_frequency",
                        "reception_hours",
                        "collection_rules",
                    )
                ),
                "Incomplete bulky guide",
            )
    checked = set()
    for area in areas:
        require(set(area) <= AREA_FIELDS, "Non-UI area field")
        require(
            area.get("municipality_id", city["id"]) == city["id"],
            "Cross-municipality area",
        )
        pid, cid = area["rule_profile_id"], area["calendar_id"]
        require(
            pid in profiles
            and cid in calendars
            and calendars[cid]["rule_profile_id"] == pid,
            "Broken area/calendar/profile reference",
        )
        if (pid, cid) in checked:
            continue
        checked.add((pid, cid))
        bundle, streams = loaded[pid]
        record = bundle["calendars"][cid]
        require(set(record) <= RECORD_FIELDS, "Non-UI calendar record field")
        require(
            record["verification_status"] in {"checked", "partially_checked"},
            "Unverified calendar",
        )
        verification = record.get("collection_type_verification")
        unknown = set()
        if (
            verification is not None
            or record["verification_status"] == "partially_checked"
        ):
            require(
                isinstance(verification, dict) and set(verification) == streams,
                "Incomplete stream verification",
            )
            for stream, info in verification.items():
                require(
                    info["status"] in {"checked", "unverified"},
                    "Unknown verification status",
                )
                if info["status"] == "unverified":
                    require(
                        info.get("message") and info.get("source_url"),
                        "Unverified stream lacks evidence",
                    )
                    unknown.add(stream)
            require(
                bool(unknown) == (record["verification_status"] == "partially_checked")
                and unknown != streams,
                "Inconsistent partial verification",
            )
        pending = record.get("unverified_dates", {})
        require(
            isinstance(pending, dict) and set(pending) <= streams,
            "Unknown unverified stream",
        )
        for stream, entries in pending.items():
            for raw, info in entries.items():
                require(
                    first <= day(raw) <= last
                    and info.get("message")
                    and info.get("source_url"),
                    "Invalid unknown date/evidence",
                )
        require(isinstance(record["days"], dict), "Invalid calendar days")
        for raw, codes in record["days"].items():
            require(first <= day(raw) <= last, "Date outside validity period")
            require(
                isinstance(codes, list)
                and len(codes) == len(set(codes))
                and set(codes) <= streams,
                "Invalid/duplicate scheduled stream",
            )
            require(
                not set(codes) & unknown
                and not any(raw in pending.get(c, {}) for c in codes),
                "Unverified collection was scheduled",
            )
    for candidates in reg.get("legacy_district_candidates", {}).values():
        require(set(candidates) <= set(ids), "Invalid legacy area reference")
    if city.get("addresses_asset"):
        addresses = decode(files[asset_name(city["addresses_asset"])])
        require(
            addresses["municipality_id"] == city["id"]
            and addresses["version"] == city["version"],
            "Address identity/version mismatch",
        )
        for entry in addresses["entries"]:
            require(
                entry["area_id"] in ids
                and entry.get("town")
                and entry.get("lookup_town"),
                "Invalid official address reference",
            )


def validate_assets(catalog, files):
    expected = expected_files(catalog)
    require(set(files) == set(expected), "Missing or unexpected UI assets")
    require(
        decode(files["municipality_catalog.json"]) == catalog,
        "Catalog payload mismatch",
    )
    for city in catalog["municipalities"]:
        validate_city(city, files)


def descriptors(catalog, files):
    owners = expected_files(catalog)
    return {
        name: {
            "sha256": digest(body),
            "bytes": len(body),
            "municipality_id": owners[name],
        }
        for name, body in sorted(files.items())
    }


def dataset_version(descriptions):
    return digest(encode(descriptions))
