#!/usr/bin/env python3
"""Reproduce Ikata data offline after fetch. Only explicit index generation is paid.

fetch -> inspect -> review pinned audit summaries -> build -> verify -> activate.
Activation requires a matching municipality-specific CSV/index manifest. Neither
an unreviewed PDF nor another municipality's data can satisfy that gate.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/regions/ikata'
CITY = '38442'
VERSION = 'ikata-2026.1'
VALID_FROM, VALID_TO = '2026-04-01', '2027-03-31'
GUIDE_URL = 'https://www.town.ikata.ehime.jp/soshiki/32/11452.html'
CALENDAR_URL = 'https://www.town.ikata.ehime.jp/soshiki/32/26164.html'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def fetch():
    def download(source):
        if (urlparse(source['url']).hostname != 'www.town.ikata.ehime.jp'
                or Path(source['file']).name != source['file']):
            raise ValueError('Unexpected official source location')
        body = urlopen(source['url'], timeout=60).read()
        if hashlib.sha256(body).hexdigest() != source['sha256']:
            raise ValueError(f"Official source changed; review required: {source['file']}")
        target = DATA/'source'/source['file']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return {**source, 'retrieved_at': datetime.now(timezone.utc).isoformat()}
    results = list(ThreadPoolExecutor(max_workers=3).map(download, read(DATA/'sources.json')['sources']))
    write(DATA/'source/downloads.json', results)
    print(f'Fetched and hash-checked {len(results)} official sources')


def checked_sources():
    sources = read(DATA/'sources.json')['sources']
    for source in sources:
        if digest(DATA/'source'/source['file']) != source['sha256']:
            raise ValueError(f"Official source changed; review required: {source['file']}")
    return {source['file']: source for source in sources}


def classification_options(note, primary):
    """Only explicit whole-item branches; accessory labels do not classify bodies."""
    from ikata_pdf import CATEGORY_CODES
    patterns = (
        r'指定袋に(?:入らないものは|入るものは|入れば)(可燃|埋立|粗大)',
        r'汚れ(?:の落ちない|た)(?:もの|物)は(可燃|埋立)',
        r'(?:金属製のもの|木製・プラ製のもの|紙製のもの|白色以外のもの|ビニール加工のもの)は(可燃|埋立|プラ)',
        r'LEDは(埋立)',
        r'濡れた・汚れた・ひどく破れた古着は(可燃)',
    )
    codes = {CATEGORY_CODES[label] for pattern in patterns for label in re.findall(pattern, note)}
    if '農業・漁業用は、産業廃棄物' in note or '家電4 品目対象品は排出禁止' in note:
        codes.add('not_collected')
    return sorted(codes-{primary})


def item_rows():
    from ikata_pdf import extract_items
    rules = read(DATA/'official_rules.json')
    extracted = extract_items(DATA/'source')
    rows = []
    for row in extracted:
        code = row['category']
        note = row['note']
        source_url = 'https://www.town.ikata.ehime.jp/uploaded/attachment/'+row['source_file']+'#page='+str(row['part_page'])
        # This guide-wide rule applies to the seven explicitly labelled 古着
        # rows, not to all paper or to garments with a different fixed category.
        if code == 'paper_textiles' and '古着として' in note:
            note += '。ガイド13ページ：濡れた・汚れた・ひどく破れた古着は可燃。'
        if row['source_page'] == 27 and row['item'] == '乾電池（ボタン型・充電式）':
            if code != 'hazardous' or note != '販売店などに相談':
                raise ValueError('Reviewed battery correction source changed')
            code = 'not_collected'
            note += '。辞典27ページの有害表記は、ガイド14・49ページの排出禁止指定で確認・補正。町の収集へ出さない。'
            source_url = 'https://www.town.ikata.ehime.jp/uploaded/attachment/10412.pdf'
        rows.append({'item_id': row['item_id'], 'item': row['item'], 'category': code,
            'category_display': rules['categories'][code]['name'], 'note': note,
            'category_options': json.dumps(classification_options(note, code)),
            'disposal_instructions': rules['categories'][code]['instructions'],
            'source_url': source_url,
            'source_category': row['source_category']})
    for example in rules['examples']:
        rows.append({'item_id': example['id'], 'item': example['item'], 'category': example['category'],
            'category_display': rules['categories'][example['category']]['name'], 'note': example['note'],
            'category_options': json.dumps(example.get('category_options', [])),
            'disposal_instructions': '', 'source_url': example['source_url'], 'source_category': '公式ガイド確認済み説明例'})
    if len({r['item_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate item ID')
    review = {'official_items': len(extracted), 'search_records': len(rows),
              'source_categories': dict(sorted(Counter(r['source_category'] for r in extracted).items())),
              'page_counts': {str(k): v for k, v in sorted(Counter(r['source_page'] for r in extracted).items())},
              'conditional_records': sum(r['category_options'] != '[]' for r in rows),
              'runtime_categories': dict(sorted(Counter(r['category'] for r in rows[:len(extracted)]).items())),
              'rows_sha256': value_digest(rows), 'dictionary_audit': '26_pages_full_and_parts_text_geometry_raster'}
    write(DATA/'generated/dictionary-extraction.json', extracted)
    return rows, review


def inspect_calendars():
    import pymupdf
    from ikata_pdf import calendar_days
    sources = checked_sources()
    areas = read(DATA/'areas.json')['areas']
    index = (DATA/'source/26164.html').read_text(encoding='utf-8')
    calendars, reviews, runtime_areas = {}, {}, []
    for area in areas:
        file = area['source_file']; source = sources[file]
        # Check the official index's named link and the PDF's own target-area
        # box, so a valid calendar cannot silently be assigned to another group.
        link = re.search(r'href="/uploaded/attachment/'+re.escape(file)+r'"[^>]*>(.*?)</a>', index, re.S)
        names = '、'.join(area['official_names'])
        compact = lambda text: re.sub(r'\s+', '', re.sub('<[^>]*>', '', text))
        pdf_text = pymupdf.open(DATA/'source'/file)[0].get_text()
        if (not link or compact(names) not in compact(link.group(1))
                or compact('、'.join(area.get('pdf_area_names', area['official_names']))) not in compact(pdf_text)
                or area['official_calendar_code'] not in pdf_text):
            raise ValueError(f'Official area/calendar mapping mismatch: {area["id"]}')
        days, audit = calendar_days(DATA/'source'/file)
        reviews[area['calendar_id']] = {**audit, 'source_sha256': source['sha256'], 'days_sha256': value_digest(days)}
        calendars[area['calendar_id']] = {'source_url': source['url'], 'source_sha256': source['sha256'],
            'verification_status': 'checked', 'days': days, 'exceptions': []}
        runtime_areas.append({k: area[k] for k in ('id', 'name', 'display_name', 'calendar_id', 'rule_profile_id')} |
            {'source_url': source['url'], 'needs_local_confirmation': True})
    if len({a['id'] for a in runtime_areas}) != len(areas) or len({a['display_name'] for a in areas}) != len(areas):
        raise ValueError('Duplicate or ambiguous area')
    return runtime_areas, calendars, reviews


def bulky_config():
    steps = [('対象品目と収集方法を確認', '町指定埋立ごみ袋（30リットル）に入らないもの等が対象。家電リサイクル4品目、充電式電池、農漁業用品などの禁止品は出せません。'),
             ('町の窓口又は許可業者へ連絡', '町民課・各支所に電話又は窓口で申し込むか、許可業者に依頼します。収集日・場所・手数料は申込先に確認してください。このアプリからは申し込めません。'),
             ('納付券など申込先の指示を確認', '町の収集では許可証・手数料納付券（シール）・納付書の案内に従い、手数料を納付してシールを貼ります。2026年度PDFには粗大ごみの収集日がないため、日付を推測しません。'),
             ('直接搬入する場合', '伊方町一般廃棄物最終処分場（九町2番耕地117番地2）は毎週金曜14〜16時、祝日を除きます。10kgにつき20円、端数は10kgへ切上げ。可燃ごみ・禁止品は搬入できません。最新の条件を公式案内で確認してください。')]
    return {'municipality_id': CITY, 'municipality_name': '伊方町', 'collection_frequency': '申込制・有料（収集日は申込先に確認）',
            'reception_hours': '町民課・各支所の開庁時間にご相談ください。',
            'collection_rules': '町民課・各支所又は許可業者で収集日・料金・場所を確認してください。定期カレンダーには粗大ごみの収集日の記載がありません。',
            'fee_structure_type': 'size_based', 'application_method': 'phone', 'phone_number': '0894-38-0211',
            'information_url': GUIDE_URL,
            'steps': [{'step_number': i, 'title': title, 'description': description}
                      for i, (title, description) in enumerate(steps, 1)]}


def registry_record(areas):
    rules = read(DATA/'official_rules.json')
    profiles = {key: {'items_path': 'knowledge/items.csv', 'embedding_index_path': 'knowledge/item_embeddings.npz',
        'index_profile_id': 'townwide', 'calendar_path': 'generated/calendar-2026.json',
        'knowledge_title': '伊方町公式ごみ分別ガイドブック・ごみ分別辞典',
        'classification_rules': rules['classification_rules'], 'size_question': '町指定のごみ袋に入る大きさですか？（埋立ごみ袋は30リットル）',
        'categories': {code: {k: v for k, v in definition.items() if k not in ('instructions', 'source_url')}
                       for code, definition in rules['categories'].items()},
        'bulky_waste': {'category_code': 'bulky', 'config': bulky_config()}}
        for key in ('ikata', 'seto', 'misaki')}
    return {'schema_version': 1, 'municipality_id': CITY, 'municipality_name': '伊方町',
        'prefecture_id': '38', 'prefecture_name': '愛媛県', 'version': VERSION,
        'valid_from': VALID_FROM, 'valid_to': VALID_TO, 'collection_areas': areas,
        'calendars': [{'id': a['calendar_id'], 'rule_profile_id': a['rule_profile_id']} for a in areas], 'rule_profiles': profiles}


def build(*, inspect_only=False):
    areas, calendars, reviews = inspect_calendars()
    rows, item_review = item_rows()
    calendar_review = {'schema_version': 1, 'version': VERSION, 'calendars': reviews}
    write(DATA/'generated/calendar-review-candidate.json', calendar_review)
    write(DATA/'generated/item-review-candidate.json', item_review)
    if inspect_only:
        print('Inspect candidates and the official PDFs before accepting audit summaries')
        return
    if read(DATA/'calendar_reviews.json') != calendar_review or read(DATA/'item_reviews.json') != item_review:
        raise ValueError('Reviewed calendar/dictionary audit differs; review required')
    registry = registry_record(areas)
    write(DATA/'registry.json', registry)
    write(DATA/'generated/calendar-2026.json', {k: registry[k] for k in ('municipality_id', 'version', 'valid_from', 'valid_to')} | {'calendars': calendars})
    target = DATA/'knowledge/items.csv'; target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(f'Built {len(rows)} search records / {len(areas)} collection groups / {len(calendars)} calendars')


def verify(*, without_index=False):
    sys.path.insert(0, str(ROOT/'backend'))
    from app.services.region_registry_service import RegionRegistry
    from app.services.calendar_service import CalendarService
    from app.services.embedding_search_service import EmbeddingSearchService
    areas, calendars, reviews = inspect_calendars()
    rows, item_review = item_rows()
    if (read(DATA/'calendar_reviews.json')['calendars'] != reviews
            or read(DATA/'item_reviews.json') != item_review):
        raise ValueError('Official PDF audit differs from reviewed result')
    with (DATA/'knowledge/items.csv').open(encoding='utf-8', newline='') as stream:
        if list(csv.DictReader(stream)) != rows:
            raise ValueError('CSV differs from official dictionary and reviewed examples')
    registry = RegionRegistry(DATA/'registry.json')
    expected_calendar = {k: registry.data[k] for k in ('municipality_id', 'version', 'valid_from', 'valid_to')} | {'calendars': calendars}
    if registry.data != registry_record(areas) or read(DATA/'generated/calendar-2026.json') != expected_calendar:
        raise ValueError('Runtime registry/calendar differs from official sources')
    for profile in registry.profiles.values():
        if not without_index:
            import numpy as np
            service = EmbeddingSearchService(items_path=profile.items_path, embeddings_path=profile.embedding_index_path,
                                            municipality_id=CITY, profile_id='townwide', runtime_client=object())
            if not service.is_ready:
                raise ValueError('Missing verified Ikata index; registration prohibited')
            with np.load(profile.embedding_index_path, allow_pickle=False) as index:
                if (list(map(str, index['item_ids'])) != [r['item_id'] for r in rows]
                        or not np.isfinite(index['vectors']).all()
                        or not np.allclose(np.linalg.norm(index['vectors'], axis=1), 1, atol=.002)):
                    raise ValueError('Invalid Ikata index vectors/row order')
    for area in areas:
        context = registry.resolve(CITY, area['id'])
        calendar = CalendarService(region=context)
        if (calendar.availability != 'available' or calendar.next_collection('bulky') is not None
                or calendar.next_collection('not_collected') is not None):
            raise ValueError('Invalid collection availability/method')
    result = {'official_items': item_review['official_items'], 'search_records': len(rows),
              'collection_groups': len(areas), 'official_calendar_pdfs': len(calendars),
              'printed_dates_and_raster_cells': sum(r['raster_cells'] for r in reviews.values()),
              'index_checked': not without_index, 'valid_from': VALID_FROM, 'valid_to': VALID_TO}
    write(DATA/'generated/verification.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return result


def activate():
    verify()
    catalog_path = ROOT/'data/regions/catalog.json'
    catalog = read(catalog_path)
    entry = {'id': CITY, 'registry_path': 'ikata/registry.json'}
    existing = next((e for e in catalog['municipalities'] if e['id'] == CITY), None)
    if existing and existing != entry:
        raise ValueError('Existing catalog entry differs')
    if not existing:
        catalog['municipalities'].append(entry); write(catalog_path, catalog)
    print('Ikata registered; generate Flutter assets next')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fetch', 'inspect', 'build', 'verify', 'activate'])
    parser.add_argument('--without-index', action='store_true')
    args = parser.parse_args()
    if args.command == 'fetch': fetch()
    elif args.command == 'inspect': build(inspect_only=True)
    elif args.command == 'build': build()
    elif args.command == 'verify': verify(without_index=args.without_index)
    else: activate()
