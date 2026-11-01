"""Synthetic parsing/area-filter tests: no official files, network or Bedrock."""
import importlib.util
import json
from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import yawatahama_data as data
from yawatahama_pdf import layout, extract


def test_item_cells_preserve_conditional_categories_notes_and_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(data, 'DATA', tmp_path)
    (tmp_path / 'source').mkdir()
    rules = {'categories': {
        'burnable': {'name': '燃やすごみ'}, 'non_burnable': {'name': '燃やさないごみ'},
        'bulky': {'name': '粗大ごみ'},
    }, 'examples': []}
    (tmp_path / 'official_rules.json').write_text(json.dumps(rules))
    header = '<tr><th></th><th>名前</th><th>分別</th><th>持込制限</th><th>説明１</th><th>説明２</th></tr>'
    row = '<tr><td>あ</td><td>試験いす</td><td>素材で判断</td><td>※</td><td>木製は可燃ごみ</td><td>袋に入らないものは粗大ごみ</td></tr>'
    (tmp_path / 'source/items-a.html').write_text('<table>'+header+row+'</table>')
    (tmp_path / 'source/items-b.html').write_text('<table>'+header+'</table>')
    records = data.item_rows()
    assert len(records) == 1
    assert records[0]['category'] == ''
    assert records[0]['source_category'] == '素材で判断'
    assert json.loads(records[0]['category_options']) == ['bulky', 'burnable']
    assert '木製は可燃ごみ' in records[0]['note']
    assert '袋に入らないものは粗大ごみ' in records[0]['note']
    assert '※' in records[0]['note']


def test_paper_day_filters_never_duplicate_both_addresses_collection_dates():
    days = {'2026-11-03': ['burnable', 'newspaper'], '2026-11-06': ['burnable', 'newspaper']}
    config = {'paper_collection_types': ['newspaper'], 'variants': {'13': [
        {'suffix': 'tu', 'paper_weekday_iso': 2}, {'suffix': 'fr', 'paper_weekday_iso': 5}]}}
    first, second = data.area_variants(13, days, [], config)
    assert first['days']['2026-11-03'] == ['burnable', 'newspaper']
    assert first['days']['2026-11-06'] == ['burnable']
    assert second['days']['2026-11-03'] == ['burnable']
    assert second['days']['2026-11-06'] == ['burnable', 'newspaper']
    assert days['2026-11-03'] == ['burnable', 'newspaper']
    days['2026-11-04'] = ['newspaper']
    with pytest.raises(ValueError, match='contradicts'):
        data.area_variants(13, days, [], config)


def test_sixth_week_dates_use_opposite_triangles_of_the_shared_cell():
    x, y, shared, last = layout(date(2026, 8, 24))
    x2, y2, shared2, last2 = layout(date(2026, 8, 31))
    assert (x, y) == (x2, y2)
    assert shared and shared2
    assert not last and last2


def test_unknown_pdf_layout_is_rejected_before_date_generation():
    with pytest.raises(ValueError, match='geometry'):
        extract(SimpleNamespace(rect=SimpleNamespace(width=595, height=842)))


def test_catalog_cannot_escape_municipality_directory(tmp_path):
    from app.services.region_registry_service import MunicipalityCatalog, RegionalDataError
    path = tmp_path / 'catalog.json'
    path.write_text(json.dumps({'municipalities': [{'id': '90001', 'registry_path': '../registry.json'}]}))
    with pytest.raises(RegionalDataError):
        MunicipalityCatalog(path)


def test_partial_address_uses_non_paper_dates_without_selecting_a_paper_weekday():
    days = {'2026-11-03': ['burnable', 'newspaper'], '2026-11-06': ['burnable', 'paper_packaging']}
    papers = ['newspaper', 'paper_packaging']
    config = {'paper_collection_types': papers, 'variants': {'13': [
        {'suffix': 'tu', 'paper_weekday_iso': 2}, {'suffix': 'fr', 'paper_weekday_iso': 5},
        {'suffix': 'go', 'unverified_collection_types': papers}]}}
    first, second, partial = data.area_variants(13, days, [], config)
    assert partial['days'] == {'2026-11-03': ['burnable'], '2026-11-06': ['burnable']}
    assert 'paper_weekday_iso' not in partial
    assert first['days']['2026-11-03'] == ['burnable', 'newspaper']
    assert second['days']['2026-11-06'] == ['burnable', 'paper_packaging']
