"""Synthetic Ikata pipeline regressions: no official data, network or Bedrock."""
from io import BytesIO
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
import ikata_data
from ikata_pdf import raster_types


@pytest.mark.parametrize('note,primary,expected', [
    ('指定袋に入らないものは粗大', 'landfill', ['bulky']),
    ('指定袋に入るものは埋立', 'bulky', ['landfill']),
    ('指定袋に入れば可燃', 'bulky', ['burnable']),
    ('使い切り、すすいで汚れの落ちないものは埋立', 'plastic_packaging', ['landfill']),
    ('汚れの落ちないものは可燃', 'styrofoam', ['burnable']),
    ('白色以外のものはプラ', 'styrofoam', ['plastic_packaging']),
    ('LEDは埋立', 'hazardous', ['landfill']),
    ('農業・漁業用は、産業廃棄物', 'bulky', ['not_collected']),
    ('金具は外して埋立', 'burnable', []),
    ('金属部分は埋立', 'burnable', []),
    ('アルミ箔は可燃', 'paper_textiles', []),
    ('電池は外して', 'landfill', []),
])
def test_only_explicit_item_conditions_authorize_category_changes(note, primary, expected):
    assert ikata_data.classification_options(note, primary) == expected


def test_raster_detects_simultaneous_streams_and_blank_dates_independently():
    palette = {'first': np.array([255, 230, 180]), 'second': np.array([210, 240, 200])}
    pixels = np.full((20, 50, 3), 255)
    assert raster_types(pixels, palette) == set()
    pixels[:10] = palette['first']; pixels[10:] = palette['second']
    assert raster_types(pixels, palette) == {'first', 'second'}
    with pytest.raises(ValueError, match='Empty raster'):
        raster_types(np.empty((0, 0, 3)), palette)


def test_changed_download_never_overwrites_reviewed_original(tmp_path, monkeypatch):
    monkeypatch.setattr(ikata_data, 'DATA', tmp_path)
    target = tmp_path/'source/one.pdf'; target.parent.mkdir(); target.write_bytes(b'original')
    (tmp_path/'sources.json').write_text(json.dumps({'sources': [{
        'file': 'one.pdf', 'url': 'https://www.town.ikata.ehime.jp/uploaded/attachment/one.pdf',
        'sha256': ikata_data.digest(target)}]}))
    monkeypatch.setattr(ikata_data, 'urlopen', lambda *args, **kwargs: BytesIO(b'changed'))
    with pytest.raises(ValueError, match='review required'):
        ikata_data.fetch()
    assert target.read_bytes() == b'original'


def test_missing_index_prevents_registration_and_preserves_existing_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(ikata_data, 'ROOT', tmp_path)
    catalog = tmp_path/'data/regions/catalog.json'; catalog.parent.mkdir(parents=True)
    original = b'{"municipalities":[{"id":"existing","registry_path":"existing/registry.json"}]}'
    catalog.write_bytes(original)
    def unavailable():
        raise ValueError('Missing verified Ikata index')
    monkeypatch.setattr(ikata_data, 'verify', unavailable)
    with pytest.raises(ValueError, match='Missing verified'):
        ikata_data.activate()
    assert catalog.read_bytes() == original


def test_review_mismatch_stops_before_runtime_data_are_written(tmp_path, monkeypatch):
    monkeypatch.setattr(ikata_data, 'DATA', tmp_path)
    monkeypatch.setattr(ikata_data, 'inspect_calendars', lambda: ([], {}, {'a': {'days_sha256': 'changed'}}))
    monkeypatch.setattr(ikata_data, 'item_rows', lambda: ([], {}))
    (tmp_path/'calendar_reviews.json').write_text('{}')
    (tmp_path/'item_reviews.json').write_text('{}')
    with pytest.raises(ValueError, match='review required'):
        ikata_data.build()
    assert not (tmp_path/'registry.json').exists()
    assert not (tmp_path/'generated/calendar-2026.json').exists()
