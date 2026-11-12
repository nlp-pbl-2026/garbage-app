"""Explicit local integration tests. All official datasets must be installed."""

import asyncio
from pathlib import Path
import sys

from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.main import app
from app.services.region_registry_service import get_registry
from verify_municipality_data import verify


def test_all_twenty_municipalities_have_isolated_verified_runtime_data():
    report = verify()
    assert report["municipalities"] == 20
    assert report["indices"] == 21  # Imabari mainland/Sekizen; Matsuyama shares one.
    assert report["areas"] == 706
    assert report["api_calls"] == 0


def test_every_profile_items_api_is_local_and_rejects_cross_city_districts():
    async def run():
        catalog = get_registry()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for city_id in catalog.entries:
                registry = catalog.registry(city_id)
                for profile_id, profile in registry.profiles.items():
                    area = next(
                        a
                        for a in registry.areas.values()
                        if a["rule_profile_id"] == profile_id
                    )
                    response = await client.get(
                        f"/api/search/items/{city_id}",
                        params={
                            "district_id": area["id"],
                            "category": next(iter(profile.categories)),
                        },
                    )
                    assert response.status_code == 200, (
                        city_id,
                        profile_id,
                        response.text,
                    )
                    assert response.json()["municipality_name"].startswith(
                        registry.data["municipality_name"]
                    )
                other_id = next(
                    identifier
                    for identifier in catalog.entries
                    if identifier != city_id
                )
                other = next(iter(catalog.registry(other_id).areas))
                response = await client.get(
                    f"/api/search/items/{city_id}", params={"district_id": other}
                )
                assert response.status_code == 422
            assert (await client.get("/api/search/items/99999")).status_code == 404

    asyncio.run(run())
