"""Synthetic and reviewed Shikokuchuo tests; no network or Bedrock."""
from datetime import date
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import shikokuchuo_data


def test_twenty_reviewed_areas_preserve_cutoff_and_regional_profiles():
    areas = shikokuchuo_data.AREAS

    assert len(areas) == 20
    assert [row["cutoff"] for row in areas].count("07:00") == 5
    assert [row["cutoff"] for row in areas].count("07:30") == 15
    assert [row["rule_profile_id"] for row in areas].count("mishima_0730") == 5
    assert areas[1]["address_labels"] == ["天生津", "宝洞山", "石ノ口", "切山"]
    assert areas[17]["address_labels"][0:3] == ["中山全域", "秋田", "程野"]


def test_kawanoe_weekly_and_nth_weekday_rules_match_official_table():
    calendars, _ = shikokuchuo_data.calendar_payload()
    first = calendars["shikokuchuo-01"]["days"]
    merged = calendars["shikokuchuo-05"]["days"]

    assert first["2026-04-01"] == ["misc_paper", "newspaper"]
    assert first["2026-04-02"] == ["burnable", "hazardous", "nonburnable"]
    assert first["2026-04-04"] == ["cardboard_milk"]
    assert first["2026-04-06"] == ["bottles_cans_pet", "burnable"]
    assert merged["2026-04-02"] == [
        "cardboard_milk", "magazines", "misc_paper", "newspaper"
    ]


def test_official_closures_are_removed_but_mishima_festival_exception_remains():
    calendars, _ = shikokuchuo_data.calendar_payload()
    kawanoe = calendars["shikokuchuo-01"]["days"]
    mishima1 = calendars["shikokuchuo-10"]["days"]
    mishima2 = calendars["shikokuchuo-11"]["days"]

    for value in shikokuchuo_data.CLOSURES:
        assert value not in kawanoe
    assert mishima1["2026-10-14"] == ["magazines", "misc_paper"]
    assert mishima1["2026-10-15"] == ["burnable"]
    assert mishima2["2026-10-14"] == ["nonburnable"]
    assert "2026-10-22" not in mishima1
    assert "2026-12-31" not in mishima1


def test_shingu_resource_and_burnable_rules_remain_distinct():
    calendars, _ = shikokuchuo_data.calendar_payload()
    area1 = calendars["shikokuchuo-18"]["days"]
    area2 = calendars["shikokuchuo-19"]["days"]
    area3 = calendars["shikokuchuo-20"]["days"]

    assert area1["2026-04-02"] == ["burnable"]
    assert area2["2026-04-01"] == ["burnable"]
    assert "burnable" in area3["2026-04-03"]
    assert area3["2026-04-04"] == ["hazardous", "nonburnable"]


def test_reviewed_items_keep_resource_lithium_and_route_exceptions():
    rows = {row["item"]: row for row in shikokuchuo_data.item_definitions()}

    assert len(rows) == 402
    assert rows["ペットボトル"]["category"] == "bottles_cans_pet"
    assert rows["牛乳パック（500ml以下）"]["category"] == "misc_paper"
    assert rows["牛乳パック（1000ml）"]["category"] == "cardboard_milk"
    assert rows["モバイルバッテリー"]["category"] == "hazardous"
    assert rows["スマートフォン"]["category"] == "hazardous"
    assert rows["オートバイ"]["category"] == "not_collected"
    assert rows["エアコン"]["category"] == "appliance_recycling"
    assert rows["雑がみ"]["category_options"] == ["burnable"]
    assert rows["菓子箱"]["category_options"] == ["burnable"]


def test_registry_exposes_three_time_and_exception_profiles_without_guessing():
    registry = json.loads((ROOT / "data/regions/shikokuchuo/registry.json").read_text(encoding="utf-8"))
    review = json.loads((ROOT / "data/regions/shikokuchuo/calendar_reviews.json").read_text(encoding="utf-8"))

    assert registry["municipality_id"] == "38213"
    assert len(registry["collection_areas"]) == len(registry["calendars"]) == 20
    assert set(registry["rule_profiles"]) == {"standard_0730", "early_0700", "mishima_0730"}
    assert registry["rule_profiles"]["early_0700"]["categories"]["burnable"]["cutoff"] == "07:00"
    assert registry["rule_profiles"]["standard_0730"]["categories"]["burnable"]["cutoff"] == "07:30"
    assert "Weather" in review["verification"]["limitations"]


def test_free_workflow_never_invokes_bedrock_or_changes_aws():
    source = (ROOT / "scripts/shikokuchuo_data.py").read_text(encoding="utf-8").lower()
    assert "boto3" not in source
    assert "invoke_model" not in source
    assert "terraform" not in source
