"""Readers for the pinned Imabari PDFs; no network or model calls.

The mainland dictionary contains obsolete off-page artwork and overlapping
classification glyphs. Read only the printed table, and use the *rendered*
category background, rather than concatenating hidden/overprinted labels.
"""

from collections import Counter
from datetime import date
import calendar as cal
import re
import unicodedata


def compact(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))


def glyphs(page):
    result = {}
    for span in page.get_texttrace():
        if span["type"] == 3 or not span["opacity"]:
            continue
        for code, _, _, box in span["chars"]:
            if code >= 0:
                key = code, tuple(round(v * 2) for v in box)
                result[key] = chr(code), box
    return list(result.values())


def text_in(chars, rect):
    x0, y0, x1, y1 = rect
    selected = [
        (c, b)
        for c, b in chars
        if x0 <= (b[0] + b[2]) / 2 < x1 and y0 <= (b[1] + b[3]) / 2 < y1
    ]
    lines = []
    for c, b in sorted(selected, key=lambda v: ((v[1][1] + v[1][3]) / 2, v[1][0])):
        y = (b[1] + b[3]) / 2
        if not lines or y - lines[-1][0] > 3:
            lines.append((y, []))
        lines[-1][1].append((c, b))
    return "".join(
        "".join(c for c, _ in sorted(line, key=lambda v: v[1][0])) for _, line in lines
    ).strip()


def rgb_at(pix, x, y):
    return pix.pixel(
        round(x * pix.width / pix.irect.width), round(y * pix.height / pix.irect.height)
    )[:3]


# Colours are the visible legend, not the stale category text layer.
DICT_COLORS = {
    "burnable": (255, 242, 31),
    "non_burnable": (101, 180, 128),
    "plastics": (78, 185, 221),
    "resources": (244, 169, 0),
    "hazardous": (0, 0, 0),
    "dangerous": (230, 0, 18),
    "bulky": (219, 190, 219),
    "consult": (127, 195, 195),
    "not_collected": (233, 83, 142),
}


def mainland_dictionary(path):
    import pymupdf

    rows, counts = [], {}
    for pi, page in enumerate(pymupdf.open(path)):
        if pi == 0 or pi == 15:
            continue
        chars = glyphs(page)
        # Duplicate backgrounds exist; keep one rectangle per physical cell.
        rects = {
            tuple(round(v, 2) for v in d["rect"])
            for d in page.get_drawings()
            if d["fill"] is not None
            and 13 < d["rect"].width < 15
            and 20 < d["rect"].height < 50
            and (140 < d["rect"].x0 < 150 or 400 < d["rect"].x0 < 410)
            and 10 < d["rect"].y0 < 828
        }
        pix = page.get_pixmap(alpha=False)
        before = len(rows)
        for x0, y0, x1, y1 in sorted(rects, key=lambda r: (r[0], r[1])):
            color = pix.pixel(round(x0 + 2), round(y0 + 2))[:3]
            category = min(
                DICT_COLORS,
                key=lambda c: sum((a - b) ** 2 for a, b in zip(color, DICT_COLORS[c])),
            )
            if sum((a - b) ** 2 for a, b in zip(color, DICT_COLORS[category])) > 2000:
                raise ValueError(f"Unknown visible category colour p{pi+1}: {color}")
            item_left, note_right = (56, 306) if x0 < 200 else (317, 565)
            item = text_in(chars, (item_left, y0, x0, y1))
            note = text_in(chars, (x1, y0, note_right, y1))
            if not item:
                raise ValueError(f"Empty dictionary item p{pi+1}: {y0}")
            rows.append(
                dict(
                    item_id=f"im-m-{pi+1:02}-{len(rows)-before+1:03}",
                    item=item,
                    category=category,
                    note=note,
                    pdf_page=pi + 1,
                    rect=[item_left, y0, note_right, y1],
                    category_rect=[x0, y0, x1, y1],
                )
            )
        counts[str(pi + 1)] = len(rows) - before
    return rows, counts


SEKIZEN_CATEGORIES = {
    "燃えるごみ(可燃)": "burnable",
    "燃えないごみ(不燃)": "non_burnable",
    "資源物": "resources",
    "粗大ごみ": "bulky",
    "有害危険": "hazardous_dangerous",
    "―": "not_collected",
    "—": "not_collected",
    "-": "not_collected",
}


def sekizen_dictionary(path):
    import pymupdf

    rows, counts = [], {}
    for pi, page in enumerate(pymupdf.open(path)):
        table = page.find_tables().tables[0]
        chars = glyphs(page)
        before = len(rows)
        for row in table.rows:
            item = text_in(chars, row.cells[1]) if row.cells[1] else ""
            label = compact(text_in(chars, row.cells[2])) if row.cells[2] else ""
            if label in {"分別区分", ""}:
                continue
            if label not in SEKIZEN_CATEGORIES:
                raise ValueError(f"Unknown Sekizen category {label}")
            note = text_in(chars, row.cells[3]) if row.cells[3] else ""
            rows.append(
                dict(
                    item_id=f"im-s-{pi+1:02}-{len(rows)-before+1:03}",
                    item=item,
                    category=SEKIZEN_CATEGORIES[label],
                    note=note,
                    pdf_page=pi + 1,
                    rect=[
                        row.cells[1][0],
                        row.cells[1][1],
                        row.cells[3][2],
                        row.cells[1][3],
                    ],
                    category_rect=list(row.cells[2]),
                )
            )
        counts[str(pi + 1)] = len(rows) - before
    return rows, counts


