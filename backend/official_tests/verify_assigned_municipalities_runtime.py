"""Local runtime checks for the seven assigned municipalities.

These tests use regenerated official CSV/calendar data and the local NPZ files.
The fake query vector exercises the production index loader without calling
Bedrock.  They are intentionally separate from the ordinary synthetic suite.
"""

from __future__ import annotations

import csv
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app
from app.services.calendar_service import CalendarService
from app.services.embedding_search_service import EmbeddingSearchService
from app.services.region_registry_service import get_registry


ASSIGNED = {
    "38207": {"slug": "ozu", "name": "大洲市", "items": 632, "areas": 29},
    "38402": {"slug": "tobe", "name": "砥部町", "items": 806, "areas": 7},
    "38506": {"slug": "ainan", "name": "愛南町", "items": 977, "areas": 8},
    "38488": {"slug": "kihoku", "name": "鬼北町", "items": 1219, "areas": 8},
    "38484": {"slug": "matsuno", "name": "松野町", "items": 1434, "areas": 11},
    "38422": {"slug": "uchiko", "name": "内子町", "items": 876, "areas": 26},
    "38401": {"slug": "masaki", "name": "松前町", "items": 1384, "areas": 2},
}
EXISTING = {"38201", "38204", "38210", "38442", "38205"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_catalog_and_flutter_assets_register_only_the_completed_datasets():
    catalog = get_registry()
    assert set(catalog.entries) == EXISTING | set(ASSIGNED)
    frontend = json.loads(
        (ROOT / "frontend/assets/data/municipality_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    frontend_entries = {entry["id"]: entry for entry in frontend["municipalities"]}
    assert set(frontend_entries) == set(catalog.entries)
    for municipality_id, expected in ASSIGNED.items():
        registry = catalog.registry(municipality_id)
        assert registry.data["municipality_name"] == expected["name"]
        assert len(registry.areas) == expected["areas"]
        assert len(registry.calendars) == expected["areas"]
        ui_registry = json.loads(
            (
                ROOT
                / "frontend/assets/data"
                / f"municipality_{municipality_id}_registry.json"
            ).read_text(encoding="utf-8")
        )
        assert len(ui_registry["collection_areas"]) == expected["areas"]
        assert [
            area.get("display_name", area["name"])
            for area in ui_registry["collection_areas"]
        ] == [
            area.get("display_name", area["name"])
            for area in registry.data["collection_areas"]
        ]
        assert all(area["name"].strip() for area in ui_registry["collection_areas"])
        assert frontend_entries[municipality_id]["name"] == expected["name"]
        calendar_asset = next(
            iter(frontend_entries[municipality_id]["profiles"].values())
        )["calendar_asset"]
        frontend_calendar = ROOT / "frontend" / calendar_asset
        source_calendar = next(iter(registry.profiles.values())).calendar_path
        assert frontend_calendar.read_bytes() == source_calendar.read_bytes()


@pytest.mark.parametrize("municipality_id", ASSIGNED)
def test_csv_npz_manifest_and_calendar_are_a_verified_municipality_pair(
    municipality_id,
):
    expected = ASSIGNED[municipality_id]
    registry = get_registry().registry(municipality_id)
    profile = next(iter(registry.profiles.values()))
    manifest_path = profile.items_path.parent / "index_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["municipality_id"] == municipality_id
    assert manifest["profile_id"] == "citywide"
    assert manifest["item_count"] == expected["items"]
    assert manifest["model_id"] == "amazon.titan-embed-text-v2:0"
    assert manifest["dimensions"] == 1024
    assert manifest["source_sha256"] == sha256(profile.items_path)
    assert manifest["index_sha256"] == sha256(profile.embedding_index_path)

    with profile.items_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == expected["items"]
    assert len({row["item_id"] for row in rows}) == len(rows)
    with np.load(profile.embedding_index_path, allow_pickle=False) as index:
        vectors = index["vectors"]
        assert vectors.shape == (expected["items"], 1024)
        assert list(map(str, index["item_ids"])) == [row["item_id"] for row in rows]
        assert np.isfinite(vectors).all()
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=0.002)
        query_vector = vectors[0].tolist()

    class Runtime:
        def invoke_model(self, **_kwargs):
            return {
                "body": io.BytesIO(
                    json.dumps({"embedding": query_vector}).encode("utf-8")
                )
            }

    service = EmbeddingSearchService(
        items_path=profile.items_path,
        embeddings_path=profile.embedding_index_path,
        municipality_id=municipality_id,
        profile_id="citywide",
        runtime_client=Runtime(),
    )
    assert service.is_ready
    matches = service.search("自治体専用索引の接続確認", limit=1)
    assert len(matches) == 1
    assert matches[0].item_id in {row["item_id"] for row in rows}

    for area in registry.data["collection_areas"]:
        region = registry.resolve(municipality_id, area["id"])
        calendar = CalendarService(region=region)
        assert calendar.availability == "available"
        for code, definition in region.rules.categories.items():
            if definition.collection_type_id is None:
                assert calendar.next_collection(code) is None
                assert calendar.collection_status(code).status == "not_scheduled"


@pytest.mark.asyncio
@pytest.mark.parametrize("municipality_id", ASSIGNED)
async def test_items_api_uses_each_municipalitys_own_csv(municipality_id):
    registry = get_registry().registry(municipality_id)
    area = registry.data["collection_areas"][0]
    category = next(
        code
        for code, definition in registry.profiles[area["rule_profile_id"]].categories.items()
        if definition.collection_type_id is None
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://local"
    ) as client:
        response = await client.get(
            f"/api/search/items/{municipality_id}",
            params={"district_id": area["id"], "category": category},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["municipality_name"] == ASSIGNED[municipality_id]["name"]
    with registry.profiles[area["rule_profile_id"]].items_path.open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        expected_names = [
            row["item"]
            for row in csv.DictReader(stream)
            if row["category"] == category
            or category in json.loads(row.get("category_options") or "[]")
        ]
    assert body["total_count"] == len(expected_names) > 0
    assert Counter(item["item_name"] for item in body["items"]) == Counter(
        expected_names
    )
