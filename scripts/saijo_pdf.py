"""Geometry readers for the pinned Saijo guide and FY2026 calendars.

White layout text is deliberately excluded. Calendar dates come from printed
numbers, never from expanding the weekday legend into assumed collection days.
"""

from datetime import date
import re
import unicodedata


def compact(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def visible(page):
    result = {}
    for span in page.get_texttrace():
        if span["type"] != 0 or not span["opacity"] or min(span["color"]) > 0.95:
            continue
        for code, _, _, box in span["chars"]:
            if code >= 0:
                result[(code, tuple(round(v, 3) for v in box))] = (chr(code), box)
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


def cluster(values, tolerance=1):
    groups = []
    for value in sorted(set(values)):
        if not groups or value - groups[-1][-1] > tolerance:
            groups.append([])
        groups[-1].append(value)
    return [sum(g) / len(g) for g in groups]


CATEGORIES = {
    "もえる": "burnable",
    "もえる(天ぷら油)": "burnable",
    "もえない": "non_burnable",
    "粗大": "bulky",
    "収集しない": "not_collected",
    "拠点回収": "drop_off",
    "資源(びん)": "bottles",
    "資源(古紙)": "paper",
    "資源(PET)": "pet_bottles",
    "資源(スプレー缶)": "spray_cans",
    "乾電池": "dry_batteries",
}
CATEGORIES.update(
    {
        "スプレー缶": "spray_cans",
        "小型家電": "small_appliances",
        "資源(ペット)(拠点回収)": "pet_bottles",
    }
)


def dictionary(path):
    import pymupdf

    doc = pymupdf.open(path)
    rows, counts = [], {}
    for pi, page in enumerate(doc):
        chars = visible(page)
        # The category column is narrower on left-hand pages. Use its actual
        # horizontal cell borders, including the last row above the footnotes.
        centers = [
            (s["bbox"][0] + s["bbox"][2]) / 2
            for b in page.get_text("dict")["blocks"]
            for l in b.get("lines", [])
            for s in l["spans"]
            if compact(s["text"]) in CATEGORIES and 150 < s["bbox"][0] < 290
        ]
        center = sorted(centers)[len(centers) // 2]
        lines = [
            d["rect"]
            for d in page.get_drawings()
            if d["type"] == "s"
            and d["rect"].height < 0.05
            and 35 < d["rect"].width < 95
            and d["rect"].x0 < center < d["rect"].x1
            and 20 < d["rect"].y0 < 789
        ]
        if len(lines) < 10:
            raise ValueError(f"Missing dictionary borders: page {pi+1}")
        left = sum(r.x0 for r in lines) / len(lines)
        right = sum(r.x1 for r in lines) / len(lines)
        ticket_lines = [
            d["rect"].x0
            for d in page.get_drawings()
            if d["type"] == "s"
            and d["rect"].height < 0.05
            and 40 < d["rect"].width < 56
            and 480 < d["rect"].x0 < 500
        ]
        ticket_left = sum(ticket_lines) / len(ticket_lines)
        ys = cluster([r.y0 for r in lines])
        before = len(rows)
        for y0, y1 in zip(ys, ys[1:]):
            label = compact(text_in(chars, (left, y0, right, y1)))
            label = re.sub(r"\(※\d\)", "", label)
            label = label.replace("(小型家電)", "")
            if not label or label == "分別区分":
                continue
            if label not in CATEGORIES:
                raise ValueError(f"Unknown dictionary category p{pi+1}: {label!r}")
            item = text_in(chars, (48, y0, left, y1))
            note = text_in(chars, (right, y0, ticket_left, y1))
            tickets = text_in(chars, (ticket_left, y0, 550, y1))
            if not item:
                raise ValueError("Empty item")
            rows.append(
                dict(
                    item_id=f"sj-{pi+13:02}-{len(rows)-before+1:03}",
                    item=item,
                    category=CATEGORIES[label],
                    source_category=label,
                    note=note,
                    tickets=tickets,
                    pdf_page=pi + 1,
                    category_rect=[left, y0, right, y1],
                    rect=[48, y0, 550, y1],
                )
            )
        counts[str(pi + 1)] = len(rows) - before
        # Independent reverse scan: every visible primary category label must
        # belong to exactly one extracted row (prevents missing bottom rows).
        labels = 0
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    x0, y0, x1, y1 = span["bbox"]
                    value = compact(span["text"])
                    value = re.sub(r"\(※\d\)", "", value).replace("(小型家電)", "")
                    if (
                        left <= (x0 + x1) / 2 < right
                        and 20 < y0 < 785
                        and value in CATEGORIES
                    ):
                        labels += 1
        # PDF text spans can join a classification to its adjacent note.
        # The separate raster/OCR audit checks every extracted category cell.
        if labels > counts[str(pi + 1)]:
            raise ValueError(f"Unassigned category spans p{pi+1}")
    return rows, counts


COLORS = {
    "burnable": (0.2, 0.8, 0.2),
    "non_burnable": (1, 0.4, 0),
    "paper": (0.816, 0.808, 0.808),
    "resources": (0.608, 0.757, 0.898),
}


def color_code(fill):
    if fill is None:
        return None
    for name, rgb in COLORS.items():
        if max(abs(a - b) for a, b in zip(fill, rgb)) < 0.035:
            return name
    return None


def calendar(path, missing_dates=None):
    import pymupdf

    page = pymupdf.open(path)[0]
    chars, drawings = visible(page), page.get_drawings()
    number_spans = [
        s
        for b in page.get_text("dict")["blocks"]
        for l in b.get("lines", [])
        for s in l["spans"]
        if s["color"] != 16777215
        and re.fullmatch(r"\d{1,2}(?:/\d{1,2})?", compact(s["text"]))
    ]
    headers = sorted(
        [
            d["rect"]
            for d in drawings
            if d["fill"]
            and abs(d["fill"][0] - 0.753) < 0.01
            and 180 < d["rect"].width < 240
            and 10 < d["rect"].height < 15
        ],
        key=lambda r: (round(r.y0), r.x0),
    )
    if len(headers) != 12 or "令和8年度" not in compact(
        text_in(chars, (0, 0, 842, 110))
    ):
        raise ValueError("Unexpected calendar edition or month headers")
    days, cells, months = {}, [], []
    for mi, header in enumerate(headers):
        month = (mi + 3) % 12 + 1
        year = 2026 if month >= 4 else 2027
        # A clipped gray header in the August A之谷 table omits Saturday.
        # The seven printed weekday centers determine the full table width.
        weekdays = [
            (c, b)
            for c, b in chars
            if c in "日月火水木金土"
            and header.y0 < (b[1] + b[3]) / 2 < header.y1
            and header.x0 - 1 < (b[0] + b[2]) / 2 < header.x0 + 240
        ]
        weekdays.sort(key=lambda v: v[1][0])
        if "".join(c for c, _ in weekdays) != "日月火水木金土":
            raise ValueError(f"Weekday header missing: {path} month{month}")
        centers = [(b[0] + b[2]) / 2 for _, b in weekdays]
        width = (centers[-1] - centers[0]) / 6
        x0 = centers[0] - width / 2
        # Some borders consist of seven separate black rectangles. Require
        # their combined horizontal coverage, rather than assuming one path.
        segments = [
            d["rect"]
            for d in drawings
            if d["fill"] == (0, 0, 0)
            and d["rect"].width > 20
            and d["rect"].height < 1.5
            and header.y1 - 1 < d["rect"].y0 < header.y1 + 225
            and d["rect"].x1 > x0
            and d["rect"].x0 < x0 + 7 * width
        ]
        ys = []
        for y in cluster([(r.y0 + r.y1) / 2 for r in segments]):
            coverage = sum(
                max(0, min(r.x1, x0 + 7 * width) - max(r.x0, x0))
                for r in segments
                if abs((r.y0 + r.y1) / 2 - y) < 1
            )
            if coverage > 6.5 * width:
                ys.append(y)
        ys = ys[:6]
        if len(ys) != 6:
            raise ValueError(f"Five printed week rows missing: {path} month{month}")
        found = []
        for ri, (top, bottom) in enumerate(zip(ys, ys[1:])):
            for ci in range(7):
                rect = [
                    x0 + ci * width + 0.6,
                    top + 0.6,
                    x0 + (ci + 1) * width - 0.6,
                    bottom - 0.6,
                ]
                text = compact(text_in(chars, rect))
                numbers = []
                glyphs = []
                for span in number_spans:
                    b = span["bbox"]
                    value = compact(span["text"])
                    if (
                        rect[0] < (b[0] + b[2]) / 2 < rect[2]
                        and rect[1] < (b[1] + b[3]) / 2 < rect[3]
                    ):
                        numbers.extend(int(v) for v in value.split("/"))
                        glyphs.append(dict(text=value, rect=list(b)))
                numbers = sorted(set(numbers))
                printed_numbers = list(numbers)
                replacement = (missing_dates or {}).get(f"{month}-{ri}-{ci}")
                if isinstance(replacement, dict):
                    if numbers != replacement["printed"]:
                        raise ValueError("Date-label review no longer matches source")
                    numbers = replacement["dates"]
                if not numbers:
                    replacement = (missing_dates or {}).get(f"{month}-{ri}-{ci}")
                    if replacement is not None and not isinstance(replacement, dict):
                        numbers = [replacement]
                if not numbers:
                    if isinstance(replacement, dict) and replacement["dates"] == []:
                        # Reviewed painted content outside this printed month
                        # is not a dated collection event (e.g. stale Nov cell).
                        cells.append(
                            dict(
                                month=month,
                                dates=[],
                                printed_numbers=printed_numbers,
                                number_glyphs=glyphs,
                                text=text,
                                codes=[],
                                closed=False,
                                rect=rect,
                                colors=[],
                                excluded_non_date=True,
                            )
                        )
                        continue
                    if text:
                        raise ValueError(
                            f"Text without date: {path} m{month} r{ri} c{ci}: {text} {rect}"
                        )
                    continue
                codes = []
                for label, code in [
                    ("もえる", "burnable"),
                    ("もえない", "non_burnable"),
                    ("乾電池", "dry_batteries"),
                    ("古紙", "paper"),
                    ("ガラスびん", "bottles"),
                    ("ペット", "pet_bottles"),
                    ("スプレー", "spray_cans"),
                ]:
                    if label in text:
                        codes.append(code)
                if "ガラスびん等" in text:
                    codes += ["pet_bottles", "spray_cans"]
                closed = "休み" in text
                if closed and codes:
                    raise ValueError("Closed cell also contains collection")
                fills = set()
                for d in drawings:
                    r = d["rect"]
                    code = color_code(d["fill"])
                    if (
                        code
                        and r.width > 3
                        and r.height > 2
                        and rect[0] < (r.x0 + r.x1) / 2 < rect[2]
                        and rect[1] < (r.y0 + r.y1) / 2 < rect[3]
                    ):
                        fills.add(code)
                expected = set(codes) - {
                    "dry_batteries",
                    "bottles",
                    "pet_bottles",
                    "spray_cans",
                }
                if set(codes) & {"bottles", "pet_bottles", "spray_cans"}:
                    expected.add("resources")
                if fills != expected and not (
                    fills == expected - {"non_burnable"} and "resources" in fills
                ):
                    raise ValueError(
                        f"Label/color mismatch: {path} {month}/{numbers}: {text!r} {fills}/{expected}"
                    )
                if len(numbers) > 1 and (numbers != [24, 31] and numbers != [23, 30]):
                    raise ValueError(
                        f"Unexpected diagonal cell dates: {path} {month} {ri} {ci}: {text}"
                    )
                if len(numbers) > 1 and (
                    ci > 1 or set(codes) - {"burnable", "non_burnable", "dry_batteries"}
                ):
                    raise ValueError("Ambiguous shared date-cell collection")
                for number in numbers:
                    day = date(year, month, number)
                    if (day.weekday() + 1) % 7 != ci:
                        raise ValueError(
                            f"Printed weekday mismatch: {path} {day} col{ci}: {text!r}"
                        )
                    key = day.isoformat()
                    if key in days:
                        raise ValueError(
                            f"Duplicate date: {path} {key} cell{ri}/{ci}: {text}"
                        )
                    days[key] = sorted(codes)
                    found.append(number)
                cells.append(
                    dict(
                        month=month,
                        dates=[date(year, month, n).isoformat() for n in numbers],
                        printed_numbers=printed_numbers,
                        number_glyphs=glyphs,
                        text=text,
                        codes=sorted(codes),
                        closed=closed,
                        rect=rect,
                        colors=sorted(fills),
                    )
                )
        import calendar as cal

        if sorted(found) != list(range(1, cal.monthrange(year, month)[1] + 1)):
            raise ValueError(f"Missing printed day numbers: {path} {month}: {found}")
        months.append(
            dict(month=month, rect=[x0, header.y0 - 22, x0 + 7 * width, ys[-1] + 1])
        )
    if len(days) != 365:
        raise ValueError("Expected a complete fiscal year")
    return dict(
        days=dict(sorted(days.items())),
        cells=cells,
        months=months,
        legend=text_in(chars, (0, ys[-1] + 1, 842, 1190)),
        title=text_in(chars, (0, 100, 842, 155)),
    )
