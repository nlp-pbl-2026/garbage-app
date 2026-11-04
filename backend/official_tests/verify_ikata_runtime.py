"""Explicit reviewed-data/API checks; no network, paid inference or DB writes."""
import csv
from datetime import date, datetime
import json
from pathlib import Path
import sys
from unittest.mock import patch
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'backend'))

from app.main import app
from app.services.calendar_service import CalendarService
from app.services.embedding_search_service import EmbeddingSearchService
from app.services.item_search_service import ItemMatch
from app.services.region_registry_service import get_registry, RegionResolutionError
from app.services.waste_guide_service import ClassificationDecision, RetrievedDocument, WasteGuideService

CITY = '38442'


def test_all_areas_catalog_profiles_and_calendar_assets_are_isolated():
    catalog = get_registry(); registry = catalog.registry(CITY)
    assert {'38201', '38204', '38210', CITY} <= set(catalog.entries)
    assert len(registry.areas) == 8 and len(registry.calendars) == 8
    assert set(registry.profiles) == {'ikata', 'seto', 'misaki'}
    backend = ROOT/'data/regions/ikata/generated/calendar-2026.json'
    frontend = ROOT/'frontend/assets/data/municipality_38442_0_calendar.json'
    assert backend.read_bytes() == frontend.read_bytes()
    for area in registry.areas.values():
        assert len(area['id']) <= 20
        assert not any(s in area['display_name'] for s in ('曜', 'A-', 'B-', 'C-', '未確認'))
        region = catalog.resolve(CITY, area['id'])
        assert region.version == 'ikata-2026.1'
        assert region.rules.index_profile_id == 'townwide'
        assert 'ikata/knowledge' in str(region.rules.items_path)
        assert 'ikata/knowledge' in str(region.rules.embedding_index_path)
        assert CalendarService(region=region).availability == 'available'
        for definition in region.rules.categories.values():
            if definition.collection_type_id:
                assert definition.cutoff.hour == 8 and definition.cutoff.minute == 0
        for code in ('bulky', 'not_collected'):
            cal = CalendarService(region=region)
            assert cal.collection_status(code).status == 'not_scheduled'
            assert cal.next_collection(code, from_date=date(2026, 4, 1)) is None
    for city, district in [('38201', '38201-08'), ('38204', '38204-01'), ('38210', '38210-iyo-central')]:
        region = catalog.resolve(city, district)
        assert region.version != 'ikata-2026.1'
        with pytest.raises(RegionResolutionError):
            catalog.resolve(CITY, district)


def test_printed_year_end_weekends_holidays_and_cutoff():
    registry = get_registry().registry(CITY)
    raw = json.loads((ROOT/'data/regions/ikata/generated/calendar-2026.json').read_text())
    # Explicit observations from the eight PDF grids, not a recurrence formula.
    assert raw['calendars']['ik-c-1']['days']['2026-04-04'] == ['burnable']
    assert raw['calendars']['ik-c-1']['days']['2026-04-05'] == []
    assert raw['calendars']['ik-a-1']['days']['2026-05-05'] == ['landfill']
    assert raw['calendars']['ik-a-1']['days']['2026-12-31'] == ['burnable']
    assert raw['calendars']['ik-b-1']['days']['2026-12-29'] == ['burnable']
    assert raw['calendars']['ik-b-1']['days']['2026-12-30'] == []
    assert raw['calendars']['ik-c-1']['days']['2026-12-30'] == ['burnable']
    assert raw['calendars']['ik-c-1']['days']['2026-12-31'] == []
    for area in registry.areas.values():
        days = raw['calendars'][area['calendar_id']]['days']
        assert len(days) == 365
        for key in ('2027-01-01', '2027-01-02', '2027-01-03'):
            assert days[key] == []
        cal = CalendarService(region=registry.resolve(CITY, area['id']))
        assert cal.next_collection('burnable', from_date=date(2027, 4, 1)) is None
    cal = CalendarService(region=registry.resolve(CITY, '38442-01'))
    before = datetime(2026, 11, 2, 7, 59, tzinfo=ZoneInfo('Asia/Tokyo'))
    assert cal.next_collection('burnable', at=before).date == date(2026, 11, 2)
    assert cal.next_collection('burnable', at=before.replace(hour=8, minute=0)).date == date(2026, 11, 5)
    # Identically named 高浦 belongs to two explicitly different regional lists.
    assert '瀬戸地域' in registry.areas['38442-05']['display_name']
    assert '三崎地域' in registry.areas['38442-07']['display_name']
    assert raw['calendars']['ik-b-2']['days']['2026-04-13'] == ['paper_textiles']
    assert raw['calendars']['ik-b-3']['days']['2026-04-20'] == ['paper_textiles']


