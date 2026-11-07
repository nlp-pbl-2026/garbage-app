#!/usr/bin/env python3
"""Reproduce Kamijima Town data from pinned official one-page guides.

The free workflow is fetch -> inspect -> build -> verify.  It never invokes
Bedrock, edits another municipality, deploys to AWS, or extrapolates beyond the
reviewed 2026 fiscal-year interval.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import ssl
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/kamijima"
CITY = "38356"
VERSION = "kamijima-2026.1"
VALID_FROM = "2026-04-01"
VALID_TO = "2027-03-31"
HOST = "www.town.kamijima.lg.jp"
PAGE_URL = "https://www.town.kamijima.lg.jp/soshiki/5/665.html"
COPYRIGHT_URL = "https://www.town.kamijima.lg.jp/site/userguide/1434.html"
GUIDE_URL = "https://www.town.kamijima.lg.jp/uploaded/attachment/6629.pdf"
PDF_URLS = {
    "yuge": "https://www.town.kamijima.lg.jp/uploaded/attachment/6620.pdf",
    "ikina": "https://www.town.kamijima.lg.jp/uploaded/attachment/6621.pdf",
    "iwagi": "https://www.town.kamijima.lg.jp/uploaded/attachment/6622.pdf",
    "uoshima": "https://www.town.kamijima.lg.jp/uploaded/attachment/6623.pdf",
}
SOURCES = {
    "copyright.html": COPYRIGHT_URL,
    "guide-page.html": PAGE_URL,
    "guide.pdf": GUIDE_URL,
    **{f"{slug}.pdf": url for slug, url in PDF_URLS.items()},
}

COLLECTION_TYPES = (
    "burnable", "nonburnable", "cans", "metals_hazardous",
    "newspaper", "cardboard", "magazines", "bulky",
)


def rule(types, weekdays, occurrences=(1, 2, 3, 4, 5), months=range(1, 13)):
    return {
        "types": list(types), "weekdays": list(weekdays),
        "occurrences": list(occurrences), "months": list(months),
    }


COMMON_THURSDAY = [
    rule(("metals_hazardous",), (4,), (4,), (2, 4, 6, 8, 10, 12)),
    rule(("newspaper",), (4,), (1,)),
    rule(("cardboard",), (4,), (2,)),
    rule(("magazines",), (4,), (3,)),
    rule(("bulky",), (4,), (4,), (1, 3, 5, 7, 9, 11)),
]

COMMON_WEDNESDAY = [
    rule(("nonburnable",), (3,), (2,)),
    rule(("cans",), (3,), (1, 3)),
    rule(("metals_hazardous",), (3,), (4,), (2, 4, 6, 8, 10, 12)),
    rule(("newspaper",), (4,), (1,)),
    rule(("cardboard",), (4,), (2,)),
    rule(("magazines",), (4,), (3,)),
    rule(("bulky",), (3,), (4,), (1, 3, 5, 7, 9, 11)),
]


AREAS = [
    {
        "id": "38356-01", "name": "弓削地区1",
        "display_name": "弓削：久司浦・沢津・上弓削・緑ヶ丘・引野・明神",
        "calendar_id": "kamijima-yuge-1", "rule_profile_id": "main_islands",
        "source_file": "yuge.pdf",
        "address_labels": ["久司浦", "沢津", "上弓削", "緑ヶ丘", "引野", "明神"],
        "rules": [
            rule(("burnable",), (1, 4)),
            rule(("nonburnable",), (3,), (1, 3)),
            rule(("cans",), (3,), (2, 4)),
            *COMMON_THURSDAY,
        ],
    },
    {
        "id": "38356-02", "name": "弓削地区2",
        "display_name": "弓削：中都・浜都・日比・太田・土生・鎌田",
        "calendar_id": "kamijima-yuge-2", "rule_profile_id": "main_islands",
        "source_file": "yuge.pdf",
        "address_labels": ["中都", "浜都", "日比", "太田", "土生", "鎌田"],
        "rules": [
            rule(("burnable",), (2, 5)),
            rule(("nonburnable",), (1,), (1, 3)),
            rule(("cans",), (1,), (2, 4)),
            *COMMON_THURSDAY,
        ],
    },
    {
        "id": "38356-03", "name": "弓削地区3",
        "display_name": "弓削：岳の下・狩尾・大谷・佐島・藤谷",
        "calendar_id": "kamijima-yuge-3", "rule_profile_id": "main_islands",
        "source_file": "yuge.pdf",
        "address_labels": ["岳の下", "狩尾", "大谷", "佐島", "藤谷"],
        "rules": [
            rule(("burnable",), (2, 5)),
            rule(("nonburnable",), (3,), (1, 3)),
            rule(("cans",), (3,), (2, 4)),
            *COMMON_THURSDAY,
        ],
    },
    {
        "id": "38356-04", "name": "生名南（1～3分団）",
        "display_name": "生名南：稲浦・奥里・脇・前新開・久保の谷・中の谷・厳島・浦の浜・中側・岡庄・中後・尾又",
        "calendar_id": "kamijima-ikina-south", "rule_profile_id": "main_islands",
        "source_file": "ikina.pdf",
        "address_labels": ["稲浦", "奥里", "脇", "前新開", "久保の谷", "中の谷", "厳島", "浦の浜", "中側", "岡庄", "中後", "尾又"],
        "rules": [rule(("burnable",), (1, 4)), *COMMON_WEDNESDAY],
    },
    {
        "id": "38356-05", "name": "生名北（4～6分団）",
        "display_name": "生名北：南寮・深浦・丸山・南立石・北立石・公営住宅・恵生・西浦",
        "calendar_id": "kamijima-ikina-north", "rule_profile_id": "main_islands",
        "source_file": "ikina.pdf",
        "address_labels": ["南寮", "深浦", "丸山", "南立石", "北立石", "公営住宅", "恵生", "西浦"],
        "rules": [rule(("burnable",), (2, 5)), *COMMON_WEDNESDAY],
    },
    {
        "id": "38356-06", "name": "岩城A地区",
        "display_name": "岩城A：東1・東2・西・高原・大谷・新地・谷",
        "calendar_id": "kamijima-iwagi-a", "rule_profile_id": "main_islands",
        "source_file": "iwagi.pdf",
        "address_labels": ["東1", "東2", "西", "高原", "大谷", "新地", "谷"],
        "rules": [
            rule(("burnable",), (1, 4)),
            rule(("nonburnable",), (3,), (2,)),
            rule(("cans",), (3,), (1, 3)),
            rule(("metals_hazardous",), (3,), (4,), (2, 4, 6, 8, 10, 12)),
            rule(("newspaper",), (4,), (2,)),
            rule(("cardboard",), (4,), (3,)),
            rule(("magazines",), (4,), (4,)),
            rule(("bulky",), (3,), (4,), (1, 3, 5, 7, 9, 11)),
        ],
    },
    {
        "id": "38356-07", "name": "岩城B地区",
        "display_name": "岩城B：浜・浜2・西部・赤石・小漕・長江・船越・海原",
        "calendar_id": "kamijima-iwagi-b", "rule_profile_id": "main_islands",
        "source_file": "iwagi.pdf",
        "address_labels": ["浜", "浜2", "西部", "赤石", "小漕", "長江", "船越", "海原"],
        "rules": [
            rule(("burnable",), (2, 5)),
            rule(("nonburnable",), (3,), (2,)),
            rule(("cans",), (3,), (1, 3)),
            rule(("metals_hazardous",), (3,), (4,), (2, 4, 6, 8, 10, 12)),
            rule(("newspaper",), (4,), (2,)),
            rule(("cardboard",), (4,), (3,)),
            rule(("magazines",), (4,), (4,)),
            rule(("bulky",), (3,), (4,), (1, 3, 5, 7, 9, 11)),
        ],
    },
    {
        "id": "38356-08", "name": "魚島地区",
        "display_name": "魚島地区（魚島クリーンセンター持込）",
        "calendar_id": "kamijima-uoshima", "rule_profile_id": "uoshima",
        "source_file": "uoshima.pdf", "address_labels": ["魚島"],
        "rules": [rule(COLLECTION_TYPES, (1, 2, 3, 4, 5))],
    },
]


ITEM_GROUPS = [
    ("burnable", "燃やせるごみ", [
        "台所ごみ", "生ごみ", "卵殻", "貝殻", "衣類", "毛布", "ペットボトル",
        "ポリバケツ", "ゴム製品", "食用油", "皮製品", "ビニール類", "靴",
        "折詰容器", "アルミホイル", "灰", "発泡スチロール", "木くず",
        "庭木の剪定枝",
    ], "", []),
    ("burnable", "燃やせるごみ", ["ダンボール（雨で濡れたもの）"],
     "雨で濡れるなど資源ごみで出せないダンボールは燃やせるごみです。", ["cardboard"]),
    ("bottles", "ビン類", ["飲料用びん", "食品用びん", "化粧品の空きびん", "割れたびん"], "", []),
    ("glass", "ガラス類", ["板ガラス", "ガラス食器", "鏡", "LED電球", "白熱電球"], "", []),
    ("ceramics", "陶器類", ["せともの", "茶碗", "花瓶", "壺", "植木鉢（少量）", "七輪"],
     "植木鉢は少量に限ります。量が多い場合は最終処分場へ持ち込みます。", ["landfill"]),
    ("cans", "缶類", ["ジュース缶", "ビール缶", "スプレー缶", "カセットボンベ", "菓子缶", "調味料缶"],
     "スプレー缶・カセットボンベは完全に使い切り、穴を開けません。", []),
    ("small_metals", "小物金属類", ["鍋", "やかん", "包丁", "金ざる", "ハサミ", "釘", "針金", "栓抜き", "一斗缶"],
     "金属以外を取り除き、釘・ネジ等は袋に入れます。", []),
    ("hazardous", "有害ごみ", ["乾電池", "ライター", "カッターの刃", "カミソリ", "針", "温度計（水銀）", "水銀体温計", "蛍光管"],
     "刃先の鋭い物は安全に包みます。水銀使用廃製品は排出容器を分け、破損品は袋に入れます。", []),
    ("newspaper", "古紙類（新聞）", ["新聞紙"], "20～30cm程度にひもで十字に縛ります。", []),
    ("cardboard", "古紙類（ダンボール）", ["ダンボール"],
     "断面が波状の物をひもで十字に縛ります。雨で濡れるなど資源に出せない場合は燃やせるごみです。", ["burnable"]),
    ("magazines", "古紙類（雑誌）", ["雑誌", "本", "カタログ", "教科書", "チラシ", "空き箱（菓子類）", "厚紙"],
     "20～30cm程度にひもで十字に縛り、粘着テープは使いません。", []),
    ("bulky", "可燃系粗大ごみ", ["タンス", "木製家具", "ふとん"],
     "可燃系粗大ごみです。粗大ごみシールを料金表に対応する金額分貼ります。", []),
    ("bulky", "不燃系粗大ごみ", ["電化製品（家電リサイクル対象外）", "自転車", "ガスコンロ"],
     "不燃系粗大ごみです。家電リサイクル対象品は含みません。", []),
    ("appliance_recycling", "家電リサイクル対象製品", ["冷蔵庫", "冷凍庫", "テレビ", "エアコン", "洗濯機"],
     "購入店または買替え店へ引取りを依頼します。依頼できない場合のみ町で取り扱います。", []),
    ("landfill", "最終処分場搬入物", ["土", "石", "瓦", "煉瓦", "コンクリート殻（鉄筋を除く）", "植木鉢（多量）"],
     "役場で受付を済ませてから最終処分場へ持ち込みます。魚島地区は事前に役場へ相談してください。", []),
    ("not_collected", "町で収集・処理できない物", [
        "産業廃棄物", "建築廃材", "漁網", "農業用廃ビニール", "バイク", "農薬",
        "劇毒物", "消火器", "業務用ガスボンベ", "バッテリー", "ピアノ", "タイヤ",
        "廃油", "ガソリン", "灯油", "FRP製品", "船外機", "パソコン", "その他危険物",
        "ボタン電池", "充電用電池", "携帯電話の電池",
    ], "販売店、メーカー、修理業者または専門業者へ依頼します。", []),
]


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def fetch():
    pinned = {row["file"]: row for row in read(DATA / "sources.json")["sources"]}
    records = []
    for filename, url in SOURCES.items():
        parsed = urlparse(url)
        if parsed.hostname != HOST or Path(filename).name != filename:
            raise ValueError("Unexpected Kamijima source location")
        request = Request(url, headers={"User-Agent": "garbage-app-data-builder/1.0"})
        try:
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            context = ssl.create_default_context()
        body = urlopen(request, timeout=90, context=context).read()
        path = DATA / "source" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        actual = digest(path)
        if filename not in pinned or pinned[filename]["url"] != url or pinned[filename]["sha256"] != actual:
            raise ValueError(f"Official Kamijima source changed: {filename}")
        records.append({"file": filename, "url": url, "sha256": actual,
                        "retrieved_at": datetime.now(timezone.utc).isoformat()})
    write(DATA / "source/downloads.json", sorted(records, key=lambda row: row["file"]))
    print(f"Saved and verified {len(records)} official Kamijima source files")


def checked_sources():
    reviewed = read(DATA / "sources.json")
    if reviewed["municipality_id"] != CITY or reviewed["version"] != VERSION:
        raise ValueError("Kamijima source review identity mismatch")
    for record in reviewed["sources"]:
        path = DATA / "source" / record["file"]
        if not path.is_file() or record["url"] != SOURCES.get(record["file"]) or digest(path) != record["sha256"]:
            raise ValueError(f"Kamijima source missing or changed: {record['file']}")
    return reviewed


def _validate_rules(rules):
    for entry in rules:
        if set(entry) != {"types", "weekdays", "occurrences", "months"}:
            raise ValueError("Unexpected recurrence field")
        if (not entry["types"] or not set(entry["types"]) <= set(COLLECTION_TYPES)
                or not entry["weekdays"] or any(day not in range(1, 8) for day in entry["weekdays"])
                or not entry["occurrences"] or any(n not in range(1, 6) for n in entry["occurrences"])
                or not entry["months"] or any(month not in range(1, 13) for month in entry["months"])):
            raise ValueError("Invalid Kamijima recurrence")


def expand_rules(rules):
    _validate_rules(rules)
    result = {}
    current = date.fromisoformat(VALID_FROM)
    end = date.fromisoformat(VALID_TO)
    while current <= end:
        codes = set()
        occurrence = (current.day - 1) // 7 + 1
        for entry in rules:
            if (current.month in entry["months"] and current.isoweekday() in entry["weekdays"]
                    and occurrence in entry["occurrences"]):
                codes.update(entry["types"])
        if codes:
            result[current.isoformat()] = sorted(codes)
        current += timedelta(days=1)
    return result


def reviewed_areas():
    return [{key: value for key, value in area.items() if key != "rules"} for area in AREAS]


def calendar_payload():
    calendars = {}
    reviews = []
    for area in AREAS:
        days = expand_rules(area["rules"])
        source_url = PDF_URLS[area["source_file"].removesuffix(".pdf")]
        calendars[area["calendar_id"]] = {
            "source_url": source_url,
            "verification_status": "checked",
            "days": days,
            "exceptions": [],
        }
        reviews.append({
            "area_id": area["id"], "calendar_id": area["calendar_id"],
            "source_file": area["source_file"], "address_labels": area["address_labels"],
            "rules": area["rules"], "days_sha256": value_digest(days),
            "dated_cells": len(days),
            "collection_dates": dict(sorted(Counter(code for values in days.values() for code in values).items())),
        })
    review = {
        "schema_version": 1, "municipality_id": CITY, "version": VERSION,
        "valid_from": VALID_FROM, "valid_to": VALID_TO,
        "areas": reviews,
        "verification": {
            "method": "The four official one-page district guides were rendered at 180 dpi and visually reviewed; their weekly, Nth-weekday, odd-month and even-month rules were expanded to explicit dates.",
            "coverage": "Three Yuge groups, two Ikina groups, two Iwagi groups and the Uoshima weekday drop-off schedule.",
            "limitations": "The guides do not state holiday, year-end or temporary exceptions. No exception was invented; dates are the direct recurrence expansion and must be regenerated if the official guides change.",
            "reviewed_at": "2026-11-07"
        }
    }
    return calendars, review


def item_definitions():
    rows = []
    number = 1
    for category, source_category, names, note, options in ITEM_GROUPS:
        for name in names:
            rows.append({
                "item_id": f"kamijima-{number:04d}", "item": name,
                "category": category, "source_category": source_category,
                "note": note, "category_options": list(options),
            })
            number += 1
    if len({row["item_id"] for row in rows}) != len(rows) or len({row["item"] for row in rows}) != len(rows):
        raise ValueError("Duplicate Kamijima item or ID")
    return rows


def item_review():
    rows = item_definitions()
    return {
        "schema_version": 1, "municipality_id": CITY, "version": VERSION,
        "official_item_examples": len(rows), "items_sha256": value_digest(rows),
        "categories": dict(sorted(Counter(row["category"] for row in rows).items())),
        "conditional_records": sum(bool(row["category_options"]) for row in rows),
        "source_files": ["guide.pdf", "yuge.pdf", "ikina.pdf", "iwagi.pdf", "uoshima.pdf"],
        "verification": {
            "method": "Named examples and explicit exclusions were transcribed from the rendered official guides and checked against PDF text extraction where available.",
            "limitations": "This is the complete set of named examples in the reviewed guides, not an exhaustive municipality dictionary. Unknown items must not be classified solely by analogy.",
            "reviewed_at": "2026-11-07"
        }
    }


def item_rows():
    categories = read(DATA / "official_rules.json")["categories"]
    rows = []
    for item in item_definitions():
        definition = categories[item["category"]]
        aliases = {
            "充電用電池": "充電式電池 リチウムイオン電池",
            "携帯電話の電池": "携帯電話 電池パック",
            "バイク": "原付 オートバイ 二輪車",
        }.get(item["item"], "")
        rows.append({
            "item_id": item["item_id"], "item": item["item"],
            "category": item["category"], "category_display": definition["name"],
            "note": item["note"], "search_text": " ".join(filter(None, (
                item["item"], aliases, item["source_category"], item["note"], definition.get("instructions", "")
            ))),
            "disposal_instructions": definition.get("instructions", ""),
            "category_options": json.dumps(item["category_options"], ensure_ascii=False),
            "source_url": PDF_URLS["yuge"], "source_category": item["source_category"],
        })
    return rows


def _bulky_config(profile_id):
    fish = profile_id == "uoshima"
    return {
        "municipality_id": CITY, "municipality_name": "上島町",
        "collection_frequency": ("月曜日から金曜日に魚島クリーンセンターへ持込"
                                 if fish else "奇数月の地区指定第4曜日に収集"),
        "reception_hours": ("魚島クリーンセンター：月～金 7:00～10:00"
                            if fish else "直接搬入：月～金 13:30～16:50"),
        "collection_rules": "粗大ごみ処理手数料表を確認し、金額分のシールを貼って、可燃系と不燃系を分けます。直接搬入は料金半額です。",
        "fee_structure_type": "size_based", "application_method": "none",
        "phone_number": "0897-78-0011" if fish else "0897-77-2503",
        "web_form_url": None, "information_url": PAGE_URL,
        "steps": [
            {"step_number": 1, "title": "品目を確認", "description": "可燃系粗大ごみと不燃系粗大ごみを分け、家電リサイクル品や町で処理できない物を除きます。"},
            {"step_number": 2, "title": "手数料を確認", "description": "公式の粗大ごみ処理手数料表を確認し、役場で必要な金額分の粗大ごみシールを購入します。"},
            {"step_number": 3, "title": "シールを貼って排出", "description": ("魚島クリーンセンターの平日受入時間に持ち込みます。" if fish else "選択した地区の公式カレンダー日までにシールを貼り、指定場所へ出します。")},
            {"step_number": 4, "title": "直接搬入する場合", "description": "公式案内の受付時間を確認し、可燃系と不燃系を分けて搬入します。"},
        ],
    }


def _profile(profile_id, rules):
    fish = profile_id == "uoshima"
    categories = {}
    for code, definition in rules["categories"].items():
        category = {key: value for key, value in definition.items() if key != "instructions"}
        if category.get("collection_type_id"):
            category["cutoff"] = "10:00" if fish else "08:00"
            if fish:
                category["start_time"] = "07:00"
                category["time_note"] = "月曜日から金曜日の午前7時から午前10時までに魚島クリーンセンターへ持ち込みます。"
        categories[code] = category
    profile_rules = rules["classification_rules"]
    if fish:
        profile_rules += " 魚島地区では定期区分を月曜日から金曜日の午前7時から午前10時までに魚島クリーンセンターへ持ち込む。"
    return {
        "items_path": "knowledge/items.csv",
        "embedding_index_path": "knowledge/item_embeddings.npz",
        "index_profile_id": "citywide",
        "calendar_path": "generated/calendar-2026.json",
        "classification_rules": profile_rules,
        "size_question": "品目の素材、大きさ、家電リサイクル対象かどうかは分かりますか？",
        "knowledge_title": "上島町家庭ごみの正しい出し方",
        "categories": categories,
        "bulky_waste": {
            "category_code": "bulky", "collection_type_id": "bulky",
            "config": _bulky_config(profile_id),
        },
    }


def build(*, inspect_only=False):
    checked_sources()
    calendars, calendar_review = calendar_payload()
    current_item_review = item_review()
    write(DATA / "generated/calendar-review-candidate.json", calendar_review)
    write(DATA / "generated/item-review-candidate.json", current_item_review)
    write(DATA / "generated/areas-candidate.json", {"areas": reviewed_areas()})
    if inspect_only:
        print("Wrote Kamijima calendar, area and item review candidates")
        return
    if read(DATA / "calendar_reviews.json") != calendar_review:
        raise ValueError("Kamijima calendar rules differ from the reviewed record")
    if read(DATA / "item_reviews.json") != current_item_review:
        raise ValueError("Kamijima item examples differ from the reviewed record")
    if read(DATA / "areas.json") != {"areas": reviewed_areas()}:
        raise ValueError("Kamijima area mapping differs from the reviewed record")
    rules = read(DATA / "official_rules.json")
    areas = []
    for area in AREAS:
        areas.append({
            "id": area["id"], "name": area["name"], "display_name": area["display_name"],
            "calendar_id": area["calendar_id"], "rule_profile_id": area["rule_profile_id"],
            "address_labels": area["address_labels"], "needs_local_confirmation": True,
            "source_url": PDF_URLS[area["source_file"].removesuffix(".pdf")],
        })
    registry = {
        "schema_version": 1, "municipality_id": CITY, "municipality_name": "上島町",
        "prefecture_id": "38", "prefecture_name": "愛媛県", "version": VERSION,
        "valid_from": VALID_FROM, "valid_to": VALID_TO,
        "collection_areas": areas,
        "calendars": [{"id": area["calendar_id"], "rule_profile_id": area["rule_profile_id"]} for area in AREAS],
        "rule_profiles": {
            "main_islands": _profile("main_islands", rules),
            "uoshima": _profile("uoshima", rules),
        },
    }
    write(DATA / "registry.json", registry)
    write(DATA / "generated/calendar-2026.json", {
        "municipality_id": CITY, "version": VERSION,
        "valid_from": VALID_FROM, "valid_to": VALID_TO, "calendars": calendars,
    })
    entries = []
    for area in areas:
        entries.extend({"town": label, "lookup_town": label, "area_id": area["id"]}
                       for label in area["address_labels"])
    write(DATA / "generated/addresses.json", {
        "municipality_id": CITY, "version": VERSION, "entries": entries,
    })
    rows = item_rows()
    target = DATA / "knowledge/items.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write(DATA / "generated/item-review.json", {
        "item_count": len(rows), "csv_sha256": digest(target),
        "categories": dict(sorted(Counter(row["category"] for row in rows).items())),
    })
    print(f"Built {len(areas)} Kamijima areas, {len(calendars)} calendars and {len(rows)} item records")


def verify(*, without_index=False):
    checked_sources()
    calendars, calendar_review = calendar_payload()
    if read(DATA / "calendar_reviews.json") != calendar_review or read(DATA / "item_reviews.json") != item_review():
        raise ValueError("Kamijima reviewed metadata changed")
    registry = read(DATA / "registry.json")
    bundle = read(DATA / "generated/calendar-2026.json")
    if bundle["calendars"] != calendars or registry["collection_areas"] != [
        {"id": area["id"], "name": area["name"], "display_name": area["display_name"],
         "calendar_id": area["calendar_id"], "rule_profile_id": area["rule_profile_id"],
         "address_labels": area["address_labels"], "needs_local_confirmation": True,
         "source_url": PDF_URLS[area["source_file"].removesuffix(".pdf")]} for area in AREAS
    ]:
        raise ValueError("Kamijima generated registry/calendar changed")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError("Kamijima item CSV changed")
    index = DATA / "knowledge/item_embeddings.npz"
    manifest = DATA / "knowledge/index_manifest.json"
    if not without_index:
        if not index.is_file() or not manifest.is_file():
            raise ValueError("Kamijima embedding index is missing")
        metadata = read(manifest)
        if (metadata["municipality_id"] != CITY or metadata["profile_id"] != "citywide"
                or metadata["item_count"] != len(rows) or metadata["source_sha256"] != digest(DATA / "knowledge/items.csv")
                or metadata["index_sha256"] != digest(index)):
            raise ValueError("Kamijima CSV/index/manifest mismatch")
    result = {
        "item_count": len(rows), "collection_areas": len(AREAS), "calendars": len(calendars),
        "valid_from": VALID_FROM, "valid_to": VALID_TO,
        "embedding_ready": index.is_file() and manifest.is_file(),
        "catalog_registered": any(row["id"] == CITY for row in read(ROOT / "data/regions/catalog.json")["municipalities"]),
    }
    write(DATA / "generated/verification.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "inspect", "build", "verify"))
    parser.add_argument("--without-index", action="store_true")
    args = parser.parse_args()
    if args.command == "fetch":
        fetch()
    elif args.command == "inspect":
        build(inspect_only=True)
    elif args.command == "build":
        build()
    else:
        verify(without_index=args.without_index)
