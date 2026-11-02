#!/usr/bin/env python3
"""Extract Tobe item tables and dated collections from official PDFs.

The municipality publishes machine-readable, ruled PDF tables.  This module
uses their cell boundaries and text, not OCR or recurrence guesses.  Monthly
calendar PDFs are authoritative only for the dates printed in each issue.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import re
import unicodedata


COLLECTION_ORDER = (
    "burnable",
    "pruning",
    "plastic_packaging",
    "containers",
    "paper_cloth",
    "hazardous",
    "miscellaneous",
)

CALENDAR_IDS = (
    "tobe-asou",
    "tobe-miyauchi-tobe",
    "tobe-hirota-weekly-1",
    "tobe-hirota-weekly-2",
    "tobe-tanoura",
    "tobe-ohira",
    "tobe-unosaki",
)

SPECIAL_CALENDARS = {
    "田ノ浦": "tobe-tanoura",
    "大平": "tobe-ohira",
    "鵜ノ崎": "tobe-unosaki",
}

CATEGORY_CODES = {
    "可燃ごみ": "burnable",
    "剪定枝葉・草": "pruning",
    "剪定枝・葉・草": "pruning",
    "プラスチック製容器包装": "plastic_packaging",
    "プラ製容器包装": "plastic_packaging",
    "空きびん": "bottles",
    "空き缶": "cans",
    "金属くず": "metals",
    "ペットボトル": "pet_bottles",
    "段ボール": "cardboard",
    "紙パック": "paper_cartons",
    "新聞・チラシ": "newspaper",
    "新聞チラシ": "newspaper",
    "雑誌・雑がみ": "magazines",
    "雑誌雑がみ": "magazines",
    "古着・古布": "textiles",
    "古着古布": "textiles",
    "危険ごみ": "hazardous",
    "雑ごみ": "miscellaneous",
    "美化センター": "facility_dropoff",
    "千里埋立処分場": "facility_dropoff",
    "千里": "facility_dropoff",
    "排出禁止物": "not_collected",
}


def clean(value) -> str:
    value = "" if value is None else str(value)
    value = unicodedata.normalize("NFKC", value)
    return " ".join(value.replace("\u3000", " ").split())


def compact(value) -> str:
    return re.sub(r"[\s・･、,]", "", clean(value))


def category_code(label: str, note: str = "") -> str | None:
    """Map an official item-table label without inventing a classification."""
    normalized = compact(label)
    if "可燃" in normalized and "ごみ" in normalized:
        return "burnable"
    if "プラ製" in normalized and "容器包装" in normalized:
        return "plastic_packaging"
    if "剪定枝" in normalized and "草" in normalized:
        return "pruning"
    for official, code in sorted(CATEGORY_CODES.items(), key=lambda item: len(item[0]), reverse=True):
        if compact(official) in normalized:
            return code
    if not normalized:
        normalized_note = compact(note)
        aliases = sorted(CATEGORY_CODES, key=len, reverse=True)
        for official in aliases:
            target = compact(official)
            if target and (target + "参照") in normalized_note:
                return CATEGORY_CODES[official]
        if "枝参照" in normalized_note:
            return "pruning"
        return None
    escaped = label.encode("unicode_escape").decode("ascii")
    raise ValueError(f"Unknown Tobe dictionary category: {escaped}")


def _table_matrices(page):
    try:
        return [table.extract() for table in page.find_tables().tables]
    except (AttributeError, TypeError, ValueError):
        return []


def _item_groups(row):
    cells = [clean(value) for value in row]
    if len(cells) < 4:
        return []
    if len(cells) >= 8:
        return [cells[index:index + 4] for index in range(0, len(cells) - 3, 4)]
    return [cells[:4]]


def extract_items(document, *, minimum_rows: int = 500):
    """Return item/category/note records from the official dictionary PDF."""
    rows = []
    seen = set()
    for page_number, page in enumerate(document, 1):
        for matrix in _table_matrices(page):
            for raw_row in matrix:
                for item, note, category, recycle in _item_groups(raw_row):
                    if compact(item) in {"品名", "品目"} or not item:
                        continue
                    code = category_code(category, note)
                    if code is None:
                        # Cross-reference-only rows without an identifiable
                        # target are retained for audit but cannot be searched
                        # safely until a human assigns their category.
                        continue
                    key = (page_number, item, note, category, recycle)
                    if key in seen:
                        continue
                    seen.add(key)
                    options = ["collection_box"] if "小型家電" in compact(recycle) else []
                    rows.append({
                        "item": item,
                        "note": note,
                        "category": code,
                        "source_category": category,
                        "recycle": recycle,
                        "category_options": options,
                        "source_page": page_number,
                    })
    if len(rows) < minimum_rows:
        raise ValueError(f"Tobe dictionary extraction is incomplete: {len(rows)} rows")
    for index, row in enumerate(rows, 1):
        row["item_id"] = f"tobe-{index:04d}"
    return rows


def _row_boundaries(page, table_left: float, table_right: float) -> list[float]:
    values = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] != "l":
                continue
            start, end = item[1], item[2]
            if abs(start.y - end.y) > .5:
                continue
            left, right = sorted((start.x, end.x))
            if abs(left - table_left) <= 2 and abs(right - table_right) <= 2:
                values.append((start.y + end.y) / 2)
    result = []
    for value in sorted(values):
        if not result or value - result[-1] > 1:
            result.append(value)
    return result


def _cell_text(words, x0: float, x1: float, y0: float, y1: float) -> str:
    selected = [word for word in words
                if x0 <= word["x"] + word["width"] / 2 <= x1
                and y0 <= word["y"] + word["height"] / 2 <= y1]
    lines = {}
    for word in selected:
        key = (word["block"], word["line"])
        lines.setdefault(key, []).append(word)
    ordered = []
    for line in sorted(lines.values(), key=lambda values: (min(value["y"] for value in values),
                                                            min(value["x"] for value in values))):
        line.sort(key=lambda value: (value["x"], value["word"]))
        ordered.append("".join(value["text"] for value in line))
    return clean(" ".join(ordered))


def extract_items_from_words(document, words, *, minimum_rows: int = 500):
    """Combine Poppler Unicode words with PDF rule coordinates.

    Some icon fonts in the dictionary have incomplete ToUnicode maps in
    PyMuPDF/pdfminer.  Poppler returns the visible Japanese text correctly;
    the PDF vector rules provide the cell boundaries.
    """
    by_page = {}
    for word in words:
        by_page.setdefault(word["page"], []).append(word)
    layouts = (
        ((42.52, 126.14, 216.85, 255.12, 289.13), (42.52, 289.13)),
        ((297.64, 381.26, 471.97, 510.24, 544.25), (297.64, 544.25)),
    )
    rows = []
    seen = set()
    canonical = {code: label for label, code in CATEGORY_CODES.items()}
    for page_number, page in enumerate(document, 1):
        page_words = by_page.get(page_number, [])
        for columns, (table_left, table_right) in layouts:
            boundaries = _row_boundaries(page, table_left, table_right)
            for top, bottom in zip(boundaries, boundaries[1:]):
                if bottom - top > 45:
                    continue
                values = [_cell_text(page_words, left, right, top, bottom)
                          for left, right in zip(columns, columns[1:])]
                item, note, label, recycle = values
                if not item or compact(item) in {"品名", "品目"}:
                    continue
                code = category_code(label, note)
                if code is None:
                    continue
                key = (page_number, item, note, code, recycle)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "item": item,
                    "note": note,
                    "category": code,
                    "source_category": canonical[code],
                    "recycle": recycle,
                    "category_options": ["collection_box"] if "小型家電" in compact(recycle) else [],
                    "source_page": page_number,
                })
    if len(rows) < minimum_rows:
        raise ValueError(f"Tobe dictionary extraction is incomplete: {len(rows)} rows")
    for index, row in enumerate(rows, 1):
        row["item_id"] = f"tobe-{index:04d}"
    return rows


def _header_indexes(row):
    cells = [compact(value) for value in row]
    wanted = {
        "asou": ("麻生小校区",),
        "miyauchi": ("宮内小砥部小校区", "宮内小・砥部小校区"),
        "hirota": ("広田地域",),
    }
    indexes = {}
    for key, labels in wanted.items():
        indexes[key] = next(
            (index for index, cell in enumerate(cells)
             if any(compact(label) in cell for label in labels)),
            None,
        )
    return indexes if all(value is not None for value in indexes.values()) else None


def _calendar_rows(page):
    candidates = []
    for matrix in _table_matrices(page):
        for header_index, row in enumerate(matrix):
            indexes = _header_indexes(row)
            if indexes:
                candidates.append((len(matrix) - header_index, matrix, header_index, indexes))
    if not candidates:
        raise ValueError("Tobe calendar collection table was not found")
    _, matrix, header_index, indexes = max(candidates, key=lambda value: value[0])
    return matrix[header_index + 1:], indexes


def _date_from_row(cells, asou_index: int, year: int, month: int) -> date | None:
    prefix = " ".join(clean(value) for value in cells[:asou_index])
    match = re.search(r"(?:(\d{1,2})\s*/\s*)?(\d{1,2})", prefix)
    if not match:
        return None
    explicit_month = int(match.group(1)) if match.group(1) else month
    day = int(match.group(2))
    explicit_year = year
    if month == 12 and explicit_month == 1:
        explicit_year += 1
    elif month <= 3 and explicit_month >= 11:
        explicit_year -= 1
    try:
        parsed = date(explicit_year, explicit_month, day)
    except ValueError:
        return None
    current = date(year, month, 1)
    distance = (parsed - current).days
    return parsed if -7 <= distance <= 42 else None


def _base_types(cell: str) -> list[str]:
    text = compact(cell)
    found = []
    tests = (
        ("burnable", "可燃ごみ"),
        ("pruning", "剪定枝"),
        ("plastic_packaging", "プラ製容器包装"),
        ("containers", "ペットボトル"),
        ("paper_cloth", "紙類"),
        ("paper_cloth", "古着"),
        ("paper_cloth", "古布"),
        ("hazardous", "危険ごみ"),
        ("miscellaneous", "雑ごみ"),
    )
    for code, marker in tests:
        if marker in text and code not in found:
            found.append(code)
    return sorted(found, key=COLLECTION_ORDER.index)


def collection_types(cell: str, area: str) -> list[str]:
    """Map one printed area cell to runtime collection type IDs."""
    found = _base_types(cell)
    if area == "hirota-weekly-1":
        text = compact(cell)
        if "可燃ごみ" in text and "週1" not in text:
            found = [value for value in found if value != "burnable"]
    return found


def extract_calendar(document, *, year: int, month: int, minimum_rows: int = 28):
    """Extract all seven selectable Tobe calendars from one monthly PDF."""
    if len(document) != 1:
        raise ValueError("Tobe monthly life calendar must have one page")
    result = {identifier: {} for identifier in CALENDAR_IDS}
    rows, indexes = _calendar_rows(document[0])
    row_year, row_month = year, month
    for row in rows:
        day = _date_from_row(row, indexes["asou"], row_year, row_month)
        if day is None:
            continue
        row_year, row_month = day.year, day.month
        cells = [clean(value) for value in row]
        values = {
            "tobe-asou": collection_types(cells[indexes["asou"]], "asou"),
            "tobe-miyauchi-tobe": collection_types(cells[indexes["miyauchi"]], "miyauchi"),
            "tobe-hirota-weekly-1": collection_types(cells[indexes["hirota"]], "hirota-weekly-1"),
            "tobe-hirota-weekly-2": collection_types(cells[indexes["hirota"]], "hirota-weekly-2"),
        }
        combined = " ".join(cells[indexes[key]] for key in ("asou", "miyauchi", "hirota"))
        normalized = compact(combined)
        for label, calendar_id in SPECIAL_CALENDARS.items():
            values[calendar_id] = list(COLLECTION_ORDER) if label in normalized and "すべて" in normalized else []
        for calendar_id, types in values.items():
            result[calendar_id][day.isoformat()] = types
    if len(result["tobe-asou"]) < minimum_rows:
        raise ValueError("Tobe monthly calendar has too few dated rows")
    counts = {identifier: dict(Counter(code for values in days.values() for code in values))
              for identifier, days in result.items()}
    return result, {"dated_rows": len(result["tobe-asou"]), "collection_marks": counts}
