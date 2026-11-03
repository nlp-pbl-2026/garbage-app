#!/usr/bin/env python3
"""Extract Matsuno's official item table from the April 2026 PDF."""
from __future__ import annotations

import re
from pathlib import Path


CATEGORY_CODES = {
    "可燃": "burnable",
    "不燃": "nonburnable",
    "PET": "pet_bottles",
    "び・か": "containers",
    "びん・缶": "containers",
    "古紙": "waste_paper",
    "資源": "resources",
    "プラ": "plastic",
    "家電": "small_appliances",
    "粗大": "bulky",
    "禁止": "not_collected",
}

OPTION_PATTERNS = (
    ("容器包装プラスチック", "plastic"),
    ("製品プラスチック", "plastic"),
    ("ペットボトル", "pet_bottles"),
    ("びん・缶", "containers"),
    ("びん・かん", "containers"),
    ("小型家電", "small_appliances"),
    ("粗大", "bulky"),
    ("不燃", "nonburnable"),
    ("可燃", "burnable"),
    ("古紙", "waste_paper"),
    ("資源ごみ", "resources"),
)


def _compact(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "").replace("ＰＥＴ", "PET").strip()


def _text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def category_code(label: str) -> str:
    normalized = _compact(label)
    try:
        return CATEGORY_CODES[normalized]
    except KeyError as error:
        raise ValueError(f"Unknown Matsuno category: {label!r}") from error


def category_options(note: str, primary: str) -> list[str]:
    values = []
    for phrase, code in OPTION_PATTERNS:
        prohibited = re.search(
            re.escape(phrase)
            + r"(?:ごみ)?(?:に|へ|では|として).{0,8}"
            + r"(?:混ぜない|入れない|出せない|出さない|不可|禁止)",
            note,
        )
        if prohibited:
            continue
        if phrase in note and code != primary and code not in values:
            values.append(code)
    return values


def extract_items_from_pages(pages, *, start_page: int = 22, minimum_rows: int = 1):
    items = []
    headers = 0
    for offset, page in enumerate(pages):
        physical_page = start_page + offset
        tables = page.extract_tables()
        if len(tables) != 1:
            raise ValueError(
                f"Expected one Matsuno item table on PDF page {physical_page}, "
                f"found {len(tables)}"
            )
        pending = None

        def finish():
            nonlocal pending
            if not pending:
                return
            if not pending["source_category"]:
                raise ValueError(
                    f"Missing Matsuno category on PDF page {physical_page}: "
                    f"{pending['item']}"
                )
            primary = category_code(pending["source_category"])
            pending["category"] = primary
            pending["category_options"] = category_options(pending["note"], primary)
            items.append(pending)
            pending = None

        for raw in tables[0]:
            if len(raw) < 3:
                raise ValueError(f"Malformed Matsuno table row on PDF page {physical_page}")
            name = _text(raw[0])
            source_category = _compact(raw[1])
            note = _text(raw[2])
            if _compact(name) == "品名" and source_category == "分類":
                headers += 1
                continue
            if name and not source_category and not note and len(_compact(name)) <= 2:
                finish()
                continue
            if name:
                finish()
                pending = {
                    "item": name,
                    "source_category": source_category,
                    "note": note,
                    "source_page": physical_page,
                }
                continue
            if not pending:
                if source_category or note:
                    raise ValueError(
                        f"Orphan Matsuno continuation on PDF page {physical_page}: {raw}"
                    )
                continue
            if source_category:
                if pending["source_category"] and pending["source_category"] != source_category:
                    raise ValueError(
                        f"Multiple Matsuno categories for {pending['item']}: "
                        f"{pending['source_category']} / {source_category}"
                    )
                pending["source_category"] = source_category
            if note:
                pending["note"] = " ".join(
                    part for part in (pending["note"], note) if part
                )
        finish()
    if headers != len(pages):
        raise ValueError(f"Matsuno table headers changed: {headers} / {len(pages)}")
    if len(items) < minimum_rows:
        raise ValueError(f"Too few Matsuno item records: {len(items)}")
    for number, item in enumerate(items, 1):
        item["item_id"] = f"matsuno-{number:04d}"
    return items


def extract_items(path: Path, *, minimum_rows: int = 1400):
    import pdfplumber

    with pdfplumber.open(path) as document:
        # Physical pages 22-63 are the reviewed alphabetical item table.
        return extract_items_from_pages(
            document.pages[21:63], start_page=22, minimum_rows=minimum_rows
        )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    print(json.dumps(extract_items(args.pdf), ensure_ascii=False, indent=2))
