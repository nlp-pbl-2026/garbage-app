#!/usr/bin/env python3
"""Reproduce Kihoku data from official HTML and PDF sources.

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
import shutil
import ssl
import subprocess
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/kihoku"
CITY = "38488"
VERSION = "kihoku-2026.1"
HOST = "www.town.kihoku.ehime.jp"

WASTE_URL = "https://www.town.kihoku.ehime.jp/soshiki/kankyou/58.html"
RESOURCE_URL = "https://www.town.kihoku.ehime.jp/soshiki/kankyou/264.html"
PLASTIC_URL = "https://www.town.kihoku.ehime.jp/soshiki/kankyou/33929.html"
BATTERY_URL = "https://www.town.kihoku.ehime.jp/soshiki/kankyou/34157.html"
LARGE_WASTE_URL = "https://www.town.kihoku.ehime.jp/soshiki/kankyou/15663.html"
ITEM_TABLE_URL = "https://www.town.kihoku.ehime.jp/uploaded/attachment/6289.pdf"
SORTING_GUIDE_URL = "https://www.town.kihoku.ehime.jp/uploaded/attachment/8646.pdf"
PLASTIC_GUIDE_URL = "https://www.town.kihoku.ehime.jp/uploaded/attachment/18327.pdf"
BATTERY_GUIDE_URL = "https://www.town.kihoku.ehime.jp/uploaded/attachment/18393.pdf"
COPYRIGHT_URL = "https://www.town.kihoku.ehime.jp/site/userguide/info.html"

SOURCES = {
    "waste-page.html": WASTE_URL,
    "resource-page.html": RESOURCE_URL,
    "plastic-page.html": PLASTIC_URL,
    "battery-page.html": BATTERY_URL,
    "large-waste-page.html": LARGE_WASTE_URL,
    "item-table.pdf": ITEM_TABLE_URL,
    "sorting-guide.pdf": SORTING_GUIDE_URL,
    "plastic-guide.pdf": PLASTIC_GUIDE_URL,
    "battery-guide.pdf": BATTERY_GUIDE_URL,
    "copyright.html": COPYRIGHT_URL,
}

AREA_DEFINITIONS = (
    {
        "slug": "izumi",
        "name": "泉地区",
        "display_name": "泉地区",
        "address_labels": ["泉地区"],
        "rules": {"burnable": "月・木", "nonburnable": "火", "pet_bottles": "第1・第3金", "containers": "水"},
    },
    {
        "slug": "aiji",
        "name": "愛治地区",
        "display_name": "愛治地区",
        "address_labels": ["愛治地区"],
        "rules": {"burnable": "月・木", "nonburnable": "月", "pet_bottles": "第2・第4金", "containers": "水"},
    },
    {
        "slug": "yoshifuji",
        "name": "好藤地区",
        "display_name": "好藤地区（年則を含む）",
        "address_labels": ["好藤地区", "年則"],
        "rules": {"burnable": "火・金", "nonburnable": "月", "pet_bottles": "第2・第4金", "containers": "水"},
    },
    {
        "slug": "mishima",
        "name": "三島地区",
        "display_name": "三島地区",
        "address_labels": ["三島地区"],
        "rules": {"burnable": "火・金", "nonburnable": "木", "pet_bottles": "第2・第4金", "containers": "水"},
    },
    {
        "slug": "hiyoshi",
        "name": "日吉地区",
        "display_name": "日吉地区",
        "address_labels": ["日吉地区"],
        "rules": {"burnable": "火・金", "nonburnable": "木", "pet_bottles": "第1・第3金", "containers": "水"},
    },
    {
        "slug": "chikanaga-sakae-asahi",
        "name": "近永地区 栄町・旭町",
        "display_name": "近永地区（栄町・旭町）",
        "address_labels": ["栄町", "旭町"],
        "rules": {"burnable": "火・金", "nonburnable": "火", "pet_bottles": "第1・第3金", "containers": "水"},
    },
    {
        "slug": "chikanaga-central",
        "name": "近永地区 中心部",
        "display_name": "近永地区（新町・本町・南町・鬼北の里）",
        "address_labels": ["新町", "本町", "南町", "鬼北の里"],
        "rules": {"burnable": "月・木", "nonburnable": "火", "pet_bottles": "第1・第3金", "containers": "水"},
    },
    {
        "slug": "chikanaga-outer",
        "name": "近永地区 周辺部",
        "display_name": "近永地区（牛野川・水分・北川・成川・今在家・奈良・芝・中野川・永野市）",
        "address_labels": ["牛野川", "水分", "北川", "成川", "今在家", "奈良", "芝", "中野川", "永野市"],
        "rules": {"burnable": "月・木", "nonburnable": "金", "pet_bottles": "第1・第3金", "containers": "水"},
    },
)

WEEKDAYS = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}

# The item table predates the two April 2026 collection changes below.  Keep
# its audited rows, but let the newer official notices win for affected items.
RECHARGEABLE_BATTERY_ITEMS = {
    "乾電池（充電式）",
    "充電式電池",
    "デジタルカメラ・ビデオのバッテリー",
    "電池（充電式）",
    "ニカド電池",
    "ニッケル水素電池",
    "リチウムイオン電池",
}

# These names occur both in the old item table and as examples in the current
# clean-plastic guide.  The drop-off route is conditional: the plastic must be
# clean/dry and must not match an exclusion in the guide.  Burnable collection
# remains valid, so clean_plastic is an option rather than a replacement.
CLEAN_PLASTIC_ITEMS = {
    "アイスクリーム容器・ふた",
    "衣装ケース（紙製・プラ製）",
    "計量カップ(プラ製）",
    "クリアファイル",
    "くし（髪結い櫛）",
    "ケチャップの容器ふた（プラ製）",
    "コップ（紙製・プラ製）",
    "ごみ箱（竹製・プラ製）",
    "粉石けんの計量スプーン（プラ製）",
    "粉ミルクのスプーン（プラ製）",
    "皿・サラダボウル",
    "三角コーナー（プラ製）",
    "シャンプーのボトル・容器",
    "スナック菓子の袋",
    "スプーン",
    "スポンジ",
    "洗剤の容器",
    "洗面器（プラ製・木製）",
    "タッパー",
    "たまごパック",
    "詰め替えパック・ボトル",
    "DVD・DVDケース",
    "豆腐のパック",
    "バケツ",
    "歯ブラシ",
    "ハンガー（木・プラ製）",
    "パンの外袋",
    "ペットボトルのキャップ",
    "ペットボトルのラベル",
    "風呂いす（木製・プラ製）",
    "ボウル（プラ製・木製）",
    "ポリバケツ",
    "マヨネーズの容器",
    "ヨーグルトのふた",
    "ヨーグルトの外フイルム",
    "ヨーグルトの容器（紙製・プラ製）",
    "リンスの容器",
    "レジ袋",
    "レトルト食品パック・袋",
    "下敷き（文房具）",
    "じょうろ（プラ製）",
    "ざる",
    "弁当・惣菜の容器（紙製・プラ製）",
}

BATTERY_NOTE = (
    "令和8年4月から小型充電式電池を分別回収。端子をビニールテープ等で絶縁し、"
    "環境保全課、各公民館または日吉支所の事務所へ持ち込む。取り外せないものは"
    "小型家電として出し、膨らんだ電池は回収ボックスに入れず事務所へ直接持ち込む。"
)
CLEAN_PLASTIC_NOTE = (
    "プラスチック部分がきれいで乾いており、厚さ5mm以上・強化プラスチック・"
    "在宅医療品・電化製品などの対象外条件に当たらない場合は、令和8年4月開始の"
    "きれいなプラスチック拠点回収も利用できる。従来どおり可燃ごみでも回収される。"
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
        raise ValueError("Unexpected Kihoku source location")
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
    print(f"Saved {len(records)} official Kihoku source files")


def source_records():
    records = read(DATA / "source/downloads.json")
    for record in records:
        path = DATA / "source" / record["file"]
        if not path.exists() or digest(path) != record["sha256"]:
            raise ValueError(f"Kihoku source changed: {record['file']}")
    return {record["file"]: record for record in records}


def source_candidate():
    records = source_records()
    return {
        "schema_version": 1,
        "municipality_id": CITY,
        "version": VERSION,
        "valid_from": "2026-04-01",
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
        raise ValueError("Fetched Kihoku originals differ from reviewed source pins")
    return source_records()


def validate_schedule_source():
    text = (DATA / "source/waste-page.html").read_text(encoding="utf-8")
    required = (
        "泉地区、愛治地区、近永地区（栄町、旭町以外）",
        "好藤地区、三島地区、日吉地区、近永地区（栄町・旭町）",
        "新町・本町・南町・栄町・旭町・鬼北の里",
        "牛野川・水分・北川・成川・今在家・奈良・芝・中野川・永野市",
        "毎月　第１、第３金曜日",
        "毎月　第２、第４金曜日",
    )
    missing = [value for value in required if value not in text]
    if missing:
        raise ValueError(f"Official Kihoku schedule text changed: {missing}")


def _rule_dates(rule: str, start: date, end: date):
    if rule.startswith("第"):
        numbers, weekday_name = rule[1:].split("金")[0], "金"
        occurrences = [int(value) for value in numbers.split("・第")]
        weekday = WEEKDAYS[weekday_name]
        values = []
        cursor = date(start.year, start.month, 1)
        while cursor <= end:
            month_values = []
            day = cursor
            while day.month == cursor.month:
                if day.weekday() == weekday:
                    month_values.append(day)
                day += timedelta(days=1)
            values.extend(
                month_values[number - 1]
                for number in occurrences
                if start <= month_values[number - 1] <= end
            )
            cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        return values
    weekdays = {WEEKDAYS[value] for value in rule.split("・")}
    values = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() in weekdays:
            values.append(cursor)
        cursor += timedelta(days=1)
    return values


def inspect_calendars():
    validate_schedule_source()
    valid_from = date(2026, 4, 1)
    valid_to = date(2026, 12, 31)
    areas = []
    calendars = {}
    reviewed_areas = []
    for definition in AREA_DEFINITIONS:
        identifier = f"kihoku-{definition['slug']}"
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
            "rule_profile_id": "kihoku",
            "address_labels": definition["address_labels"],
            "needs_local_confirmation": True,
            "source_url": WASTE_URL,
        })
        calendars[identifier] = {
            "source_url": WASTE_URL,
            "verification_status": "rule_derived",
            "days": days,
            "exceptions": [],
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
        "source_url": WASTE_URL,
        "areas": reviewed_areas,
        "verification": {
            "method": "Official HTML district tables converted from weekly and first/third or second/fourth Friday rules",
            "coverage": "Eight district combinations; burnable, nonburnable, PET bottles and bottles/cans",
            "limitations": "The official page publishes recurring weekdays, not a dated annual calendar; temporary holiday and year-end changes are not inferred",
            "reviewed_at": "2026-11-03",
        },
    }
    return areas, calendars, reviews


def ensure_tsv():
    source = DATA / "source/item-table.pdf"
    target = DATA / "generated/item-table.tsv"
    marker = DATA / "generated/item-table-source.json"
    source_hash = digest(source)
    if marker.exists() and target.exists():
        recorded = read(marker)
        if recorded.get("source_sha256") == source_hash and recorded.get("pdf_pages") == "3-31":
            return target
    executable = shutil.which("pdftotext")
    if not executable:
        raise RuntimeError("Poppler pdftotext is required for the Kihoku item table")
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        executable, "-enc", "UTF-8", "-tsv", str(source), str(target)
    ], check=True)
    write(marker, {"source_sha256": source_hash, "pdf_pages": "3-31", "extractor": "Poppler TSV"})
    return target


def extracted_items():
    from kihoku_pdf import extract_items
    return extract_items(ensure_tsv(), DATA / "source/item-table.pdf")


def item_review(rows=None):
    rows = extracted_items() if rows is None else rows
    return {
        "schema_version": 1,
        "version": VERSION,
        "official_items": len(rows),
        "items_sha256": value_digest(rows),
        "primary_categories": dict(Counter(row["category"] for row in rows)),
        "records_with_notes": sum(bool(row["note"]) for row in rows),
        "source_pdf_pages": "3-31",
        "extraction_method": "Poppler TSV coordinates over the official two-column ruled item table",
        "current_rule_supplements": [
            "Clean plastic drop-off effective 2026-04-01",
            "Separated lithium-ion and other small rechargeable-battery collection effective 2026-04-01",
        ],
        "reviewed_at": "2026-11-03",
    }


def _item_row(item, rules):
    category = item["category"]
    source_category = item["source_category"]
    note = item["note"]
    source_url = f"{ITEM_TABLE_URL}#page={item['source_page']}"
    options = []
    if item["item"] in RECHARGEABLE_BATTERY_ITEMS:
        category = "rechargeable_batteries"
        source_category = "小型充電式電池（令和8年4月更新）"
        note = BATTERY_NOTE
        source_url = f"{BATTERY_GUIDE_URL}#page=2"
    elif category == "burnable" and (
        item["item"] in CLEAN_PLASTIC_ITEMS
        or "プラ製" in item["item"]
        or "プラスチック" in item["item"]
    ):
        options = ["clean_plastic"]
        source_category = f"{source_category}／きれいなプラスチック（令和8年4月更新）"
        note = " ".join(part for part in (note, CLEAN_PLASTIC_NOTE) if part)
        source_url = PLASTIC_GUIDE_URL
    definition = rules["categories"][category]
    return {
        "item_id": item["item_id"],
        "item": item["item"],
        "category": category,
        "category_display": definition["name"],
        "note": note,
        "search_text": " ".join((item["item"], source_category, note)).strip(),
        "disposal_instructions": definition.get("instructions", ""),
        "category_options": json.dumps(options, ensure_ascii=False),
        "source_url": source_url,
        "source_category": source_category,
    }


def item_rows():
    rules = read(DATA / "official_rules.json")
    extracted = extracted_items()
    extracted_names = {item["item"] for item in extracted}
    missing = (RECHARGEABLE_BATTERY_ITEMS | CLEAN_PLASTIC_ITEMS) - extracted_names
    if missing:
        raise ValueError(f"Kihoku current-rule item names missing from extraction: {sorted(missing)}")
    return [_item_row(item, rules) for item in extracted]


def bulky_config():
    return {
        "municipality_id": CITY,
        "municipality_name": "鬼北町",
        "collection_frequency": "予約制・水曜日（祝日を除く）",
        "reception_hours": "役場への直接持込は開庁時間内。広域環境センターの受付条件は公式案内で確認",
        "collection_rules": "指定袋に入らない粗大ごみは、役場環境保全課・日吉支所または広域環境センターへ直接持ち込むか、町委託業者・許可業者へ依頼します。",
        "fee_structure_type": "item_or_weight_based",
        "application_method": "phone_or_direct_dropoff",
        "phone_number": "0895-45-1111",
        "web_form_url": None,
        "information_url": LARGE_WASTE_URL,
        "steps": [
            {"step_number": 1, "title": "処理方法を選ぶ", "description": "自分で持ち込むか、環境保全課の予約回収または町の許可業者への依頼を選びます。"},
            {"step_number": 2, "title": "料金と受付条件を確認", "description": "町で処理する粗大ごみは1品500円からです。広域環境センターは10kgあたり50円です。"},
            {"step_number": 3, "title": "予約または直接持込", "description": "町委託業者の回収は祝日を除く水曜日限定で、事前予約が必要です。"},
            {"step_number": 4, "title": "運搬を依頼する場合", "description": "運搬手数料または許可業者の見積額を確認してから依頼します。"},
        ],
    }


def build(*, inspect_only: bool = False):
    write(DATA / "generated/sources-candidate.json", source_candidate())
    areas, calendars, calendar_reviews = inspect_calendars()
    write(DATA / "generated/calendar-review-candidate.json", calendar_reviews)
    extracted = extracted_items()
    reviewed_items = item_review(extracted)
    write(DATA / "generated/item-review-candidate.json", reviewed_items)
    if inspect_only:
        write(DATA / "generated/items-candidate.json", extracted)
        print("Wrote Kihoku source/calendar/item candidates; review before build")
        return
    checked_sources()
    if read(DATA / "calendar_reviews.json") != calendar_reviews:
        raise ValueError("Kihoku rule-derived dates differ from the approved review")
    if read(DATA / "item_reviews.json") != reviewed_items:
        raise ValueError("Kihoku PDF-derived items differ from the approved review")
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
        "size_question": "鬼北町の指定ごみ袋に入りますか？素材や汚れ、電池の有無を確認できますか？",
        "knowledge_title": "鬼北町公式家庭ごみ分別早見表",
        "categories": categories,
        "bulky_waste": {"category_code": "bulky", "config": bulky_config()},
    }
    registry = {
        "schema_version": 1,
        "municipality_id": CITY,
        "municipality_name": "鬼北町",
        "prefecture_id": "38",
        "prefecture_name": "愛媛県",
        "version": VERSION,
        "valid_from": calendar_reviews["valid_from"],
        "valid_to": calendar_reviews["valid_to"],
        "collection_areas": areas,
        "calendars": [{"id": area["calendar_id"], "rule_profile_id": "kihoku"} for area in areas],
        "rule_profiles": {"kihoku": profile},
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
        "current_rechargeable_battery_records": sum(
            row["category"] == "rechargeable_batteries" for row in rows
        ),
        "clean_plastic_option_records": sum(
            "clean_plastic" in json.loads(row["category_options"]) for row in rows
        ),
        "source_categories": dict(Counter(row["source_category"] for row in rows)),
        "csv_sha256": digest(target),
    })
    print(f"Built {len(areas)} Kihoku areas, {len(calendars)} calendars and {len(rows)} item records")


def verify():
    checked_sources()
    areas, calendars, calendar_reviews = inspect_calendars()
    if read(DATA / "calendar_reviews.json") != calendar_reviews:
        raise ValueError("Kihoku calendar audit differs from reviewed metadata")
    if read(DATA / "item_reviews.json") != item_review():
        raise ValueError("Kihoku item audit differs from reviewed metadata")
    registry = read(DATA / "registry.json")
    bundle = read(DATA / "generated/calendar-2026.json")
    if registry["collection_areas"] != areas or bundle["calendars"] != calendars:
        raise ValueError("Kihoku registry/calendar differs from official rules")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError("Kihoku CSV differs from the official item extraction")
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
