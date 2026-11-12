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
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from urllib.request import urlopen

from uwajima_html import content, Document, expanded
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
            urlparse(s["url"]).hostname
            not in {"www.city.uwajima.ehime.jp", "www8.cao.go.jp"}
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
            note = (
                "使用済みマンガン・アルカリ乾電池、ボタン電池、リチウム一次電池は指定拠点へ。ボタン・リチウム一次電池は端子を絶縁。通常は袋に入れず直接容器へ、液漏れ時は袋に入れる。地域別の回収日が未確認の場合は拠点を案内。"
                if source.endswith("kandenchi-recycle.html")
                else "小型充電式電池は端子を絶縁し、使い切って透明な袋に入れて市役所・支所の充電池回収へ。可燃・不燃に入れない。大型・鉛蓄電池は対象外。"
            )
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
        if item in {"食品トレー", "トレー（食品用・プラ製）"}:
            options.add("clean_plastics")
            note = "通常収集は燃えるごみ。資源拠点を利用する場合は、洗って汚れを落とし乾燥させた、一辺50cm未満の容器包装プラスチックとして回収できる。拠点によって容器包装のみを受け付ける場合があるので、持込先の対象品目を確認する。"
            source = base + "plastic-jissyou.html"
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


def resource_paper_rules():
    table = expanded(
        Document((DATA / "source/resource-schedule-uwajima.html").read_text()).tables[0]
    )
    result = {}
    for row in table[1:]:
        for offset in [1, 5]:
            if len(row) > offset + 3 and row[offset + 2]["text"] == "○":
                name, rule = row[offset]["text"], row[offset + 1]["text"]
                if name in result:
                    raise ValueError("Duplicate resource association")
                result[name] = rule
    return result


def holidays():
    result = set()
    with (DATA / "source/national-holidays.csv").open(
        encoding="cp932", newline=""
    ) as f:
        for row in list(csv.reader(f))[1:]:
            year, month, day = map(int, row[0].split("/"))
            result.add(date(year, month, day).isoformat())
    return result


def resource_transfers():
    table = expanded(Document((DATA / "source/transfer-11.html").read_text()).tables[0])
    result = []
    for row in table[1:]:
        old = re.search(r"(\d+)月(\d+)日", row[0]["text"])
        new = re.search(r"(\d+)月(\d+)日", row[1]["text"])
        if old is None or new is None:
            raise ValueError("Resource transfer table changed")
        result.append(
            dict(
                original=f"2026-{int(old[1]):02}-{int(old[2]):02}",
                replacement=f"2026-{int(new[1]):02}-{int(new[2]):02}",
                items=row[2]["text"],
                associations=row[3]["text"],
            )
        )
    return result


