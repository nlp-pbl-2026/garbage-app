"""Regional search behavior with synthetic data and no Bedrock calls."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.calendar_service import CalendarService
from app.services.nakajima_search_service import NakajimaSearchService
from app.services.nakajima_rule_service import evidence_text as island_evidence_text, resolve_shared_item
from app.services.item_search_service import ItemMatch
from app.services.region_registry_service import RegionContext
from app.services.waste_guide_service import (
    BedrockGateway, ClassificationDecision, ImageInput, RetrievedDocument, UnsupportedRegionError,
    WasteGuideService,
)
import json


ISLAND = RegionContext("38201", "38201-test-island", "試験島", "island-calendar",
                       "nakajima", "test-v1", "2026-04-01", "2027-03-31")
MAINLAND = RegionContext("38201", "38201-test-main", "試験地区", "main-calendar",
                         "matsuyama_hojo", "test-v1", "2026-04-01", "2027-03-31")


def calendar(region, days):
    return CalendarService(region=region, bundle={
        "version": "test-v1", "valid_from": "2026-04-01", "valid_to": "2027-03-31",
        "calendars": {region.calendar_id: {"verification_status": "checked", "days": days}},
    })


def test_calendar_uses_each_profile_and_category_cutoff():
    service = calendar(ISLAND, {
        "2026-10-30": ["combustible", "cans", "bulky"],
        "2026-11-06": ["combustible", "cans"],
    })
    tokyo = ZoneInfo("Asia/Tokyo")
    assert service.next_collection("可燃", at=datetime(2026, 10, 30, 6, 59, tzinfo=tokyo)).date == date(2026, 10, 30)
    assert service.next_collection("可燃", at=datetime(2026, 10, 30, 7, tzinfo=tokyo)).date == date(2026, 11, 6)
    assert service.next_collection("缶", at=datetime(2026, 10, 30, 7, 59, tzinfo=tokyo)).date == date(2026, 10, 30)
    assert service.next_collection("缶", at=datetime(2026, 10, 30, 8, tzinfo=tokyo)).date == date(2026, 11, 6)
    assert service.next_collection("粗大", from_date=date(2026, 10, 30)).date == date(2026, 10, 30)
    assert service.next_collection("缶", from_date=date(2027, 4, 1)) is None
    assert calendar(MAINLAND, {"2026-10-30": ["combustible"]}).next_collection("粗大", from_date=date(2026, 10, 30)) is None


class FakeRegistry:
    def resolve(self, municipality_id, district_id):
        return ISLAND if district_id == ISLAND.area_id else MAINLAND


class FakeIslandSearch:
    def search(self, query):
        return [{"item": "アルミ缶", "category": "缶", "category_display": "缶類",
                 "note": "飲料缶を出す", "item_id": "nk-item-test", "score": 1.0}]


class FakeGateway:
    def rewrite_query(self, query, clarifications, image=None):
        return query

    def classify(self, query, clarifications, documents, image=None):
        return ClassificationDecision(is_resolved=True, item_name="アルミ缶",
                                      category_code="缶", confidence=.98, evidence_indexes=(1,))


def test_nakajima_uses_only_island_evidence(monkeypatch):
    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr("app.services.waste_guide_service.NakajimaSearchService", FakeIslandSearch)
    service = WasteGuideService(gateway=FakeGateway(),
        calendar=calendar(ISLAND, {"2026-11-02": ["cans"]}),
        now_provider=lambda: datetime(2026, 10, 30, 9, tzinfo=ZoneInfo("Asia/Tokyo")))
    result = service.query(query="アルミ缶", municipality_id="38201", district_id=ISLAND.area_id)
    assert result.decision.category_code == "缶"
    assert result.next_collection.date == date(2026, 11, 2)
    assert "試験島地区" in result.answer
    assert all(doc.uri.startswith("nakajima://") for doc in result.sources)
    with pytest.raises(UnsupportedRegionError):
        service.decide(query="アルミ缶", rewritten_query="アルミ缶",
                       documents=[RetrievedDocument(text="分類: 金・ガ", uri="local://items/main")],
                       municipality_id="38201", district_id=ISLAND.area_id)


def test_nakajima_unknown_text_or_image_fails_closed_without_mainland_fallback(tmp_path, monkeypatch):
    import csv
    source = tmp_path / "nakajima_items.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["item_id", "item", "category",
                                                    "category_display", "note"])
        writer.writeheader()
        writer.writerow({"item_id": "nk-item-can", "item": "アルミ缶", "category": "缶",
                         "category_display": "缶類", "note": "飲料缶"})
    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr("app.services.nakajima_search_service.config.NAKAJIMA_ITEMS_PATH", str(source))
    assert NakajimaSearchService().search("アルミ缶")[0]["category"] == "缶"
    assert NakajimaSearchService().search("未知の電化製品") == []
    service = WasteGuideService(gateway=FakeGateway())
    for image in (None, ImageInput("png", b"test")):
        result = service.query(query="未知の電化製品" if image is None else "",
                               municipality_id="38201", district_id=ISLAND.area_id, image=image)
        assert result.status == "needs_clarification"
        assert not result.sources


def test_nakajima_item_example_does_not_inherit_unrelated_section_conditions(tmp_path, monkeypatch):
    import csv
    source = tmp_path / "nakajima_items.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["item_id", "item", "category",
                                                    "category_display", "note"])
        writer.writeheader()
        writer.writerow({"item_id": "nk-item-foil", "item": "アルミ箔", "category": "可燃",
                         "category_display": "可燃ごみ",
                         "note": "中島地域2026年度カレンダーに可燃ごみの品目例として掲載。"})

    class FoilGateway(FakeGateway):
        def classify(self, query, clarifications, documents, image=None):
            return ClassificationDecision(is_resolved=True, item_name="アルミ箔",
                                          category_code="可燃", confidence=.98,
                                          evidence_indexes=(1,))

    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr("app.services.nakajima_search_service.config.NAKAJIMA_ITEMS_PATH", str(source))
    service = WasteGuideService(gateway=FoilGateway(),
        calendar=calendar(ISLAND, {"2026-11-02": ["combustible"]}),
        now_provider=lambda: datetime(2026, 10, 30, 9, tzinfo=ZoneInfo("Asia/Tokyo")))
    result = service.query(query="アルミ箔", municipality_id="38201", district_id=ISLAND.area_id)
    assert result.status == "answered"
    assert result.next_collection.date == date(2026, 11, 2)


def test_mainland_rejects_island_evidence(monkeypatch):
    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    service = WasteGuideService(gateway=FakeGateway())
    with pytest.raises(UnsupportedRegionError):
        service.decide(query="アルミ缶", rewritten_query="アルミ缶",
                       documents=[RetrievedDocument(text="分類: 缶", uri="nakajima://items/item")],
                       municipality_id="38201", district_id=MAINLAND.area_id)


def test_nakajima_prompt_and_evidence_reject_mainland_category():
    class Runtime:
        request = None

        def converse(self, **kwargs):
            self.request = kwargs
            return {"output": {"message": {"content": [{"text": json.dumps({
                "is_resolved": True, "item_name": "アルミ缶", "category_code": "金・ガ",
                "confidence": .99, "evidence_indexes": [1],
            })}]}}}

    runtime = Runtime()
    gateway = BedrockGateway(runtime_client=runtime, agent_runtime_client=object(),
                             embedding_search=object())
    decision = gateway.classify("アルミ缶", [], [RetrievedDocument(
        text="品目: アルミ缶\n分類: 缶類 (缶)\n出し方・条件: 飲料缶を出す")],
        region=ISLAND)
    assert not decision.is_resolved
    prompt = runtime.request["messages"][0]["content"][0]["text"]
    assert "中島地域" in prompt and "分類コードは" in prompt
    assert "戸別申込制を当てはめない" in prompt


@pytest.mark.parametrize(("name", "mainland", "note", "expected", "status"), [
    ("缶詰", "金・ガ", "", "缶", "split_rule"),
    ("お茶の缶", "金・ガ", "", "缶", "split_rule"),
    ("しょうゆのびん", "金・ガ", "すすいで出す", "びん", "split_rule"),
    ("スプレー缶", "金・ガ", "必ず使い切る", "金・ガ", "split_rule"),
    ("コップ（ガラス製）", "金・ガ", "", "金・ガ", "split_rule"),
    ("空き缶・空きびん", "金・ガ", "", None, "conditional"),
    ("マニキュアのびん", "金・ガ", "中身が固まっている場合は「粗大」", None, "conditional"),
    ("缶（アルミ・スチール）", "金・ガ", "", None, "conditional"),
    ("いす", "粗大", "", "粗大", "common_rule"),
    ("木材", "可燃", "袋に入らないものは「粗大」", None, "conditional"),
    ("対象外", "禁止", "", None, "unverified"),
])
def test_nakajima_shared_rule_split_and_uncertainty(name, mainland, note, expected, status):
    match = ItemMatch("item-1", name, mainland, "", note, .9)
    result = resolve_shared_item(match)
    assert (result.category, result.status) == (expected, status)
    if expected:
        text = island_evidence_text(match, result)
        assert "中島地域" in text
        assert "松山・北条" not in text
        assert "戸別収集の申し込み" not in text


def test_nakajima_retrieval_uses_shared_vectors_without_mainland_notes(monkeypatch):
    class SharedGateway(FakeGateway):
        def __init__(self):
            self.limit = None

        def search_item_candidates(self, query, *, limit=None):
            self.limit = limit
            return [
                ItemMatch("item-can", "缶詰", "金・ガ", "金物・ガラス類",
                          "松山・北条の金・ガの日に出す", .91),
                ItemMatch("item-chair", "いす", "粗大", "粗大ごみ",
                          "戸別収集の申し込みが必要", .88),
                ItemMatch("item-mixed", "空き缶・空きびん", "金・ガ", "金物・ガラス類", "", .84),
            ]

    class NoIslandHits:
        def search(self, query):
            return []

    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr("app.services.waste_guide_service.NakajimaSearchService", NoIslandHits)
    gateway = SharedGateway()
    service = WasteGuideService(gateway=gateway)
    docs = service.retrieve(rewritten_query="缶詰 いす", municipality_id="38201",
                            district_id=ISLAND.area_id)
    assert gateway.limit == 24
    assert len(docs) == 1  # The chair's mainland collection note needs review.
    assert docs[0].uri == "nakajima://shared/item-can"
    assert "分類: 缶類 (缶)" in docs[0].text
    assert "松山・北条" not in docs[0].text


def test_nakajima_retrieval_keeps_official_examples_when_vectors_unavailable(monkeypatch):
    class MissingGateway(FakeGateway):
        def search_item_candidates(self, query, *, limit=None):
            from app.services.waste_guide_service import WasteGuideError
            raise WasteGuideError("index is unavailable")

    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr("app.services.waste_guide_service.NakajimaSearchService", FakeIslandSearch)
    service = WasteGuideService(gateway=MissingGateway())
    docs = service.retrieve(rewritten_query="アルミ缶", municipality_id="38201",
                            district_id=ISLAND.area_id)
    assert len(docs) == 1 and docs[0].uri.startswith("nakajima://items/")


@pytest.mark.parametrize("image", [None, ImageInput("png", b"sample")])
def test_nakajima_shared_candidate_can_answer_text_and_image_without_mainland_evidence(monkeypatch, image):
    class SharedQueryGateway(FakeGateway):
        def rewrite_query(self, query, clarifications, image=None):
            return "缶詰"

        def search_item_candidates(self, query, *, limit=None):
            return [ItemMatch("item-can", "缶詰", "金・ガ", "金物・ガラス類",
                              "松山・北条の金・ガで出す", .93)]

        def classify(self, query, clarifications, documents, image=None):
            assert documents and all("松山・北条" not in doc.text for doc in documents)
            return ClassificationDecision(is_resolved=True, item_name="缶詰",
                                          category_code="缶", confidence=.96,
                                          evidence_indexes=(1,))

    class NoIslandHits:
        def search(self, query):
            return []

    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr("app.services.waste_guide_service.NakajimaSearchService", NoIslandHits)
    service = WasteGuideService(
        gateway=SharedQueryGateway(),
        calendar=calendar(ISLAND, {"2026-11-02": ["cans"]}),
        now_provider=lambda: datetime(2026, 10, 30, 9, tzinfo=ZoneInfo("Asia/Tokyo")),
    )
    result = service.query(query="缶詰" if image is None else "",
                           municipality_id="38201", district_id=ISLAND.area_id,
                           image=image)
    assert result.status == "answered"
    assert result.decision.category_code == "缶"
    assert result.next_collection.date == date(2026, 11, 2)
    assert all(doc.uri.startswith("nakajima://shared/") for doc in result.sources)


def test_nakajima_shared_bulky_item_uses_island_collection_method(monkeypatch):
    class BulkyGateway(FakeGateway):
        def search_item_candidates(self, query, *, limit=None):
            return [ItemMatch("item-chair", "いす", "粗大", "粗大ごみ", "", .91)]

        def classify(self, query, clarifications, documents, image=None):
            assert "地区別カレンダーの収集日に集積場所" in documents[0].text
            assert "戸別" not in documents[0].text
            return ClassificationDecision(is_resolved=True, item_name="いす",
                                          category_code="粗大", confidence=.95,
                                          evidence_indexes=(1,))

    class NoIslandHits:
        def search(self, query):
            return []

    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr("app.services.waste_guide_service.NakajimaSearchService", NoIslandHits)
    service = WasteGuideService(gateway=BulkyGateway(),
        calendar=calendar(ISLAND, {"2026-11-02": ["bulky"]}),
        now_provider=lambda: datetime(2026, 10, 30, 9, tzinfo=ZoneInfo("Asia/Tokyo")))
    result = service.query(query="いす", municipality_id="38201", district_id=ISLAND.area_id)
    assert result.status == "answered"
    assert result.next_collection.date == date(2026, 11, 2)
    assert "戸別" not in result.answer


@pytest.mark.parametrize(("query", "expected"), [
    ("缶", "飲料・缶詰用"),
    ("びん", "飲料・食料品用"),
    ("空き缶・空きびん", "缶とびんのどちら"),
])
def test_nakajima_ambiguous_container_requires_user_confirmation(monkeypatch, query, expected):
    class NoClassificationGateway(FakeGateway):
        def classify(self, *args, **kwargs):
            raise AssertionError("ambiguous use must not reach model classification")

    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    service = WasteGuideService(gateway=NoClassificationGateway())
    result = service.decide(query=query, rewritten_query="缶詰",
        documents=[RetrievedDocument(text="品目: 缶詰\n分類: 缶類 (缶)",
                                     uri="nakajima://items/test", score=.99)],
        municipality_id="38201", district_id=ISLAND.area_id)
    assert result.status == "needs_clarification"
    assert expected in result.follow_up_question


def test_nakajima_mixed_container_answers_advance_to_use_question():
    first = WasteGuideService._nakajima_container_question("空き缶・空きびん", [])
    second = WasteGuideService._nakajima_container_question(
        "空き缶・空きびん", [{"answer": "缶"}])
    third = WasteGuideService._nakajima_container_question(
        "空き缶・空きびん", [{"answer": "缶"}, {"answer": "飲料用"}])
    assert first == "捨てるのは缶とびんのどちらですか？"
    assert second == "その缶は飲料・缶詰用ですか、それとも別の用途ですか？"
    assert third is None


def test_nakajima_furniture_example_matches_natural_phrase(tmp_path):
    import csv
    source = tmp_path / "nakajima_items.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "item_id", "item", "category", "category_display", "note",
        ])
        writer.writeheader()
        writer.writerow({"item_id": "nk-item-furniture", "item": "家具類",
                         "category": "粗大", "category_display": "粗大ごみ",
                         "note": "中島の公式カレンダーに家具類が掲載"})
        writer.writerow({"item_id": "nk-item-network", "item": "ネット類",
                         "category": "プラ", "category_display": "プラスチック製容器包装",
                         "note": "包装用ネット"})

    service = NakajimaSearchService(path=source)
    assert service.search("大きな壊れた家具")[0]["item"] == "家具類"
    assert service.search("大きな壊れた木製家具")[0]["category"] == "粗大"
    assert service.search("漁業用ネット") == []  # Other *類 examples are not stemmed.
    assert service.search("スプリングマットレス付き家具") == []


def test_nakajima_food_bottle_accepts_context_and_yes_answer():
    question = "そのびんは飲料・食料品用ですか？"
    assert WasteGuideService._nakajima_container_question(
        "ジャムが入っていたガラスびん", []) is None
    assert WasteGuideService._nakajima_container_question(
        "ガラスびん", []) == question
    assert WasteGuideService._nakajima_container_question(
        "ガラスびん", [{"question": question, "answer": "はい"}]) is None
    assert WasteGuideService._nakajima_container_question(
        "ガラスびん", [{"question": "飲料・食料用品ですか？", "answer": "はい"}]) is None
    assert WasteGuideService._nakajima_container_question(
        "ガラスびん", [{"question": question, "answer": "飲料・食料品用です"}]) is None
    assert WasteGuideService._nakajima_container_question(
        "ガラスびん", [{"question": "ガラス製ですか？", "answer": "はい"}]) == question
    assert WasteGuideService._nakajima_container_question(
        "ガラスびん", [{"question": question, "answer": "はい"},
                     {"question": question, "answer": "いいえ"}]) == question


@pytest.mark.parametrize(("query", "clarifications", "category", "item"), [
    ("大きな壊れた家具", [], "粗大", "家具類"),
    ("大きな壊れた家具", [{"question": "素材は何ですか？", "answer": "木材"}], "粗大", "家具類"),
    ("ジャムが入っていたガラスびん", [], "びん", "びん類"),
    ("ガラスびん", [{"question": "そのびんは飲料・食料品用ですか？", "answer": "はい"}], "びん", "びん類"),
])
def test_reported_nakajima_search_flows_keep_official_evidence(
    tmp_path, monkeypatch, query, clarifications, category, item,
):
    import csv
    source = tmp_path / "nakajima_items.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "item_id", "item", "category", "category_display", "note",
        ])
        writer.writeheader()
        writer.writerow({"item_id": "nk-item-furniture", "item": "家具類",
                         "category": "粗大", "category_display": "粗大ごみ",
                         "note": "公式カレンダーに家具類が粗大ごみとして掲載"})
        writer.writerow({"item_id": "nk-rule-bottle", "item": "びん類",
                         "category": "びん", "category_display": "びん類",
                         "note": "飲料・食料品用のびんを収集"})

    class DecisionGateway(FakeGateway):
        def classify(self, query, clarifications, documents, image=None):
            assert documents[0].uri.startswith("nakajima://items/")
            assert f"品目: {item}" in documents[0].text
            return ClassificationDecision(is_resolved=True, item_name=item,
                                          category_code=category, confidence=.96,
                                          evidence_indexes=(1,))

    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr("app.services.nakajima_search_service.config.NAKAJIMA_ITEMS_PATH", str(source))
    collection_type = "bulky" if category == "粗大" else "bottles"
    service = WasteGuideService(gateway=DecisionGateway(),
        calendar=calendar(ISLAND, {"2026-11-02": [collection_type]}),
        now_provider=lambda: datetime(2026, 10, 30, 9, tzinfo=ZoneInfo("Asia/Tokyo")))
    result = service.query(query=query, municipality_id="38201", district_id=ISLAND.area_id,
                           clarifications=clarifications)
    assert result.status == "answered"
    assert result.decision.category_code == category
    assert result.next_collection.date == date(2026, 11, 2)


@pytest.mark.parametrize("rewritten", ["大きな壊れた家具", "ジャム用ガラスびん 飲料・食料品用"])
def test_verified_nakajima_rule_precedes_shared_index(tmp_path, monkeypatch, rewritten):
    import csv
    source = tmp_path / "nakajima_items.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "item_id", "item", "category", "category_display", "note",
        ])
        writer.writeheader()
        writer.writerow({"item_id": "nk-item-furniture", "item": "家具類",
                         "category": "粗大", "category_display": "粗大ごみ", "note": "公式例"})
        writer.writerow({"item_id": "nk-rule-bottle", "item": "びん類",
                         "category": "びん", "category_display": "びん類",
                         "note": "飲料・食料品用のびん"})

    class IndexMustNotRun(FakeGateway):
        def search_item_candidates(self, query, *, limit=None):
            raise AssertionError("The official rule already supplies evidence")

    monkeypatch.setattr("app.services.waste_guide_service.get_registry", lambda: FakeRegistry())
    monkeypatch.setattr("app.services.nakajima_search_service.config.NAKAJIMA_ITEMS_PATH", str(source))
    service = WasteGuideService(gateway=IndexMustNotRun())
    docs = service.retrieve(rewritten_query=rewritten, municipality_id="38201",
                            district_id=ISLAND.area_id)
    assert len(docs) == 1 and docs[0].uri.startswith("nakajima://items/")
