#!/usr/bin/env python3
"""Fetch, audit, build and verify pinned FY2026 Kumakogen data without paid APIs.

The index is supplied separately or explicitly generated after paid approval.
Neither missing data nor a changed official source is silently accepted.
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
import subprocess
import sys
from urllib.parse import urlparse
from urllib.request import urlopen

from kumakogen_pdf import (
    CATEGORY_CODES,
    compact,
    extract_items,
    timetable,
    expand_ics,
    ics_events,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/kumakogen"
CITY, VERSION = "38386", "kumakogen-2026.1"
VALID_FROM, VALID_TO = "2026-04-01", "2027-03-31"
PDF_URL = "https://www.kumakogen.jp/uploaded/attachment/14587.pdf"
GUIDE_URL = "https://www.kumakogen.jp/uploaded/attachment/7553.pdf"


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


def normalize_source(body, source):
    if source.get("canonicalization") in {
        "icalendar_without_dtstamp_lf",
        "icalendar_unfold_sort_events_without_dtstamp_lf",
    }:
        text = body.decode("utf-8-sig").replace("\r\n", "\n")
        text = re.sub(r"(?m)^DTSTAMP:[^\n]*\n", "", text)
        if (
            source["canonicalization"]
            == "icalendar_unfold_sort_events_without_dtstamp_lf"
        ):
            text = re.sub(r"\n[ \t]", "", text)
            header = text.split("BEGIN:VEVENT\n", 1)[0]
            blocks = re.findall(r"BEGIN:VEVENT\n(.*?)END:VEVENT\n", text, re.S)
            if (
                not blocks
                or not text.endswith("END:VCALENDAR\n")
                or "BEGIN:VTIMEZONE" in text
            ):
                raise ValueError("Unexpected public-calendar structure")
            events = sorted(
                "BEGIN:VEVENT\n"
                + "\n".join(sorted(b.strip().splitlines()))
                + "\nEND:VEVENT\n"
                for b in blocks
            )
            text = header + "".join(events) + "END:VCALENDAR\n"
        return text.encode("utf-8")
    return body


def fetch():
    def download(source):
        host = urlparse(source["url"]).hostname
        if (
            host not in {"www.kumakogen.jp", "calendar.google.com"}
            or Path(source["file"]).name != source["file"]
        ):
            raise ValueError("Unexpected official source location")
        body = normalize_source(urlopen(source["url"], timeout=60).read(), source)
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
    print(f"Fetched/hash-checked {len(results)} sources")


def checked_sources():
    for source in read(DATA / "sources.json")["sources"]:
        if digest(DATA / "source" / source["file"]) != source["sha256"]:
            raise ValueError(f"Source changed or missing: {source['file']}")


def audit_images():
    import pymupdf

    checked_sources()
    output = DATA / "generated/ocr"
    output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, pages in [("dictionary", range(15, 45)), ("calendar-2026", range(4))]:
        source = DATA / "source" / (name + ".pdf")
        doc = pymupdf.open(source)
        for pi in pages:
            key = f"{name}-p{pi+1:02}"
            image = output / (key + ".png")
            doc[pi].get_pixmap(matrix=pymupdf.Matrix(4, 4), alpha=False).save(image)
            manifest.append(
                {
                    "id": key,
                    "image": str(image.resolve()),
                    "image_sha256": digest(image),
                    "source_sha256": digest(source),
                }
            )
    _, audits = timetable(DATA / "source/calendar-2026.pdf")
    doc = pymupdf.open(DATA / "source/calendar-2026.pdf")
    for audit in audits:
        for cell in audit["cells"]:
            key = f"cell-p{audit['page']}-{cell['kind']}-{cell['row']}-{cell['column_month']:02}"
            image = output / (key + ".png")
            # Date alone, excluding the ruled border and the neighbouring cell.
            rect = pymupdf.Rect(cell["rect"]) + (0.8, 0.8, -0.8, -0.8)
            doc[audit["page"] - 1].get_pixmap(
                matrix=pymupdf.Matrix(5, 5), clip=rect, alpha=False
            ).save(image)
            manifest.append(
                {
                    "id": key,
                    "image": str(image.resolve()),
                    "image_sha256": digest(image),
                    "source_sha256": digest(DATA / "source/calendar-2026.pdf"),
                }
            )
    manifest_path = output / "manifest.json"
    write(manifest_path, manifest)
    binary = Path("/private/tmp/kumakogen-ocr")
    subprocess.run(
        [
            "swiftc",
            "-module-cache-path",
            "/private/tmp/kumakogen-swift-cache",
            str(ROOT / "scripts/toon_ocr.swift"),
            "-o",
            str(binary),
        ],
        check=True,
    )
    subprocess.run([str(binary), str(manifest_path), str(output)], check=True)


def checked_ocr(key, source):
    record = read(DATA / "generated/ocr" / (key + ".json"))
    image = DATA / "generated/ocr" / (key + ".png")
    if record["source_sha256"] != digest(DATA / "source" / source) or record[
        "image_sha256"
    ] != digest(image):
        raise ValueError("OCR source/render changed")
    return record["observations"]


def image_audit():
    """OCR first; unread text must match an OCR-verified raster or manual crop.

    Raster comparison never changes the extracted label. A different nearest
    label or a large distance requires an explicitly reviewed exception.
    """
    import numpy as np
    import pymupdf
    from PIL import Image

    def shape(image):
        array = np.asarray(image.convert("RGB"))
        mask = np.max(array, axis=2) < 110
        yy, xx = np.where(mask)
        if not len(xx):
            return None
        mask = mask[yy.min() : yy.max() + 1, xx.min() : xx.max() + 1]
        return (
            np.asarray(
                Image.fromarray((mask * 255).astype("uint8")).resize(
                    (100, 50), Image.Resampling.BILINEAR
                )
            ).astype(float)
            / 255
        )

    def nearest(value, templates):
        if value is None:
            return None
        return min(
            (float(np.mean(np.abs(value - other))), label, key)
            for label, examples in templates.items()
            for key, other in examples
        )

    manual = read(DATA / "manual_image_reviews.json")
    if manual["source_sha256"] != {
        name: digest(DATA / "source" / name)
        for name in ("dictionary.pdf", "calendar-2026.pdf")
    }:
        raise ValueError("Manual image review belongs to different source PDFs")
    _, audits = timetable(DATA / "source/calendar-2026.pdf")
    entries = []
    for audit in audits:
        for cell in audit["cells"]:
            key = f"cell-p{audit['page']}-{cell['kind']}-{cell['row']}-{cell['column_month']:02}"
            text = "".join(
                compact(v["text"]) for v in checked_ocr(key, "calendar-2026.pdf")
            )
            entries.append(
                (
                    key,
                    cell["printed"],
                    text,
                    shape(Image.open(DATA / "generated/ocr" / (key + ".png"))),
                )
            )
    templates = {}
    for key, label, text, value in entries:
        if label == text and value is not None:
            templates.setdefault(label, []).append((key, value))
    date_raster, date_manual = [], []
    for key, label, text, value in entries:
        if label == text:
            continue
        best = nearest(value, templates)
        if best and best[1] == label and best[0] < 0.045:
            date_raster.append(key)
        elif manual["calendar_cells"].get(key) == label:
            date_manual.append(key)
        else:
            raise ValueError(f"Unverified rendered date: {key} {label!r} OCR={text!r}")
    if set(date_manual) != set(manual["calendar_cells"]):
        raise ValueError("Stale manual date exceptions")
    extracted, _ = extract_items(DATA / "source/dictionary.pdf")
    doc = pymupdf.open(DATA / "source/dictionary.pdf")
    observations = {
        pi: checked_ocr(f"dictionary-p{pi:02}", "dictionary.pdf")
        for pi in range(16, 46)
    }
    rows, templates = [], {}
    for row in extracted:
        page = doc[row["pdf_page"] - 1]
        x0, y0, x1, y1 = row["category_rect"]
        seen = "".join(
            v["text"]
            for v in observations[row["pdf_page"]]
            if x0 / page.rect.width
            <= (v["box"][0] + v["box"][2]) / 2
            < x1 / page.rect.width
            and y0 / page.rect.height
            <= (v["box"][1] + v["box"][3]) / 2
            < y1 / page.rect.height
        )
        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(4, 4),
            clip=pymupdf.Rect(x0 + 16, y0 + 1, x1 - 0.8, y1 - 1),
            alpha=False,
        )
        value = shape(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        passed = row["source_category"] in compact(seen)
        if passed and value is not None:
            templates.setdefault(row["source_category"], []).append(
                (row["item_id"], value)
            )
        rows.append((row, value, passed))
    dictionary_raster, dictionary_manual, flowchart = [], [], []
    for row, value, passed in rows:
        if passed:
            continue
        if row["category"] == "consult":
            x0, y0, x1, y1 = row["rect"]
            seen = "".join(
                v["text"]
                for v in observations[row["pdf_page"]]
                if x0 / 595.276 <= (v["box"][0] + v["box"][2]) / 2 < x1 / 595.276
                and y0 / 841.89 <= (v["box"][1] + v["box"][3]) / 2 < y1 / 841.89
            )
            if "木のフロー" in seen:
                flowchart.append(row["item_id"])
                continue
        best = nearest(value, templates)
        if best and best[1] == row["source_category"] and best[0] < 0.06:
            dictionary_raster.append(row["item_id"])
        elif manual["dictionary_rows"].get(row["item_id"]) == row["source_category"]:
            dictionary_manual.append(row["item_id"])
        else:
            raise ValueError(
                f"Unverified rendered dictionary category: {row['item_id']}"
            )
    if set(dictionary_manual) != set(manual["dictionary_rows"]):
        raise ValueError("Stale dictionary manual exceptions")
    result = {
        "calendar_cells": len(entries),
        "calendar_ocr": sum(a == b for _, a, b, _ in entries),
        "calendar_raster": date_raster,
        "calendar_manual": date_manual,
        "dictionary_rows": len(rows),
        "dictionary_ocr": sum(passed for _, _, passed in rows),
        "dictionary_raster": dictionary_raster,
        "dictionary_flowchart_row_ocr": flowchart,
        "dictionary_manual": dictionary_manual,
        "scope": "All printed monthly dates and dictionary classifications; not a full independent transcription of item names/notes. Weekly rules compared with the official linked current calendars.",
    }
    write(DATA / "generated/image-audit-candidate.json", result)
    if result != read(DATA / "image_reviews.json"):
        raise ValueError("Independent image audit differs from reviewed summary")
    return result


def classification_options(note, primary):
    note = compact(note)
    options = set()
    # Explicitly named alternatives are permissions, never unconditional rules.
    condition = (
        r"袋に入(?:れば|るものは|るもの|らないものは|らないもの|らない場合は|らなければ|らないければ)|袋で運べないものは|"
        r"汚れ(?:の落ちないものは|がとれないものは|が取れないものは|たものは|がとれなければ)|"
        r"(?:プラ|プラスチック|金属|木|紙|和紙|ナイロン|幼児用プラ)製(?:のもの)?は|プラスチックは|"
        r"乳白色のものは|金網は|電気製品は|電気式は|電動式は(?:電池をはずし(?:て)?)?|"
        r"ビニール(?:など)?で加工(?:した|している)ものは|他人に見られたくない場合は|"
        r"プライバシー対策の場合は|プライバシー保護のため|プラマークがあれば|"
        r"ポータブルプレイヤーは|おもりを使っているものは|電気・電池を使用するものは|"
        r"食品トレイ以外で「プラ」マークの表記がないものは|土鍋、ガラス製は|"
        r"紙製のものはリサイクル困難なため|針金を使用しているものは|鏡付のコンパクトは|"
        r"アルミ箔のものは|電池を使用するものは、電池をはずして|金属がついていてはずせないものは|"
        r"大人が一人で運べる大きさ、袋で運べるものは"
    )
    branches = re.findall(r"(?:" + condition + r")[「『]([^」』]+)[」』]", note)
    for label in branches:
        label = label.removesuffix("ごみ").removesuffix("類")
        if label == "紙":
            label = "紙類"
        if label in CATEGORY_CODES:
            options.add(CATEGORY_CODES[label])
    if "金網は「燃えないごみ」又は「粗大ごみ」" in note:
        options.update(["non_burnable", "bulky"])
    if "素材に応じて" in note or (
        primary == "bulky" and "袋に入" in note and not options
    ):
        options.update(["burnable", "non_burnable"])
    if "排出禁止" in note:
        options.add("not_collected")
    return sorted(options - {primary})


def item_rows():
    extracted, counts = extract_items(DATA / "source/dictionary.pdf")
    rules = read(DATA / "official_rules.json")
    rows = []
    for raw in extracted:
        row = {
            "item_id": raw["item_id"],
            "item": raw["item"],
            "category": raw["category"],
            "note": raw["note"],
            "source_url": GUIDE_URL + f"#page={raw['pdf_page']}",
            "source_category": raw["source_category"],
        }
        options = classification_options(row["note"], row["category"])
        # These conditions apply to the requested item itself. Keep them in
        # item evidence, not only in the broad stream preparation instructions.
        if raw["category"] == "pet_bottles":
            row[
                "note"
            ] += "。汚れが落ちないものは「燃えるごみ」。PET本体と外したキャップ・ラベルを区別する。"
            options = sorted(set(options + ["burnable"]))
        elif raw["category"] == "bottles":
            row["note"] += "。乳白色又は汚れの取れないびんは「燃えないごみ」。"
            options = sorted(set(options + ["non_burnable"]))
        elif raw["category"] == "clothes":
            row["note"] += "。汚れが落ちない・破れたものは「燃えるごみ」。"
            options = sorted(set(options + ["burnable"]))
        if raw["category"] == "consult":
            row[
                "note"
            ] += "。木の直径・厚さ15cm以内で長さ50cm程度（板は各辺50cm程度）にできれば燃えるごみ。それ以外は環境衛生センターへ相談する。"
            options = ["burnable"]
        # Later official battery advice supersedes the old dictionary. Preserve
        # the raw extraction, source category and revision provenance separately.
        if raw["item"] == "リチウムイオン電池":
            row["note"] = (
                "2026年10月14日公式案内：機器から取り外した正常な電池は資源ごみ。破損・変形・膨張した電池又は取り外せない機器は環境衛生センターへ直接持込。状態と取り外し可否が不明なら確認する。"
            )
            options = ["direct_delivery"]
            row["source_url"] = "https://www.kumakogen.jp/soshiki/4/27263.html"
        if raw["category"] == "small_appliances":
            row[
                "note"
            ] += "。2026年10月14日案内を優先し、リチウムイオン電池を取り外せない機器や破損・変形・膨張した電池は環境衛生センターへ直接持込。電池の有無と取り外し可否を確認する。"
            options = sorted(set(options + ["direct_delivery"]))
        row.update(
            category_display=rules["categories"][row["category"]]["name"],
            category_options=json.dumps(options),
            disposal_instructions=rules["categories"][row["category"]]["instructions"],
        )
        rows.append(row)
    for example in rules["examples"]:
        rows.append(
            {
                "item_id": example["id"],
                "item": example["item"],
                "category": example["category"],
                "note": example["note"],
                "source_url": example["source_url"],
                "source_category": "公式資料の確認済み説明例",
                "category_display": rules["categories"][example["category"]]["name"],
                "category_options": json.dumps(example.get("category_options", [])),
                "disposal_instructions": "",
            }
        )
    if len({r["item_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate item IDs")
    review = {
        "official_items": len(extracted),
        "search_records": len(rows),
        "page_counts": counts,
        "source_categories": dict(
            sorted(Counter(r["source_category"] for r in extracted).items())
        ),
        "rows_sha256": value_digest(rows),
        "reverse_painted_category_icons": sum(
            r["category"] != "consult" for r in extracted
        ),
        "flowchart_reference_rows": sum(r["category"] == "consult" for r in extracted),
    }
    write(DATA / "generated/dictionary-extraction.json", extracted)
    return rows, review


def calendar_records():
    from collection_recurrence import expand

    pages, audits = timetable(DATA / "source/calendar-2026.pdf")
    config = read(DATA / "areas.json")
    resource_codes = [
        k
        for k, v in read(DATA / "official_rules.json")["categories"].items()
        if v.get("resource_day")
    ]
    calendars, areas, reviews = {}, [], []
    for spec in config["areas"]:
        pi = spec["pdf_page"] - 1
        days = expand(
            VALID_FROM,
            VALID_TO,
            [{"weekdays": spec["burnable_weekdays"], "types": ["burnable"]}],
            collection_types=["burnable", "non_burnable"],
        )
        weekly = spec.get("non_burnable_weekdays")
        if weekly:
            other = expand(
                VALID_FROM,
                VALID_TO,
                [{"weekdays": weekly, "types": ["non_burnable"]}],
                collection_types=["non_burnable"],
            )
            for day, codes in other.items():
                days[day] = sorted(set(days[day] + codes))
        else:
            for day in pages[pi]["non_burnable"][spec["non_burnable_row"]]["dates"]:
                days[day].append("non_burnable")
        # Only explicit weekly EXDATEs in the officially linked calendar are
        # used as exceptions. Past years' dates are never shifted into FY2026.
        events = ics_events(DATA / "source" / spec["ics_file"])
        exclusions = []
        for event in events:
            if not event.get("RRULE", [""])[0].startswith("FREQ=WEEKLY"):
                continue
            stream = {
                "可燃ごみ（燃えるごみ）": "burnable",
                "不燃ごみ（燃えないごみ）": "non_burnable",
            }.get(event.get("SUMMARY", [""])[0])
            if not stream:
                raise ValueError("Unexpected weekly public-calendar stream")
            for field in event.get("EXDATE", []):
                for raw in field.split(","):
                    day = datetime.strptime(raw, "%Y%m%d").date().isoformat()
                    if day in days and stream in days[day]:
                        days[day].remove(stream)
                        exclusions.append({"date": day, "stream": stream})
        all_dates = pages[pi]["all_resources"][spec["resource_row"]]["dates"]
        extra_dates = pages[pi]["plastic_cans"][spec["resource_row"]]["dates"]
        for day in all_dates:
            days[day] = sorted(set(days[day] + resource_codes))
        for day in extra_dates:
            days[day] = sorted(set(days[day] + ["plastic_packaging", "cans"]))
        linked = expand_ics(DATA / "source" / spec["ics_file"])
        expected = {
            "burnable": sorted(d for d, c in days.items() if "burnable" in c),
            "non_burnable": sorted(d for d, c in days.items() if "non_burnable" in c),
            "all_resources": sorted(all_dates),
            "plastic_cans": sorted(extra_dates),
        }
        differences = {
            key: {
                "pdf_only": sorted(set(expected[key]) - set(linked[key])),
                "linked_only": sorted(set(linked[key]) - set(expected[key])),
            }
            for key in expected
            if expected[key] != linked[key]
        }
        # Monthly data always comes from the FY2026 PDF. ICS is an independent
        # comparison and may contain a documented recurring-rule discrepancy.
        if any(key in differences for key in ("burnable", "non_burnable")):
            raise ValueError(f"Weekly public-calendar/PDF mismatch: {spec['id']}")
        days = {d: sorted(set(c)) for d, c in days.items()}
        record = {
            "verification_status": "checked",
            "source_url": PDF_URL + f"#page={pi+1}",
            "days": days,
        }
        calendar_id = spec["calendar_id"]
        if calendar_id in calendars and calendars[calendar_id] != record:
            raise ValueError("Shared calendar IDs have different dates")
        calendars[calendar_id] = record
        areas.append(
            {
                k: spec[k]
                for k in (
                    "id",
                    "name",
                    "display_name",
                    "calendar_id",
                    "rule_profile_id",
                )
            }
            | {"source_url": record["source_url"], "needs_local_confirmation": True}
        )
        reviews.append(
            {
                "area_id": spec["id"],
                "days": len(days),
                "collection_days": sum(bool(c) for c in days.values()),
                "weekly_exclusions": sorted(
                    exclusions, key=lambda e: (e["date"], e["stream"])
                ),
                "public_calendar_differences": differences,
                "days_sha256": value_digest(days),
            }
        )
    return (
        areas,
        calendars,
        {
            "timetable_pages": 4,
            "monthly_date_cells": sum(a["monthly_date_cells"] for a in audits),
            "areas": reviews,
        },
        audits,
    )


def registry_record(areas):
    rules = read(DATA / "official_rules.json")
    categories = {
        k: {
            a: b
            for a, b in v.items()
            if a not in {"instructions", "resource_day", "source_url"}
        }
        for k, v in rules["categories"].items()
    }
    return {
        "schema_version": 1,
        "municipality_id": CITY,
        "municipality_name": "久万高原町",
        "prefecture_id": "38",
        "prefecture_name": "愛媛県",
        "version": VERSION,
        "valid_from": VALID_FROM,
        "valid_to": VALID_TO,
        "collection_areas": areas,
        "calendars": [
            {"id": key, "rule_profile_id": "citywide"}
            for key in dict.fromkeys(a["calendar_id"] for a in areas)
        ],
        "rule_profiles": {
            "citywide": {
                "items_path": "knowledge/items.csv",
                "embedding_index_path": "knowledge/item_embeddings.npz",
                "index_profile_id": "citywide",
                "calendar_path": "generated/calendar-2026.json",
                "knowledge_title": "久万高原町公式家庭ごみ分別辞典・現行案内",
                "classification_rules": rules["classification_rules"],
                "size_question": "45リットルの指定ごみ袋に入る大きさですか？",
                "categories": categories,
                "bulky_waste": {
                    "category_code": "bulky",
                    "config": rules["bulky_config"],
                },
            }
        },
    }


def build(inspect_only=False):
    checked_sources()
    areas, calendars, calendar_review, audits = calendar_records()
    rows, item_review = item_rows()
    write(DATA / "generated/calendar-review-candidate.json", calendar_review)
    write(DATA / "generated/item-review-candidate.json", item_review)
    if inspect_only:
        print(
            f"Review {len(rows)} items / {len(areas)} areas / {len(calendars)} calendars against sources"
        )
        return
    if calendar_review != read(DATA / "calendar_reviews.json") or item_review != read(
        DATA / "item_reviews.json"
    ):
        raise ValueError(
            "Reviewed extraction differs; inspect and review changed sources"
        )
    image_audit()
    registry = registry_record(areas)
    write(DATA / "registry.json", registry)
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
    print(f"Built {len(rows)} items / {len(areas)} areas / {len(calendars)} calendars")


def verify(without_index=False):
    checked_sources()
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.region_registry_service import RegionRegistry
    from app.services.calendar_service import CalendarService
    from app.services.embedding_search_service import EmbeddingSearchService

    areas, calendars, review, _ = calendar_records()
    rows, item_review = item_rows()
    if review != read(DATA / "calendar_reviews.json") or item_review != read(
        DATA / "item_reviews.json"
    ):
        raise ValueError("Official extraction/review mismatch")
    image_audit()
    registry = RegionRegistry(DATA / "registry.json")
    expected = {
        k: registry.data[k]
        for k in ("municipality_id", "version", "valid_from", "valid_to")
    } | {"calendars": calendars}
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        if list(csv.DictReader(stream)) != rows:
            raise ValueError("CSV/source mismatch")
    if read(
        DATA / "generated/calendar-2026.json"
    ) != expected or registry.data != registry_record(areas):
        raise ValueError("Runtime calendar/registry mismatch")
    if not without_index:
        import numpy as np

        profile = registry.profiles["citywide"]
        service = EmbeddingSearchService(
            items_path=profile.items_path,
            embeddings_path=profile.embedding_index_path,
            municipality_id=CITY,
            profile_id="citywide",
            runtime_client=object(),
        )
        if not service.is_ready:
            raise ValueError("Missing/mismatched Kumakogen-specific index")
        with np.load(profile.embedding_index_path, allow_pickle=False) as index:
            if (
                list(map(str, index["item_ids"])) != [r["item_id"] for r in rows]
                or not np.isfinite(index["vectors"]).all()
                or not np.allclose(
                    np.linalg.norm(index["vectors"], axis=1), 1, atol=0.002
                )
            ):
                raise ValueError("Index IDs/vectors mismatch")
    for area in areas:
        cal = CalendarService(region=registry.resolve(CITY, area["id"]))
        if (
            cal.availability != "available"
            or cal.next_collection("bulky") is not None
            or cal.next_collection("direct_delivery") is not None
        ):
            raise ValueError("Invalid availability/disposal method")
    result = {
        "official_items": item_review["official_items"],
        "search_records": len(rows),
        "collection_areas": len(areas),
        "calendars": len(calendars),
        "monthly_pdf_date_cells": review["monthly_date_cells"],
        "area_dates": len(areas) * 365,
        "index_checked": not without_index,
    }
    write(DATA / "generated/verification.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return result


def activate():
    verify()
    path = ROOT / "data/regions/catalog.json"
    catalog = read(path)
    entry = {"id": CITY, "registry_path": "kumakogen/registry.json"}
    current = next((e for e in catalog["municipalities"] if e["id"] == CITY), None)
    if current and current != entry:
        raise ValueError("Existing catalog entry differs")
    if not current:
        catalog["municipalities"].append(entry)
        write(path, catalog)
    print(
        "Kumakogen registered; generate only its Flutter assets with --merge-existing"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["fetch", "audit-images", "inspect", "build", "verify", "activate"],
    )
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--without-index", action="store_true")
    args = parser.parse_args()
    if args.data_dir:
        if args.command == "activate":
            parser.error("activate must use repository data")
        DATA = args.data_dir.resolve()
    if args.command == "inspect":
        build(inspect_only=True)
    elif args.command == "verify":
        verify(without_index=args.without_index)
    else:
        globals()[args.command.replace("-", "_")]()
