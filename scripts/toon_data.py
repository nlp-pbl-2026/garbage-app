#!/usr/bin/env python3
"""Reproduce Toon data offline after fetch. Only explicit index generation is paid.

fetch -> audit-images -> inspect -> review pinned audit summaries -> build -> verify -> activate.
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
DATA = ROOT / "data/regions/toon"
CITY = "38215"
VERSION = "toon-2026.1"
VALID_FROM, VALID_TO = "2026-04-01", "2027-03-31"
GUIDE_URL = "https://www.city.toon.ehime.jp/site/141/1130.html"
CALENDAR_URL = "https://www.city.toon.ehime.jp/site/141/31626.html"


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
            urlparse(source["url"]).hostname != "www.city.toon.ehime.jp"
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
    from toon_pdf import CATEGORY_CODES, compact

    note = compact(note)
    patterns = (
        r"(?:大きいもの|大きなもの|大型のもの|小型|汚れたもの|金属製|木製|プラ製|紙製|革製|シート状のもの|無色透明袋に入らないもの|無色透明袋に入るもの|指定ごみ袋に入らないもの|指定ごみ袋に入るもの|指定袋に入らないもの|指定袋に入るもの|コンテナに入らない大型のもの)は[「『](燃やす|紙|びん|金属|ペット|プラ|その他|粗大|水銀|不可)[」』]",
        r"(?:500ml未満、内側が銀色のもの|500ml未満|プラマークがないもの|ビニール・金銀加工しているもの|水銀未使用のもの|金属製以外|それ以外の素材|その他の素材|紙製の容器|プラスチック製のもの|ガラス製|ペットボトルマークのあるもの|針金を使用しているもの|底が金属の場合|中身がくっついているもの)は[「『](燃やす|紙|びん|金属|ペット|プラ|その他|粗大|水銀|不可)[」』]",
        r"(?:無色透明袋に入もの|指定ごみ袋やコンテナに入らないもの)は[「『](その他|粗大)[」』]",
        r"無色透明袋に入らないものは縛って[「『](粗大)[」』]",
        r"(?:金属製|自動車用・バイク用は)[「『](金属|不可)[」』]",
        r"不燃性のものは他のごみと別に単独で小分けにして[「『](その他)[」』]",
        r"電子式は電池を外して[「『](その他)[」』]",
        r"充電式は[「『](不可)[」』]",
    )
    codes = {
        CATEGORY_CODES[label]
        for pattern in patterns
        for label in re.findall(pattern, note)
    }
    if "農業用は不可" in note or "事業用不可" in note or "大人2人" in note:
        codes.add("not_collected")
    return sorted(codes - {primary})


def dictionary_audit(extracted):
    """Independent local OCR plus 13 explicitly reviewed rendered row crops."""
    import pymupdf
    from toon_pdf import compact

    doc = pymupdf.open(DATA / "source/22090.pdf")
    manual = read(DATA / "manual_dictionary_reviews.json")
    misses = []
    matches = 0
    for row in extracted:
        if not row["source_category"]:
            continue
        page = doc[row["pdf_page"] - 1]
        ocr = read(DATA / f'generated/ocr/22090-{row["pdf_page"]:02}.json')
        if ocr["source_sha256"] != digest(DATA / "source/22090.pdf"):
            raise ValueError("Stale dictionary OCR")
        left, top, right, bottom = row["rect"]
        c0, c1 = (156.6, 199.1) if left < 100 else (410.8, 453.4)
        box = pymupdf.Rect(c0, top, c1, bottom)
        observations = [
            o
            for o in ocr["observations"]
            if (
                ob := pymupdf.Rect(
                    o["box"][0] * page.rect.width,
                    o["box"][1] * page.rect.height,
                    o["box"][2] * page.rect.width,
                    o["box"][3] * page.rect.height,
                )
            ).x0
            < box.x1
            and ob.x1 > box.x0
            and ob.y0 < box.y1
            and ob.y1 > box.y0
            and (ob & box).height > min(ob.height, box.height) * 0.6
        ]
        if any(row["source_category"] in compact(o["text"]) for o in observations):
            matches += 1
        elif (
            manual["entries"].get(row["item_id"], {}).get("category")
            == row["source_category"]
        ):
            misses.append(row["item_id"])
        else:
            raise ValueError("Dictionary OCR/manual audit missing: " + row["item_id"])
    blanks = [r["item_id"] for r in extracted if not r["source_category"]]
    if blanks != list(manual["blank_classification"]):
        raise ValueError("Unexpected blank classification")
    return {
        "classification_rows_checked": matches + len(misses),
        "reviewed_blank_rows": len(blanks),
        "manual_review_ids": misses,
        "method": "glyph_traces_vs_Apple_Vision_OCR_and_reviewed_row_images",
    }


def item_rows():
    from toon_pdf import extract_items

    rules = read(DATA / "official_rules.json")
    extracted, counts = extract_items(DATA / "source/22090.pdf")
    rows = []
    for row in extracted:
        code = row["category"]
        note = row["note"]
        if row["item"] in ("電池（ボタン電池・乾電池）", "ボタン電池"):
            code = "batteries"
        elif row["item"] == "体温計（水銀使用）":
            code = "thermometers"
        elif row["item"] in ("温度計・湿度計（水銀使用）", "水銀血圧計"):
            code = "mercury_instruments"
            note += "。辞典の分類は水銀。地区カレンダーの水銀関連区分との対応は未確認。環境保全課に確認。"
        if not code:
            note += "分類欄は原本でも空欄。推測で確定しない。表示や用途を確認し、別の確認済み根拠がなければ判定保留。"
        options = classification_options(note, code)
        if row["item"] == "携帯電話":
            note += "。2026年3月の公式案内で、リチウムイオン電池等を内蔵する小型家電は市役所環境保全課又は川内支所の回収対象。"
            options.append("small_device_dropoff")
        rows.append(
            {
                "item_id": row["item_id"],
                "item": row["item"],
                "category": code,
                "category_display": (
                    rules["categories"][code]["name"] if code else "分類要確認"
                ),
                "note": note,
                "category_options": json.dumps(options),
                "disposal_instructions": (
                    rules["categories"][code]["instructions"] if code else ""
                ),
                "source_url": "https://www.city.toon.ehime.jp/uploaded/attachment/22090.pdf#page="
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
                "source_category": "公式資料の確認済み説明例",
            }
        )
    if len({r["item_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate item IDs")
    audit = dictionary_audit(extracted)
    review = {
        "official_items": len(extracted),
        "search_records": len(rows),
        "page_counts": counts,
        "source_categories": dict(
            sorted(Counter(r["source_category"] for r in extracted).items())
        ),
        "conditional_records": sum(r["category_options"] != "[]" for r in rows),
        "rows_sha256": value_digest(rows),
        "dictionary_audit": audit,
    }
    write(DATA / "generated/dictionary-extraction.json", extracted)
    return rows, review


def official_area_rows():
    import html
    from toon_pdf import compact

    found = {}
    for file in ("shigenobu.html", "kawauchi.html"):
        index = (DATA / "source" / file).read_text()
        for row in re.findall(r"<tr\b.*?</tr>", index, re.S):
            link = re.search(
                r'href="/uploaded/attachment/(\d+\.pdf)"[^>]*>(.*?)</a>', row, re.S
            )
            if not link:
                continue
            title = compact(html.unescape(re.sub("<[^>]+>", "", link[2]))).split(
                "[PDF"
            )[0]
            found[link[1]] = title
    if len(found) != 32:
        raise ValueError("Official 32-calendar index changed")
    return found


def inspect_calendars():
    import pymupdf
    from toon_pdf import calendar_days, compact

    sources = checked_sources()
    areas = read(DATA / "areas.json")["areas"]
    mapping = official_area_rows()
    calendars, reviews, runtime_areas = {}, {}, []
    for area in areas:
        file = area["source_file"]
        source = sources[file]
        if mapping[file] != compact(area["official_title"]):
            raise ValueError("Official calendar index mismatch: " + file)
        text = compact(pymupdf.open(DATA / "source" / file)[0].get_text())
        if area["rule_profile_id"] == "kawauchi":
            if any(compact(n) not in text for n in area["official_places"]):
                raise ValueError("Kawauchi PDF area box mismatch")
        elif compact(area["pdf_area_title"]) not in text:
            raise ValueError("Shigenobu PDF target name mismatch")
        days, audit = calendar_days(
            DATA / "source" / file, area["rule_profile_id"], DATA / "generated/ocr"
        )
        # Same place name does not identify the West Oka / Takubo variants.
        # Validate their printed weekly pattern in ordinary April independently
        # of the official index link and file name; do not extrapolate dates.
        if "燃やすごみ" in area["name"]:
            expected = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5}
            weekdays = {
                expected[k]
                for k in area["name"].split("燃やすごみ", 1)[1]
                if k in expected
            }
            from datetime import date

            actual = {
                date.fromisoformat(day).weekday()
                for day, streams in days.items()
                if day.startswith("2026-04-") and "burnable" in streams
            }
            if actual != weekdays:
                raise ValueError("Same-town burnable weekday variant mismatch")

        if audit["ocr_unmatched"]:
            raise ValueError("Calendar image audit incomplete: " + file)
        review = {
            k: v
            for k, v in audit.items()
            if k not in ("ocr_labels", "template_labels", "ocr_unmatched")
        }
        review.update(
            image_labels_checked=audit["ocr_labels"] + audit["template_labels"],
            source_sha256=source["sha256"],
            days_sha256=value_digest(days),
        )
        reviews[area["calendar_id"]] = review
        verification = {
            code: {"status": "checked"}
            for code in (
                "burnable",
                "paper",
                "metals",
                "bottles_glass",
                "pet_bottles",
                "plastic_packaging",
                "non_burnable",
                "bulky",
                "mercury",
                "batteries",
            )
        }
        verification["mercury_instruments"] = {
            "status": "unverified",
            "message": "水銀使用の温度計・湿度計・血圧計の収集区分と日程は未確認です。市環境保全課へ確認してください。",
            "source_url": GUIDE_URL,
        }
        calendars[area["calendar_id"]] = {
            "source_url": source["url"],
            "source_sha256": source["sha256"],
            "verification_status": "partially_checked",
            "collection_type_verification": verification,
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
        len({a["id"] for a in runtime_areas}) != 32
        or len({a["display_name"] for a in areas}) != 32
    ):
        raise ValueError("Ambiguous area names/IDs")
    return runtime_areas, calendars, reviews


def address_rows():
    entries = []
    for area in read(DATA / "areas.json")["areas"]:
        places = area["official_places"]
        if area["id"] == "38215-14":
            places = ["牛渕", "堀池"]
        elif area["id"] == "38215-20":
            places = ["野田1丁目", "野田2丁目"]
        elif area["id"] == "38215-21":
            places = ["新村", "野田3丁目"]
        for name in places:
            lookup = re.sub(r"[（(].*|[0-9]+丁目", "", name)
            entries.append({"town": name, "lookup_town": lookup, "area_id": area["id"]})
    return {
        "municipality_id": CITY,
        "version": VERSION,
        "verification_status": "checked",
        "entries": entries,
    }


def bulky_config(profile):
    steps = [
        (
            "対象と大きさを確認",
            "指定袋・45Lの無色透明袋・コンテナに入らないもの等。1m程度、標準的な大人2人で持ち運べるものに限ります。家電リサイクル対象品、処理困難物、事業ごみは出せません。",
        ),
        (
            "地区の収集日を確認",
            "申込制の戸別収集ではなく、選択した地区の粗大ごみ収集日に集積場へ出します。重信は地区で決められた時刻を確認し、川内は当日午前6〜8時に出してください。",
        ),
        (
            "中身が分かる状態で出す",
            "箱に詰めず、電池・バッテリーや燃料を取り除き、布団等は濡れないように出してください。",
        ),
        (
            "大量ごみ・搬入について",
            "引越し等の多量ごみは専門業者へ相談してください。東温市リサイクルセンターは粗大ごみを受け入れません。持込可能な普通ごみの区分別手数料・受付時間は公式案内で確認してください。",
        ),
    ]
    return {
        "municipality_id": CITY,
        "municipality_name": "東温市",
        "collection_frequency": "地区別カレンダーの粗大ごみ収集日",
        "reception_hours": "定期収集のため申込受付なし。相談は市環境保全課へ。",
        "collection_rules": (
            "川内地区は当日午前6〜8時。"
            if profile == "kawauchi"
            else "重信地区は各地区で決められた搬出時刻を確認してください。"
        ),
        "fee_structure_type": "fixed",
        "application_method": "none",
        "phone_number": "089-964-4415",
        "information_url": GUIDE_URL,
        "steps": [
            {"step_number": i, "title": t, "description": d}
            for i, (t, d) in enumerate(steps, 1)
        ],
    }


def registry_record(areas):
    rules = read(DATA / "official_rules.json")
    profiles = {}
    for key in ("shigenobu", "kawauchi"):
        categories = {
            code: {k: v for k, v in value.items() if k != "instructions"}
            for code, value in rules["categories"].items()
        }
        categories["thermometers"]["collection_type_id"] = (
            "batteries" if key == "shigenobu" else "mercury"
        )
        categories["batteries"]["collection_name"] = (
            "乾電池・体温計" if key == "shigenobu" else "乾電池類"
        )
        categories["mercury"]["collection_name"] = (
            "蛍光灯・鏡" if key == "shigenobu" else "蛍光灯・鏡・体温計"
        )
        for definition in categories.values():
            stream = definition.get("collection_type_id")
            if not stream:
                continue
            if key == "shigenobu" and stream not in ("burnable", "paper"):
                definition.pop("cutoff", None)
                definition["cutoff_status"] = "unverified"
                definition["time_note"] = (
                    "搬出時刻は地域で確認してください。期限未確認の区分は、検索の次回収集日を翌日以降で案内します。"
                )
            else:
                definition["start_time"] = "06:00"
                definition["cutoff"] = "08:00"
                definition["time_note"] = "当日の午前6時〜8時の間に出してください。"
        profiles[key] = {
            "items_path": "knowledge/items.csv",
            "embedding_index_path": "knowledge/item_embeddings.npz",
            "index_profile_id": "citywide",
            "calendar_path": "generated/calendar-2026.json",
            "knowledge_title": "東温市公式ごみ分別はやわかり帳・2026年度カレンダー",
            "classification_rules": rules["classification_rules"]
            + "\n現在の分別設定は"
            + (
                "重信地区。水銀式体温計の収集日は乾電池・体温計。燃やす・紙以外の搬出時刻は地域で確認。"
                if key == "shigenobu"
                else "川内地区。水銀式体温計の収集日は蛍光灯・鏡・体温計。全定期区分は午前6〜8時。"
            ),
            "size_question": "指定袋・45Lの無色透明袋又は品目に応じたコンテナに入る大きさですか？",
            "categories": categories,
            "bulky_waste": {"category_code": "bulky", "config": bulky_config(key)},
        }
    return {
        "schema_version": 1,
        "municipality_id": CITY,
        "municipality_name": "東温市",
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


def audit_images():
    """Mac local Vision OCR. Other platforms may use a matching shared audit bundle."""
    import pymupdf, subprocess, shutil, tempfile

    out = DATA / "generated/rendered"
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for source in checked_sources().values():
        if (
            source.get("index_page") not in ("shigenobu.html", "kawauchi.html")
            and source["file"] != "22090.pdf"
        ):
            continue
        doc = pymupdf.open(DATA / "source" / source["file"])
        pages = range(17, 56) if source["file"] == "22090.pdf" else range(len(doc))
        for pi in pages:
            identifier = f'{Path(source["file"]).stem}-{pi+1:02}'
            target = out / (identifier + ".png")
            scale = 2.5 if source["file"] == "22090.pdf" else 2
            doc[pi].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).save(
                target
            )
            manifest.append(
                {
                    "id": identifier,
                    "image": str(target.resolve()),
                    "image_sha256": digest(target),
                    "source_sha256": source["sha256"],
                }
            )
    write(DATA / "generated/ocr-pages.json", manifest)
    if not shutil.which("swiftc"):
        raise RuntimeError(
            "Local Apple Vision requires macOS/Swift; supply the documented matching OCR audit bundle on another OS"
        )
    with tempfile.TemporaryDirectory(prefix="toon-vision-") as temp:
        binary = Path(temp) / "toon-ocr"
        subprocess.run(
            [
                "swiftc",
                str(ROOT / "scripts/toon_ocr.swift"),
                "-o",
                str(binary),
                "-module-cache-path",
                str(Path(temp) / "cache"),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(binary),
                str(DATA / "generated/ocr-pages.json"),
                str(DATA / "generated/ocr"),
            ],
            check=True,
        )


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
                raise ValueError("Missing verified Toon index; registration prohibited")
            with np.load(profile.embedding_index_path, allow_pickle=False) as index:
                if (
                    list(map(str, index["item_ids"])) != [r["item_id"] for r in rows]
                    or not np.isfinite(index["vectors"]).all()
                    or not np.allclose(
                        np.linalg.norm(index["vectors"], axis=1), 1, atol=0.002
                    )
                ):
                    raise ValueError("Invalid Toon index vectors/row order")
    for area in areas:
        context = registry.resolve(CITY, area["id"])
        calendar = CalendarService(region=context)
        if (
            calendar.availability != "partially_available"
            or calendar.next_collection("not_collected") is not None
            or calendar.next_collection("small_device_dropoff") is not None
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
    entry = {"id": CITY, "registry_path": "toon/registry.json"}
    existing = next((e for e in catalog["municipalities"] if e["id"] == CITY), None)
    if existing and existing != entry:
        raise ValueError("Existing catalog entry differs")
    if not existing:
        catalog["municipalities"].append(entry)
        write(catalog_path, catalog)
    print("Toon registered; generate Flutter assets next")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["fetch", "audit-images", "inspect", "build", "verify", "activate"],
    )
    parser.add_argument("--without-index", action="store_true")
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Isolated Toon metadata/source/output directory for reproduction",
    )
    args = parser.parse_args()
    if args.data_dir:
        if args.command == "activate":
            parser.error("activate must use the repository Toon data directory")
        DATA = args.data_dir.resolve()
    if args.command == "fetch":
        fetch()
    elif args.command == "audit-images":
        audit_images()
    elif args.command == "inspect":
        build(inspect_only=True)
    elif args.command == "build":
        build()
    elif args.command == "verify":
        verify(without_index=args.without_index)
    else:
        activate()
