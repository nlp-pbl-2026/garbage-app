#!/usr/bin/env python3
"""Extract Uchiko's current item dictionary and 2026 calendar tables."""
from __future__ import annotations

from datetime import date
import re
from pathlib import Path


CATEGORY_CODES = {
    "可燃": "burnable",
    "不燃": "nonburnable",
    "粗大": "bulky",
    "（素材）": "material_dependent",
    "［禁止］": "not_collected",
    "［家電４品目］": "appliance_recycling",
    "資源雑誌等": "waste_paper",
    "資源布・古着": "textiles",
    "生ごみ": "organic",
    "資源びん": "bottles",
    "廃食油": "waste_oil",
    "資源かん": "cans",
    "資源紙パック": "paper_cartons",
    "資源新聞": "newspapers",
    "資源白色トレー": "white_trays",
    "資源白色トレイ": "white_trays",
    "資源ダンボール": "cardboard",
    "資源ペットボトル": "pet_bottles",
}

RESOURCE_ROW_CODES = (
    ("waste_paper",),
    ("cans",),
    ("bottles", "pet_bottles", "white_trays", "textiles"),
    ("nonburnable",),
)


def _compact(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def _text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def category_code(label: str) -> str:
    normalized = _compact(label).replace("※", "")
    try:
        return CATEGORY_CODES[normalized]
    except KeyError as error:
        raise ValueError(f"Unknown Uchiko category: {label!r}") from error


def category_options(note: str, primary: str) -> list[str]:
    values = []

    def add(code: str):
        if code != primary and code not in values:
            values.append(code)

    if re.search(r"袋に入らない[^。]*粗大", note):
        add("bulky")
    if "その他の地区は可燃" in note:
        add("burnable")
    if "素材により「可燃」または「不燃」" in note:
        add("burnable")
        add("nonburnable")
    if re.search(
        r"(?:金属製|金属部分|金具|一辺(?:が)?20.{0,4}以上|割れたもの).{0,12}不燃",
        note,
    ):
        add("nonburnable")
    if re.search(
        r"(?:木製|カーボン|ナイロン製|ビニール加工|汚れがひどい).{0,12}可燃",
        note,
    ):
        add("burnable")
    return values


def extract_items_from_pages(pages, *, start_page: int = 2, minimum_rows: int = 1):
    items = []
    for offset, page in enumerate(pages):
        physical_page = start_page + offset
        tables = page.extract_tables()
        if len(tables) != 1:
            raise ValueError(
                f"Expected one Uchiko item table on PDF page {physical_page}, "
                f"found {len(tables)}"
            )
        table = tables[0]
        if not table or _compact(table[0][1]) != "品目":
            raise ValueError(f"Uchiko item header changed on PDF page {physical_page}")
        for raw in table[1:]:
            if len(raw) != 4:
                raise ValueError(f"Malformed Uchiko item row on PDF page {physical_page}")
            item = _text(raw[1])
            source_category = _compact(raw[2])
            note = _text(raw[3])
            if not item:
                if source_category or note:
                    raise ValueError(
                        f"Orphan Uchiko item continuation on PDF page {physical_page}: {raw}"
                    )
                continue
            # One ruled cell boundary splits the closing parenthesis from the item name.
            if source_category.startswith("）"):
                item += "）"
                source_category = source_category[1:]
            primary = category_code(source_category)
            items.append({
                "item": item,
                "category": primary,
                "source_category": source_category.replace("※", ""),
                "note": note,
                "category_options": category_options(note, primary),
                "source_page": physical_page,
            })
    if len(items) < minimum_rows:
        raise ValueError(f"Too few Uchiko item records: {len(items)}")
    if len({item["item"] for item in items}) != len(items):
        raise ValueError("Duplicate Uchiko item names found")
    for number, item in enumerate(items, 1):
        item["item_id"] = f"uchiko-{number:04d}"
    return items


def extract_items(path: Path, *, minimum_rows: int = 850):
    import pdfplumber

    with pdfplumber.open(path) as document:
        if len(document.pages) != 13:
            raise ValueError(f"Uchiko dictionary page count changed: {len(document.pages)}")
        return extract_items_from_pages(
            document.pages[1:13], start_page=2, minimum_rows=minimum_rows
        )


def extract_resource_tables_from_page(page, *, source_name="calendar.pdf"):
    """Return literal 2026 dates from one calendar page."""
    tables = [
        table
        for table in page.extract_tables()
        if table and len(table[0]) == 15 and len(table) == 5
    ]
    results = []
    for table_number, table in enumerate(tables, 1):
        if _compact(table[0][2]) != "収集曜日":
            raise ValueError(f"Uchiko calendar header changed: {source_name} table {table_number}")
        days: dict[str, list[str]] = {}
        rules = {}
        for row, codes in zip(table[1:], RESOURCE_ROW_CODES, strict=True):
            rule = _text(row[2])
            for code in codes:
                rules[code] = rule
            for month, cell in enumerate(row[3:15], 1):
                matches = re.findall(r"\d+", _compact(cell))
                if len(matches) != 1:
                    raise ValueError(
                        f"Unexpected Uchiko date in {source_name} table {table_number}: {cell!r}"
                    )
                value = date(2026, month, int(matches[0])).isoformat()
                days.setdefault(value, []).extend(codes)
        results.append({
            "rules": rules,
            "days": {day: sorted(set(codes)) for day, codes in sorted(days.items())},
        })
    if not results:
        raise ValueError(f"No Uchiko resource tables found: {source_name}")
    return results


def extract_resource_tables(path: Path):
    """Return literal 2026 dates from each resource/nonburnable table."""
    import pdfplumber

    with pdfplumber.open(path) as document:
        if len(document.pages) != 1:
            raise ValueError(f"Uchiko calendar page count changed: {path.name}")
        return extract_resource_tables_from_page(
            document.pages[0], source_name=path.name
        )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("items", "calendar"))
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    value = extract_items(args.pdf) if args.kind == "items" else extract_resource_tables(args.pdf)
    print(json.dumps(value, ensure_ascii=False, indent=2))
