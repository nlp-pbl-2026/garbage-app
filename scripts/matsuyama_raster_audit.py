"""Independent rendered-pixel audit for all calendar date cells.

This uses locations from the extraction review but samples PDF raster colors,
not the vector fills read by matsuyama_pdf.py. It checks colored collection
markers, including small outlined dates, and absence of markers on Sundays.
Printed words and the contents of island legend groups still require text review.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import json

import numpy as np
import pymupdf

from matsuyama_data import DATA, read_json, sha256


MAIN_COLORS = {
    ("combustible",): (237, 134, 179),
    ("plastic_packaging",): (250, 190, 0),
    ("paper",): (142, 195, 30),
    ("metal_glass",): (0, 184, 238),
    ("landfill",): (143, 130, 188),
    ("mercury",): (167, 170, 169),
    ("pet_bottle",): (236, 108, 0),
}
ISLAND_COLORS = {
    ("combustible",): (237, 134, 179),
    ("bulky", "cans", "landfill", "mercury", "metal_glass",
     "pet_bottle", "plastic_packaging"): (250, 190, 0),
    ("bottles", "paper", "pet_bottle", "plastic_packaging"): (0, 184, 238),
}


def audit() -> dict:
    registry = read_json(DATA / "registry.json")
    extracted = read_json(DATA / "source/extraction-review.json")["calendars"]
    generated = read_json(DATA / "generated/calendar-2026.json")["calendars"]
    counts = Counter()
    failures = []
    for source in registry["calendars"]:
        calendar_id = source["id"]
        path = DATA / "source" / source["file"]
        if sha256(path) != source["sha256"]:
            raise ValueError(f"Official PDF changed: {calendar_id}")
        page = pymupdf.open(path)[0]
        pixels = page.get_pixmap(alpha=False)
        raster = np.frombuffer(pixels.samples, np.uint8).reshape(
            pixels.height, pixels.width, 3).astype(np.int32)
        palette = ISLAND_COLORS if source["rule_profile_id"] == "nakajima" else MAIN_COLORS
        for day, cell in extracted[calendar_id]["cells"].items():
            x0, y0, x1, y1 = cell["bbox"]
            is_small = y1 - y0 < 20
            if is_small:
                counts["outlined_small"] += 1
            if date.fromisoformat(day).weekday() == 6:
                counts["sunday_cells"] += 1
            patch = raster[round(y0):round(y1), round(x0 - 4):round(x1 + 4)]
            solids = sorted(((int(np.count_nonzero(
                np.sum((patch - np.asarray(rgb)) ** 2, axis=2) < 100)), categories)
                for categories, rgb in palette.items()), reverse=True)
            first, second = solids[0][0], solids[1][0]
            # Small outlined dates expose fewer solid pixels. Orange PET markers
            # are particularly narrow; the thresholds also reject gray text on
            # empty dates, which would otherwise look like a mercury marker.
            minimum = (5 if solids[0][1] == ("pet_bottle",) else 8) if is_small else 25
            rendered = tuple(sorted(solids[0][1])) if first >= minimum and first >= second * 1.5 else ()
            expected = tuple(sorted(generated[calendar_id]["days"][day]))
            counts["raster_checked"] += 1
            if rendered != expected:
                failures.append((calendar_id, day, expected, rendered, first, second))
    if failures:
        raise ValueError(f"Rendered PDF/date mismatch: {failures[:10]} ({len(failures)} total)")
    return dict(counts)


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
