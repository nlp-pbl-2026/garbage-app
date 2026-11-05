"""Explicit local official-data checks, separate from ordinary synthetic tests."""

import csv
from datetime import date, datetime
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
from app.services.calendar_service import CalendarService
from app.services.embedding_search_service import EmbeddingSearchService
from app.services.item_search_service import ItemMatch
from app.services.region_registry_service import get_registry, RegionResolutionError
from app.services.waste_guide_service import ClassificationDecision, WasteGuideService

CITY = "38205"


def test_all_15_areas_profiles_and_shared_frontend_calendar():
    cat = get_registry()
    reg = cat.registry(CITY)
    assert {"38201", "38204", "38210", "38442", CITY} <= set(cat.entries)
    assert len(reg.areas) == 15 and len(reg.calendars) == 15
    assert set(reg.profiles) == {"mainland", "oshima", "besshiyama"}
    assert (
        ROOT / "data/regions/niihama/generated/calendar-2026.json"
    ).read_bytes() == (
        ROOT / "frontend/assets/data/municipality_38205_0_calendar.json"
    ).read_bytes()
    for area in reg.areas.values():
        assert len(area["id"]) <= 20
        assert not any(t in area["display_name"] for t in ("タイプ", "曜", "未確認"))
        ctx = cat.resolve(CITY, area["id"])
        cal = CalendarService(region=ctx)
        assert ctx.version == "niihama-2026.1" and cal.availability == "available"
        assert ctx.rules.index_profile_id == "citywide"
        assert ctx.rules.classification_rules.endswith(
            "定期収集の搬出期限は当日9時です。"
            if area["rule_profile_id"] == "besshiyama"
            else "定期収集の搬出期限は当日7時30分です。"
        )
        assert "niihama/knowledge" in str(ctx.rules.items_path)
        for code in ("bulky", "not_collected", "self_delivery", "consultation"):
            assert cal.next_collection(code, from_date=date(2026, 4, 1)) is None
            assert cal.collection_status(code).status == "not_scheduled"
        for definition in ctx.rules.categories.values():
            if definition.collection_type_id:
                assert definition.cutoff.strftime("%H:%M") == (
                    "09:00" if area["rule_profile_id"] == "besshiyama" else "07:30"
                )
        assert cal.next_collection("burnable", from_date=date(2027, 4, 1)) is None
    for city, area in [
        ("38201", "38201-08"),
        ("38204", "38204-01"),
        ("38210", "38210-iyo-central"),
        ("38442", "38442-01"),
    ]:
        assert cat.resolve(city, area).version != "niihama-2026.1"
        with pytest.raises(RegionResolutionError):
            cat.resolve(CITY, area)


def test_printed_special_symbols_closures_and_regional_differences():
    raw = json.loads(
        (ROOT / "data/regions/niihama/generated/calendar-2026.json").read_text()
    )
    for cal in raw["calendars"].values():
        assert len(cal["days"]) == 365
        for dt in (
            "2026-05-03",
            "2026-05-05",
            "2026-12-31",
            "2027-01-01",
            "2027-01-02",
            "2027-01-03",
            "2026-05-31",
            "2027-01-31",
        ):
            assert cal["days"][dt] == []
        for codes in cal["days"].values():
            assert set(codes) <= {
                d.collection_type_id
                for d in get_registry()
                .resolve(CITY, "38205-01")
                .rules.categories.values()
                if d.collection_type_id
            }
    days = lambda i: raw["calendars"][f"nh-{i:02}"]["days"]
    assert days(1)["2026-04-12"] == []  # ●: facility open only
    assert days(1)["2026-04-30"] == []  # / and circled date: not curbside
    assert days(1)["2026-12-30"] == ["burnable"]
    assert days(13)["2026-04-04"] == ["bottles_cans", "paper", "pet_bottles"]
    assert days(13)["2026-04-15"] == ["non_burnable", "textiles"]
    assert days(15)["2026-04-07"] == ["textiles"]
    assert days(15)["2026-04-14"] == ["bottles_cans", "paper", "pet_bottles"]
    assert days(13)["2027-01-04"] == ["burnable"] and days(14)["2027-01-04"] == []
    assert days(15)["2026-12-29"] == ["hazardous"]


