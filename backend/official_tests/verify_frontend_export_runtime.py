"""Offline public API integration; requires the installed official UI datasets."""

import asyncio
import json
from pathlib import Path
import sys
from urllib.parse import urlencode, urlsplit

from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.lambda_main import app, handler
from app.services.frontend_data_contract import asset_name, decode
from app.services.frontend_data_service import build_snapshot
from fetch_frontend_data import fetch


def public_environment(monkeypatch):
    catalog = ROOT / "data/regions/catalog.json"
    monkeypatch.setenv("MUNICIPALITY_CATALOG_PATH", str(catalog))
    monkeypatch.delenv("FRONTEND_DATA_ALLOW_UNREVIEWED_LOCAL", raising=False)
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "offline-public-api-test")
    monkeypatch.setenv("AWS_LAMBDA_RUNTIME_API", "127.0.0.1:9001")
    return catalog


def test_public_snapshot_downloads_all_twenty_municipalities_without_local_override(
    tmp_path, monkeypatch
):
    catalog = public_environment(monkeypatch)
    client = TestClient(
        app, base_url="https://example.test", client=("198.51.100.1", 1)
    )

    def get(url):
        parsed = urlsplit(url)
        response = client.get(
            parsed.path + ("?" + parsed.query if parsed.query else "")
        )
        assert response.status_code == 200, response.text
        return response.json()

    # Keep API pacing disabled only in this in-process integration test.
    monkeypatch.setattr("fetch_frontend_data.time.sleep", lambda _: None)
    expected = {c["id"] for c in decode(catalog.read_bytes())["municipalities"]}
    output = tmp_path / "downloaded"
    manifest = fetch("https://example.test", output, expected_ids=expected, get=get)
    assert len(expected) == 20
    assert manifest["publication_status"] == "enabled"
    assert manifest["redistribution_status"] == "pending"
    original, assets = build_snapshot(catalog)
    assert manifest["dataset_version"] == original["dataset_version"]
    assert len(assets) == 47
    assert all((output / name).read_bytes() == body for name, body in assets.items())
    cities = manifest["catalog"]["municipalities"]
    assert sum(len(c["profiles"]) for c in cities) == 43
    assert sum("addresses_asset" in c for c in cities) == 6
    assert sum("addresses_asset" not in c for c in cities) == 14
    assert (
        sum(
            len(decode(assets[asset_name(c["registry_asset"])])["collection_areas"])
            for c in cities
        )
        == 706
    )
    assert all(p.suffix == ".json" for p in output.iterdir())
    assert "publication" not in manifest  # Do not distribute the operator record.


@pytest.fixture
def lambda_event_loop():
    # Other tests use asyncio.run(), which clears the implicit main-thread loop.
    # Lambda's synchronous adapter needs its own loop for this simulated runtime.
    with asyncio.Runner() as runner:
        yield runner.get_loop()


def test_api_gateway_lambda_proxy_can_export_all_municipalities(
    monkeypatch, lambda_event_loop
):
    public_environment(monkeypatch)

    def invoke(path, query=None):
        return handler(
            {
                "version": "2.0",
                "routeKey": "$default",
                "rawPath": path,
                "rawQueryString": urlencode(query or {}),
                "headers": {"host": "example.test", "x-forwarded-proto": "https"},
                "requestContext": {
                    "http": {"method": "GET", "path": path, "sourceIp": "198.51.100.1"}
                },
                "body": None,
                "isBase64Encoded": False,
            },
            None,
        )

    response = invoke("/api/frontend-data/manifest")
    assert response["statusCode"] == 200
    manifest = json.loads(response["body"])
    for city in manifest["catalog"]["municipalities"]:
        response = invoke(
            "/api/frontend-data/municipalities/" + city["id"],
            {"version": manifest["dataset_version"]},
        )
        assert response["statusCode"] == 200, (city["id"], response)
        bundle = json.loads(response["body"])
        assert bundle["municipality_id"] == city["id"]
        assert bundle["dataset_version"] == manifest["dataset_version"]
