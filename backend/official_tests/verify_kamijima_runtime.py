"""Local runtime checks for regenerated Kamijima CSV, calendar and Titan index."""
from __future__ import annotations

import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.calendar_service import CalendarService
from app.services.embedding_search_service import EmbeddingSearchService
from app.services.item_search_service import ItemSearchService
from app.services.region_registry_service import MunicipalityCatalog
from app.services.waste_guide_service import ClassificationDecision, WasteGuideService


CITY = "38356"
ITEMS = 106
AREAS = 8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_kamijima_runtime_assets_are_one_verified_municipality_pair():
    catalog = MunicipalityCatalog(ROOT / "data/regions/catalog.json")
    registry = catalog.registry(CITY)
    assert registry.data["municipality_name"] == "上島町"
    assert len(registry.areas) == len(registry.calendars) == AREAS
    assert set(registry.profiles) == {"main_islands", "uoshima"}

    profiles = list(registry.profiles.values())
    assert len({profile.items_path for profile in profiles}) == 1
    assert len({profile.embedding_index_path for profile in profiles}) == 1
    items_path = profiles[0].items_path
    index_path = profiles[0].embedding_index_path
    manifest = json.loads((items_path.parent / "index_manifest.json").read_text(encoding="utf-8"))
    with items_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == ITEMS
    assert manifest["municipality_id"] == CITY
    assert manifest["profile_id"] == "citywide"
    assert manifest["item_count"] == ITEMS
    assert manifest["model_id"] == "amazon.titan-embed-text-v2:0"
    assert manifest["dimensions"] == 1024
    assert manifest["source_sha256"] == sha256(items_path)
    assert manifest["index_sha256"] == sha256(index_path)

    with np.load(index_path, allow_pickle=False) as index:
        vectors = index["vectors"]
        assert vectors.shape == (ITEMS, 1024)
        assert list(map(str, index["item_ids"])) == [row["item_id"] for row in rows]
        assert np.isfinite(vectors).all()
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=0.002)
        query_vector = vectors[0].tolist()

    class Runtime:
        def invoke_model(self, **_kwargs):
            return {"body": io.BytesIO(json.dumps({"embedding": query_vector}).encode())}

    search = EmbeddingSearchService(
        items_path=items_path, embeddings_path=index_path,
        municipality_id=CITY, profile_id="citywide", runtime_client=Runtime(),
    )
    assert search.is_ready
    assert search.search("上島町専用索引の接続確認", limit=1)[0].item_id.startswith("kamijima-")


def test_kamijima_runtime_calendar_uses_each_official_area_and_time_window():
    catalog = MunicipalityCatalog(ROOT / "data/regions/catalog.json")
    yuge1 = catalog.resolve(CITY, "38356-01")
    yuge2 = catalog.resolve(CITY, "38356-02")
    fish = catalog.resolve(CITY, "38356-08")

    assert CalendarService(region=yuge1).next_collection("burnable", from_date=date(2026, 4, 6)).date == date(2026, 4, 6)
    assert CalendarService(region=yuge2).next_collection("bottles", from_date=date(2026, 4, 1)).date == date(2026, 4, 6)
    assert CalendarService(region=fish).next_collection("bulky", from_date=date(2026, 4, 4)).date == date(2026, 4, 6)
    assert yuge1.rules.categories["burnable"].cutoff.isoformat(timespec="minutes") == "08:00"
    assert fish.rules.categories["burnable"].start_time.isoformat(timespec="minutes") == "07:00"
    assert fish.rules.categories["burnable"].cutoff.isoformat(timespec="minutes") == "10:00"
    assert CalendarService(region=yuge1).next_collection("not_collected", from_date=date(2026, 4, 1)) is None


def test_kamijima_quantity_branch_requires_confirmation_before_classification():
    catalog = MunicipalityCatalog(ROOT / "data/regions/catalog.json")
    region = catalog.resolve(CITY, "38356-01")
    search = ItemSearchService(
        items_path=region.asset_path("items_path"), municipality_id=CITY
    )
    documents = WasteGuideService._exact_item_documents(
        search=search, query="陶器の植木鉢", region=region
    )
    assert documents and "条件付き分類コード" in documents[0].text

    class Gateway:
        def classify(self, query, clarifications, evidence, image=None):
            return ClassificationDecision(
                is_resolved=True,
                item_name="陶器の植木鉢",
                category_code="ceramics",
                confidence=.99,
                evidence_indexes=(1,),
            )

    result = WasteGuideService(gateway=Gateway()).decide(
        query="陶器の植木鉢",
        rewritten_query="陶器の植木鉢",
        documents=documents,
        municipality_id=CITY,
        district_id="38356-01",
    )
    assert result.status == "needs_clarification"
    assert result.follow_up_question == "植木鉢は少量ですか、それとも多量ですか？"
