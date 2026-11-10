"""Reviewed Seiyo City data tests; no network or Bedrock calls."""
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import seiyo_data

sys.path.insert(0, str(ROOT / "backend"))
from app.services.item_search_service import ItemSearchService
from app.services.region_registry_service import MunicipalityCatalog
from app.services.waste_guide_service import RetrievedDocument, WasteGuideService


def test_seventeen_reviewed_areas_keep_region_and_cutoff_profiles():
    areas = seiyo_data.AREAS

    assert len(areas) == 17
    assert [row["rule_profile_id"] for row in areas].count("cutoff_0700") == 13
    assert [row["rule_profile_id"] for row in areas].count("cutoff_0800") == 4
    assert areas[0]["address_labels"] == ["明浜町", "俵津", "渡江", "狩浜", "高山", "宮野浦", "田之浜"]
    assert areas[12]["address_labels"] == ["魚成", "遊子川"]
    assert areas[13]["address_labels"] == ["土居", "高川"]


def test_new_year_closures_shift_operational_week_counts():
    calendars, _ = seiyo_data.calendar_payload()
    akehama = calendars["seiyo-01"]["days"]
    uwa2 = calendars["seiyo-03"]["days"]

    for closed in ("2026-12-31", "2027-01-01", "2027-01-02", "2027-01-03"):
        assert closed not in akehama
        assert closed not in uwa2
    assert akehama["2027-01-09"] == ["pet"]
    assert uwa2["2027-01-08"] == ["bottles", "burnable"]


def test_nomura_burnable_courses_do_not_share_false_dates():
    calendars, _ = seiyo_data.calendar_payload()
    monday_thursday = calendars["seiyo-05"]["days"]
    tuesday_friday = calendars["seiyo-06"]["days"]
    wednesday_saturday = calendars["seiyo-07"]["days"]

    assert "burnable" in monday_thursday["2026-04-02"]
    assert "burnable" not in tuesday_friday.get("2026-04-02", [])
    assert "burnable" in tuesday_friday["2026-04-03"]
    assert "burnable" in wednesday_saturday["2026-04-04"]


def test_oonogahara_and_shirokawa_special_schedules_are_separate():
    calendars, _ = seiyo_data.calendar_payload()
    oonogahara = calendars["seiyo-12"]["days"]
    uonashi_yusukawa = calendars["seiyo-13"]["days"]
    doi_takagawa = calendars["seiyo-14"]["days"]

    assert "2026-08-15" not in oonogahara
    assert set(oonogahara["2027-01-08"]) == {
        "newspaper", "misc_paper", "milk_carton", "cardboard", "clothes",
        "pet", "container_plastic", "bottles", "cans", "other_plastic",
        "metal", "small_appliance", "landfill", "used_oil",
    }
    assert uonashi_yusukawa["2026-04-01"] == ["cardboard", "milk_carton", "misc_paper", "newspaper"]
    assert "2026-04-01" not in doi_takagawa
    assert doi_takagawa["2026-04-15"] == ["cardboard", "milk_carton", "misc_paper", "newspaper"]


def test_reviewed_dictionary_keeps_size_material_and_prohibited_exceptions():
    rows = {row["item"]: row for row in seiyo_data.item_definitions()}

    assert len(seiyo_data.item_definitions()) == 1293
    assert rows["エアコン(室外機を含む)"]["category"] == "not_collected"
    assert rows["バッテリー（充電式電池）"]["category"] == "hazardous"
    assert rows["飲料容器パック（中が白色で500ml以上）"]["category"] == "milk_carton"
    assert rows["飲料容器パック（中が銀色または500ml未満）"]["category"] == "burnable"
    assert rows["紙パック(中が白色で500ml以上)"]["category_options"] == ["burnable"]
    assert rows["紙パック(中が銀色または500ml未満)"]["category_options"] == ["milk_carton"]
    assert rows["カーペット"]["category_options"] == ["bulky"]
    assert rows["めがね(金属製)"]["category_options"] == ["landfill"]


def test_registry_exposes_only_reviewed_profiles_and_omits_unmapped_bulky_dates():
    registry = json.loads((ROOT / "data/regions/seiyo/registry.json").read_text(encoding="utf-8"))
    review = json.loads((ROOT / "data/regions/seiyo/calendar_reviews.json").read_text(encoding="utf-8"))

    assert registry["municipality_id"] == "38214"
    assert len(registry["collection_areas"]) == len(registry["calendars"]) == 17
    assert set(registry["rule_profiles"]) == {"cutoff_0700", "cutoff_0800"}
    assert registry["rule_profiles"]["cutoff_0700"]["categories"]["burnable"]["cutoff"] == "07:00"
    assert registry["rule_profiles"]["cutoff_0800"]["categories"]["burnable"]["cutoff"] == "08:00"
    assert "粗大ごみ小地区" in review["verification"]["limitations"]


def test_free_workflow_never_invokes_bedrock_or_changes_aws():
    source = (ROOT / "scripts/seiyo_data.py").read_text(encoding="utf-8").lower()
    assert "boto3" not in source
    assert "invoke_model" not in source
    assert "terraform" not in source


def test_paper_pack_guard_asks_lining_then_capacity_from_official_branches():
    region = MunicipalityCatalog(ROOT / "data/regions/catalog.json").resolve("38214", "38214-01")
    search = ItemSearchService(items_path=region.asset_path("items_path"), municipality_id="38214")
    documents = [
        RetrievedDocument(text=match.evidence_text, score=match.score)
        for match in search.search("飲料用の紙パック", limit=8)
    ]

    assert "内側" in WasteGuideService._conditional_evidence_question(
        query="飲料用の紙パック", clarifications=[], documents=documents, region=region,
    )
    assert "容量" in WasteGuideService._conditional_evidence_question(
        query="飲料用の紙パック",
        clarifications=[{"question": "紙パックの内側は？", "answer": "白色です"}],
        documents=documents,
        region=region,
    )
    assert WasteGuideService._conditional_evidence_question(
        query="内側が銀色の飲料用紙パック",
        clarifications=[], documents=documents, region=region,
    ) is None
