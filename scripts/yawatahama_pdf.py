"""Extract dated calendar icons and independently check raster background colors.

The 2026 official A3 layout has 4 columns x 3 months, with diagonal shared cells
for a sixth week. Both routes handle those cells; no weekday recurrence is used
as collection data. PyMuPDF is needed only for official-data integration checks.
"""
import calendar
from datetime import date
from collections import Counter

# Verified against the named symbols in the official legend. RGB values are PDF
# vector fills, not screen colors or a mapping borrowed from another municipality.
ICON_COLORS = {
    (0.95273, 0.43906, 0.26134): "burnable",
    (0.21122, 0.46592, 0.73765): "non_burnable",
    (0.81566, 0.60562, 0.25084): "cardboard",
    (0.65530, 0.66363, 0.67346): "newspaper",
    (0.57092, 0.15113, 0.56152): "magazines",
    (0.99973, 0.79641, 0.01537): "bottles",
    (0.93762, 0.35572, 0.63056): "cans",
    (0.04442, 0.69535, 0.29541): "pet_bottles",
    (0.47453, 0.38177, 0.66764): "plastic_packaging",
    (0.94876, 0.44440, 0.52464): "paper_packaging",
}
BACKGROUND_COLORS = {
    (0.99272, 0.72361, 0.07263): "burnable",
    (0.72541, 0.89963, 0.98233): "non_burnable",
    (0.94592, 0.81192, 0.67449): "cardboard",
    (0.90323, 0.90668, 0.91019): "newspaper",
    (0.78112, 0.62794, 0.79417): "magazines",
    (1.00000, 0.97493, 0.68057): "bottles",
    (0.97345, 0.75833, 0.85173): "cans",
    (0.75586, 0.88382, 0.75532): "pet_bottles",
    (0.68437, 0.73977, 0.88147): "plastic_packaging",
    (0.98837, 0.82730, 0.78340): "paper_packaging",
}
X0, Y0, PANEL_X, PANEL_Y = 28.3465, 226.7723, 286.2995, 204.0945
WIDTH, HEIGHT = 39.685, 31.181


def mapped(code, island):
    return "paper_all" if island and code == "paper_packaging" else code


def layout(day):
    index = (day.month - 4) % 12
    column = (day.weekday() + 1) % 7
    first = (date(day.year, day.month, 1).weekday() + 1) % 7
    week = (first + day.day - 1) // 7
    x = X0 + index % 4 * PANEL_X + column * WIDTH
    y = Y0 + index // 4 * PANEL_Y + min(week, 4) * HEIGHT
    shared = calendar.monthrange(day.year, day.month)[1] + first > 35 and column < (
        calendar.monthrange(day.year, day.month)[1] + first - 35) and week >= 4
    return x, y, shared, week == 5


def _dates():
    return [date(2026 if m >= 4 else 2027, m, d)
            for m in [*range(4, 13), 1, 2, 3]
            for d in range(1, calendar.monthrange(2026 if m >= 4 else 2027, m)[1] + 1)]


def extract(page, *, island=False):
    if abs(page.rect.width - 1190.55) > .1 or abs(page.rect.height - 841.89) > .1:
        raise ValueError("Unexpected calendar page geometry")
    # Route A: actual PDF date labels plus vector icon fills.
    labels = {}
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = span["text"]
                x, y, x1, y1 = span["bbox"]
                if not text.isdigit() or not 220 < y < 792 or span["size"] > 12:
                    continue
                panel = int((x - X0) // PANEL_X) + int((y - Y0 + 2) // PANEL_Y) * 4
                if not 0 <= panel < 12:
                    raise ValueError("Date label outside month panels")
                month = (panel + 3) % 12 + 1
                day = date(2026 if month >= 4 else 2027, month, int(text))
                left, top, shared, last = layout(day)
                if not left <= x <= left + WIDTH or not top - 3 <= y <= top + HEIGHT:
                    raise ValueError(f"PDF date disagrees with weekday/row: {day}")
                if day in labels:
                    raise ValueError(f"Duplicate PDF date: {day}")
                labels[day] = (x, y, x1, y1)
    if set(labels) != set(_dates()):
        raise ValueError(f"Missing PDF date labels: {set(_dates()) - set(labels)}")
    days = {day.isoformat(): set() for day in labels}
    icon_count = 0
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if drawing["fill"] is None or rect.y0 < 220 or rect.y1 > 792:
            continue
        color = tuple(round(c, 5) for c in drawing["fill"])
        if color not in ICON_COLORS or not (5 < rect.width < 17 and abs(rect.width - rect.height) < .5):
            continue
        cx, cy = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
        matches = []
        for day in labels:
            x, y, shared, last = layout(day)
            if not (x < cx < x + WIDTH and y < cy < y + HEIGHT):
                continue
            if shared and (((cx - x) / WIDTH + (cy - y) / HEIGHT > 1) != last):
                continue
            matches.append(day)
        if len(matches) != 1:
            raise ValueError(f"Unassigned/ambiguous collection symbol: {rect}, {matches}")
        days[matches[0].isoformat()].add(mapped(ICON_COLORS[color], island))
        icon_count += 1
    return {day: sorted(codes) for day, codes in sorted(days.items())}, icon_count


def audit_raster(page, expected, *, island=False, scale=2):
    import pymupdf
    # Route B uses Gregorian calendar positions (no PDF labels/icon coordinates),
    # and the distinct pastel *background* palette rather than icon colors.
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
    samples = pix.samples
    palette = [(tuple(round(c * 255) for c in color), mapped(code, island))
               for color, code in BACKGROUND_COLORS.items()]
    palette.append(((255, 255, 255), ""))
    cells = 0
    compressed = 0
    for day in _dates():
        x, y, shared, last = layout(day)
        codes = set()
        for left, right in ([(.04, .96)] if shared else [(.04, .46), (.54, .96)]):
            counts = Counter()
            for ustep in range(24):
                u = left + (right - left) * ustep / 23
                for vstep in range(16):
                    v = .06 + .88 * vstep / 15
                    if shared and (abs(u + v - 1) < .10 or ((u + v > 1) != last)):
                        continue
                    px, py = round((x + u * WIDTH) * scale), round((y + v * HEIGHT) * scale)
                    offset = py * pix.stride + px * 3
                    pixel = samples[offset:offset+3]
                    if len(pixel) != 3:
                        raise ValueError("Sample outside rendered PDF")
                    distances = [(sum((pixel[i] - color[i]) ** 2 for i in range(3)), code)
                                 for color, code in palette]
                    distance, code = min(distances)
                    if distance <= 27:
                        counts[code] += 1
            if shared:
                codes.update(code for code, count in counts.items()
                             if code and count >= max(15, sum(counts.values()) * .10))
                continue
            if not counts or counts.most_common(1)[0][1] / sum(counts.values()) < .70:
                raise ValueError(f"Ambiguous rendered background at {day}: {counts}")
            code = counts.most_common(1)[0][0]
            if code:
                codes.add(code)
        if sorted(codes) != expected[day.isoformat()]:
            raise ValueError(f"Icon/background disagreement {day}: {expected[day.isoformat()]} != {sorted(codes)}")
        cells += 1
        compressed += shared
    return {"date_cells": cells, "compressed_date_cells": compressed, "render_scale": scale}
