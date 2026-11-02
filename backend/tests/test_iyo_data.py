"""Synthetic evidence: unit tests need neither official files nor AWS."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
import iyo_data
from iyo_pdf import observed_types


def observation(*fills, text='', top=()):
    return {'fills': list(fills), 'text': text, 'top_colors': set(top)}


def test_nonburnable_split_band_keeps_simultaneous_types_and_area_weekday():
    area = {'rule_profile_id':'iyo','burnable_weekdays':[1,5], 'plastic_weekday':3,'nonburnable_weekday':2}
    ob = observation(((.815,.848,.456),'布類'),((.915,.648,.710),'かん類'))
    assert observed_types(ob,'2026-04-14',area) == ['cans','textiles']
    assert observed_types(ob,'2026-04-15',area) == []


def test_partial_area_never_assigns_unknown_types_or_second_cans_date():
    area = {'rule_profile_id':'iyo','burnable_weekdays':[1,5], 'plastic_weekday':3,'nonburnable_weekday':2,
            'unverified_collection_types':['bottles','paper','pet_bottles','non_burnable','hazardous']}
    assert observed_types(observation(((.929,.733,.356),'びん類')),'2026-04-07',area) == []
    assert observed_types(observation(((.915,.648,.710),'かん類')),'2026-04-28',area) == []
    assert observed_types(observation(top=[(.984,.970,.864)]),'2026-04-06',area) == ['burnable']


def test_futami_letters_and_upper_lower_resource_collections_are_isolated():
    area = {'rule_profile_id':'futami','official_group':'F','burnable_weekdays':[2,6],
            'plastic_weekday':4,'subregion':'lower'}
    ob = observation(((.743,.637,.458),'F'),text='F')
    assert observed_types(ob,'2026-04-08',area) == ['bottles','cans','hazardous','non_burnable']
    assert observed_types(observation(text='布・紙類（上灘）'),'2026-04-11',area) == []
    assert observed_types(observation(text='布・紙類（下灘）'),'2026-04-04',area) == ['paper','textiles']


def test_nakayama_cell_text_is_used_instead_of_text_of_merged_rectangle():
    area = {'rule_profile_id':'nakayama','official_group':'sare'}
    # One blue PDF rectangle spans neighboring Monday/Tuesday cells. Its entire
    # text is not evidence that Tuesday also collects PET/textiles.
    ob = observation(((.713,.848,.921),'ペットボトル布類プラスチック製容器包装'),text='プラスチック製容器包装')
    assert observed_types(ob,'2026-12-08',area) == ['plastic_packaging']


def test_changed_official_source_fails_before_build(tmp_path,monkeypatch):
    monkeypatch.setattr(iyo_data,'DATA',tmp_path)
    (tmp_path/'source').mkdir()
    (tmp_path/'source/test.pdf').write_bytes(b'changed')
    (tmp_path/'sources.json').write_text(json.dumps({'sources':[{'file':'test.pdf','sha256':'wrong'}]}))
    with pytest.raises(ValueError,match='source changed'):
        iyo_data.checked_sources()


def test_missing_verified_index_prevents_catalog_activation(tmp_path,monkeypatch):
    monkeypatch.setattr(iyo_data,'ROOT',tmp_path)
    def unavailable():
        raise ValueError('Missing index')
    monkeypatch.setattr(iyo_data,'verify',unavailable)
    with pytest.raises(ValueError,match='Missing index'):
        iyo_data.activate()
    assert not (tmp_path/'data/regions/catalog.json').exists()


def test_material_word_is_not_a_classification_and_caps_do_not_change_pet_body():
    assert iyo_data.classification_options('プラ製のものは「その他」', 'paper') == ['non_burnable']
    assert iyo_data.classification_options('プラマークがなければ「可燃」', 'plastic_packaging') == ['burnable']
    assert iyo_data.classification_options('乳白色のびんは「その他」', 'bottles') == ['non_burnable']
    assert iyo_data.classification_options('すすいでから出す', 'pet_bottles') == []