def address_rows(path):
    """Keep every printed address qualifier; never guess a street boundary."""
    import pymupdf

    rows = []
    for pi, page in enumerate(pymupdf.open(path)):
        chars = glyphs(page)
        town = ""
        for row in page.find_tables().tables[0].rows[1:]:
            cells = [text_in(chars, r) if r else "" for r in row.cells]
            if cells[1]:
                town = cells[1]
            if not cells[5]:
                continue
            rows.append(
                dict(
                    town=town,
                    qualifiers=cells[2:5],
                    calendar_label=cells[5],
                    pdf_page=pi + 1,
                )
            )
    return rows


# Identical printed month grid on all 42 numbered PDFs (including scanned 41).
# Every date glyph is audited separately; this geometry does not generate a
# recurrence from the collection weekday legend.
MONTH_TOPS = [335.34, 555.27, 775.92, 996.27]
MONTH_LEFTS = [28.35, 291.97, 555.59]
CELL_WIDTH, CELL_HEIGHT = 257.95 / 7, 35.665


def month_cells(month):
    index = (month - 4) % 12
    x0, y0 = MONTH_LEFTS[index % 3], MONTH_TOPS[index // 3]
    year = 2026 if month >= 4 else 2027
    first = (date(year, month, 1).weekday() + 1) % 7
    for day in range(1, cal.monthrange(year, month)[1] + 1):
        pos = first + day - 1
        week, col = divmod(pos, 7)
        # Five-row months print overflow dates in the bottom cell, separated
        # by a slash (e.g. May 24/31). Both dates are individually audited.
        row = min(week, 4)
        rect = [
            x0 + col * CELL_WIDTH,
            y0 + row * CELL_HEIGHT,
            x0 + (col + 1) * CELL_WIDTH,
            y0 + (row + 1) * CELL_HEIGHT,
        ]
        yield date(year, month, day).isoformat(), rect, week == 5


MAIN_COLORS = {
    "burnable": (255, 241, 0),
    "non_burnable": (137, 201, 151),
    "plastics": (126, 206, 244),
    "resources": (241, 158, 194),
}
SEKIZEN_COLORS = {
    "burnable": (241, 158, 194),
    "non_burnable": (126, 206, 244),
    "plastics": (137, 201, 151),
    "resources": (146, 136, 185),
    "paper": (175, 175, 175),
    "hazardous_dangerous": (255, 241, 0),
    "bulky": (249, 190, 0),
}


def raster_streams(page, rect, sekizen=False, scale=3, pixels=None, scanned=False):
    """Read every colour wedge, including same-day multiple collections."""
    import numpy as np
    import pymupdf

    x0, y0, x1, y1 = rect
    # Exclude the bulky application band at the bottom of mainland cells.
    if pixels is None:
        clip = pymupdf.Rect(x0 + 3, y0 + 2, x1 - 3, y1 - 7)
        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False
        )
        a = (
            np.frombuffer(pix.samples, dtype=np.uint8)
            .reshape(pix.height, pix.width, pix.n)[:, :, :3]
            .astype(int)
        )
    else:
        a = pixels[
            round((y0 + 2) * scale) : round((y1 - 7) * scale),
            round((x0 + 3) * scale) : round((x1 - 3) * scale),
        ].astype(int)
    colors = dict(SEKIZEN_COLORS if sekizen else MAIN_COLORS)
    if scanned:
        # The scanned 岡村 legend uses different grey/orange inks.
        colors.update(paper=(145, 155, 155), bulky=(255, 185, 55))
    counts = {
        k: int((np.max(np.abs(a - np.array(rgb)), axis=2) < 20).sum())
        for k, rgb in colors.items()
    }
    # Grey antialiasing around black date numerals is not a paper wedge.
    # The smallest genuine grey sector exceeds 35 square PDF points.
    return (
        sorted(
            k
            for k, n in counts.items()
            if n > (35 if k == "paper" else 12) * scale * scale
        ),
        counts,
    )


def numbered_calendar(path, sekizen=False):
    import pymupdf
    import numpy as np

    page = pymupdf.open(path)[0]
    chars = glyphs(page)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=False)
    pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )[:, :, :3]
    result, cells = {}, []
    for month in [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]:
        for day, rect, overflow in month_cells(month):
            raw = text_in(chars, rect)
            d = date.fromisoformat(day)
            shared = (
                int(day[-2:]) + 7 <= cal.monthrange(d.year, month)[1]
                and (d.day + (date(d.year, month, 1).weekday() + 1) % 7 - 1) // 7 == 4
            ) or overflow
            stream_rect = list(rect)
            if shared:
                # E.g. Aug 24/31: a resource marker can belong only to 24.
                # Read each printed half separately, never copy it to 31.
                if overflow:
                    stream_rect[1] = (rect[1] + rect[3]) / 2
                else:
                    stream_rect[3] = (rect[1] + rect[3]) / 2
            streams, counts = raster_streams(
                page, stream_rect, sekizen, pixels=pixels, scanned=not chars
            )
            if chars:
                labels = {
                    "burnable": "可燃",
                    "non_burnable": "不燃",
                    "plastics": "プラ",
                    "resources": "缶" if sekizen else "資源",
                    "paper": "紙",
                    "hazardous_dangerous": "有害",
                    "bulky": "粗大",
                }
                for code in streams:
                    if labels[code] not in compact(raw):
                        raise ValueError(
                            f"Visible colour / printed label mismatch: {path.name} {day} {code}"
                        )
            result[day] = streams
            cells.append(
                dict(
                    date=day,
                    rect=rect,
                    stream_rect=stream_rect,
                    text=raw,
                    streams=streams,
                    pixels=counts,
                    overflow=overflow,
                    shared=shared,
                )
            )
    return dict(days=result, cells=cells, native_text=bool(chars))
