"""Explicit local official-data integration checks; no Bedrock or AWS calls."""

import csv
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
from unittest.mock import patch
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app
from app.services.region_registry_service import get_registry
from app.services.calendar_service import CalendarService
from app.services.embedding_search_service import EmbeddingSearchService, ItemMatch
from app.services.waste_guide_service import WasteGuideService, ClassificationDecision

CITY = "38215"
DATA = ROOT / "data/regions/toon"


def test_all_32_areas_11680_dates_and_separate_rule_profiles():
    reg = get_registry().registry(CITY)
    raw = json.loads((DATA / "generated/calendar-2026.json").read_text())
    assert len(reg.areas) == 32
    assert len(raw["calendars"]) == 32
    checked = 0
    for area in reg.areas.values():
        ctx = reg.resolve(CITY, area["id"])
        cal = CalendarService(region=ctx)
        record = raw["calendars"][ctx.calendar_id]
        assert cal.availability == "partially_available"
        assert len(record["days"]) == 365
        for day, codes in record["days"].items():
            expected = {
                code
                for code, entries in cal._dates.items()
                if any(e.date.isoformat() == day for e in entries)
            }
            assert expected == set(codes)
            checked += 1
        for code in ("not_collected", "small_device_dropoff"):
            assert cal.next_collection(code, from_date=date(2026, 4, 1)) is None
            assert cal.collection_status(code).status == "not_scheduled"
        assert (
            cal.next_collection("mercury_instruments", from_date=date(2026, 4, 1))
            is None
        )
        assert cal.collection_status("mercury_instruments").status == "unverified"
        assert cal.next_collection("burnable", from_date=date(2027, 4, 1)) is None
        assert cal.next_collection("bulky", from_date=date(2026, 4, 1)) is not None
    assert checked == 11680


def test_current_csv_and_city_specific_shared_index():
    reg = get_registry().registry(CITY)
    ctx = reg.resolve(CITY, "38215-01")
    rows = list(csv.DictReader(ctx.rules.items_path.open()))
    assert len([r for r in rows if r["item_id"].startswith("tn-p")]) == 1260
    assert len([r for r in rows if r["item_id"].startswith("tn-rule-")]) == 20
    assert len([r for r in rows if not r["category"]]) == 1
    assert next(r for r in rows if not r["category"])["item"] == "卵パック（プラ製）"
    for profile in reg.profiles.values():
        assert profile.items_path == ctx.rules.items_path
        assert profile.embedding_index_path == ctx.rules.embedding_index_path
        svc = EmbeddingSearchService(
            items_path=profile.items_path,
            embeddings_path=profile.embedding_index_path,
            municipality_id=CITY,
            profile_id="citywide",
            runtime_client=object(),
        )
        assert svc.is_ready
    with np.load(ctx.rules.embedding_index_path, allow_pickle=False) as index:
        assert index["vectors"].shape == (len(rows), 1024)
        assert list(map(str, index["item_ids"])) == [r["item_id"] for r in rows]
    for row in rows:
        assert not row["category"] or row["category"] in ctx.category_codes
        assert set(json.loads(row["category_options"])) <= set(ctx.category_codes)


def test_thermometer_alias_and_unknown_cutoff_never_invent_a_time():
    for area, stream in [("38215-03", "batteries"), ("38215-30", "mercury")]:
        ctx = get_registry().resolve(CITY, area)
        cal = CalendarService(region=ctx)
        assert ctx.rules.categories["thermometers"].collection_type_id == stream
        assert (
            cal.next_collection("thermometers", from_date=date(2026, 4, 1)).date
            == cal.next_collection(stream, from_date=date(2026, 4, 1)).date
        )
    for area in ("38215-01", "38215-30"):
        ctx = get_registry().resolve(CITY, area)
        cal = CalendarService(region=ctx)
        day = cal.next_collection("metals", from_date=date(2026, 4, 1)).date
        now = datetime.combine(
            day, datetime.min.time(), tzinfo=ZoneInfo("Asia/Tokyo")
        ) + timedelta(hours=7)
        next_date = cal.next_collection("metals", at=now).date
        if area == "38215-01":
            assert ctx.rules.categories["metals"].cutoff is None
            assert next_date > day
        else:
            assert ctx.rules.categories["metals"].cutoff.hour == 8
            assert next_date == day


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "area,code",
    [
        ("38215-01", "bulky"),
        ("38215-30", "thermometers"),
        ("38215-01", "mercury_instruments"),
        ("38215-01", "small_device_dropoff"),
        ("38215-01", "not_collected"),
    ],
)
async def test_api_classification_collection_status_and_bulky_guide(area, code):
    region = get_registry().resolve(CITY, area)
    rows = list(csv.DictReader(region.rules.items_path.open()))
    row = next(
        r
        for r in rows
        if r["category"] == code
        and (r["category_options"] == "[]" or code == "thermometers")
    )
    match = ItemMatch(
        item_id=row["item_id"],
        item=row["item"],
        category=code,
        category_display=row["category_display"],
        note=row["note"],
        score=0.99,
        disposal_instructions=row["disposal_instructions"],
    )

    class Classifier:
        def classify(self, *a, **k):
            return ClassificationDecision(
                True,
                match.item,
                code,
                match.disposal_instructions,
                0.99,
                evidence_indexes=(1,),
            )

    now = datetime(2026, 11, 5, 7, tzinfo=ZoneInfo("Asia/Tokyo"))
    service = WasteGuideService(gateway=Classifier(), now_provider=lambda: now)
    with patch(
        "app.routers.search_router.WasteGuideService", return_value=service
    ), patch("app.routers.search_router.SearchLogService"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://local"
        ) as client:
            res = await client.post(
                "/api/search/decide",
                json={
                    "municipality_id": CITY,
                    "district_id": area,
                    "query": row["item"],
                    "rewritten_query": row["item"],
                    "documents": [
                        {
                            "snippet": match.evidence_text,
                            "score": 0.99,
                            "uri": region.evidence_prefix + "items/" + row["item_id"],
                        }
                    ],
                },
            )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "answered", body
    assert body["classification"]["category_code"] == code
    cal = CalendarService(region=region)
    expected = cal.next_collection(code, at=now)
    assert (body["next_collection"] or {}).get("date") == (
        expected.date.isoformat() if expected else None
    )
    assert (
        body["collection_status"]["status"]
        == cal.collection_status(code, expected).status
    )
    if code == "mercury_instruments":
        assert "未確認" in body["collection_status"]["message"]


@pytest.mark.asyncio
async def test_bulky_is_regular_collection_and_other_municipalities_stay_independent():
    for area in ("38215-01", "38215-30"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://local"
        ) as client:
            res = await client.get(
                "/api/search/items/" + CITY,
                params={"district_id": area, "category": "bulky"},
            )
            assert res.status_code == 200, res.text
            assert res.json()["municipality_name"] == "東温市"
            assert res.json()["total_count"] >= 286
            assert (
                await client.get(
                    "/api/search/items/" + CITY,
                    params={"district_id": "38442-01", "category": "bulky"},
                )
            ).status_code == 422
    for profile in get_registry().registry(CITY).data["rule_profiles"].values():
        guide = profile["bulky_waste"]["config"]
        assert guide["application_method"] == "none"
        assert "受け入れません" in guide["steps"][-1]["description"]
    assert set(get_registry().entries) >= {
        "38201",
        "38204",
        "38210",
        "38442",
        "38205",
        "38215",
    }
