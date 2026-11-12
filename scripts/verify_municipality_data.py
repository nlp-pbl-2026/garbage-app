#!/usr/bin/env python3
"""Offline integration checks for catalog-declared data, never a RAG accuracy test.

Uses a stored item vector to exercise index retrieval without query embedding.
Does not download, regenerate, deploy or modify any municipality data.
"""

import argparse
import csv
import hashlib
import io
import json
from datetime import date, timedelta
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.calendar_service import CalendarService
from app.services.embedding_search_service import EmbeddingSearchService
from app.services.item_search_service import ItemSearchService
from app.services.region_registry_service import MunicipalityCatalog


class StoredVectorRuntime:
    """Local fixture response; no boto client and no model/API inference."""

    def __init__(self, vector):
        self.vector = vector

    def invoke_model(self, **_kwargs):
        return {"body": io.BytesIO(json.dumps({"embedding": self.vector}).encode())}


def verify(catalog_path=None):
    catalog_path = catalog_path or ROOT / "data/regions/catalog.json"
    catalog = MunicipalityCatalog(catalog_path)
    indices, bundles, cities = {}, {}, []
    for city_id in catalog.entries:
        registry = catalog.registry(city_id)
        base = registry.path.parent.resolve()
        first, last = map(
            date.fromisoformat, (registry.data["valid_from"], registry.data["valid_to"])
        )
        profiles = []
        for profile_id, profile in registry.profiles.items():
            for path in (
                profile.items_path,
                profile.embedding_index_path,
                profile.calendar_path,
            ):
                assert path.resolve().is_relative_to(base), (city_id, profile_id, path)
                assert path.is_file(), path
            key = (profile.items_path, profile.embedding_index_path)
            if key not in indices:
                with profile.items_path.open(
                    encoding="utf-8-sig", newline=""
                ) as stream:
                    rows = list(csv.DictReader(stream))
                manifest_path = profile.items_path.parent / "index_manifest.json"
                manifest = json.loads(manifest_path.read_text())
                for path, field in (
                    (profile.items_path, "source_sha256"),
                    (profile.embedding_index_path, "index_sha256"),
                ):
                    assert (
                        hashlib.sha256(path.read_bytes()).hexdigest() == manifest[field]
                    ), path
                ids = [row["item_id"] for row in rows]
                assert len(ids) == len(set(ids)) == manifest["item_count"]
                assert manifest["model_id"] == "amazon.titan-embed-text-v2:0"
                assert manifest["dimensions"] == 1024
                with np.load(
                    profile.embedding_index_path, allow_pickle=False
                ) as values:
                    assert values["item_ids"].astype(str).tolist() == ids
                    vectors = values["vectors"]
                    assert vectors.shape == (len(ids), 1024)
                    assert np.isfinite(vectors).all()
                    assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=0.002)
                    vector = vectors[0].tolist()
                search = EmbeddingSearchService(
                    items_path=profile.items_path,
                    embeddings_path=profile.embedding_index_path,
                    municipality_id=city_id,
                    profile_id=profile.index_profile_id,
                    runtime_client=StoredVectorRuntime(vector),
                )
                assert search.is_ready
                hits = search.search("stored vector connectivity check", limit=1)
                assert hits and hits[0].item_id in ids
                query = next(row["item"] for row in rows if len(row["item"]) >= 2)
                keyword = ItemSearchService(
                    items_path=profile.items_path, municipality_id=city_id
                )
                assert keyword.search(query, limit=1)
                indices[key] = dict(
                    items=len(ids),
                    municipality_id=city_id,
                    profile_id=profile.index_profile_id,
                    csv_sha256=manifest["source_sha256"],
                    npz_sha256=manifest["index_sha256"],
                )
            else:
                assert indices[key]["municipality_id"] == city_id
                assert indices[key]["profile_id"] == profile.index_profile_id
            profiles.append(profile_id)
            if profile.calendar_path not in bundles:
                bundles[profile.calendar_path] = json.loads(
                    profile.calendar_path.read_text()
                )

        cells, events, partial, unknown_streams, unknown_days = 0, 0, 0, 0, 0
        for area in registry.areas.values():
            region = registry.resolve(city_id, area["id"])
            bundle = bundles[region.rules.calendar_path]
            service = CalendarService(region=region, bundle=bundle)
            assert service.availability in {"available", "partially_available"}, area[
                "id"
            ]
            record = bundle["calendars"][area["calendar_id"]]
            cells += len(record["days"])
            partial += service.availability == "partially_available"
            for day, streams in record["days"].items():
                assert date.fromisoformat(day).isoformat() == day
                assert first <= date.fromisoformat(day) <= last
                assert len(streams) == len(set(streams)), (area["id"], day)
                events += len(streams)
            for code, definition in region.rules.categories.items():
                assert (
                    service.next_collection(code, from_date=last + timedelta(days=1))
                    is None
                )
                assert (
                    service.next_collection(code, from_date=first - timedelta(days=1))
                    is None
                )
                result = service.next_collection(code, from_date=first)
                if definition.collection_type_id is None:
                    assert (
                        result is None
                        and service.collection_status(code).status == "not_scheduled"
                    )
                elif result:
                    assert first <= result.date <= last
                    assert (
                        definition.collection_type_id
                        in record["days"][result.date.isoformat()]
                    )
                info = record.get("collection_type_verification", {}).get(
                    definition.collection_type_id, {}
                )
                if info.get("status") == "unverified":
                    unknown_streams += 1
                    assert (
                        result is None
                        and service.collection_status(code).status == "unverified"
                    )
                for day in record.get("unverified_dates", {}).get(
                    definition.collection_type_id, {}
                ):
                    unknown_days += 1
                    assert (
                        service.next_collection(code, from_date=date.fromisoformat(day))
                        is None
                    )
                    assert service.collection_status(code).status == "unverified"
        cities.append(
            dict(
                id=city_id,
                name=registry.data.get("municipality_name"),
                version=registry.data["version"],
                valid_from=str(first),
                valid_to=str(last),
                profiles=profiles,
                areas=len(registry.areas),
                calendars=len(registry.calendars),
                area_date_cells=cells,
                area_events=events,
                partially_available_areas=partial,
                unverified_area_categories=unknown_streams,
                unverified_area_dates=unknown_days,
            )
        )
    return dict(
        municipalities=len(cities),
        profiles=sum(len(c["profiles"]) for c in cities),
        indices=len(indices),
        items=sum(i["items"] for i in indices.values()),
        calendar_bundles=len(bundles),
        areas=sum(c["areas"] for c in cities),
        area_date_cells=sum(c["area_date_cells"] for c in cities),
        cities=cities,
        api_calls=0,
        semantic_accuracy_tested=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="Optional local report, never the source dataset"
    )
    args = parser.parse_args()
    report = verify()
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    print(output)