def calendar_records():
    records = areas(DATA)
    byurl = {s["url"]: s for s in sources()}
    unique = {}
    calendars = {}
    selected = []
    review = []
    resources = []
    paper_rules = resource_paper_rules()
    public_holidays = holidays()
    transfers = resource_transfers()
    resource_url = "https://www.city.uwajima.ehime.jp/soshiki/15/gomi-u-shigen.html"
    transfer_url = "https://www.city.uwajima.ehime.jp/info/shigen-furikae11.html"
    for i, r in enumerate(records, 1):
        source = byurl[r["pdf_url"]] if r["pdf_url"] else None
        webpage = next(
            s["url"] for s in sources() if s["file"] == f'calendar-{r["region"]}.html'
        )
        unknown = {}

        def mark_unknown(code, day, message, url):
            unknown.setdefault(code, {})[day] = dict(message=message, source_url=url)
            if day in days:
                days[day] = [c for c in days[day] if c != code]

        if source:
            key = source["sha256"]
            if key not in unique:
                parsed, stats = calendar_image(DATA / "source" / source["file"])
                unique[key] = (parsed, stats, source)
            parsed, stats, _ = unique[key]
            days = {d: list(cs) for d, cs in parsed.items()}
        else:
            key = r["name"]
            days = {
                d.isoformat(): sorted(
                    c
                    for c, rule in r["rules"].items()
                    if c != "paper" and matches(d, rule)
                )
                for d in dates()
            }
            # Island HTML does not specify a New Year's exception. Do not carry
            # another area's Jan 1 closure over to these collection boats.
            for code in days.get("2027-01-01", []):
                mark_unknown(
                    code,
                    "2027-01-01",
                    "離島の年始の収集可否は公式資料から確認できません。自治会又は市へ確認してください。",
                    webpage,
                )
        if r["region"] == "mima":
            for d in dates():
                if matches(d, r["rules"]["paper"]):
                    days.setdefault(d.isoformat(), []).append("paper")
        paper_rule = paper_rules.get(r["name"]) if r["region"] == "uwajima" else None
        if paper_rule and paper_rule != "各自":
            resources.append(
                dict(
                    area=r["name"],
                    association=r["name"],
                    rule=paper_rule,
                    source_url=resource_url,
                )
            )
            for d in dates():
                if ("奇数月" in paper_rule and d.month % 2 == 0) or (
                    "偶数月" in paper_rule and d.month % 2 == 1
                ):
                    continue
                if not matches(d, paper_rule):
                    continue
                day = d.isoformat()
                if day in public_holidays:
                    applicable = [
                        t
                        for t in transfers
                        if t["original"] == day
                        and r["name"] in t["associations"].split("、")
                    ]
                    if applicable:
                        replacement = applicable[0]["replacement"]
                        days.setdefault(replacement, []).append("paper")
                    else:
                        mark_unknown(
                            "paper",
                            day,
                            "祝日の資源回収は振替日が未確認です。自治会又は市で確認してください。",
                            resource_url,
                        )
                else:
                    days.setdefault(day, []).append("paper")
        if source and source["file"] in [
            "calendar-uwajima-65710.pdf",
            "calendar-uwajima-69373.pdf",
        ]:
            mark_unknown(
                "burnable",
                "2026-09-30",
                "9月30日の燃えるごみは、PDFの空欄とHTMLの曜日案内が一致しないため未確認です。市へ確認してください。",
                source["url"],
            )
        pid = r["region"] + ("_islands" if not source else "")
        verified = {
            c: dict(status="checked")
            for c in ["burnable", "non_burnable", "bottles_cans", "pet", "paper"]
        }
        if (
            "paper" not in r["rules"]
            and not paper_rule
            and not any("paper" in cs for cs in days.values())
        ):
            verified["paper"] = dict(
                status="unverified",
                message="古紙の回収区域・日程をこの収集地区だけでは確定できません。自治会又は市で確認し、古紙の拠点回収もご利用ください。",
                source_url=resource_url if r["region"] == "uwajima" else webpage,
            )
        if "月末" in r["rules"].get("pet", ""):
            verified["pet"] = dict(
                status="unverified",
                message="ペットボトルは「月末」と案内されていますが、具体的な日付は未確認です。自治会又は市へ確認してください。",
                source_url=webpage,
            )
        if r["region"] == "uwajima" and r["name"] == "高光（平駄場）":
            verified["pet"] = dict(
                status="unverified",
                message="ペットボトルはHTMLの第2・4木曜とPDFの第2・4金曜が一致しないため未確認です。市へ確認してください。",
                source_url=source["url"],
            )
            for cs in days.values():
                if "pet" in cs:
                    cs.remove("pet")
        # The ID includes the exact resource association, so a holiday transfer
        # cannot leak into another town sharing the same station-calendar PDF.
        cid = (
            "uw-"
            + hashlib.sha256(
                (
                    str(key)
                    + pid
                    + r["rules"].get("paper", "")
                    + (r["name"] if paper_rule else "")
                ).encode()
            ).hexdigest()[:12]
        )
        calendar = dict(
            verification_status=(
                "partially_checked"
                if any(v["status"] == "unverified" for v in verified.values())
                else "checked"
            ),
            source_url=unique[key][2]["url"] if source else webpage,
            collection_type_verification=verified,
            days={
                d.isoformat(): sorted(set(days.get(d.isoformat(), []))) for d in dates()
            },
        )
        if unknown:
            calendar["unverified_dates"] = unknown
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
            resource_associations=resources,
            resource_transfers=transfers,
            unknown_dates={
                cid: cal["unverified_dates"]
                for cid, cal in calendars.items()
                if "unverified_dates" in cal
            },
            decisions=dict(
                mima_heading="User approved FY2026 second half based on official FY2026 page and all printed weekday/date positions; no date rewriting",
                resource_scope="Exact official association name matches only; ambiguous crosswalks remain unverified",
                individual_pdf_dates="Explicit printed dates take precedence over general HTML recurrence; absent/contradictory dates are unverified",
            ),
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
