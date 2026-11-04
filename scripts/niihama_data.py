#!/usr/bin/env python3
"""Reproduce Niihama data offline after fetch. Only explicit index generation is paid.

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
DATA = ROOT / "data/regions/niihama"
CITY = "38205"
VERSION = "niihama-2026.1"
VALID_FROM, VALID_TO = "2026-04-01", "2027-03-31"
GUIDE_URL = "https://www.city.niihama.lg.jp/soshiki/haiki/pamphlet.html"
CALENDAR_URL = "https://www.city.niihama.lg.jp/soshiki/haiki/gomika.html"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def fetch():
    def download(source):
        if (
            urlparse(source["url"]).hostname != "www.city.niihama.lg.jp"
            or Path(source["file"]).name != source["file"]
        ):
            raise ValueError("Unexpected official source location")
        body = urlopen(source["url"], timeout=60).read()
        if hashlib.sha256(body).hexdigest() != source["sha256"]:
            raise ValueError(
                f"Official source changed; review required: {source['file']}"
            )
        target = DATA / "source" / source["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return {**source, "retrieved_at": datetime.now(timezone.utc).isoformat()}

    results = list(
        ThreadPoolExecutor(max_workers=3).map(
            download, read(DATA / "sources.json")["sources"]
        )
    )
    write(DATA / "source/downloads.json", results)
    print(f"Fetched and hash-checked {len(results)} official sources")


def checked_sources():
    sources = read(DATA / "sources.json")["sources"]
    for source in sources:
        if digest(DATA / "source" / source["file"]) != source["sha256"]:
            raise ValueError(
                f"Official source changed; review required: {source['file']}"
            )
    return {source["file"]: source for source in sources}


def classification_options(note, primary):
    """Alternatives must describe the whole item, never removed batteries/caps."""
    from niihama_pdf import CATEGORY_CODES, compact

    note = compact(note)
    patterns = (
        r"30cm(?:以下|超え|超)(?:のプラ・木製|のプラ製|のもの)?は(燃やすごみ|不燃ごみ|大型ごみ|有害ごみ)",
        r"(?:金属製|プラスチック製|プラ製|木製|可燃性|鉄板入り|金属フレーム)は(燃やすごみ|不燃ごみ)",
        r"(?:内側がアルミコーティングのものや500ml未満のもの|金・銀色|水銀式)は(燃やすごみ|有害ごみ)",
        r"それ以外は(大型ごみ)",
        r"30cm以下にたためるものは(燃やすごみ)",
        r"30cm超え?は清掃センターへ(自己搬入)",
    )
    codes = {
        CATEGORY_CODES[label]
        for pattern in patterns
        for label in re.findall(pattern, note)
    }
    if "金属製は不燃ごみ" in note and "30cm以下のプラ" in note:
        codes.add("non_burnable")
    if "※1" in note:
        codes.add("not_collected")
    if primary == "textiles":
        codes.add("burnable")
    return sorted(codes - {primary})


def item_rows():
    from niihama_pdf import extract_items, compact

    rules = read(DATA / "official_rules.json")
    extracted, counts = extract_items(DATA / "source/79661.pdf")
    footnotes = {
        "1": "辞典共通凡例※1：180cm×90cm×90cm以下（金属製の厚み2mm以下）。上限を超えるものは販売店へ相談。",
        "2": "辞典共通凡例※2：切るかたたんで30cm以下のものは燃やすごみ、それ以外は大型ごみ。",
        "3": "辞典共通凡例※3：自己解体の場合のみ搬入可能。",
        "4": "辞典共通凡例※4：自己解体の場合のみ搬入可能（1世帯あたり年間1トンまで）。",
    }
    rows = []
    for row in extracted:
        code = row["category"]
        note = row["source_note"]
        for number in re.findall(r"※([1-4])", compact(note)):
            note += "。" + footnotes[number]
        if code == "textiles":
            note += "。ガイド8ページ：洗濯済みで汚れ・破れのない非冬物等が対象。冬物・制服・汚れ・破れ・濡れたものは燃やすごみ。"
        if row["item"] in ("ボタン電池", "充電式電池"):
            note += "。ガイド13ページは電気店等の店頭回収も案内。端子を絶縁する。辞典の分類は有害ごみ。"
        if row["item"] == "モバイルバッテリー":
            if code != "hazardous":
                raise ValueError("Current battery revision missing")
            note += "2026年1月から有害ごみ。端子を絶縁し透明袋で有害ごみコンテナへ（現行ガイド13ページ）。"
        rows.append(
            {
                "item_id": row["item_id"],
                "item": row["item"],
                "category": code,
                "category_display": rules["categories"][code]["name"],
                "note": note,
                "category_options": json.dumps(classification_options(note, code)),
                "disposal_instructions": rules["categories"][code]["instructions"],
                "source_url": "https://www.city.niihama.lg.jp/uploaded/attachment/79661.pdf#page="
                + str(row["pdf_page"]),
                "source_category": row["source_category"],
            }
        )
    for example in rules["examples"]:
        rows.append(
            {
                "item_id": example["id"],
                "item": example["item"],
                "category": example["category"],
                "category_display": rules["categories"][example["category"]]["name"],
                "note": example["note"],
                "category_options": json.dumps(example.get("category_options", [])),
                "disposal_instructions": "",
                "source_url": example["source_url"],
                "source_category": "公式ガイド確認済み説明例",
            }
        )
    if len({r["item_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate item ID")
    review = {
        "official_items": len(extracted),
        "search_records": len(rows),
        "source_categories": dict(
            sorted(Counter(r["source_category"] for r in extracted).items())
        ),
        "page_counts": counts,
        "conditional_records": sum(r["category_options"] != "[]" for r in rows),
        "rows_sha256": value_digest(rows),
        "dictionary_audit": "20_pages_row_borders_text_counts_raster_categories; common_image_footnotes_visually_reviewed",
    }
    write(DATA / "generated/dictionary-extraction.json", extracted)
    return rows, review


def official_area_rows():
    import html
    from niihama_pdf import compact

    index = (DATA / "source/calendar.html").read_text(encoding="utf-8")
    found = {}
    for match in re.finditer(r"<tr>(.*?)</tr>", index, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", match[1], re.S)
        if len(cells) != 4:
            continue
        link = re.search(r"attachment/(799(?:6[1-9]|7[0-5])\.pdf)", cells[2])
        if link:
            clean = lambda x: compact(html.unescape(re.sub("<[^>]+>", "", x))).replace(
                "\u200b", ""
            )
            found[link[1]] = (clean(cells[0]), clean(cells[1]))
    if len(found) != 15:
        raise ValueError("Official district table changed")
    return found


def inspect_calendars():
    import pymupdf
    from niihama_pdf import calendar_days, compact

    sources = checked_sources()
    areas = read(DATA / "areas.json")["areas"]
    mapping = official_area_rows()
    calendars, reviews, runtime_areas = {}, {}, []
    for area in areas:
        file = area["source_file"]
        source = sources[file]
        if mapping[file] != (
            compact(area["official_calendar_code"]),
            compact(area["name"]),
        ):
            raise ValueError("Official area/calendar table mismatch: " + area["id"])
        text = compact(pymupdf.open(DATA / "source" / file)[0].get_text())
        # PDF target box and the current HTML table independently name each group.
        # Road-side wording differs only in this reviewed abbreviation.
        names = compact(area["pdf_area_names"])
        if names not in text:
            raise ValueError("PDF target box mismatch: " + area["id"] + " " + names)
        days, audit = calendar_days(DATA / "source" / file, area["rule_profile_id"])
        reviews[area["calendar_id"]] = {
            **audit,
            "source_sha256": source["sha256"],
            "days_sha256": value_digest(days),
        }
        calendars[area["calendar_id"]] = {
            "source_url": source["url"],
            "source_sha256": source["sha256"],
            "verification_status": "checked",
            "days": days,
            "exceptions": [],
        }
        runtime_areas.append(
            {
                k: area[k]
                for k in (
                    "id",
                    "name",
                    "display_name",
                    "calendar_id",
                    "rule_profile_id",
                )
            }
            | {"source_url": source["url"], "needs_local_confirmation": True}
        )
    if (
        len({a["id"] for a in runtime_areas}) != 15
        or len({a["display_name"] for a in areas}) != 15
    ):
        raise ValueError("Duplicate or ambiguous area")
    return runtime_areas, calendars, reviews


def address_rows():
    # Exact official town names create candidates only. Road sides, chome,
    # block ranges and the two 宮西町 groups always need user confirmation.
    entries = []
    for area in read(DATA / "areas.json")["areas"]:
        for town in area["name"].split("、"):
            lookup = re.sub(r"[0-9０-９].*|[（(].*", "", town)
            entries.append({"town": town, "lookup_town": lookup, "area_id": area["id"]})
    return {
        "municipality_id": CITY,
        "version": VERSION,
        "source_url": CALENDAR_URL,
        "verification_status": "checked",
        "entries": entries,
    }


def bulky_config():
    steps = [
        (
            "対象と寸法を確認",
            "日常生活の大型ごみが対象。引越し・解体・遺品整理等の大量ごみ、家電リサイクル品や処理困難物等は対象外。180cmちょうどの受付可否は公式資料間で表現が異なるため市へ確認してください。",
        ),
        (
            "電話又は電子申請で申し込む",
            "0897-31-5300（開庁日9〜14時）又は公式サイトの電子申請。1回10点まで、次回申込は2か月後。このアプリから申込みはできません。",
        ),
        (
            "確認はがきと処理券を準備",
            "はがきの収集日・品目・場所を確認し、1点200円の大型ごみ処理券を購入して貼り付けます。搬入用の処理券とは異なります。",
        ),
        (
            "指定日の午前9時までに出す",
            "指定された屋外の場所へ出してください。ステーションの定期収集へ出すものではありません。",
        ),
        (
            "直接搬入する場合",
            "市の清掃センター・最終処分場へ品目別の条件を確認。50kgまで500円、超過10kgごと100円。施設の休業日や搬入制限は公式カレンダーで確認してください。",
        ),
    ]
    return {
        "municipality_id": CITY,
        "municipality_name": "新居浜市",
        "collection_frequency": "事前申込制・有料（1点200円）",
        "reception_hours": "開庁日9:00〜14:00",
        "collection_rules": "確認はがきで指定された日の午前9時までに指定場所へ。通常ステーション収集日は設定しません。",
        "fee_structure_type": "fixed",
        "application_method": "both",
        "web_form_url": "https://www.city.niihama.lg.jp/soshiki/digital/densisinsei.html",
        "phone_number": "0897-31-5300",
        "information_url": "https://www.city.niihama.lg.jp/soshiki/haiki/dasikata-oogata.html",
        "steps": [
            {"step_number": i, "title": title, "description": description}
            for i, (title, description) in enumerate(steps, 1)
        ],
    }


def registry_record(areas):
    rules = read(DATA / "official_rules.json")
    profiles = {}
    for key in ("mainland", "oshima", "besshiyama"):
        categories = {
            code: {k: v for k, v in definition.items() if k != "instructions"}
            for code, definition in rules["categories"].items()
        }
        for definition in categories.values():
            if "collection_type_id" in definition:
                definition["cutoff"] = "09:00" if key == "besshiyama" else "07:30"
        profiles[key] = {
            "items_path": "knowledge/items.csv",
            "embedding_index_path": "knowledge/item_embeddings.npz",
            "index_profile_id": "citywide",
            "calendar_path": "generated/calendar-2026.json",
            "knowledge_title": "新居浜市公式ごみ分別大辞典・2026年度カレンダー",
            "classification_rules": rules["classification_rules"]
            + (
                "\nこの分別設定は別子山地域です。定期収集の搬出期限は当日9時です。"
                if key == "besshiyama"
                else "\nこの分別設定の定期収集の搬出期限は当日7時30分です。"
            ),
            "size_threshold_cm": 30,
            "size_question": "品物の最も長い部分は30cm以下ですか？（取っ手などを含めて測ってください）",
            "categories": categories,
            "bulky_waste": {"category_code": "bulky", "config": bulky_config()},
        }
    return {
        "schema_version": 1,
        "municipality_id": CITY,
        "municipality_name": "新居浜市",
        "prefecture_id": "38",
        "prefecture_name": "愛媛県",
        "version": VERSION,
        "valid_from": VALID_FROM,
        "valid_to": VALID_TO,
        "collection_areas": areas,
        "calendars": [
            {"id": a["calendar_id"], "rule_profile_id": a["rule_profile_id"]}
            for a in areas
        ],
        "rule_profiles": profiles,
    }


def build(*, inspect_only=False):
    areas, calendars, reviews = inspect_calendars()
    rows, item_review = item_rows()
    calendar_review = {"schema_version": 1, "version": VERSION, "calendars": reviews}
    write(DATA / "generated/calendar-review-candidate.json", calendar_review)
    write(DATA / "generated/item-review-candidate.json", item_review)
    if inspect_only:
        print(
            "Inspect candidates and the official PDFs before accepting audit summaries"
        )
        return
    if (
        read(DATA / "calendar_reviews.json") != calendar_review
        or read(DATA / "item_reviews.json") != item_review
    ):
        raise ValueError("Reviewed calendar/dictionary audit differs; review required")
    registry = registry_record(areas)
    write(DATA / "registry.json", registry)
    write(DATA / "generated/addresses.json", address_rows())
    write(
        DATA / "generated/calendar-2026.json",
        {
            k: registry[k]
            for k in ("municipality_id", "version", "valid_from", "valid_to")
        }
        | {"calendars": calendars},
    )
    target = DATA / "knowledge/items.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"Built {len(rows)} search records / {len(areas)} collection groups / {len(calendars)} calendars"
    )


def verify(*, without_index=False):
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.region_registry_service import RegionRegistry
    from app.services.calendar_service import CalendarService
    from app.services.embedding_search_service import EmbeddingSearchService

    areas, calendars, reviews = inspect_calendars()
    rows, item_review = item_rows()
    if (
        read(DATA / "calendar_reviews.json")["calendars"] != reviews
        or read(DATA / "item_reviews.json") != item_review
    ):
        raise ValueError("Official PDF audit differs from reviewed result")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        if list(csv.DictReader(stream)) != rows:
            raise ValueError(
                "CSV differs from official dictionary and reviewed examples"
            )
    registry = RegionRegistry(DATA / "registry.json")
    expected_calendar = {
        k: registry.data[k]
        for k in ("municipality_id", "version", "valid_from", "valid_to")
    } | {"calendars": calendars}
    if (
        registry.data != registry_record(areas)
        or read(DATA / "generated/calendar-2026.json") != expected_calendar
    ):
        raise ValueError("Runtime registry/calendar differs from official sources")
    if read(DATA / "generated/addresses.json") != address_rows():
        raise ValueError("Address candidates differ from the official district table")
    for profile in registry.profiles.values():
        if not without_index:
            import numpy as np

            service = EmbeddingSearchService(
                items_path=profile.items_path,
                embeddings_path=profile.embedding_index_path,
                municipality_id=CITY,
                profile_id="citywide",
                runtime_client=object(),
            )
            if not service.is_ready:
                raise ValueError(
                    "Missing verified Niihama index; registration prohibited"
                )
            with np.load(profile.embedding_index_path, allow_pickle=False) as index:
                if (
                    list(map(str, index["item_ids"])) != [r["item_id"] for r in rows]
                    or not np.isfinite(index["vectors"]).all()
                    or not np.allclose(
                        np.linalg.norm(index["vectors"], axis=1), 1, atol=0.002
                    )
                ):
                    raise ValueError("Invalid Niihama index vectors/row order")
    for area in areas:
        context = registry.resolve(CITY, area["id"])
        calendar = CalendarService(region=context)
        if (
            calendar.availability != "available"
            or calendar.next_collection("bulky") is not None
            or calendar.next_collection("not_collected") is not None
            or calendar.next_collection("self_delivery") is not None
            or calendar.next_collection("consultation") is not None
        ):
            raise ValueError("Invalid collection availability/method")
    result = {
        "official_items": item_review["official_items"],
        "search_records": len(rows),
        "collection_groups": len(areas),
        "official_calendar_pdfs": len(calendars),
        "printed_dates_and_raster_cells": sum(
            r["raster_dates"] for r in reviews.values()
        ),
        "index_checked": not without_index,
        "valid_from": VALID_FROM,
        "valid_to": VALID_TO,
    }
    write(DATA / "generated/verification.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return result


def activate():
    verify()
    catalog_path = ROOT / "data/regions/catalog.json"
    catalog = read(catalog_path)
    entry = {"id": CITY, "registry_path": "niihama/registry.json"}
    existing = next((e for e in catalog["municipalities"] if e["id"] == CITY), None)
    if existing and existing != entry:
        raise ValueError("Existing catalog entry differs")
    if not existing:
        catalog["municipalities"].append(entry)
        write(catalog_path, catalog)
    print("Niihama registered; generate Flutter assets next")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["fetch", "inspect", "build", "verify", "activate"]
    )
    parser.add_argument("--without-index", action="store_true")
    args = parser.parse_args()
    if args.command == "fetch":
        fetch()
    elif args.command == "inspect":
        build(inspect_only=True)
    elif args.command == "build":
        build()
    elif args.command == "verify":
        verify(without_index=args.without_index)
    else:
        activate()
