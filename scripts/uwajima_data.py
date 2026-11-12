#!/usr/bin/env python3
"""Reproduce Uwajima FY2026 data. No model calls: fetch/inspect/build/verify/activate.

Official downloads and generated CSV/calendar/NPZ are Git-ignored. Reviewed
hashes and extraction reports are tracked. Changed source data fail closed.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from urllib.request import urlopen

from uwajima_html import content
from uwajima_pdf import calendar_image, dictionary
from uwajima_schedule import REGIONS, areas, dates, matches

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/uwajima"
CITY, VERSION = "38203", "uwajima-2026.1"
FROM, TO = "2026-04-01", "2027-03-31"


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
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def sources():
    return read(DATA / "sources.json")["sources"]


def checked_sources():
    records = sources()
    if len({s["file"] for s in records}) != len(records):
        raise ValueError("Duplicate source filenames")
    for s in records:
        if digest(DATA / "source" / s["file"]) != s["sha256"]:
            raise ValueError("Missing/changed source: " + s["file"])


def fetch():
    def download(s):
        if (
            urlparse(s["url"]).hostname != "www.city.uwajima.ehime.jp"
            or Path(s["file"]).name != s["file"]
        ):
            raise ValueError("Unexpected source location")
        body = urlopen(s["url"], timeout=90).read()
        if s.get("canonicalization") == "main_body_utf8":
            body = content(body)
        if hashlib.sha256(body).hexdigest() != s["sha256"]:
            raise ValueError("Official source changed; review required: " + s["file"])
        (DATA / "source").mkdir(parents=True, exist_ok=True)
        (DATA / "source" / s["file"]).write_bytes(body)

    list(ThreadPoolExecutor(4).map(download, sources()))
    print("Fetched and hash-checked official sources")


def item_rows():
    raw, counts = dictionary(DATA / "source/document-55088.pdf")
    rules = read(DATA / "official_rules.json")
    dictionary_url = next(
        s["url"] for s in sources() if s["file"] == "document-55088.pdf"
    )
    base = "https://www.city.uwajima.ehime.jp/soshiki/15/"
    updates, rows = [], []
    for original in raw:
        r = dict(original)
        item, note, category = r["item"], r["note"], r["category"]
        source = dictionary_url + "#page=" + str(r["pdf_page"])
        options = set()
        # Only whole-item alternatives, not a cap/handle mentioned in the note.
        if "指定袋に入" in note:
            if category != "bulky" and "粗大" in note:
                options.add("bulky")
            if category == "bulky":
                if "可燃" in note:
                    options.add("burnable")
                if "不燃" in note:
                    options.add("non_burnable")
        if any(
            t in note for t in ["金属製は不燃", "樹脂製は可燃", "プラ製のものは可燃"]
        ):
            options.update(
                c
                for t, c in [
                    ("金属製は不燃", "non_burnable"),
                    ("樹脂製は可燃", "burnable"),
                    ("プラ製のものは可燃", "burnable"),
                ]
                if t in note
            )
        if "汚れ" in note and "可燃へ" in note:
            options.add("burnable")
        if category == "pet":
            note = "PETマークのある飲料・食品用ボトル本体。キャップとラベルを外し中をすすいで出す。汚れのひどい本体は可燃。外したキャップとラベルは可燃又は洗浄・乾燥してプラスチックの拠点へ。本体の分類に付属品の区分を適用しない。"
            options.add("burnable")
            source = base + "gomi-sutekata.html"
        if item.startswith("電池（") and "小型シール鉛" not in item:
            category = "batteries"
            source = base + (
                "denti.html"
                if any(
                    t in item for t in ["充電", "ニカド", "ニッケル", "リチウムイオン"]
                )
                else "kandenchi-recycle.html"
            )
            note = rules["categories"]["batteries"]["instructions"]
        if item == "バッテリー（小型充電式電池）":
            category = "batteries"
            note = rules["categories"]["batteries"]["instructions"]
            source = base + "denti.html"
        if "電池は外す" in note or item in {
            "携帯電話",
            "PHS（携帯電話）",
            "ノートパソコン",
        }:
            note += "。電池を外して指定袋へ。取り外せない充電池内蔵製品は無理に分解せず本体ごと市役所・支所の充電池回収へ。"
            options.add("batteries")
        if item == "ペットボトルのキャップ・ラベル":
            note = "取り外したプラスチック製キャップ・ラベルは可燃。洗い汚れを落として乾燥させれば、容器包装プラスチックとして拠点回収も利用可能。PET本体の区分を付けない。"
            source = base + "plastic-jissyou.html"
            options.add("clean_plastics")
        options.discard(category)
        if (category, note, source) != (
            original["category"],
            original["note"],
            dictionary_url + "#page=" + str(r["pdf_page"]),
        ):
            updates.append(
                dict(
                    item_id=r["item_id"],
                    item=item,
                    old_category=original["category"],
                    new_category=category,
                    source_url=source,
                )
            )
        rows.append(
            dict(
                item_id=r["item_id"],
                item=item,
                category=category,
                note=note,
                source_url=source,
                category_display=rules["categories"][category]["name"],
                category_options=json.dumps(sorted(options)),
                disposal_instructions=rules["categories"][category]["instructions"],
            )
        )
    for i, e in enumerate(read(DATA / "examples.json"), 1):
        rows.append(
            dict(
                item_id=f"uw-example-{i:03}",
                item=e["item"],
                category=e["category"],
                note=e["note"],
                source_url=e["source_url"],
                category_display=rules["categories"][e["category"]]["name"],
                category_options=json.dumps(e.get("category_options", [])),
                disposal_instructions=rules["categories"][e["category"]][
                    "instructions"
                ],
            )
        )
    return rows, dict(
        official_rows=len(raw),
        examples=len(rows) - len(raw),
        page_counts=counts,
        raw_sha256=value_digest(raw),
        rows_sha256=value_digest(rows),
        category_counts=dict(Counter(r["category"] for r in rows)),
        current_updates=updates,
    )


def calendar_records():
    records = areas(DATA)
    byurl = {s["url"]: s for s in sources()}
    unique = {}
    calendars = {}
    selected = []
    review = []
    for i, r in enumerate(records, 1):
        source = byurl[r["pdf_url"]] if r["pdf_url"] else None
        if source:
            key = source["sha256"]
            if key not in unique:
                days, stats = calendar_image(DATA / "source" / source["file"])
                unique[key] = (days, stats, source)
            days, stats, _ = unique[key]
            days = {d: list(cs) for d, cs in days.items()}
        else:
            key = r["name"]
            days = {
                d.isoformat(): sorted(
                    c
                    for c, rule in r["rules"].items()
                    if c != "paper" and matches(d, rule)
                )
                for d in dates()
                if d.isoformat() not in ["2027-01-01", "2027-01-02", "2027-01-03"]
            }
            days = {d: cs for d, cs in days.items() if cs}
        if r["region"] == "mima":
            for d in dates():
                if matches(d, r["rules"]["paper"]):
                    days.setdefault(d.isoformat(), []).append("paper")
        # Calendar identity includes its resource-area intersection/profile.
        pid = r["region"] + ("_islands" if not source else "")
        cid = (
            "uw-"
            + hashlib.sha256(
                (str(key) + pid + r["rules"].get("paper", "")).encode()
            ).hexdigest()[:12]
        )
        webpage = next(
            s["url"] for s in sources() if s["file"] == f'calendar-{r["region"]}.html'
        )
        verified = {
            c: dict(status="checked")
            for c in ["burnable", "non_burnable", "bottles_cans", "pet", "paper"]
        }
        if "paper" not in r["rules"] and not any("paper" in cs for cs in days.values()):
            verified["paper"] = dict(
                status="unverified",
                message="古紙の回収区域・日程をこの収集地区だけでは確定できません。自治会又は市で確認し、古紙の拠点回収もご利用ください。",
                source_url=(
                    "https://www.city.uwajima.ehime.jp/soshiki/15/gomi-u-shigen.html"
                    if r["region"] == "uwajima"
                    else webpage
                ),
            )
        if "月末" in r["rules"].get("pet", ""):
            verified["pet"] = dict(
                status="unverified",
                message="ペットボトルは「月末」と案内されていますが、具体的な日付は未確認です。自治会又は市へ確認してください。",
                source_url=webpage,
            )
        calendar = dict(
            verification_status=(
                "partially_checked"
                if any(v["status"] == "unverified" for v in verified.values())
                else "checked"
            ),
            source_url=unique[key][2]["url"] if source else webpage,
            collection_type_verification=verified,
            days={d: sorted(set(cs)) for d, cs in sorted(days.items())},
        )
        if cid in calendars and calendars[cid] != calendar:
            raise ValueError("Calendar identity collision")
        calendars[cid] = calendar
        selected.append(
            dict(
                id=f"38203-a{i:03}",
                name=REGIONS[r["region"]] + " → " + r["name"],
                display_name=REGIONS[r["region"]] + " → " + r["name"],
                calendar_id=cid,
                rule_profile_id=pid,
                source_url=r["pdf_url"] or webpage,
                needs_local_confirmation=True,
            )
        )
    for key, (days, stats, s) in unique.items():
        review.append(dict(file=s["file"], sha256=key, **stats))
    return (
        selected,
        calendars,
        dict(
            original_pdf_links=118,
            distinct_pdf_contents=len(unique),
            selectable_areas=len(selected),
            calendar_patterns=len(calendars),
            pdf_cells=sum(r["cells"] for r in review),
            pdfs=review,
        ),
    )


def registry_record(selected, calendars):
    rules = read(DATA / "official_rules.json")
    profiles = {}
    for pid in sorted({a["rule_profile_id"] for a in selected}):
        cats = {
            code: {
                k: v for k, v in cat.items() if k not in {"instructions", "source_url"}
            }
            for code, cat in rules["categories"].items()
        }
        for code, cat in cats.items():
            if not cat.get("collection_type_id"):
                continue
            if pid.endswith("_islands"):
                cat.update(
                    cutoff_status="unverified",
                    time_note="離島の搬出場所・船便・時刻は自治会又は市に確認してください。",
                )
            else:
                cat.update(
                    cutoff="08:30",
                    time_note="収集日の午前8時30分までに、地区で決められた場所へ。",
                )
                if code != "paper":
                    cat["start_time"] = "06:00"
            if code == "paper":
                cat["answer_note"] = (
                    "古紙の回収場所はごみステーションと異なる場合があります。自治会の指定場所へ。"
                )
                if pid.startswith("tsushima"):
                    cat[
                        "time_note"
                    ] += "雨・祝日は月曜地区は木曜、火曜地区は金曜に延期。延期日も雨・祝日なら翌月。船便は荒天で変更の場合があります。"
                if pid == "yoshida":
                    cat[
                        "time_note"
                    ] += "雨天は中止。祝日の変更は公式カレンダーを確認してください。"
        profiles[pid] = dict(
            items_path="knowledge/items.csv",
            embedding_index_path="knowledge/item_embeddings.npz",
            index_profile_id="common",
            calendar_path="generated/calendar-2026.json",
            categories=cats,
            classification_rules=rules["classification_rules"],
            knowledge_title="宇和島市家庭ごみ分別早見表・現行公式案内",
            size_question="市の指定ごみ袋に入れて口を結べる大きさですか？",
            bulky_waste=dict(category_code="bulky", config=rules["bulky_config"]),
        )
    return dict(
        schema_version=1,
        municipality_id=CITY,
        municipality_name="宇和島市",
        prefecture_id="38",
        prefecture_name="愛媛県",
        version=VERSION,
        valid_from=FROM,
        valid_to=TO,
        collection_areas=selected,
        rule_profiles=profiles,
        calendars=[
            dict(
                id=cid,
                rule_profile_id=next(
                    a["rule_profile_id"] for a in selected if a["calendar_id"] == cid
                ),
            )
            for cid in calendars
        ],
    )


def inspect():
    checked_sources()
    _, items = item_rows()
    _, _, cal = calendar_records()
    write(DATA / "generated/item-review-candidate.json", items)
    write(DATA / "generated/calendar-review-candidate.json", cal)
    print(
        "Items:",
        items["official_rows"],
        "examples:",
        items["examples"],
        "areas:",
        cal["selectable_areas"],
        "calendar patterns:",
        cal["calendar_patterns"],
    )


def build():
    checked_sources()
    rows, items = item_rows()
    selected, calendars, cal = calendar_records()
    if items != read(DATA / "item_reviews.json") or cal != read(
        DATA / "calendar_reviews.json"
    ):
        raise ValueError("Reviewed extraction changed")
    registry = registry_record(selected, calendars)
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
    with path.open("w", encoding="utf8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(
        "Built",
        len(rows),
        "rows,",
        len(selected),
        "selected areas,",
        len(calendars),
        "calendar patterns",
    )


def verify(without_index=False):
    checked_sources()
    rows, items = item_rows()
    selected, cals, cal = calendar_records()
    reg = registry_record(selected, cals)
    if (
        items != read(DATA / "item_reviews.json")
        or cal != read(DATA / "calendar_reviews.json")
        or reg != read(DATA / "registry.json")
    ):
        raise ValueError("Reviewed extraction/registry changed")
    if read(DATA / "generated/calendar-2026.json") != {
        k: reg[k] for k in ["municipality_id", "version", "valid_from", "valid_to"]
    } | dict(calendars=cals):
        raise ValueError("Generated calendar changed")
    with (DATA / "knowledge/items.csv").open(encoding="utf8", newline="") as f:
        if list(csv.DictReader(f)) != rows:
            raise ValueError("Generated CSV changed")
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.region_registry_service import RegionRegistry
    from app.services.calendar_service import CalendarService

    registry = RegionRegistry(DATA / "registry.json")
    for a in selected:
        service = CalendarService(region=registry.resolve(CITY, a["id"]))
        for c in ["bulky", "dropoff", "batteries", "clean_plastics", "not_collected"]:
            if service.next_collection(c) is not None:
                raise ValueError("Nonregular item has scheduled date")
    if not without_index:
        import numpy as np
        from app.services.embedding_search_service import EmbeddingSearchService

        index = EmbeddingSearchService(
            items_path=DATA / "knowledge/items.csv",
            embeddings_path=DATA / "knowledge/item_embeddings.npz",
            runtime_client=object(),
            municipality_id=CITY,
            profile_id="common",
        )
        if not index.is_ready:
            raise ValueError("Dedicated index unavailable")
        with np.load(
            DATA / "knowledge/item_embeddings.npz", allow_pickle=False
        ) as values:
            if values["item_ids"].tolist() != [r["item_id"] for r in rows]:
                raise ValueError("Index order differs")
    print(
        "Verified official data"
        + (" (index not checked)" if without_index else " and dedicated index")
    )


def activate():
    verify()
    # Image/source review must also have been completed before publication.
    if read(DATA / "image_reviews.json")["status"] != "checked":
        raise ValueError("Image review incomplete")
    path = ROOT / "data/regions/catalog.json"
    catalog = read(path)
    entry = dict(id=CITY, registry_path="uwajima/registry.json")
    current = next((r for r in catalog["municipalities"] if r["id"] == CITY), None)
    if current and current != entry:
        raise ValueError("Conflicting municipality entry")
    if not current:
        catalog["municipalities"].append(entry)
    write(path, catalog)


def main():
    global DATA
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command", choices=["fetch", "inspect", "build", "verify", "activate"]
    )
    p.add_argument("--data-dir", type=Path, default=DATA)
    p.add_argument("--without-index", action="store_true")
    args = p.parse_args()
    DATA = args.data_dir.resolve()
    if args.command == "verify":
        verify(args.without_index)
    else:
        globals()[args.command]()


if __name__ == "__main__":
    main()
