#!/usr/bin/env python3
"""Reproduce Masaki Town data from its official guide and FY2026 calendars.

The workflow is fetch -> inspect -> build -> verify.  It never invokes
Bedrock, generates embeddings, edits the municipality catalog, or deploys.
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
import shutil
import ssl
import subprocess
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/masaki"
CITY = "38401"
VERSION = "masaki-2026.1"
HOST = "www.town.masaki.ehime.jp"

CALENDAR_PAGE_URL = f"https://{HOST}/site/hikkoshisumai/gomi-calendar-h30.html"
GUIDE_URL = f"https://{HOST}/uploaded/attachment/16014.pdf"
SEPARATION_URL = f"https://{HOST}/uploaded/attachment/21989.pdf"
WASTE_PLAN_URL = f"https://{HOST}/uploaded/attachment/24411.pdf"
MASAKI_CALENDAR_URL = f"https://{HOST}/uploaded/attachment/24135.pdf"
KITAIYO_CALENDAR_URL = f"https://{HOST}/uploaded/attachment/24136.pdf"
BULKY_URL = f"https://{HOST}/site/gomi/10385.html"
COPYRIGHT_URL = f"https://{HOST}/soshiki/3/web.html"

SOURCES = {
    "calendar-page.html": CALENDAR_PAGE_URL,
    "calendar-masaki.pdf": MASAKI_CALENDAR_URL,
    "calendar-kitaiyo-okada.pdf": KITAIYO_CALENDAR_URL,
    "guide-2021.pdf": GUIDE_URL,
    "separation-2024.pdf": SEPARATION_URL,
    "waste-plan-2026.pdf": WASTE_PLAN_URL,
    "bulky-page.html": BULKY_URL,
    "copyright.html": COPYRIGHT_URL,
}

COMMON_RULES = {
    "burnable": "毎週月・木",
    "waste_paper": "第1・第3火",
    "bottles": "第2土",
    "cans": "第1土",
    "metal": "第4土",
    "textiles": "第2火",
    "hazardous": "第3土",
    "landfill": "第4火",
}

AREA_DEFINITIONS = (
    {
        "slug": "masaki-school",
        "name": "松前校区",
        "calendar_id": "masaki-masaki-school",
        "source_file": "calendar-masaki.pdf",
        "source_url": MASAKI_CALENDAR_URL,
        "rules": {
            **COMMON_RULES,
            "pet_bottles": "第1・第3金",
            "plastic": "毎週水",
            "pruning": "第2・第4金",
        },
    },
    {
        "slug": "kitaiyo-okada-school",
        "name": "北伊予・岡田校区",
        "calendar_id": "masaki-kitaiyo-okada-school",
        "source_file": "calendar-kitaiyo-okada.pdf",
        "source_url": KITAIYO_CALENDAR_URL,
        "rules": {
            **COMMON_RULES,
            "pet_bottles": "第1・第3水",
            "plastic": "毎週金",
            "pruning": "第2・第4水",
        },
    },
)

WEEKDAYS = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
CLOSURES = {
    "masaki-masaki-school": {
        "burnable": {date(2026, 12, 31)},
        "pet_bottles": {date(2027, 1, 1)},
        "cans": {date(2027, 1, 2)},
        "hazardous": {date(2027, 1, 16)},
    },
    "masaki-kitaiyo-okada-school": {
        "burnable": {date(2026, 12, 31)},
        "plastic": {date(2027, 1, 1)},
        "cans": {date(2027, 1, 2)},
        "hazardous": {date(2027, 1, 16)},
    },
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _download(pair):
    filename, url = pair
    parsed = urlparse(url)
    if parsed.hostname != HOST or Path(filename).name != filename:
        raise ValueError("Unexpected Masaki source location")
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
    print(f"Saved {len(records)} official Masaki source files")


def source_records():
    records = read(DATA / "source/downloads.json")
    for record in records:
        path = DATA / "source" / record["file"]
        if not path.exists() or digest(path) != record["sha256"]:
            raise ValueError(f"Masaki source changed: {record['file']}")
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
            "guide-2021.pdf": "Item names and primary classifications from the 2021 revised official guide",
            "calendar-page.html": "Current notice includes the April 2023 dirty-plastic rule override",
            "separation-2024.pdf": "Current summary table confirming the post-2023 separation rules",
            "waste-plan-2026.pdf": "FY2026 statutory schedule and disposal-method table",
            "calendar-masaki.pdf": "Literal FY2026 Masaki school-zone calendar",
            "calendar-kitaiyo-okada.pdf": "Literal FY2026 Kitaiyo/Okada school-zone calendar",
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
        raise ValueError("Fetched Masaki originals differ from reviewed source pins")
    return source_records()


def validate_sources():
    html = (DATA / "source/calendar-page.html").read_text(encoding="utf-8")
    required = (
        "令和８年度",
        "/uploaded/attachment/24135.pdf",
        "/uploaded/attachment/24136.pdf",
        "汚れが取れないとき",
        "プラスチック類",
    )
    missing = [marker for marker in required if marker not in html]
    if missing:
        raise ValueError(f"Official Masaki calendar page changed: {missing}")

    import pymupdf

    expected_pages = {
        "calendar-masaki.pdf": 16,
        "calendar-kitaiyo-okada.pdf": 16,
        "guide-2021.pdf": 40,
        "separation-2024.pdf": 1,
    }
    for filename, expected in expected_pages.items():
        with pymupdf.open(DATA / "source" / filename) as document:
            if len(document) != expected:
                raise ValueError(
                    f"Masaki {filename} page count changed: {len(document)}"
                )


def _rule_dates(rule: str, start: date, end: date):
    if rule.startswith("毎週"):
        weekdays = {WEEKDAYS[value] for value in rule.removeprefix("毎週").split("・")}
        values = []
        cursor = start
        while cursor <= end:
            if cursor.weekday() in weekdays:
                values.append(cursor)
            cursor += timedelta(days=1)
        return values

    numbers = [int(value) for value in re.findall(r"第(\d+)", rule)]
    weekday_name = rule[-1]
    if not numbers or weekday_name not in WEEKDAYS:
        raise ValueError(f"Unsupported Masaki schedule rule: {rule}")
    values = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        weekdays = []
        day = cursor
        while day.month == cursor.month:
            if day.weekday() == WEEKDAYS[weekday_name]:
                weekdays.append(day)
            day += timedelta(days=1)
        values.extend(
            weekdays[number - 1]
            for number in numbers
            if number <= len(weekdays) and start <= weekdays[number - 1] <= end
        )
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return values


def _calendar_dates(definition, start: date, end: date):
    days = {}
    closures = CLOSURES[definition["calendar_id"]]
    for code, rule in definition["rules"].items():
        for value in _rule_dates(rule, start, end):
            if value in closures.get(code, set()):
                continue
            days.setdefault(value.isoformat(), []).append(code)
    return {day: sorted(set(codes)) for day, codes in sorted(days.items())}


def inspect_calendars():
    validate_sources()
    start, end = date(2026, 4, 1), date(2027, 3, 31)
    areas, calendars, reviewed = [], {}, []
    records = source_records()
    for definition in AREA_DEFINITIONS:
        days = _calendar_dates(definition, start, end)
        closures = CLOSURES[definition["calendar_id"]]
        areas.append(
            {
                "id": f"{CITY}-{definition['slug']}",
                "name": definition["name"],
                "display_name": definition["name"],
                "calendar_id": definition["calendar_id"],
                "rule_profile_id": "masaki",
                "address_labels": [definition["name"]],
                "needs_local_confirmation": True,
                "source_url": definition["source_url"],
                "mapping_note": "町内住所から校区への自動判定は未実装のため、公式資料または現地で校区確認が必要",
            }
        )
        exceptions = [
            {
                "type": "no_collection",
                "date": closed.isoformat(),
                "collection_type": code,
                "note": "令和8年度公式カレンダーの『収集休み』表記",
            }
            for code, values in closures.items()
            for closed in sorted(values)
        ]
        calendars[definition["calendar_id"]] = {
            "source_url": definition["source_url"],
            "verification_status": "checked",
            "verification_method": "checked_against_literal_calendar",
            "days": days,
            "exceptions": exceptions,
        }
        reviewed.append(
            {
                "calendar_id": definition["calendar_id"],
                "display_name": definition["name"],
                "source_file": definition["source_file"],
                "source_sha256": records[definition["source_file"]]["sha256"],
                "rules": definition["rules"],
                "closures": [
                    {"date": closed.isoformat(), "collection_type": code}
                    for code, values in closures.items()
                    for closed in sorted(values)
                ],
                "days_sha256": value_digest(days),
                "dated_cells": len(days),
                "collection_dates": dict(
                    Counter(code for codes in days.values() for code in codes)
                ),
            }
        )
    reviews = {
        "schema_version": 1,
        "version": VERSION,
        "valid_from": start.isoformat(),
        "valid_to": end.isoformat(),
        "source_page_url": CALENDAR_PAGE_URL,
        "areas": reviewed,
        "verification": {
            "method": "FY2026 official calendar month grids checked against weekly/nth-weekday rules; printed collection holidays retained as explicit exceptions",
            "calendar_pdf_pages": "3, 5, 7-10 (April 2026 through March 2027)",
            "limitations": "School-zone membership is not inferred from an address; temporary weather or operational changes require current municipal confirmation",
            "reviewed_at": "2026-11-03",
        },
    }
    return areas, calendars, reviews


def extracted_items():
    import pymupdf
    from masaki_pdf import extract_items_from_words

    executable = shutil.which("pdftotext")
    if not executable:
        raise RuntimeError("Poppler pdftotext is required for the Masaki guide")
    output = DATA / "generated/guide.tsv"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            executable,
            "-enc",
            "UTF-8",
            "-tsv",
            str(DATA / "source/guide-2021.pdf"),
            str(output),
        ],
        check=True,
    )
    with output.open(encoding="utf-8", newline="") as stream:
        words = [
            {
                "page": int(row["page_num"]),
                "block": int(row["block_num"]),
                "line": int(row["line_num"]),
                "word": int(row["word_num"]),
                "x": float(row["left"]),
                "y": float(row["top"]),
                "width": float(row["width"]),
                "height": float(row["height"]),
                "text": row["text"],
            }
            for row in csv.DictReader(stream, delimiter="\t")
            if row.get("level") == "5"
        ]
    return extract_items_from_words(
        pymupdf.open(DATA / "source/guide-2021.pdf"), words, minimum_rows=1300
    )


def item_review(rows=None):
    rows = extracted_items() if rows is None else rows
    return {
        "schema_version": 1,
        "version": VERSION,
        "official_items": len(rows),
        "items_sha256": value_digest(rows),
        "primary_categories": dict(Counter(row["category"] for row in rows)),
        "conditional_records": sum(bool(row["category_options"]) for row in rows),
        "current_rule_overrides": sum(
            row["source_note"] != row["note"] for row in rows
        ),
        "source_pdf_pages": "20-38",
        "extraction_method": "Poppler Unicode words aligned to PyMuPDF ruled-table geometry; no OCR",
        "reviewed_at": "2026-11-03",
    }


def item_rows():
    rules = read(DATA / "official_rules.json")
    rows = []
    for item in extracted_items():
        definition = rules["categories"][item["category"]]
        rows.append(
            {
                "item_id": item["item_id"],
                "item": item["item"],
                "category": item["category"],
                "category_display": definition["name"],
                "note": item["note"],
                "search_text": " ".join(
                    (item["item"], item["source_category"], item["note"])
                ).strip(),
                "disposal_instructions": definition.get("instructions", ""),
                "category_options": json.dumps(
                    item["category_options"], ensure_ascii=False
                ),
                "source_url": f"{GUIDE_URL}#page={item['source_page']}",
                "source_category": item["source_category"],
            }
        )
    return rows


def bulky_config():
    return {
        "municipality_id": CITY,
        "municipality_name": "松前町",
        "collection_frequency": "公式カレンダー記載の申込期間ごとの戸別収集",
        "reception_hours": "申込期間は選択地区の令和8年度ごみカレンダーで確認",
        "collection_rules": "45L以下の袋に入らないものが対象。1回の申込期間につき1世帯5点まで、長さ3m以内かつ大人2人で運べる大きさです。",
        "fee_structure_type": "fixed",
        "application_method": "web_form",
        "phone_number": "089-985-4117",
        "web_form_url": None,
        "information_url": BULKY_URL,
        "steps": [
            {"step_number": 1, "title": "申込期間を確認", "description": "選択した校区のごみカレンダーで黄色表示の申込期間を確認します。"},
            {"step_number": 2, "title": "電子申請またははがきで申込", "description": "1点ずつ品目を記載し、排出場所を指定します。申込後の追加・変更はできません。"},
            {"step_number": 3, "title": "通知を確認", "description": "町から届く粗大ごみ収集通知はがきで収集日を確認します。"},
            {"step_number": 4, "title": "シールを貼って排出", "description": "氏名を記入したシールを貼り、指定場所へ収集日の午前7時までに出します。"},
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
        print("Wrote Masaki source/calendar/item candidates; review before build")
        return

    checked_sources()
    if read(DATA / "calendar_reviews.json") != calendar_reviews:
        raise ValueError("Masaki dates differ from the approved calendar review")
    if read(DATA / "item_reviews.json") != reviewed_items:
        raise ValueError("Masaki items differ from the approved item review")

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
        "size_question": "松前町の45L袋に入りますか？材質、汚れ、電池の有無、校区を確認できますか？",
        "knowledge_title": "松前町ごみ分別の手引き（現行ルール補正済み）",
        "categories": categories,
        "bulky_waste": {"category_code": "bulky", "config": bulky_config()},
    }
    registry = {
        "schema_version": 1,
        "municipality_id": CITY,
        "municipality_name": "松前町",
        "prefecture_id": "38",
        "prefecture_name": "愛媛県",
        "version": VERSION,
        "valid_from": calendar_reviews["valid_from"],
        "valid_to": calendar_reviews["valid_to"],
        "collection_areas": areas,
        "calendars": [
            {"id": area["calendar_id"], "rule_profile_id": "masaki"}
            for area in areas
        ],
        "rule_profiles": {"masaki": profile},
    }
    write(DATA / "registry.json", registry)
    write(
        DATA / "generated/calendar-2026.json",
        {
            "municipality_id": CITY,
            "version": VERSION,
            "valid_from": calendar_reviews["valid_from"],
            "valid_to": calendar_reviews["valid_to"],
            "calendars": calendars,
        },
    )
    rows = item_rows()
    target = DATA / "knowledge/items.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write(
        DATA / "generated/item-review.json",
        {
            "official_items": len(rows),
            "source_categories": dict(Counter(row["source_category"] for row in rows)),
            "conditional_records": sum(row["category_options"] != "[]" for row in rows),
            "csv_sha256": digest(target),
        },
    )
    print(
        f"Built {len(areas)} Masaki areas, {len(calendars)} calendars "
        f"and {len(rows)} item records"
    )


def verify():
    checked_sources()
    areas, calendars, calendar_reviews = inspect_calendars()
    if read(DATA / "calendar_reviews.json") != calendar_reviews:
        raise ValueError("Masaki calendar audit differs from reviewed metadata")
    if read(DATA / "item_reviews.json") != item_review():
        raise ValueError("Masaki item audit differs from reviewed metadata")
    registry = read(DATA / "registry.json")
    bundle = read(DATA / "generated/calendar-2026.json")
    if registry["collection_areas"] != areas or bundle["calendars"] != calendars:
        raise ValueError("Masaki registry/calendar differs from official calendars")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError("Masaki CSV differs from official item extraction")
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
