#!/usr/bin/env python3
"""Reproduce Iyo FY2026 data. fetch/inspect/build/verify never call Bedrock.

Original files, CSVs, dates and embeddings are intentionally outside Git.
Reviewed rules, source pins and audit summaries are tracked. Source changes fail
closed and require a new review; registration is a separate readiness gate.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/regions/iyo'
CITY = '38210'
VERSION = 'iyo-2026.1'
CALENDAR_URL = 'https://www.city.iyo.lg.jp/shiminseikatsu/kurashi/gomi/shushubi/index.html'
BULKY_URL = 'https://www.city.iyo.lg.jp/shiminseikatsu/kurashi/gomi/bunbetsu/sodai/dashikata/calendar.html'


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
    def download(record):
        url = record['url']
        if urlparse(url).hostname != 'www.city.iyo.lg.jp' or Path(record['file']).name != record['file']:
            raise ValueError('Unexpected official source location')
        target = DATA / 'source' / record['file']
        target.parent.mkdir(parents=True, exist_ok=True)
        body = urlopen(url, timeout=60).read()
        if hashlib.sha256(body).hexdigest() != record['sha256']:
            # Keep the reviewed original, if present. Never silently accept a
            # new official edition or overwrite it with changed HTML/PDF bytes.
            raise ValueError(f"Official source changed; review required: {record['file']}")
        target.write_bytes(body)
        return {**record, 'retrieved_at': datetime.now(timezone.utc).isoformat()}
    results = list(ThreadPoolExecutor(max_workers=3).map(download, read(DATA/'sources.json')['sources']))
    write(DATA/'source/downloads.json', results)
    print(f'Fetched and hash-checked {len(results)} official files')


def checked_sources():
    sources = read(DATA/'sources.json')['sources']
    for source in sources:
        if digest(DATA/'source'/source['file']) != source['sha256']:
            raise ValueError(f"Reviewed source changed: {source['file']}")
    return {s['file']: s for s in sources}


def item_rows():
    from iyo_pdf import extract_items
    rules = read(DATA/'official_rules.json')
    categories = rules['categories']
    rows = []
    extracted = extract_items(DATA/'source/p26~_1.pdf')
    if len(extracted) != 1697:
        raise ValueError('Official dictionary row count changed')
    for row in extracted:
        category = row['category']
        disposal = categories[category]['instructions']
        rows.append({'item_id': row['item_id'], 'item': row['item'], 'category': category,
            'category_display': categories[category]['name'], 'note': row['note'],
            'disposal_instructions': disposal,
            # Only item-specific conditions may authorize another classification.
            # Common disposal prose can describe removable caps/labels or other
            # items; it must never turn those into options for this item's body.
            'category_options': json.dumps(classification_options(row['note'], category), ensure_ascii=False),
            'source_url': checked_dictionary_url()+'#page='+str(row['source_page']),
            'source_category': row['source_category']})
    for example in rules['examples']:
        rows.append({'item_id': example['id'], 'item': example['item'], 'category': example['category'],
            'category_display': (categories[example['category']]['name'] if example['category'] else example['category_display']), 'note': example['note'],
            'disposal_instructions': '', 'category_options': json.dumps(example.get('category_options', [])),
            'source_url': example['source_url'], 'source_category': '公式更新ページの確認済み例'})
    write(DATA/'generated/dictionary-extraction.json', extracted)
    return rows


def classification_options(note, primary):
    from iyo_pdf import CATEGORY_CODES
    # Short labels such as プラ also occur in material descriptions (プラ製),
    # marks and nouns. Only explicitly quoted classification labels authorize
    # alternatives. Do not mine common instructions or matching substrings.
    return sorted({CATEGORY_CODES[label] for label in re.findall(r'「([^」]+)」', note)
                   if label in CATEGORY_CODES} - {primary})


def checked_dictionary_url():
    return next(s['url'] for s in read(DATA/'sources.json')['sources'] if s['file']=='p26~_1.pdf')


def inspect_calendars():
    from collection_recurrence import expand
    from iyo_pdf import calendar_observations, observed_types
    sources = checked_sources()
    config = read(DATA/'calendar_rules.json')
    observations = {profile: calendar_observations(DATA/'source'/filename)
                    for profile,filename in config['source_files'].items()}
    calendars, areas, reviews = {}, [], {}
    for area in config['areas']:
        profile = area['rule_profile_id']
        source = sources[config['source_files'][profile]]
        days = expand(config['valid_from'], config['valid_to'], area['rules'],
            collection_types=config['collection_types'], closed_dates=config['closed_dates'],
            replacements=area['replacements'])
        audit = {'pdf_date_labels': 365, 'raster_and_text_days': 0, 'shared_cells_header_rule_days': [],
                 'year_end_table_days': len(area['replacements'])}
        for day, observation in observations[profile].items():
            if day in area['replacements']:
                continue  # checked against the explicit table below
            if observation['shared_cell']:
                audit['shared_cells_header_rule_days'].append(day)
                continue
            actual = observed_types(observation, day, area)
            if actual != days[day]:
                raise ValueError(f"PDF/date mismatch {area['id']} {day}: {actual} != {days[day]}")
            audit['raster_and_text_days'] += 1
        verify_year_end_table(area)
        audit['days_sha256'] = value_digest(days)
        audit['source_sha256'] = source['sha256']
        reviews[area['calendar_id']] = audit
        record = {'source_url': source['url'], 'source_sha256': source['sha256'],
                  'verification_status': 'checked', 'days': days, 'exceptions': [],
                  'official_area_note': area.get('verification_message', '')}
        if area.get('unverified_collection_types'):
            record['verification_status'] = 'partially_checked'
            record['collection_type_verification'] = {code:
                ({'status': 'unverified', 'message': area['verification_message'], 'source_url': source['url']}
                 if code in area['unverified_collection_types'] else {'status': 'checked'})
                for code in config['collection_types']}
        calendars[area['calendar_id']] = record
        areas.append({k: area[k] for k in ('id','name','display_name','calendar_id','rule_profile_id')} |
                     {'needs_local_confirmation': True, 'source_url': source['url']})
    if len({a['display_name'] for a in areas}) != len(areas):
        raise ValueError('Ambiguous duplicate area display name')
    return areas, calendars, reviews


def verify_year_end_table(area):
    """Defined below using reviewed table row/column coordinates, not recurrence."""
    from iyo_pdf import year_end_types
    actual = year_end_types(DATA/'source', area)
    # Unverified streams are omitted, never guessed from the normal district row.
    unknown = set(area.get('unverified_collection_types', []))
    actual = {day: sorted(set(codes)-unknown) for day,codes in actual.items()}
    if actual != {day: sorted(codes) for day,codes in area['replacements'].items()}:
        raise ValueError(f"Year-end PDF table differs from overrides: {area['id']}: {actual}")


def bulky_config(profile):
    deadline = {'futami': '双海地域は偶数月14日締切です。', 'nakayama': '中山地域は偶数月28日締切です。',
        'iyo': '伊予地域の上吾川・米湊・灘町・湊町・下吾川は偶数月14日締切。それ以外の伊予地域（上唐川・下唐川・大平上・大平下・三秋・中村・森・本郡・尾﨑・三島町・市場・稲荷・下三谷・上三谷・上野・宮下・八倉）は偶数月28日締切です。住所の区分を公式ページで確認してください。'}[profile]
    steps = [('対象品目を確認', '原則45リットルの袋に入らず、大人1人で運べるもの。家電リサイクル対象品などは収集できません。1回5点まで、年30点までです。'),
             ('住所と申込期限を確認', deadline+'収集は翌奇数月の年6回です。'),
             ('はがき又は電子申請で申し込む', 'はがきは申込期限の消印有効です。公式サイトからえひめ電子申請システムにも進めます。アプリからの自動申込みは行いません。'),
             ('通知はがきで収集日を確認', '通知はがきに記載された収集日に、粗大ごみシールを貼って午前8時30分までに申込場所へ出してください。立会い不要。粗大ごみの戸別収集は無料ですが、直接搬入・許可業者の費用は別途確認してください。')]
    return {'municipality_id': CITY, 'municipality_name': '伊予市', 'collection_frequency': '事前申込制・年6回（奇数月）',
            'reception_hours': deadline, 'collection_rules': deadline+'収集日は通知はがきで確認してください。',
            'fee_structure_type': 'fixed', 'application_method': 'web_form', 'phone_number': '089-909-6338',
            'web_form_url': BULKY_URL, 'information_url': BULKY_URL,
            'steps': [{'step_number': i,'title': title,'description': text} for i,(title,text) in enumerate(steps,1)]}


def build(*, inspect_only=False):
    areas, calendars, reviews = inspect_calendars()
    candidate = {'schema_version': 1, 'version': VERSION, 'calendars': reviews}
    write(DATA/'generated/review-candidate.json', candidate)
    if inspect_only:
        print('Inspection passed; compare source PDFs before accepting review-candidate.json')
        return
    if read(DATA/'calendar_reviews.json') != candidate:
        raise ValueError('Reviewed calendar audit differs; inspect the source change first')
    rules = read(DATA/'official_rules.json')
    categories = {code: {k:v for k,v in definition.items() if k != 'instructions'}
                  for code,definition in rules['categories'].items()}
    profiles = {profile: {'items_path': 'knowledge/items.csv', 'embedding_index_path': 'knowledge/item_embeddings.npz',
        'index_profile_id': 'citywide', 'calendar_path': 'generated/calendar-2026.json',
        'knowledge_title': '伊予市公式ごみ分別の手引き・辞典・更新情報', 'classification_rules': rules['classification_rules'],
        'size_question': '45リットルの袋に入る大きさですか？大人1人で持ち運べますか？',
        'categories': categories, 'bulky_waste': {'category_code': 'bulky', 'config': bulky_config(profile)}}
        for profile in ('iyo','futami','nakayama')}
    registry = {'schema_version': 1,'municipality_id': CITY,'municipality_name': '伊予市',
        'prefecture_id': '38','prefecture_name': '愛媛県','version': VERSION,
        'valid_from': '2026-04-01','valid_to': '2027-03-31','collection_areas': areas,
        'calendars': [{'id': a['calendar_id'],'rule_profile_id': a['rule_profile_id']} for a in areas],
        'rule_profiles': profiles}
    write(DATA/'registry.json', registry)
    write(DATA/'generated/calendar-2026.json', {k:registry[k] for k in ('municipality_id','version','valid_from','valid_to')} | {'calendars': calendars})
    rows = item_rows()
    target = DATA/'knowledge/items.csv'
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',encoding='utf-8',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write(DATA/'generated/item-review.json', {'official_items':1697,'total_search_records':len(rows),
        'source_categories':dict(Counter(r['source_category'] for r in rows)),
        'conditional_records':sum(r['category_options']!='[]' for r in rows), 'csv_sha256':digest(target)})
    print(f'Built {len(areas)} areas / 3 official PDFs / {len(calendars)} calendars / {len(rows)} search records')


def verify(*, without_index=False):
    sys.path.insert(0,str(ROOT/'backend'))
    from app.services.region_registry_service import RegionRegistry
    from app.services.calendar_service import CalendarService
    from app.services.embedding_search_service import EmbeddingSearchService
    checked_sources()
    areas, calendars, reviews = inspect_calendars()
    if read(DATA/'calendar_reviews.json')['calendars'] != reviews:
        raise ValueError('Official PDF audit differs from reviewed result')
    registry = RegionRegistry(DATA/'registry.json')
    if registry.data['collection_areas'] != areas or read(DATA/'generated/calendar-2026.json')['calendars'] != calendars:
        raise ValueError('Generated runtime data differ from source-derived calendars')
    with (DATA/'knowledge/items.csv').open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError('CSV differs from official dictionary and reviewed update examples')
    for profile in registry.profiles.values():
        if not without_index:
            import numpy as np
            service=EmbeddingSearchService(items_path=profile.items_path,embeddings_path=profile.embedding_index_path,
                municipality_id=CITY,profile_id='citywide',runtime_client=object())
            if not service.is_ready:
                raise ValueError('Missing/inconsistent Iyo embedding index; registration prohibited')
            with np.load(profile.embedding_index_path, allow_pickle=False) as index:
                if (list(map(str,index['item_ids'])) != [row['item_id'] for row in rows]
                        or not np.isfinite(index['vectors']).all()
                        or not np.allclose(np.linalg.norm(index['vectors'],axis=1),1,atol=.002)):
                    raise ValueError('Index row order, finite values or normalization mismatch')
    for area in registry.areas.values():
        context=registry.resolve(CITY,area['id'])
        calendar=CalendarService(calendar_path=context.rules.calendar_path,region=context)
        expected='partially_available' if area['id'].endswith('iyo-hiraoka') else 'available'
        if calendar.availability!=expected:
            raise ValueError('Calendar verification status mismatch')
    result={'official_items':1697,'search_records':len(rows),'collection_areas':len(areas),'official_calendar_pdfs':3,
        'area_calendars':len(calendars),'official_date_labels':1095,'index_checked':not without_index,
        'partial_area':'38210-iyo-hiraoka','unverified_collection_types':['bottles','pet_bottles','non_burnable','hazardous','paper']}
    write(DATA/'generated/verification.json',result)
    print(json.dumps(result,ensure_ascii=False))
    return result


def activate():
    verify()
    catalog=read(ROOT/'data/regions/catalog.json')
    entry={'id':CITY,'registry_path':'iyo/registry.json'}
    existing=next((e for e in catalog['municipalities'] if e['id']==CITY),None)
    if existing and existing!=entry:
        raise ValueError('Existing catalog registration differs')
    if not existing:
        catalog['municipalities'].append(entry)
        write(ROOT/'data/regions/catalog.json',catalog)
    print('Iyo registered; regenerate Flutter assets next')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['fetch','inspect','build','verify','activate'])
    parser.add_argument('--without-index',action='store_true',help='Offline data audit only; never activates the municipality')
    args=parser.parse_args()
    if args.command=='inspect':build(inspect_only=True)
    elif args.command=='verify':verify(without_index=args.without_index)
    elif args.command=='activate':activate()
    elif args.command=='build':build()
    else:fetch()
