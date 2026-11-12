#!/usr/bin/env python3
"""
choumei.csv と municipality_registry.json から
municipality_addresses.json を生成するスクリプト。

CSVの地区番号（1〜84）を registry の collection_areas の ID にマッピングする。
番号形式のIDは "38201-{番号:02d}" で対応。
ca- 形式のIDは地区名での文字列マッチングで対応。
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "frontend/assets/choumei.csv"
REGISTRY_PATH = ROOT / "frontend/assets/data/municipality_registry.json"
OUTPUT_PATH = ROOT / "frontend/assets/data/municipality_addresses.json"

MUNICIPALITY_ID = "38201"

# CSVの地区番号 → registry の area_id への手動マッピング。
# 番号形式（38201-01 等）は自動解決するが、
# ca- 形式や複数マッピングが必要なものはここで明示する。
#
# 値がリストの場合、その町名はすべての area_id に登録される（複数候補）。
MANUAL_NUMBER_MAP: dict[str, list[str]] = {
    # 番号10「道後」→ 道後(ca-dogo) と 湯築(ca-yuzuki) の2エリアに分かれている
    # GPSで取れる「道後湯之町」等の町名は両方の候補として提示する
    "10": ["38201-ca-dogo", "38201-ca-yuzuki"],
    # 番号31「石井」→ 石井東(ca-ishii-east) と 石井西(ca-ishii-west) に分かれているが
    # CSVには東西の区別がないため両候補として登録し、ユーザーに選択させる
    "31": ["38201-ca-ishii-west", "38201-ca-ishii-east"],
    # 番号32「荏原」→ registryに対応IDなし（久谷地区に統合済みの可能性）
    # 久谷(ca-kutani)に紐づける
    "32": ["38201-ca-kutani"],
    # 番号33「坂本」→ 久谷地区に含まれる
    "33": ["38201-ca-kutani"],
    # 番号81「睦野」→ 睦月(ca-mutsuki) と 野忽那(ca-nogutsuna) に分かれている
    "81": ["38201-ca-mutsuki", "38201-ca-nogutsuna"],
    # 番号82「東中島」→ 中島大浦(ca-nk-oura)、小浜(ca-obama)、長師(ca-nagashi)、
    #                   宮野(ca-miyano)、神浦(ca-konoura) に分かれている
    "82": ["38201-ca-nk-oura", "38201-ca-obama", "38201-ca-nagashi",
           "38201-ca-miyano", "38201-ca-konoura"],
    # 番号83「西中島」→ 宇和間(ca-uwama)、熊田(ca-kumata)、吉木(ca-yoshiki)、
    #                   饒(ca-nyo)、畑里(ca-hatari)、中島粟井(ca-nk-awai) に分かれている
    "83": ["38201-ca-uwama", "38201-ca-kumata", "38201-ca-yoshiki",
           "38201-ca-nyo", "38201-ca-hatari", "38201-ca-nk-awai"],
    # 番号84「神和」→ 上怒和(ca-kami-nuwa)、元怒和(ca-moto-nuwa)、
    #                 津和地(ca-tsuwaji)、二神(ca-futagami) に分かれている
    "84": ["38201-ca-kami-nuwa", "38201-ca-moto-nuwa",
           "38201-ca-tsuwaji", "38201-ca-futagami"],
}


def load_registry():
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_csv():
    rows = []
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # ヘッダー行をスキップ
        for row in reader:
            if len(row) < 4:
                continue
            district_number = row[0].strip()
            district_name = row[1].strip()
            town_name = row[3].strip()
            rows.append({
                "district_number": district_number,
                "district_name": district_name,
                "town_name": town_name,
            })
    return rows


def build_number_map(registry):
    """registry の番号形式 ID（38201-01 等）から district_number → area_id を構築する。"""
    number_map = {}
    for area in registry["collection_areas"]:
        suffix = area["id"].replace(f"{MUNICIPALITY_ID}-", "")
        if suffix.isdigit():
            number_map[int(suffix)] = area["id"]
    return number_map


def find_area_ids(district_number_str: str, number_map: dict) -> list[str]:
    """
    CSVの地区番号から area_id のリストを返す。
    手動マッピングが優先。なければ番号形式マップを参照。
    """
    # 手動マッピング優先
    if district_number_str in MANUAL_NUMBER_MAP:
        return MANUAL_NUMBER_MAP[district_number_str]

    # 番号形式（自動）
    try:
        num = int(district_number_str)
        if num in number_map:
            return [number_map[num]]
    except ValueError:
        pass

    return []


def main():
    registry = load_registry()
    csv_rows = load_csv()
    number_map = build_number_map(registry)

    entries = []
    unmatched = []

    for row in csv_rows:
        area_ids = find_area_ids(row["district_number"], number_map)
        if not area_ids:
            unmatched.append(row)
            continue

        town = row["town_name"]
        for area_id in area_ids:
            entries.append({
                "town": town,
                "lookup_town": town,
                "area_id": area_id,
            })

    result = {
        "municipality_id": MUNICIPALITY_ID,
        "version": registry["version"],
        "entries": entries,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"生成完了: {len(entries)} 件のエントリ → {OUTPUT_PATH}")

    if unmatched:
        print(f"\n警告: マッチしなかった行 {len(unmatched)} 件:")
        for row in unmatched:
            print(f"  地区番号={row['district_number']}, 地区名={row['district_name']}, 町名={row['town_name']}")
    else:
        print("すべての行がマッチしました。")

    # 確認: registryの全地区がentriesにあるか
    all_area_ids = {area["id"] for area in registry["collection_areas"]}
    covered = {e["area_id"] for e in entries}
    missing = all_area_ids - covered
    if missing:
        print(f"\n注意: addresses.jsonに含まれていないエリアID ({len(missing)} 件):")
        for m in sorted(missing):
            area_name = next((a["name"] for a in registry["collection_areas"] if a["id"] == m), "?")
            print(f"  {m} ({area_name})")
    else:
        print("すべてのエリアIDがカバーされています。")


if __name__ == "__main__":
    main()
