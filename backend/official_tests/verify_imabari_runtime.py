"""Explicit local official-artifact integration checks; no paid API calls."""

import csv
from datetime import date, datetime, timedelta
import json
import re
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app
from app.services.calendar_service import CalendarService
from app.services.embedding_search_service import EmbeddingSearchService
from app.services.region_registry_service import get_registry

DATA = ROOT / "data/regions/imabari"
CITY = "38202"


def context(calendar):
    registry = get_registry().registry(CITY)
    area = next(a for a in registry.areas.values() if a["calendar_id"] == calendar)
    return registry.resolve(CITY, area["id"])


def test_all_233_areas_44_calendars_share_verified_explicit_dates():
    registry = get_registry().registry(CITY)
    records = json.loads((DATA / "generated/calendar-2026.json").read_text())[
        "calendars"
    ]
    assert len(registry.areas) == 233 and len(records) == 44
    assert len({a["display_name"] for a in registry.areas.values()}) == 233
    count = 0
    for area in registry.areas.values():
        cal = CalendarService(region=registry.resolve(CITY, area["id"]))
        days = records[area["calendar_id"]]["days"]
        actual = {d: [] for d in days}
        for code, entries in cal._dates.items():
            for entry in entries:
                actual[entry.date.isoformat()].append(code)
        assert {d: sorted(v) for d, v in actual.items()} == days
        assert cal.next_collection("burnable", from_date=date(2027, 4, 1)) is None
        if area["rule_profile_id"] != "sekizen":
            assert cal.next_collection("bulky", from_date=date(2026, 4, 1)) is None
            assert cal.collection_status("bulky").status == "not_scheduled"
        count += len(days)
    assert count == 85045


def test_shared_small_date_cells_island_holidays_and_new_year_closures():
    records = json.loads((DATA / "generated/calendar-2026.json").read_text())[
        "calendars"
    ]
    assert records["im-02"]["days"]["2026-08-24"] == ["resources"]
    assert records["im-02"]["days"]["2026-08-31"] == []
    for key in ["im-41", "im-42"]:
        assert records[key]["days"]["2026-12-31"] == []
        assert records[key]["days"]["2027-01-01"] == []
    assert records["im-41"]["days"]["2027-02-11"] == ["plastics"]
    assert records["im-12_tokku"]["days"]["2026-04-29"] == []
    assert records["im-12_tokku"]["days"]["2026-04-30"] == ["burnable", "non_burnable"]
    assert records["im-36_tokku"]["days"]["2026-05-05"] == ["plastics", "resources"]
    assert (
        records["im-36_tokku"]["days"]["2026-05-06"] == []
    )  # reservation-only bulky date


@pytest.mark.parametrize("key,count", [("mainland", 867), ("sekizen", 214)])
def test_dedicated_index_manifest_ids_dimensions_and_categories(key, count):
    profile = get_registry().registry(CITY).profiles[key]
    rows = list(csv.DictReader(profile.items_path.open()))
    assert len(rows) == count
    service = EmbeddingSearchService(
        items_path=profile.items_path,
        embeddings_path=profile.embedding_index_path,
        municipality_id=CITY,
        profile_id=key,
        runtime_client=object(),
    )
    assert service.is_ready
    with np.load(profile.embedding_index_path, allow_pickle=False) as index:
        assert index["vectors"].shape == (count, 1024)
        assert list(index["item_ids"]) == [r["item_id"] for r in rows]
        assert np.isfinite(index["vectors"]).all()
        assert np.allclose(np.linalg.norm(index["vectors"], axis=1), 1, atol=0.002)
    for row in rows:
        assert row["category"] in profile.categories
        assert set(json.loads(row["category_options"])) <= profile.categories.keys()


def test_current_sekizen_rules_supersede_the_2019_dictionary_explicitly():
    registry = get_registry().registry(CITY)

    def rows(profile):
        return {
            r["item"]: r
            for r in csv.DictReader(registry.profiles[profile].items_path.open())
        }

    main, sek = rows("mainland"), rows("sekizen")
    assert main["ストロー"]["category"] == "burnable"
    assert sek["植木鉢（プラスチック製）"]["category"] == "plastics"
    assert "50cm未満" in sek["植木鉢（プラスチック製）"]["note"]
    assert sek["リチウム電池"]["category"] == "hazardous_dangerous"
    assert sek["割れたびん"]["category"] == "non_burnable"
    assert sek["新聞紙"]["category"] == "paper"
    assert sek["衣類"]["category"] == "burnable"
    assert main["スプレー缶"]["category"] == "dangerous"
    assert sek["スプレー缶"]["category"] == "hazardous_dangerous"
    assert (
        registry.profiles["hatohama_islands"].embedding_index_path
        == registry.profiles["mainland"].embedding_index_path
    )
    assert (
        registry.profiles["sekizen"].embedding_index_path
        != registry.profiles["mainland"].embedding_index_path
    )


def test_verified_cutoffs_and_unknown_ship_departure_are_not_conflated():
    now = datetime(2026, 4, 3, 6, 29, tzinfo=ZoneInfo("Asia/Tokyo"))
    main = CalendarService(region=context("im-01"))
    assert main.next_collection("burnable", at=now).date == now.date()
    assert (
        main.next_collection("burnable", at=now + timedelta(minutes=1)).date
        > now.date()
    )
    ctx = context("im-12_tokku")
    assert ctx.rules.categories["burnable"].cutoff is None
    assert ctx.rules.categories["burnable"].cutoff_status == "unverified"
    assert "出航時刻" in ctx.rules.categories["burnable"].time_note
    island = CalendarService(region=ctx)
    wednesday = datetime(2026, 4, 1, 5, tzinfo=ZoneInfo("Asia/Tokyo"))
    assert island.next_collection("burnable", at=wednesday).date == date(2026, 4, 8)
    for key in ["im-36_tokku", "im-41", "im-42"]:
        assert context(key).rules.categories["burnable"].cutoff.hour == 8
        assert context(key).rules.categories["burnable"].cutoff.minute == 30


@pytest.mark.asyncio
async def test_health_and_regional_bulky_items_api_without_models():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://local"
    ) as client:
        assert (await client.get("/api/health")).status_code == 200
        for key in ["im-01", "im-12_tokku", "im-36_tokku", "im-41", "im-42"]:
            region = context(key)
            response = await client.get(
                "/api/search/items/" + CITY,
                params=dict(district_id=region.area_id, category="bulky"),
            )
            assert response.status_code == 200
            assert not re.search(
                r"(?<!\d)0円", json.dumps(response.json(), ensure_ascii=False)
            )


def test_packaging_declares_both_nested_indices_without_sources_or_logs(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    from package_backend_data import stage_data
    import shutil

    source = tmp_path / "source"
    # The production function checks paths relative to the catalog root.
    target = source / "imabari"
    for relative in ["registry.json", "generated/calendar-2026.json"] + [
        f"knowledge/{p}/{n}"
        for p in ["mainland", "sekizen"]
        for n in ["items.csv", "item_embeddings.npz", "index_manifest.json"]
    ]:
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DATA / relative, path)
    catalog = source / "catalog.json"
    catalog.write_text(
        json.dumps(
            dict(
                schema_version=1,
                municipalities=[dict(id=CITY, registry_path="imabari/registry.json")],
            )
        )
    )
    files = stage_data(tmp_path / "lambda", catalog)
    assert len(files) == 9
    assert len([p for p in files if p.suffix == ".npz"]) == 2
    assert not any(
        p.suffix in {".pdf", ".jsonl"}
        or "/source/" in str(p.relative_to(tmp_path / "lambda"))
        for p in files
    )
