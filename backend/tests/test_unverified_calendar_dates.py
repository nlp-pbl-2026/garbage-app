"""Date-level uncertainty must not erase known dates or promise a later next date."""

from copy import deepcopy
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest
from app.services.calendar_service import CalendarService
from app.services.region_registry_service import (
    RegionContext,
    RuleProfile,
    CategoryDefinition,
)


def fixture():
    profile = RuleProfile(
        categories={
            "burn": CategoryDefinition("試験可燃", "burnable", time(8, 30)),
            "paper": CategoryDefinition("試験古紙", "paper", time(8, 30)),
            "carry": CategoryDefinition("持込"),
        },
        items_path=Path("unused.csv"),
        embedding_index_path=Path("unused.npz"),
        calendar_path=Path("unused.json"),
    )
    region = RegionContext(
        "90001",
        "area",
        "試験地区",
        "calendar",
        "test",
        "v1",
        "2026-04-01",
        "2027-03-31",
        municipality_name="試験市",
        profile=profile,
    )
    record = dict(
        verification_status="checked",
        days={
            "2026-09-29": ["burnable"],
            "2026-09-30": ["paper"],
            "2026-10-01": ["burnable"],
        },
        unverified_dates={
            "burnable": {
                "2026-09-30": dict(
                    message="公式資料が不一致",
                    source_url="https://example.test/calendar",
                )
            }
        },
    )
    return region, dict(
        municipality_id="90001",
        version="v1",
        valid_from="2026-04-01",
        valid_to="2027-03-31",
        calendars={"calendar": record},
    )


def test_unknown_between_now_and_next_known_day_blocks_the_next_date_only():
    region, bundle = fixture()
    service = CalendarService(region=region, bundle=bundle)
    assert service.next_collection("burn", from_date=date(2026, 9, 29)).date == date(
        2026, 9, 29
    )
    result = service.next_collection("burn", from_date=date(2026, 9, 30))
    assert result is None
    assert service.collection_status("burn", result).status == "unverified"
    assert service.next_collection("paper", from_date=date(2026, 9, 30)).date == date(
        2026, 9, 30
    )
    result = service.next_collection("burn", from_date=date(2026, 10, 1))
    assert result.date == date(2026, 10, 1)
    assert service.collection_status("burn", result).status == "scheduled"
    assert service.next_collection("burn", from_date=date(2027, 4, 1)) is None
    assert service.collection_status("burn").status == "no_upcoming_collection"
    assert service.collection_status("carry").status == "not_scheduled"


def test_unknown_day_expires_at_the_same_official_cutoff():
    region, bundle = fixture()
    service = CalendarService(region=region, bundle=bundle)
    zone = ZoneInfo("Asia/Tokyo")
    assert (
        service.next_collection("burn", at=datetime(2026, 9, 30, 8, 29, tzinfo=zone))
        is None
    )
    assert service.collection_status("burn").status == "unverified"
    result = service.next_collection(
        "burn", at=datetime(2026, 9, 30, 8, 30, tzinfo=zone)
    )
    assert result.date == date(2026, 10, 1)
    assert service.collection_status("burn", result).status == "scheduled"


@pytest.mark.parametrize(
    "change", ["overlap", "outside", "no_evidence", "unknown_stream"]
)
def test_invalid_date_level_verification_fails_closed(change):
    region, bundle = fixture()
    r = bundle["calendars"]["calendar"]
    if change == "overlap":
        r["days"]["2026-09-30"].append("burnable")
    elif change == "outside":
        r["unverified_dates"]["burnable"]["2027-04-01"] = deepcopy(
            r["unverified_dates"]["burnable"]["2026-09-30"]
        )
    elif change == "no_evidence":
        r["unverified_dates"]["burnable"]["2026-09-30"].pop("source_url")
    else:
        r["unverified_dates"]["unregistered"] = {}
    with pytest.raises(ValueError, match="[Uu]nverified"):
        CalendarService(region=region, bundle=bundle)