def test_dictionary_manifest_and_corrected_battery_are_a_verified_pair():
    region = get_registry().resolve(CITY, '38442-01')
    with region.rules.items_path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1207
    dictionary = [r for r in rows if r['item_id'].startswith('ik-p')]
    assert len(dictionary) == 1196
    battery = next(r for r in dictionary if r['item'] == '乾電池（ボタン型・充電式）')
    assert battery['category'] == 'not_collected' and battery['source_category'] == '有害'
    assert battery['source_url'].endswith('10412.pdf')
    assert '14・49ページ' in battery['note']
    bath = next(r for r in dictionary if r['item'] == '入浴剤の容器（プラスチック製）')
    assert bath['category'] == 'plastic_packaging'
    search = EmbeddingSearchService(items_path=region.rules.items_path, embeddings_path=region.rules.embedding_index_path,
                                    municipality_id=CITY, profile_id='townwide', runtime_client=object())
    assert search.is_ready
    with np.load(region.rules.embedding_index_path, allow_pickle=False) as index:
        assert list(map(str, index['item_ids'])) == [r['item_id'] for r in rows]
        assert index['vectors'].shape == (1207, 1024)
    for row in rows:
        assert row['category'] in region.category_codes
        assert set(json.loads(row['category_options'])) <= set(region.category_codes)


@pytest.mark.asyncio
@pytest.mark.parametrize('code', ['burnable', 'landfill', 'bottles', 'cans', 'pet_bottles',
    'plastic_packaging', 'styrofoam', 'paper_textiles', 'hazardous', 'bulky', 'not_collected'])
async def test_each_category_api_uses_ikata_dates_and_never_schedules_application_or_prohibited_items(code):
    region = get_registry().resolve(CITY, '38442-01')
    with region.rules.items_path.open(encoding='utf-8', newline='') as stream:
        row = min((r for r in csv.DictReader(stream) if r['category'] == code and r['category_options'] == '[]'),
                  key=lambda r: len(r['note']))
    match = ItemMatch(item_id=row['item_id'], item=row['item'], category=code,
        category_display=row['category_display'], note=row['note'], score=.99,
        disposal_instructions=row['disposal_instructions'])
    class LocalClassifier:
        def classify(self, *args, **kwargs):
            return ClassificationDecision(True, match.item, code, match.disposal_instructions, .99, evidence_indexes=(1,))
    now = datetime(2026, 11, 3, 7, 0, tzinfo=ZoneInfo('Asia/Tokyo'))
    service = WasteGuideService(gateway=LocalClassifier(), now_provider=lambda: now)
    query = match.item+('（プラマーク付き）' if code == 'plastic_packaging' else '')
    with patch('app.routers.search_router.WasteGuideService', return_value=service), patch('app.routers.search_router.SearchLogService'):
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://local') as client:
            response = await client.post('/api/search/decide', json={'municipality_id': CITY, 'district_id': region.area_id,
                'query': query, 'rewritten_query': query, 'documents': [{'snippet': match.evidence_text,
                    'score': .99, 'uri': region.evidence_prefix+'items/'+match.item_id}]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['status'] == 'answered', body
    assert body['classification']['category_code'] == code
    if code in ('bulky', 'not_collected'):
        assert body['next_collection'] is None
        assert body['collection_status']['status'] == 'not_scheduled'
        if code == 'bulky': assert '申込' in body['answer']
    else:
        assert body['next_collection']['date'] == CalendarService(region=region).next_collection(code, at=now).date.isoformat()
        assert body['collection_status']['status'] == 'scheduled'


@pytest.mark.asyncio
async def test_bulky_list_for_all_areas_and_mismatched_district_fail_closed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://local') as client:
        for area in get_registry().registry(CITY).areas.values():
            response = await client.get('/api/search/items/'+CITY, params={'district_id': area['id'], 'category': 'bulky'})
            assert response.status_code == 200, response.text
            body = response.json()
            assert body['municipality_name'] == '伊方町'
            assert body['total_count'] > 180  # Includes explicitly conditional rows.
        bad = await client.get('/api/search/items/'+CITY, params={'district_id': '38201-08', 'category': 'bulky'})
        assert bad.status_code == 422


def test_unknown_bucket_size_cannot_be_invented_by_rewrite_or_model():
    region = get_registry().resolve(CITY, '38442-01')
    with region.rules.items_path.open(encoding='utf-8', newline='') as stream:
        row = next(r for r in csv.DictReader(stream) if r['item_id'] == 'ik-rule-plastic-bucket')
    match = ItemMatch(item_id=row['item_id'], item=row['item'], category=row['category'],
        category_display=row['category_display'], note=row['note'], score=.99,
        category_options=tuple(json.loads(row['category_options'])))
    class WrongClassifier:
        def classify(self, *args, **kwargs):
            return ClassificationDecision(True, 'バケツ', 'bulky', '袋に入らない', .99, evidence_indexes=(1,))
    result = WasteGuideService(gateway=WrongClassifier()).decide(query='壊れたプラスチック製バケツ',
        rewritten_query='袋に入らない大型のバケツ', municipality_id=CITY, district_id='38442-01',
        clarifications=[], documents=[RetrievedDocument(
            text=match.evidence_text, score=.99, uri=region.evidence_prefix+'items/'+match.item_id)])
    assert result.status == 'needs_clarification'
    assert not result.decision.is_resolved and result.next_collection is None
    assert '袋' in result.follow_up_question
