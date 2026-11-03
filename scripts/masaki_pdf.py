#!/usr/bin/env python3
"""Extract Masaki Town's item index from the official sorting guide.

The guide uses Japanese fonts whose PDF character maps are incomplete for
some readers.  Poppler provides the visible Unicode text, while PyMuPDF is
used only for the ruled-table geometry.  This avoids OCR and keeps every
record tied to the printed item table.
"""
from __future__ import annotations

import re
import unicodedata


CATEGORY_CODES = {
    "可燃": "burnable",
    "紙（新聞）": "newspapers",
    "紙（新）": "newspapers",
    "紙（段）": "cardboard",
    "紙（パ）": "paper_cartons",
    "紙（雑）": "mixed_paper",
    "プラ": "plastic",
    "ペット": "pet_bottles",
    "かん": "cans",
    "びん": "bottles",
    "金属": "metal",
    "古着": "textiles",
    "せん": "pruning",
    "せんてい": "pruning",
    "廃食用油": "waste_oil",
    "有害": "hazardous",
    "埋立": "landfill",
    "粗大": "bulky",
    "禁止": "not_collected",
}

TABLE_LAYOUTS = (
    (39.68, 134.36, 171.21, 289.13),
    (306.14, 400.81, 437.66, 555.59),
)


def clean(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    return " ".join(value.replace("\u3000", " ").split())


def compact(value: str | None) -> str:
    return re.sub(r"[\s・･、,]", "", clean(value))


def category_code(label: str) -> str:
    normalized = compact(label)
    for official, code in sorted(
        CATEGORY_CODES.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if compact(official) == normalized:
            return code
    escaped = label.encode("unicode_escape").decode("ascii")
    raise ValueError(f"Unknown Masaki dictionary category: {escaped}")


def category_options(note: str, primary: str) -> list[str]:
    """Keep explicit alternative outcomes without overriding the primary."""
    values = []

    def add(code: str):
        if code != primary and code not in values:
            values.append(code)

    normalized = compact(note)
    if re.search(
        r"45(?:リットル|ℓ|L)?の袋に入らなければ粗大|指定袋に入らなければ粗大",
        normalized,
    ):
        add("bulky")
    if "金属製のものは金属" in normalized or "金属部分は金属" in normalized:
        add("metal")
    if "電池は有害" in normalized or "電池を外して有害" in normalized:
        add("hazardous")
    # The 2021 guide contains an old dirty-plastic fallback to burnable.
    # It is deliberately not emitted as an option: the current official
    # rule (effective April 2023) requires cleaning and plastic collection.
    return values


def current_note(note: str, category: str) -> str:
    """Remove superseded plastic-to-burnable fallbacks from search data."""
    normalized = compact(note)
    old_fallback = (
        category == "plastic"
        and "可燃" in normalized
        and (
            "汚れ" in normalized
            or "中身が残" in normalized
        )
    )
    if old_fallback:
        return (
            "現行ルール（令和5年4月以降）: 中身を使い切り、汚れを取り除いて"
            "プラスチック類へ出す。紙・金属など異素材の部品は材質別に分ける。"
        )
    return note


def _row_boundaries(page, left: float, right: float) -> list[float]:
    values = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] != "l":
                continue
            start, end = item[1], item[2]
            if abs(start.y - end.y) > 0.5:
                continue
            x0, x1 = sorted((start.x, end.x))
            if abs(x0 - left) <= 2 and abs(x1 - right) <= 2:
                values.append((start.y + end.y) / 2)
    result = []
    for value in sorted(values):
        if not result or value - result[-1] > 1:
            result.append(value)
    return result


def _cell_text(words, x0: float, x1: float, y0: float, y1: float) -> str:
    selected = [
        word
        for word in words
        if x0 <= word["x"] + word["width"] / 2 <= x1
        and y0 <= word["y"] + word["height"] / 2 <= y1
    ]
    lines = {}
    for word in selected:
        key = (word["block"], word["line"])
        lines.setdefault(key, []).append(word)
    ordered = []
    for line in sorted(
        lines.values(),
        key=lambda values: (
            min(value["y"] for value in values),
            min(value["x"] for value in values),
        ),
    ):
        line.sort(key=lambda value: (value["x"], value["word"]))
        ordered.append("".join(value["text"] for value in line))
    return clean(" ".join(ordered))


def extract_items_from_words(document, words, *, minimum_rows: int = 1):
    by_page = {}
    for word in words:
        by_page.setdefault(word["page"], []).append(word)

    items = []
    seen = set()
    for page_number in range(20, 39):
        page = document[page_number - 1]
        page_words = by_page.get(page_number, [])
        for columns in TABLE_LAYOUTS:
            left, _, _, right = columns
            boundaries = _row_boundaries(page, left, right)
            if len(boundaries) < 30:
                raise ValueError(
                    f"Masaki table geometry changed on PDF page {page_number}: "
                    f"{len(boundaries)} boundaries"
                )
            for top, bottom in zip(boundaries, boundaries[1:]):
                values = [
                    _cell_text(page_words, x0, x1, top, bottom)
                    for x0, x1 in zip(columns, columns[1:])
                ]
                item, label, source_note = values
                if compact(item) == "品名" and compact(label) == "分類":
                    continue
                if not item:
                    if not source_note and len(compact(label)) <= 2:
                        # Kana section heading printed inside the middle column.
                        continue
                    if label or source_note:
                        raise ValueError(
                            f"Orphan Masaki table row on PDF page {page_number}: {values}"
                        )
                    continue
                code = category_code(label)
                key = (page_number, item, label, source_note)
                if key in seen:
                    continue
                seen.add(key)
                note = current_note(source_note, code)
                items.append(
                    {
                        "item": item,
                        "category": code,
                        "source_category": label,
                        "note": note,
                        "source_note": source_note,
                        "category_options": category_options(source_note, code),
                        "source_page": page_number,
                    }
                )
    if len(items) < minimum_rows:
        raise ValueError(f"Too few Masaki item records: {len(items)}")
    for number, item in enumerate(items, 1):
        item["item_id"] = f"masaki-{number:04d}"
    return items


if __name__ == "__main__":
    import argparse
    import csv
    import json
    from pathlib import Path

    import pymupdf

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("tsv", type=Path)
    args = parser.parse_args()
    with args.tsv.open(encoding="utf-8", newline="") as stream:
        words = [
            {
                "page": int(row["page_num"]),
                "block": int(row["block_num"]),
                "line": int(row["line_num"]),
                "word": int(row["word_num"]),
                "x": float(row["left"]),
                "y": float(row["top"]),
                "width": float(row["width"]),
                "height": float(row["height"]),
                "text": row["text"],
            }
            for row in csv.DictReader(stream, delimiter="\t")
            if row.get("level") == "5"
        ]
    result = extract_items_from_words(pymupdf.open(args.pdf), words)
    print(json.dumps(result, ensure_ascii=False, indent=2))
