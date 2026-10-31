"""Synthetic municipalities exercise isolation without official data or AWS calls."""
import csv
import hashlib
import io
import importlib.util
import json
from pathlib import Path
from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app import config
from app.main import app
from app.services.calendar_service import CalendarService
from app.services.region_registry_service import (
    MunicipalityCatalog, RegionalDataError, RegionResolutionError, get_registry,
)
from app.services.waste_guide_service import (
    BedrockGateway, ClassificationDecision, ImageInput, RetrievedDocument,
    UnsupportedRegionError, WasteGuideError, WasteGuideService,
)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def municipalities(tmp_path, monkeypatch):
    # Deliberately reuse area IDs, profile IDs, item IDs and category codes.
    # Only the municipality and dataset version identify which files to use.
    for city, label, version in [("90001", "試験市A", "a-v1"), ("90002", "試験町B", "b-v1")]:
        root = tmp_path / city
        root.mkdir()
        items = root / "items.csv"
        with items.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["item_id", "item", "category", "category_display", "note"])
            writer.writeheader()
            writer.writerow(dict(item_id="same-item", item="試験品", category="可燃",
                                 category_display=f"{label}回収物", note=f"{label}専用の出し方"))
            writer.writerow(dict(item_id="dropoff", item="試験持込品", category="X",
                                 category_display="専用持込", note="公式窓口へ持ち込む"))
        index = root / "items.npz"
        np.savez(index, vectors=np.array([[1., 0.], [0., 1.]], dtype=np.float32),
                 item_ids=np.array(["same-item", "dropoff"]),
                 model_id="synthetic-embedding", dimensions=2)
        write_json(root / "index_manifest.json", {
            "municipality_id": city, "profile_id": "nakajima", "item_count": 2,
            "model_id": "synthetic-embedding", "dimensions": 2,
            "source_sha256": hashlib.sha256(items.read_bytes()).hexdigest(),
            "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
        })
        write_json(root / "registry.json", {
            "municipality_id": city, "municipality_name": label, "version": version,
            "valid_from": "2026-01-01", "valid_to": "2026-12-31",
            "collection_areas": [{"id": "same-area", "name": f"{label}地区",
                                  "calendar_id": "same-calendar", "rule_profile_id": "nakajima"}],
            "calendars": [{"id": "same-calendar", "rule_profile_id": "nakajima"}],
            "rule_profiles": {"nakajima": {
                "items_path": "items.csv", "embedding_index_path": "items.npz",
                "calendar_path": "calendar.json", "classification_rules": f"{label}では試験品を回収物に分類する。",
                "size_question": f"{label}の指定袋に入りますか？",
                "categories": {
                    "可燃": {"name": f"{label}回収物", "collection_type_id": "test_stream", "cutoff": "08:30"},
                    "X": {"name": "専用持込", "answer_note": f"{label}の公式窓口へ持ち込んでください。"},
                },
            }},
        })
        days = (["2026-11-02", "2026-11-04"] if city == "90001" else ["2026-11-03", "2026-11-05"])
        write_json(root / "calendar.json", {
            "municipality_id": city, "version": version,
            "valid_from": "2026-01-01", "valid_to": "2026-12-31",
            "calendars": {"same-calendar": {"verification_status": "checked",
                                             "days": {day: ["test_stream"] for day in days}}},
        })
    catalog = tmp_path / "catalog.json"
    write_json(catalog, {"municipalities": [
        {"id": city, "registry_path": f"{city}/registry.json"} for city in ("90001", "90002")
    ]})
    monkeypatch.setenv("MUNICIPALITY_CATALOG_PATH", str(catalog))
    get_registry.cache_clear()
    yield tmp_path
    get_registry.cache_clear()


