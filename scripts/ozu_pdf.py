#!/usr/bin/env python3
"""Extract Ozu FY2026 collection dates from the official PDF calendars.

The city publishes three PDF layout families.  This parser does not OCR their
Japanese labels.  It reconstructs each calendar grid from the PDF rules and
maps the repeated, embedded collection icons to Gregorian date cells.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
import calendar
from itertools import combinations
import re
from statistics import median


CATEGORY_ORDER = (
    "burnable",
    "non_burnable",
    "cans_bottles",
    "pet_styro",
    "paper_cloth",
    "hazardous",
    "bulky",
)

IMAGE_CATEGORIES = {
    (51, 52): "burnable",
    (47, 42): "non_burnable",
    (28, 65): "cans_bottles",
    (44, 89): "pet_styro",
    (68, 56): "paper_cloth",
    (33, 45): "hazardous",
}


@dataclass(frozen=True)
class Grid:
    year: int
    month: int
    x_bounds: tuple[float, ...]
    y_bounds: tuple[float, ...]

    def locate(self, x: float, y: float) -> date | None:
        column = next(
            (index for index, (left, right) in enumerate(zip(self.x_bounds, self.x_bounds[1:]))
             if left <= x <= right),
            None,
        )
        row = next(
            (index for index, (top, bottom) in enumerate(zip(self.y_bounds, self.y_bounds[1:]))
             if top <= y <= bottom),
            None,
        )
        if column is None or row is None:
            return None
        first_column = (date(self.year, self.month, 1).weekday() + 1) % 7
        day = row * 7 + column - first_column + 1
        if not 1 <= day <= calendar.monthrange(self.year, self.month)[1]:
            return None
        return date(self.year, self.month, day)


def fiscal_months() -> list[tuple[int, int]]:
    return [(2026, month) for month in range(4, 13)] + [(2027, month) for month in range(1, 4)]


def empty_days() -> dict[str, list[str]]:
    current = date(2026, 4, 1)
    end = date(2027, 4, 1)
    result = {}
    while current < end:
        result[current.isoformat()] = []
        current += timedelta(days=1)
    return result


def _cluster_weighted(values: list[tuple[float, float]], tolerance: float = 1.5) -> list[tuple[float, float]]:
    """Return (weighted coordinate, total coverage) clusters."""
    groups: list[list[tuple[float, float]]] = []
    for coordinate, weight in sorted(values):
        if not groups or coordinate - groups[-1][-1][0] > tolerance:
            groups.append([])
        groups[-1].append((coordinate, weight))
    result = []
    for group in groups:
        total = sum(weight for _, weight in group)
        coordinate = sum(value * weight for value, weight in group) / total
        result.append((coordinate, total))
    return result


def _segments(page):
    """Yield normalized axis-aligned PDF rule segments."""
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "l":
                start, end = item[1], item[2]
                if abs(start.x - end.x) <= 1 and abs(start.y - end.y) > 8:
                    yield "v", (start.x + end.x) / 2, min(start.y, end.y), max(start.y, end.y)
                elif abs(start.y - end.y) <= 1 and abs(start.x - end.x) > 15:
                    yield "h", (start.y + end.y) / 2, min(start.x, end.x), max(start.x, end.x)
            elif item[0] == "re":
                rect = item[1]
                if rect.width <= 2 and rect.height > 8:
                    yield "v", (rect.x0 + rect.x1) / 2, rect.y0, rect.y1
                elif rect.height <= 2 and rect.width > 15:
                    yield "h", (rect.y0 + rect.y1) / 2, rect.x0, rect.x1
                elif rect.width > 100 and rect.height > 100:
                    yield "v", rect.x0, rect.y0, rect.y1
                    yield "v", rect.x1, rect.y0, rect.y1
                    yield "h", rect.y0, rect.x0, rect.x1
                    yield "h", rect.y1, rect.x0, rect.x1


def _date_spans(page):
    candidates = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = span["text"].strip()
                if re.fullmatch(r"\d{1,2}", text) and 180 < span["bbox"][1] < 800:
                    candidates.append(span)
    font_counts = Counter((span["font"], round(span["size"], 1)) for span in candidates)
    if not font_counts:
        raise ValueError("Calendar has no numeric date font")
    date_font, count = font_counts.most_common(1)[0]
    if count < 170:
        raise ValueError(f"Calendar date font coverage is too small: {count}")
    return [span for span in candidates if (span["font"], round(span["size"], 1)) == date_font]


def _panel_spans(page, page_index: int, panel_index: int):
    column = panel_index % 3
    row = panel_index // 3
    x0 = page.rect.width * column / 3
    x1 = page.rect.width * (column + 1) / 3
    y0, y1 = ((180, 510) if row == 0 else (490, page.rect.height))
    return [span for span in _date_spans(page)
            if x0 <= (span["bbox"][0] + span["bbox"][2]) / 2 < x1
            and y0 <= (span["bbox"][1] + span["bbox"][3]) / 2 < y1]


def _expected_weeks(year: int, month: int) -> int:
    first_column = (date(year, month, 1).weekday() + 1) % 7
    return (first_column + calendar.monthrange(year, month)[1] + 6) // 7


def _grid_for_panel(page, page_index: int, panel_index: int, segments) -> Grid:
    year, month = fiscal_months()[page_index * 6 + panel_index]
    panel_column = panel_index % 3
    panel_row = panel_index // 3
    panel_x0 = page.rect.width * panel_column / 3
    panel_x1 = page.rect.width * (panel_column + 1) / 3
    panel_y0, panel_y1 = ((180, 510) if panel_row == 0 else (490, page.rect.height))
    spans = _panel_spans(page, page_index, panel_index)
    expected_days = calendar.monthrange(year, month)[1]
    if len(spans) < expected_days - 5:
        raise ValueError(f"Too few date labels for {year}-{month:02}: {len(spans)}")

    span_y0 = min((span["bbox"][1] + span["bbox"][3]) / 2 for span in spans)
    span_y1 = max((span["bbox"][1] + span["bbox"][3]) / 2 for span in spans)
    approximate_height = median(
        abs((a["bbox"][1] + a["bbox"][3] - b["bbox"][1] - b["bbox"][3]) / 2)
        for a in spans for b in spans
        if 25 < abs((a["bbox"][1] + a["bbox"][3] - b["bbox"][1] - b["bbox"][3]) / 2) < 50
    )
    grid_y0 = span_y0 - approximate_height
    grid_y1 = span_y1 + approximate_height * 1.5

    vertical = []
    horizontal = []
    for orientation, coordinate, start, end in segments:
        if orientation == "v" and panel_x0 - 20 <= coordinate <= panel_x1 + 20:
            overlap = max(0, min(end, grid_y1, panel_y1) - max(start, grid_y0, panel_y0))
            if overlap:
                vertical.append((coordinate, overlap))
        elif orientation == "h" and panel_y0 <= coordinate <= panel_y1:
            overlap = max(0, min(end, panel_x1) - max(start, panel_x0))
            if overlap > 10:
                horizontal.append((coordinate, overlap))

    weeks = _expected_weeks(year, month)
    expected_grid_height = approximate_height * weeks
    x_candidates = [coordinate for coordinate, coverage in _cluster_weighted(vertical)
                    if coverage > expected_grid_height * .4]
    first_column = (date(year, month, 1).weekday() + 1) % 7
    best_x = None
    for bounds in combinations(x_candidates, 8):
        widths = [right - left for left, right in zip(bounds, bounds[1:])]
        if min(widths) < 35 or max(widths) > 100:
            continue
        score = 0
        for span in spans:
            center = (span["bbox"][0] + span["bbox"][2]) / 2
            column = next((index for index, pair in enumerate(zip(bounds, bounds[1:]))
                           if pair[0] <= center <= pair[1]), None)
            expected_column = (first_column + int(span["text"]) - 1) % 7
            if column == expected_column:
                score += 1
        candidate = (score, tuple(bounds))
        if best_x is None or candidate[0] > best_x[0]:
            best_x = candidate
    if best_x is None or best_x[0] < len(spans) - 3:
        raise ValueError(f"Could not align vertical calendar rules for {year}-{month:02}: {x_candidates}")

    y_candidates = [coordinate for coordinate, coverage in _cluster_weighted(horizontal)
                    if coverage > (panel_x1 - panel_x0) * .5]
    best = None
    for bounds in combinations(y_candidates, weeks + 1):
        score = 0
        for span in spans:
            center = (span["bbox"][1] + span["bbox"][3]) / 2
            row = next((index for index, pair in enumerate(zip(bounds, bounds[1:]))
                        if pair[0] <= center <= pair[1]), None)
            day = int(span["text"])
            expected_row = (first_column + day - 1) // 7
            if row == expected_row:
                score += 1
        penalty = sum(abs((right - left) - approximate_height) for left, right in zip(bounds, bounds[1:]))
        candidate = (score, -penalty, tuple(bounds))
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    # Some official panels merge the final week with a note row, so their last
    # horizontal rule spans only part of the panel.  Infer only that missing
    # edge from the otherwise regular row pitch and snap every available edge
    # back to an observed PDF rule.
    for start in y_candidates:
        inferred = []
        inferred_edges = 0
        for index in range(weeks + 1):
            predicted = start + approximate_height * index
            nearby = [value for value in y_candidates
                      if abs(value - predicted) <= approximate_height * .25]
            if nearby:
                inferred.append(min(nearby, key=lambda value: abs(value - predicted)))
            else:
                inferred.append(predicted)
                inferred_edges += 1
        if any(right <= left for left, right in zip(inferred, inferred[1:])):
            continue
        score = 0
        for span in spans:
            center = (span["bbox"][1] + span["bbox"][3]) / 2
            row = next((index for index, pair in enumerate(zip(inferred, inferred[1:]))
                        if pair[0] <= center <= pair[1]), None)
            expected_row = (first_column + int(span["text"]) - 1) // 7
            if row == expected_row:
                score += 1
        penalty = (sum(abs((right - left) - approximate_height) for left, right in zip(inferred, inferred[1:]))
                   + inferred_edges * approximate_height)
        candidate = (score, -penalty, tuple(inferred))
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    if best is None or best[0] < len(spans) - 3:
        raise ValueError(f"Could not align horizontal calendar rules for {year}-{month:02}")
    return Grid(year, month, best_x[1], best[2])


def _vector_anchor(drawing) -> tuple[str, ...] | None:
    rect = drawing["rect"]
    width, height = rect.width, rect.height
    items = len(drawing["items"])
    if items == 11 and 17.5 <= width <= 19.0 and 18.5 <= height <= 20.0:
        return ("burnable",)
    if items == 17 and 14.0 <= width <= 17.5 and 13.0 <= height <= 16.2:
        return ("non_burnable",)
    if ((items == 32 and 12.0 <= width <= 13.2 and 12.0 <= height <= 13.2) or
            (items == 10 and ((8.5 <= width <= 9.5 and 20.0 <= height <= 21.5) or
                              (10.2 <= width <= 11.2 and 24.0 <= height <= 25.5)))):
        return ("cans_bottles",)
    if items == 16 and 10.0 <= width <= 11.8 and 26.0 <= height <= 28.2:
        return ("pet_styro",)
    if items == 8 and ((7.4 <= width <= 8.4 and 14.0 <= height <= 15.5) or
                       (9.0 <= width <= 10.2 and 17.0 <= height <= 18.5) or
                       (12.0 <= width <= 13.5 and 23.0 <= height <= 25.0)):
        return ("hazardous",)
    if items == 39 and 21.0 <= width <= 26.0 and 17.0 <= height <= 21.0:
        return ("paper_cloth",)
    if items == 11 and 17.0 <= width <= 19.0 and 2.4 <= height <= 3.7:
        return ("bulky",)
    return None


def _anchors(page, image_layout: bool):
    if image_layout:
        for info in page.get_image_info(xrefs=True):
            category = IMAGE_CATEGORIES.get((info["width"], info["height"]))
            if category:
                rect = info["bbox"]
                yield ((category,), (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
        return
    for drawing in page.get_drawings():
        categories = _vector_anchor(drawing)
        if categories:
            rect = drawing["rect"]
            yield categories, (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2


def extract(document):
    if len(document) != 2:
        raise ValueError("Ozu official calendars must have two pages")
    days = empty_days()
    counts = Counter()
    families = []
    for page_index, page in enumerate(document):
        segments = list(_segments(page))
        grids = [_grid_for_panel(page, page_index, panel, segments) for panel in range(6)]
        image_layout = len(page.get_image_info(xrefs=True)) > 50
        families.append("embedded-images" if image_layout else "vector-icons")
        for categories, x, y in _anchors(page, image_layout):
            matched = next((grid.locate(x, y) for grid in grids if grid.locate(x, y)), None)
            if matched is None:
                continue  # legend icon outside the date grids
            key = matched.isoformat()
            for category in categories:
                if category not in days[key]:
                    days[key].append(category)
                    counts[category] += 1
    if len(set(families)) != 1:
        raise ValueError(f"Calendar pages use inconsistent icon layouts: {families}")
    for values in days.values():
        values.sort(key=CATEGORY_ORDER.index)
    # Remote Hijikawa routes include both once-weekly and twice-weekly
    # burnable schedules; every route still has monthly paper collection.
    if counts["burnable"] < 45 or counts["paper_cloth"] < 10:
        raise ValueError(f"Implausible annual icon coverage: {dict(counts)}")
    return days, {"family": families[0], "collection_dates": dict(counts),
                  "dated_cells": len(days), "mapped_category_marks": sum(counts.values())}
