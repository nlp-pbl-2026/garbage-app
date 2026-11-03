#!/usr/bin/env python3
"""Extract Kihoku's two-column item table from Poppler TSV output."""
from __future__ import annotations

import csv
from pathlib import Path
import re


CATEGORY_CODES = {
    "可燃": "burnable",
    "不燃": "nonburnable",
    "びん缶": "containers",
    "禁止": "not_collected",
    "古紙": "waste_paper",
    "資源": "resources",
    "粗大": "bulky",
    "ペット": "pet_bottles",
}

COLUMNS = (
    {"item": (60.0, 168.0), "category": (168.0, 198.0), "note": (198.0, 326.0)},
    {"item": (330.0, 438.0), "category": (438.0, 466.0), "note": (466.0, 594.0)},
)


def _clean(value: str) -> str:
    return (
        re.sub(r"\s+", "", value)
        .replace("…", "")
        .replace("�", "・")
        .strip()
    )


def load_words(path: Path):
    with path.open(encoding="utf-8", newline="") as stream:
        return [
            {
                "page": int(row["page_num"]),
                "x": float(row["left"]),
                "y": float(row["top"]),
                "width": float(row["width"]),
                "height": float(row["height"]),
                "text": row["text"],
            }
            for row in csv.DictReader(stream, delimiter="\t")
            if row.get("level") == "5" and 3 <= int(row["page_num"]) <= 31
        ]


def _lines(words):
    """Join adjacent words printed on the same baseline."""
    lines = []
    for word in sorted(words, key=lambda value: (value["y"], value["x"])):
        center_y = word["y"] + word["height"] / 2
        for line in reversed(lines[-3:]):
            if abs(line["y"] - center_y) <= 2.2:
                line["words"].append(word)
                line["y"] = sum(
                    item["y"] + item["height"] / 2 for item in line["words"]
                ) / len(line["words"])
                break
        else:
            lines.append({"y": center_y, "words": [word]})
    for line in lines:
        line["words"].sort(key=lambda value: value["x"])
        line["text"] = "".join(word["text"] for word in line["words"])
    return sorted(lines, key=lambda value: value["y"])


def _category_rows(words, x0: float, x1: float):
    category_words = [
        word for word in words
        if x0 <= word["x"] < x1 and 232.0 <= word["y"] <= 830.0
    ]
    raw_lines = _lines(category_words)
    rows = []
    index = 0
    while index < len(raw_lines):
        line = raw_lines[index]
        text = _clean(line["text"])
        if re.fullmatch(r"[ぁ-んァ-ン]", text):
            index += 1
            continue
        used = [line]
        if text not in CATEGORY_CODES and index + 1 < len(raw_lines):
            following = raw_lines[index + 1]
            combined = _clean(text + following["text"])
            if following["y"] - line["y"] <= 16.0 and combined in CATEGORY_CODES:
                text = combined
                used.append(following)
                index += 1
        if text not in CATEGORY_CODES:
            # A few long notes begin slightly inside the narrow category band.
            # They are retained by the note-column extraction and are not rows.
            index += 1
            continue
        rows.append({
            "y": sum(value["y"] for value in used) / len(used),
            "source_category": text,
            "category": CATEGORY_CODES[text],
        })
        index += 1
    return rows


def _cell_text(words, x0: float, x1: float, top: float, bottom: float, *, item=False):
    selected = [
        word for word in words
        if x0 <= word["x"] < x1
        and top <= word["y"] + word["height"] / 2 < bottom
    ]
    lines = _lines(selected)
    if item:
        lines = [
            line for line in lines
            if not re.fullmatch(r"[ぁ-んァ-ン]", _clean(line["text"]))
        ]
    return _clean("".join(line["text"] for line in lines))


def _note_text(words, column, top: float, bottom: float, source_category: str):
    selected = [
        word for word in words
        if column["category"][0] <= word["x"] < column["note"][1]
        and top <= word["y"] + word["height"] / 2 < bottom
    ]
    category_words = [
        word for word in selected if word["x"] < column["note"][0]
    ]
    matched = []
    combined = ""
    for word in sorted(category_words, key=lambda value: (value["y"], value["x"])):
        candidate = _clean(word["text"])
        if source_category.startswith(combined + candidate):
            matched.append(word)
            combined += candidate
            if combined == source_category:
                break
    if combined == source_category:
        matched_ids = {id(word) for word in matched}
        selected = [word for word in selected if id(word) not in matched_ids]
    return _clean("".join(line["text"] for line in _lines(selected))).strip("●")


