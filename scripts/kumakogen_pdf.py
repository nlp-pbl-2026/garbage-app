"""Readers for the pinned Kumakogen dictionary and FY2026 ruled timetable.

Geometry identifies cells; visible glyph traces identify text. Rendered pixels
and separately generated Apple Vision observations audit the interpretation.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import unicodedata

CATEGORY_CODES = {
    "燃える": "burnable",
    "燃えない": "non_burnable",
    "紙類": "paper",
    "ビン": "bottles",
    "カン": "cans",
    "ペット": "pet_bottles",
    "金属": "metals",
    "古着": "clothes",
    "プラ": "plastic_packaging",
    "蛍光灯": "fluorescent",
    "乾電池": "batteries",
    "廃食用油": "cooking_oil",
    "小型家電": "small_appliances",
    "粗大": "bulky",
    "禁止": "not_collected",
    "直接持込": "direct_delivery",
    "木のフローチャート参照": "consult",
}


def compact(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))


def spans(page):
    """Visible glyphs, excluding invisible text and duplicate bold painting."""
    result = {}
    for span in page.get_texttrace():
        if span["type"] == 3 or not span["opacity"]:
            continue
        for code, _, _, box in span["chars"]:
            if code < 0:
                continue
            result[(code, tuple(round(v, 3) for v in box))] = (chr(code), box)
    return list(result.values())


def in_rect(chars, rect):
    selected = [
        (c, b)
        for c, b in chars
        if rect[0] <= (b[0] + b[2]) / 2 < rect[2]
        and rect[1] <= (b[1] + b[3]) / 2 < rect[3]
    ]
    selected.sort(key=lambda x: (round((x[1][1] + x[1][3]) / 2, 1), x[1][0]))
    # Fonts may have slightly different baselines within one printed line.
    lines = []
    for char, box in selected:
        cy = (box[1] + box[3]) / 2
        if not lines or abs(cy - lines[-1][0]) > 3:
            lines.append((cy, [(char, box)]))
        else:
            lines[-1][1].append((char, box))
    return "".join(
        "".join(c for c, _ in sorted(line, key=lambda x: x[1][0])) for _, line in lines
    ).strip()


def dictionary_borders(drawings, left):
    """Include the offset final border, including tables extending below 805pt."""
    return sorted(
        {
            round(d["rect"].y0, 2)
            for d in drawings
            if d["color"]
            and d["rect"].height < 0.1
            and 110 < d["rect"].width < 115
            and abs(d["rect"].x0 - left) < 0.6
            and 54 < d["rect"].y0 < 811
        }
    )


def extract_items(path):
    import pymupdf

    doc = pymupdf.open(path)
    if len(doc) != 46:
        raise ValueError("Dictionary edition/page count changed")
    rows, counts = [], {}
    for pi in range(15, 45):
        page = doc[pi]
        chars, drawings = spans(page), page.get_drawings()
        headers = sorted(
            [
                d["rect"]
                for d in drawings
                if d["fill"]
                and 240 < d["rect"].width < 255
                and 38 < d["rect"].y0 < 42
                and 14 < d["rect"].height < 18
            ],
            key=lambda r: r.x0,
        )
        if len(headers) != 2:
            raise ValueError(f"Missing dictionary columns: p{pi+1}")
        before = len(rows)
        for side, header in enumerate(headers, 1):
            left = header.x0
            c0, c1, right = left + 113.38, left + 160.44, header.x1
            ys = dictionary_borders(drawings, left)
            if len(ys) < 25:
                raise ValueError(f"Missing ruled rows: p{pi+1}/{side}")
            for ri, (top, bottom) in enumerate(zip(ys, ys[1:]), 1):
                item = in_rect(chars, (left, top, c0, bottom))
                label = compact(in_rect(chars, (c0, top, c1, bottom)))
                note = in_rect(chars, (c1, top, right, bottom))
                if not item and re.fullmatch(r"[ぁ-ん]", label):
                    continue
                # Green kana section headers and deliberately blank cells.
                if not label:
                    if item and len(compact(item)) > 1:
                        raise ValueError(f"Unclassified item: p{pi+1} {item}")
                    continue
                label = label.replace("×", "")
                if label == "持直接持込":
                    label = "直接持込"
                if label.startswith("木のフロ"):
                    note = in_rect(chars, (c0, top, right, bottom))
                    label = "木のフローチャート参照"
                if label not in CATEGORY_CODES:
                    raise ValueError(
                        f"Unknown dictionary class: p{pi+1} {item}: {label}"
                    )
                if not item:
                    raise ValueError(f"Class without item p{pi+1}")
                rows.append(
                    {
                        "item_id": f"kk-p{pi+1:02}-{side}-{ri:02}",
                        "item": item,
                        "category": CATEGORY_CODES[label],
                        "note": note,
                        "source_category": label,
                        "pdf_page": pi + 1,
                        "rect": [round(left, 3), top, round(right, 3), bottom],
                        "category_rect": [round(c0, 3), top, round(c1, 3), bottom],
                    }
                )
        page_rows = rows[before:]
        symbol_counts = Counter()
        for drawing in drawings:
            box = drawing["rect"]
            fill = drawing["fill"]
            if not (
                fill
                and min(fill) < 0.95
                and abs(box.width - 14.173) < 0.1
                and 13.4 < box.height < 14.3
                and 55 < box.y0 < 811
            ):
                continue
            if not any(
                abs(box.x0 - (header.x0 + 113.38) - 5.65) < 1 for header in headers
            ):
                continue
            matching = [
                row
                for row in page_rows
                if row["category_rect"][0]
                < (box.x0 + box.x1) / 2
                < row["category_rect"][2]
                and row["rect"][1] < (box.y0 + box.y1) / 2 < row["rect"][3]
            ]
            if len(matching) != 1:
                raise ValueError(
                    f"Painted category icon without extracted row p{pi+1}: {box}"
                )
            symbol_counts[matching[0]["item_id"]] += 1
        if any(
            symbol_counts[row["item_id"]] != (0 if row["category"] == "consult" else 1)
            for row in page_rows
        ):
            raise ValueError(f"Dictionary row/icon count mismatch p{pi+1}")
        counts[str(pi + 1)] = len(rows) - before
    return rows, counts


def month_date(value, month):
    """A June column may explicitly say July 2; never discard its month."""
    value = compact(value)
    m = re.fullmatch(r"(?:(\d{1,2})月)?(\d{1,2})(?:日)?", value)
    if not m:
        raise ValueError(f"Invalid printed date: {value!r}")
    actual_month = int(m[1]) if m[1] else month
    result = date(2026 if actual_month >= 4 else 2027, actual_month, int(m[2]))
    if not date(2026, 4, 1) <= result <= date(2027, 3, 31):
        raise ValueError("Printed date outside FY2026")
    return result.isoformat()


def timetable(path):
    import pymupdf
    import numpy as np

    doc = pymupdf.open(path)
    if len(doc) != 5:
        raise ValueError("Timetable edition changed")
    result, audit = [], []
    for pi in range(4):
        page = doc[pi]
        chars = spans(page)
        if "令和8年度" not in compact(page.get_text()):
            raise ValueError("FY2026 header missing")
        tables = sorted(
            [t for t in page.find_tables().tables if t.col_count == 13],
            key=lambda t: t.bbox[1],
        )
        expected = 2 if pi in (0, 2, 3) else 3
        if len(tables) != expected:
            raise ValueError(f"Timetable tables missing p{pi+1}")
        if pi == 3:
            # The small grey Yanadani table is made from filled rectangles,
            # rather than stroked rules; find_tables does not see its cells.
            # Coordinates are reviewed against the pinned PDF's painted rules.
            from types import SimpleNamespace

            xs = [33.84] + [126.41 + 28.34 * i for i in range(13)]
            ys = [287.116, 322.9, 354.94, 386.74]
            grey = SimpleNamespace(
                rows=[
                    SimpleNamespace(
                        cells=[(xs[c], ys[r], xs[c + 1], ys[r + 1]) for c in range(13)]
                    )
                    for r in range(3)
                ]
            )
            tables.insert(0, grey)
        pixel = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=False)
        image = np.frombuffer(pixel.samples, np.uint8).reshape(
            pixel.height, pixel.width, 3
        )
        page_result, checks = {}, []
        for ti, table in enumerate(tables):
            kind = (
                ["all_resources", "plastic_cans"]
                if pi not in (1, 3)
                else ["non_burnable", "all_resources", "plastic_cans"]
            )[ti]
            data_rows = []
            for ri, row in enumerate(table.rows[1:]):
                label = in_rect(chars, row.cells[0])
                dates = []
                for mi, rect in enumerate(row.cells[1:]):
                    if rect is None:
                        raise ValueError("Merged date cells require explicit review")
                    value = in_rect(chars, rect)
                    day = month_date(value, (mi + 3) % 12 + 1)
                    dates.append(day)
                    # Alternating date cell fills + header define the stream;
                    # compare the vector cell header with rendered colour.
                    checks.append(
                        {
                            "kind": kind,
                            "row": ri,
                            "column_month": (mi + 3) % 12 + 1,
                            "printed": compact(value),
                            "date": day,
                            "rect": list(rect),
                        }
                    )
                if len(set(dates)) != 12:
                    raise ValueError("Duplicate monthly date")
                data_rows.append({"label": label, "dates": dates})
            header = table.rows[0].cells[1]
            x, y = int((header[0] + header[2]) / 2 * 3), int((header[1] + 2) * 3)
            rgb = image[y, x].astype(int).tolist()
            if kind == "all_resources" and not (
                rgb[1] > 180 and rgb[0] < 70 and rgb[2] < 70
            ):
                raise ValueError("Green resource header not rendered")
            if kind == "plastic_cans" and not (rgb[2] > 150 and rgb[0] < 70):
                raise ValueError("Blue plastic/cans header not rendered")
            page_result[kind] = data_rows
        result.append(page_result)
        audit.append(
            {"page": pi + 1, "monthly_date_cells": len(checks), "cells": checks}
        )
    return result, audit


def ics_events(path):
    """Strict subset of public Google iCalendar: all-day events only."""
    text = re.sub(r"\r?\n[ \t]", "", Path(path).read_text())
    events = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        fields = {}
        for line in block.split("END:VEVENT")[0].splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields.setdefault(key.split(";")[0], []).append(value)
        if "DTSTART" not in fields or len(fields["DTSTART"][0]) != 8:
            raise ValueError("Unsupported non-all-day event")
        events.append(fields)
    return events


def expand_ics(path):
    """Independent public-calendar check, bounded to FY2026 and respecting overrides."""
    from dateutil.rrule import rrulestr

    events = ics_events(path)
    start, end = datetime(2026, 4, 1), datetime(2027, 3, 31)
    overrides = {
        (e["UID"][0], e["RECURRENCE-ID"][0]): e for e in events if "RECURRENCE-ID" in e
    }
    names = {
        "可燃ごみ（燃えるごみ）": "burnable",
        "不燃ごみ（燃えないごみ）": "non_burnable",
        "燃えないごみ": "non_burnable",
        "資源ごみ（すべて）": "all_resources",
        "プラカンのみ": "plastic_cans",
        "資源ごみ（プラスチック・カンのみ）": "plastic_cans",
    }
    result = {key: set() for key in names.values()}
    for event in events:
        if "RECURRENCE-ID" in event:
            continue
        if event.get("STATUS") == ["CANCELLED"]:
            continue
        summary = event.get("SUMMARY", [""])[0]
        if summary not in names:
            raise ValueError(f"Unknown calendar summary {summary}")
        day = datetime.strptime(event["DTSTART"][0], "%Y%m%d")
        dates = (
            rrulestr(event["RRULE"][0], dtstart=day).between(start, end, inc=True)
            if "RRULE" in event
            else [day]
        )
        excluded = {v for field in event.get("EXDATE", []) for v in field.split(",")}
        for occurrence in dates:
            raw = occurrence.strftime("%Y%m%d")
            override = overrides.get((event["UID"][0], raw))
            if override:
                if override.get("STATUS") == ["CANCELLED"]:
                    continue
                occurrence = datetime.strptime(override["DTSTART"][0], "%Y%m%d")
            elif raw in excluded:
                continue
            if start <= occurrence <= end:
                result[names[summary]].add(occurrence.date().isoformat())
        # A recurrence immediately outside FY2026 can be moved into the period.
        for (uid, _), override in overrides.items():
            if uid != event["UID"][0] or override.get("STATUS") == ["CANCELLED"]:
                continue
            moved = datetime.strptime(override["DTSTART"][0], "%Y%m%d")
            if start <= moved <= end:
                result[names[summary]].add(moved.date().isoformat())
    return {key: sorted(value) for key, value in result.items()}
