#!/usr/bin/env python3
"""Reproduce pinned Saijo FY2026 data. All commands here are API-free.

fetch -> audit-images -> inspect -> build -> verify [--without-index]
An approved/shared index is required before activate. Changed official sources
or reviewed extraction results stop the build rather than silently changing data.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse
from urllib.request import urlopen

from saijo_pdf import calendar, dictionary, compact

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/saijo"
CITY, VERSION = "38206", "saijo-2026.1"
VALID_FROM, VALID_TO = "2026-04-01", "2027-03-31"


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def normalize_source(body, source):
    if source.get("canonicalization") == "main_body_utf8":
        return (
            body.split("<!-- main_bodyここから -->".encode(), 1)[1]
            .split("<!-- main_bodyここまで -->".encode(), 1)[0]
            .strip()
        )
    return body


def fetch():
    def download(source):
        if (
            urlparse(source["url"]).hostname
            not in {"www.city.saijo.ehime.jp", "www.sodai-saijo.jp"}
            or Path(source["file"]).name != source["file"]
        ):
            raise ValueError("Unexpected source location")
        body = normalize_source(urlopen(source["url"], timeout=60).read(), source)
        if hashlib.sha256(body).hexdigest() != source["sha256"]:
            raise ValueError(
                "Official source changed; review required: " + source["file"]
            )
        path = DATA / "source" / source["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    list(ThreadPoolExecutor(4).map(download, read(DATA / "sources.json")["sources"]))
    print("Fetched/hash-checked official sources")


def checked_sources():
    for source in read(DATA / "sources.json")["sources"]:
        if digest(DATA / "source" / source["file"]) != source["sha256"]:
            raise ValueError("Source missing or changed: " + source["file"])


def classification_options(note, primary):
    """Only explicit whole-item alternatives, never discarded accessories."""
    options = set()
    for clause in re.split(r"[。\n]", compact(note)):
        if any(
            s in clause
            for s in [
                "キャップとラベルは外し",
                "金属は取り外し",
                "ケースは",
                "蓋は外し",
                "電源コードは",
            ]
        ):
            continue
        if re.search(
            r"(?:製(?:のもの)?は|小さいものは|大きいものは|汚れ.{0,12}ものは|割れたものは|入.{0,20}ものは|れないものは)",
            clause,
        ):
            for label, code in [
                ("もえるごみ", "burnable"),
                ("もえないごみ", "non_burnable"),
                ("粗大ごみ", "bulky"),
            ]:
                if label in clause:
                    options.add(code)
    return sorted(options - {primary})


def item_rows():
    raw, counts = dictionary(DATA / "source/guide-10.pdf")
    rules = read(DATA / "official_rules.json")
    rows = []
    for r in raw:
        category = r["category"]
        note = r["note"]
        if category == "not_collected" and re.search(
            r"(?:クリーンセンター|最終処分場).{0,10}(?:直接搬入|へ)", note
        ):
            category = "direct_delivery"
        options = classification_options(note, category)
        if category == "pet_bottles":
            note += "。飲料用PET本体。汚れが落ちない本体はもえるごみ。外したキャップ・ラベルの分類を本体に適用しない。"
            options = sorted(set(options + ["burnable"]))
        if category == "bottles":
            options = sorted(set(options + ["non_burnable"]))
        if "※３参照" in note or "※3参照" in note:
            note += "。電源コードは根本から50cm以内に切り、もえないごみへ。"
        fee_note = ""
        if r["tickets"] and compact(r["tickets"]) != "-":
            fee_note = (
                "。この品目の処理券："
                + r["tickets"]
                + "（1枚300円。※1は指定袋に入れ口を縛れない場合のみ。受付で条件・枚数を確認）。"
            )
        if "小型家電" in r["note"] or r["item"] == "小型家電":
            note += (
                "。電池を取り外せない場合は現行公式案内に従い市衛生課の窓口に相談する。"
            )
            options = sorted(set(options + ["consult"]))
        if r["item"] == "リチウムイオン電池":
            note += "。2026年2月公式広報でもリチウム蓄電池を拠点窓口又はJBRC回収BOXで回収。取り外せない機器・状態不明の場合は市衛生課へ相談。"
        rows.append(
            dict(
                item_id=r["item_id"],
                item=r["item"],
                category=category,
                note=note,
                source_url="https://www.city.saijo.ehime.jp/uploaded/attachment/61346.pdf#page="
                + str(r["pdf_page"]),
                source_category=r["source_category"],
                category_display=rules["categories"][category]["name"],
                category_options=json.dumps(options),
                disposal_instructions=rules["categories"][category]["instructions"]
                + fee_note,
            )
        )
    for e in rules["examples"]:
        rows.append(
            dict(
                item_id=e["id"],
                item=e["item"],
                category=e["category"],
                note=e["note"],
                source_url=e["source_url"],
                source_category="公式資料の説明例",
                category_display=rules["categories"][e["category"]]["name"],
                category_options=json.dumps(e.get("category_options", [])),
                disposal_instructions="",
            )
        )
    if len({r["item_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate item IDs")
    review = dict(
        official_items=len(raw),
        examples=len(rules["examples"]),
        search_records=len(rows),
        page_counts=counts,
        source_categories=dict(
            sorted(Counter(r["source_category"] for r in raw).items())
        ),
        rows_sha256=value_digest(rows),
    )
    write(DATA / "generated/dictionary-extraction.json", raw)
    return rows, review


def calendar_records():
    config = read(DATA / "areas.json")
    date_review = read(DATA / "date_label_reviews.json")
    if date_review["approval_status"] != "user_approved_geometry_and_legend_correction":
        raise ValueError("Date label corrections need review")
    for name, sha in date_review["source_sha256"].items():
        if digest(DATA / "source" / name) != sha:
            raise ValueError("Date label correction source changed")
    sources = {s["file"]: s["url"] for s in read(DATA / "sources.json")["sources"]}
    calendars, audits, reviews = {}, {}, []
    for spec in config["calendars"]:
        name = spec["source_file"]
        audit = calendar(DATA / "source" / name, date_review["cells"].get(name))
        days = audit["days"]
        # The festival notice is an explicit FY2026 exception, not a recurrence.
        closures = []
        if spec["region"] in {"西条", "丹原"}:
            closures += ["2026-10-15", "2026-10-16"]
        if spec["region"] == "小松":
            closures += ["2026-10-16"]
        if spec["id"] in {"sj-04", "sj-13"}:
            closures += ["2026-10-17"]
        if any(days[d] for d in closures):
            raise ValueError("Festival notice/PDF conflict")
        record = dict(
            verification_status="checked", source_url=sources[name], days=days
        )
        if spec["as_needed_resources"]:
            record["verification_status"] = "partially_checked"
            record["collection_type_verification"] = {
                code: dict(status="checked")
                for code in ["burnable", "non_burnable", "paper", "dry_batteries"]
            }
            for code in ["bottles", "pet_bottles", "spray_cans"]:
                if any(code in c for c in days.values()):
                    raise ValueError("As-needed stream has a guessed date")
                record["collection_type_verification"][code] = dict(
                    status="unverified",
                    message="公式カレンダーでは随時収集とされています。収集日・出す場所は自治会又は西条市へ確認してください。",
                    source_url=sources[name],
                )
        calendars[spec["id"]] = record
        audits[spec["id"]] = audit
        reviews.append(
            dict(
                calendar_id=spec["id"],
                source_file=name,
                dates=len(days),
                collection_days=sum(bool(c) for c in days.values()),
                multiple_stream_days=sum(len(c) > 1 for c in days.values()),
                closed_dates=sorted(
                    d for c in audit["cells"] if c["closed"] for d in c["dates"]
                ),
                festival_closures=closures,
                days_sha256=value_digest(days),
            )
        )
    areas = [
        {k: v for k, v in a.items() if k != "region"}
        | dict(
            source_url=calendars[a["calendar_id"]]["source_url"],
            needs_local_confirmation=True,
        )
        for a in config["areas"]
    ]
    if len({a["display_name"] for a in areas}) != len(areas):
        raise ValueError("Ambiguous duplicate display names")
    return (
        areas,
        calendars,
        dict(
            calendars=reviews,
            calendar_dates=365 * len(calendars),
            selectable_areas=len(areas),
        ),
        audits,
    )


def registry_record(areas):
    rules = read(DATA / "official_rules.json")
    cats = {
        k: {a: b for a, b in v.items() if a not in {"instructions", "source_url"}}
        for k, v in rules["categories"].items()
    }
    return dict(
        schema_version=1,
        municipality_id=CITY,
        municipality_name="西条市",
        prefecture_id="38",
        prefecture_name="愛媛県",
        version=VERSION,
        valid_from=VALID_FROM,
        valid_to=VALID_TO,
        collection_areas=areas,
        calendars=[
            dict(id=k, rule_profile_id="citywide")
            for k in dict.fromkeys(a["calendar_id"] for a in areas)
        ],
        rule_profiles=dict(
            citywide=dict(
                items_path="knowledge/items.csv",
                embedding_index_path="knowledge/item_embeddings.npz",
                index_profile_id="citywide",
                calendar_path="generated/calendar-2026.json",
                knowledge_title="西条市公式家庭ごみ分別ガイドブック・現行案内",
                classification_rules=rules["classification_rules"],
                size_question="西条市の指定袋（大）に入れて口を縛れる大きさですか？",
                categories=cats,
                bulky_waste=dict(category_code="bulky", config=rules["bulky_config"]),
            )
        ),
    )


def audit_images():
    """Render independent OCR inputs, plus check whole/split dictionary pages."""
    import pymupdf

    checked_sources()
    _, _, _, audits = calendar_records()
    out = DATA / "generated/ocr"
    out.mkdir(parents=True, exist_ok=True)
    manifest = []

    def render(page, rect, key, source):
        target = out / (key + ".png")
        page.get_pixmap(
            matrix=pymupdf.Matrix(4, 4), clip=pymupdf.Rect(rect), alpha=False
        ).save(target)
        manifest.append(
            dict(
                id=key,
                image=str(target.resolve()),
                image_sha256=digest(target),
                source_sha256=digest(source),
            )
        )

    whole = pymupdf.open(DATA / "source/guidebook.pdf")
    part = pymupdf.open(DATA / "source/guide-10.pdf")
    equal = []
    for pi, page in enumerate(part):
        other = whole[pi + 13]
        if compact(page.get_text()) != compact(other.get_text()):
            raise ValueError("Whole/split dictionary text differs")
        a = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        b = other.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        if a.samples != b.samples:
            raise ValueError("Whole/split dictionary rendering differs")
        equal.append(pi + 1)
        render(page, page.rect, f"dictionary-{pi+1:02}", DATA / "source/guide-10.pdf")
    for cid, audit in audits.items():
        source = DATA / "source" / f"calendar-{cid[-2:]}.pdf"
        page = pymupdf.open(source)[0]
        for month in audit["months"]:
            render(page, month["rect"], f"{cid}-m{month['month']:02}", source)
    write(out / "manifest.json", manifest)
    binary = Path("/private/tmp/saijo-ocr")
    subprocess.run(
        [
            "swiftc",
            "-module-cache-path",
            "/private/tmp/saijo-swift-cache",
            str(ROOT / "scripts/toon_ocr.swift"),
            "-o",
            str(binary),
        ],
        check=True,
    )
    subprocess.run([str(binary), str(out / "manifest.json"), str(out)], check=True)
    write(
        DATA / "generated/whole-split-audit.json",
        dict(pages=equal, text_equal=True, raster_equal=True),
    )


def image_audit():
    from saijo_image_audit import audit

    raw, _ = dictionary(DATA / "source/guide-10.pdf")
    _, _, _, calendars = calendar_records()
    return audit(DATA, raw, calendars, digest)


def build(inspect_only=False):
    checked_sources()
    rows, item_review = item_rows()
    areas, calendars, cal_review, _ = calendar_records()
    write(DATA / "generated/item-review-candidate.json", item_review)
    write(DATA / "generated/calendar-review-candidate.json", cal_review)
    if inspect_only:
        print(
            f"Inspect {len(rows)} rows / {len(areas)} areas / {len(calendars)} calendars"
        )
        return
    if item_review != read(DATA / "item_reviews.json") or cal_review != read(
        DATA / "calendar_reviews.json"
    ):
        raise ValueError("Reviewed extraction differs")
    image_audit()
    registry = registry_record(areas)
    write(DATA / "registry.json", registry)
    write(
        DATA / "generated/calendar-2026.json",
        {
            k: registry[k]
            for k in ["municipality_id", "version", "valid_from", "valid_to"]
        }
        | dict(calendars=calendars),
    )
    path = DATA / "knowledge/items.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Built {len(rows)} rows / {len(areas)} areas / {len(calendars)} calendars")


def verify(without_index=False):
    checked_sources()
    areas, calendars, review, _ = calendar_records()
    rows, item_review = item_rows()
    if review != read(DATA / "calendar_reviews.json") or item_review != read(
        DATA / "item_reviews.json"
    ):
        raise ValueError("Source/review mismatch")
    image_audit()
    registry = registry_record(areas)
    if registry != read(DATA / "registry.json"):
        raise ValueError("Registry differs")
    expected = {
        k: registry[k] for k in ["municipality_id", "version", "valid_from", "valid_to"]
    } | dict(calendars=calendars)
    if expected != read(DATA / "generated/calendar-2026.json"):
        raise ValueError("Calendar differs")
    with (DATA / "knowledge/items.csv").open(encoding="utf8", newline="") as f:
        if list(csv.DictReader(f)) != rows:
            raise ValueError("CSV differs")
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.region_registry_service import RegionRegistry
    from app.services.calendar_service import CalendarService

    reg = RegionRegistry(DATA / "registry.json")
    for area in areas:
        cal = CalendarService(region=reg.resolve(CITY, area["id"]))
        if any(
            cal.next_collection(c) is not None
            for c in [
                "bulky",
                "drop_off",
                "direct_delivery",
                "not_collected",
                "small_appliances",
            ]
        ):
            raise ValueError("Nonregular collection date")
    if not without_index:
        from app.services.embedding_search_service import EmbeddingSearchService
        import numpy as np

        profile = reg.profiles["citywide"]
        index = EmbeddingSearchService(
            items_path=profile.items_path,
            embeddings_path=profile.embedding_index_path,
            municipality_id=CITY,
            profile_id="citywide",
            runtime_client=object(),
        )
        if not index.is_ready:
            raise ValueError("Missing/inconsistent Saijo index")
        with np.load(profile.embedding_index_path, allow_pickle=False) as data:
            if (
                list(map(str, data["item_ids"])) != [r["item_id"] for r in rows]
                or not np.isfinite(data["vectors"]).all()
                or not np.allclose(
                    np.linalg.norm(data["vectors"], axis=1), 1, atol=0.002
                )
            ):
                raise ValueError("Index IDs/vectors differ")
    result = dict(
        official_items=item_review["official_items"],
        examples=item_review["examples"],
        search_records=len(rows),
        areas=len(areas),
        calendars=len(calendars),
        calendar_dates=365 * len(calendars),
        index_checked=not without_index,
    )
    write(DATA / "generated/verification.json", result)
    print(json.dumps(result))
    return result


def activate():
    verify()
    path = ROOT / "data/regions/catalog.json"
    catalog = read(path)
    entry = dict(id=CITY, registry_path="saijo/registry.json")
    previous = next((v for v in catalog["municipalities"] if v["id"] == CITY), None)
    if previous and previous != entry:
        raise ValueError("Catalog entry differs")
    if not previous:
        catalog["municipalities"].append(entry)
        write(path, catalog)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["fetch", "inspect", "audit-images", "build", "verify", "activate"],
    )
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--without-index", action="store_true")
    args = parser.parse_args()
    if args.data_dir:
        if args.command == "activate":
            parser.error("activate uses repository data only")
        DATA = args.data_dir.resolve()
    if args.command == "inspect":
        build(inspect_only=True)
    elif args.command == "verify":
        verify(without_index=args.without_index)
    else:
        globals()[args.command.replace("-", "_")]()
