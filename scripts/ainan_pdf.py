#!/usr/bin/env python3
"""Extract Ainan's ruled item table from rendered pages and OCR coordinates."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

from PIL import Image
import numpy as np


ITEM_X_MAX = 490
CATEGORY_X_MIN = 490
CATEGORY_X_MAX = 665
TABLE_X_MIN = 120
TABLE_X_MAX = 1520

CATEGORY_COLORS = {
    "burnable": (255, 188, 56),
    "containers": (153, 99, 69),
    "pet_bottles": (168, 209, 79),
    "nonburnable": (74, 81, 138),
    "paper_resource": (155, 193, 231),
    "small_appliances": (250, 175, 206),
    "not_collected": (242, 66, 52),
}

CATEGORY_NAMES = {
    "burnable": "可燃",
    "containers": "びん・缶",
    "pet_bottles": "ペットボトル",
    "nonburnable": "不燃",
    "waste_paper": "古紙",
    "dry_batteries": "資源",
    "small_appliances": "小型家電",
    "bulky": "粗大",
    "not_collected": "禁止",
}

OCR_ITEM_CORRECTIONS = {
    (4, "アルミコーティンク袋"): "アルミコーティング袋",
    (4, "アダブター(家電製品)"): "アダプター(家電製品)",
    (5, "ウインドサーフィン用ポード"): "ウインドサーフィン用ボード",
    (5, "アンプ(家製品)"): "アンプ(家電製品)",
    (5, "-輪車(遊具)"): "一輪車(遊具)",
    (5, "-升びん"): "一升びん",
    (5, "-斗缶"): "一斗缶",
    (6, "ウ工ストバッグ"): "ウエストバッグ",
    (6, "工アーポンプ(プラ製)"): "エアーポンプ(プラ製)",
    (6, "工アコン"): "エアコン",
    (6, "工アマット"): "エアマット",
    (7, "オルコール"): "オルゴール",
    (8, "カー丁ン"): "カーテン",
    (8, "カセットボンべ(カセットコンロ用)"): "カセットボンベ(カセットコンロ用)",
    (9, "ガスポンべ(プロバンガス用)"): "ガスボンベ(プロパンガス用)",
    (9, "カ/ヾン"): "カバン",
    (9, "力、つら"): "かつら",
    (10, "キーポード(家電製品)(楽器・パソコン用)"): "キーボード(家電製品)(楽器・パソコン用)",
    (10, "乾電池(水銀電池充電池等)"): "乾電池(水銀電池・充電池等)",
    (10, "給油ホンプ(電動式)(家電製品)"): "給油ポンプ(電動式)(家電製品)",
    (11, "啗具"): "漁具",
    (11, "ェ刄浄機(家電製品)"): "空気清浄機(家電製品)",
    (11, "ェ気清浄機フィルター"): "空気清浄機フィルター",
    (11, "クーラー(工アコン)"): "クーラー(エアコン)",
    (11, "クールポックス(発砲スチロール)"): "クールボックス(発泡スチロール)",
    (11, "果物バック・ネット"): "果物バッグ・ネット",
    (12, "クレョン・クレバス"): "クレヨン・クレパス",
    (12, "クレョン・クレバスのケース"): "クレヨン・クレパスのケース",
    (13, "こたっ布団"): "こたつ布団",
    (14, "コルクポード"): "コルクボード",
    (14, "ゴルフ/ヾッグ"): "ゴルフバッグ",
    (14, "コンクリートプロック"): "コンクリートブロック",
    (14, "小型簡易ポイラー"): "小型簡易ボイラー",
    (16, "蛇ロ"): "蛇口",
    (16, "シャン丁リア"): "シャンデリア",
    (16, "しやもじ"): "しゃもじ",
    (16, "シュースの紙パック"): "ジュースの紙パック",
    (17, "じようろ(プラ製)"): "じょうろ(プラ製)",
    (17, "しよう油さし(プラ製)"): "しょう油さし(プラ製)",
    (17, "しよう油のボトル、容器(ペットボトル)"): "しょう油のボトル、容器(ペットボトル)",
    (17, "しよう油のボトル、容器(びん製)"): "しょう油のボトル、容器(びん製)",
    (17, "しようのう(防虫剤)"): "しょうのう(防虫剤)",
    (17, "シルノヾーカー"): "シルバーカー",
    (17, "′ヾンぐノンシンナー"): "シンナー・ベンジン",
    (17, "スーッケース・トランク"): "スーツケース・トランク",
    (18, "スノーポード"): "スノーボード",
    (19, "スリッ/ヾ"): "スリッパ",
    (20, "ソファーソファーべッド"): "ソファー・ソファーベッド",
    (21, "タッ/ヾ--"): "タッパー",
    (21, "ダンポール"): "ダンボール",
    (21, "たわし(わら・しゅろ製プラ製)"): "たわし(わら・しゅろ製・プラ製)",
    (22, "つつばり棚・つつばり棒"): "つっぱり棚・つっぱり棒",
    (22, "っぽ(壷)"): "つぼ(壺)",
    (22, "テ・イツぐノユベーノ、-"): "ティッシュペーパー",
    (23, "テニスポール"): "テニスボール",
    (23, "テレピ台"): "テレビ台",
    (23, "電子ヒアノ"): "電子ピアノ",
    (23, "電子レンシ(家電製品)"): "電子レンジ(家電製品)",
    (24, "天ぶらガード"): "天ぷらガード",
    (24, "天ぶら油の容器(金属製)"): "天ぷら油の容器(金属製)",
    (24, "天ぶら鍋"): "天ぷら鍋",
    (24, "言ーロ(家蚫製品)"): "ドローン(家電製品)",
    (24, "トランク・スーッケース"): "トランク・スーツケース",
    (24, "トランシーーノヾ--(家電製品)"): "トランシーバー(家電製品)",
    (25, ":六ヱ、〃ルしロ"): "流し台",
    (25, "ねすみカゴ"): "ねずみカゴ",
    (25, "ねすみ取り(マット)"): "ねずみ取り(マット)",
    (25, "授袋(シュラフザック)"): "寝袋(シュラフザック)",
    (25, "ネコ車(-輪車)"): "ネコ車(一輪車)",
    (26, "/ヾ・-べ卉・ユ・ーコンロ"): "バーベキューコンロ",
    (26, "/ヾケッ"): "バケツ",
    (26, "/ヾソコン"): "パソコン",
    (26, "/ヾッグ、"): "バッグ",
    (27, "ノ、ンドルカ/ヾ-"): "ハンドルカバー",
    (28, "(家電製品)"): "ヒーター(家電製品)",
    (29, "フライバン"): "フライパン",
    (29, "プレーヤー()DDVD等)"): "プレーヤー(CD・DVD等)",
    (29, "プロック(コンクリート)"): "ブロック(コンクリート)",
    (29, "プロック(おもちゃ)"): "ブロック(おもちゃ)",
    (30, "フロッヒーディスク"): "フロッピーディスク",
    (30, "プロバンガスポンべ"): "プロパンガスボンベ",
    (30, "ヘアヒン"): "ヘアピン",
    (30, "べッドマット"): "ベッドマット",
    (30, "′、ンぐノン・ぐノンナー"): "ベンジン・シンナー",
    (30, "べンチ(椅子)"): "ベンチ(椅子)",
    (30, "べルト"): "ベルト",
    (31, "ポールベン"): "ボールペン",
    (31, "ポイラー(風呂用)"): "ボイラー(風呂用)",
    (31, "(ゴム製・ビニール製)"): "ボート(ゴム製・ビニール製)",
    (31, "ポート(上記以外)"): "ボート(上記以外)",
    (31, "ポードマーカー"): "ボードマーカー",
    (31, "ホームペーカリー(家電製品)"): "ホームベーカリー(家電製品)",
    (31, "ポーリングの球"): "ボウリングの球",
    (31, "ポール(球技用)"): "ボール(球技用)",
    (31, "ポストンバック"): "ボストンバッグ",
    (32, "マジック・マジックベン"): "マジック・マジックペン",
    (33, "(家電製品)"): "ミシン(家電製品)",
    (34, "モ/ヾイノレノヾッテリー"): "モバイルバッテリー",
    (34, "ャカン"): "ヤカン",
    (34, "ャスリ"): "ヤスリ",
    (35, "リャカー"): "リヤカー",
    (35, "レシャーシート"): "レジャーシート",
    (35, "レンヾノロ"): "レンジ台",
}


def _distance(left, right):
    return sum((a - b) ** 2 for a, b in zip(left, right)) ** 0.5


def _normalise(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    text = text.replace("−", "-").replace("―", "-")
    text = text.replace("丿レ", "ル")
    text = text.replace("ボンべ", "ボンベ")
    text = re.sub(r"(?<=[ァ-ヶ])-|-(?=[ァ-ヶ])", "ー", text)
    return text.strip("・")


def _horizontal_boundaries(array: np.ndarray) -> list[int]:
    sample = array[
        120:min(array.shape[0], 2220),
        TABLE_X_MIN:min(array.shape[1], TABLE_X_MAX):4,
    ]
    channel_range = sample.max(axis=2) - sample.min(axis=2)
    dark = (channel_range < 35) & (sample.sum(axis=2) < 240)
    candidates = (np.flatnonzero(dark.sum(axis=1) > 200) + 120).tolist()
    groups: list[list[int]] = []
    for y in candidates:
        if not groups or y > groups[-1][-1] + 3:
            groups.append([y])
        else:
            groups[-1].append(y)
    return [round(sum(group) / len(group)) for group in groups]


def _row_words(ocr, top: int, bottom: int):
    lines = []
    for line in ocr["lines"]:
        words = [
            word
            for word in line["words"]
            if top < word["y"] + word["height"] / 2 < bottom
        ]
        if words:
            lines.append((min(word["y"] for word in words), sorted(words, key=lambda word: word["x"])))
    return [word for _, words in sorted(lines, key=lambda pair: pair[0]) for word in words]


def _column_text(words, left: float, right: float | None = None) -> str:
    selected = [
        word
        for word in words
        if word["x"] >= left and (right is None or word["x"] < right)
    ]
    return _normalise("".join(word["text"] for word in selected))


def _color_categories(array: np.ndarray, top: int, bottom: int) -> list[str]:
    region = array[
        top + 4:bottom - 3:3,
        CATEGORY_X_MIN + 3:CATEGORY_X_MAX - 2:3,
    ].reshape(-1, 3).astype(np.int32)
    codes = list(CATEGORY_COLORS)
    targets = np.asarray([CATEGORY_COLORS[code] for code in codes], dtype=np.int32)
    distances = ((region[:, None, :] - targets[None, :, :]) ** 2).sum(axis=2)
    closest = distances.argmin(axis=1)
    accepted = distances[np.arange(len(region)), closest] <= 32 ** 2
    counts = Counter(codes[index] for index in closest[accepted])
    if not counts:
        return []
    maximum = max(counts.values())
    return [code for code, count in counts.items() if count >= max(20, maximum * 0.2)]


def _categories(array, top: int, bottom: int, text: str, item: str) -> list[str]:
    codes = _color_categories(array, top, bottom)
    if "粗大" in text or "大粗" in text:
        codes.append("bulky")
    if "古紙" in text:
        codes = [code for code in codes if code != "paper_resource"]
        codes.append("waste_paper")
    elif "資源" in text:
        codes = [code for code in codes if code != "paper_resource"]
        codes.append("dry_batteries")
    elif "paper_resource" in codes:
        codes = [code for code in codes if code != "paper_resource"]
        codes.append(
            "dry_batteries"
            if any(token in item for token in ("電池", "バッテリ"))
            else "waste_paper"
        )
    if not codes and not text:
        # Bulky rows use an unfilled white category cell with black text. OCR
        # occasionally misses those two characters, but no other data category
        # uses an unfilled cell in the official table.
        codes.append("bulky")
    preferred = [
        "burnable",
        "containers",
        "pet_bottles",
        "nonburnable",
        "paper_resource",
        "waste_paper",
        "dry_batteries",
        "small_appliances",
        "bulky",
        "not_collected",
    ]
    return [code for code in preferred if code in set(codes)]


def extract_items(image_dir: Path, ocr_dir: Path, *, minimum_rows: int = 500):
    rows = []
    for image_path in sorted(image_dir.glob("page-*.png")):
        page = int(image_path.stem.rsplit("-", 1)[-1])
        ocr_path = ocr_dir / f"{image_path.stem}.json"
        image = Image.open(image_path).convert("RGB")
        array = np.asarray(image)
        ocr = json.loads(ocr_path.read_text(encoding="utf-8-sig"))
        boundaries = _horizontal_boundaries(array)
        if len(boundaries) < 5:
            raise ValueError(f"Ainan table ruling was not found on page {page}")
        for top, bottom in zip(boundaries, boundaries[1:]):
            if bottom - top < 15:
                continue
            words = _row_words(ocr, top, bottom)
            item = _column_text(words, 0, ITEM_X_MAX)
            item = OCR_ITEM_CORRECTIONS.get((page, item), item)
            category_text = _column_text(words, CATEGORY_X_MIN, CATEGORY_X_MAX)
            note = _column_text(words, CATEGORY_X_MAX)
            if (
                top < 200
                or not item
                or "具体例" in item
                or item in {"品名", "品目"}
                or category_text in {"分別", "別分"}
            ):
                continue
            categories = _categories(array, top, bottom, category_text, item)
            if not categories:
                raise ValueError(
                    f"Ainan category could not be read on PDF page {page}: "
                    f"{item!r} ({category_text!r})"
                )
            primary = categories[0]
            rows.append({
                "item_id": f"ainan-{len(rows) + 1:04}",
                "item": item,
                "category": primary,
                "category_options": categories[1:],
                "source_category": "、".join(CATEGORY_NAMES[code] for code in categories),
                "note": note,
                "source_page": page,
            })
    if len(rows) < minimum_rows:
        raise ValueError(f"Only {len(rows)} Ainan item rows were extracted")
    return rows
