"""Read Uwajima's ruled dictionary and coloured, raster-only FY2026 calendars.

The calendar reader uses the printed cell positions and icon palette, not weekday
recurrences. The independent HTML/weekday and rendered OCR checks live in the
data/audit commands. A shared sixth-week cell is split into its printed halves.
"""

from __future__ import annotations

import calendar
from collections import Counter
from datetime import date
import hashlib
import re

import numpy as np
import pymupdf

CATEGORIES = {
    "可燃": "burnable",
    "不燃": "non_burnable",
    "粗大": "bulky",
    "古紙": "paper",
    "禁止": "not_collected",
    "びん・缶": "bottles_cans",
    "資源": "dropoff",
    "ペット": "pet",
}
PALETTE = {
    "burnable": (246, 140, 40),
    "non_burnable": (0, 104, 179),
    "bottles_cans": (152, 64, 67),
    "pet": (91, 170, 74),
    "paper": (159, 120, 180),
}


def compact(text):
    return re.sub(r"\s+", "", text or "")


def cell_text(page, rect):
    """Order visible glyphs by baseline then x; preserve displaced long vowels.

    MuPDF's table text places small/rotated glyphs (ー、) after the whole line.
    The PDF trace gives their actual printed position and visibility.
    """
    if rect is None:
        return ""
    selected = {}
    for span in page.get_texttrace():
        if span["type"] == 3 or not span["opacity"]:
            continue
        for code, _, origin, box in span["chars"]:
            if (
                code >= 0
                and rect[0] < (box[0] + box[2]) / 2 < rect[2]
                and rect[1] < (box[1] + box[3]) / 2 < rect[3]
            ):
                selected[(code, tuple(round(v * 2) for v in box))] = (chr(code), box)
    lines = []
    for char, box in sorted(
        selected.values(), key=lambda v: ((v[1][1] + v[1][3]) / 2, v[1][0])
    ):
        y = (box[1] + box[3]) / 2
        if not lines or y - lines[-1][0] > 3:
            lines.append((y, []))
        lines[-1][1].append((char, box))
    return "".join(
        "".join(c for c, b in sorted(line, key=lambda v: v[1][0])) for _, line in lines
    ).strip()


def dictionary(path):
    rows, pages = [], []
    for page_index, page in enumerate(pymupdf.open(path)):
        if page_index == 0:
            continue
        tables = page.find_tables().tables
        if len(tables) != 1:
            raise ValueError(f"Dictionary table changed: page {page_index + 1}")
        count = 0
        for row in tables[0].rows:
            item, category, note = [cell_text(page, rect) for rect in row.cells]
            if not category or compact(category) == "分類":
                continue  # kana section heading or the repeated column header
            code = CATEGORIES[compact(category)]
            if not item or "�" in item + (note or ""):
                raise ValueError("Missing/invalid dictionary item")
            count += 1
            rows.append(
                dict(
                    item_id=f"38203-{len(rows)+1:04d}",
                    item=re.sub(r"\s+", "", item),
                    category=code,
                    note=re.sub(r"\s+", "", note or ""),
                    pdf_page=page_index + 1,
                    rect=list(row.cells[0]),
                    category_rect=list(row.cells[1]),
                )
            )
        pages.append(dict(page=page_index + 1, rows=count))
    if len(rows) != 1124:
        raise ValueError(f"Official dictionary count changed: {len(rows)}")
    return rows, pages


def month_box(index):
    # PDF points (A3 portrait): same ruled five-row template in all 33 images.
    column, row = index % 3, index // 3
    left = [30.0, 296.0, 562.0][column]
    top = [114.5, 315.0, 707.5, 908.0][row]
    return left, top, left + 250.0, top + 154.5


def calendar_image(path, *, include_cells=False):
    document = pymupdf.open(path)
    if len(document) != 1 or not 840 < document[0].rect.width < 844:
        raise ValueError("Unknown calendar page geometry")
    pix = document[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, 3
    )
    result, cells = {}, []
    for index in range(12):
        month = (index + 3) % 12 + 1
        year = 2026 if month >= 4 else 2027
        left, top, right, bottom = month_box(index)
        first = (date(year, month, 1).weekday() + 1) % 7
        last = calendar.monthrange(year, month)[1]
        for day in range(1, last + 1):
            row, column = divmod(first + day - 1, 7)
            shared = row == 5 or (row == 4 and day + 7 <= last)
            y0 = top + min(row, 4) * (bottom - top) / 5
            y1 = y0 + (bottom - top) / 5
            x0 = left + column * (right - left) / 7
            x1 = x0 + (right - left) / 7
            crop = pixels[
                round(y0 * 2) + 1 : round(y1 * 2) - 1,
                round(x0 * 2) + 1 : round(x1 * 2) - 1,
            ].astype(np.int16)
            codes, scores = [], {}
            for code, rgb in PALETTE.items():
                hits = np.max(np.abs(crop - np.array(rgb)), axis=2) < 4
                if shared:
                    yy, xx = np.indices(hits.shape)
                    upper = (xx + 0.5) / hits.shape[1] + (yy + 0.5) / hits.shape[0] < 1
                    hits &= ~upper if row == 5 else upper
                score = int(hits.sum())
                scores[code] = score
                if score >= (4 if shared else 8):
                    codes.append(code)
            iso = date(year, month, day).isoformat()
            if codes:
                result[iso] = sorted(codes)
            cells.append(
                dict(
                    date=iso,
                    box=[x0, y0, x1, y1],
                    scores=scores,
                    categories=sorted(codes),
                    shared=shared,
                )
            )
    review = dict(
        cells=len(cells),
        events=sum(map(len, result.values())),
        categories=dict(Counter(c for cs in result.values() for c in cs)),
        days_sha256=hashlib.sha256(str(sorted(result.items())).encode()).hexdigest(),
    )
    return (result, review, cells) if include_cells else (result, review)
