"""Regional search behavior with synthetic data and no Bedrock calls."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.calendar_service import CalendarService
from app.services.nakajima_search_service import NakajimaSearchService
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
