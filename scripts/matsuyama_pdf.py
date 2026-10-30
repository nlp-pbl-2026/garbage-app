"""Strict geometric reader for the official FY2026 calendar layout.

No recurring-date inference: all 365 printed date cells must be present. Category
labels are checked independently against their vector fill colors. A changed
layout, unknown label/color or missing cell stops the build for human review.
"""
from __future__ import annotations

import calendar
from datetime import date
import re

MAIN_LABELS = {"可燃": "combustible", "プラ": "plastic_packaging", "紙類": "paper",
               "金・ガ": "metal_glass", "埋立": "landfill", "水銀": "mercury",
               "ペット": "pet_bottle"}
MAIN_COLORS = {(0.933, 0.528, 0.704): ("combustible",),
               (0.98, 0.747, 0.0): ("plastic_packaging",),
               (0.56, 0.766, 0.12): ("paper",),
               (0.0, 0.725, 0.936): ("metal_glass",),
               (0.56, 0.509, 0.737): ("landfill",),
               (0.654, 0.667, 0.663): ("mercury",),
               (0.929, 0.425, 0.0): ("pet_bottle",)}
ISLAND_GROUPS = (("cans", "metal_glass", "landfill", "mercury", "bulky",
                  "pet_bottle", "plastic_packaging"),
                 ("paper", "bottles", "pet_bottle", "plastic_packaging"))


def read_calendar(path, profile):
    import pymupdf

    document = pymupdf.open(path)
    if len(document) != 1:
        raise ValueError("Expected one official calendar page")
    page = document[0]
    if abs(page.rect.width - 1190.55) > 1 or abs(page.rect.height - 1683.78) > 1:
        raise ValueError("Unreviewed PDF page geometry")
    spans = [s for b in page.get_text("rawdict")["blocks"]
             for line in b.get("lines", []) for s in line["spans"]]
    chars = [dict(c, font_size=s["size"]) for s in spans for c in s["chars"]]
    headers = [("".join(c["c"] for c in s["chars"]).strip(), s["bbox"])
               for s in spans if abs(s["size"] - 30) < .1]
    header_months = [t for t, box in sorted(headers, key=lambda v: (round(v[1][1]), v[1][0]))
                     if t.isdigit() and box[1] < 640]
    if header_months != [str(m) for m in [4,5,6,7,8,9,10,11,12,1,2,3]]:
        raise ValueError(f"Unreviewed month headers: {header_months}")

    labels = dict(MAIN_LABELS)
    colors = dict(MAIN_COLORS)
    legend_text = page.get_text(clip=pymupdf.Rect(270, 20, 600, 108))
    if profile == "nakajima":
        groups = re.findall(r"第([1-5])([月火水木金土日])曜ごみ", legend_text)
        if len(groups) != 2:
            raise ValueError("Unrecognized island collection legend")
        labels = {"可燃": ("combustible",)}
        labels.update({f"第{n}{weekday}": categories
                       for (n, weekday), categories in zip(groups, ISLAND_GROUPS)})
        colors = {(0.933, 0.528, 0.704): ("combustible",),
                  (0.98, 0.747, 0.0): ISLAND_GROUPS[0],
                  (0.0, 0.725, 0.936): ISLAND_GROUPS[1]}
        # Guard the actual group contents, not merely weekday labels.
        for word in ["缶類", "金物・ガラス類", "埋立", "水銀", "粗大ごみ", "紙類", "びん類"]:
            if word not in legend_text:
                raise ValueError(f"Missing island legend component: {word}")
    else:
        labels = {k: (v,) for k, v in labels.items()}
        for word in ["可燃ごみ", "紙類", "ペットボトル", "プラスチック製容器包装", "金物・ガラス類"]:
            if word not in re.sub(r"\s", "", legend_text):
                raise ValueError(f"Missing mainland legend component: {word}")

    fills = [(d["rect"], tuple(round(v, 3) for v in d["fill"]))
             for d in page.get_drawings() if d["fill"] and
             d["rect"].x1 < 975 and 160 < d["rect"].y0 < 837 and
             5 < d["rect"].width < 40 and 5 < d["rect"].height < 40]
    cells = {}
    for span in spans:
        if not (abs(span["size"] - 17.892) < .12 or abs(span["size"] - 8.946) < .08):
            continue
        text = "".join(c["c"] for c in span["chars"])
        for match in re.finditer(r"\d+", text):
            run = span["chars"][match.start():match.end()]
            box = pymupdf.Rect(min(c["bbox"][0] for c in run), min(c["bbox"][1] for c in run),
                               max(c["bbox"][2] for c in run), max(c["bbox"][3] for c in run))
            x, y = (box.x0 + box.x1) / 2, box.y0
            if not (24 < x < 970 and 160 < y < 837) or not 1 <= int(match[0]) <= 31:
                continue
            column = int((x - 24) // 238.1)
            row = int((y - 111.1) // 239.55)
            if column not in range(4) or row not in range(3):
                raise ValueError("Date outside reviewed calendar grid")
            month = (4 + 4 * row + column - 1) % 12 + 1
            printed_date = date(2026 if month >= 4 else 2027, month, int(match[0]))
            weekday = (printed_date.weekday() + 1) % 7
            cell_x = 44.3 + column * 238.1 + weekday * 32
            if abs(x - cell_x) > 10:
                raise ValueError(f"Date/weekday geometry mismatch: {printed_date}")
            key = printed_date.isoformat()
            if key in cells:
                old = cells[key]
                if abs(old["bbox"][1] - box.y0) > 1 or abs(old["bbox"][0] - box.x0) > 1:
                    raise ValueError(f"Duplicate date with conflicting position: {key}")
                continue  # outlined numbers have duplicate text layers
            label_chars = [c for c in chars if cell_x - 16.8 < (c["bbox"][0] + c["bbox"][2]) / 2 < cell_x + 16.8
                           and box.y1 - 1 < (c["bbox"][1] + c["bbox"][3]) / 2 < box.y1 + 6
                           and not (c["c"].isdigit() and abs(c["font_size"] - 8.946) < .08)]
            label_chars.sort(key=lambda c: c["bbox"][0])
            label = re.sub(r"\s", "", "".join(c["c"] for c in label_chars))
            categories = labels.get(label.removesuffix("振替"))
            if label not in ("", "休止") and categories is None:
                raise ValueError(f"Unknown printed category at {key}: {label!r}")
            point = pymupdf.Point(x, (box.y0 + box.y1) / 2 + (4 if box.height > 20 else 1))
            fill_categories = {colors[color] for rect, color in fills if color in colors and point in rect}
            if len(fill_categories) > 1:
                raise ValueError(f"Conflicting date colors: {key}")
            expected = next(iter(fill_categories), ())
            if tuple(categories or ()) != expected:
                raise ValueError(f"Label/color disagreement at {key}: {label!r}, colors={expected}")
            cells[key] = {"categories": sorted(categories or ()), "label": label,
                          "bbox": [round(v, 2) for v in box]}
    if len(cells) != 365:
        raise ValueError(f"Expected all 365 printed cells, got {len(cells)}")
    for month in range(1, 13):
        year = 2026 if month >= 4 else 2027
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            if date(year, month, day).isoformat() not in cells:
                raise ValueError(f"Missing printed day: {year}-{month}-{day}")
    return {"days": {key: value["categories"] for key, value in sorted(cells.items())},
            "exceptions": {key: value["label"] for key, value in sorted(cells.items()) if value["label"] == "休止" or "振替" in value["label"]},
            "legend_text": legend_text, "cells": cells}