def test_cutoff_uses_local_profile_and_does_not_schedule_facility_days():
    for area, day, hour, minute in [("38205-01", 1, 7, 30), ("38205-15", 2, 9, 0)]:
        cal = CalendarService(region=get_registry().resolve(CITY, area))
        now = datetime(2026, 4, day, hour, minute, tzinfo=ZoneInfo("Asia/Tokyo"))
        assert cal.next_collection("burnable", at=now).date > date(2026, 4, day)
        from datetime import timedelta

        assert cal.next_collection(
            "burnable", at=now - timedelta(minutes=1)
        ).date == date(2026, 4, day)


def test_dictionary_counts_current_battery_notes_and_manifest():
    ctx = get_registry().resolve(CITY, "38205-01")
    with ctx.rules.items_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1364
    official = [r for r in rows if r["item_id"].startswith("nh-p")]
    assert len(official) == 1349
    assert (
        next(r for r in official if r["item"] == "モバイルバッテリー")["category"]
        == "hazardous"
    )
    assert (
        next(r for r in official if r["item"] == "ガスボンベ（カセット式）")["category"]
        == "bottles_cans"
    )
    assert "180cm×90cm×90cm" in next(r for r in official if r["item"] == "雨戸")["note"]
    assert len([r for r in official if r["category"] == "consultation"]) == 2
    svc = EmbeddingSearchService(
        items_path=ctx.rules.items_path,
        embeddings_path=ctx.rules.embedding_index_path,
        municipality_id=CITY,
        profile_id="citywide",
        runtime_client=object(),
    )
    assert svc.is_ready
    with np.load(ctx.rules.embedding_index_path, allow_pickle=False) as index:
        assert list(map(str, index["item_ids"])) == [r["item_id"] for r in rows]
        assert index["vectors"].shape == (1364, 1024)
    for row in rows:
        assert row["category"] in ctx.category_codes
        assert set(json.loads(row["category_options"])) <= set(ctx.category_codes)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code",
    [
        "burnable",
        "non_burnable",
        "textiles",
        "plastic_packaging",
        "bottles_cans",
        "pet_bottles",
        "paper",
        "hazardous",
        "bulky",
        "self_delivery",
        "not_collected",
        "consultation",
    ],
)
async def test_each_category_api_uses_own_evidence_calendar_and_collection_method(code):
    region = get_registry().resolve(CITY, "38205-15")
    with region.rules.items_path.open(encoding="utf-8", newline="") as stream:
        row = min(
            (
                r
                for r in csv.DictReader(stream)
                if r["category"] == code and r["category_options"] == "[]"
            ),
            key=lambda r: len(r["note"]),
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

    now = datetime(2026, 11, 4, 7, tzinfo=ZoneInfo("Asia/Tokyo"))
    service = WasteGuideService(gateway=Classifier(), now_provider=lambda: now)
    query = match.item
    with patch(
        "app.routers.search_router.WasteGuideService", return_value=service
    ), patch("app.routers.search_router.SearchLogService"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://local"
        ) as client:
            response = await client.post(
                "/api/search/decide",
                json={
                    "municipality_id": CITY,
                    "district_id": region.area_id,
                    "query": query,
                    "rewritten_query": query,
                    "documents": [
                        {
                            "snippet": match.evidence_text,
                            "score": 0.99,
                            "uri": region.evidence_prefix + "items/" + match.item_id,
                        }
                    ],
                },
            )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "answered", body
    assert body["classification"]["category_code"] == code
    expected = CalendarService(region=region).next_collection(code, at=now)
    assert (body["next_collection"] or {}).get("date") == (
        expected.date.isoformat() if expected else None
    )
    if code in ("bulky", "self_delivery", "not_collected", "consultation"):
        assert body["collection_status"]["status"] == "not_scheduled"


@pytest.mark.asyncio
async def test_bulky_api_uses_niihama_and_rejects_mismatched_area():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://local"
    ) as client:
        response = await client.get(
            "/api/search/items/" + CITY,
            params={"district_id": "38205-01", "category": "bulky"},
        )
        assert response.status_code == 200
        assert response.json()["municipality_name"] == "新居浜市"
        assert response.json()["total_count"] > 436
        assert (
            await client.get(
                "/api/search/items/" + CITY,
                params={"district_id": "38442-01", "category": "bulky"},
            )
        ).status_code == 422
