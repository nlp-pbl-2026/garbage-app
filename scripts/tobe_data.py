#!/usr/bin/env python3
"""Reproduce Tobe data from official HTML and PDF sources.

The workflow is fetch -> inspect -> build -> verify.  It never invokes Bedrock,
generates embeddings, edits the municipality catalog, or deploys to AWS.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/tobe"
CITY = "38402"
VERSION = "tobe-2026.1"
HOST = "www.town.tobe.ehime.jp"
RULES_URL = "https://www.town.tobe.ehime.jp/soshikikarasagasu/chominka/gomi/871.html"
CALENDAR_PAGE_URL = "https://www.town.tobe.ehime.jp/gomi_search/4959.html"
DICTIONARY_URL = "https://www.town.tobe.ehime.jp/material/files/group/12/22532.pdf"
SEPARATION_TABLE_URL = "https://www.town.tobe.ehime.jp/material/files/group/12/22241.pdf"
HANDBOOK_URL = "https://www.town.tobe.ehime.jp/material/files/group/12/gomibunbetuchou.pdf"
CARRY_IN_URL = "https://www.town.tobe.ehime.jp/kurashi_tetsuzuki/gomi_risaikuru_kankyo/1/1745.html"
HAULERS_URL = "https://www.town.tobe.ehime.jp/soshikikarasagasu/chominka/gomi/850.html"
BASE_SOURCES = {
    "rules-page.html": RULES_URL,
    "calendar-page.html": CALENDAR_PAGE_URL,
    "dictionary.pdf": DICTIONARY_URL,
    "separation-table.pdf": SEPARATION_TABLE_URL,
    "handbook.pdf": HANDBOOK_URL,
    "carry-in.html": CARRY_IN_URL,
    "licensed-haulers.html": HAULERS_URL,
}

AREA_DEFINITIONS = (
    ("38402-asou", "麻生小校区", "麻生小校区（田ノ浦を除く）", "tobe-asou"),
    ("38402-miyauchi-tobe", "宮内小・砥部小校区", "宮内小・砥部小校区（大平・鵜ノ崎を除く）", "tobe-miyauchi-tobe"),
    ("38402-hirota-weekly-1", "広田地域 可燃週1回", "広田地域（可燃ごみ週1回）", "tobe-hirota-weekly-1"),
    ("38402-hirota-weekly-2", "広田地域 可燃週2回", "広田地域（可燃ごみ週2回）", "tobe-hirota-weekly-2"),
    ("38402-tanoura", "田ノ浦", "田ノ浦", "tobe-tanoura"),
    ("38402-ohira", "大平", "大平", "tobe-ohira"),
    ("38402-unosaki", "鵜ノ崎", "鵜ノ崎", "tobe-unosaki"),
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


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._link = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._link = [dict(attrs).get("href", ""), ""]

    def handle_data(self, text):
        if self._link is not None:
            self._link[1] += text

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None:
            self._link[1] = " ".join(self._link[1].split())
            self.links.append(tuple(self._link))
            self._link = None

    @classmethod
    def load(cls, path: Path):
        parser = cls()
        parser.feed(path.read_text(encoding="utf-8"))
        return parser


def calendar_entries(data_path: Path = DATA):
    """Read the currently published FY2026 monthly calendar links.

    The page also keeps November-March links from the previous fiscal year.
    Its current-fiscal block is the first descending run ending at April, so
    parsing stops at April instead of accidentally relabeling old PDFs.
    """
    entries = []
    for href, text in Links.load(data_path / "source/calendar-page.html").links:
        match = re.search(r"くらしのカレンダー\s*(\d{1,2})月号", text)
        if not match or not href.lower().endswith(".pdf"):
            continue
        month = int(match.group(1))
        if not entries:
            if not 4 <= month <= 12:
                continue
        elif month != entries[-1]["month"] - 1:
            break
        url = urljoin(CALENDAR_PAGE_URL, href)
        filename = f"calendar-2026-{month:02}.pdf"
        entries.append({"year": 2026, "month": month, "filename": filename,
                        "url": url, "title": text})
        if month == 4:
            break
    if not entries or entries[-1]["month"] != 4:
        raise ValueError("Official Tobe FY2026 calendar links do not reach April")
    entries.reverse()
    return entries


def _download(pair):
    filename, url = pair
    parsed = urlparse(url)
    if parsed.hostname != HOST or Path(filename).name != filename:
        raise ValueError("Unexpected Tobe source location")
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
    return {"file": filename, "url": url, "sha256": digest(path),
            "retrieved_at": datetime.now(timezone.utc).isoformat()}


def fetch():
    records = list(ThreadPoolExecutor(max_workers=4).map(_download, BASE_SOURCES.items()))
    calendars = {entry["filename"]: entry["url"] for entry in calendar_entries()}
    records.extend(ThreadPoolExecutor(max_workers=4).map(_download, calendars.items()))
    records.sort(key=lambda item: item["file"])
    write(DATA / "source/downloads.json", records)
    print(f"Saved {len(records)} official Tobe source files")


def source_records():
    records = read(DATA / "source/downloads.json")
    for record in records:
        path = DATA / "source" / record["file"]
        if not path.exists() or digest(path) != record["sha256"]:
            raise ValueError(f"Tobe source changed: {record['file']}")
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
        "copyright_url": "https://www.town.tobe.ehime.jp/gyoseijoho/koho_johokokai_ikemboshu/6/3254.html",
        "sources": [records[name] for name in sorted(records)],
    }


def checked_sources():
    actual = source_candidate()
    recorded = read(DATA / "sources.json")
    pairs = lambda value: {item["file"]: (item["url"], item["sha256"])
                           for item in value["sources"]}
    if pairs(actual) != pairs(recorded):
        raise ValueError("Fetched Tobe originals differ from reviewed source pins")
    return source_records()


def item_rows():
    import pymupdf
    from tobe_pdf import extract_items_from_words

    rules = read(DATA / "official_rules.json")
    executable = shutil.which("pdftotext")
    if not executable:
        raise RuntimeError("Poppler pdftotext is required for the Tobe dictionary")
    output = DATA / "generated/dictionary.tsv"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([executable, "-enc", "UTF-8", "-tsv",
                    str(DATA / "source/dictionary.pdf"), str(output)], check=True)
    with output.open(encoding="utf-8", newline="") as stream:
        words = [{
            "page": int(row["page_num"]),
            "block": int(row["block_num"]),
            "line": int(row["line_num"]),
            "word": int(row["word_num"]),
            "x": float(row["left"]),
            "y": float(row["top"]),
            "width": float(row["width"]),
            "height": float(row["height"]),
            "text": row["text"],
        } for row in csv.DictReader(stream, delimiter="\t") if row.get("level") == "5"]
    extracted = extract_items_from_words(pymupdf.open(DATA / "source/dictionary.pdf"), words)
    rows = []
    for item in extracted:
        category = item["category"]
        definition = rules["categories"][category]
        note_parts = [item["note"]]
        if item["recycle"]:
            note_parts.append("リサイクル: " + item["recycle"])
        rows.append({
            "item_id": item["item_id"],
            "item": item["item"],
            "category": category,
            "category_display": definition["name"],
            "note": " ".join(part for part in note_parts if part),
            "search_text": " ".join((item["item"], item["source_category"], item["recycle"])).strip(),
            "disposal_instructions": definition.get("instructions", ""),
            "category_options": json.dumps(item["category_options"], ensure_ascii=False),
            "source_url": f"{DICTIONARY_URL}#page={item['source_page']}",
            "source_category": item["source_category"],
        })
    return rows


def inspect_calendars():
    import pymupdf
    from tobe_pdf import CALENDAR_IDS, extract_calendar

    records = source_records()
    merged = {identifier: {} for identifier in CALENDAR_IDS}
    monthly = {}
    source_urls = []
    for entry in calendar_entries():
        path = DATA / "source" / entry["filename"]
        calendars, audit = extract_calendar(pymupdf.open(path), year=entry["year"], month=entry["month"])
        monthly[f"2026-{entry['month']:02}"] = {
            "source_sha256": records[entry["filename"]]["sha256"],
            "source_url": entry["url"],
            **audit,
        }
        source_urls.append(entry["url"])
        for identifier, days in calendars.items():
            for day, types in days.items():
                previous = merged[identifier].get(day)
                if previous is not None and previous != types:
                    raise ValueError(f"Overlapping Tobe calendar issues disagree: {identifier} {day}")
                merged[identifier][day] = types
    if not merged["tobe-asou"] or min(merged["tobe-asou"]) != "2026-04-01":
        raise ValueError("Tobe verified calendar coverage must start on 2026-04-01")
    valid_from = min(merged["tobe-asou"])
    valid_to = max(merged["tobe-asou"])
    reviews = {
        "schema_version": 1,
        "version": VERSION,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "published_months": [entry["month"] for entry in calendar_entries()],
        "monthly_sources": monthly,
        "calendars": {identifier: {
            "days_sha256": value_digest(days),
            "dated_cells": len(days),
            "collection_dates": dict(Counter(code for values in days.values() for code in values)),
        } for identifier, days in merged.items()},
        "verification": {
            "method": "Official monthly life-calendar ruled tables and printed cell text",
            "coverage": f"Published FY2026 issues through {valid_to}; no recurrence inferred beyond printed dates",
            "limitations": "Months not yet published by Tobe Town are outside this registry validity period",
            "reviewed_at": "2026-11-02",
        },
    }
    areas = [{
        "id": identifier,
        "name": name,
        "display_name": display,
        "calendar_id": calendar_id,
        "rule_profile_id": "tobe",
        "address_labels": [display],
        "needs_local_confirmation": True,
        "source_url": CALENDAR_PAGE_URL,
    } for identifier, name, display, calendar_id in AREA_DEFINITIONS]
    calendar_records = {identifier: {
        "source_url": CALENDAR_PAGE_URL,
        "source_month_urls": source_urls,
        "verification_status": "checked",
        "days": days,
        "exceptions": [],
    } for identifier, days in merged.items()}
    return areas, calendar_records, reviews


def bulky_config():
    return {
        "municipality_id": CITY,
        "municipality_name": "砥部町",
        "collection_frequency": "ごみステーションでの定期収集なし",
        "reception_hours": "美化センター：月～金・第2/第4日曜 9:00～16:00（年末年始を除く）",
        "collection_rules": "指定袋に入らない大きな雑ごみ、20kg以上、一時多量ごみは、美化センター等へ直接持ち込むか、町の許可を受けた収集運搬業者へ依頼します。",
        "fee_structure_type": "weight_based",
        "application_method": "direct_dropoff",
        "phone_number": "089-962-5168",
        "web_form_url": None,
        "information_url": CARRY_IN_URL,
        "steps": [
            {"step_number": 1, "title": "対象と持込先を確認", "description": "指定袋に入らない雑ごみ、20kg以上、引越し等の一時多量ごみは美化センターが主な持込先です。ブロック・瓦・石等は千里埋立処分場の対象です。"},
            {"step_number": 2, "title": "受付日と費用を確認", "description": "施設の受付日、休業日、重量制の処理手数料を公式ページで確認してください。"},
            {"step_number": 3, "title": "直接持ち込む", "description": "受付で計量後、自分で分別ごとの場所へ降ろします。指定ごみ袋は不要です。"},
            {"step_number": 4, "title": "運搬を依頼する場合", "description": "町の一般廃棄物収集運搬許可業者だけに依頼してください。料金は業者へ直接確認します。"},
        ],
    }


def build(*, inspect_only: bool = False):
    write(DATA / "generated/sources-candidate.json", source_candidate())
    areas, calendars, reviews = inspect_calendars()
    write(DATA / "generated/review-candidate.json", reviews)
    if inspect_only:
        print("Wrote Tobe source/calendar candidates; review before build")
        return
    checked_sources()
    if read(DATA / "calendar_reviews.json") != reviews:
        raise ValueError("Tobe PDF-derived dates differ from the approved review")
    rules = read(DATA / "official_rules.json")
    categories = {code: {key: value for key, value in definition.items() if key != "instructions"}
                  for code, definition in rules["categories"].items()}
    profile = {
        "items_path": "knowledge/items.csv",
        "embedding_index_path": "knowledge/item_embeddings.npz",
        "index_profile_id": "citywide",
        "calendar_path": "generated/calendar-2026.json",
        "classification_rules": rules["classification_rules"],
        "size_question": "砥部町の指定ごみ袋に入りますか？重さは20kg未満ですか？",
        "knowledge_title": "砥部町公式ごみ分別辞典",
        "categories": categories,
        "bulky_waste": {"category_code": "facility_dropoff", "config": bulky_config()},
    }
    registry = {
        "schema_version": 1,
        "municipality_id": CITY,
        "municipality_name": "砥部町",
        "prefecture_id": "38",
        "prefecture_name": "愛媛県",
        "version": VERSION,
        "valid_from": reviews["valid_from"],
        "valid_to": reviews["valid_to"],
        "collection_areas": areas,
        "calendars": [{"id": area["calendar_id"], "rule_profile_id": "tobe"} for area in areas],
        "rule_profiles": {"tobe": profile},
    }
    write(DATA / "registry.json", registry)
    write(DATA / "generated/calendar-2026.json", {
        "municipality_id": CITY,
        "version": VERSION,
        "valid_from": reviews["valid_from"],
        "valid_to": reviews["valid_to"],
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
    print(f"Built {len(areas)} Tobe areas, {len(calendars)} calendars and {len(rows)} item records")


def verify():
    checked_sources()
    areas, calendars, reviews = inspect_calendars()
    if read(DATA / "calendar_reviews.json") != reviews:
        raise ValueError("Tobe official calendar audit differs from reviewed metadata")
    registry = read(DATA / "registry.json")
    bundle = read(DATA / "generated/calendar-2026.json")
    if registry["collection_areas"] != areas or bundle["calendars"] != calendars:
        raise ValueError("Tobe registry/calendar differs from official monthly PDFs")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError("Tobe CSV differs from the official dictionary extraction")
    index = DATA / "knowledge/item_embeddings.npz"
    manifest = DATA / "knowledge/index_manifest.json"
    result = {
        "official_items": len(rows),
        "collection_areas": len(areas),
        "published_calendar_months": reviews["published_months"],
        "valid_from": reviews["valid_from"],
        "valid_to": reviews["valid_to"],
        "embedding_ready": index.exists() and manifest.exists(),
        "catalog_registered": any(item["id"] == CITY for item in read(ROOT / "data/regions/catalog.json")["municipalities"]),
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
