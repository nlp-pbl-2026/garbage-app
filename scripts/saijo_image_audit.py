"""Offline raster/OCR checks independent of PDF text decoding.

OCR-seeded glyph templates cover repeated small print; uncertain matches fail
closed and require a source-hash-pinned manual review. No model/API inference.
"""

import json
from collections import Counter

from saijo_pdf import compact


def audit(data, raw_items, calendars, digest):
    import numpy as np
    import pymupdf
    from PIL import Image

    def read(path):
        return json.loads(path.read_text())

    root = data / "generated/ocr"
    manifest = {r["id"]: r for r in read(root / "manifest.json")}

    def observations(key, source):
        record = read(root / (key + ".json"))
        meta = manifest[key]
        if (
            record["source_sha256"] != digest(source)
            or record["image_sha256"] != digest(root / (key + ".png"))
            or meta["image_sha256"] != record["image_sha256"]
        ):
            raise ValueError("Stale OCR input/output: " + key)
        return record["observations"]

    def nearby(obs, rect, image_rect):
        ox, oy, x1, y1 = image_rect
        w, h = x1 - ox, y1 - oy
        return [
            o
            for o in obs
            if rect[0] <= ox + (o["box"][0] + o["box"][2]) / 2 * w < rect[2]
            and rect[1] <= oy + (o["box"][1] + o["box"][3]) / 2 * h < rect[3]
        ]

    raster_cache = [None, None]

    def shape(page, rect):
        # Replay a PDF page once, rather than once for every tiny date glyph.
        key = (page.parent.name, page.number)
        if raster_cache[0] != key:
            pix = page.get_pixmap(matrix=pymupdf.Matrix(5, 5), alpha=False)
            raster_cache[:] = [
                key,
                Image.frombytes("RGB", (pix.width, pix.height), pix.samples),
            ]
        import math

        image = raster_cache[1].crop(
            (
                math.floor(rect[0] * 5),
                math.floor(rect[1] * 5),
                math.ceil(rect[2] * 5),
                math.ceil(rect[3] * 5),
            )
        )
        a = np.asarray(image)
        mask = np.min(a, axis=2) < 150
        yy, xx = np.where(mask)
        if not len(xx):
            return None
        mask = mask[yy.min() : yy.max() + 1, xx.min() : xx.max() + 1]
        return (
            np.asarray(
                Image.fromarray((mask * 255).astype("uint8")).resize(
                    (100, 35), Image.Resampling.BILINEAR
                )
            ).astype(float)
            / 255
        )

    nearest_cache = {}

    def nearest(value, templates):
        if value is None:
            return None
        key = (id(templates), value.tobytes())
        if key in nearest_cache:
            return nearest_cache[key]
        candidates = [
            (float(np.mean(np.abs(value - bitmap))), label)
            for label, bitmaps in templates.items()
            for bitmap in bitmaps
        ]
        result = min(candidates) if candidates else None
        nearest_cache[key] = result
        return result

    manual_path = data / "manual_image_reviews.json"
    manual = (
        read(manual_path) if manual_path.exists() else dict(dictionary={}, dates={})
    )
    for name, sha in manual.get("source_sha256", {}).items():
        if digest(data / "source" / name) != sha:
            raise ValueError("Manual image review belongs to another source")
    entries = []
    templates = {}
    dict_doc = pymupdf.open(data / "source/guide-10.pdf")
    obs = {
        pi: observations(f"dictionary-{pi:02}", data / "source/guide-10.pdf")
        for pi in range(1, 27)
    }
    for r in raw_items:
        page = dict_doc[r["pdf_page"] - 1]
        rect = r["category_rect"]
        text = compact(
            "".join(
                o["text"] for o in nearby(obs[r["pdf_page"]], rect, list(page.rect))
            )
        )
        label = r["source_category"]
        base = label.split("(")[0]
        # OCR alone cannot distinguish resource subclasses by the word 資源.
        passed = label in text if "(" in label and base == "資源" else base in text
        value = shape(page, [rect[0] + 1, rect[1] + 0.8, rect[2] - 0.8, rect[3] - 0.8])
        if passed and value is not None:
            templates.setdefault(label, []).append(value)
        entries.append((r["item_id"], label, passed, value, text))
    stats = Counter()
    unresolved = []
    for key, label, passed, value, text in entries:
        if passed:
            stats["dictionary_ocr"] += 1
            continue
        best = nearest(value, templates)
        if best and best[1] == label and best[0] < 0.10:
            stats["dictionary_raster"] += 1
        elif manual.get("dictionary", {}).get(key) == label:
            stats["dictionary_manual"] += 1
        else:
            unresolved.append(
                dict(kind="dictionary", id=key, label=label, ocr=text, nearest=best)
            )

    number_entries = []
    templates = {}
    colors = 0
    date_cells = 0
    closed = 0
    for cid, cal in calendars.items():
        source = data / "source" / f"calendar-{cid[-2:]}.pdf"
        page = pymupdf.open(source)[0]
        # Rendered pixel colors must agree with the painted rectangles and
        # printed stream labels. Not merely generated JSON vs generated JSON.
        pix = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=False)
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, 3
        )
        months = {m["month"]: m for m in cal["months"]}
        observations_by_month = {
            m: observations(f"{cid}-m{m:02}", source) for m in months
        }
        for ci, cell in enumerate(cal["cells"]):
            if cell.get("excluded_non_date"):
                continue
            date_cells += len(cell["dates"])
            closed += int(cell["closed"])
            x0, y0, x1, y1 = cell["rect"]
            a = image[int(y0 * 3) : int(y1 * 3), int(x0 * 3) : int(x1 * 3)]
            from saijo_pdf import COLORS

            for code in cell["colors"]:
                rgb = np.asarray(COLORS[code]) * 255
                if not (np.max(np.abs(a.astype(float) - rgb), axis=2) < 12).any():
                    raise ValueError("Rendered color mismatch")
            colors += 1
            month = months[cell["month"]]
            seen = observations_by_month[cell["month"]]
            for gi, glyph in enumerate(cell["number_glyphs"]):
                key = f'{cid}-m{cell["month"]:02}-c{ci}-g{gi}'
                # OCR often joins neighbouring date numbers into one line.
                # Only use single-number observations as training labels.
                near = nearby(seen, glyph["rect"], month["rect"])
                text = compact("".join(o["text"] for o in near))
                label = glyph["text"]
                value = shape(page, glyph["rect"])
                passed = text == label
                if passed and value is not None:
                    templates.setdefault(label, []).append(value)
                number_entries.append((key, label, passed, value, text))
    # Bound duplicate templates while retaining normal, red and blue fonts.
    templates = {
        k: list({a.tobytes(): a for a in v}.values())[:12] for k, v in templates.items()
    }
    for key, label, passed, value, text in number_entries:
        if passed:
            stats["date_glyph_ocr"] += 1
            continue
        best = nearest(value, templates)
        if best and best[1] == label and best[0] < 0.10:
            stats["date_glyph_raster"] += 1
        elif manual.get("dates", {}).get(key) == label:
            stats["date_glyph_manual"] += 1
        else:
            unresolved.append(
                dict(kind="date", id=key, label=label, ocr=text, nearest=best)
            )
    report = dict(
        dictionary_rows=len(entries),
        calendar_dates=date_cells,
        rendered_cells=colors,
        closed_cells=closed,
        date_glyphs=len(number_entries),
        **dict(stats),
        unresolved=unresolved,
        whole_split=read(data / "generated/whole-split-audit.json"),
        scope="Every extracted dictionary classification and printed numeric glyph; every calendar cell color/label. Names/notes matched across full and split PDFs, not independently re-transcribed. Date-label corrections and the month-external painted cell are recorded separately.",
    )
    target = data / "generated/image-audit-candidate.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if unresolved:
        raise ValueError(
            f"{len(unresolved)} unresolved raster/OCR entries; see {target}"
        )
    reviewed = data / "image_reviews.json"
    if not reviewed.exists() or read(reviewed) != report:
        raise ValueError("Image audit differs from reviewed summary")
    return report
