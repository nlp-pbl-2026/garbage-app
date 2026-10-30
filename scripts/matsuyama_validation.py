"""Separate official-data gate; never used as an API-dependent unit test."""
from __future__ import annotations

import csv
from datetime import date, timedelta
import json
from pathlib import Path
import sys

from matsuyama_data import DATA, ROOT, read_json, sha256, normalized_hash
from matsuyama_pdf import read_calendar


def check_calendar_record(record: dict, extracted: dict, review: dict, calendar_id: str) -> None:
    """A copied or jointly edited backend/Flutter bundle is not source verification."""
    if (record["days"] != extracted["days"]
            or record["exceptions"] != extracted["exceptions"]
            or normalized_hash(record) != review["normalized_sha256"]):
        raise ValueError(f"Generated calendar differs from reviewed PDF extraction: {calendar_id}")


def validate() -> dict:
    registry = read_json(DATA / "registry.json")
    bundle_path = DATA / "generated/calendar-2026.json"
    bundle = read_json(bundle_path)
    reviews = read_json(DATA / "calendar_reviews.json")["calendars"]
    extracted = read_json(DATA / "source/extraction-review.json")["calendars"]
    assert bundle_path.read_bytes() == (ROOT / "frontend/assets/data/municipality_calendar.json").read_bytes()
    assert registry == read_json(ROOT / "frontend/assets/data/municipality_registry.json")
    assert (len(registry["collection_areas"]), len(registry["calendars"])) == (58, 43)
    assert len({area["id"] for area in registry["collection_areas"]}) == 58
    assert len({area["name"] for area in registry["collection_areas"]}) == 58
    calendars = {calendar["id"]: calendar for calendar in registry["calendars"]}
    assert set(bundle["calendars"]) == set(calendars) == set(reviews) == set(extracted)
    expected = {(date(2026, 4, 1) + timedelta(days=offset)).isoformat() for offset in range(365)}
    for area in registry["collection_areas"]:
        assert calendars[area["calendar_id"]]["rule_profile_id"] == area["rule_profile_id"]
    assert {area["calendar_id"] for area in registry["collection_areas"]} == set(calendars)
    for calendar_id, source in calendars.items():
        record = bundle["calendars"][calendar_id]
        review = reviews[calendar_id]
        assert record["verification_status"] == review["verification_status"] == "checked"
        assert sha256(DATA / "source" / source["file"]) == source["sha256"] == review["source_sha256"]
        assert normalized_hash(extracted[calendar_id]) == review["normalized_sha256"]
        check_calendar_record(record, extracted[calendar_id], review, calendar_id)
        # Re-read the actual PDF, rather than trusting a stored intermediate file.
        fresh = read_calendar(DATA / "source" / source["file"], source["rule_profile_id"])
        check_calendar_record(record, fresh, review, calendar_id)
        assert set(record["days"]) == expected
        allowed = {"combustible", "plastic_packaging", "paper", "metal_glass", "landfill", "mercury", "pet_bottle"}
        if source["rule_profile_id"] == "nakajima":
            allowed |= {"cans", "bottles", "bulky"}
        for codes in record["days"].values():
            assert len(codes) == len(set(codes)) and set(codes) <= allowed
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.calendar_service import CalendarService
    from app.services.region_registry_service import CATEGORY_DEFINITIONS, RegionRegistry
    resolver = RegionRegistry(DATA / "registry.json")
    for area in registry["collection_areas"]:
        region = resolver.resolve("38201", area["id"])
        service = CalendarService(region=region, bundle=bundle)
        assert service.availability == "available"
        record = bundle["calendars"][region.calendar_id]
        for code, (identifier, _) in CATEGORY_DEFINITIONS.items():
            expected_dates = {date.fromisoformat(raw_date) for raw_date, identifiers in record["days"].items()
                              if identifier in identifiers}
            actual_dates = {entry.date for entry in service._dates.get(identifier, [])}
            assert expected_dates == actual_dates, (area["name"], code)
    addresses = read_json(DATA / "generated/addresses.json")
    knowledge = read_json(DATA / "knowledge_reviews.json")
    for filename, digest in read_json(DATA / "auxiliary_sources.json")["sources"].items():
        assert sha256(DATA / "source" / filename) == digest
    assert addresses == read_json(ROOT / "frontend/assets/data/municipality_addresses.json")
    assert len(addresses["entries"]) == knowledge["address_entries"] == 710
    assert {row["area_id"] for row in addresses["entries"]} <= {area["id"] for area in registry["collection_areas"]}
    for filename, digest in knowledge["address_source_sha256"].items():
        assert sha256(DATA / "source" / filename) == digest
    nakajima_path = DATA / "generated/nakajima_items.csv"
    with nakajima_path.open(encoding="utf-8", newline="") as stream:
        island_rows = list(csv.DictReader(stream))
    assert len(island_rows) == knowledge["nakajima"]["item_count"]
    assert sha256(DATA / "source/2026nakajimaoura.pdf") == knowledge["nakajima"]["source_sha256"]
    assert all(row["verification_status"].startswith("official_") for row in island_rows)
    return {"areas": 58, "calendars": 43, "date_cells": 43 * 365,
            "address_rows": len(addresses["entries"]), "nakajima_evidence_rows": len(island_rows),
            "shared_calendar_sha256": sha256(bundle_path)}


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