class Runtime:
    def __init__(self):
        self.embeddings = []
        self.prompts = []
        self.resolved = True
        self.category = "可燃"
        self.vector = [1., 0.]

    def invoke_model(self, **kwargs):
        self.embeddings.append(kwargs)
        return {"body": io.BytesIO(json.dumps({"embedding": self.vector}).encode())}

    def converse(self, **kwargs):
        self.prompts.append(kwargs)
        prompt = kwargs["messages"][0]["content"][-1]["text"]
        payload = ({"search_query": "試験品"} if '"search_query"' in prompt else {
            "is_resolved": self.resolved, "item_name": "試験品", "category_code": self.category,
            "disposal_instructions": "資料の出し方に従う", "confidence": .97,
            "clarifying_question": "家庭用の品物ですか？", "evidence_indexes": [1],
        })
        return {"output": {"message": {"content": [{"text": json.dumps(payload)}]}}}


def guide(runtime=None):
    runtime = runtime or Runtime()
    return WasteGuideService(
        gateway=BedrockGateway(runtime_client=runtime, agent_runtime_client=object()),
        today_provider=lambda: date(2026, 11, 1),
    )


def test_catalog_resolves_independent_profiles_and_ignores_legacy_overrides(municipalities, monkeypatch):
    for name in ("KNOWLEDGE_ITEMS_PATH", "EMBEDDING_INDEX_PATH", "CALENDAR_BUNDLE_PATH"):
        monkeypatch.setattr(config, name, "/missing/matsuyama-only")
    catalog = get_registry()
    a, b = (catalog.resolve(city, "same-area") for city in ("90001", "90002"))
    assert a.category_names["可燃"] == "試験市A回収物"
    assert not a.is_nakajima  # Matching profile names never activate Matsuyama's rules.
    assert a.asset_path("items_path") != b.asset_path("items_path")
    assert a.asset_path("calendar_path") == municipalities / "90001/calendar.json"
    with pytest.raises(RegionResolutionError):
        catalog.resolve("38201", "same-area")
    with pytest.raises(RegionResolutionError):
        catalog.resolve("90001", "38201-08")


@pytest.mark.parametrize("broken", ["missing_registry", "wrong_municipality", "missing_profiles", "missing_categories",
                                   "missing_rules", "invalid_cutoff", "absolute_asset"])
def test_registered_broken_data_fails_without_default_city(municipalities, broken):
    path = municipalities / "90001/registry.json"
    if broken == "missing_registry":
        path.unlink()
    else:
        raw = json.loads(path.read_text())
        if broken == "wrong_municipality": raw["municipality_id"] = "38201"
        if broken == "missing_profiles": raw.pop("rule_profiles")
        if broken == "missing_categories": raw["rule_profiles"]["nakajima"]["categories"] = {}
        if broken == "missing_rules": raw["rule_profiles"]["nakajima"].pop("classification_rules")
        if broken == "invalid_cutoff": raw["rule_profiles"]["nakajima"]["categories"]["可燃"]["cutoff"] = "99:99"
        if broken == "absolute_asset": raw["rule_profiles"]["nakajima"]["items_path"] = str(path.parent / "items.csv")
        write_json(path, raw)
    with pytest.raises(RegionalDataError):
        get_registry().resolve("90001", "same-area")


