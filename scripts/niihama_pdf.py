"""Offline Niihama PDF readers: ruled rows, printed dates, symbols and raster audit."""

from __future__ import annotations
import calendar
from collections import Counter
from datetime import date
from pathlib import Path
import re
import unicodedata

CATEGORY_CODES = {
    "燃やすごみ": "burnable",
    "不燃ごみ": "non_burnable",
    "布類": "textiles",
    "プラ製容器包装": "plastic_packaging",
    "びん・缶": "bottles_cans",
    "ペットボトル": "pet_bottles",
    "古紙類": "paper",
    "有害ごみ": "hazardous",
    "大型ごみ": "bulky",
    "自己搬入": "self_delivery",
    "収集しない": "not_collected",
}
COLORS = {
    "burnable": (0.945, 0.620, 0.761),
    "non_burnable": (1, 0.944, 0),
    "textiles": (0.780, 0.819, 0.920),
    "plastic_packaging": (0.622, 0.849, 0.967),
    "bottles_cans": (0.843, 0.908, 0.685),
    "pet_bottles": (0.971, 0.723, 0.426),
    "paper": (0.132, 0.673, 0.221),
    "hazardous": (0.864, 0.866, 0.868),
}
SYMBOLS = {
    "燃": "burnable",
    "不燃": "non_burnable",
    "布類": "textiles",
    "プ容": "plastic_packaging",
    "びん缶": "bottles_cans",
    "ぺ": "pet_bottles",
    "ペ": "pet_bottles",
    "紙": "paper",
    "有害": "hazardous",
}


