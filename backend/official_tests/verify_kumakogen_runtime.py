"""Explicit integration checks for locally prepared official data; no API cost."""

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
from app.services.region_registry_service import get_registry, MunicipalityCatalog
from app.services.calendar_service import CalendarService
from app.services.embedding_search_service import EmbeddingSearchService, ItemMatch
from app.services.waste_guide_service import WasteGuideService, ClassificationDecision

CITY = "38386"
DATA = ROOT / "data/regions/kumakogen"


def test_all_23_areas_22_calendars_and_8395_dates():
    reg = get_registry().registry(CITY)
    raw = json.loads((DATA / "generated/calendar-2026.json").read_text())
    assert len(reg.areas) == 23
    assert len(raw["calendars"]) == 22
    assert len({a["display_name"] for a in reg.areas.values()}) == 23
    count = 0
    for area in reg.areas.values():
        ctx = reg.resolve(CITY, area["id"])
        cal = CalendarService(region=ctx)
        record = raw["calendars"][ctx.calendar_id]
        assert cal.availability == "available"
        assert len(record["days"]) == 365
        for day, codes in record["days"].items():
            assert set(codes) == {
                code
                for code, entries in cal._dates.items()
                if any(d.date.isoformat() == day for d in entries)
            }
            count += 1
        assert cal.next_collection("bulky", from_date=date(2026, 4, 1)) is None
        assert (
            cal.next_collection("direct_delivery", from_date=date(2026, 4, 1)) is None
        )
        assert cal.next_collection("burnable", from_date=date(2027, 4, 1)) is None
        assert cal.collection_status("not_collected").status == "not_scheduled"
    assert count == 8395
    assert reg.areas["38386-19"]["calendar_id"] == reg.areas["38386-23"]["calendar_id"]


def test_cross_month_dates_all_resources_vs_plastic_cans_and_year_end_exclusions():
    raw = json.loads((DATA / "generated/calendar-2026.json").read_text())["calendars"]
    # Mikawa: June column explicitly says July2; September says October1.
    for day in ["2026-07-02", "2026-10-01"]:
        assert {"plastic_packaging", "cans"} <= set(raw["kk-08"]["days"][day])
        assert "paper" not in raw["kk-08"]["days"][day]
    # Omogo: June column explicitly says July1.
    assert "cans" in raw["kk-14"]["days"]["2026-07-01"]
    # Yanadani: April/June/September cells name a date in the following month.
    for day in ["2026-05-01", "2026-07-03", "2026-10-02"]:
        assert {"cans", "plastic_packaging"} <= set(raw["kk-20"]["days"][day])
    assert "burnable" not in raw["kk-01"]["days"]["2026-12-30"]
    assert "burnable" not in raw["kk-01"]["days"]["2027-01-01"]
    assert "non_burnable" not in raw["kk-01"]["days"]["2027-01-01"]
    assert "burnable" not in raw["kk-14"]["days"]["2026-12-31"]
    # Prefer FY2026 PDF over a known stale monthly public-calendar rule.
    assert "paper" in raw["kk-07"]["days"]["2026-06-24"]
    assert "paper" not in raw["kk-07"]["days"]["2026-06-17"]


def test_index_csv_manifest_and_current_battery_provenance():
    reg = get_registry().registry(CITY)
    ctx = reg.resolve(CITY, "38386-01")
    profile = ctx.rules
    rows = list(csv.DictReader(profile.items_path.open(encoding="utf-8")))
    assert len(rows) == 2018
    assert sum(r["item_id"].startswith("kk-p") for r in rows) == 2002
    assert sum(r["item_id"].startswith("kk-rule-") for r in rows) == 16
    svc = EmbeddingSearchService(
        items_path=profile.items_path,
        embeddings_path=profile.embedding_index_path,
        municipality_id=CITY,
        profile_id="citywide",
        runtime_client=object(),
    )
    assert svc.is_ready
    with np.load(profile.embedding_index_path, allow_pickle=False) as index:
        assert index["vectors"].shape == (2018, 1024)
        assert list(map(str, index["item_ids"])) == [r["item_id"] for r in rows]
        assert np.isfinite(index["vectors"]).all()
    lithium = next(r for r in rows if r["item"] == "リチウムイオン電池")
    assert lithium["source_url"] == "https://www.kumakogen.jp/soshiki/4/27263.html"
    assert "direct_delivery" in json.loads(lithium["category_options"])
    for row in rows:
        assert row["category"] in ctx.category_codes
        assert set(json.loads(row["category_options"])) <= set(ctx.category_codes)


def test_eight_oclock_cutoff_and_disposal_only_categories():
    cal = CalendarService(region=get_registry().resolve(CITY, "38386-01"))
    at = datetime(2026, 11, 11, 7, 59, tzinfo=ZoneInfo("Asia/Tokyo"))
    assert cal.next_collection("burnable", at=at).date == at.date()
    assert (
        cal.next_collection("burnable", at=at + timedelta(minutes=1)).date > at.date()
    )
    assert all(
        k not in cal._dates
        for k in ["bulky", "direct_delivery", "not_collected", "consult"]
    )


@pytest.mark.asyncio
async def test_bulky_guide_api_has_no_automatic_application_or_old_deadlines():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://local"
    ) as client:
        response = await client.get(
            "/api/search/items/" + CITY,
            params={"category": "bulky", "district_id": "38386-01"},
        )
    assert response.status_code == 200
    text = json.dumps(response.json(), ensure_ascii=False)
    assert "粗大" in text
    assert "0円" not in text


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["paper", "batteries", "bulky", "direct_delivery"])
async def test_decision_api_uses_own_sources_and_calendar(code):
    ctx = get_registry().resolve(CITY, "38386-01")
    row = next(
        r
        for r in csv.DictReader(ctx.rules.items_path.open())
        if r["category"] == code and r["category_options"] == "[]"
    )

    class Gateway:
        def classify(self, *a, **k):
            return ClassificationDecision(
                True,
                row["item"],
                code,
                row["note"] or row["disposal_instructions"],
                0.99,
                evidence_indexes=(1,),
            )

    service = WasteGuideService(
        gateway=Gateway(),
        now_provider=lambda: datetime(2026, 11, 11, 7, tzinfo=ZoneInfo("Asia/Tokyo")),
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
    from app.services.waste_guide_service import RetrievedDocument

    document = RetrievedDocument(
        match.evidence_text,
        0.99,
        ctx.evidence_prefix + "items/" + row["item_id"],
        "公式資料",
    )
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
                    "district_id": "38386-01",
                    "query": row["item"],
                    "rewritten_query": row["item"],
                    "documents": [
                        {
                            "snippet": document.text,
                            "score": document.score,
                            "uri": document.uri,
                            "title": document.title,
                        }
                    ],
                },
            )
    assert response.status_code == 200
    result = response.json()
    assert result["classification"]["category_code"] == code
    if code in ["bulky", "direct_delivery"]:
        assert result["next_collection"] is None
    else:
        assert result["next_collection"] is not None
