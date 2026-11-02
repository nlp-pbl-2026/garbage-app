"""Explicit local-data integration; no network, Bedrock or persistent DB writes.

Run separately after the documented generators and index placement, not as part
of ordinary synthetic unit tests. The filename is deliberately outside pytest's
test_*.py discovery pattern: pytest backend/official_tests/verify_iyo_runtime.py
"""
from datetime import date, datetime
import csv
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))
from app.main import app
from app.services.region_registry_service import get_registry
from app.services.calendar_service import CalendarService
from app.services.item_search_service import ItemMatch
from app.services.waste_guide_service import ClassificationDecision, WasteGuideService


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


@pytest.mark.asyncio
@pytest.mark.parametrize('code', ['bottles','pet_bottles','non_burnable','hazardous','paper',
                                 'burnable','plastic_packaging','textiles','cans'])
async def test_partial_area_api_only_warns_for_the_five_unverified_types(code):
    """Stub the paid classifier, but use real CSV evidence, calendar and API."""
    region=get_registry().resolve('38210','38210-iyo-hiraoka')
    with region.rules.items_path.open(encoding='utf-8',newline='') as stream:
        rows=[r for r in csv.DictReader(stream) if r['category']==code]
        row=min(rows,key=lambda r:len(r['note']))
    item=ItemMatch(item_id=row['item_id'],item=row['item'],category=code,
        category_display=row['category_display'],note=row['note'],score=.99,
        disposal_instructions=row['disposal_instructions'],category_options=tuple(json.loads(row['category_options'])))

    class LocalClassifier:
        def classify(self,*args,**kwargs):
            return ClassificationDecision(True,item.item,code,item.disposal_instructions,.99,
                                          evidence_indexes=(1,))

    service=WasteGuideService(gateway=LocalClassifier(),
        now_provider=lambda: datetime(2026,11,2,8,15,tzinfo=ZoneInfo('Asia/Tokyo')))
    # Confirm the packaging condition rather than testing a missing mark here.
    query=item.item+('（プラマーク付き）' if code=='plastic_packaging' else '')
    with patch('app.routers.search_router.WasteGuideService',return_value=service),patch('app.routers.search_router.SearchLogService'):
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://local') as client:
            response=await client.post('/api/search/decide',json={
                'municipality_id':'38210','district_id':region.area_id,
                'query':query,'rewritten_query':query,
                'documents':[{'snippet':item.evidence_text,'score':.99,'uri':region.evidence_prefix+'items/'+item.item_id}]})
    assert response.status_code==200,response.text
    body=response.json()
    assert body['status']=='answered',body
    assert body['classification']['category_code']==code
    if code in {'bottles','pet_bottles','non_burnable','hazardous','paper'}:
        assert body['next_collection'] is None
        assert body['collection_status']['status']=='unverified'
        assert '未確認' in body['answer']
        assert body['collection_status']['source_url'].endswith('/r8iyo.pdf')
    else:
        assert body['next_collection'] is not None
        assert body['collection_status']['status']=='scheduled'
        assert '未確認' not in body['answer']


@pytest.mark.asyncio
async def test_material_answer_and_rewrite_cannot_invent_inability_to_carry_furniture():
    """Replay the live failure with a stub model; actual Iyo evidence and API."""
    region=get_registry().resolve('38210','38210-iyo-central')
    with region.rules.items_path.open(encoding='utf-8',newline='') as stream:
        row=next(r for r in csv.DictReader(stream) if r['item_id']=='iy-rule-heavy-furniture')
    item=ItemMatch(item_id=row['item_id'],item=row['item'],category=row['category'],
        category_display=row['category_display'],note=row['note'],score=.99,
        category_options=tuple(json.loads(row['category_options'])))

    class WrongModel:
        def classify(self,*args,**kwargs):
            return ClassificationDecision(True,'大きな壊れた家具','not_collected',
                                          '1人で運べないため収集不可',.99,evidence_indexes=(1,))

    service=WasteGuideService(gateway=WrongModel())
    with patch('app.routers.search_router.WasteGuideService',return_value=service),patch('app.routers.search_router.SearchLogService'):
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://local') as client:
            response=await client.post('/api/search/decide',json={
                'municipality_id':'38210','district_id':region.area_id,
                'query':'大きな壊れた家具',
                'clarifications':[{'question':'素材は何ですか？','answer':'木材'}],
                'rewritten_query':'大人1人で持ち運べない木製家具',
                'documents':[{'snippet':item.evidence_text,'score':.99,'uri':region.evidence_prefix+'items/'+item.item_id}]})
    assert response.status_code==200,response.text
    body=response.json()
    assert body['status']=='needs_clarification'
    assert body['classification'] is None
    assert body['next_collection'] is None
    assert body['follow_up_question']=='大人1人で持ち運べる重さ・大きさですか？'
