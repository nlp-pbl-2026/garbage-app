#!/usr/bin/env python3
"""Reproduce Ozu FY2026 regional data from official HTML/PDF sources.

The workflow is fetch -> inspect -> review metadata -> build -> verify.  Source
documents, derived CSV/calendar JSON and embeddings remain outside Git.  Titan
embedding generation is a separate paid operation and is never called here.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/ozu"
CITY = "38207"
VERSION = "ozu-2026.1"
PAGES = {
    "ozu": "https://www.city.ozu.ehime.jp/soshiki/kankyo/65775.html",
    "nagahama": "https://www.city.ozu.ehime.jp/soshiki/kankyo/65772.html",
    "hijikawa": "https://www.city.ozu.ehime.jp/soshiki/kankyo/65773.html",
    "kawabe": "https://www.city.ozu.ehime.jp/soshiki/kankyo/65774.html",
    "dictionary": "https://www.city.ozu.ehime.jp/soshiki/kankyo/0745.html",
}
DICTIONARY_PDF = "https://www.city.ozu.ehime.jp/uploaded/attachment/46102.pdf"
REGION_NAMES = {"ozu": "大洲地域", "nagahama": "長浜地域", "hijikawa": "肱川地域", "kawabe": "河辺地域"}
REGION_CODES = {"ozu": "main", "nagahama": "nagahama", "hijikawa": "hijikawa", "kawabe": "kawabe"}
EXPECTED_CALENDARS = {"ozu": 14, "nagahama": 2, "hijikawa": 12, "kawabe": 1}


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


class OfficialHtml(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.links = []
        self._row = None
        self._cell = None
        self._link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self._row = []
        if tag in ("td", "th") and self._row is not None:
            self._cell = {"text": "", "links": []}
        if tag == "a":
            self._link = [attrs.get("href", ""), ""]
        if tag == "br" and self._cell is not None:
            self._cell["text"] += " "

    def handle_data(self, text):
        if self._cell is not None:
            self._cell["text"] += text
        if self._link is not None:
            self._link[1] += text

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None:
            link = tuple(self._link)
            self.links.append(link)
            if self._cell is not None:
                self._cell["links"].append(link)
            self._link = None
        if tag in ("td", "th") and self._cell is not None:
            self._cell["text"] = " ".join(self._cell["text"].split())
            self._row.append(self._cell)
            self._cell = None
        if tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    @classmethod
    def load(cls, path: Path):
        parser = cls()
        parser.feed(path.read_text(encoding="utf-8"))
        return parser


def calendar_entries(data_path: Path = DATA):
    entries = []
    for region in REGION_NAMES:
        parser = OfficialHtml.load(data_path / "source" / f"{region}.html")
        found = []
        for cells in parser.rows:
            if len(cells) < 3:
                continue
            calendar_link = next(
                (link for cell in cells for link in cell["links"]
                 if re.search(r"/uploaded/attachment/(\d+)\.pdf$", link[0])
                 and "令和８年度" in link[1]),
                None,
            )
            if calendar_link is None:
                continue
            match = re.search(r"/uploaded/attachment/(\d+)\.pdf$", calendar_link[0])
            number_text = cells[0]["text"].translate(str.maketrans("０１２３４５６７８９", "0123456789"))
            if not number_text.isdigit():
                raise ValueError(f"Invalid official calendar number: {cells[0]['text']}")
            title = re.sub(r"\s*\[PDFファイル.*$", "", calendar_link[1]).strip()
            area = cells[-1]["text"].strip()
            if not area:
                raise ValueError(f"Missing official area for {calendar_link[0]}")
            attachment = match.group(1)
            found.append({
                "region": region,
                "region_name": REGION_NAMES[region],
                "region_code": REGION_CODES[region],
                "number": int(number_text),
                "title": title,
                "area": area,
                "filename": f"calendar-{attachment}.pdf",
                "url": urljoin(PAGES[region], calendar_link[0]),
                "page_url": PAGES[region],
            })
        found.sort(key=lambda entry: entry["number"])
        if len(found) != EXPECTED_CALENDARS[region] or [entry["number"] for entry in found] != list(range(1, len(found) + 1)):
            raise ValueError(f"Official {region} calendar table is incomplete")
        entries.extend(found)
    if len({entry["filename"] for entry in entries}) != sum(EXPECTED_CALENDARS.values()):
        raise ValueError("Official calendar attachment IDs are not unique")
    return entries


def _download(pair):
    filename, url = pair
    if urlparse(url).hostname != "www.city.ozu.ehime.jp":
        raise ValueError("Unexpected official source host")
    path = DATA / "source" / filename
    request = Request(url, headers={"User-Agent": "garbage-app-data-builder/1.0"})
    data = urlopen(request, timeout=90).read()
    path.write_bytes(data)
    return {"file": filename, "url": url, "sha256": digest(path),
            "retrieved_at": datetime.now(timezone.utc).isoformat()}


def fetch():
    source = DATA / "source"
    source.mkdir(parents=True, exist_ok=True)
    pages = {f"{key}.html": url for key, url in PAGES.items()}
    pages["dictionary.pdf"] = DICTIONARY_PDF
    records = list(ThreadPoolExecutor(max_workers=4).map(_download, pages.items()))
    calendar_targets = {entry["filename"]: entry["url"] for entry in calendar_entries()}
    records.extend(ThreadPoolExecutor(max_workers=4).map(_download, calendar_targets.items()))
    write(source / "downloads.json", records)
    print(f"Saved {len(records)} official source files")


def source_records():
    records = read(DATA / "source/downloads.json")
    for record in records:
        path = DATA / "source" / record["file"]
        if not path.exists() or digest(path) != record["sha256"]:
            raise ValueError(f"Source changed: {record['file']}")
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
        "copyright_url": "https://www.city.ozu.ehime.jp/site/userguide/copyright.html",
        "sources": [records[name] for name in sorted(records)],
    }


def checked_sources():
    actual = source_candidate()
    recorded = read(DATA / "sources.json")
    actual_pairs = {item["file"]: (item["url"], item["sha256"]) for item in actual["sources"]}
    recorded_pairs = {item["file"]: (item["url"], item["sha256"]) for item in recorded["sources"]}
    if actual_pairs != recorded_pairs:
        raise ValueError("Fetched originals differ from recorded source provenance")
    return source_records()


CATEGORY_MAP = {
    "もやすごみ": "burnable",
    "もやさないごみ": "non_burnable",
    "粗大ごみ": "bulky",
    "収集しません": "not_collected",
    "資源（古紙）": "paper_cloth",
    "資源（古布）": "paper_cloth",
    "資源（缶・びん）": "cans_bottles",
    "資源（発泡スチロール）": "pet_styro",
    "資源（ペットボトル）": "pet_styro",
    "有害ごみ": "hazardous",
    "回収ボックス": "collection_box",
    "拠点回収": "collection_box",
}


def category_code(label: str, item: str) -> str:
    if label in CATEGORY_MAP:
        return CATEGORY_MAP[label]
    if label == "資源ごみ":
        return "paper_cloth" if "紙" in item else "cans_bottles"
    if "メーカー回収" in label:
        return "not_collected"
    raise ValueError(f"Unknown official category: {label}")


def _dictionary_words():
    executable = shutil.which("pdftotext")
    if not executable:
        raise RuntimeError("Poppler pdftotext is required to extract the official dictionary table")
    output = DATA / "generated/dictionary.tsv"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([executable, "-enc", "UTF-8", "-f", "6", "-l", "25", "-tsv",
                    str(DATA / "source/dictionary.pdf"), str(output)], check=True)
    with output.open(encoding="utf-8", newline="") as stream:
        return [{**row, "page": int(row["page_num"]), "x": float(row["left"]),
                 "y": float(row["top"])} for row in csv.DictReader(stream, delimiter="\t")
                if row.get("level") == "5"]


def item_rows_from_words(words, rules, *, expected_count: int = 624):
    category_labels = set(CATEGORY_MAP) | {"資源ごみ"}
    categories = [word for word in words if 180 <= word["x"] < 290 and
                  (word["text"] in category_labels or "メーカー回収" in word["text"])]
    categories.sort(key=lambda word: (word["page"], word["y"]))
    if len(categories) != expected_count:
        raise ValueError(f"Expected {expected_count} official category rows, got {len(categories)}")

    base_words = [word for word in words if 65 <= word["x"] < 125 and word["text"].strip()]
    base_words.sort(key=lambda word: (word["page"], word["y"], word["x"]))
    bases = []
    for word in base_words:
        if (bases and bases[-1]["page"] == word["page"] and
                word["y"] - bases[-1]["last_y"] < 14):
            bases[-1]["text"] += word["text"]
            bases[-1]["last_y"] = word["y"]
            bases[-1]["y"] = (bases[-1]["first_y"] + word["y"]) / 2
        else:
            bases.append({"page": word["page"], "text": word["text"],
                          "first_y": word["y"], "last_y": word["y"], "y": word["y"]})
    by_page = defaultdict(list)
    for base in bases:
        by_page[base["page"]].append(base)

    assignments = []
    for category in categories:
        candidates = by_page[category["page"]]
        base = min(candidates, key=lambda item: abs(item["y"] - category["y"]) +
                   (3 if item["y"] > category["y"] else 0))
        assignments.append((category, base))
    category_count_by_base = Counter((base["page"], base["first_y"]) for _, base in assignments)
    used_qualifiers = set()
    rows = []
    aliases = {definition["name"]: code for code, definition in rules["categories"].items()}
    aliases.update({"燃やすごみ": "burnable", "燃やさないごみ": "non_burnable"})

    for category, base in assignments:
        qualifier_candidates = [word for word in words
                                if word["page"] == category["page"] and 125 <= word["x"] < 180
                                and abs(word["y"] - category["y"]) < 34]
        qualifier = ""
        close_qualifiers = sorted({word["text"] for word in qualifier_candidates
                                   if abs(word["y"] - category["y"]) <= 16})
        base_key = (base["page"], base["first_y"])
        if category_count_by_base[base_key] > 1 and qualifier_candidates and len(close_qualifiers) < 2:
            available = [word for word in qualifier_candidates
                         if (word["page"], word["x"], word["y"], word["text"]) not in used_qualifiers]
            if available:
                selected = min(available, key=lambda word: abs(word["y"] - category["y"]))
                used_qualifiers.add((selected["page"], selected["x"], selected["y"], selected["text"]))
                qualifier = selected["text"]
        item = base["text"] + (f"（{qualifier}）" if qualifier else "")
        label = category["text"]
        code = category_code(label, item)
        nearby = [word for word in words if word["page"] == category["page"] and word["x"] >= 290
                  and abs(word["y"] - category["y"]) <= 16]
        nearby.sort(key=lambda word: (word["y"], word["x"]))
        note_parts = []
        for word in nearby:
            if word["text"] not in note_parts:
                note_parts.append(word["text"])
        if len(close_qualifiers) >= 2:
            note_parts.insert(0, "素材・種類: " + " / ".join(close_qualifiers))
        elif qualifier:
            note_parts.insert(0, f"素材・種類: {qualifier}")
        note = " ".join(note_parts)
        options = sorted({alias_code for alias, alias_code in aliases.items()
                          if alias_code != code and (f"「{alias}」" in note or
                              f"{alias}袋に入れば" in note or f"又は {alias}袋" in note)})
        rows.append({
            "item_id": f"ozu-{len(rows) + 1:04}",
            "item": item,
            "category": code,
            "category_display": label,
            "note": note,
            "search_text": " ".join(part for part in (item, " ".join(close_qualifiers), label) if part),
            "disposal_instructions": rules["categories"][code].get("instructions", ""),
            "category_options": json.dumps(options, ensure_ascii=False),
            "source_url": DICTIONARY_PDF,
            "source_category": label,
        })
    return rows


def item_rows():
    rules = read(DATA / "official_rules.json")
    rows = item_rows_from_words(_dictionary_words(), rules)
    for example in rules["examples"]:
        rows.append({
            "item_id": example["id"], "item": example["item"], "category": example["category"],
            "category_display": rules["categories"][example["category"]]["name"],
            "note": example["note"], "search_text": example["item"],
            "disposal_instructions": rules["categories"][example["category"]].get("instructions", ""),
            "category_options": "[]", "source_url": example["source_url"],
            "source_category": "公式分別ルール",
        })
    return rows


def inspect_calendars():
    import pymupdf
    from ozu_pdf import extract

    sources = source_records()
    reviews, calendars, areas = {}, {}, []
    for entry in calendar_entries():
        region_code = entry["region_code"]
        calendar_id = f"ozu-{region_code}-{entry['number']:02}"
        document = pymupdf.open(DATA / "source" / entry["filename"])
        days, audit = extract(document)
        review = {
            "source_sha256": sources[entry["filename"]]["sha256"],
            "days_sha256": value_digest(days),
            **audit,
            "source_url": entry["url"],
        }
        reviews[calendar_id] = review
        calendars[calendar_id] = {
            "source_url": entry["url"], "source_sha256": review["source_sha256"],
            "verification_status": "pending", "days": days, "exceptions": [],
        }
        profile = "nagahama" if entry["region"] == "nagahama" else "standard"
        areas.append({
            "id": f"38207-{region_code}-{entry['number']:02}",
            "name": f"{entry['region_name']} {entry['number']}：{entry['title'].removeprefix('令和８年度').strip()}",
            "display_name": entry["area"], "calendar_id": calendar_id,
            "rule_profile_id": profile, "official_calendar_number": entry["number"],
            "official_calendar_title": entry["title"], "address_labels": [entry["area"]],
            "needs_local_confirmation": True, "source_url": entry["page_url"],
        })
        print(f"{calendar_id}: {audit['family']}, {audit['mapped_category_marks']} category marks", flush=True)
    names = [area["display_name"] for area in areas]
    if len(areas) != 29 or any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError("Ozu collection area names must be 29 nonempty unique values")
    return areas, calendars, reviews


def _profile(rules, profile_id: str):
    categories = {code: {key: value for key, value in definition.items() if key != "instructions"}
                  for code, definition in rules["categories"].items()}
    bulky = dict(rules["bulky_config"])
    if profile_id == "nagahama":
        bulky.update({"phone_number": "0893-52-1113",
                      "collection_rules": rules["nagahama_bulky_collection_rules"]})
    return {
        "items_path": "knowledge/items.csv",
        "embedding_index_path": "knowledge/item_embeddings.npz",
        "index_profile_id": "citywide",
        "calendar_path": "generated/calendar-2026.json",
        "classification_rules": rules["classification_rules"],
        "size_question": "大洲市の指定ごみ袋に入る大きさですか？",
        "knowledge_title": "大洲市公式ごみ分別辞典",
        "categories": categories,
        "bulky_waste": {"category_code": "bulky", "config": bulky},
    }


def build(*, inspect_only: bool = False):
    write(DATA / "generated/sources-candidate.json", source_candidate())
    if not inspect_only:
        checked_sources()
    areas, calendars, reviews = inspect_calendars()
    candidate = {
        "schema_version": 1,
        "version": VERSION,
        "calendars": reviews,
        "verification": {
            "method": "PDF calendar rules reconstructed from vector lines; repeated collection icons mapped by vector signatures or embedded-image dimensions",
            "coverage": "29 PDFs x 365 dates = 10585 dated cells, including blank days",
            "visual_review": "Representative Ozu, Nagahama, Hijikawa and Kawabe first pages compared date-by-date for April 2026",
            "limitations": "Annual PDFs are authoritative for planned dates; later weather, disaster or emergency changes are not inferred",
            "reviewed_at": "2026-11-02"
        }
    }
    if inspect_only:
        write(DATA / "generated/review-candidate.json", candidate)
        print("Wrote source and calendar review candidates; review before build")
        return
    approved = read(DATA / "calendar_reviews.json")
    if approved["version"] != VERSION or approved["calendars"] != reviews:
        raise ValueError("PDF-derived dates differ from the approved calendar review")
    for record in calendars.values():
        record["verification_status"] = "checked"
    rules = read(DATA / "official_rules.json")
    registry = {
        "schema_version": 1, "municipality_id": CITY, "municipality_name": "大洲市",
        "prefecture_id": "38", "prefecture_name": "愛媛県", "version": VERSION,
        "valid_from": "2026-04-01", "valid_to": "2027-03-31",
        "collection_areas": areas,
        "calendars": [{"id": area["calendar_id"], "rule_profile_id": area["rule_profile_id"]}
                      for area in areas],
        "rule_profiles": {profile: _profile(rules, profile) for profile in ("standard", "nagahama")},
    }
    write(DATA / "registry.json", registry)
    write(DATA / "generated/calendar-2026.json", {
        "municipality_id": CITY, "version": VERSION, "valid_from": "2026-04-01",
        "valid_to": "2027-03-31", "calendars": calendars,
    })
    rows = item_rows()
    target = DATA / "knowledge/items.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write(DATA / "generated/item-review.json", {
        "official_table_rows": 624, "total_search_records": len(rows),
        "source_sha256": digest(target),
        "source_categories": dict(Counter(row["source_category"] for row in rows)),
        "conditional_rows": sum(bool(json.loads(row["category_options"])) for row in rows),
    })
    print(f"Built {len(areas)} areas, {len(calendars)} calendars and {len(rows)} search records")


def verify():
    checked_sources()
    areas, calendars, reviews = inspect_calendars()
    approved = read(DATA / "calendar_reviews.json")
    if reviews != approved["calendars"]:
        raise ValueError("Official PDF verification no longer matches review metadata")
    registry = read(DATA / "registry.json")
    bundle = read(DATA / "generated/calendar-2026.json")
    if registry["collection_areas"] != areas or set(bundle["calendars"]) != set(calendars):
        raise ValueError("Registry/calendar area mapping differs from official HTML")
    for identifier, expected in calendars.items():
        actual = bundle["calendars"][identifier]
        if actual["days"] != expected["days"] or actual["verification_status"] != "checked":
            raise ValueError(f"Calendar mismatch: {identifier}")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        actual_rows = list(csv.DictReader(stream))
    if actual_rows != item_rows():
        raise ValueError("CSV differs from the official dictionary extraction")
    index = DATA / "knowledge/item_embeddings.npz"
    manifest = DATA / "knowledge/index_manifest.json"
    embedding_ready = index.exists() and manifest.exists()
    result = {
        "official_item_rows": 624, "search_records": len(actual_rows),
        "collection_areas": len(areas), "source_pdfs": 30,
        "source_calendar_date_cells": len(calendars) * 365,
        "source_hashes": len(source_records()), "embedding_ready": embedding_ready,
        "catalog_registered": any(item["id"] == CITY for item in read(ROOT / "data/regions/catalog.json")["municipalities"]),
    }
    write(DATA / "generated/verification.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "inspect", "build", "verify"])
    args = parser.parse_args()
    if args.command == "fetch":
        fetch()
    elif args.command == "inspect":
        build(inspect_only=True)
    elif args.command == "build":
        build()
    else:
        verify()