def test_unknown_city_is_rejected_before_creating_aws_clients(municipalities, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("No AWS client is needed for unsupported regions")
    monkeypatch.setattr("app.services.waste_guide_service.boto3.client", unexpected)
    with pytest.raises(UnsupportedRegionError):
        WasteGuideService().rewrite(query="試験品", municipality_id="38201", district_id="38201-08")


def test_real_search_code_switches_indexes_rules_and_calendars(municipalities):
    runtime = Runtime()
    service = guide(runtime)
    a = service.query(query="試験品", municipality_id="90001", district_id="same-area")
    b = service.query(query="試験品", municipality_id="90002", district_id="same-area", image=ImageInput("png", b"test"))
    assert a.category_name == "試験市A回収物" and b.category_name == "試験町B回収物"
    assert a.next_collection.date == date(2026, 11, 2)
    assert b.next_collection.date == date(2026, 11, 3)
    assert "試験市A専用" in a.sources[0].text
    assert "試験町B専用" in b.sources[0].text
    assert a.sources[0].uri != b.sources[0].uri
    for request in runtime.prompts:
        prompt = request["messages"][0]["content"][-1]["text"]
        assert "松山市" not in prompt and "松山・北条" not in prompt and "中島地域" not in prompt
    assert runtime.embeddings[0]["modelId"] == "synthetic-embedding"
    assert len(service._gateway._regional_embedding_searches) == 2


@pytest.mark.parametrize("missing", ["items.csv", "items.npz", "index_manifest.json"])
def test_missing_knowledge_never_uses_matsuyama(municipalities, missing):
    (municipalities / "90001" / missing).unlink()
    runtime = Runtime()
    with pytest.raises(WasteGuideError, match="index is unavailable"):
        guide(runtime).retrieve(rewritten_query="試験品", municipality_id="90001", district_id="same-area")
    assert not runtime.embeddings


def test_low_level_search_requires_explicit_paths_for_new_city():
    from app.services.embedding_search_service import EmbeddingSearchService
    from app.services.item_search_service import ItemSearchService
    with pytest.raises(ValueError, match="explicit regional"):
        ItemSearchService(municipality_id="90001")
    with pytest.raises(ValueError, match="Explicit regional"):
        EmbeddingSearchService(municipality_id="90001")


@pytest.mark.parametrize("key,value", [("municipality_id", "90002"), ("profile_id", "other"), ("source_sha256", "invalid")])
def test_index_identity_and_hash_are_checked(municipalities, key, value):
    path = municipalities / "90001/index_manifest.json"
    raw = json.loads(path.read_text()); raw[key] = value; write_json(path, raw)
    with pytest.raises(WasteGuideError):
        guide().retrieve(rewritten_query="試験品", municipality_id="90001", district_id="same-area")


def test_calendar_uses_minute_cutoff_and_calendar_year(municipalities):
    region = get_registry().resolve("90001", "same-area")
    calendar = CalendarService(region=region)
    assert calendar.next_collection("可燃", at=datetime(2026, 11, 2, 8, 29, tzinfo=ZoneInfo("Asia/Tokyo"))).date == date(2026, 11, 2)
    assert calendar.next_collection("可燃", at=datetime(2026, 11, 2, 8, 30, tzinfo=ZoneInfo("Asia/Tokyo"))).date == date(2026, 11, 4)
    assert calendar.next_collection("可燃", from_date=date(2027, 1, 1)) is None
    assert calendar.next_collection("X", from_date=date(2026, 11, 1)) is None


@pytest.mark.parametrize("change", ["missing", "municipality_id", "version", "verification_status"])
def test_unavailable_calendar_has_no_default_dates(municipalities, change):
    path = municipalities / "90001/calendar.json"
    if change == "missing": path.unlink()
    else:
        raw = json.loads(path.read_text())
        if change == "verification_status": raw["calendars"]["same-calendar"][change] = "pending"
        else: raw[change] = "other"
        write_json(path, raw)
    calendar = CalendarService(region=get_registry().resolve("90001", "same-area"))
    assert calendar.availability != "available"
    assert calendar.next_collection("可燃", from_date=date(2026, 11, 1)) is None


@pytest.mark.parametrize("uri", ["local://items/same-item", "nakajima://items/same-item",
                                 "regional://90002/nakajima/a-v1/items/same-item",
                                 "regional://90001/other/a-v1/items/same-item",
                                 "regional://90001/nakajima/old/items/same-item"])
def test_other_dataset_evidence_is_rejected(municipalities, uri):
    runtime = Runtime()
    with pytest.raises(UnsupportedRegionError):
        guide(runtime).decide(query="試験品", rewritten_query="試験品",
                              municipality_id="90001", district_id="same-area",
                              documents=[RetrievedDocument("分類コード: 可燃", uri=uri)])
    assert not runtime.prompts


def test_followups_and_non_calendar_guidance_use_selected_city(municipalities):
    runtime = Runtime(); runtime.resolved = False
    service = guide(runtime)
    first = service.query(query="試験品", municipality_id="90001", district_id="same-area")
    assert first.status == "needs_clarification"
    runtime.resolved = True
    answered = service.query(query="試験品", municipality_id="90001", district_id="same-area",
                             clarifications=[{"question": first.follow_up_question, "answer": "はい"}])
    assert answered.status == "answered"
    empty = service.decide(query="未知", rewritten_query="未知", documents=[], municipality_id="90001",
                           district_id="same-area", clarifications=[{"question": "品物は？", "answer": "未知"}])
    assert "試験市A" in empty.answer and "松山市" not in empty.answer
    region = get_registry().resolve("90001", "same-area")
    note = service._build_answer(ClassificationDecision(True, "試験持込品", "X"), None, region=region)
    assert "公式窓口へ持ち込んで" in note and "戸別収集" not in note


def test_matsuyama_category_is_not_accepted_in_another_city(municipalities):
    runtime = Runtime(); runtime.category = "埋立"
    result = guide(runtime).query(query="試験品", municipality_id="90001", district_id="same-area")
    assert result.status == "needs_clarification"
    assert result.next_collection is None and not result.decision.is_resolved


def test_new_category_code_can_be_classified_with_local_label_and_disposal(municipalities):
    runtime = Runtime(); runtime.category = "X"; runtime.vector = [0., 1.]
    result = guide(runtime).query(query="試験持込品", municipality_id="90001", district_id="same-area")
    assert result.status == "answered" and result.category_name == "専用持込"
    assert result.next_collection is None
    assert "試験市Aの公式窓口へ持ち込んで" in result.answer


def test_missing_calendar_can_classify_but_never_invent_a_collection_date(municipalities):
    (municipalities / "90001/calendar.json").unlink()
    result = guide().query(query="試験品", municipality_id="90001", district_id="same-area")
    assert result.status == "answered" and result.next_collection is None
    assert "次回収集日を確認できません" in result.answer


def test_generic_lexical_search_uses_selected_items(municipalities, monkeypatch):
    monkeypatch.setattr(config, "LEXICAL_SEARCH_ENABLED", True)
    docs = guide().retrieve(rewritten_query="試験品", municipality_id="90002", district_id="same-area")
    assert docs and all(doc.uri.startswith("regional://90002/") for doc in docs)
    assert "試験町B専用" in docs[0].text


def test_global_knowledge_base_never_applies_to_new_city(municipalities, monkeypatch):
    monkeypatch.setattr(config, "USE_BEDROCK_KNOWLEDGE_BASE", True)
    monkeypatch.setattr(config, "BEDROCK_KNOWLEDGE_BASE_ID", "matsuyama-only")
    with pytest.raises(WasteGuideError, match="not configured"):
        guide().retrieve(rewritten_query="試験品", municipality_id="90001", district_id="same-area")


@pytest.mark.asyncio
async def test_api_preserves_response_shape_with_new_category_names(municipalities, monkeypatch):
    service = guide()
    events = []
    class Log:
        def record(self, event): events.append(event)
    monkeypatch.setattr("app.routers.search_router.WasteGuideService", lambda: service)
    monkeypatch.setattr("app.routers.search_router.SearchLogService", Log)
    body = {"query": "試験品", "municipality_id": "90001", "district_id": "same-area"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        rewritten = (await client.post("/api/search/rewrite", json=body)).json()["rewritten_query"]
        retrieved = await client.post("/api/search/retrieve", json={**body, "rewritten_query": rewritten})
        documents = retrieved.json()["documents"]
        response = await client.post("/api/search/decide", json={**body, "rewritten_query": rewritten, "documents": documents})
        assert response.status_code == 200
        assert response.json()["classification"]["category_name"] == "試験市A回収物"
        assert response.json()["next_collection"]["date"] == "2026-11-02"
        assert events[0]["category_name"] == "試験市A回収物"
        items = await client.get("/api/search/items/90001", params={"district_id": "same-area", "category": "X"})
        assert items.status_code == 200
        assert items.json()["municipality_name"] == "試験市A"
        assert items.json()["items"][0]["category"] == "専用持込"


@pytest.mark.asyncio
async def test_api_errors_distinguish_unsupported_and_missing_data(municipalities):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/search/rewrite", json={
            "query": "試験品", "municipality_id": "not-registered", "district_id": "same-area"})
        assert response.status_code == 422
        assert (await client.get("/api/search/items/not-registered")).status_code == 404
        assert (await client.get("/api/search/items/90001")).status_code == 422
        (municipalities / "90001/registry.json").unlink()
        response = await client.post("/api/search/rewrite", json={
            "query": "試験品", "municipality_id": "90001", "district_id": "same-area"})
        assert response.status_code == 503