def _graphic_layout(pdf_path: Path, page_number: int, column):
    import pymupdf

    page = pymupdf.open(pdf_path)[page_number - 1]
    table_x0, table_x1 = column["item"][0], column["note"][1]
    category_x0, category_x1 = column["category"]
    values = []
    fills = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        table_outline = (
            drawing["type"] == "s"
            and abs(rect.x0 - table_x0) <= 5.0
            and abs(rect.x1 - table_x1) <= 5.0
        )
        category_fill = (
            drawing["type"] == "f"
            and abs(rect.x0 - category_x0) <= 5.0
            and abs(rect.x1 - category_x1) <= 5.0
        )
        if (
            (table_outline or category_fill)
            and rect.y0 >= 210.0
            and rect.y1 <= 835.0
            and rect.height >= 12.0
        ):
            values.extend((rect.y0, rect.y1))
            if category_fill:
                fills.append({"top": rect.y0, "bottom": rect.y1})
    clusters = []
    for value in sorted(values):
        if clusters and value - clusters[-1][-1] <= 1.0:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return {
        "boundaries": [sum(cluster) / len(cluster) for cluster in clusters],
        "fills": fills,
    }


def extract_items(tsv_path: Path, pdf_path: Path | None = None):
    words = load_words(tsv_path)
    pages = sorted({word["page"] for word in words})
    items = []
    for page_number in pages:
        page_words = [word for word in words if word["page"] == page_number]
        for column_index, column in enumerate(COLUMNS):
            if page_number == 31 and column_index == 1:
                continue
            fallback = _category_rows(page_words, *column["category"])
            layout = _graphic_layout(pdf_path, page_number, column) if pdf_path else {
                "boundaries": [], "fills": []
            }
            boundaries = layout["boundaries"]
            categories = []
            for index, row in enumerate(fallback):
                fill = next(
                    (
                        value for value in layout["fills"]
                        if value["top"] - 1 <= row["y"] <= value["bottom"] + 1
                    ),
                    None,
                )
                if fill:
                    peers = [
                        value for value in fallback
                        if fill["top"] - 1 <= value["y"] <= fill["bottom"] + 1
                    ]
                    peer_index = peers.index(row)
                    top = fill["top"]
                    bottom = fill["bottom"]
                    if peer_index:
                        between = [
                            value for value in boundaries
                            if peers[peer_index - 1]["y"] < value < row["y"]
                        ]
                        midpoint = (peers[peer_index - 1]["y"] + row["y"]) / 2
                        top = min(between, key=lambda value: abs(value - midpoint)) if between else midpoint
                    if peer_index + 1 < len(peers):
                        between = [
                            value for value in boundaries
                            if row["y"] < value < peers[peer_index + 1]["y"]
                        ]
                        midpoint = (row["y"] + peers[peer_index + 1]["y"]) / 2
                        bottom = min(between, key=lambda value: abs(value - midpoint)) if between else midpoint
                elif boundaries:
                    before = [value for value in boundaries if value < row["y"]]
                    after = [value for value in boundaries if value > row["y"]]
                    top = max(before, default=232.0)
                    bottom = min(after, default=832.0)
                else:
                    top = 232.0 if index == 0 else (fallback[index - 1]["y"] + row["y"]) / 2
                    bottom = 832.0 if index + 1 == len(fallback) else (row["y"] + fallback[index + 1]["y"]) / 2
                category_cell = _cell_text(
                    page_words, *column["category"], top - 1, bottom + 1
                )
                category_spill = ""
                if category_cell.startswith(row["source_category"]):
                    category_spill = category_cell[len(row["source_category"]):]
                categories.append({
                    **row,
                    "top": top,
                    "bottom": bottom,
                    "category_spill": category_spill,
                })
            for row in categories:
                top, bottom = row["top"], row["bottom"]
                item = _cell_text(page_words, *column["item"], top, bottom, item=True).strip("●")
                note = _note_text(page_words, column, top, bottom, row["source_category"])
                if not item:
                    raise ValueError(
                        f"Missing Kihoku item on PDF page {page_number}, "
                        f"y={top:.1f}-{bottom:.1f}, category={row['source_category']}"
                    )
                items.append({
                    "item": item,
                    "category": row["category"],
                    "source_category": row["source_category"],
                    "note": note,
                    "source_page": page_number,
                })
    for number, item in enumerate(items, 1):
        item["item_id"] = f"kihoku-{number:04d}"
    return items


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tsv", type=Path)
    parser.add_argument("--pdf", type=Path)
    args = parser.parse_args()
    print(json.dumps(extract_items(args.tsv, args.pdf), ensure_ascii=False, indent=2))
