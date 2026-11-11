"""Explicit local official-data/API checks. No real model or AWS calls."""

import csv
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
import numpy as np
import pytest
from httpx import AsyncClient, ASGITransport

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app
from app.services.region_registry_service import get_registry
from app.services.calendar_service import CalendarService
from app.services.embedding_search_service import EmbeddingSearchService

DATA = ROOT / "data/regions/saijo"
CITY = "38206"


def test_all_39_areas_25_calendars_and_14235_dates():
    registry = get_registry().registry(CITY)
    raw = json.loads((DATA / "generated/calendar-2026.json").read_text())["calendars"]
    assert len(registry.areas) == 39 and len(raw) == 25
    assert len({a["display_name"] for a in registry.areas.values()}) == 39
    checked = 0
    for area in registry.areas.values():
        cal = CalendarService(region=registry.resolve(CITY, area["id"]))
        actual = {d: [] for d in raw[area["calendar_id"]]["days"]}
        for code, entries in cal._dates.items():
            for entry in entries:
                actual[entry.date.isoformat()].append(code)
        assert {k: sorted(v) for k, v in actual.items()} == raw[area["calendar_id"]][
            "days"
        ]
        checked += len(actual)
        assert cal.next_collection("burnable", from_date=date(2027, 4, 1)) is None
        for code in [
            "bulky",
            "drop_off",
            "not_collected",
            "direct_delivery",
            "small_appliances",
        ]:
            assert cal.next_collection(code, from_date=date(2026, 4, 1)) is None
            assert cal.collection_status(code).status == "not_scheduled"
    assert checked == 14235


def test_festival_closures_and_printed_same_day_multiple_streams():
    raw = json.loads((DATA / "generated/calendar-2026.json").read_text())["calendars"]
    for i in list(range(1, 14)) + list(range(20, 25)):
        for d in ["2026-10-15", "2026-10-16"]:
            assert raw[f"sj-{i:02}"]["days"][d] == []
    assert raw["sj-25"]["days"]["2026-10-16"] == []
    assert raw["sj-04"]["days"]["2026-10-17"] == []
    assert raw["sj-13"]["days"]["2026-10-17"] == []
    assert set(raw["sj-20"]["days"]["2026-04-03"]) == {
        "burnable",
        "non_burnable",
        "dry_batteries",
        "paper",
        "bottles",
        "pet_bottles",
        "spray_cans",
    }
    assert raw["sj-20"]["days"]["2026-11-27"]
    assert "2026-12-04" not in {
        d for d in raw["sj-20"]["days"] if d.startswith("2026-11")
    }
    assert "bottles" in raw["sj-05"]["days"]["2026-08-26"]
    assert "bottles" not in raw["sj-05"]["days"]["2026-08-25"]


@pytest.mark.parametrize("area", ["38206-02", "38206-03", "38206-05"])
def test_as_needed_resources_are_unverified_not_no_collection(area):
    cal = CalendarService(region=get_registry().resolve(CITY, area))
    for code in ["bottles", "pet_bottles", "spray_cans"]:
        assert cal.next_collection(code, from_date=date(2026, 4, 1)) is None
        status = cal.collection_status(code)
        assert status.status == "unverified"
        assert "随時" in status.message
    assert cal.next_collection("burnable", from_date=date(2026, 4, 1))


def test_index_ids_dimensions_normalization_and_manifest():
    region = get_registry().resolve(CITY, "38206-01")
    profile = region.rules
    rows = list(csv.DictReader(profile.items_path.open()))
    assert len(rows) == 1283
    service = EmbeddingSearchService(
        items_path=profile.items_path,
        embeddings_path=profile.embedding_index_path,
        municipality_id=CITY,
        profile_id="citywide",
        runtime_client=object(),
    )
    assert service.is_ready
    with np.load(profile.embedding_index_path, allow_pickle=False) as index:
        assert index["vectors"].shape == (1283, 1024)
        assert list(map(str, index["item_ids"])) == [r["item_id"] for r in rows]
        assert np.allclose(np.linalg.norm(index["vectors"], axis=1), 1, atol=0.002)
    for r in rows:
        assert r["category"] in region.category_codes
        assert set(json.loads(r["category_options"])) <= set(region.category_codes)
    pet = next(r for r in rows if r["item"] == "ペットボトル")
    assert pet["category"] == "pet_bottles"
    assert json.loads(pet["category_options"]) == ["burnable"]


def test_eight_oclock_cutoff():
    cal = CalendarService(region=get_registry().resolve(CITY, "38206-01"))
    now = datetime(2026, 11, 12, 7, 59, tzinfo=ZoneInfo("Asia/Tokyo"))
    assert cal.next_collection("burnable", at=now).date == now.date()
    assert (
        cal.next_collection("burnable", at=now + timedelta(minutes=1)).date > now.date()
    )


@pytest.mark.asyncio
async def test_health_and_bulky_dictionary_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://local"
    ) as client:
        assert (await client.get("/api/health")).status_code == 200
        r = await client.get(
            "/api/search/items/" + CITY,
            params=dict(category="bulky", district_id="38206-01"),
        )
        assert r.status_code == 200
        assert "家具" in json.dumps(r.json(), ensure_ascii=False)
        assert "0円" not in json.dumps(r.json(), ensure_ascii=False)


def test_contradictory_two_meter_boundary_is_held_before_model_classification():
    from app.services.waste_guide_service import WasteGuideService, RetrievedDocument
    from app.services.item_search_service import ItemSearchService

    ctx = get_registry().resolve(CITY, "38206-01")
    rows = ItemSearchService(items_path=ctx.rules.items_path, municipality_id=CITY)
    # Use actual structured same-city search evidence without a model call.
    matches = rows.search("剪定木", limit=10)
    docs = [
        RetrievedDocument(
            text=m.evidence_text,
            score=m.score,
            uri=ctx.evidence_prefix + "items/" + m.item_id,
        )
        for m in matches
    ]

    class NoModel:
        def classify(self, *a, **k):
            raise AssertionError(
                "uncertain boundary must be held before classification"
            )

    result = WasteGuideService(gateway=NoModel()).decide(
        query="幹の太さ直径4cm、長さ2mちょうどの剪定木",
        rewritten_query="剪定木",
        documents=docs,
        municipality_id=CITY,
        district_id="38206-01",
    )
    assert result.status == "unable_to_determine"
    assert result.next_collection is None
    assert not result.decision.is_resolved
    assert "確認" in result.answer
