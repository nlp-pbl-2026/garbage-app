#!/usr/bin/env python3
"""Reproduce Ainan data from official HTML and scanned PDF sources.

The workflow is fetch -> inspect -> build -> verify. It never invokes Bedrock,
generates embeddings, edits the municipality catalog, or deploys to AWS.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/ainan"
CITY = "38506"
VERSION = "ainan-2026.1"
HOST = "www.town.ainan.ehime.jp"
SCHEDULE_URL = "https://www.town.ainan.ehime.jp/kurashi/tetsuduki/kankyoeisei/gomi/gomishushunittei.html"
ITEMS_PAGE_URL = "https://www.town.ainan.ehime.jp/kurashi/tetsuduki/kankyoeisei/gomi/R412bunbetsu.html"
COLLECTION_RULES_URL = "https://www.town.ainan.ehime.jp/kurashi/tetsuduki/kankyoeisei/gomi/files/gominoshushubi202004.pdf"
PAPER_BATTERY_URL = "https://www.town.ainan.ehime.jp/kurashi/tetsuduki/kankyoeisei/gomi/files/2026shinbunshushu.pdf"
SORTING_GUIDE_URL = "https://www.town.ainan.ehime.jp/kurashi/tetsuduki/kankyoeisei/gomi/files/gomibunnbetu2020.pdf"
ITEM_TABLE_URL = "https://www.town.ainan.ehime.jp/kurashi/tetsuduki/kankyoeisei/gomi/files/r6.8.8gomibunnbetuhayamihyo.pdf"
COPYRIGHT_URL = "https://www.town.ainan.ehime.jp/kurashi/hpnitsuite/chosakuken/"

SOURCES = {
    "schedule-page.html": SCHEDULE_URL,
    "items-page.html": ITEMS_PAGE_URL,
    "collection-rules.pdf": COLLECTION_RULES_URL,
    "paper-battery-2026.pdf": PAPER_BATTERY_URL,
    "sorting-guide.pdf": SORTING_GUIDE_URL,
    "item-table.pdf": ITEM_TABLE_URL,
    "copyright.html": COPYRIGHT_URL,
}

WEEKDAYS = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}
COLLECTION_LABELS = {
    "可燃ごみ": "burnable",
    "びん・缶": "containers",
    "ペットボトル": "pet_bottles",
    "不燃物": "nonburnable",
}

HTML_CORRECTIONS = {
    "電気毛布": {
        "category": "nonburnable",
        "category_options": ["bulky"],
        "note": "指定袋に入れる場合はコードと共に50センチメートル以下に切断してください。環境衛生センターへ持ち込む場合は有料です。",
    },
    "カーペット(ホットカーペット等)": {
        "category": "nonburnable",
        "category_options": ["bulky"],
        "note": "指定袋に入れる場合はコードと共に50センチメートル以下に切断してください。環境衛生センターへ持ち込む場合は有料です。",
    },
    "ブルーシート": {
        "category": "burnable",
        "category_options": [],
        "note": "指定袋に入れる場合は50cm以下に切断して出してください。",
    },
    "鉄アレイ": {
        "category": "nonburnable",
        "category_options": [],
        "note": "紙に包み、「鉄アレイ キケン」と表示してください。",
    },
    "布団・毛布": {
        "category": "bulky",
        "category_options": ["burnable"],
        "note": "指定袋に入れる場合は50cm以下に切断して出してください。",
    },
    "ガステーブル": {
        "category": "nonburnable",
        "category_options": ["bulky"],
        "note": "電池を外してください。指定袋に入らない場合は粗大ごみです。",
    },
    "ジュニアシート(自動車用)": {
        "category": "burnable",
        "category_options": ["nonburnable"],
        "note": "金属部分がある場合は不燃ごみです。",
    },
    "洗濯バサミ": {
        "category": "nonburnable",
        "category_options": ["burnable"],
        "note": "金属部分がなければ可燃ごみです。",
    },
    "テニスラケット": {
        "category": "nonburnable",
        "category_options": ["burnable", "bulky"],
        "note": "木製なら可燃ごみです。指定袋に入らない場合は粗大ごみです。",
    },
    "バルサン(くん煙殺虫剤)": {
        "category": "containers",
        "category_options": [],
        "note": "使用済みのものに限ります。",
    },
    "金庫(小さく軽量のもの)": {
        "category": "not_collected",
        "category_options": [],
        "note": "取扱店へ相談してください。",
    },
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
        raise ValueError("Unexpected Ainan source location")
    request = Request(url, headers={"User-Agent": "garbage-app-data-builder/1.0"})
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    body = urlopen(request, timeout=90, context=context).read()
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
    print(f"Saved {len(records)} official Ainan source files")


def source_records():
    records = read(DATA / "source/downloads.json")
    for record in records:
        path = DATA / "source" / record["file"]
        if not path.exists() or digest(path) != record["sha256"]:
            raise ValueError(f"Ainan source changed: {record['file']}")
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
    }


def checked_sources():
    actual = source_candidate()
    recorded = read(DATA / "sources.json")
    pairs = lambda value: {
        item["file"]: (item["url"], item["sha256"])
        for item in value["sources"]
    }
    if pairs(actual) != pairs(recorded):
        raise ValueError("Fetched Ainan originals differ from reviewed source pins")
    return source_records()


class ScheduleHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active_heading = ""
        self.heading_parts = None
        self.table = None
        self.row = None
        self.cell = None
        self.tables = []

    def handle_starttag(self, tag, attrs):
        if tag == "h3":
            self.heading_parts = []
        elif tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"th", "td"} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.heading_parts is not None:
            self.heading_parts.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "h3" and self.heading_parts is not None:
            self.active_heading = "".join(self.heading_parts).strip()
            self.heading_parts = None
        elif tag in {"th", "td"} and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if any(self.row):
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            if any("ブロック" in cell for row in self.table for cell in row):
                self.tables.append((self.active_heading, self.table))
            self.table = None


def schedule_rules():
    parser = ScheduleHTML()
    parser.feed((DATA / "source/schedule-page.html").read_text(encoding="utf-8"))
    result = []
    for heading, table in parser.tables:
        match = re.match(r"(\d+)\.\s*(.*)", " ".join(heading.split()))
        if not match:
            continue
        number = int(match.group(1))
        address_expression = match.group(2)
        rules = {}
        for row in table:
            for label, code in COLLECTION_LABELS.items():
                if label in row:
                    rules[code] = row[-1]
        if set(rules) != set(COLLECTION_LABELS.values()):
            raise ValueError(f"Incomplete Ainan schedule table for block {number}: {rules}")
        result.append({
            "number": number,
            "address_expression": address_expression,
            "address_labels": [part.strip() for part in address_expression.split("、")],
            "rules": rules,
        })
    if [item["number"] for item in result] != list(range(1, 9)):
        raise ValueError("Official Ainan schedule must contain blocks 1 through 8")
    return result


def _rule_dates(rule: str, year: int):
    weekdays = [WEEKDAYS[name] for name in WEEKDAYS if f"{name}曜日" in rule]
    nth = re.fullmatch(r"第(\d)([月火水木金土日])曜日", rule)
    if nth:
        occurrence = int(nth.group(1))
        weekday = WEEKDAYS[nth.group(2)]
        values = []
        for month in range(1, 13):
            matches = []
            cursor = date(year, month, 1)
            while cursor.month == month:
                if cursor.weekday() == weekday:
                    matches.append(cursor)
                cursor += timedelta(days=1)
            values.append(matches[occurrence - 1])
        return values
    if not weekdays:
        raise ValueError(f"Unsupported Ainan recurrence: {rule}")
    values = []
    cursor = date(year, 1, 1)
    while cursor.year == year:
        if cursor.weekday() in weekdays:
            values.append(cursor)
        cursor += timedelta(days=1)
    return values


def inspect_calendars():
    areas = []
    calendars = {}
    review_blocks = []
    for block in schedule_rules():
        identifier = f"ainan-block-{block['number']}"
        days = {}
        for code, rule in block["rules"].items():
            for value in _rule_dates(rule, 2026):
                days.setdefault(value.isoformat(), []).append(code)
        days = {day: sorted(codes) for day, codes in sorted(days.items())}
        display = f"ブロック{block['number']}（{block['address_expression']}）"
        areas.append({
            "id": f"{CITY}-block-{block['number']}",
            "name": f"ブロック{block['number']}",
            "display_name": display,
            "calendar_id": identifier,
            "rule_profile_id": "ainan",
            "address_labels": block["address_labels"],
            "needs_local_confirmation": True,
            "source_url": SCHEDULE_URL,
        })
        calendars[identifier] = {
            "source_url": SCHEDULE_URL,
            "verification_status": "checked",
            "days": days,
            "exceptions": [],
        }
        review_blocks.append({
            **block,
            "days_sha256": value_digest(days),
            "dated_cells": len(days),
            "collection_dates": dict(Counter(code for values in days.values() for code in values)),
        })
    reviews = {
        "schema_version": 1,
        "version": VERSION,
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "source_url": SCHEDULE_URL,
        "blocks": review_blocks,
        "paper_battery_source_url": PAPER_BATTERY_URL,
        "verification": {
            "method": "Official 2026 HTML block tables converted from weekly and nth-weekday rules",
            "coverage": "Eight official blocks; burnable, bottles/cans, PET bottles and nonburnable waste",
            "limitations": "Paper and dry-battery collection uses a separate ten-site schedule and is not inferred from the eight residential blocks",
            "reviewed_at": "2026-11-02",
        },
    }
    return areas, calendars, reviews


def ensure_ocr():
    source = DATA / "source/item-table.pdf"
    image_dir = DATA / "generated/ocr-pages"
    ocr_dir = DATA / "generated/ocr-json"
    marker_path = DATA / "generated/ocr-source.json"
    source_hash = digest(source)
    if marker_path.exists():
        marker = read(marker_path)
        if (
            marker.get("source_sha256") == source_hash
            and len(list(image_dir.glob("page-*.png"))) == 33
            and len(list(ocr_dir.glob("page-*.json"))) == 33
        ):
            return image_dir, ocr_dir
    renderer = shutil.which("pdftoppm")
    if not renderer:
        raise RuntimeError("Poppler pdftoppm is required for the Ainan item table")
    image_dir.mkdir(parents=True, exist_ok=True)
    ocr_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        renderer, "-f", "4", "-l", "36", "-r", "200", "-png",
        str(source), str(image_dir / "page"),
    ], check=True)
    if os.name != "nt":
        raise RuntimeError("Ainan inspect currently requires Windows Japanese OCR")
    subprocess.run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(ROOT / "scripts/ainan_windows_ocr.ps1"),
        "-InputDirectory", str(image_dir),
        "-OutputDirectory", str(ocr_dir),
    ], check=True)
    write(marker_path, {
        "source_sha256": source_hash,
        "render_dpi": 200,
        "pdf_pages": "4-36",
        "ocr_engine": "Windows.Media.Ocr ja",
    })
    return image_dir, ocr_dir


def extracted_items():
    from ainan_pdf import CATEGORY_NAMES, extract_items

    image_dir, ocr_dir = ensure_ocr()
    rows = extract_items(image_dir, ocr_dir)
    by_name = {row["item"]: row for row in rows}
    missing = sorted(set(HTML_CORRECTIONS) - set(by_name))
    if missing:
        raise ValueError(f"Ainan HTML correction items missing from OCR: {missing}")
    for name, correction in HTML_CORRECTIONS.items():
        row = by_name[name]
        row.update(correction)
        codes = [row["category"], *row["category_options"]]
        row["source_category"] = "、".join(CATEGORY_NAMES[code] for code in codes)
    return rows


def item_review(rows=None):
    rows = extracted_items() if rows is None else rows
    return {
        "schema_version": 1,
        "version": VERSION,
        "official_items": len(rows),
        "items_sha256": value_digest(rows),
        "primary_categories": dict(Counter(row["category"] for row in rows)),
        "multi_category_records": sum(bool(row["category_options"]) for row in rows),
        "records_with_notes": sum(bool(row["note"]) for row in rows),
        "source_pdf_pages": "4-36",
        "extraction_method": "200 dpi ruled-table segmentation plus Windows Japanese OCR coordinates and official category colors",
        "html_corrections": sorted(HTML_CORRECTIONS),
        "reviewed_at": "2026-11-02",
    }


def item_rows():
    rules = read(DATA / "official_rules.json")
    rows = []
    for item in extracted_items():
        category = item["category"]
        definition = rules["categories"][category]
        rows.append({
            "item_id": item["item_id"],
            "item": item["item"],
            "category": category,
            "category_display": definition["name"],
            "note": item["note"],
            "search_text": " ".join((item["item"], item["source_category"], item["note"])).strip(),
            "disposal_instructions": definition.get("instructions", ""),
            "category_options": json.dumps(item["category_options"], ensure_ascii=False),
            "source_url": f"{ITEM_TABLE_URL}#page={item['source_page']}",
            "source_category": item["source_category"],
        })
    return rows


def bulky_config():
    return {
        "municipality_id": CITY,
        "municipality_name": "愛南町",
        "collection_frequency": "ごみステーションでの定期収集なし",
        "reception_hours": "愛南町環境衛生センター：月～土 9:00～16:00（予約必要、休業日あり）",
        "collection_rules": "指定ごみ袋に収まらない原則100×80×250cm以内の粗大ごみは、環境衛生センター等へ直接持ち込むか、町の許可業者へ収集運搬を依頼します。",
        "fee_structure_type": "weight_based",
        "application_method": "guide_only",
        "phone_number": "0895-72-6955",
        "web_form_url": None,
        "information_url": ITEMS_PAGE_URL,
        "steps": [
            {"step_number": 1, "title": "品目と大きさを確認", "description": "指定袋に収まらず、原則100×80×250cm以内のものが粗大ごみです。禁止物は持ち込めません。"},
            {"step_number": 2, "title": "持込先へ予約", "description": "愛南町環境衛生センターへ持ち込む場合は、受付時間と休業日を確認して事前に予約します。"},
            {"step_number": 3, "title": "分別して持ち込む", "description": "袋に入る大きさのごみも施設へ持ち込む場合は分別し、中身が見える透明・半透明袋を使用します。"},
            {"step_number": 4, "title": "運搬を依頼する場合", "description": "家庭系粗大ごみ収集運搬許可業者へ依頼し、料金を各業者へ確認します。"},
        ],
    }


def build(*, inspect_only: bool = False):
    write(DATA / "generated/sources-candidate.json", source_candidate())
    areas, calendars, calendar_review = inspect_calendars()
    write(DATA / "generated/calendar-review-candidate.json", calendar_review)
    extracted = extracted_items()
    reviewed_items = item_review(extracted)
    write(DATA / "generated/item-review-candidate.json", reviewed_items)
    if inspect_only:
        write(DATA / "generated/items-candidate.json", extracted)
        print("Wrote Ainan source/calendar/item candidates; review before build")
        return
    checked_sources()
    if read(DATA / "calendar_reviews.json") != calendar_review:
        raise ValueError("Ainan HTML-derived dates differ from the approved review")
    if read(DATA / "item_reviews.json") != reviewed_items:
        raise ValueError("Ainan OCR-derived items differ from the approved review")
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
        "size_question": "愛南町の指定ごみ袋に入りますか？素材や長さは分かりますか？",
        "knowledge_title": "愛南町公式家庭ごみ分別早見表",
        "categories": categories,
        "bulky_waste": {"category_code": "bulky", "config": bulky_config()},
    }
    registry = {
        "schema_version": 1,
        "municipality_id": CITY,
        "municipality_name": "愛南町",
        "prefecture_id": "38",
        "prefecture_name": "愛媛県",
        "version": VERSION,
        "valid_from": calendar_review["valid_from"],
        "valid_to": calendar_review["valid_to"],
        "collection_areas": areas,
        "calendars": [{"id": area["calendar_id"], "rule_profile_id": "ainan"} for area in areas],
        "rule_profiles": {"ainan": profile},
    }
    write(DATA / "registry.json", registry)
    write(DATA / "generated/calendar-2026.json", {
        "municipality_id": CITY,
        "version": VERSION,
        "valid_from": calendar_review["valid_from"],
        "valid_to": calendar_review["valid_to"],
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
    print(f"Built {len(areas)} Ainan areas, {len(calendars)} calendars and {len(rows)} item records")


def verify():
    checked_sources()
    areas, calendars, calendar_review = inspect_calendars()
    if read(DATA / "calendar_reviews.json") != calendar_review:
        raise ValueError("Ainan official calendar audit differs from reviewed metadata")
    if read(DATA / "item_reviews.json") != item_review():
        raise ValueError("Ainan official item audit differs from reviewed metadata")
    registry = read(DATA / "registry.json")
    bundle = read(DATA / "generated/calendar-2026.json")
    if registry["collection_areas"] != areas or bundle["calendars"] != calendars:
        raise ValueError("Ainan registry/calendar differs from official HTML rules")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError("Ainan CSV differs from the reviewed official table extraction")
    index = DATA / "knowledge/item_embeddings.npz"
    manifest = DATA / "knowledge/index_manifest.json"
    result = {
        "official_items": len(rows),
        "collection_areas": len(areas),
        "valid_from": calendar_review["valid_from"],
        "valid_to": calendar_review["valid_to"],
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
