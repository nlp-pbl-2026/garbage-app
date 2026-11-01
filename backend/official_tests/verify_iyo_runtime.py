"""Explicit local-data integration; no network, Bedrock or persistent DB writes.

Run separately after the documented generators and index placement, not as part
of ordinary synthetic unit tests. The filename is deliberately outside pytest's
test_*.py discovery pattern: pytest backend/official_tests/verify_iyo_runtime.py
"""
from datetime import date, datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from app.main import app
from app.services.region_registry_service import get_registry
from app.services.calendar_service import CalendarService


def test_iyo_all_areas_versions_streams_cutoffs_and_existing_city_isolation():
    catalog = get_registry()
    registry = catalog.registry('38210')
    assert len(registry.areas) == 16
    for area in registry.areas.values():
        assert len(area['id']) <= 20  # item-list API's district_id contract
        context = catalog.resolve('38210',area['id'])
        assert context.version == 'iyo-2026.1'
        assert 'iyo' in str(context.rules.items_path)
        assert 'iyo' in str(context.rules.embedding_index_path)
        calendar = CalendarService(region=context)
        assert calendar.availability in ('available','partially_available')
        assert all(d.cutoff.hour==8 and d.cutoff.minute==30 for d in context.rules.categories.values() if d.collection_type_id)
    assert catalog.resolve('38201','38201-08').version != registry.data['version']
    assert catalog.resolve('38204','38204-01').version != registry.data['version']


def test_iyo_unknown_cutoff_holidays_exception_and_fifth_monday():
    catalog = get_registry()
    calendar = CalendarService(region=catalog.resolve('38210','38210-iyo-central'))
    before = datetime(2026,11,2,8,29,tzinfo=ZoneInfo('Asia/Tokyo'))
    assert calendar.next_collection('burnable',at=before).date == date(2026,11,2)
    assert calendar.next_collection('burnable',at=before.replace(minute=30)).date == date(2026,11,6)
    assert calendar.next_collection('burnable',from_date=date(2027,4,1)) is None
    assert calendar.collection_status('bulky').status == 'not_scheduled'
    partial = CalendarService(region=catalog.resolve('38210','38210-iyo-hiraoka'))
    for code in ['paper','bottles','pet_bottles','non_burnable','hazardous']:
        assert partial.next_collection(code,from_date=date(2026,11,1)) is None
        assert partial.collection_status(code).status == 'unverified'
    bundle = json.loads((ROOT/'data/regions/iyo/generated/calendar-2026.json').read_text())
    days = bundle['calendars']['iy-nakayama-sare']['days']
    assert days['2026-08-24'] == ['paper']
    assert days['2026-08-31'] == []
    assert 'plastic_packaging' in days['2026-12-29']
    assert days['2026-12-30'] == ['burnable']
    assert days['2027-01-01'] == []


@pytest.mark.asyncio
async def test_all_area_bulky_item_apis_and_unsupported_region():
    # ASGITransport without lifespan does not initialize/change the user's DB.
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://local') as client:
        for area in get_registry().registry('38210').areas.values():
            response = await client.get('/api/search/items/38210',params={'district_id':area['id'],'category':'bulky'})
            assert response.status_code==200,response.text
            body=response.json()
            assert body['municipality_name']=='伊予市'
            # The existing list API includes conditionally bulky items as well
            # as 309 fixed-category entries; it retains each item's base label
            # and conditions rather than presenting all 585 as unconditional.
            assert body['total_count']==585
            assert sum(row['category']=='粗大ごみ' for row in body['items'])==309
            assert any('袋' in (row.get('notes') or '') for row in body['items'])
        response=await client.get('/api/search/items/38210',params={'district_id':'38201-08','category':'bulky'})
        assert response.status_code==422
        response=await client.get('/api/search/items/unknown',params={'district_id':'38210-iyo-central','category':'bulky'})
        assert response.status_code==404


def test_frontend_and_backend_use_identical_calendar_and_guide_regions():
    source=ROOT/'data/regions/iyo/generated/calendar-2026.json'
    frontend=ROOT/'frontend/assets/data'
    assert (frontend/'municipality_38210_0_calendar.json').read_bytes()==source.read_bytes()
    catalog=json.loads((frontend/'municipality_catalog.json').read_text())
    city=next(c for c in catalog['municipalities'] if c['id']=='38210')
    assert city['version']=='iyo-2026.1'
    for profile in ['iyo','futami','nakayama']:
        config=city['profiles'][profile]['bulky_waste']['config']
        assert config['municipality_id']=='38210'
        assert config['information_url'].startswith('https://www.city.iyo.lg.jp/')
    assert '14日' in city['profiles']['futami']['bulky_waste']['config']['reception_hours']
    assert '28日' in city['profiles']['nakayama']['bulky_waste']['config']['reception_hours']
