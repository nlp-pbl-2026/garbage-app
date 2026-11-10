#!/usr/bin/env python3
"""Build reviewed Seiyo City items and fiscal-2026 collection calendars.

The free workflow fetches pinned official files, reads the locally reviewed
dictionary extraction, builds municipality assets, and verifies them.  It does
not invoke Bedrock, deploy AWS resources, or infer unlisted collection dates.
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
import unicodedata
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/seiyo"
CITY = "38214"
VERSION = "seiyo-2026.1"
VALID_FROM = "2026-04-01"
VALID_TO = "2027-03-31"
HOST = "www.city.seiyo.ehime.jp"
GUIDE_PAGE_URL = f"https://{HOST}/kakuka/seikatsu_fukushi/kankyo_eisei/gomi/311.html"
CALENDAR_PAGE_URL = f"https://{HOST}/kakuka/seikatsu_fukushi/kankyo_eisei/gomi/calenda/index.html"
COPYRIGHT_URL = f"https://{HOST}/kakuka/seisaku_kikaku/seisakusuishin/saitonitsuite/430.html"


def material(name: str) -> str:
    return f"https://{HOST}/material/files/group/15/{name}"


SOURCES = {
    "guide-page.html": GUIDE_PAGE_URL,
    "calendar-index.html": CALENDAR_PAGE_URL,
    "copyright.html": COPYRIGHT_URL,
    "guide-1.pdf": material("hyoushi.pdf"),
    "guide-2.pdf": material("wakekata2.pdf"),
    "guide-3.pdf": material("wakekata3.pdf"),
    "dictionary.pdf": material("gomijiten.pdf"),
    "akehama.pdf": material("R08akehama.pdf"),
    "uwa-1.pdf": material("R8uwa1.pdf"),
    "uwa-2.pdf": material("R8uwa2.pdf"),
    "uwa-3.pdf": material("R8uwa3.pdf"),
    "nomura.pdf": material("R8nomura_nomura_omote.pdf"),
    "nomura-course.pdf": material("R8nomura_nomura_course.pdf"),
    "nomura-nakasuji.pdf": material("R8nomura_nakasuji_kurara_kaifuki_yokobayashi.pdf"),
    "nomura-tanisuji.pdf": material("R8nomura_tanisuji_age_kamagawa.pdf"),
    "nomura-onaru.pdf": material("R8nomura_onaru2.pdf"),
    "nomura-sogawa.pdf": material("R8nomura_sogawa2.pdf"),
    "nomura-oonogahara.pdf": material("R8nomura_oonogahara.pdf"),
    "shirokawa.pdf": material("R8shirokawa.pdf"),
    "mikame-east.pdf": material("R8mikame_east.pdf"),
    "mikame-south.pdf": material("R8mikame_south.pdf"),
    "mikame-north.pdf": material("R8mikame_north.pdf"),
}

ALL_SCHEDULED = (
    "burnable", "landfill", "newspaper", "misc_paper", "milk_carton",
    "cardboard", "container_plastic", "other_plastic", "metal",
    "small_appliance", "clothes", "pet", "bottles", "cans",
    "used_oil", "bulky",
)
UWA_CLOSURES = {"2026-12-31", "2027-01-01", "2027-01-02", "2027-01-03"}
MIKAME_CLOSURES = {"2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02", "2027-01-03"}
NOMURA_CLOSURES = {"2026-08-15", "2026-12-31", "2027-01-01", "2027-01-02", "2027-01-03"}


def rule(types, weekdays, occurrences=(1, 2, 3, 4, 5), months=range(1, 13), *, operational=False):
    return {
        "types": list(types), "weekdays": list(weekdays),
        "occurrences": list(occurrences), "months": list(months),
        "operational": operational,
    }


AKEHAMA_RULES = [
    rule(("burnable",), (1, 4)),
    rule(("landfill",), (3,), (1,)),
    rule(("newspaper", "misc_paper", "milk_carton"), (2,), (1, 3)),
    rule(("other_plastic",), (2,), (2,)),
    rule(("metal", "small_appliance"), (3,), (2,)),
    rule(("clothes",), (5,), (1,)),
    rule(("container_plastic",), (5,), (2, 4)),
    rule(("cardboard",), (5,), (3,)),
    rule(("pet",), (6,), (1,), operational=True),
    rule(("bottles",), (6,), (2,), operational=True),
    rule(("cans",), (6,), (3,), operational=True),
    rule(("used_oil",), (2,), (4,)),
]


def uwa_rules(primary_weekdays, cycle_weekday, cycle):
    result = [rule(("burnable",), primary_weekdays)]
    for occurrence, types in enumerate(cycle, start=1):
        result.append(rule(types, (cycle_weekday,), (occurrence,), operational=True))
    result.append(rule(("used_oil",), (5,), (2,), operational=True))
    return result


UWA1_RULES = uwa_rules((1, 4), 1, [
    ("container_plastic", "cans"), ("other_plastic", "cans"),
    ("container_plastic", "cans"), ("landfill", "cans", "small_appliance", "metal"),
]) + [
    rule(("bottles",), (4,), (1, 3), operational=True),
    rule(("pet",), (4,), (2, 4), operational=True),
    rule(("newspaper", "misc_paper", "milk_carton", "cardboard"), (4,), (3,), operational=True),
    rule(("clothes",), (4,), (4,), operational=True),
]
UWA2_RULES = uwa_rules((2, 5), 2, [
    ("container_plastic", "cans"), ("other_plastic", "cans"),
    ("container_plastic", "cans"), ("landfill", "cans", "small_appliance", "metal"),
]) + [
    rule(("bottles",), (5,), (1, 3), operational=True),
    rule(("pet",), (5,), (2, 4), operational=True),
    rule(("newspaper", "misc_paper", "milk_carton", "cardboard"), (5,), (3,), operational=True),
    rule(("clothes",), (5,), (4,), operational=True),
]
UWA3_RULES = uwa_rules((3, 6), 3, [
    ("container_plastic", "cans"), ("other_plastic", "cans"),
    ("container_plastic", "cans"), ("landfill", "cans", "small_appliance", "metal"),
]) + [
    rule(("bottles",), (6,), (1, 3), operational=True),
    rule(("pet",), (6,), (2, 4), operational=True),
    rule(("newspaper", "misc_paper", "milk_carton", "cardboard"), (6,), (3,), operational=True),
    rule(("clothes",), (6,), (4,), operational=True),
]


NOMURA_RESOURCES = [
    rule(("landfill", "small_appliance", "metal"), (1,), (1,)),
    rule(("cans",), (1,), (2,)), rule(("other_plastic",), (2,), (2,)),
    rule(("pet", "container_plastic"), (3,), (1, 3)),
    rule(("bottles",), (4,), (2,)), rule(("clothes",), (5,), (2,)),
    rule(("newspaper", "misc_paper", "milk_carton", "cardboard"), (6,), (2,), operational=True),
    rule(("bulky",), (7,), (3,), (2, 4, 6, 8, 10, 12)),
    rule(("used_oil",), (4,), (4,)),
]
NAKASUJI_RESOURCES = [
    rule(("cans",), (1,), (3,)), rule(("other_plastic",), (2,), (3,)),
    rule(("pet", "container_plastic"), (3,), (2, 4)),
    rule(("landfill", "small_appliance", "metal"), (4,), (1,)),
    rule(("bottles",), (4,), (3,)), rule(("clothes",), (5,), (3,)),
    rule(("newspaper", "misc_paper", "milk_carton", "cardboard"), (6,), (3,)),
    rule(("bulky",), (7,), (3,), (2, 4, 6, 8, 10, 12)),
    rule(("used_oil",), (4,), (4,)),
]
ONARU_RESOURCES = [
    rule(("landfill", "small_appliance", "metal"), (1,), (1,)),
    rule(("cans",), (2,), (1,)),
    rule(("pet", "container_plastic"), (3,), (1, 3)),
    rule(("other_plastic", "bottles", "clothes"), (4,), (1,)),
    rule(("newspaper", "misc_paper", "milk_carton", "cardboard"), (6,), (4,)),
    rule(("bulky",), (7,), (3,), (2, 4, 6, 8, 10, 12)),
    rule(("used_oil",), (4,), (4,)),
]
SOGAWA_COMMON = [
    rule(("cans",), (1,), (4,)), rule(("other_plastic",), (2,), (4,)),
    rule(("pet", "container_plastic"), (3,), (2, 4)),
    rule(("bottles", "used_oil"), (4,), (4,)),
    rule(("bulky",), (7,), (2,), (3, 5, 9, 12)),
]
OONOGAHARA_RULES = [
    rule(("burnable",), (6,)),
    rule(("newspaper", "misc_paper", "milk_carton", "cardboard", "clothes", "pet",
          "container_plastic", "bottles", "cans", "other_plastic", "metal",
          "small_appliance", "landfill", "used_oil"), (5,), (1,), operational=True),
    rule(("bulky",), (7,), (3,), (4, 10)),
]
SHIROKAWA_COMMON = [
    rule(("burnable",), (2, 5)), rule(("cans",), (1,), (4,)),
    rule(("other_plastic",), (2,), (4,)),
    rule(("pet", "container_plastic"), (3,), (2, 4)),
    rule(("bottles", "used_oil"), (4,), (4,)),
    rule(("bulky",), (7,), (2,), (3, 5, 9, 12)),
]


def mikame_rules(*, burnable, paper, clothes_occurrence, specialty):
    result = [
        rule(("burnable",), burnable),
        rule(("newspaper", "misc_paper", "milk_carton", "cardboard"), paper),
        rule(("clothes",), paper, (clothes_occurrence,)),
        rule(("landfill",), (3,), (1,)), rule(("container_plastic",), (3,), (2, 4)),
        rule(("other_plastic",), (3,), (3 if paper == (1,) else 4,)),
        rule(("pet",), (6,), (1,)), rule(("bottles",), (6,), (2,)), rule(("cans",), (6,), (3,)),
        rule(("used_oil",), (3,), (4,)),
    ]
    for types, months in specialty:
        result.append(rule(types, (6,), (4,), months))
    return result


MIKAME_EAST = mikame_rules(
    burnable=(1, 4), paper=(2,), clothes_occurrence=1,
    specialty=[(("bulky",), (1, 4, 7, 10)), (("small_appliance",), (2, 5, 8, 11)), (("metal",), (3, 6, 9, 12))],
)
MIKAME_NORTH = mikame_rules(
    burnable=(2, 5), paper=(1,), clothes_occurrence=3,
    specialty=[(("metal",), (1, 4, 7, 10)), (("bulky",), (2, 5, 8, 11)), (("small_appliance",), (3, 6, 9, 12))],
)
MIKAME_SOUTH = mikame_rules(
    burnable=(2, 5), paper=(1,), clothes_occurrence=2,
    specialty=[(("small_appliance",), (1, 4, 7, 10)), (("metal",), (2, 5, 8, 11)), (("bulky",), (3, 6, 9, 12))],
)


def area(number, name, display_name, profile, source, labels, rules, closures):
    return {
        "id": f"{CITY}-{number:02d}", "name": name, "display_name": display_name,
        "calendar_id": f"seiyo-{number:02d}", "rule_profile_id": profile,
        "source_file": source, "address_labels": labels,
        "rules": rules, "closures": set(closures),
    }


AREAS = [
    area(1, "明浜地区", "明浜：俵津・渡江・狩浜・高山・宮野浦・田之浜", "cutoff_0800", "akehama.pdf",
         ["明浜町", "俵津", "渡江", "狩浜", "高山", "宮野浦", "田之浜"], AKEHAMA_RULES, UWA_CLOSURES),
    area(2, "宇和地区1", "宇和1：卯之町8～16区・鬼窪1～7区・伊賀上1～7区・多田・中川・坂戸ほか", "cutoff_0700", "uwa-1.pdf",
         ["卯之町8～16区", "鬼窪1～7区", "伊賀上1～7区", "みどり団地", "多田", "中川", "坂戸"], UWA1_RULES, UWA_CLOSURES),
    area(3, "宇和地区2", "宇和2：卯之町1～7区・鬼窪8～9区・郷団地・神領団地・石城・山田ほか", "cutoff_0700", "uwa-2.pdf",
         ["卯之町1～7区", "鬼窪8～9区", "郷団地", "神領団地", "久枝1区", "ひまわり", "石城", "清沢", "山田"], UWA2_RULES, UWA_CLOSURES),
    area(4, "宇和地区3", "宇和3：神領・久枝2～3区・野田・小野田・永長・田之筋・下宇和・明間ほか", "cutoff_0700", "uwa-3.pdf",
         ["神領", "久枝2～3区", "野田", "小野田", "永長", "れんげ", "上松葉", "下松葉", "松葉団地", "さくら", "田之筋", "下宇和", "明間"], UWA3_RULES, UWA_CLOSURES),
    area(5, "野村（月・木コース）", "野村：もやすごみ月・木コース（資源日は共通）", "cutoff_0700", "nomura.pdf",
         ["野村月木コース", "パドック野村前", "公園団地", "愛宕", "岩村", "石久保"], [rule(("burnable",), (1, 4)), *NOMURA_RESOURCES], NOMURA_CLOSURES),
    area(6, "野村（火・金コース）", "野村：もやすごみ火・金コース（資源日は共通）", "cutoff_0700", "nomura.pdf",
         ["野村火金コース", "西予市野村支所", "三島町", "伊勢井谷", "古市", "太田"], [rule(("burnable",), (2, 5)), *NOMURA_RESOURCES], NOMURA_CLOSURES),
    area(7, "野村（水・土コース）", "野村：もやすごみ水・土コース（資源日は共通）", "cutoff_0700", "nomura.pdf",
         ["野村水土コース", "緑ヶ丘", "権現", "中村", "峰", "次の川"], [rule(("burnable",), (3, 6)), *NOMURA_RESOURCES], NOMURA_CLOSURES),
    area(8, "中筋・蔵良・貝吹・横林", "野村：中筋・蔵良・貝吹・横林", "cutoff_0700", "nomura-nakasuji.pdf",
         ["中筋", "蔵良", "貝吹", "横林"], [rule(("burnable",), (3, 6)), *NAKASUJI_RESOURCES], NOMURA_CLOSURES),
    area(9, "渓筋・阿下・釜川", "野村：渓筋・阿下・釜川", "cutoff_0700", "nomura-tanisuji.pdf",
         ["渓筋", "阿下", "釜川"], [rule(("burnable",), (1, 4)), *NAKASUJI_RESOURCES], NOMURA_CLOSURES),
    area(10, "大成", "野村：大成", "cutoff_0700", "nomura-onaru.pdf", ["大成"],
         [rule(("burnable",), (3, 6)), *ONARU_RESOURCES], NOMURA_CLOSURES),
    area(11, "惣川", "野村：惣川", "cutoff_0700", "nomura-sogawa.pdf", ["惣川"],
         [rule(("burnable",), (2, 5)), rule(("landfill", "small_appliance", "metal"), (1,), (1, 3)),
          rule(("newspaper", "misc_paper", "milk_carton", "cardboard"), (3,), (1, 3)),
          rule(("clothes",), (4,), (1, 3)), *SOGAWA_COMMON], NOMURA_CLOSURES),
    area(12, "大野ヶ原", "野村：大野ヶ原", "cutoff_0700", "nomura-oonogahara.pdf", ["大野ヶ原"],
         OONOGAHARA_RULES, NOMURA_CLOSURES),
    area(13, "城川（魚成・遊子川）", "城川：魚成・遊子川", "cutoff_0700", "shirokawa.pdf", ["魚成", "遊子川"],
         [*SHIROKAWA_COMMON, rule(("landfill", "small_appliance", "metal"), (1,), (1,)),
          rule(("newspaper", "misc_paper", "milk_carton", "cardboard"), (3,), (1,)), rule(("clothes",), (4,), (1,))], NOMURA_CLOSURES),
    area(14, "城川（土居・高川）", "城川：土居・高川", "cutoff_0700", "shirokawa.pdf", ["土居", "高川"],
         [*SHIROKAWA_COMMON, rule(("landfill", "small_appliance", "metal"), (1,), (3,)),
          rule(("newspaper", "misc_paper", "milk_carton", "cardboard"), (3,), (3,)), rule(("clothes",), (4,), (3,))], NOMURA_CLOSURES),
    area(15, "三瓶町東地区", "三瓶町東地区", "cutoff_0800", "mikame-east.pdf", ["三瓶町東地区"], MIKAME_EAST, MIKAME_CLOSURES),
    area(16, "三瓶町南地区", "三瓶町南地区", "cutoff_0800", "mikame-south.pdf", ["三瓶町南地区"], MIKAME_SOUTH, MIKAME_CLOSURES),
    area(17, "三瓶町北地区", "三瓶町北地区", "cutoff_0800", "mikame-north.pdf", ["三瓶町北地区"], MIKAME_NORTH, MIKAME_CLOSURES),
]


EMPTY_NAMES = {
    (8, "left", 2, 19): "ござ", (9, "left", 1, 16): "雑誌", (9, "left", 2, 1): "シーツ",
    (11, "left", 2, 8): "スーツ", (13, "left", 2, 23): "畳", (14, "left", 2, 6): "机",
    (15, "right", 1, 13): "電卓", (16, "left", 2, 6): "ナット", (17, "left", 3, 5): "ノート",
    (17, "right", 2, 1): "ネジ", (19, "right", 2, 9): "服", (19, "right", 2, 13): "筆",
    (20, "left", 2, 7): "ベッド", (22, "right", 3, 1): "ミシン", (26, "right", 2, 4): "綿",
}
COLOR_CATEGORIES = {
    "#31AB41": "burnable", "#CE4523": "small_appliance", "#19693E": "metal",
    "#E487C9": "other_plastic", "#878485": "bulky", "#7F3125": "landfill",
    "#255D9B": "container_plastic", "#EE293A": "not_collected", "#A72498": "clothes",
    "#B2B1B1": "bottles", "#33B999": "hazardous", "#1E9DCB": "cans",
    "#99D64B": "used_oil", "#F58028": "pet",
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def checked_sources():
    metadata = read(DATA / "sources.json")
    pinned = {entry["file"]: entry for entry in metadata["sources"]}
    missing = sorted(set(SOURCES) - set(pinned))
    if missing:
        raise ValueError(f"Unpinned Seiyo source files: {missing}")
    for filename, expected in pinned.items():
        path = DATA / "source" / filename
        if not path.is_file():
            raise ValueError(f"Missing Seiyo source file: {path}")
        if digest(path) != expected["sha256"]:
            raise ValueError(f"Official Seiyo source changed: {filename}")
    return metadata


def fetch():
    pinned = {entry["file"]: entry for entry in read(DATA / "sources.json")["sources"]}
    for filename, url in SOURCES.items():
        parsed = urlparse(url)
        if parsed.hostname != HOST or Path(filename).name != filename:
            raise ValueError("Unexpected Seiyo source location")
        request = Request(url, headers={"User-Agent": "garbage-app-data-builder/1.0"})
        try:
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            context = ssl.create_default_context()
        body = urlopen(request, timeout=120, context=context).read()
        target = DATA / "source" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        if filename not in pinned or pinned[filename]["url"] != url or pinned[filename]["sha256"] != digest(target):
            raise ValueError(f"Official Seiyo source changed: {filename}")
    print(f"Saved and verified {len(SOURCES)} official Seiyo source files")


def clean_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").replace(" ", "")
    for old, new in {
        "なと": "など", "レコーター": "レコーダー", "サイス": "サイズ", "すすく": "すすぐ",
        "45kんサイズ": "45リットルサイズ", "45kサイズ": "45リットルサイズ",
        "45リサイズ": "45リットルサイズ", "45イサイズ": "45リットルサイズ",
        "ヒニール": "ビニール", "ホックス": "ボックス", "カートリッシ": "カートリッジ",
        "インクリホン": "インクリボン", "インバクト": "インパクト", "アタブター": "アダプター",
        "ウインドプレーカー": "ウインドブレーカー", "果物バック": "果物パック",
        "クリーニンク": "クリーニング", "ハンカー": "ハンガー", "クレシット": "クレジット",
        "コンクリートフロック": "コンクリートブロック", "コンタクトレンス": "コンタクトレンズ",
        "スパイクシュース": "スパイクシューズ", "スプリンクマットレス": "スプリングマットレス",
        "タイレクトメール": "ダイレクトメール", "ァープレコーダー": "テープレコーダー",
        "バーへキュー": "バーベキュー", "バケッ(": "バケツ(", "歯磨き粉のチュープ": "歯磨き粉のチューブ",
        "ハントクリーナー": "ハンドクリーナー", "ヒールびん": "ビールびん", "プロック(": "ブロック(",
        "べットの": "ペットの", "ホームペーカリー": "ホームベーカリー", "ホットカーベット": "ホットカーペット",
        "マッサーシ": "マッサージ", "マヨネース": "マヨネーズ", "レトルトバック": "レトルトパック",
        "飲料容器バック": "飲料容器パック", "卵バック": "卵パック", "いちこ・バック": "いちごパック",
        "いちこバック": "いちごパック", "牛乳バック": "牛乳パック", "酒バック": "酒パック",
        "紙バック": "紙パック", "豆腐バック": "豆腐パック", "電池バック": "電池パック",
        "包装バック": "包装パック", "歯ブラシの包装バック": "歯ブラシの包装パック",
        "500m床満": "500ml未満", "500m似上": "500ml以上", "500m2未満": "500ml未満",
        "500m2以上": "500ml以上", "販冗店": "販売店", "てきるたけ": "できるだけ",
        "ひもて": "ひもで", "個人肩報": "個人情報", "レンス": "レンズ", "カラス": "ガラス",
        "チュープ": "チューブ", "キーホード": "キーボード", "ホード": "ボード",
        "ストープ": "ストーブ", "カーベット": "カーペット", "カーホン": "カーボン",
        "シュニア": "ジュニア", "シュレッター": "シュレッダー", "水中メカネ": "水中メガネ",
        "スホンプレッサー": "ズボンプレッサー", "プルーシート": "ブルーシート",
        "しゅうたん": "じゅうたん", "ぬいくるみ": "ぬいぐるみ", "マーカリン": "マーガリン",
        "ポリバケッ": "ポリバケツ", "こみ箱": "ごみ箱", "コルクホード": "コルクボード",
        "キャリーバック": "キャリーバッグ", "べヒー": "ベビー", "べニヤ": "ベニヤ",
        "べットケーシ": "ペットケージ", "べットトイレ": "ペットトイレ",
        "ベットケーシ": "ペットケージ", "ベットトイレ": "ペットトイレ",
        "電子レンシ": "電子レンジ", "オープントースターレンシ": "オーブントースター・レンジ",
        "ガスレンシ": "ガスレンジ", "カスレンシ": "ガスレンジ", "カステープル": "ガステーブル",
        "カスコンロ": "ガスコンロ", "カス炊飯器": "ガス炊飯器", "カスホンべ": "ガスボンベ",
        "乳母車(ヘビーカー)": "乳母車（ベビーカー）", "テープカッター": "テープカッター",
        "ァープカッター": "テープカッター", "ァープルクロス": "テーブルクロス", "ァープル": "テーブル",
        "バイプ": "パイプ", "べヒーカー": "ベビーカー", "べヒーン一ト": "ベビーシート",
        "ポタン式": "ボタン式", "ホタン式": "ボタン式", "ルーベ": "ルーペ",
        "ミー一バイク": "ミニバイク", "飲料容器パック(中が銀色または500ml未満)": "飲料容器パック（中が銀色または500ml未満）",
        "飲料容器パック(中が白色で500ml以上)": "飲料容器パック（中が白色で500ml以上）",
        "販販売売店店ななどどにに相相談談": "販売店などに相談",
        "工ア": "エア", "ケーム": "ゲーム", "カス": "ガス", "ホンべ": "ボンベ",
        "ホトル": "ボトル", "べットボトル": "ペットボトル", "べットホトル": "ペットボトル",
        "ラへル": "ラベル", "サラタ": "サラダ", "サラタホウル": "サラダボウル",
        "カーナヒケーション": "カーナビゲーション", "シャム": "ジャム", "シュース": "ジュース",
        "シューサー": "ジューサー", "デシタル": "デジタル", "ヨークルト": "ヨーグルト",
        "チューフ": "チューブ", "紙製て": "紙製で", "すすいて": "すすいで",
        "布などて": "布などで", "布なとて": "布などで", "包んて": "包んで", "のみて": "のみで",
        "アイッシュべー/ヾー": "ティッシュペーパー", "ティッシュべーパ-": "ティッシュペーパー",
        "ティッシュべー": "ティッシュペー", "ペーパ-": "ペーパー", "ティー/ヾッグ": "ティーバッグ",
        "トランシー/ヾー": "トランシーバー", "シェー/ヾー": "シェーバー", "タッ/ヾー": "タッパー",
        "キーボード(ノヾソコン用)": "キーボード（パソコン用）", "コンノヾス": "コンパス",
        "クーノ、ン": "クーハン", "あせシート": "あぜシート", "かはん": "かばん",
        "卯バック": "卵パック", "つほ": "つぼ", "とんふり": "どんぶり",
        "電気力ーベット": "電気カーペット", "電気力ミソリ": "電気カミソリ",
        "タフレット": "タブレット", "ヒール": "ビール", "ひけそり": "ひげそり",
        "ヒデオ": "ビデオ", "儂業用)": "（農業用）", "IJSBメモリ": "USBメモリ",
        "レトルトバック": "レトルトパック", "45リトルッサイズ": "45リットルサイズ",
        "45サイズ": "45リットルサイズ", "454サイズ": "45リットルサイズ", "電45リットルサイズ": "45リットルサイズ",
        "サイズの袋ない": "サイズの袋に入らない", "活動を伴うもの「排出禁止」": "活動を伴うものは「排出禁止」",
        "取り扱いに/王,山、": "取り扱いに注意", "取り扱いに/王思": "取り扱いに注意",
        "取り扱いに/王思": "取り扱いに注意", "個人情報の取り扱注意": "個人情報の取り扱いに注意",
        "個人情報の取り扱いに/王思": "個人情報の取り扱いに注意",
        "できるだけ販売店き取つてもらう": "できるだけ販売店に引き取ってもらう",
        "中身を使いっ、っとすすぐ": "中身を使い切って、さっとすすぐ",
        "さっとすすぐ・、": "さっとすすぐ、", "さっとすすぐ\"": "さっとすすぐ",
        "食用油の容器(ひん)": "食用油の容器（びん）", "べットシーツ": "ペットシーツ",
        "ウオシュレット": "ウォシュレット", "洗えなかったら「燃\"": "洗えなかったら「燃」",
    }.items():
        value = value.replace(old, new)
    exact = {
        "ーHコンロ": "IHコンロ", "ーCレコーダー": "ICレコーダー",
        "-升びん": "一升びん", "ー升びん": "一升びん", "-升びんのふた": "一升びんのふた",
        "ー升びんのふた": "一升びんのふた", "-斗缶": "一斗缶", "ー斗缶": "一斗缶",
        "ー輪車(工ンシン付を除く)": "一輪車（エンジン付を除く）",
        "ー輪車(工ンジン付を除く)": "一輪車（エンジン付を除く）",
        "庫・冷蔵庫・冷凍庫": "冷温庫・冷蔵庫・冷凍庫", "た(プラスチック製)": "ふた（プラスチック製）",
        "コン/ヾネ(コンクリートバネル)": "コンパネ（コンクリートパネル）",
        "シート(レシャーン一ト・フルーシート)": "シート（レジャーシート・ブルーシート）",
        "ケームソフト()D・DVD)": "ゲームソフト（CD・DVD）",
        "メモリーカード()F・SDなど)": "メモリーカード（CF・SDなど）",
        "噴霧器(工ンジジンン式式))": "噴霧器（エンジン式）",
        "めがね(プラスチック製": "めがね（プラスチック製）",
        "/ヾッテリー池)": "バッテリー（充電式電池）",
        "(充ノヾッテリー用)": "バッテリー（バイク・車用）",
        "(/ヾック": "バッグ",
        "シューサー": "ジューサー", "シュース": "ジュース",
        "ホンべ(ガスボンへ)": "ボンベ（ガスボンベ）",
    }
    value = exact.get(value, value)
    if value.endswith("個人情報の取り扱いに"):
        value += "注意"
    exact_notes = {
        "個人情報の取り扱いに": "個人情報の取り扱いに注意",
        "45リットルサイズの袋に入": "45リットルサイズの袋に入らないものは「粗大」",
        "45リットルサイズの袋に入らないものは「粗": "45リットルサイズの袋に入らないものは「粗大」",
        "足ふみ式のものは「粗": "足踏み式のものは「粗大」",
        "さっとすすぐ\"、洗えなかったら「燃": "さっとすすぐ、洗えなかったら「燃」",
        "粗大」さっとすすぐ": "さっとすすぐ",
    }
    return exact_notes.get(value, value).strip('"')


def item_category(record, name):
    color = record["category_color"]
    if color in COLOR_CATEGORIES:
        return COLOR_CATEGORIES[color]
    if color != "#FAB81D":
        raise ValueError(f"Unknown Seiyo category color {color}: {name}")
    label = clean_text(record.get("category_text", ""))
    if "新聞" in label or "新聞" in name or name == "チラシ":
        return "newspaper"
    if "段" in label or "段ボール" in name:
        return "cardboard"
    if "紙バ" in label or "紙パック" in name or name.startswith("飲料容器パック"):
        return "milk_carton"
    return "misc_paper"


def category_options(note: str):
    mapping = {
        "粗大": "bulky", "金属": "metal", "他プ": "other_plastic", "燃": "burnable",
        "埋立": "landfill", "小家電": "small_appliance", "禁止": "not_collected",
        "古布": "clothes", "容プ": "container_plastic",
    }
    return sorted({code for label, code in mapping.items() if f"「{label}」" in note})


def item_definitions():
    path = DATA / "source/dictionary-extracted.json"
    if not path.is_file():
        raise ValueError("Run scripts/seiyo_dictionary_extract.py and place dictionary-extracted.json under data/regions/seiyo/source")
    records = read(path)
    if len(records) != 1293:
        raise ValueError(f"Expected 1,293 reviewed Seiyo dictionary rows, found {len(records)}")
    rows = []
    for number, record in enumerate(records, start=1):
        identity = (record["page"], record["side"], record["table"], record["row"])
        name = clean_text(EMPTY_NAMES.get(identity, record.get("name", "")))
        note = clean_text(record.get("note", ""))
        if not name:
            raise ValueError(f"Unreviewed empty Seiyo item name: {identity}")
        category = item_category(record, name)
        options = category_options(note)
        paper_pack_condition = (
            category in {"burnable", "milk_carton"}
            and ("パック" in name or "乳酸菌飲料の容器" in name)
            and any(marker in name for marker in ("銀色", "白色", "500ml"))
        )
        if paper_pack_condition:
            options = ["milk_carton"] if category == "burnable" else ["burnable"]
        rows.append({
            "item_id": f"seiyo-{number:04d}", "item": name,
            "category": category, "note": note,
            "category_options": options, "source_page": record["page"] + 24,
        })
    duplicates = [name for name, count in Counter(row["item"] for row in rows).items() if count > 1]
    if duplicates:
        for index, row in enumerate(rows, start=1):
            if row["item"] in duplicates:
                row["item_id"] = f"seiyo-{index:04d}"
    return rows


def item_rows():
    categories = read(DATA / "official_rules.json")["categories"]
    result = []
    for row in item_definitions():
        definition = categories[row["category"]]
        result.append({
            "item_id": row["item_id"], "item": row["item"], "category": row["category"],
            "category_display": definition["name"], "note": row["note"],
            "search_text": " ".join(filter(None, (row["item"], definition["name"], row["note"], definition.get("instructions", "")))),
            "disposal_instructions": definition.get("instructions", ""),
            "category_options": json.dumps(row["category_options"], ensure_ascii=False),
            "source_url": SOURCES["dictionary.pdf"], "source_category": definition["name"],
        })
    return result


def expand_rules(rules, closures):
    start, end = date.fromisoformat(VALID_FROM), date.fromisoformat(VALID_TO)
    days = {}
    current = start
    while current <= end:
        key = current.isoformat()
        if key in closures:
            current += timedelta(days=1)
            continue
        for entry in rules:
            if current.month not in entry["months"] or current.isoweekday() not in entry["weekdays"]:
                continue
            if entry["operational"]:
                occurrence = sum(
                    1 for day in range(1, current.day + 1)
                    if date(current.year, current.month, day).isoweekday() == current.isoweekday()
                    and date(current.year, current.month, day).isoformat() not in closures
                )
            else:
                occurrence = (current.day - 1) // 7 + 1
            if occurrence in entry["occurrences"]:
                days.setdefault(key, []).extend(entry["types"])
        current += timedelta(days=1)
    return {key: sorted(set(values)) for key, values in sorted(days.items())}


def calendar_payload():
    calendars = {}
    counts = {}
    for entry in AREAS:
        days = expand_rules(entry["rules"], entry["closures"])
        calendars[entry["calendar_id"]] = {
            "id": entry["calendar_id"], "name": entry["display_name"],
            "rule_profile_id": entry["rule_profile_id"],
            "source_url": SOURCES[entry["source_file"]],
            "verification_status": "checked",
            "days": days,
        }
        counts[entry["calendar_id"]] = {
            "dates": len(days), "events": sum(len(values) for values in days.values()),
            "sha256": value_digest(days),
        }
    review = {
        "schema_version": 1, "municipality_id": CITY, "version": VERSION,
        "valid_from": VALID_FROM, "valid_to": VALID_TO,
        "collection_areas": len(AREAS), "calendars": len(calendars), "calendar_counts": counts,
        "closures": {
            "akehama_uwa": sorted(UWA_CLOSURES), "mikame": sorted(MIKAME_CLOSURES),
            "nomura_shirokawa": sorted(NOMURA_CLOSURES),
        },
        "verification": {
            "method": "令和8年度の公式17表（地区カレンダー14表と、野村もやすごみ3コース、城川2資源グループ）を画像で照合し、曜日・第N週・月別区分・休業日を実日付へ展開した。",
            "limitations": "明浜・宇和PDF内の粗大ごみ小地区は、公式索引に住所との完全対応がないため定期通知へ追加しない。野村・城川の清掃センター受入日は公式掲載日のみ収録する。臨時変更は生成しない。",
            "reviewed_at": "2026-11-09",
        },
    }
    return calendars, review


def item_review():
    rows = item_definitions()
    return {
        "schema_version": 1, "municipality_id": CITY, "version": VERSION,
        "official_items": len(rows), "items_sha256": value_digest(rows),
        "categories": dict(sorted(Counter(row["category"] for row in rows).items())),
        "conditional_records": sum(bool(row["category_options"]) for row in rows),
        "source_files": ["dictionary.pdf", "guide-1.pdf", "guide-2.pdf", "guide-3.pdf"],
        "verification": {
            "method": "公式分別辞典27ページを300dpiで描画し、表の色区分と1,293行をOCR転記した。空欄15行は拡大画像で目視補完し、代表行を分別ガイドと照合した。",
            "limitations": "OCRは転記補助であり、材質・45リットル袋・汚れ等の条件が質問にない場合は追加確認する。未知品目を類推だけで確定しない。",
            "reviewed_at": "2026-11-09",
        },
    }


def bulky_config():
    return {
        "municipality_id": CITY, "municipality_name": "西予市",
        "collection_frequency": "地域別カレンダーまたは清掃センター受入（公式日程を確認）",
        "reception_hours": "宇和清掃センターは平日9:00～16:30。休日受入は公式カレンダーの確認済み日のみ。",
        "collection_rules": "45リットル袋に入らない物は粗大ごみです。地域別の小地区日程が確認できない場合は通知を生成しません。",
        "fee_structure_type": "fixed", "application_method": "guide_only",
        "phone_number": "0894-62-2219", "web_form_url": None, "information_url": CALENDAR_PAGE_URL,
        "steps": [
            {"step_number": 1, "title": "大きさと地域を確認", "description": "45リットル袋に入るかと、お住まいの地域・収集小地区を確認します。"},
            {"step_number": 2, "title": "公式カレンダーを確認", "description": "地域別の収集日、シール、持込先を公式PDFで確認します。"},
            {"step_number": 3, "title": "必要なシールを購入", "description": "シール対象地域では事前に指定販売先で購入します。"},
            {"step_number": 4, "title": "指定方法で排出・持込", "description": "公式に確認できた日時・場所だけを利用し、未確認日には出しません。"},
        ],
    }


def profile(profile_id, rules):
    cutoff = "07:00" if profile_id == "cutoff_0700" else "08:00"
    categories = {}
    for code, definition in rules["categories"].items():
        value = {key: val for key, val in definition.items() if key != "instructions"}
        if value.get("collection_type_id"):
            value["cutoff"] = cutoff
        categories[code] = value
    return {
        "items_path": "knowledge/items.csv", "embedding_index_path": "knowledge/item_embeddings.npz",
        "index_profile_id": "citywide", "calendar_path": "generated/calendar-2026.json",
        "classification_rules": rules["classification_rules"],
        "size_question": "材質、45リットル袋に入る大きさか、容器包装の識別表示、汚れを落とせるかを教えてください。",
        "knowledge_title": "西予市ごみ分類辞典", "categories": categories,
        "bulky_waste": {"category_code": "bulky", "config": bulky_config()},
    }


def build(*, inspect_only=False):
    checked_sources()
    calendars, review = calendar_payload()
    current_items = item_review()
    write(DATA / "generated/calendar-review-candidate.json", review)
    write(DATA / "generated/item-review-candidate.json", current_items)
    area_review = {"areas": [{key: value for key, value in row.items() if key not in {"rules", "closures"}} for row in AREAS]}
    write(DATA / "generated/areas-candidate.json", area_review)
    if inspect_only:
        print("Wrote Seiyo calendar, area and item review candidates")
        return
    if read(DATA / "calendar_reviews.json") != review:
        raise ValueError("Seiyo calendar rules differ from reviewed record")
    if read(DATA / "item_reviews.json") != current_items:
        raise ValueError("Seiyo item records differ from reviewed record")
    if read(DATA / "areas.json") != area_review:
        raise ValueError("Seiyo area mapping differs from reviewed record")
    rules = read(DATA / "official_rules.json")
    areas = [{
        "id": row["id"], "name": row["name"], "display_name": row["display_name"],
        "calendar_id": row["calendar_id"], "rule_profile_id": row["rule_profile_id"],
        "address_labels": row["address_labels"], "needs_local_confirmation": True,
        "source_url": SOURCES[row["source_file"]],
    } for row in AREAS]
    registry = {
        "schema_version": 1, "municipality_id": CITY, "municipality_name": "西予市",
        "prefecture_id": "38", "prefecture_name": "愛媛県", "version": VERSION,
        "valid_from": VALID_FROM, "valid_to": VALID_TO,
        "collection_areas": areas,
        "calendars": [{"id": row["calendar_id"], "rule_profile_id": row["rule_profile_id"]} for row in AREAS],
        "rule_profiles": {
            "cutoff_0700": profile("cutoff_0700", rules),
            "cutoff_0800": profile("cutoff_0800", rules),
        },
    }
    write(DATA / "registry.json", registry)
    write(DATA / "generated/calendar-2026.json", {
        "municipality_id": CITY, "version": VERSION, "valid_from": VALID_FROM,
        "valid_to": VALID_TO, "calendars": calendars,
    })
    entries = []
    for row in areas:
        entries.extend({"town": label, "lookup_town": label, "area_id": row["id"]} for label in row["address_labels"])
    write(DATA / "generated/addresses.json", {"municipality_id": CITY, "version": VERSION, "entries": entries})
    rows = item_rows()
    target = DATA / "knowledge/items.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    write(DATA / "generated/item-review.json", {
        "item_count": len(rows), "csv_sha256": digest(target),
        "categories": dict(sorted(Counter(row["category"] for row in rows).items())),
    })
    print(f"Built {len(areas)} Seiyo areas, {len(calendars)} calendars and {len(rows)} item records")


def verify(*, without_index=False):
    checked_sources()
    calendars, review = calendar_payload()
    if read(DATA / "calendar_reviews.json") != review or read(DATA / "item_reviews.json") != item_review():
        raise ValueError("Seiyo reviewed metadata changed")
    registry = read(DATA / "registry.json")
    bundle = read(DATA / "generated/calendar-2026.json")
    if bundle["calendars"] != calendars or len(registry["collection_areas"]) != len(AREAS):
        raise ValueError("Seiyo generated registry/calendar changed")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError("Seiyo item CSV changed")
    index = DATA / "knowledge/item_embeddings.npz"
    manifest = DATA / "knowledge/index_manifest.json"
    if not without_index:
        if not index.is_file() or not manifest.is_file():
            raise ValueError("Seiyo embedding index is missing")
        metadata = read(manifest)
        if (metadata["municipality_id"] != CITY or metadata["profile_id"] != "citywide"
                or metadata["item_count"] != len(rows) or metadata["source_sha256"] != digest(DATA / "knowledge/items.csv")
                or metadata["index_sha256"] != digest(index)):
            raise ValueError("Seiyo CSV/index/manifest mismatch")
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
    if args.command == "fetch": fetch()
    elif args.command == "inspect": build(inspect_only=True)
    elif args.command == "build": build()
    else: verify(without_index=args.without_index)
