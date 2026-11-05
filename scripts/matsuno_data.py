#!/usr/bin/env python3
"""Reproduce Matsuno data from the town's current official PDFs.

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
DATA = ROOT / "data/regions/matsuno"
CITY = "38484"
VERSION = "matsuno-2026.1"
HOST = "www.town.matsuno.ehime.jp"

WASTE_URL = "https://www.town.matsuno.ehime.jp/soshiki/9/1333.html"
SORTING_BOOK_URL = "https://www.town.matsuno.ehime.jp/uploaded/attachment/7083.pdf"
CALENDAR_URL = "https://www.town.matsuno.ehime.jp/uploaded/attachment/1714.pdf"
COPYRIGHT_URL = "https://www.town.matsuno.ehime.jp/soshiki/1/1176.html"

SOURCES = {
    "waste-page.html": WASTE_URL,
    "sorting-book.pdf": SORTING_BOOK_URL,
    "calendar.pdf": CALENDAR_URL,
    "copyright.html": COPYRIGHT_URL,
}

STANDARD_EAST = {
    "burnable": "毎週火・金",
    "nonburnable": "毎週月",
    "resources": "毎週月",
    "pet_bottles": "毎週水",
    "containers": "毎週水",
    "waste_paper": "毎週木",
}
STANDARD_WEST = {
    "burnable": "毎週月・木",
    "nonburnable": "毎週金",
    "resources": "毎週金",
    "pet_bottles": "毎週水",
    "containers": "毎週水",
    "waste_paper": "毎週火",
}


def _area(slug, name, rules, *, display_name=None, labels=None):
    return {
        "slug": slug,
        "name": name,
        "display_name": display_name or name,
        "address_labels": labels or [name],
        "rules": dict(rules),
    }


AREA_DEFINITIONS = (
    _area("matsumaru", "松丸", STANDARD_EAST),
    _area("nobunono", "延野々", STANDARD_WEST),
    _area("toyooka-ushiro", "豊岡後", STANDARD_WEST),
    _area("toyooka-mae", "豊岡前", STANDARD_WEST),
    _area("tomioka", "富岡", STANDARD_WEST),
    _area(
        "kamieji",
        "上家地",
        {
            "burnable": "毎週月・木",
            "nonburnable": "第1・第3金",
            "resources": "第1・第3金",
            "pet_bottles": "第2・第4水",
            "containers": "第2・第4水",
            "waste_paper": "第2火",
        },
    ),
    _area("meguro", "目黒", STANDARD_WEST),
    _area(
        "yoshino",
        "吉野",
        STANDARD_EAST,
        display_name="吉野（葛川地区を除く）",
        labels=["吉野（葛川地区を除く）"],
    ),
    _area(
        "kuzukawa",
        "葛川地区",
        {
            "burnable": "毎週火",
            "nonburnable": "第2・第4月",
            "resources": "第2・第4月",
            "pet_bottles": "第1・第3水",
            "containers": "第1・第3水",
            "waste_paper": "第1木",
        },
        display_name="葛川地区（吉野内）",
        labels=["葛川", "葛川地区"],
    ),
    _area("warabiu", "蕨生", STANDARD_EAST),
    _area("okunogawa", "奥野川", STANDARD_EAST),
)

WEEKDAYS = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
CLOSED_DATES = {
    date(2026, 8, 15),
    date(2026, 12, 31),
    date(2027, 1, 1),
    date(2027, 1, 2),
    date(2027, 1, 3),
}


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
        raise ValueError("Unexpected Matsuno source location")
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
    records = list(ThreadPoolExecutor(max_workers=4).map(_download, SOURCES.items()))
    records.sort(key=lambda item: item["file"])
    write(DATA / "source/downloads.json", records)
    print(f"Saved {len(records)} official Matsuno source files")


def source_records():
    records = read(DATA / "source/downloads.json")
    for record in records:
        path = DATA / "source" / record["file"]
        if not path.exists() or digest(path) != record["sha256"]:
            raise ValueError(f"Matsuno source changed: {record['file']}")
    return {record["file"]: record for record in records}


def source_candidate():
    records = source_records()
    return {
        "schema_version": 1,
        "municipality_id": CITY,
        "version": VERSION,
        "valid_from": "2026-04-01",
        "valid_to": "2027-03-31",
        "license_status": "permission_required_for_redistribution",
        "copyright_url": COPYRIGHT_URL,
        "sources": [records[name] for name in sorted(records)],
        "source_notes": {
            "sorting-book.pdf": "Current source of truth effective 2026-04-01",
            "calendar.pdf": "Official page still links this 2017 reference; not used to generate 2026 dates",
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
        raise ValueError("Fetched Matsuno originals differ from reviewed source pins")
    return source_records()


def validate_sources():
    html = (DATA / "source/waste-page.html").read_text(encoding="utf-8")
    required = (
        "令和8年4月1日",
        "/uploaded/attachment/7083.pdf",
        "/uploaded/attachment/1714.pdf",
    )
    missing = [value for value in required if value not in html]
    if missing:
        raise ValueError(f"Official Matsuno page changed: {missing}")
    import pdfplumber

    with pdfplumber.open(DATA / "source/sorting-book.pdf") as book:
        if len(book.pages) != 65:
            raise ValueError(f"Matsuno sorting book page count changed: {len(book.pages)}")
        cover = book.pages[0].extract_text() or ""
        schedule = book.pages[2].extract_text() or ""
    for value in ("令和８年４月１日", "松 丸", "葛川地区", "第２・第４水曜日"):
        if value not in cover + schedule:
            raise ValueError(f"Matsuno current book marker missing: {value}")
    with pdfplumber.open(DATA / "source/calendar.pdf") as old_book:
        old_calendar = old_book.pages[0].extract_text() or ""
    if not re.search(r"2017年\s*７月", old_calendar):
        raise ValueError("Matsuno standalone calendar is no longer the reviewed 2017 reference")


def _rule_dates(rule: str, start: date, end: date):
    if rule.startswith("毎週"):
        weekdays = {WEEKDAYS[value] for value in rule.removeprefix("毎週").split("・")}
        values = []
        cursor = start
        while cursor <= end:
            if cursor.weekday() in weekdays and cursor not in CLOSED_DATES:
                values.append(cursor)
            cursor += timedelta(days=1)
        return values
    numbers = [int(value) for value in re.findall(r"第(\d+)", rule)]
    weekday_name = rule[-1]
    if not numbers or weekday_name not in WEEKDAYS:
        raise ValueError(f"Unsupported Matsuno schedule rule: {rule}")
    values = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        month_values = []
        day = cursor
        while day.month == cursor.month:
            if day.weekday() == WEEKDAYS[weekday_name]:
                month_values.append(day)
            day += timedelta(days=1)
        values.extend(
            month_values[number - 1]
            for number in numbers
            if number <= len(month_values)
            and start <= month_values[number - 1] <= end
            and month_values[number - 1] not in CLOSED_DATES
        )
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return values


def inspect_calendars():
    validate_sources()
    valid_from = date(2026, 4, 1)
    valid_to = date(2027, 3, 31)
    areas = []
    calendars = {}
    reviewed_areas = []
    for definition in AREA_DEFINITIONS:
        identifier = f"matsuno-{definition['slug']}"
        days = {}
        for code, rule in definition["rules"].items():
            for value in _rule_dates(rule, valid_from, valid_to):
                days.setdefault(value.isoformat(), []).append(code)
        days = {day: sorted(codes) for day, codes in sorted(days.items())}
        areas.append({
            "id": f"{CITY}-{definition['slug']}",
            "name": definition["name"],
            "display_name": definition["display_name"],
            "calendar_id": identifier,
            "rule_profile_id": "matsuno",
            "address_labels": definition["address_labels"],
            "needs_local_confirmation": True,
            "source_url": f"{SORTING_BOOK_URL}#page=3",
        })
        calendars[identifier] = {
            "source_url": f"{SORTING_BOOK_URL}#page=3",
            "verification_status": "checked",
            "verification_method": "rule_derived_with_weather_confirmation",
            "days": days,
            "exceptions": [
                {
                    "type": "weather_confirmation",
                    "category": "waste_paper",
                    "note": "古紙は雨天時に収集されないため、当日の天候と町の案内を確認",
                },
                {
                    "type": "temporary_change_confirmation",
                    "note": "積雪その他の変更は回覧・防災無線等を確認",
                },
            ],
        }
        reviewed_areas.append({
            "calendar_id": identifier,
            "display_name": definition["display_name"],
            "address_labels": definition["address_labels"],
            "rules": definition["rules"],
            "days_sha256": value_digest(days),
            "dated_cells": len(days),
            "collection_dates": dict(Counter(code for codes in days.values() for code in codes)),
        })
    reviews = {
        "schema_version": 1,
        "version": VERSION,
        "valid_from": valid_from.isoformat(),
        "valid_to": valid_to.isoformat(),
        "source_url": f"{SORTING_BOOK_URL}#page=3",
        "areas": reviewed_areas,
        "closed_dates": sorted(value.isoformat() for value in CLOSED_DATES),
        "verification": {
            "method": "Current April 2026 book schedule converted from weekly and nth-weekday rules",
            "coverage": "Ten named settlements plus the Kuzukawa exception within Yoshino",
            "limitations": "Rain cancels waste-paper collection; snow and temporary changes are announced separately and are not inferred",
            "stale_source_excluded": CALENDAR_URL,
            "reviewed_at": "2026-11-03",
        },
    }
    return areas, calendars, reviews


def extracted_items():
    from matsuno_pdf import extract_items
    return extract_items(DATA / "source/sorting-book.pdf")


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
        "source_pdf_pages": "22-63",
        "extraction_method": "pdfplumber ruled-table extraction with merged category-cell continuation recovery",
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
            "source_url": f"{SORTING_BOOK_URL}#page={item['source_page']}",
            "source_category": item["source_category"],
        })
    return rows


def bulky_config():
    return {
        "municipality_id": CITY,
        "municipality_name": "松野町",
        "collection_frequency": "年2回（回覧で周知）",
        "reception_hours": "環境センターへの直接持込は月～土曜日13:00～16:30（祝祭日・年末年始を除く）",
        "collection_rules": "町の粗大ごみ収集日は回覧で確認します。直接持ち込む場合は幅1m×高さ80cm×長さ2.5m以内です。",
        "fee_structure_type": "weight_based",
        "application_method": "guide_only",
        "phone_number": "0895-42-1115",
        "web_form_url": None,
        "information_url": WASTE_URL,
        "steps": [
            {"step_number": 1, "title": "町の回覧を確認", "description": "年2回の粗大ごみ収集日は回覧で周知されます。"},
            {"step_number": 2, "title": "直接持込も選択", "description": "宇和島地区広域事務組合環境センターへ持ち込む場合は、種類ごとに分別します。"},
            {"step_number": 3, "title": "料金とサイズを確認", "description": "家庭ごみは10kgあたり50円で、粗大ごみの受入可能サイズを確認します。"},
            {"step_number": 4, "title": "運搬が難しい場合", "description": "町の許可業者へ料金を確認して依頼します。"},
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
        print("Wrote Matsuno source/calendar/item candidates; review before build")
        return
    checked_sources()
    if read(DATA / "calendar_reviews.json") != calendar_reviews:
        raise ValueError("Matsuno rule-derived dates differ from the approved review")
    if read(DATA / "item_reviews.json") != reviewed_items:
        raise ValueError("Matsuno PDF-derived items differ from the approved review")
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
        "size_question": "松野町の指定ごみ袋に入りますか？素材、汚れ、電池の有無を確認できますか？",
        "knowledge_title": "松野町家庭ごみ分別・分類ブック（令和8年4月版）",
        "categories": categories,
        "bulky_waste": {"category_code": "bulky", "config": bulky_config()},
    }
    registry = {
        "schema_version": 1,
        "municipality_id": CITY,
        "municipality_name": "松野町",
        "prefecture_id": "38",
        "prefecture_name": "愛媛県",
        "version": VERSION,
        "valid_from": calendar_reviews["valid_from"],
        "valid_to": calendar_reviews["valid_to"],
        "collection_areas": areas,
        "calendars": [{"id": area["calendar_id"], "rule_profile_id": "matsuno"} for area in areas],
        "rule_profiles": {"matsuno": profile},
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
    print(f"Built {len(areas)} Matsuno areas, {len(calendars)} calendars and {len(rows)} item records")


def verify():
    checked_sources()
    areas, calendars, calendar_reviews = inspect_calendars()
    if read(DATA / "calendar_reviews.json") != calendar_reviews:
        raise ValueError("Matsuno calendar audit differs from reviewed metadata")
    if read(DATA / "item_reviews.json") != item_review():
        raise ValueError("Matsuno item audit differs from reviewed metadata")
    registry = read(DATA / "registry.json")
    bundle = read(DATA / "generated/calendar-2026.json")
    if registry["collection_areas"] != areas or bundle["calendars"] != calendars:
        raise ValueError("Matsuno registry/calendar differs from official rules")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError("Matsuno CSV differs from official item extraction")
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
