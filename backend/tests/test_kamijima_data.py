"""Synthetic and reviewed Kamijima tests; no network, source PDFs or Bedrock."""
from datetime import date
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import kamijima_data


def test_weekly_nth_and_month_parity_rules_expand_only_inside_fiscal_year():
    days = kamijima_data.expand_rules([
        kamijima_data.rule(("burnable",), (1, 4)),
        kamijima_data.rule(("metals_hazardous",), (4,), (4,), (2, 4, 6, 8, 10, 12)),
        kamijima_data.rule(("bulky",), (4,), (4,), (1, 3, 5, 7, 9, 11)),
    ])

    assert min(days) == "2026-04-02"
    assert max(days) == "2027-03-29"
    assert days["2026-04-23"] == ["burnable", "metals_hazardous"]
    assert days["2026-05-28"] == ["bulky", "burnable"]
    assert "bulky" not in days["2026-04-23"]
    assert "metals_hazardous" not in days["2026-05-28"]


def test_reviewed_area_groups_preserve_the_four_official_district_guides():
    areas = kamijima_data.AREAS

    assert len(areas) == 8
    assert [area["source_file"] for area in areas].count("yuge.pdf") == 3
    assert [area["source_file"] for area in areas].count("ikina.pdf") == 2
    assert [area["source_file"] for area in areas].count("iwagi.pdf") == 2
    assert [area["source_file"] for area in areas].count("uoshima.pdf") == 1
    assert areas[0]["address_labels"] == ["久司浦", "沢津", "上弓削", "緑ヶ丘", "引野", "明神"]
    assert areas[3]["address_labels"][0:3] == ["稲浦", "奥里", "脇"]
    assert areas[7]["rule_profile_id"] == "uoshima"


def test_yuge_groups_keep_distinct_burnable_bottle_and_can_weekdays():
    calendars, _ = kamijima_data.calendar_payload()
    group1 = calendars["kamijima-yuge-1"]["days"]
    group2 = calendars["kamijima-yuge-2"]["days"]
    group3 = calendars["kamijima-yuge-3"]["days"]

    assert group1["2026-04-01"] == ["nonburnable"]
    assert group2["2026-04-06"] == ["nonburnable"]
    assert "2026-04-06" not in group3
    assert group1["2026-04-08"] == ["cans"]
    assert "2026-04-08" not in group2
    assert group3["2026-04-08"] == ["cans"]


def test_ikina_and_iwagi_schedules_preserve_paper_and_bulky_differences():
    calendars, _ = kamijima_data.calendar_payload()
    ikina = calendars["kamijima-ikina-south"]["days"]
    iwagi = calendars["kamijima-iwagi-a"]["days"]

    assert "newspaper" in ikina["2026-04-02"]
    assert "cardboard" in ikina["2026-04-09"]
    assert "magazines" in ikina["2026-04-16"]
    assert "newspaper" in iwagi["2026-04-09"]
    assert "cardboard" in iwagi["2026-04-16"]
    assert "magazines" in iwagi["2026-04-23"]
    assert "bulky" in ikina["2026-05-27"]


def test_uoshima_is_a_weekday_dropoff_window_not_an_island_collection_guess():
    calendars, _ = kamijima_data.calendar_payload()
    days = calendars["kamijima-uoshima"]["days"]

    assert days["2026-04-01"] == sorted(kamijima_data.COLLECTION_TYPES)
    assert "2026-04-04" not in days
    assert len(days) == 261


def test_item_examples_preserve_surprising_and_conditional_official_rules():
    by_name = {row["item"]: row for row in kamijima_data.item_definitions()}

    assert len(by_name) == 106
    assert by_name["ペットボトル"]["category"] == "burnable"
    assert by_name["LED電球"]["category"] == "glass"
    assert by_name["充電用電池"]["category"] == "not_collected"
    assert by_name["ダンボール"]["category_options"] == ["burnable"]
    assert by_name["植木鉢（少量）"]["category_options"] == ["landfill"]
    assert by_name["自転車"]["category"] == "bulky"
    assert by_name["バイク"]["category"] == "not_collected"


def test_reviewed_registry_has_two_time_profiles_and_no_unverified_substitution():
    registry = json.loads((ROOT / "data/regions/kamijima/registry.json").read_text(encoding="utf-8"))
    review = json.loads((ROOT / "data/regions/kamijima/calendar_reviews.json").read_text(encoding="utf-8"))

    assert registry["municipality_id"] == "38356"
    assert len(registry["collection_areas"]) == len(registry["calendars"]) == 8
    assert all(area["needs_local_confirmation"] for area in registry["collection_areas"])
    mainland = registry["rule_profiles"]["main_islands"]["categories"]["burnable"]
    fish = registry["rule_profiles"]["uoshima"]["categories"]["burnable"]
    assert mainland["cutoff"] == "08:00" and "start_time" not in mainland
    assert fish["start_time"] == "07:00" and fish["cutoff"] == "10:00"
    assert "holiday" in review["verification"]["limitations"].lower()


def test_kamijima_free_workflow_never_invokes_bedrock_or_changes_aws():
    source = (ROOT / "scripts/kamijima_data.py").read_text(encoding="utf-8").lower()
    assert "boto3" not in source
    assert "invoke_model" not in source
    assert "terraform" not in source
