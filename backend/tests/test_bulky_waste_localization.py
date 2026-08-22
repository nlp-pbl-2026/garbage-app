"""Tests for bulky waste endpoint localization (Task 5.4).

Verifies that:
- Endpoints return localized item_name and notes when translations exist
- Endpoints fall back to Japanese when no translation exists
- Error messages are returned in the resolved request language
"""

import sys
import os
from pathlib import Path

# Ensure backend app is importable
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import BulkyWasteItem, BulkyWasteItemTranslation, MunicipalityConfig


# In-memory test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    """Create test database tables and return a session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session):
    """Create test client with overridden DB dependency."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_data(db_session):
    """Insert sample municipality config and bulky waste items."""
    config = MunicipalityConfig(
        municipality_id="38201",
        municipality_name="松山市",
        collection_frequency="月2回",
        reception_hours="8:30-17:00",
        collection_rules="事前申込が必要",
        fee_structure_type="size_based",
        application_method="both",
        web_form_url="https://example.com",
        phone_number="089-000-0000",
        steps=[{"step_number": 1, "title": "申込", "description": "電話で申し込む"}],
    )
    db_session.add(config)

    item1 = BulkyWasteItem(
        id=1,
        municipality_id="38201",
        item_name="ソファ",
        item_name_kana="そふぁ",
        category="家具",
        fee_amount=1000,
        notes="3人掛け以上は追加料金",
    )
    item2 = BulkyWasteItem(
        id=2,
        municipality_id="38201",
        item_name="自転車",
        item_name_kana="じてんしゃ",
        category="乗り物",
        fee_amount=500,
        notes=None,
    )
    db_session.add_all([item1, item2])

    # Add English translation for item1 only
    translation_en = BulkyWasteItemTranslation(
        bulky_waste_item_id=1,
        language_code="en",
        item_name="Sofa",
        notes="Additional fee for 3-seater or larger",
    )
    db_session.add(translation_en)

    # Add partial translation for item2 (item_name only, no notes)
    translation_en_item2 = BulkyWasteItemTranslation(
        bulky_waste_item_id=2,
        language_code="en",
        item_name="Bicycle",
        notes=None,
    )
    db_session.add(translation_en_item2)

    await db_session.commit()


class TestBulkyWasteLocalization:
    """Test localized content returned by bulky waste endpoints."""

    @pytest.mark.asyncio
    async def test_items_returned_in_english(self, client, sample_data):
        """When Accept-Language is 'en', translated item_name/notes should be returned."""
        response = await client.get(
            "/api/bulky-waste/items/38201",
            headers={"Accept-Language": "en"},
        )
        assert response.status_code == 200
        data = response.json()
        items = data["items"]

        # Item 1 has full translation
        sofa = next(i for i in items if i["id"] == 1)
        assert sofa["item_name"] == "Sofa"
        assert sofa["notes"] == "Additional fee for 3-seater or larger"

        # Item 2 has item_name translation but no notes → fallback to Japanese (None)
        bicycle = next(i for i in items if i["id"] == 2)
        assert bicycle["item_name"] == "Bicycle"
        assert bicycle["notes"] is None  # Original is None, stays None

    @pytest.mark.asyncio
    async def test_items_returned_in_japanese_by_default(self, client, sample_data):
        """Without Accept-Language header, items are returned in Japanese."""
        response = await client.get("/api/bulky-waste/items/38201")
        assert response.status_code == 200
        data = response.json()
        items = data["items"]

        sofa = next(i for i in items if i["id"] == 1)
        assert sofa["item_name"] == "ソファ"
        assert sofa["notes"] == "3人掛け以上は追加料金"

    @pytest.mark.asyncio
    async def test_items_fallback_to_japanese_for_unsupported_language(self, client, sample_data):
        """When Accept-Language is unsupported (e.g., 'fr'), fallback to Japanese."""
        response = await client.get(
            "/api/bulky-waste/items/38201",
            headers={"Accept-Language": "fr"},
        )
        assert response.status_code == 200
        data = response.json()
        items = data["items"]

        sofa = next(i for i in items if i["id"] == 1)
        assert sofa["item_name"] == "ソファ"
        assert sofa["notes"] == "3人掛け以上は追加料金"

    @pytest.mark.asyncio
    async def test_item_detail_localized(self, client, sample_data):
        """Item detail endpoint returns localized content."""
        response = await client.get(
            "/api/bulky-waste/items/38201/1",
            headers={"Accept-Language": "en"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["item_name"] == "Sofa"
        assert data["notes"] == "Additional fee for 3-seater or larger"

    @pytest.mark.asyncio
    async def test_item_detail_japanese_when_ja(self, client, sample_data):
        """Item detail in Japanese skips translation lookup."""
        response = await client.get(
            "/api/bulky-waste/items/38201/1",
            headers={"Accept-Language": "ja"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["item_name"] == "ソファ"
        assert data["notes"] == "3人掛け以上は追加料金"

    @pytest.mark.asyncio
    async def test_regional_variant_resolves_to_base(self, client, sample_data):
        """Accept-Language 'en-US' resolves to 'en' and returns English translations."""
        response = await client.get(
            "/api/bulky-waste/items/38201/1",
            headers={"Accept-Language": "en-US"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["item_name"] == "Sofa"


class TestBulkyWasteErrorMessages:
    """Test that error messages are returned in the resolved language."""

    @pytest.mark.asyncio
    async def test_404_error_in_english(self, client, sample_data):
        """404 error for missing municipality is in English when Accept-Language is 'en'."""
        response = await client.get(
            "/api/bulky-waste/items/99999",
            headers={"Accept-Language": "en"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "The specified municipality was not found"

    @pytest.mark.asyncio
    async def test_404_error_in_japanese_default(self, client, sample_data):
        """404 error defaults to Japanese without Accept-Language header."""
        response = await client.get("/api/bulky-waste/items/99999")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "指定された自治体が見つかりません"

    @pytest.mark.asyncio
    async def test_404_item_error_in_english(self, client, sample_data):
        """404 error for missing item is in English."""
        response = await client.get(
            "/api/bulky-waste/items/38201/999",
            headers={"Accept-Language": "en"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "The specified item was not found"

    @pytest.mark.asyncio
    async def test_404_item_error_in_portuguese(self, client, sample_data):
        """404 error for missing item is in Portuguese."""
        response = await client.get(
            "/api/bulky-waste/items/38201/999",
            headers={"Accept-Language": "pt"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "O item especificado não foi encontrado"

    @pytest.mark.asyncio
    async def test_config_404_error_in_chinese(self, client, sample_data):
        """404 for config endpoint is in Chinese."""
        response = await client.get(
            "/api/bulky-waste/config/99999",
            headers={"Accept-Language": "zh"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "未找到指定的市区町村"

    @pytest.mark.asyncio
    async def test_config_404_error_in_vietnamese(self, client, sample_data):
        """404 for config endpoint is in Vietnamese."""
        response = await client.get(
            "/api/bulky-waste/config/99999",
            headers={"Accept-Language": "vi"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Không tìm thấy thành phố được chỉ định"