def compact(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def page_lines(page):
    return [
        line
        for block in page.get_text("rawdict")["blocks"]
        for line in block.get("lines", [])
    ]


def cell_text(lines, rect):
    return "".join(
        "".join(
            c["c"]
            for s in line["spans"]
            for c in s["chars"]
            if rect.x0 <= (c["bbox"][0] + c["bbox"][2]) / 2 < rect.x1
            and rect.y0 <= (c["bbox"][1] + c["bbox"][3]) / 2 < rect.y1
        )
        for line in lines
    ).strip()


def extract_items(path: Path):
    import pymupdf
    import numpy as np

    doc = pymupdf.open(path)
    if len(doc) != 21:
        raise ValueError("Dictionary edition/layout changed")
    rows = []
    counts = {}
    palette = {}
    for pi in range(20):
        p = doc[pi]
        lines = page_lines(p)
        offset = -11.28 if pi % 2 else 0
        pix = p.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        rgb = np.frombuffer(pix.samples, np.uint8).reshape(
            pix.height, pix.width, pix.n
        )[:, :, :3]
        page_rows = []
        text_counts = Counter()
        for base, c0, c1, right in [
            (64.93, 147.54, 201.54, 303.09),
            (321.51, 404.10, 458.10, 559.66),
        ]:
            left, c0, c1, right = [x + offset for x in (base, c0, c1, right)]
            ys = []
            for d in p.get_drawings():
                for cmd in d["items"]:
                    if cmd[0] == "l":
                        a, b = cmd[1:]
                        x0, x1 = sorted([a.x, b.x])
                        if (
                            abs(a.y - b.y) < 0.1
                            and x0 < left + 0.2
                            and x1 >= c0 - 1
                            and 90 < a.y < 830
                        ):
                            ys.append(round(a.y, 2))
            ys = sorted(set(ys))
            ys = [v for i, v in enumerate(ys) if i == 0 or v - ys[i - 1] > 0.5]
            if len(ys) < 25:
                raise ValueError("Dictionary row borders missing")
            # An independent text-layer count does not depend on these row boundaries.
            for line in lines:
                label = cell_text([line], pymupdf.Rect(c0, 103, c1, 823))
                if label:
                    text_counts[label] += 1
            for rownum, (top, bottom) in enumerate(zip(ys, ys[1:]), 1):
                item = cell_text(lines, pymupdf.Rect(left, top, c0, bottom))
                label = cell_text(lines, pymupdf.Rect(c0, top, c1, bottom))
                note = cell_text(lines, pymupdf.Rect(c1, top, right, bottom))
                original = label
                if label not in CATEGORY_CODES:
                    combined = label + note
                    if combined != "廃棄物対策課に相談ください":
                        raise ValueError(
                            f"Unknown dictionary category: {pi+27} {item} {combined}"
                        )
                    category = "consultation"
                    note = combined
                else:
                    category = CATEGORY_CODES[label]
                if not item:
                    raise ValueError("Empty dictionary item")
                # Mode of the whole colour strip, independent of the text. The two
                # consultation rows have no filled classification cell and remain distinct.
                patch = rgb[
                    round((top + 2) * 2) : round((bottom - 2) * 2),
                    round((c0 + 2) * 2) : round((c0 + 4) * 2),
                ]
                color = tuple(np.median(patch.reshape(-1, 3), axis=0).astype(int))
                if category != "consultation":
                    if (
                        label in palette
                        and max(
                            abs(int(a) - int(b)) for a, b in zip(color, palette[label])
                        )
                        > 3
                    ):
                        raise ValueError(
                            f"Dictionary text/raster category mismatch: {pi+27} {item}"
                        )
                    palette.setdefault(label, color)
                page_rows.append(
                    {
                        "item_id": f"nh-p{pi+27:02}-{int(base>300)+1}-{rownum:02}",
                        "item": item,
                        "category": category,
                        "source_category": original,
                        "source_note": note,
                        "source_page": pi + 27,
                        "pdf_page": pi + 1,
                        "rect": [round(left, 2), top, round(right, 2), bottom],
                    }
                )
        if Counter(r["source_category"] for r in page_rows) != text_counts:
            raise ValueError("Dictionary row/text count mismatch")
        counts[str(pi + 27)] = len(page_rows)
        rows.extend(page_rows)
    if len(rows) != 1349 or set(palette) != set(CATEGORY_CODES):
        raise ValueError("Dictionary count/categories changed")
    return rows, counts


def color_code(color):
    distances = {
        code: max(abs(float(a) - b) for a, b in zip(color, rgb))
        for code, rgb in COLORS.items()
    }
    code = min(distances, key=distances.get)
    return code if distances[code] < 0.005 else None


def star_types(profile, color):
    if color == "paper" and profile in ("oshima", "besshiyama"):
        return {"bottles_cans", "pet_bottles", "paper"}
    if color == "non_burnable" and profile == "oshima":
        return {"non_burnable", "textiles"}
    raise ValueError("Unreviewed star/colour/profile combination")


def observed_types(symbol, profile, color):
    if symbol == "※":
        return star_types(profile, color)
    if symbol in ("", "休", "●", "/"):
        return set()
    if symbol not in SYMBOLS:
        raise ValueError(f"Unknown calendar symbol: {symbol!r}")
    return {SYMBOLS[symbol]}


def calendar_days(path: Path, profile):
    import pymupdf
    import numpy as np

    p = pymupdf.open(path)[0]
    if len(p.parent) != 1 or "令和８年度" not in p.get_text():
        raise ValueError("Calendar year/layout changed")
    lines = page_lines(p)
    headers = []
    for word in p.get_text("words"):
        match = re.fullmatch(r"(?:令和9年)?(\d{1,2})月", compact(word[4]))
        if match:
            headers.append((int(match[1]), word))
    if len(headers) != 12 or {m for m, w in headers} != set(range(1, 13)):
        raise ValueError("Month headers missing")
    drawings = p.get_drawings()
    rectangles = []
    for d in drawings:
        if d["fill"]:
            code = color_code(d["fill"])
            if code:
                rectangles.extend(
                    (c[1], code)
                    for c in d["items"]
                    if c[0] == "re" and 30 < c[1].width < 33 and c[1].y0 > 170
                )
    pix = p.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[
        :, :, :3
    ]
    palette = {
        code: np.round(np.array(value) * 255).astype(int)
        for code, value in COLORS.items()
    }
    result = {}
    audit = {
        "printed_dates": 0,
        "raster_dates": 0,
        "shared_sunday_dates": [],
        "closed_dates": [],
        "facility_only_dates": [],
        "simultaneous_dates": 0,
        "collection_counts": Counter(),
    }
    for month, header in headers:
        year = 2026 if month >= 4 else 2027
        col = (month - 4) % 3
        x0 = 29.347 + 232.44 * col
        y0 = header[1] + 44.246
        physical_rows = 6 if month in (7, 8, 9) else 5
        for row in range(physical_rows):
            for weekday in range(7):
                cell = pymupdf.Rect(
                    x0 + weekday * 31.181,
                    y0 + row * 36.85,
                    x0 + (weekday + 1) * 31.181,
                    y0 + (row + 1) * 36.85,
                )
                dayband = cell_text(
                    lines, pymupdf.Rect(cell.x0, cell.y0, cell.x1, cell.y0 + 18.425)
                )
                daytext = compact(dayband).replace("○", "").replace("〇", "")
                if not re.fullmatch(r"\d{1,2}(?:/\d{1,2})?", daytext):
                    continue  # explicit blank cells/printed notes
                printed = list(map(int, daytext.split("/")))
                for day in printed:
                    dt = date(year, month, day)
                    if (dt.weekday() + 1) % 7 != weekday:
                        raise ValueError("Printed date/weekday mismatch")
                    logical = ((date(year, month, 1).weekday() + 1) % 7 + day - 1) // 7
                    if logical != row and not (
                        logical == 5 and row == 4 and weekday == 0 and len(printed) == 2
                    ):
                        raise ValueError("Unexpected shared or misplaced date cell")
                symbol = (
                    compact(
                        cell_text(
                            lines,
                            pymupdf.Rect(cell.x0, cell.y0 + 18.425, cell.x1, cell.y1),
                        )
                    )
                    .replace("○", "")
                    .replace("〇", "")
                )
                center = pymupdf.Point(cell.x0 + 4, cell.y0 + 25)
                colors = {code for rect, code in rectangles if rect.contains(center)}
                if len(colors) > 1:
                    raise ValueError("Overlapping calendar colours")
                vector = next(iter(colors), None)
                codes = observed_types(symbol, profile, vector)
                patch = rgb[
                    round((cell.y0 + 2) * 2) : round((cell.y1 - 2) * 2),
                    round((cell.x0 + 2) * 2) : round((cell.x1 - 2) * 2),
                ].astype(int)
                visible = {
                    code
                    for code, color in palette.items()
                    if np.mean(np.max(abs(patch - color), axis=-1) <= 4) > 0.35
                }
                if len(visible) > 1:
                    raise ValueError("Ambiguous raster colour")
                raster_code = next(iter(visible), None)
                raster = (
                    star_types(profile, raster_code)
                    if symbol == "※"
                    else {raster_code} if raster_code else set()
                )
                if codes != raster:
                    raise ValueError(
                        f"Calendar text/raster mismatch: {path.name} {month}/{printed}: {symbol} {codes} {raster}"
                    )
                for day in printed:
                    key = date(year, month, day).isoformat()
                    if key in result:
                        raise ValueError("Duplicate calendar date")
                    result[key] = sorted(codes)
                    audit["printed_dates"] += 1
                    audit["raster_dates"] += 1
                    if len(printed) > 1:
                        audit["shared_sunday_dates"].append(key)
                    if symbol == "休":
                        audit["closed_dates"].append(key)
                    if symbol in ("●", "/"):
                        audit["facility_only_dates"].append(key)
                    if len(codes) > 1:
                        audit["simultaneous_dates"] += 1
                    audit["collection_counts"].update(codes)
    if len(result) != 365:
        raise ValueError(f"Incomplete year: {path.name}: {len(result)}")
    for field in ("shared_sunday_dates", "closed_dates", "facility_only_dates"):
        audit[field].sort()
    audit["collection_counts"] = dict(sorted(audit["collection_counts"].items()))
    return dict(sorted(result.items())), audit
