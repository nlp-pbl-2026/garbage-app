#!/usr/bin/env python3
"""Reproduce Imabari FY2026 data without model calls.

fetch -> inspect -> audit-images -> build -> verify [--without-index]
Activation additionally requires both dedicated, validated Embedding indices.
Source/extraction changes fail closed and require a new recorded review.
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
import subprocess
import sys
from urllib.parse import urlparse
from urllib.parse import urljoin
from urllib.request import urlopen
from html import unescape

from imabari_pdf import (
    address_rows,
    compact,
    mainland_dictionary,
    numbered_calendar,
    sekizen_dictionary,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/imabari"
CITY, VERSION = "38202", "imabari-2026.1"
VALID_FROM, VALID_TO = "2026-04-01", "2027-03-31"
BASE = "https://www.city.imabari.ehime.jp/recycle/"


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
    if source.get("canonicalization") == "main_element_utf8":
        matches = re.findall(rb"<main\b[^>]*>(.*?)</main>", body, re.S)
        if len(matches) != 1:
            raise ValueError("Expected one official main content element")
        return matches[0].strip()
    return body


def checked_sources():
    sources = read(DATA / "sources.json")["sources"]
    if len({s["file"] for s in sources}) != len(sources):
        raise ValueError("Duplicate source filename")
    for s in sources:
        if digest(DATA / "source" / s["file"]) != s["sha256"]:
            raise ValueError("Missing or changed source: " + s["file"])


def fetch():
    def download(s):
        if (
            urlparse(s["url"]).hostname != "www.city.imabari.ehime.jp"
            or Path(s["file"]).name != s["file"]
        ):
            raise ValueError("Unexpected source location")
        body = normalize_source(urlopen(s["url"], timeout=90).read(), s)
        if hashlib.sha256(body).hexdigest() != s["sha256"]:
            raise ValueError("Official source changed; review required: " + s["file"])
        path = DATA / "source" / s["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    list(ThreadPoolExecutor(4).map(download, read(DATA / "sources.json")["sources"]))
    print("Fetched/hash-checked official sources")


def item_rows():
    rules = read(DATA / "official_rules.json")["profiles"]
    result, reviews = {}, {}
    plastic_items = {
        "植木鉢（プラスチック製）",
        "おもちゃ（プラスチック類）",
        "洗面器（プラスチック製）",
        "卵パック",
        "茶碗（プラスチック製）",
        "トレイ（食品）",
        "発砲スチロール",
        "プラスチック製品（指定袋に入るもの）",
        "プランター（指定袋に入るもの）",
        "ポリバケツ（指定袋に入らないもの）",
        "ポリ容器（指定袋に入らないもの）",
    }
    paper_items = {"菓子箱（紙）", "牛乳パック", "雑誌", "新聞紙", "段ボール", "チラシ"}
    for profile, reader, filename in [
        ("mainland", mainland_dictionary, "gomi_bunbetu.pdf"),
        ("sekizen", sekizen_dictionary, "gomi_hayamihyo_sekizen_2019.pdf"),
    ]:
        raw, counts = reader(DATA / "source" / filename)
        rows = []
        for item in raw:
            category, note = item["category"], item["note"]
            options = set()
            if profile == "mainland":
                if "解体確認" in note:
                    category = "direct_delivery"
                    note = note.replace(
                        "解体確認",
                        "個人で解体したものは市で解体ごみの確認手続きが必要（直接持込み）",
                    )
                if "処理方法❶" in note or "処理方法❷" in note:
                    note = note.replace(
                        "処理方法❶", "販売店又は今治市許可業者へ処理を依頼"
                    ).replace("処理方法❷", "販売店又は産業廃棄物許可業者へ処理を依頼")
                for label, code in [
                    ("可燃ごみへ", "burnable"),
                    ("不燃ごみへ", "non_burnable"),
                    ("粗大ごみへ", "bulky"),
                ]:
                    if label in compact(note):
                        options.add(code)
                if "素材に合わせて排出" in compact(note):
                    options.update(["burnable", "non_burnable"])
                if "ペットボトル" in item["item"] and category == "resources":
                    note += "。飲食用PET本体はキャップ・ラベルを外し水洗いして資源へ。外したプラ製キャップ・ラベルはプラへ。本体の分類に付属品の区分を適用しない。"
                if item["item"] in {"リチウムイオン電池", "モバイルバッテリー"}:
                    category = "hazardous"
                    note = "小型充電式電池は有害ごみ。電動自転車等の大型充電式電池は販売店等へ。"
            else:
                # Old row is provenance, not unqualified current evidence.
                if item["item"] in paper_items:
                    category = "paper"
                if item["item"] in plastic_items:
                    category = "plastics"
                    note = "2026年度資料による更新：プラスチックのみ・50cm未満・汚れを落としたものはプラスチック資源。金属等が外せないものは燃えないごみ。50cm以上・汚れが落ちないものは燃えるごみ（指定袋に入らなければ粗大ごみ）。材質と大きさが未確認なら確認する。"
                    options.update(["burnable", "non_burnable", "bulky"])
                if item["item"] == "ペットボトル":
                    note = "2026年度資料：飲食用PET本体はキャップ・ラベルを外し水洗いして資源物。外したキャップ・ラベルはプラスチック資源。本体に付属品の区分を適用しない。"
                if item["item"] in {"乾電池", "リチウム電池"}:
                    category = "hazardous_dangerous"
                    note = "2026年度案内を優先：乾電池・ボタン電池・リチウム電池・ニカド電池・リチウムイオン電池は有害・危険ごみコンテナへ。大型バッテリー等は販売店へ。"
                if item["item"] == "割れたびん":
                    category = "non_burnable"
                    note = "2026年度資料を優先：割れたガラスは丈夫な布や紙に包んで燃えないごみ。"
                if item["item"] in {"灯油の残り", "ペイント類（家庭用に限る）"}:
                    category = "not_collected"
                    note = "2026年度資料の収集できないもの（廃油・ペンキ類）を優先。販売店等に相談。"
                if item["item"] == "ハンガー（スチール製）":
                    note = "スチール製は燃えないごみ。2026年度資料ではプラスチックのみの50cm未満・汚れを落としたハンガーはプラスチック資源。"
                    options.add("plastics")
                if item["item"] == "まな板":
                    note = "2026年度資料ではプラスチック製のまな板（厚さ5mm以上）は燃えるごみ。材質・厚さが未確認なら確認。薄いプラスチックのみ・50cm未満で汚れを落としたものはプラスチック資源。"
                    options.add("plastics")
                for label, code in [
                    ("燃えるごみ", "burnable"),
                    ("燃えないごみ", "non_burnable"),
                    ("粗大ごみへ", "bulky"),
                ]:
                    if label in note:
                        options.add(code)
                if item["item"] == "封筒":
                    options.add("paper")
                if item["item"] == "蛍光管":
                    options.add("non_burnable")
            options.discard(category)
            source = next(
                s["url"]
                for s in read(DATA / "sources.json")["sources"]
                if s["file"] == filename
            )
            rows.append(
                dict(
                    item_id=item["item_id"],
                    item=item["item"],
                    category=category,
                    note=note,
                    source_url=source + "#page=" + str(item["pdf_page"]),
                    category_display=rules[profile]["categories"][category]["name"],
                    category_options=json.dumps(sorted(options)),
                    disposal_instructions=rules[profile]["categories"][category][
                        "instructions"
                    ],
                )
            )
        examples = read(DATA / "examples.json")[profile]
        for i, e in enumerate(examples, 1):
            rows.append(
                dict(
                    item_id=f"im-{'m'if profile=='mainland'else's'}-example-{i:03}",
                    item=e["item"],
                    category=e["category"],
                    note=e["note"],
                    source_url=e["source_url"],
                    category_display=rules[profile]["categories"][e["category"]][
                        "name"
                    ],
                    category_options=json.dumps(e.get("category_options", [])),
                    disposal_instructions=rules[profile]["categories"][e["category"]][
                        "instructions"
                    ],
                )
            )
        result[profile] = rows
        reviews[profile] = dict(
            official_rows=len(raw),
            examples=len(examples),
            page_counts=counts,
            raw_sha256=value_digest(raw),
            rows_sha256=value_digest(rows),
            category_counts=dict(Counter(r["category"] for r in rows)),
        )
    return result, reviews


def special_calendar(key):
    """Expand only explicitly printed FY2026 special-island rules.

    Wednesday public holidays are checked against the red date numerals in
    the numbered FY2026 calendars; these exceptions are FY-specific.
    """
    if key not in {"12_tokku", "36_tokku"}:
        raise ValueError("Unknown special calendar")
    days = {}
    d = date(2026, 4, 1)
    holiday_wednesdays = {date(2026, 4, 29), date(2026, 5, 6), date(2026, 9, 23)}
    resource_dates = {
        date(2026, 5, 5),
        date(2026, 8, 4),
        date(2026, 11, 3),
        date(2027, 2, 2),
    }
    while d <= date(2027, 3, 31):
        codes = []
        if key == "12_tokku":
            if (
                d.weekday() == 2
                and d not in holiday_wednesdays
                and not (date(2027, 1, 1) <= d <= date(2027, 1, 3))
            ) or d - timedelta(days=1) in holiday_wednesdays:
                codes += ["burnable", "non_burnable"]
            if d.weekday() == 4 and 8 <= d.day <= 14:
                codes += ["resources", "plastics"]
        else:
            if d.weekday() == 4 and not (date(2027, 1, 1) <= d <= date(2027, 1, 3)):
                codes += ["burnable", "non_burnable"]
            if d in resource_dates:
                codes += ["resources", "plastics"]
        # Hazardous/dangerous use the same explicitly printed resources day.
        days[d.isoformat()] = sorted(codes)
        d += timedelta(days=1)
    return dict(
        days=days,
        rule_expansion=True,
        source_key=key,
        holiday_shifts=(
            ["2026-04-29→2026-04-30", "2026-05-06→2026-05-07", "2026-09-23→2026-09-24"]
            if key == "12_tokku"
            else []
        ),
        reservation_only_bulky=True,
    )


def calendar_records():
    sources = read(DATA / "sources.json")["sources"]
    specs = []
    for s in sources:
        if not re.fullmatch(r"calendar-\d\d(?:_tokku)?\.pdf", s["file"]):
            continue
        key = s["file"][9:-4]
        label = s["label"]
        # The official HTML supplies labels; strip only download hints.
        if key == "12_tokku":
            label = "波止浜（特）"
        elif key == "36_tokku":
            label = "宮窪（特）"
        else:
            label = re.sub(r"[（(]PDF.*$", "", label)
            label = re.sub(r"\s*地区\s*$", "", label)
            label = re.sub(r"\s*\[.*$", "", label).strip()
        specs.append(
            dict(
                id="im-" + key,
                key=key,
                label=label,
                source_file=s["file"],
                source_url=s["url"],
            )
        )
    if len(specs) != 44:
        raise ValueError("Exactly 42 numbered + 2 special calendar PDFs required")
    index = (DATA / "source/calendar-2026.html").read_text(encoding="utf8")
    links = {
        urljoin(BASE + "calendar/R08/", unescape(url)): unescape(
            re.sub("<[^>]+>", "", text)
        ).strip()
        for url, text in re.findall(
            r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', index, re.S
        )
        if ".pdf" in url
    }
    if len(links) != 44 or any(s["source_url"] not in links for s in specs):
        raise ValueError("FY2026 index/calendar link mismatch")
    for spec in specs:
        original = next(s for s in sources if s["file"] == spec["source_file"])
        if compact(links[spec["source_url"]]) != compact(original["label"]):
            raise ValueError("Official calendar index label changed")
    calendars, audits = {}, {}
    for spec in specs:
        key = spec["key"]
        audit = (
            special_calendar(key)
            if "tokku" in key
            else numbered_calendar(
                DATA / "source" / spec["source_file"], key in {"41", "42"}
            )
        )
        calendars[spec["id"]] = dict(
            verification_status="checked",
            source_url=spec["source_url"],
            days=audit["days"],
        )
        audits[spec["id"]] = audit
    by_label = {compact(s["label"]): s for s in specs}
    # Exact labels used in the address table and the FY2026 index.
    aliases = {"波止浜(特)": "12_tokku", "宮窪(特)": "36_tokku"}
    for label, key in aliases.items():
        by_label[label] = next(s for s in specs if s["key"] == key)
    addresses = address_rows(DATA / "source/sakuin.pdf")
    areas = []
    for i, row in enumerate(addresses, 1):
        label = compact(row["calendar_label"])
        if label not in by_label:
            raise ValueError(
                f"Address calendar not in current index: {label}; {list(by_label)}"
            )
        spec = by_label[label]
        town = re.sub(r"（[ぁ-ゖー]+）", "", row["town"]).strip()
        qualifiers = [q.strip() for q in row["qualifiers"]]
        detail = "／".join(
            q
            for q in [
                qualifiers[0],
                "番地" + qualifiers[1] if qualifiers[1] else "",
                "枝番" + qualifiers[2] if qualifiers[2] else "",
            ]
            if q
        )
        name = town + ("（" + detail + "）" if detail else "")
        profile = (
            "sekizen"
            if spec["key"] in {"41", "42"}
            else (
                "hatohama_islands"
                if spec["key"] == "12_tokku"
                else "ushima" if spec["key"] == "36_tokku" else "mainland"
            )
        )
        display_name = name
        if spec["key"] == "12_tokku":
            display_name = "離島：" + ("来島・小島" if "来島" in town else town)
        elif spec["key"] == "36_tokku":
            display_name = "離島：宮窪町・鵜島"
        elif profile == "sekizen":
            display_name = "関前：" + town.removeprefix("関前")
        areas.append(
            dict(
                id=f"38202-a{i:03}",
                name=name,
                display_name=display_name,
                calendar_id=spec["id"],
                rule_profile_id=profile,
                source_url=spec["source_url"],
                needs_local_confirmation=True,
                address_index_source_url=BASE
                + "calendar/sakuin.pdf?R7#page="
                + str(row["pdf_page"]),
            )
        )
    if len({a["display_name"] for a in areas}) != len(areas):
        raise ValueError("Duplicate area names")
    review = dict(
        calendar_count=len(calendars),
        numbered_calendars=42,
        special_calendars=2,
        calendar_dates=365 * 44,
        selectable_areas=len(areas),
        address_rows_sha256=value_digest(addresses),
        calendars=[
            dict(
                calendar_id=s["id"],
                source_file=s["source_file"],
                dates=365,
                collection_days=sum(
                    bool(v) for v in calendars[s["id"]]["days"].values()
                ),
                stream_counts=dict(
                    Counter(c for v in calendars[s["id"]]["days"].values() for c in v)
                ),
                days_sha256=value_digest(calendars[s["id"]]["days"]),
            )
            for s in specs
        ],
    )
    return areas, calendars, review, audits, specs


def registry_record(areas, specs):
    rules = read(DATA / "official_rules.json")["profiles"]
    profiles = {}
    for pid in ["mainland", "hatohama_islands", "ushima", "sekizen"]:
        index = "sekizen" if pid == "sekizen" else "mainland"
        spec = rules[index]
        cats = {
            k: {a: b for a, b in v.items() if a not in {"instructions", "source_url"}}
            for k, v in spec["categories"].items()
        }
        for code, cat in cats.items():
            if not cat.get("collection_type_id"):
                continue
            if pid == "mainland" and code in {"burnable", "non_burnable"}:
                cat.update(
                    cutoff="06:30",
                    time_note="収集日の朝6時30分までに決められたごみ集積所へ。",
                )
            elif pid in {"ushima", "sekizen"}:
                cat.update(
                    cutoff="08:30",
                    time_note="収集日当日の朝8時30分までに、地区の決められた場所へ。",
                )
            else:
                cat.update(
                    cutoff_status="unverified",
                    time_note=(
                        "波止浜港8時40分着（第3便）の各島の出航時刻までに、各島の指定の港へ。出航時刻は船便で確認してください。"
                        if pid == "hatohama_islands"
                        else "地域で決めた時間内に資源集積所へ。時間は自治会等で確認してください。"
                    ),
                )
        bulky = dict(spec["bulky_config"])
        if pid == "hatohama_islands":
            bulky.update(
                collection_rules="1回5点まで。指定の申込期間に受付センターへ予約し、収集日の朝に各島の指定の港へ処理券を貼って搬出。収集日は申込時に案内されます。"
            )
        if pid == "ushima":
            bulky.update(
                phone_number="0897-86-2500",
                collection_frequency="鵜島の年4回・要申込み",
                collection_rules="宮窪支所の指定申込期間に電話で申し込み、収集日の朝、指定場所へ処理券を貼って搬出。予約前の収集予定は作成しません。",
            )
        profiles[pid] = dict(
            items_path=f"knowledge/{index}/items.csv",
            embedding_index_path=f"knowledge/{index}/item_embeddings.npz",
            index_profile_id=index,
            calendar_path="generated/calendar-2026.json",
            categories=cats,
            classification_rules=spec["classification_rules"],
            knowledge_title="今治市公式分別早見表・現行案内"
            + ("（関前）" if pid == "sekizen" else "（関前を除く）"),
            size_question="指定ごみ袋に入れて口を縛り、持ち上げても袋が破れない大きさ・重さですか？",
            bulky_waste=dict(category_code="bulky", config=bulky),
        )
    return dict(
        schema_version=1,
        municipality_id=CITY,
        municipality_name="今治市",
        prefecture_id="38",
        prefecture_name="愛媛県",
        version=VERSION,
        valid_from=VALID_FROM,
        valid_to=VALID_TO,
        collection_areas=areas,
        rule_profiles=profiles,
        calendars=[
            dict(
                id=s["id"],
                rule_profile_id=next(
                    a["rule_profile_id"] for a in areas if a["calendar_id"] == s["id"]
                ),
            )
            for s in specs
        ],
    )


def inspect():
    checked_sources()
    _, items = item_rows()
    _, _, calendars, _, _ = calendar_records()
    write(DATA / "generated/item-review-candidate.json", items)
    write(DATA / "generated/calendar-review-candidate.json", calendars)
    print(
        "Official rows:",
        {k: v["official_rows"] for k, v in items.items()},
        "areas:",
        calendars["selectable_areas"],
        "calendars:",
        calendars["calendar_count"],
    )


def build():
    checked_sources()
    rows, items = item_rows()
    areas, calendars, review, _, specs = calendar_records()
    if items != read(DATA / "item_reviews.json") or review != read(
        DATA / "calendar_reviews.json"
    ):
        raise ValueError("Reviewed extraction changed")
    from imabari_image_audit import audit

    audit(DATA)
    registry = registry_record(areas, specs)
    write(DATA / "registry.json", registry)
    write(
        DATA / "generated/calendar-2026.json",
        {
            k: registry[k]
            for k in ["municipality_id", "version", "valid_from", "valid_to"]
        }
        | dict(calendars=calendars),
    )
    for profile, values in rows.items():
        path = DATA / "knowledge" / profile / "items.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    print(
        "Built",
        sum(map(len, rows.values())),
        "rows /",
        len(areas),
        "areas /",
        len(calendars),
        "calendars",
    )


def verify(without_index=False):
    checked_sources()
    from imabari_image_audit import audit

    audit(DATA)
    rows, items = item_rows()
    areas, calendars, review, _, specs = calendar_records()
    registry = registry_record(areas, specs)
    if (
        items != read(DATA / "item_reviews.json")
        or review != read(DATA / "calendar_reviews.json")
        or registry != read(DATA / "registry.json")
    ):
        raise ValueError("Reviewed metadata/registry differs")
    expected = {
        k: registry[k] for k in ["municipality_id", "version", "valid_from", "valid_to"]
    } | dict(calendars=calendars)
    if expected != read(DATA / "generated/calendar-2026.json"):
        raise ValueError("Calendar differs")
    for profile, values in rows.items():
        with (DATA / "knowledge" / profile / "items.csv").open(
            encoding="utf8", newline=""
        ) as f:
            if list(csv.DictReader(f)) != values:
                raise ValueError("CSV differs")
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.region_registry_service import RegionRegistry
    from app.services.calendar_service import CalendarService

    reg = RegionRegistry(DATA / "registry.json")
    for area in areas:
        service = CalendarService(region=reg.resolve(CITY, area["id"]))
        for c in ["not_collected", "direct_delivery", "consult", "small_appliances"] + (
            [] if area["rule_profile_id"] == "sekizen" else ["bulky"]
        ):
            if service.next_collection(c) is not None:
                raise ValueError("Nonregular collection has a date")
    if not without_index:
        import numpy as np
        from app.services.embedding_search_service import EmbeddingSearchService

        for key in ["mainland", "sekizen"]:
            profile = reg.profiles[key]
            index = EmbeddingSearchService(
                items_path=profile.items_path,
                embeddings_path=profile.embedding_index_path,
                runtime_client=object(),
                municipality_id=CITY,
                profile_id=key,
            )
            if not index.is_ready:
                raise ValueError("Index not ready: " + key)
            with np.load(profile.embedding_index_path, allow_pickle=False) as data:
                if data["item_ids"].tolist() != [r["item_id"] for r in rows[key]]:
                    raise ValueError("Index ID order differs")
    print(
        "Verified Imabari data"
        + (" (without paid index)" if without_index else " and both indices")
    )


def activate():
    verify()
    path = ROOT / "data/regions/catalog.json"
    catalog = read(path)
    entry = dict(id=CITY, registry_path="imabari/registry.json")
    entries = catalog["municipalities"]
    current = next((e for e in entries if e["id"] == CITY), None)
    if current and current != entry:
        raise ValueError("Conflicting existing catalog entry")
    if not current:
        entries.append(entry)
    write(path, catalog)
    print("Registered only Imabari, preserving all existing municipalities")


def main():
    global DATA
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["fetch", "inspect", "build", "verify", "activate", "audit-images"],
    )
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--without-index", action="store_true")
    args = parser.parse_args()
    DATA = args.data_dir.resolve()
    if args.command == "verify":
        verify(args.without_index)
    elif args.command == "audit-images":
        from imabari_image_audit import run_ocr

        run_ocr(DATA)
    else:
        globals()[args.command]()


if __name__ == "__main__":
    main()
