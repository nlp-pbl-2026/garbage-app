"""Local runtime checks for regenerated Seiyo assets and Titan index."""
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


CITY = "38214"
ITEMS = 1293
AREAS = 17


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_runtime_assets_are_one_verified_municipality_pair():
    catalog = MunicipalityCatalog(ROOT / "data/regions/catalog.json")
    registry = catalog.registry(CITY)
    assert registry.data["municipality_name"] == "西予市"
    assert len(registry.areas) == len(registry.calendars) == AREAS
    assert set(registry.profiles) == {"cutoff_0700", "cutoff_0800"}

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
    assert search.search("西予市専用索引の接続確認", limit=1)[0].item_id.startswith("seiyo-")


def test_runtime_calendar_keeps_cutoffs_closures_and_region_variants():
    catalog = MunicipalityCatalog(ROOT / "data/regions/catalog.json")
    akehama = catalog.resolve(CITY, "38214-01")
    uwa2 = catalog.resolve(CITY, "38214-03")
    nomura = catalog.resolve(CITY, "38214-05")
    mikame = catalog.resolve(CITY, "38214-15")

    assert akehama.rules.categories["burnable"].cutoff.isoformat(timespec="minutes") == "08:00"
    assert uwa2.rules.categories["burnable"].cutoff.isoformat(timespec="minutes") == "07:00"
    assert CalendarService(region=akehama).next_collection("pet", from_date=date(2027, 1, 1)).date == date(2027, 1, 9)
    assert CalendarService(region=uwa2).next_collection("bottles", from_date=date(2027, 1, 1)).date == date(2027, 1, 8)
    assert CalendarService(region=nomura).next_collection("bulky", from_date=date(2026, 4, 1)).date == date(2026, 4, 19)
    assert mikame.rules.categories["burnable"].cutoff.isoformat(timespec="minutes") == "08:00"


def test_runtime_search_uses_seiyo_rows_only():
    catalog = MunicipalityCatalog(ROOT / "data/regions/catalog.json")
    region = catalog.resolve(CITY, "38214-01")
    search = ItemSearchService(items_path=region.asset_path("items_path"), municipality_id=CITY)

    assert search.search("エアコン", limit=1)[0].category == "not_collected"
    assert search.search("充電式バッテリー", limit=1)[0].category == "hazardous"
    assert search.search("白い1000ml飲料容器パック", limit=1)[0].category == "milk_carton"