def packaging_module():
    path = Path(__file__).resolve().parents[2] / "scripts/package_backend_data.py"
    spec = importlib.util.spec_from_file_location("package_backend_data", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_includes_only_declared_runtime_data(municipalities):
    (municipalities / "90001/source.pdf").write_bytes(b"not runtime data")
    destination = municipalities / "build"
    targets = packaging_module().stage_data(destination, municipalities / "catalog.json")
    assert len(targets) == 11
    assert not list(destination.rglob("*.pdf"))
    catalog = MunicipalityCatalog(destination / "data/regions/catalog.json")
    region = catalog.resolve("90002", "same-area")
    assert region.asset_path("items_path").is_relative_to(destination)
    assert CalendarService(region=region).next_collection("可燃", from_date=date(2026, 11, 1)).date == date(2026, 11, 3)


def test_package_refuses_incomplete_data_before_copying(municipalities):
    (municipalities / "90002/items.npz").unlink()
    destination = municipalities / "build"
    with pytest.raises(FileNotFoundError):
        packaging_module().stage_data(destination, municipalities / "catalog.json")
    assert not destination.exists()


def test_explicit_conditional_codes_can_support_a_different_final_classification(municipalities):
    from app.services.item_search_service import ItemMatch
    region = MunicipalityCatalog(municipalities / "catalog.json").resolve('90001', 'same-area')
    match = ItemMatch(item_id='test', item='試験品', category='可燃', category_display='試験市A回収物',
        note='小さいものは回収、大きいものは専用持込', score=.9, category_options=('X',))
    document = RetrievedDocument(text=match.evidence_text, uri=region.evidence_prefix+'items/test')
    assert BedrockGateway._document_supports_category(document, '可燃', region=region)
    assert BedrockGateway._document_supports_category(document, 'X', region=region)
    unverified = RetrievedDocument(text=match.evidence_text.replace('条件付き分類コード: ["X"]\n', ''))
    assert not BedrockGateway._document_supports_category(unverified, 'X', region=region)


@pytest.mark.parametrize('options', ['["X", "unknown"]', '"X"', '{"X": true}', '[null]'])
def test_unknown_or_malformed_conditional_codes_never_support_a_decision(municipalities, options):
    region = MunicipalityCatalog(municipalities / "catalog.json").resolve('90001', 'same-area')
    document = RetrievedDocument(text='分類コード: 可燃\n分類: 回収物\n条件付き分類コード: '+options)
    assert not BedrockGateway._document_supports_category(document, 'X', region=region)


def test_explicit_packaging_mark_avoids_duplicate_material_question(municipalities):
    region = MunicipalityCatalog(municipalities / 'catalog.json').resolve('90001', 'same-area')
    options = dict(clarifications=[], documents=[], region=region)
    assert WasteGuideService._missing_detail_question(
        query='洗っても汚れが落ちないプラマーク付き弁当容器', **options) is None
    assert WasteGuideService._missing_detail_question(
        query='プラマーク付きではない容器', **options) is not None
    # The legacy path remains identical, including its established limitation.
    assert WasteGuideService._missing_detail_question(
        query='プラマーク付き容器', clarifications=[], documents=[]) is not None


def test_packaging_mark_decision_keeps_resolved_model_result_and_collection_date(municipalities):
    region = get_registry().resolve('90001', 'same-area')
    service = guide(Runtime())
    result = service.decide(query='洗っても汚れが落ちないプラマーク付き弁当容器',
        rewritten_query='弁当容器 プラマークあり', municipality_id='90001', district_id='same-area',
        documents=[RetrievedDocument('品目: 弁当容器\n分類コード: 可燃\n出し方・注意: プラマークを確認。汚れが落ちないものは可燃',
            score=.95, uri=region.evidence_prefix+'items/test')])
    assert result.status == 'answered'
    assert result.decision.category_code == '可燃'
    assert result.next_collection is not None
