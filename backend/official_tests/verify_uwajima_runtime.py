"""Explicit official-artifact integration checks; no paid API or cloud operations."""

import csv, hashlib, json, sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app
from app.services.region_registry_service import get_registry
from app.services.calendar_service import CalendarService
from app.services.embedding_search_service import EmbeddingSearchService

DATA = ROOT / "data/regions/uwajima"


def context(name):
    registry = get_registry().registry("38203")
    area = next(a for a in registry.areas.values() if a["name"] == name)
    return registry.resolve("38203", area["id"])


def test_20_cities_123_areas_56_patterns_and_all_area_dates_remain_consistent():
    catalog = get_registry()
    assert len(catalog.entries) == 20
    registry = catalog.registry("38203")
    assert len(registry.areas) == 123
    records = json.loads((DATA / "generated/calendar-2026.json").read_text())[
        "calendars"
    ]
    assert len(records) == 56
    checked = 0
    for area in registry.areas.values():
        service = CalendarService(region=registry.resolve("38203", area["id"]))
        record = records[area["calendar_id"]]
        actual = {day: [] for day in record["days"]}
        for code, entries in service._dates.items():
            for entry in entries:
                actual[entry.date.isoformat()].append(code)
        assert {d: sorted(c) for d, c in actual.items()} == record["days"]
        for code in [
            "bulky",
            "dropoff",
            "batteries",
            "clean_plastics",
            "not_collected",
        ]:
            assert service.next_collection(code, from_date=date(2026, 4, 1)) is None
            assert service.collection_status(code).status == "not_scheduled"
        assert service.next_collection("burnable", from_date=date(2027, 4, 1)) is None
        checked += len(actual)
    assert checked == 44895


def test_blank_day_and_pet_conflict_do_not_become_collection_promises():
    for name in [
        "伊吹町北通の一部（サントノーレ伊吹弐番館あたりの川沿い）",
        "北宇和島町",
    ]:
        service = CalendarService(region=context("宇和島地区 → " + name))
        assert service.next_collection("burnable", from_date=date(2026, 9, 30)) is None
        assert service.collection_status("burnable").status == "unverified"
        assert (
            service.next_collection("burnable", from_date=date(2026, 10, 1)) is not None
        )
    service = CalendarService(region=context("宇和島地区 → 高光（平駄場）"))
    assert service.next_collection("pet", from_date=date(2026, 4, 1)) is None
    assert service.collection_status("pet").status == "unverified"
    assert service.next_collection("burnable", from_date=date(2026, 4, 1)).date == date(
        2026, 4, 3
    )


def test_resource_transfer_is_local_and_does_not_change_regular_bottles_cans():
    service = CalendarService(region=context("宇和島地区 → 堀端町"))
    assert service.next_collection("paper", from_date=date(2026, 11, 18)).date == date(
        2026, 11, 19
    )
    assert date(2026, 11, 23) not in [d.date for d in service._dates["paper"]]
    area = context("宇和島地区 → 戎山")
    service = CalendarService(region=area)
    assert service.next_collection("paper", from_date=date(2026, 10, 11)) is None
    assert service.collection_status("paper").status == "unverified"
    assert service.next_collection("paper", from_date=date(2026, 11, 1)).date == date(
        2026, 11, 9
    )
    service = CalendarService(region=context("津島地区 → 岩松地区"))
    assert service.next_collection("paper", from_date=date(2026, 8, 10)).date == date(
        2026, 8, 14
    )


def test_island_month_end_and_new_year_remain_unverified_not_inferred():
    for name in ["戸島（本浦・美砂子・小内浦・嘉島）", "日振島（喜路・明海・能登）"]:
        service = CalendarService(region=context("宇和島地区 → " + name))
        assert service.next_collection("pet", from_date=date(2026, 4, 1)) is None
        assert service.collection_status("pet").status == "unverified"
        assert (
            service.next_collection("burnable", from_date=date(2026, 4, 1)) is not None
        )
    service = CalendarService(region=context("津島地区 → 竹ヶ島"))
    assert service.next_collection("pet", from_date=date(2026, 4, 1)).date == date(
        2026, 4, 3
    )
    assert service.next_collection("pet", from_date=date(2027, 1, 1)) is None
    assert service.collection_status("pet").status == "unverified"


def test_dedicated_csv_npz_manifest_ids_model_and_profile_are_consistent():
    rows = list(csv.DictReader((DATA / "knowledge/items.csv").open()))
    assert len(rows) == 1144
    manifest = json.loads((DATA / "knowledge/index_manifest.json").read_text())
    for key, name in [
        ("source_sha256", "items.csv"),
        ("index_sha256", "item_embeddings.npz"),
    ]:
        assert (
            manifest[key]
            == hashlib.sha256((DATA / "knowledge" / name).read_bytes()).hexdigest()
        )
    index = EmbeddingSearchService(
        items_path=DATA / "knowledge/items.csv",
        embeddings_path=DATA / "knowledge/item_embeddings.npz",
        municipality_id="38203",
        profile_id="common",
        runtime_client=object(),
    )
    assert index.is_ready
    with np.load(DATA / "knowledge/item_embeddings.npz", allow_pickle=False) as values:
        assert values["item_ids"].tolist() == [r["item_id"] for r in rows]
        assert values["vectors"].shape == (1144, 1024)
        assert np.isfinite(values["vectors"]).all()
    assert all(
        p.index_profile_id == "common"
        for p in get_registry().registry("38203").profiles.values()
    )


@pytest.mark.asyncio
async def test_local_fastapi_health_and_bulky_items_use_the_selected_city():
    registry = get_registry().registry("38203")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://local"
    ) as client:
        assert (await client.get("/api/health")).status_code == 200
        for pid in registry.profiles:
            area = next(
                a for a in registry.areas.values() if a["rule_profile_id"] == pid
            )
            result = await client.get(
                "/api/search/items/38203",
                params=dict(district_id=area["id"], category="bulky"),
            )
            assert result.status_code == 200
            assert result.json()["municipality_name"] == "宇和島市"
