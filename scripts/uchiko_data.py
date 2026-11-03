#!/usr/bin/env python3
"""Reproduce Uchiko data from the town's current official PDFs.

The workflow is fetch -> inspect -> build -> verify. It never invokes Bedrock,
generates embeddings, edits the municipality catalog, or deploys to AWS.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import ssl
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/uchiko"
CITY = "38422"
VERSION = "uchiko-2026.1"
HOST = "www.town.uchiko.ehime.jp"

SORTING_PAGE_URL = f"https://{HOST}/soshiki/10/gomibunnbetu.html"
CALENDAR_PAGE_URL = f"https://{HOST}/soshiki/10/145277.html"
DICTIONARY_URL = f"https://{HOST}/uploaded/life/139240_284629_misc.pdf"
RULES_URL = f"https://{HOST}/uploaded/life/139240_324562_misc.pdf"
COPYRIGHT_URL = f"https://{HOST}/soshiki/1/cyosakuken-menseki.html"
CALENDAR_URLS = {
    "calendar-1.pdf": f"https://{HOST}/uploaded/life/145277_324783_misc.pdf",
    "calendar-2.pdf": f"https://{HOST}/uploaded/life/145277_324784_misc.pdf",
    "calendar-3.pdf": f"https://{HOST}/uploaded/life/145277_324785_misc.pdf",
    "calendar-4.pdf": f"https://{HOST}/uploaded/life/145277_324786_misc.pdf",
    "calendar-5.pdf": f"https://{HOST}/uploaded/life/145277_324787_misc.pdf",
}
SOURCES = {
    "sorting-page.html": SORTING_PAGE_URL,
    "calendar-page.html": CALENDAR_PAGE_URL,
    "dictionary-current.pdf": DICTIONARY_URL,
    "rules-current.pdf": RULES_URL,
    **CALENDAR_URLS,
    "copyright.html": COPYRIGHT_URL,
}

WEEKDAYS = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}


def _area(
    slug,
    center,
    display_name,
    labels,
    weekly,
    resource_file,
    resource_index,
    *,
    excluded=None,
    note=None,
):
    return {
        "slug": slug,
        "center": center,
        "display_name": display_name,
        "address_labels": labels,
        "weekly": weekly,
        "excluded": excluded or {},
        "resource_file": resource_file,
        "resource_index": resource_index,
        "note": note,
    }


JAN1_DEC31 = {"burnable": ("2026-01-01", "2026-12-31")}
JAN2_MAY5 = {"burnable": ("2026-01-02", "2026-05-05")}
JAN3_AUG15 = {"burnable": ("2026-01-03", "2026-08-15")}
BIO_A_CLOSED = {"organic": ("2026-01-02", "2026-05-05")}
BIO_B_CLOSED = {"organic": ("2026-01-03", "2026-08-15")}

AREA_DEFINITIONS = (
    _area(
        "uchiko-a",
        "内子自治センター",
        "内子 1～4区・5区中町通り沿い・12～19区・20区通常収集場所",
        [
            "1～4区",
            "5区（中町通り沿い）",
            "12～19区",
            "20区（元・堀川医院道路向かい収集場所を除く）",
        ],
        {"organic": "毎週火・金", "burnable": "毎週月"},
        "calendar-1.pdf",
        0,
        excluded=BIO_A_CLOSED,
        note="20区の元・堀川医院道路向かい収集場所は別選択",
    ),
    _area(
        "uchiko-20-horikawa",
        "内子自治センター",
        "内子 20区（元・堀川医院道路向かい収集場所）",
        ["20区", "元・堀川医院道路向かい収集場所"],
        {"organic": "毎週火・金", "burnable": "毎週木"},
        "calendar-1.pdf",
        0,
        excluded={**BIO_A_CLOSED, **JAN1_DEC31},
        note="収集場所単位の例外のため現地確認が必要",
    ),
    _area(
        "uchiko-b",
        "内子自治センター",
        "内子 5区中町通り沿い以外・6～11区",
        ["5区（中町通り沿い以外）", "6～11区"],
        {"organic": "毎週水・土", "burnable": "毎週木"},
        "calendar-1.pdf",
        0,
        excluded={**BIO_B_CLOSED, **JAN1_DEC31},
    ),
    _area(
        "uchiko-21",
        "内子自治センター",
        "内子 21区",
        ["21区"],
        {"organic": "毎週水・土", "burnable": "毎週木"},
        "calendar-1.pdf",
        1,
        excluded={**BIO_B_CLOSED, **JAN1_DEC31},
    ),
    _area(
        "uchiko-22",
        "内子自治センター",
        "内子 22区",
        ["22区"],
        {"burnable": "毎週火"},
        "calendar-1.pdf",
        2,
        excluded={"burnable": ("2026-05-05",)},
    ),
    _area(
        "uchiko-east-bio",
        "内子東自治センター",
        "内子東 松尾（生ごみ収集区域）・田中・護国・岡・大岡",
        ["松尾（生ごみ収集区域）", "田中", "護国", "岡", "大岡"],
        {"organic": "毎週水・土", "burnable": "毎週木"},
        "calendar-2.pdf",
        0,
        excluded={**BIO_B_CLOSED, **JAN1_DEC31},
    ),
    _area(
        "uchiko-east-route56",
        "内子東自治センター",
        "内子東 立川（国道56号沿い）・宿茂",
        ["立川（立川中央国道56号沿い）", "宿茂"],
        {"burnable": "毎週水・土"},
        "calendar-2.pdf",
        0,
        excluded=JAN3_AUG15,
    ),
    _area(
        "uchiko-east-matsuo-other",
        "内子東自治センター",
        "内子東 松尾（生ごみ収集区域以外）",
        ["松尾（生ごみ収集区域以外）"],
        {"burnable": "毎週水・土"},
        "calendar-2.pdf",
        1,
        excluded=JAN3_AUG15,
    ),
    _area(
        "uchiko-east-tachikawa-mitsuho",
        "内子東自治センター",
        "内子東 立川（国道56号沿い以外）・満穂（論田・河内・石畳）",
        ["立川（立川中央国道56号沿い以外）", "満穂（論田・河内・石畳）"],
        {"burnable": "毎週火"},
        "calendar-2.pdf",
        1,
        excluded={"burnable": ("2026-05-05",)},
    ),
    _area(
        "uchiko-east-tominaka-tominaga",
        "内子東自治センター",
        "内子東 富中・富長",
        ["富中", "富長"],
        {"burnable": "毎週火・金"},
        "calendar-2.pdf",
        1,
        excluded=JAN2_MAY5,
    ),
    _area(
        "uchiko-east-nagata",
        "内子東自治センター",
        "内子東 長田",
        ["長田"],
        {"burnable": "毎週水"},
        "calendar-2.pdf",
        2,
    ),
    _area(
        "ose-main",
        "大瀬自治センター",
        "大瀬 本町1（高中除く）・本町2・本町3・乙成",
        ["本町1（高中を除く）", "本町2", "本町3", "乙成"],
        {"burnable": "毎週火・金"},
        "calendar-3.pdf",
        0,
        excluded=JAN2_MAY5,
    ),
    _area(
        "ose-thursday",
        "大瀬自治センター",
        "大瀬 本町1高中・中野・江子・村前・川登今岡",
        ["本町1（高中）", "中野", "江子", "村前自治会", "川登自治会（今岡）"],
        {"burnable": "毎週木"},
        "calendar-3.pdf",
        1,
        excluded=JAN1_DEC31,
    ),
    _area(
        "ose-friday",
        "大瀬自治センター",
        "大瀬 大久保・鵜川・程内",
        ["大久保", "鵜川", "程内自治会"],
        {"burnable": "毎週金"},
        "calendar-3.pdf",
        1,
        excluded={"burnable": ("2026-01-02",)},
    ),
    _area(
        "ose-wada-kogaidani",
        "大瀬自治センター",
        "大瀬 和田自治会（小貝谷）",
        ["和田自治会（小貝谷）", "小貝谷"],
        {"burnable": "毎週水"},
        "calendar-3.pdf",
        1,
    ),
    _area(
        "ose-tue-fri",
        "大瀬自治センター",
        "大瀬 和田（北深・小貝谷除く）・川登（路木・川登・梅津）",
        ["和田自治会（北深・小貝谷を除く）", "路木", "川登", "梅津"],
        {"burnable": "毎週火・金"},
        "calendar-3.pdf",
        1,
        excluded=JAN2_MAY5,
    ),
    _area(
        "ose-wada-kitafuka",
        "大瀬自治センター",
        "大瀬 和田自治会（北深）",
        ["和田自治会（北深）", "北深"],
        {"burnable": "毎週水"},
        "calendar-3.pdf",
        2,
    ),
    _area(
        "ose-ikeda",
        "大瀬自治センター",
        "大瀬 池田自治会",
        ["池田自治会"],
        {"burnable": "毎週土"},
        "calendar-3.pdf",
        3,
        excluded=JAN3_AUG15,
    ),
    _area(
        "ikazaki-side",
        "五十崎自治センター",
        "五十崎側（龍王・新町・中央・神南以外）",
        ["龍王自治会", "新町自治会", "中央自治会", "神南自治会（神南以外）"],
        {"burnable": "毎週月・木"},
        "calendar-4.pdf",
        0,
        excluded=JAN1_DEC31,
    ),
    _area(
        "ikazaki-kannan",
        "五十崎自治センター",
        "五十崎 神南自治会（神南）",
        ["神南自治会（神南）", "神南"],
        {"burnable": "毎週月"},
        "calendar-4.pdf",
        0,
        note="燃えるごみは山間部、資源・燃えないごみは五十崎側",
    ),
    _area(
        "ikazaki-tenjin",
        "五十崎自治センター",
        "五十崎 天神側",
        ["平岡自治会", "東沖自治会", "西沖自治会", "柿原自治会", "重松自治会（駄場）", "宿福自治会（福岡以外）", "御祓自治会（御祓団地）"],
        {"burnable": "毎週火・金"},
        "calendar-4.pdf",
        1,
        excluded=JAN2_MAY5,
    ),
    _area(
        "ikazaki-mountain",
        "五十崎自治センター",
        "五十崎 山間部",
        ["重松自治会（上重松・下重松・亀井・池窪）", "宿福自治会（福岡）", "御祓自治会（御祓団地以外）"],
        {"burnable": "毎週月"},
        "calendar-4.pdf",
        1,
    ),
    _area(
        "oda-upper",
        "小田自治センター",
        "小田 上川・中川・本川",
        ["上川", "中川", "本川"],
        {"burnable": "毎週月・木"},
        "calendar-5.pdf",
        0,
        excluded=JAN1_DEC31,
    ),
    _area(
        "oda-hirano-oda",
        "小田自治センター",
        "小田 平野・小田",
        ["平野", "小田"],
        {"burnable": "毎週月・木"},
        "calendar-5.pdf",
        1,
        excluded=JAN1_DEC31,
    ),
    _area(
        "oda-minamiyama",
        "小田自治センター",
        "小田 南山",
        ["南山"],
        {"burnable": "毎週火・金"},
        "calendar-5.pdf",
        1,
        excluded=JAN2_MAY5,
    ),
    _area(
        "oda-other",
        "小田自治センター",
        "小田 寺村・立石・吉野川・中田渡・上田渡・臼杵",
        ["寺村", "立石", "吉野川", "中田渡", "上田渡", "臼杵"],
        {"burnable": "毎週火・金"},
        "calendar-5.pdf",
        2,
        excluded=JAN2_MAY5,
    ),
)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _download(pair):
    filename, url = pair
    parsed = urlparse(url)
    if parsed.hostname != HOST or Path(filename).name != filename:
        raise ValueError("Unexpected Uchiko source location")
    request = Request(url, headers={"User-Agent": "garbage-app-data-builder/1.0"})
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    body = urlopen(request, timeout=120, context=context).read()
    path = DATA / "source" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {
        "file": filename,
        "url": url,
        "sha256": digest(path),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch():
    records = list(ThreadPoolExecutor(max_workers=6).map(_download, SOURCES.items()))
    records.sort(key=lambda item: item["file"])
    write(DATA / "source/downloads.json", records)
    print(f"Saved {len(records)} official Uchiko source files")


def source_records():
    records = read(DATA / "source/downloads.json")
    for record in records:
        path = DATA / "source" / record["file"]
        if not path.exists() or digest(path) != record["sha256"]:
            raise ValueError(f"Uchiko source changed: {record['file']}")
    return {record["file"]: record for record in records}


def source_candidate():
    records = source_records()
    return {
        "schema_version": 1,
        "municipality_id": CITY,
        "version": VERSION,
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "license_status": "permission_required_for_redistribution",
        "copyright_url": COPYRIGHT_URL,
        "sources": [records[name] for name in sorted(records)],
        "source_notes": {
            "dictionary-current.pdf": "Item dictionary updated 2026-05-28",
            "calendar-1.pdf": "Calendar-year source: 2026-01-01 through 2026-12-31",
            "calendar-2.pdf": "Calendar-year source: 2026-01-01 through 2026-12-31",
            "calendar-3.pdf": "Calendar-year source: 2026-01-01 through 2026-12-31",
            "calendar-4.pdf": "Calendar-year source: 2026-01-01 through 2026-12-31",
            "calendar-5.pdf": "Calendar-year source: 2026-01-01 through 2026-12-31",
        },
    }


def checked_sources():
    actual = source_candidate()
    recorded = read(DATA / "sources.json")
    pairs = lambda value: {
        item["file"]: (item["url"], item["sha256"])
        for item in value["sources"]
    }
    if pairs(actual) != pairs(recorded):
        raise ValueError("Fetched Uchiko originals differ from reviewed source pins")
    return source_records()


def validate_sources():
    import pdfplumber

    sorting_html = (DATA / "source/sorting-page.html").read_text(encoding="utf-8")
    calendar_html = (DATA / "source/calendar-page.html").read_text(encoding="utf-8")
    for value in ("139240_284629_misc.pdf", "139240_324562_misc.pdf", "令和8年5月28日"):
        if value not in sorting_html:
            raise ValueError(f"Uchiko sorting page marker missing: {value}")
    for value in ("145277_324783_misc.pdf", "145277_324787_misc.pdf", "令和８年"):
        if value not in calendar_html:
            raise ValueError(f"Uchiko calendar page marker missing: {value}")
    with pdfplumber.open(DATA / "source/dictionary-current.pdf") as document:
        if len(document.pages) != 13:
            raise ValueError("Uchiko dictionary page count changed")
        marker = document.pages[0].extract_text() or ""
    if "ごみ分別辞典" not in marker or "家庭ごみ" not in marker:
        raise ValueError("Uchiko dictionary title changed")
    expected_titles = ("内子", "内子東", "大瀬", "五十崎", "小田")
    for number, expected in enumerate(expected_titles, 1):
        with pdfplumber.open(DATA / f"source/calendar-{number}.pdf") as document:
            text = document.pages[0].extract_text() or ""
        if expected not in text or "令和8 年1 月～12 月".replace(" ", "") not in text.replace(" ", ""):
            raise ValueError(f"Uchiko calendar title changed: calendar-{number}.pdf")


def _weekly_dates(rule: str, excluded):
    weekdays = {WEEKDAYS[value] for value in rule.removeprefix("毎週").split("・")}
    excluded_dates = {date.fromisoformat(value) for value in excluded}
    values = []
    cursor = date(2026, 1, 1)
    while cursor <= date(2026, 12, 31):
        if cursor.weekday() in weekdays and cursor not in excluded_dates:
            values.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return values


def calendar_source_tables():
    from uchiko_pdf import extract_resource_tables

    return {
        filename: extract_resource_tables(DATA / "source" / filename)
        for filename in CALENDAR_URLS
    }


def inspect_calendars():
    validate_sources()
    source_tables = calendar_source_tables()
    areas = []
    calendars = {}
    reviewed_areas = []
    for definition in AREA_DEFINITIONS:
        identifier = f"uchiko-{definition['slug']}"
        source = source_tables[definition["resource_file"]][definition["resource_index"]]
        days = {day: list(codes) for day, codes in source["days"].items()}
        for code, rule in definition["weekly"].items():
            excluded = definition["excluded"].get(code, ())
            for value in _weekly_dates(rule, excluded):
                days.setdefault(value, []).append(code)
        days = {day: sorted(set(codes)) for day, codes in sorted(days.items())}
        source_url = CALENDAR_URLS[definition["resource_file"]]
        area = {
            "id": f"{CITY}-{definition['slug']}",
            "name": definition["display_name"],
            "display_name": definition["display_name"],
            "calendar_id": identifier,
            "rule_profile_id": "uchiko",
            "address_labels": definition["address_labels"],
            "parent_area": definition["center"],
            "needs_local_confirmation": True,
            "source_url": source_url,
        }
        if definition["note"]:
            area["mapping_note"] = definition["note"]
        areas.append(area)
        rules = {**definition["weekly"], **source["rules"]}
        calendars[identifier] = {
            "source_url": source_url,
            "verification_status": "official_2026_dates_and_reviewed_weekly_rules",
            "days": days,
            "exceptions": [
                {
                    "type": "calendar_year_boundary",
                    "note": "公式資料は2026暦年版。2027年1月以降へ流用しない",
                },
                {
                    "type": "local_mapping_confirmation",
                    "note": definition["note"] or "自治センター管内の地区・自治会を公式表で確認",
                },
            ],
        }
        reviewed_areas.append({
            "calendar_id": identifier,
            "center": definition["center"],
            "display_name": definition["display_name"],
            "address_labels": definition["address_labels"],
            "rules": rules,
            "excluded_dates": {
                code: list(values) for code, values in definition["excluded"].items()
            },
            "resource_table": {
                "file": definition["resource_file"],
                "index": definition["resource_index"],
            },
            "days_sha256": value_digest(days),
            "dated_cells": len(days),
            "collection_dates": dict(Counter(code for codes in days.values() for code in codes)),
        })
    reviews = {
        "schema_version": 1,
        "version": VERSION,
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "source_url": CALENDAR_PAGE_URL,
        "areas": reviewed_areas,
        "verification": {
            "method": "Literal resource/nonburnable dates extracted from five official PDFs; weekly organic/burnable rules expanded with explicit no-collection dates",
            "coverage": "Five community-center jurisdictions represented by 26 schedule combinations",
            "limitations": "Address-to-community-center mapping and named collection-place exceptions require local confirmation",
            "calendar_basis": "Calendar year 2026, not fiscal year 2026",
            "reviewed_at": "2026-11-03",
        },
    }
    return areas, calendars, reviews


def extracted_items():
    from uchiko_pdf import extract_items

    return extract_items(DATA / "source/dictionary-current.pdf")


def item_review(rows=None):
    rows = extracted_items() if rows is None else rows
    return {
        "schema_version": 1,
        "version": VERSION,
        "official_items": len(rows),
        "items_sha256": value_digest(rows),
        "primary_categories": dict(Counter(row["category"] for row in rows)),
        "conditional_records": sum(bool(row["category_options"]) for row in rows),
        "records_with_notes": sum(bool(row["note"]) for row in rows),
        "source_pdf_pages": "2-13",
        "extraction_method": "pdfplumber ruled-table extraction with split-parenthesis repair",
        "reviewed_at": "2026-11-03",
    }


def item_rows():
    rules = read(DATA / "official_rules.json")
    rows = []
    for item in extracted_items():
        definition = rules["categories"][item["category"]]
        rows.append({
            "item_id": item["item_id"],
            "item": item["item"],
            "category": item["category"],
            "category_display": definition["name"],
            "note": item["note"],
            "search_text": " ".join((item["item"], item["source_category"], item["note"])).strip(),
            "disposal_instructions": definition.get("instructions", ""),
            "category_options": json.dumps(item["category_options"], ensure_ascii=False),
            "source_url": f"{DICTIONARY_URL}#page={item['source_page']}",
            "source_category": item["source_category"],
        })
    return rows


def bulky_config():
    return {
        "municipality_id": CITY,
        "municipality_name": "内子町",
        "collection_frequency": "地域別の申込収集",
        "reception_hours": "クリーンセンター持込は月～土曜8:30～12:00、13:00～16:30（休業日を除く）",
        "collection_rules": "指定袋に入らないもの等は粗大ごみ。品目により直接持込不可のため分別辞典を確認します。",
        "fee_structure_type": "item_or_direct_dropoff",
        "application_method": "municipal_collection_or_direct_dropoff",
        "phone_number": "0893-44-6159",
        "web_form_url": None,
        "information_url": SORTING_PAGE_URL,
        "steps": [
            {"step_number": 1, "title": "品目を確認", "description": "分別辞典で粗大区分と持込可否を確認します。"},
            {"step_number": 2, "title": "町の収集へ申込", "description": "町の粗大ごみ収集を利用する場合は環境政策室へ確認します。"},
            {"step_number": 3, "title": "直接持込も選択", "description": "持込可能品は内子町クリーンセンターの受付日時を確認します。"},
        ],
    }


def build(*, inspect_only=False):
    write(DATA / "generated/sources-candidate.json", source_candidate())
    areas, calendars, calendar_reviews = inspect_calendars()
    write(DATA / "generated/calendar-review-candidate.json", calendar_reviews)
    extracted = extracted_items()
    reviewed_items = item_review(extracted)
    write(DATA / "generated/item-review-candidate.json", reviewed_items)
    if inspect_only:
        write(DATA / "generated/items-candidate.json", extracted)
        print("Wrote Uchiko source/calendar/item candidates; review before build")
        return
    checked_sources()
    if read(DATA / "calendar_reviews.json") != calendar_reviews:
        raise ValueError("Uchiko dates differ from the approved review")
    if read(DATA / "item_reviews.json") != reviewed_items:
        raise ValueError("Uchiko PDF-derived items differ from the approved review")
    rules = read(DATA / "official_rules.json")
    categories = {
        code: {key: value for key, value in definition.items() if key != "instructions"}
        for code, definition in rules["categories"].items()
    }
    profile = {
        "items_path": "knowledge/items.csv",
        "embedding_index_path": "knowledge/item_embeddings.npz",
        "index_profile_id": "citywide",
        "calendar_path": "generated/calendar-2026.json",
        "classification_rules": rules["classification_rules"],
        "size_question": "内子町の指定袋に入りますか？素材、生ごみ収集区域、家電4品目かを確認できますか？",
        "knowledge_title": "内子町ごみ分別辞典（令和8年5月更新）",
        "categories": categories,
        "bulky_waste": {"category_code": "bulky", "config": bulky_config()},
    }
    registry = {
        "schema_version": 1,
        "municipality_id": CITY,
        "municipality_name": "内子町",
        "prefecture_id": "38",
        "prefecture_name": "愛媛県",
        "version": VERSION,
        "valid_from": calendar_reviews["valid_from"],
        "valid_to": calendar_reviews["valid_to"],
        "collection_areas": areas,
        "calendars": [{"id": area["calendar_id"], "rule_profile_id": "uchiko"} for area in areas],
        "rule_profiles": {"uchiko": profile},
    }
    write(DATA / "registry.json", registry)
    write(DATA / "generated/calendar-2026.json", {
        "municipality_id": CITY,
        "version": VERSION,
        "valid_from": calendar_reviews["valid_from"],
        "valid_to": calendar_reviews["valid_to"],
        "calendars": calendars,
    })
    rows = item_rows()
    target = DATA / "knowledge/items.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write(DATA / "generated/item-review.json", {
        "official_items": len(rows),
        "source_categories": dict(Counter(row["source_category"] for row in rows)),
        "conditional_records": sum(row["category_options"] != "[]" for row in rows),
        "csv_sha256": digest(target),
    })
    print(f"Built {len(areas)} Uchiko areas, {len(calendars)} calendars and {len(rows)} item records")


def verify():
    checked_sources()
    areas, calendars, calendar_reviews = inspect_calendars()
    if read(DATA / "calendar_reviews.json") != calendar_reviews:
        raise ValueError("Uchiko calendar audit differs from reviewed metadata")
    if read(DATA / "item_reviews.json") != item_review():
        raise ValueError("Uchiko item audit differs from reviewed metadata")
    registry = read(DATA / "registry.json")
    bundle = read(DATA / "generated/calendar-2026.json")
    if registry["collection_areas"] != areas or bundle["calendars"] != calendars:
        raise ValueError("Uchiko registry/calendar differs from official rules")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError("Uchiko CSV differs from official item extraction")
    index = DATA / "knowledge/item_embeddings.npz"
    manifest = DATA / "knowledge/index_manifest.json"
    result = {
        "official_items": len(rows),
        "collection_areas": len(areas),
        "valid_from": calendar_reviews["valid_from"],
        "valid_to": calendar_reviews["valid_to"],
        "embedding_ready": index.exists() and manifest.exists(),
        "catalog_registered": any(
            item["id"] == CITY
            for item in read(ROOT / "data/regions/catalog.json")["municipalities"]
        ),
    }
    write(DATA / "generated/verification.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "inspect", "build", "verify"))
    args = parser.parse_args()
    if args.command == "fetch":
        fetch()
    elif args.command == "inspect":
        build(inspect_only=True)
    elif args.command == "build":
        build()
    else:
        verify()
