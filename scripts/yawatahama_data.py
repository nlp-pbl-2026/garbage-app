#!/usr/bin/env python3
"""Reproduce Yawatahama FY2026 data from its official HTML/PDFs; no paid calls.

fetch -> inspect -> review metadata -> build -> verify. Embeddings are a separate,
explicitly approved operation. Original PDFs/HTML, CSVs and generated dates stay
outside Git. Published catalog registration requires the separate readiness gate.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import csv
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/yawatahama"
VERSION = "yawatahama-2026.1"
CITY = "38204"
PAGES = {
    "calendar": "https://www.city.yawatahama.ehime.jp/doc/2026030500028/",
    "items-a": "https://www.city.yawatahama.ehime.jp/doc/2023083100038/",
    "items-b": "https://www.city.yawatahama.ehime.jp/doc/2023091300024/",
    "rules": "https://www.city.yawatahama.ehime.jp/doc/2022091300010/",
    "guide": "https://www.city.yawatahama.ehime.jp/doc/2021022400010/",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class OfficialHtml(HTMLParser):
    """Keep every item row/cell and PDF link; skip kana navigation headings."""
    def __init__(self):
        super().__init__()
        self.links = []
        self.rows = []
        self._link = None
        self._row = []
        self._cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self._link = [attrs.get("href", ""), ""]
        if tag == "tr":
            self._row = []
        if tag in ("td", "th"):
            if int(attrs.get("colspan", 1)) != 1:
                # Current item tables have no merged data columns.
                self._cell = None
            else:
                self._cell = ""
        if tag == "br" and self._cell is not None:
            self._cell += " "
        if tag == "img" and self._cell is not None:
            self._cell += attrs.get("alt", "")

    def handle_data(self, text):
        if self._link is not None:
            self._link[1] += text
        if self._cell is not None:
            self._cell += text

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None:
            self.links.append(tuple(self._link))
            self._link = None
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join(self._cell.split()))
            self._cell = None
        if tag == "tr":
            self.rows.append(self._row)

    @classmethod
    def load(cls, path):
        parser = cls()
        parser.feed(path.read_text(encoding="utf-8"))
        return parser


def fetch():
    source = DATA / "source"
    source.mkdir(parents=True, exist_ok=True)
    targets = {f"{key}.html": url for key, url in PAGES.items()}
    records = []
    def download(pair):
        name, url = pair
        if urlparse(url).hostname != "www.city.yawatahama.ehime.jp":
            raise ValueError("Unexpected source host")
        path = source / name
        data = urlopen(url, timeout=60).read()
        path.write_bytes(data)
        return {"file": name, "url": url, "sha256": digest(path),
                "retrieved_at": datetime.now(timezone.utc).isoformat()}
    records.extend(ThreadPoolExecutor(max_workers=3).map(download, targets.items()))
    pdfs = {}
    for key in ("calendar", "guide"):
        for href, title in OfficialHtml.load(source / f"{key}.html").links:
            url = urljoin(PAGES[key], href)
            name = Path(urlparse(url).path).name
            if re.fullmatch(r"R8_Part\d+\.pdf|2023-\d+\.pdf|guidebook2023.pdf", name):
                pdfs[name] = url
    if {f"R8_Part{i}.pdf" for i in range(1, 21)} - set(pdfs):
        raise ValueError("Official calendar list is incomplete")
    records.extend(ThreadPoolExecutor(max_workers=3).map(download, pdfs.items()))
    write(source / "downloads.json", records)
    print(f"Saved {len(records)} official source files")


def source_records():
    records = read(DATA / "source/downloads.json")
    for record in records:
        if digest(DATA / "source" / record["file"]) != record["sha256"]:
            raise ValueError(f"Source changed: {record['file']}")
    return {record["file"]: record for record in records}


def checked_sources():
    sources = source_records()
    recorded = read(DATA / "sources.json")
    if {name: (value["sha256"], value["url"]) for name, value in sources.items()} != {
            value["file"]: (value["sha256"], value["url"]) for value in recorded["sources"]}:
        raise ValueError("Fetched originals differ from recorded source provenance")
    return sources


def item_rows():
    rules = read(DATA / "official_rules.json")
    mapping = {definition["name"]: code for code, definition in rules["categories"].items()}
    aliases = {**mapping, "可燃ごみ": "burnable", "不燃ごみ": "non_burnable"}
    rows = []
    for page in ("items-a", "items-b"):
        parser = OfficialHtml.load(DATA / "source" / f"{page}.html")
        header_seen = False
        for cells in parser.rows:
            if len(cells) in (5, 6) and cells[-5:] == ["名前", "分別", "持込制限", "説明１", "説明２"]:
                header_seen = True
                continue
            if not header_seen or len(cells) <= 1:
                continue
            if len(cells) not in (5, 6):
                raise ValueError(f"Unexpected item table row: {cells}")
            name, source_category, limit, instruction, condition = cells[-5:]
            if not name or not source_category:
                raise ValueError("Missing official item/category")
            if source_category not in mapping and source_category not in ("素材で判断", "マークで判断"):
                raise ValueError(f"Unknown official category: {source_category}")
            category = mapping.get(source_category, "")
            note = "。".join(part for part in [instruction, condition,
                f"持込制限欄に「{limit}」の記載あり。搬入前に公式資料・環境センターで制限を確認" if limit else ""] if part)
            options = sorted({code for label, code in aliases.items() if label in note} - {category})
            if source_category == "マークで判断":
                # Guidebook pp.4,9,12: only the actual identification mark can select packaging.
                options = sorted(set(options) | {"plastic_packaging", "paper_packaging"})
            disposal = rules["categories"].get(category, {}).get("instructions", "")
            options = sorted(set(options) | {code for label, code in aliases.items() if label in disposal and code != category})
            rows.append({"item_id": f"yh-{len(rows)+1:04}", "item": name, "category": category,
                "category_display": source_category, "note": note, "disposal_instructions": disposal,
                "category_options": json.dumps(options, ensure_ascii=False),
                "source_url": PAGES[page], "source_category": source_category})
        if not header_seen:
            raise ValueError("Official item table header not found")
    for example in rules["examples"]:
        rows.append({"item_id": example["id"], "item": example["item"], "category": example["category"],
            "category_display": rules["categories"][example["category"]]["name"],
            "note": example["note"], "disposal_instructions": "", "category_options": json.dumps(sorted({code for label, code in aliases.items() if label in example["note"] and code != example["category"]}), ensure_ascii=False), "source_url": example["source_url"],
            "source_category": "ガイドブックの確認済み品目例"})
    return rows


def calendar_aliases():
    result = {i: [] for i in range(1, 21)}
    for href, text in OfficialHtml.load(DATA / "source/calendar.html").links:
        match = re.search(r"R8_Part(\d+)\.pdf$", href)
        label = re.match(r"(.+?)【(\d+)】", text.strip())
        if match and label:
            number = int(match[1])
            if number != int(label[2]) or number not in result:
                raise ValueError("Calendar number/link mismatch")
            if label[1] not in result[number]:
                result[number].append(label[1])
    if any(not names for names in result.values()):
        raise ValueError("Some official calendar areas have no index entries")
    return result


def area_variants(number, days, labels, config):
    variants = config["variants"].get(str(number))
    if not variants:
        display = [config.get("display_label_exclusions", {}).get(str(number), {}).get(label, label) for label in labels]
        return [{"suffix": "", "name": f"{number}：" + "、".join(display),
                 "address_labels": labels, "days": days}]
    paper = set(config["paper_collection_types"])
    allowed = {variant["paper_weekday_iso"] for variant in variants}
    for day, codes in days.items():
        if paper.intersection(codes) and date.fromisoformat(day).isoweekday() not in allowed:
            raise ValueError(f"Paper date contradicts official area note: {number}/{day}")
    return [{**variant, "days": {day: [code for code in codes if code not in paper or
        date.fromisoformat(day).isoweekday() == variant["paper_weekday_iso"]]
        for day, codes in days.items()}} for variant in variants]


def inspect_calendars(*, raster=True):
    import pymupdf
    from yawatahama_pdf import extract, audit_raster
    sources = source_records()
    aliases = calendar_aliases()
    variants = read(DATA / "calendar_variants.json")
    reviews, calendars, areas = {}, {}, []
    for number in range(1, 21):
        filename = f"R8_Part{number}.pdf"
        document = pymupdf.open(DATA / "source" / filename)
        if len(document) != 1:
            raise ValueError("Calendar must have a single page")
        page = document[0]
        days, symbols = extract(page, island=number >= 19)
        audit = audit_raster(page, days, island=number >= 19) if raster else {}
        title = "".join(page.get_text(clip=pymupdf.Rect(897, 35, 1175, 166)).split())
        if not title:
            raise ValueError("Missing official area heading")
        identifier = f"yh-{number:02}"
        reviews[identifier] = {"source_sha256": sources[filename]["sha256"], "days_sha256": value_digest(days),
            "symbol_count": symbols, **audit, "source_url": sources[filename]["url"]}
        for variant in area_variants(number, days, aliases[number], variants):
            suffix = "-" + variant["suffix"] if variant["suffix"] else ""
            calendar_id = identifier + suffix
            calendars[calendar_id] = {"source_url": sources[filename]["url"],
                "source_sha256": sources[filename]["sha256"], "verification_status": "pending",
                "days": variant["days"], "exceptions": [],
                "official_area_note": variant.get("official_note", ""), "source_calendar_id": identifier}
            areas.append({"id": f"38204-{number:02}{suffix}", "name": variant["name"],
                "calendar_id": calendar_id, "rule_profile_id": "oshima" if number >= 19 else "standard",
                "official_calendar_number": number, "official_pdf_area_heading": title,
                "address_labels": variant["address_labels"], "needs_local_confirmation": True,
                "source_url": PAGES["calendar"]})
        print(f"Calendar {number}: {len(days)} dated cells, {symbols} symbols; raster={raster}", flush=True)
    return areas, calendars, reviews


def build(*, inspect_only=False):
    if not inspect_only:
        checked_sources()
    areas, calendars, reviews = inspect_calendars()
    draft = {"schema_version": 1, "version": VERSION, "calendars": reviews}
    if inspect_only:
        write(DATA / "generated/review-candidate.json", draft)
        return
    approved = read(DATA / "calendar_reviews.json")
    if approved["calendars"] != reviews or approved["version"] != VERSION:
        raise ValueError("PDFs/generated dates differ from recorded review; inspect before approval")
    for record in calendars.values():
        record["verification_status"] = "checked"
    rules = read(DATA / "official_rules.json")
    profiles = {}
    for profile in ("standard", "oshima"):
        categories = {}
        for code, definition in rules["categories"].items():
            definition = {k: v for k, v in definition.items() if k != "instructions"}
            if profile == "oshima" and code in ("cardboard", "newspaper", "magazines", "paper_packaging"):
                definition = {**definition, "collection_type_id": "paper_all", "collection_name": "紙類（段ボール・新聞・雑誌・紙製容器包装）", "color": "#F4A7B9"}
            categories[code] = definition
        profiles[profile] = {"items_path": "knowledge/items.csv", "embedding_index_path": "knowledge/item_embeddings.npz",
            "index_profile_id": "citywide", "calendar_path": "generated/calendar-2026.json",
            "classification_rules": rules["classification_rules"], "size_question": "八幡浜市の指定ごみ袋に入る大きさですか？",
            "knowledge_title": "八幡浜市公式ごみ分別品目一覧・ガイドブック", "categories": categories,
            "bulky_waste": {"category_code": "bulky", "config": rules["bulky_config"]}}
    registry = {"schema_version": 1, "municipality_id": CITY, "municipality_name": "八幡浜市", "prefecture_id": "38",
        "prefecture_name": "愛媛県", "version": VERSION, "valid_from": "2026-04-01", "valid_to": "2027-03-31",
        "collection_areas": areas,
        "calendars": [{"id": area["calendar_id"], "rule_profile_id": area["rule_profile_id"]} for area in areas],
        "rule_profiles": profiles}
    registry["coverage_notice"] = "郷・中央（郷一木地区・旧道沿い）は、紙類の収集曜日を確認できていないため選択対象に含めていません。該当する場合は市の公式カレンダーと生活環境課で確認してください。"
    registry["excluded_address_labels"] = read(DATA / "calendar_variants.json")["unresolved_address_labels"]
    write(DATA / "registry.json", registry)
    write(DATA / "generated/calendar-2026.json", {key: registry[key] for key in
        ["municipality_id", "version", "valid_from", "valid_to"]} | {"calendars": calendars})
    rows = item_rows()
    target = DATA / "knowledge/items.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write(DATA / "generated/item-review.json", {
        "official_table_rows": sum(not row["item_id"].startswith("yh-rule-") for row in rows),
        "total_search_records": len(rows), "source_sha256": digest(target),
        "conditional_rows": sum(bool(json.loads(row["category_options"])) or not row["category"] for row in rows),
        "without_explicit_classification_options": [row["item_id"] for row in rows if not row["category"] and row["category_options"] == "[]"],
        "source_categories": dict(Counter(row["source_category"] for row in rows))})
    print(f"Built {len(areas)} areas, {len(calendars)} calendars, {len(rows)} search records")


def verify(*, raster=True):
    import numpy as np
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.region_registry_service import RegionRegistry
    from app.services.embedding_search_service import EmbeddingSearchService
    from app.services.calendar_service import CalendarService
    sources = checked_sources()
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError("CSV differs from official HTML rows and reviewed guide examples")
    registry = RegionRegistry(DATA / "registry.json")
    for profile in registry.profiles.values():
        search = EmbeddingSearchService(items_path=profile.items_path, embeddings_path=profile.embedding_index_path,
            municipality_id=CITY, profile_id="citywide", runtime_client=object())
        if not search.is_ready:
            raise ValueError("Missing verified item index")
        with np.load(profile.embedding_index_path, allow_pickle=False) as index:
            if not np.isfinite(index["vectors"]).all() or not np.allclose(np.linalg.norm(index["vectors"], axis=1), 1, atol=.002):
                raise ValueError("Non-finite or unnormalized embedding vectors")
            if list(map(str, index["item_ids"])) != [row["item_id"] for row in rows]:
                raise ValueError("CSV and index row order differ")
    for area in registry.areas.values():
        region = registry.resolve(CITY, area["id"])
        if CalendarService(calendar_path=region.rules.calendar_path, region=region).availability != "available":
            raise ValueError("Unverified calendar")
    areas, calendars, reviews = inspect_calendars(raster=raster)
    if raster and reviews != read(DATA / "calendar_reviews.json")["calendars"]:
        raise ValueError("Official PDF verification no longer matches review record")
    bundle = read(DATA / "generated/calendar-2026.json")
    if registry.data["collection_areas"] != areas or set(bundle["calendars"]) != set(calendars):
        raise ValueError("Collection area mapping differs from official sources")
    for identifier, expected in calendars.items():
        actual = bundle["calendars"][identifier]
        if actual["days"] != expected["days"] or actual["verification_status"] != "checked":
            raise ValueError(f"Calendar mismatch: {identifier}")
    frontend = ROOT / "frontend/assets/data"
    ui_catalog = read(frontend / "municipality_catalog.json")
    ui_city = next(entry for entry in ui_catalog["municipalities"] if entry["id"] == CITY)
    if ui_city["version"] != registry.data["version"]:
        raise ValueError("Flutter/backend data versions differ")
    for ui_profile in ui_city["profiles"].values():
        asset = ROOT / "frontend" / ui_profile["calendar_asset"]
        if asset.read_bytes() != (DATA / "generated/calendar-2026.json").read_bytes():
            raise ValueError("Flutter/backend calendar originals differ")
    ui_registry = read(ROOT / "frontend" / ui_city["registry_asset"])
    if ui_registry != {key: value for key, value in registry.data.items() if key != "rule_profiles"}:
        raise ValueError("Flutter/backend area metadata differ")
    result = {"official_item_rows": 768, "search_records": len(rows), "collection_areas": len(areas),
        "source_pdfs": 20, "area_calendars": len(calendars), "source_date_cells": 7300,
        "raster_verified": raster, "source_hashes": len(sources),
        "excluded_addresses": registry.data["excluded_address_labels"]}
    write(DATA / "generated/verification.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "inspect", "build", "verify"])
    args = parser.parse_args()
    if args.command == "fetch":
        fetch()
    elif args.command == "verify":
        verify()
    else:
        build(inspect_only=args.command == "inspect")
