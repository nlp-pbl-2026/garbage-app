#!/usr/bin/env python3
"""Reproduce reviewed Shikokuchuo City data from pinned official guides.

The free workflow is fetch -> inspect -> build -> verify.  It never invokes
Bedrock, deploys to AWS, or guesses weather-related collection changes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import ssl
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/shikokuchuo"
CITY = "38213"
VERSION = "shikokuchuo-2026.1"
VALID_FROM = "2026-04-01"
VALID_TO = "2027-03-31"
HOST = "www.city.shikokuchuo.ehime.jp"
PAGE_URL = f"https://{HOST}/soshiki/15/1924.html"
COPYRIGHT_URL = f"https://{HOST}/site/userguide/12028.html"
HOLIDAY_URL = f"https://{HOST}/soshiki/15/51919.html"
PDF_URLS = {
    "districts": f"https://{HOST}/uploaded/attachment/3293.pdf",
    "burnable": f"https://{HOST}/uploaded/attachment/3294.pdf",
    "nonburnable": f"https://{HOST}/uploaded/attachment/3295.pdf",
    "resources": f"https://{HOST}/uploaded/attachment/3296.pdf",
    "bulky-fees": f"https://{HOST}/uploaded/attachment/3297.pdf",
    "bulky-guide": f"https://{HOST}/uploaded/attachment/3298.pdf",
    "appliances": f"https://{HOST}/uploaded/attachment/26620.pdf",
    "waste-standards": f"https://{HOST}/uploaded/attachment/3303.pdf",
    "lithium": f"https://{HOST}/uploaded/attachment/21712.pdf",
}
SOURCES = {
    "guide-page.html": PAGE_URL,
    "copyright.html": COPYRIGHT_URL,
    "holiday-page.html": HOLIDAY_URL,
    **{f"{slug}.pdf": url for slug, url in PDF_URLS.items()},
}

COLLECTION_TYPES = (
    "burnable", "nonburnable", "hazardous", "bottles_cans_pet",
    "newspaper", "magazines", "misc_paper", "cardboard_milk",
)
CLOSURES = {
    "2026-05-02", "2026-08-15", "2026-10-14", "2026-10-15",
    "2026-10-22", "2026-10-23", "2026-12-31", "2027-01-01",
    "2027-01-02",
}
MISHIMA_FESTIVAL_COLLECTION = {"2026-10-14", "2026-10-15"}


def rule(types, weekdays, occurrences=(1, 2, 3, 4, 5), months=range(1, 13)):
    return {
        "types": list(types), "weekdays": list(weekdays),
        "occurrences": list(occurrences), "months": list(months),
    }


def standard_rules(burnable, nonburnable, bottles, newspaper, magazines, cardboard):
    return [
        rule(("burnable",), burnable),
        rule(("nonburnable",), (nonburnable,)),
        rule(("hazardous",), (nonburnable,), (1,)),
        rule(("bottles_cans_pet",), (bottles,)),
        rule(("newspaper", "misc_paper"), (newspaper,), (1, 3)),
        rule(("magazines", "misc_paper"), (magazines,), (2, 4)),
        rule(("cardboard_milk",), (cardboard,), (1,)),
    ]


def merged_paper_rules(burnable, nonburnable, bottles, paper_weekday):
    return [
        rule(("burnable",), burnable),
        rule(("nonburnable",), (nonburnable,)),
        rule(("hazardous",), (nonburnable,), (1,)),
        rule(("bottles_cans_pet",), (bottles,)),
        rule(("newspaper", "magazines", "misc_paper", "cardboard_milk"),
             (paper_weekday,), (1, 3)),
    ]


K1 = standard_rules((1, 4), 4, 1, 3, 3, 6)
K2 = standard_rules((2, 5), 5, 2, 1, 1, 4)
K3 = merged_paper_rules((2, 5), 5, 2, 4)
K4 = standard_rules((3, 6), 6, 3, 2, 2, 5)
K5 = merged_paper_rules((3, 6), 6, 3, 4)
M1 = standard_rules((1, 4), 2, 5, 3, 3, 6)
M2 = standard_rules((2, 5), 3, 6, 1, 1, 4)
M3 = standard_rules((3, 6), 1, 4, 2, 2, 5)
D1 = K1
D2 = K2
D3 = K4


def area(number, name, display_name, profile, labels, rules, cutoff="07:30"):
    if profile == "citywide":
        profile = "early_0700" if cutoff == "07:00" else "standard_0730"
    elif profile == "mishima":
        profile = "mishima_0730"
    return {
        "id": f"{CITY}-{number:02d}", "name": name,
        "display_name": display_name, "calendar_id": f"shikokuchuo-{number:02d}",
        "rule_profile_id": profile, "address_labels": labels,
        "rules": rules, "cutoff": cutoff,
    }


AREAS = [
    area(1, "川之江1（7時30分）", "川之江1：井地・西新町・東大門・大門・西大門・馬場ほか",
         "citywide", ["井地", "西新町", "東大門", "大門", "西大門", "馬場（3区の一部・4区）", "川関", "通町", "小山", "平木", "新浜", "浜田", "綿市（JR線路より北）", "城下", "南ヶ丘", "本町", "中新町", "中本町", "新町", "祇園町", "電明町", "北新町", "花園町", "高木", "西川原"], K1),
    area(2, "川之江1（7時）", "川之江1・朝7時：天生津・宝洞山・石ノ口・切山",
         "citywide", ["天生津", "宝洞山", "石ノ口", "切山"], K1, "07:00"),
    area(3, "川之江2（7時30分）", "川之江2：山下・旭町・栄町・山口・川東・金田町ほか",
         "citywide", ["山下", "旭町", "新町", "栄橋通り", "栄町上通り", "栄町", "駅通り", "馬場（1区・2区・3区の一部）", "丸住アパート", "大道", "住吉", "春日", "川原田", "山口", "川東", "土居", "中上", "中下", "松木", "綿市（JR線路より南）", "中之町", "西金川下", "国秀", "八戸", "東金川", "涼川", "大久保", "上庄", "正地"], K2),
    area(4, "川之江2（7時）", "川之江2・朝7時：三角寺・朝日・城塚・平山・横川",
         "citywide", ["三角寺", "朝日", "城塚", "平山", "横川"], K2, "07:00"),
    area(5, "川滝（7時30分）", "川滝：寒之池・田尾・中通・合路・西之尾",
         "citywide", ["寒之池", "田尾", "中通", "合路", "西之尾"], K3),
    area(6, "川滝（7時）", "川滝・朝7時：七田・久保之内・葱尾・中組・三名ほか",
         "citywide", ["七田", "久保之内", "葱尾", "中組", "三名", "椿堂", "石川", "原中", "古下田", "泉中尾"], K3, "07:00"),
    area(7, "川之江3（7時30分）", "川之江3：鉄砲町・古町・川原町・城北・金田町ほか",
         "citywide", ["鉄砲町", "古町", "川原町", "城北", "中須", "西ノ浜", "東浜", "浦町", "港通り", "農人町", "塩谷", "宮の谷", "東町", "長須", "余木", "川原田東", "川岸", "丸山", "大下", "坂ノ口", "平木", "通谷", "山田井中組", "山田井上組", "城ヶ谷団地", "涼川住宅", "井ノ上", "長途路", "西之坊", "本村", "飼谷", "飼谷団地", "池ノ奥", "南部団地", "走り出", "金沢"], K4),
    area(8, "川之江3（7時）", "川之江3・朝7時：川原田住宅",
         "citywide", ["川原田住宅"], K4, "07:00"),
    area(9, "柴生・下川（7時）", "柴生・下川・朝7時：北柴生・南柴生・長持・中下ほか",
         "citywide", ["北柴生", "南柴生", "長持", "中下", "竹花", "牛飼野", "射場", "竹本", "棒賀"], K5, "07:00"),
    area(10, "三島1", "三島1：村松町・三島朝日1～2丁目・紙屋町・寒川町東部ほか",
         "mishima", ["上柏町の一部", "下柏町の一部", "村松町", "三島朝日1丁目", "三島朝日2丁目", "三島紙屋町", "中曽根町（中田井・幸町を除く）", "三島中央1丁目", "三島中央2丁目", "三島中央4丁目（国道11号線沿い）", "三島金子1丁目（国道11号線沿い）", "具定町", "寒川町東部", "寒川町中部"], M1),
    area(11, "三島2", "三島2：三島朝日3丁目・三島宮川・中田井・幸町ほか",
         "mishima", ["上柏町の一部", "下柏町の一部", "三島朝日3丁目", "大塚住宅付近", "三島宮川1丁目", "三島宮川2丁目", "三島宮川3丁目", "三島宮川4丁目", "三島中央3丁目", "三島中央4丁目（駅前通り）", "三島中央5丁目（三島口）", "中曽根町（中田井・幸町）", "具定町の一部", "中之庄町公園通り1丁目", "中之庄町公園通り2丁目", "中之庄町公園通り3丁目", "寒川町北部の一部を除く区域", "寒川町西部の一部を除く区域"], M2),
    area(12, "三島3", "三島3：上柏・下柏・三島金子・中之庄・豊岡町ほか",
         "mishima", ["上柏町（一部を除く）", "下柏町（一部を除く）", "三島中央4丁目（駅前通り・国道11号線沿いを除く）", "三島中央5丁目（三島口を除く）", "中央本通り", "三島金子1丁目（国道11号線沿いを除く）", "三島金子2丁目", "三島金子3丁目", "中之庄町（公園通りを除く）", "寒川町北部の一部", "寒川町西部の一部", "豊岡町"], M3),
    area(13, "金砂町", "金砂町全域", "mishima", ["金砂町"], [
        rule(("burnable",), (2,)), rule(("nonburnable", "hazardous"), (2,), (2,)),
        rule(("bottles_cans_pet",), (2,), (4,)),
        rule(("newspaper", "magazines", "misc_paper", "cardboard_milk"), (4,), (1, 3)),
    ]),
    area(14, "富郷町", "富郷町全域", "mishima", ["富郷町"], [
        rule(("burnable",), (5,)), rule(("nonburnable", "hazardous"), (5,), (1,)),
        rule(("bottles_cans_pet",), (5,), (3,)),
        rule(("newspaper", "magazines", "misc_paper", "cardboard_milk"), (4,), (2, 4)),
    ]),
    area(15, "土居1", "土居1：上野・北野・畑野・浦山・土居（JR線路より北）",
         "citywide", ["上野", "北野", "畑野", "浦山", "土居（JR線路より北）"], D1),
    area(16, "土居2", "土居2：入野・中村・小林・藤原・土居南・津根北・野田北",
         "citywide", ["入野", "中村", "小林", "藤原", "土居（JR線路より南）", "津根（JR線路より北）", "野田（JR線路より北）"], D2),
    area(17, "土居3", "土居3：天満・蕪崎・津根南・野田南",
         "citywide", ["天満", "蕪崎", "津根（JR線路より南）", "野田（JR線路より南）"], D3),
    area(18, "新宮1", "新宮1：中山全域・秋田・程野・辺地床・下り付の一部",
         "citywide", ["中山全域", "秋田", "程野", "辺地床", "下り付（一部）"], [
        rule(("burnable",), (4,)), rule(("nonburnable", "hazardous"), (6,), (2,)),
        rule(("bottles_cans_pet",), (2,), (2, 4)),
        rule(("newspaper", "magazines", "misc_paper", "cardboard_milk"), (4,), (2, 4)),
    ]),
    area(19, "新宮2", "新宮2：上山全域・黒田・西ヶ市・竹の峰・寺尾・大谷・小六",
         "citywide", ["上山全域", "黒田", "西ヶ市", "竹の峰", "寺尾", "大谷", "小六"], [
        rule(("burnable",), (3,)), rule(("nonburnable", "hazardous"), (6,), (2,)),
        rule(("bottles_cans_pet",), (2,), (2, 4)),
        rule(("newspaper", "magazines", "misc_paper", "cardboard_milk"), (4,), (2, 4)),
    ]),
    area(20, "新宮3", "新宮3：新宮1・2以外（新宮・新瀬川・馬立など）",
         "citywide", ["新宮", "新瀬川", "馬立", "新宮1・2以外"], [
        rule(("burnable",), (1, 5)), rule(("nonburnable", "hazardous"), (6,), (1,)),
        rule(("bottles_cans_pet",), (2,), (1, 3)),
        rule(("newspaper", "magazines", "misc_paper", "cardboard_milk"), (4,), (1, 3)),
    ]),
]


ITEM_GROUPS = [
    ("burnable", "可燃", [
        "雨具（カッパ）", "アルミホイル（食品用）", "衣類（着られないもの）", "植木の皮・葉類",
        "落ち葉", "おむつ・紙おむつ", "貝殻", "額縁（木製・50cm以下）", "かつら類", "カーテン",
        "かばん", "革ジャンパー", "木くず", "草花", "串（竹製）", "くし（髪櫛）", "クッション",
        "クレヨン・クレパス", "グローブ", "ござ（1m未満）", "コップ（紙製）", "ゴムホース",
        "ゴムマット（1m未満）", "鯉のぼり", "ざる類（非金属）", "座布団", "生理用品",
        "石油ポンプ（手動式）", "台所ごみ", "茶がら", "使い捨てカイロ", "漬物桶（木製・一斗缶以下）",
        "積木", "天ぷら油", "デスクマット（1m未満）", "長靴", "生ごみ類", "人形類",
        "ぬいぐるみ類（一斗缶以下）", "布類", "バッグ類", "発泡スチロール", "ハンガー（木製）",
        "歯磨きチューブ", "ビニールシート（家庭用・1m以内）", "ビニールテーブルクロス（1m以内）",
        "ビデオテープ", "ファスナー（プラスチック製）", "風呂マット", "フィルム（ネガ）",
        "ヘアブラシ", "ベルト（ズボン用・金属除去済み）", "ほうき（50cm以内）", "帽子",
        "ホース（ビニール・50cm以内）", "ポール（スポーツ用品）", "保冷剤", "まくら",
        "まな板（木製）", "水まくら", "木片（建設廃材を除く）", "モップ（柄なし）", "ロープ類（50cm以内）",
    ]),
    ("nonburnable", "不燃", [
        "アイロン", "アルミホイル（食品用以外）", "移植ごて", "板ガラス", "鋳物なべ", "植木鉢（陶磁器類）",
        "植木鉢（プラスチック製）", "植木用支柱（プラスチック製・50cm以下）", "枝切りばさみ（50cm未満）",
        "延長コード", "絵の具のチューブ", "鉛筆削り器", "エアゾール缶", "王冠", "おもちゃ類（一斗缶以下）",
        "オーブントースター（一斗缶以下）", "折り畳み式椅子（小型）", "懐中電灯", "傘", "カセットコンロ",
        "カセットボンベ（卓上）", "ガスライター", "かみそり", "かみそり（充電式）", "カメラ",
        "ガラスコップ", "換気扇（一斗缶以下）", "急須", "救急箱（プラスチック）", "草刈り鎌",
        "串（金属製）", "くし（金属製）", "クリスタルガラス", "クーラーボックス（一斗缶以下）",
        "計量秤（一斗缶以下）", "化粧品びん", "玄関マット（金属使用）", "ゲーム機", "ゲームソフト",
        "コップ", "収納ケース（一斗缶以下）", "ジューサー", "ミキサー", "照明器具（一斗缶以下）",
        "CDラジカセ（一斗缶以下）", "水槽（一斗缶以下）", "水筒", "炊飯器（一斗缶以下）", "スコップ（移植ごて）",
        "スプーン", "スプレー缶", "石油ポンプ（電池式）", "洗面器（プラスチック）", "耐熱ガラス",
        "タッパー（台所用品・プラスチック製）", "樽（一斗缶以下）", "茶器（陶磁器・金属）",
        "漬物桶（プラスチック・一斗缶以下）", "電気アンカ", "電気炊飯器（一斗缶以下）", "電話機",
        "鉄板（厚さ2mm未満）", "陶磁器製品", "トースター", "時計", "土鍋", "ドライヤー", "鍋類",
        "のこぎり類", "はかり（一斗缶以下）", "バケツ（一斗缶以下）", "はさみ類", "柱時計（小型）",
        "針金（50cm以内）", "ハンガー（金属・プラスチック製）", "針（裁縫用）", "ビデオカメラ", "ファスナー（金属製）",
        "フォーク（台所用）", "筆箱", "フライパン", "フロッピーディスク", "ヘルスメーター", "ヘルメット",
        "包丁", "ポット", "ホーロー鍋", "ホース用リール（一斗缶以下）", "ボウル（台所用品）", "哺乳びん",
        "本棚（一斗缶以下）", "まくら（磁気）", "窓ガラス", "まな板（プラスチック）", "魔法瓶",
        "水さし", "蒸し器", "無線機（携帯用）", "メガネ", "やかん", "湯たんぽ",
        "ラジオ（一斗缶以下）", "ラジカセ（一斗缶以下）", "ランチジャー", "レコード盤", "ローラースケート",
    ]),
    ("bottles_cans_pet", "資源", [
        "あき缶・あきびん（飲料・飲食用）", "油びん・缶（食用）", "一升びん", "菓子缶", "かんづめ缶",
        "ジュース缶・びん", "酒びん", "清涼飲料水びん", "茶筒", "調味料の空容器", "ドリンクびん",
        "のりびん・缶（食料用）", "ペットボトル", "ミルク缶・びん", "洋酒びん", "ワンカップびん",
    ]),
    ("newspaper", "資源", ["新聞", "新聞紙", "折り込みチラシ"]),
    ("magazines", "資源", ["雑誌", "雑誌類", "本", "カタログ"]),
    ("misc_paper", "資源", [
        "雑がみ", "菓子箱", "ティッシュ箱", "たばこの箱", "カレンダー", "ポスター", "包装紙", "紙袋",
        "封筒", "はがき", "ダイレクトメール", "トイレットペーパーの芯", "牛乳パック（500ml以下）",
    ]),
    ("cardboard_milk", "資源", ["段ボール類", "牛乳パック（1000ml）"]),
    ("recycling_station", "資源（拠点回収）", ["衣類（着られるもの）", "トレー"]),
    ("hazardous", "有害", [
        "乾電池類", "蛍光管", "電球", "鏡（姿見を除く）", "リチウムイオン電池", "スマートフォン",
        "電子タバコ", "モバイルバッテリー", "リチウムイオン電池を外せない小型家電",
    ]),
    ("bulky", "粗大", [
        "アコーディオンカーテン", "編み機", "網戸", "雨戸", "アルミサッシ", "アンプ・チューナー",
        "アンテナ（テレビ用）", "あんま機", "衣装ケース・衣類箱", "椅子", "犬小屋", "一輪車", "一斗缶",
        "植木用支柱（木製）", "羽毛ふとん", "乳母車", "うわじき", "エレクトーン", "応接セット", "桶（木製）",
        "オーブンレンジ", "折り畳み式椅子", "オルガン", "額縁（木製・50cm超）", "加湿機", "カセットデッキ",
        "ガスレンジ・ガスコンロ", "ガス湯沸かし器", "カーペット", "カラーボックス", "カラオケセット",
        "脚立・はしご", "ギター", "鏡台", "草刈り機", "空気清浄器", "くわ", "下駄箱", "健康器具（家庭用）",
        "ござ", "こたつ", "琴", "ゴルフクラブ", "ゴルフバッグ", "座椅子", "座卓", "サーフボード", "サイドボード",
        "三輪車（子供用）", "芝刈り機", "食器洗い機", "食器乾燥機", "食器棚", "食卓・テーブル", "自転車",
        "じゅうたん", "障子戸", "照明器具", "CDラジカセ", "除湿器", "水槽", "炊飯器", "スーツケース",
        "姿見", "スキー板", "スコップ", "すだれ", "ステレオ", "ステレオラック", "スピーカー",
        "ストーブ（石油・ガス・電気）", "すのこ", "すべり台", "スプリングベッド", "ズボンプレッサー",
        "石油ストーブ", "扇風機", "洗濯竿", "洗濯物干し台", "洗面台・化粧台", "掃除機", "ソファー", "畳",
        "卓球台", "建具類", "たてす", "樽", "ダブルベッド", "タンス類", "調理台", "チューナー・アンプ類",
        "チャイルドシート", "漬物桶（木製）", "釣り竿", "テーブル", "電気カーペット", "電気炊飯器", "電気毛布",
        "電気マッサージ機", "電子レンジ", "電子ピアノ", "テレビ台", "テント（家庭用）", "ドア", "トタン板",
        "流し台", "パイプ椅子", "パイプベッド", "はかり", "はしご・脚立", "柱時計", "バット", "ビデオデッキ",
        "ファンヒーター", "ふすま", "ふとん", "ふとん乾燥機", "ブラインド", "ぶらさがり健康器", "ブランコ（子ども用）",
        "プランター", "プレイヤー", "風呂ふた（プラスチック製）", "噴霧器（家庭用）", "ベッド", "ボート（ゴム）",
        "マットレス", "ミシン", "ミシン台", "毛布", "もちつき器", "モップ（柄付き）", "物干し竿", "物干し台",
        "遊具", "湯沸器（台所用）", "洋服ダンス", "旅行用大型バッグ", "ルームランナー", "レンジ台", "ロッカー",
        "ワープロ", "ワゴン", "和ダンス",
    ]),
    ("appliance_recycling", "家電リサイクル", ["エアコン", "テレビ", "冷蔵庫", "冷凍庫", "洗濯機", "衣類乾燥機"]),
    ("not_collected", "市で処理できない", [
        "あぜシート", "医療器具・用品等", "オートバイ", "LPガスボンベ", "金庫", "自動車", "自動車部品",
        "消火器", "スクーター", "太陽熱温水器", "タイヤ類", "蓄電池", "電気温水器", "鉄塊", "鉄管", "鉄棒",
        "塗料・溶剤", "農機具類", "農業用資材", "農業用ビニールシート", "バッテリー類", "針（医療用）",
        "廃油・オイル", "番線くず", "ピアノ", "肥料などのビニール袋", "風呂用ボイラー", "風呂がま",
        "ボール（ボーリング用）", "ボイラー類", "ミニバイク", "溶剤・塗料容器", "漁具", "ワイヤーロープ",
    ]),
]

SPECIAL = {
    "エアゾール缶": ("中身を使い切り、屋外で穴を開けてつぶして出します。", []),
    "スプレー缶": ("中身を使い切り、屋外で穴を開けてつぶして出します。", []),
    "カセットボンベ（卓上）": ("中身を使い切り、屋外で穴を開けてつぶして出します。", []),
    "板ガラス": ("紙に包み、透明の袋に入れ「危険」と書いて出します。", []),
    "窓ガラス": ("透明の袋に入れ「危険」と書いて出します。", []),
    "乾電池類": ("透明の袋に入れて出します。", []),
    "鏡（姿見を除く）": ("透明の袋に入れ「危険」と書いて出します。姿見は粗大ごみです。", ["bulky"]),
    "リチウムイオン電池": ("製品から外して有害ごみへ出します。", []),
    "スマートフォン": ("電池を取り外せない製品は、そのまま有害ごみへ出します。", []),
    "電子タバコ": ("電池を取り外せない製品は、そのまま有害ごみへ出します。", []),
    "モバイルバッテリー": ("そのまま有害ごみへ出します。", []),
    "衣類（着られるもの）": ("市の紙ングハウス等の拠点回収へ出します。", []),
    "トレー": ("店頭回収に協力してください。", []),
    "ペットボトル": ("PETマーク付きの飲料・酒類・しょうゆ用に限り、ふたを外して水洗いし、ペットボトルだけの袋で出します。", []),
    "雑がみ": ("種類別にひもで縛るか、小さいものは封筒・紙袋に入れます。汚れ・臭い・金銀・ビニール加工紙は燃やすごみです。", ["burnable"]),
    "菓子箱": ("きれいな紙箱は雑がみです。食品の油汚れや臭いが取れない場合は燃やすごみです。", ["burnable"]),
    "牛乳パック（1000ml）": ("水洗いして切り開き、乾かして縛ります。500ml以下は雑がみです。", ["misc_paper"]),
    "枝類": ("太さ5cm以下、長さ50cm以下にして縛るか袋に入れます。", ["bulky"]),
    "おもちゃ類（一斗缶以下）": ("ぬいぐるみは燃やすごみ、一斗缶より大きいものは粗大ごみです。", ["burnable", "bulky"]),
    "まな板（プラスチック）": ("木製は燃やすごみです。", ["burnable"]),
    "モップ（柄なし）": ("柄付きは粗大ごみです。", ["bulky"]),
    "湯沸器（台所用）": ("電池を取り除きます。電池は有害ごみです。", ["hazardous"]),
}


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
            raise ValueError("Unexpected Shikokuchuo source location")
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
            raise ValueError(f"Official Shikokuchuo source changed: {filename}")
        records.append({"file": filename, "url": url, "sha256": actual,
                        "retrieved_at": datetime.now(timezone.utc).isoformat()})
    write(DATA / "source/downloads.json", sorted(records, key=lambda row: row["file"]))
    print(f"Saved and verified {len(records)} official Shikokuchuo source files")


def checked_sources():
    reviewed = read(DATA / "sources.json")
    if reviewed["municipality_id"] != CITY or reviewed["version"] != VERSION:
        raise ValueError("Shikokuchuo source review identity mismatch")
    for record in reviewed["sources"]:
        path = DATA / "source" / record["file"]
        if not path.is_file() or record["url"] != SOURCES.get(record["file"]) or digest(path) != record["sha256"]:
            raise ValueError(f"Shikokuchuo source missing or changed: {record['file']}")
    return reviewed


def _validate_rules(rules):
    for entry in rules:
        if set(entry) != {"types", "weekdays", "occurrences", "months"}:
            raise ValueError("Unexpected recurrence field")
        if (not entry["types"] or not set(entry["types"]) <= set(COLLECTION_TYPES)
                or any(day not in range(1, 8) for day in entry["weekdays"])
                or any(n not in range(1, 6) for n in entry["occurrences"])
                or any(month not in range(1, 13) for month in entry["months"])):
            raise ValueError("Invalid Shikokuchuo recurrence")


def expand_rules(rules, *, profile):
    _validate_rules(rules)
    result = {}
    skipped = CLOSURES - (MISHIMA_FESTIVAL_COLLECTION if profile.startswith("mishima") else set())
    current = date.fromisoformat(VALID_FROM)
    end = date.fromisoformat(VALID_TO)
    while current <= end:
        key = current.isoformat()
        codes = set()
        occurrence = (current.day - 1) // 7 + 1
        for entry in rules:
            if (current.month in entry["months"] and current.isoweekday() in entry["weekdays"]
                    and occurrence in entry["occurrences"]):
                codes.update(entry["types"])
        if codes and key not in skipped:
            result[key] = sorted(codes)
        current += timedelta(days=1)
    return result


def reviewed_areas():
    return [{key: value for key, value in row.items() if key != "rules"} for row in AREAS]


def calendar_payload():
    calendars = {}
    reviews = []
    for row in AREAS:
        days = expand_rules(row["rules"], profile=row["rule_profile_id"])
        skipped = sorted(CLOSURES - (MISHIMA_FESTIVAL_COLLECTION if row["rule_profile_id"].startswith("mishima") else set()))
        calendars[row["calendar_id"]] = {
            "source_url": PDF_URLS["districts"], "verification_status": "checked",
            "days": days,
            "exceptions": [{"date": value, "status": "no_collection", "source_url": HOLIDAY_URL}
                           for value in skipped],
        }
        reviews.append({
            "area_id": row["id"], "calendar_id": row["calendar_id"],
            "address_labels": row["address_labels"], "cutoff": row["cutoff"],
            "rules": row["rules"], "excluded_dates": skipped,
            "days_sha256": value_digest(days), "dated_cells": len(days),
            "collection_dates": dict(sorted(Counter(code for values in days.values() for code in values).items())),
        })
    review = {
        "schema_version": 1, "municipality_id": CITY, "version": VERSION,
        "valid_from": VALID_FROM, "valid_to": VALID_TO, "areas": reviews,
        "verification": {
            "method": "The official two-page district table was rendered at 200 dpi and visually reviewed. Weekly and Nth-weekday rules were expanded, then official 2026 fiscal-year closure dates were removed.",
            "coverage": "Twenty user-facing area choices preserve the five Kawanoe schedules and 07:00 highlighted subareas, five Mishima schedules, three Doi schedules and three Shingu schedules.",
            "limitations": "Weather, snow and road-freezing cancellations are not known in advance and are never generated. Mishima collection on 2026-10-14 and 2026-10-15 is preserved exactly as the official closure notice states.",
            "reviewed_at": "2026-11-07",
        },
    }
    return calendars, review


def item_definitions():
    rows = []
    number = 1
    for category, source_category, names in ITEM_GROUPS:
        for name in names:
            note, options = SPECIAL.get(name, ("", []))
            rows.append({
                "item_id": f"shikokuchuo-{number:04d}", "item": name,
                "category": category, "source_category": source_category,
                "note": note, "category_options": list(options),
            })
            number += 1
    if len({row["item"] for row in rows}) != len(rows):
        duplicates = [name for name, count in Counter(row["item"] for row in rows).items() if count > 1]
        raise ValueError(f"Duplicate Shikokuchuo items: {duplicates}")
    return rows


def item_review():
    rows = item_definitions()
    return {
        "schema_version": 1, "municipality_id": CITY, "version": VERSION,
        "official_items": len(rows), "items_sha256": value_digest(rows),
        "categories": dict(sorted(Counter(row["category"] for row in rows).items())),
        "conditional_records": sum(bool(row["category_options"]) for row in rows),
        "source_files": ["waste-standards.pdf", "burnable.pdf", "nonburnable.pdf", "resources.pdf", "appliances.pdf", "lithium.pdf"],
        "verification": {
            "method": "All six pages of the official waste discharge standards were rendered at 200 dpi; named rows were transcribed and cross-checked with the category-specific official guides. Explicit resource and lithium examples were added from those guides.",
            "limitations": "Size/material alternatives not stated by the user require clarification. Unknown items are not classified solely by analogy.",
            "reviewed_at": "2026-11-07",
        },
    }


def item_rows():
    categories = read(DATA / "official_rules.json")["categories"]
    result = []
    for item in item_definitions():
        definition = categories[item["category"]]
        result.append({
            "item_id": item["item_id"], "item": item["item"],
            "category": item["category"], "category_display": definition["name"],
            "note": item["note"],
            "search_text": " ".join(filter(None, (item["item"], item["source_category"], item["note"], definition.get("instructions", "")))),
            "disposal_instructions": definition.get("instructions", ""),
            "category_options": json.dumps(item["category_options"], ensure_ascii=False),
            "source_url": PDF_URLS["waste-standards"], "source_category": item["source_category"],
        })
    return result


def _bulky_config():
    return {
        "municipality_id": CITY, "municipality_name": "四国中央市",
        "collection_frequency": "戸別収集（申込制）またはクリーンセンターへ直接搬入",
        "reception_hours": "申込・搬入前に公式案内で最新情報を確認",
        "collection_rules": "一斗缶（24cm×24cm×35cm）より大きい物は原則として粗大ごみです。公式の品目別手数料と申込方法を確認してください。",
        "fee_structure_type": "size_based", "application_method": "phone",
        "phone_number": "0896-28-6015", "web_form_url": None, "information_url": PAGE_URL,
        "steps": [
            {"step_number": 1, "title": "品目と大きさを確認", "description": "一斗缶より大きい物か、公式排出基準表で粗大と指定された物かを確認します。"},
            {"step_number": 2, "title": "手数料を確認", "description": "公式の粗大ごみ処理手数料表で品目別料金を確認します。"},
            {"step_number": 3, "title": "市へ申し込む", "description": "最新の申込方法・受付日時を市の公式案内で確認します。"},
            {"step_number": 4, "title": "指定方法で排出", "description": "案内された日・場所・方法に従います。地区別定期カレンダーへ粗大ごみ日を推測追加しません。"},
        ],
    }


def _profile(profile_id, rules):
    categories = {}
    for code, definition in rules["categories"].items():
        value = {key: val for key, val in definition.items() if key != "instructions"}
        if value.get("collection_type_id"):
            value["cutoff"] = "07:00" if profile_id == "early_0700" else "07:30"
        categories[code] = value
    return {
        "items_path": "knowledge/items.csv",
        "embedding_index_path": "knowledge/item_embeddings.npz",
        "index_profile_id": "citywide", "calendar_path": "generated/calendar-2026.json",
        "classification_rules": rules["classification_rules"],
        "size_question": "品目の材質、大きさ（一斗缶より大きいか）、電池を取り外せるかを教えてください。",
        "knowledge_title": "四国中央市家庭ごみ分別・排出基準",
        "categories": categories,
        "bulky_waste": {"category_code": "bulky", "config": _bulky_config()},
    }


def build(*, inspect_only=False):
    checked_sources()
    calendars, calendar_review = calendar_payload()
    current_item_review = item_review()
    write(DATA / "generated/calendar-review-candidate.json", calendar_review)
    write(DATA / "generated/item-review-candidate.json", current_item_review)
    write(DATA / "generated/areas-candidate.json", {"areas": reviewed_areas()})
    if inspect_only:
        print("Wrote Shikokuchuo calendar, area and item review candidates")
        return
    if read(DATA / "calendar_reviews.json") != calendar_review:
        raise ValueError("Shikokuchuo calendar rules differ from reviewed record")
    if read(DATA / "item_reviews.json") != current_item_review:
        raise ValueError("Shikokuchuo item records differ from reviewed record")
    if read(DATA / "areas.json") != {"areas": reviewed_areas()}:
        raise ValueError("Shikokuchuo area mapping differs from reviewed record")
    rules = read(DATA / "official_rules.json")
    areas = [{
        "id": row["id"], "name": row["name"], "display_name": row["display_name"],
        "calendar_id": row["calendar_id"], "rule_profile_id": row["rule_profile_id"],
        "address_labels": row["address_labels"], "needs_local_confirmation": True,
        "source_url": PDF_URLS["districts"],
    } for row in AREAS]
    registry = {
        "schema_version": 1, "municipality_id": CITY, "municipality_name": "四国中央市",
        "prefecture_id": "38", "prefecture_name": "愛媛県", "version": VERSION,
        "valid_from": VALID_FROM, "valid_to": VALID_TO,
        "collection_areas": areas,
        "calendars": [{"id": row["calendar_id"], "rule_profile_id": row["rule_profile_id"]} for row in AREAS],
        "rule_profiles": {
            "standard_0730": _profile("standard_0730", rules),
            "early_0700": _profile("early_0700", rules),
            "mishima_0730": _profile("mishima_0730", rules),
        },
    }
    write(DATA / "registry.json", registry)
    write(DATA / "generated/calendar-2026.json", {
        "municipality_id": CITY, "version": VERSION, "valid_from": VALID_FROM,
        "valid_to": VALID_TO, "calendars": calendars,
    })
    entries = []
    for row in areas:
        entries.extend({"town": label, "lookup_town": label, "area_id": row["id"]}
                       for label in row["address_labels"])
    write(DATA / "generated/addresses.json", {"municipality_id": CITY, "version": VERSION, "entries": entries})
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
    print(f"Built {len(areas)} Shikokuchuo areas, {len(calendars)} calendars and {len(rows)} item records")


def verify(*, without_index=False):
    checked_sources()
    calendars, calendar_review = calendar_payload()
    if read(DATA / "calendar_reviews.json") != calendar_review or read(DATA / "item_reviews.json") != item_review():
        raise ValueError("Shikokuchuo reviewed metadata changed")
    registry = read(DATA / "registry.json")
    bundle = read(DATA / "generated/calendar-2026.json")
    if bundle["calendars"] != calendars or len(registry["collection_areas"]) != len(AREAS):
        raise ValueError("Shikokuchuo generated registry/calendar changed")
    with (DATA / "knowledge/items.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if rows != item_rows():
        raise ValueError("Shikokuchuo item CSV changed")
    index = DATA / "knowledge/item_embeddings.npz"
    manifest = DATA / "knowledge/index_manifest.json"
    if not without_index:
        if not index.is_file() or not manifest.is_file():
            raise ValueError("Shikokuchuo embedding index is missing")
        metadata = read(manifest)
        if (metadata["municipality_id"] != CITY or metadata["profile_id"] != "citywide"
                or metadata["item_count"] != len(rows) or metadata["source_sha256"] != digest(DATA / "knowledge/items.csv")
                or metadata["index_sha256"] != digest(index)):
            raise ValueError("Shikokuchuo CSV/index/manifest mismatch")
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
