"""Toon readers: glyph traces (not stale PDF ActualText), ruled cells and render audit."""

from __future__ import annotations
from collections import Counter
from datetime import date
from pathlib import Path
import re
import unicodedata

CATEGORY_CODES = {
    "燃やす": "burnable",
    "紙": "paper",
    "びん": "bottles_glass",
    "金属": "metals",
    "ペット": "pet_bottles",
    "プラ": "plastic_packaging",
    "その他": "non_burnable",
    "粗大": "bulky",
    "水銀": "mercury",
    "不可": "not_collected",
}
SYMBOLS = {
    "燃やすごみ": "burnable",
    "紙類収集": "paper",
    "びん・ガラス類": "bottles_glass",
    "缶・金属類": "metals",
    "ペット": "pet_bottles",
    "プラ類": "plastic_packaging",
    "その他": "non_burnable",
    "粗大": "bulky",
    "水銀類": "mercury",
    "電池": "batteries",
}


def compact(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))


def traces(page):
    # Some dictionary pages contain stale ActualText (e.g. the TOC instead of
    # アイスクリーム). Glyph traces reflect the visible characters. Bold calendar
    # labels are painted twice; de-duplicate by text and exact position.
    found = {}
    for span in page.get_texttrace():
        if span["type"] == 3 or span["opacity"] == 0:
            continue
        groups = []
        current = []
        for char in span["chars"]:
            if char[0] < 0:
                continue
            if current and (
                abs(char[3][1] - current[-1][3][1]) > 2
                or char[3][0] - current[-1][3][2] > span["size"] * 0.25
                or char[3][0] < current[-1][3][0] - 1
            ):
                groups.append(current)
                current = []
            current.append(char)
        if current:
            groups.append(current)
        for group in groups:
            text = "".join(chr(c[0]) for c in group).strip()
            if not text:
                continue
            box = (
                min(c[3][0] for c in group),
                min(c[3][1] for c in group),
                max(c[3][2] for c in group),
                max(c[3][3] for c in group),
            )
            key = (text, tuple(round(v, 2) for v in box))
            found[key] = {"text": text, "box": box}
    return list(found.values())


def inside(span, rect):
    b = span["box"]
    return (
        rect.x0 <= (b[0] + b[2]) / 2 < rect.x1
        and rect.y0 <= (b[1] + b[3]) / 2 < rect.y1
    )


def text_in(spans, rect):
    parts = [s for s in spans if inside(s, rect)]
    parts.sort(key=lambda s: ((s["box"][1] + s["box"][3]) / 2, s["box"][0]))
    lines = []
    for span in parts:
        cy = (span["box"][1] + span["box"][3]) / 2
        if not lines or abs(cy - lines[-1][0]) > 4:
            lines.append((cy, [span]))
        else:
            lines[-1][1].append(span)
    return "".join(
        "".join(s["text"] for s in sorted(line, key=lambda s: s["box"][0]))
        for _, line in lines
    ).strip()


def extract_items(path):
    import pymupdf

    doc = pymupdf.open(path)
    rows = []
    counts = {}
    if len(doc) != 58:
        raise ValueError("Guide edition changed")
    for pi in range(17, 56):
        p = doc[pi]
        spans = traces(p)
        drawings = p.get_drawings()
        page_rows = []
        for left, c0, c1, right in [
            (54, 156.6, 199.1, 289.4),
            (308.3, 410.8, 453.4, 543.7),
        ]:
            headers = sorted(
                {
                    round(d["rect"].y0, 1)
                    for d in drawings
                    if d["fill"]
                    and max(abs(a - b) for a, b in zip(d["fill"], (0.6, 1, 0.6)))
                    < 0.005
                    and 95 < d["rect"].width < 110
                    and abs(d["rect"].x0 - left) < 2
                }
            )
            borders = sorted(
                {
                    round(d["rect"].y0, 2)
                    for d in drawings
                    if d["fill"] == (0.0, 0.0, 0.0)
                    and d["rect"].height < 1
                    and d["rect"].width > 98
                    and abs(d["rect"].x0 - left) < 2
                }
            )
            for hi, header in enumerate(headers):
                stop = headers[hi + 1] if hi + 1 < len(headers) else 760
                ys = [y for y in borders if header + 17 < y < stop]
                ys = [y for i, y in enumerate(ys) if i == 0 or y - ys[i - 1] > 1]
                for ri, (top, bottom) in enumerate(zip(ys, ys[1:]), 1):
                    item = text_in(spans, pymupdf.Rect(left, top, c0, bottom))
                    label = compact(text_in(spans, pymupdf.Rect(c0, top, c1, bottom)))
                    note = text_in(spans, pymupdf.Rect(c1, top, right, bottom))
                    if not item and not label:
                        continue
                    if label and label not in CATEGORY_CODES:
                        raise ValueError(
                            f"Unknown dictionary label p{pi+1} {item} {label} {note}"
                        )
                    page_rows.append(
                        {
                            "item_id": f"tn-p{pi+1:02}-{int(left>300)+1}-{hi+1}-{ri:02}",
                            "item": item,
                            "category": CATEGORY_CODES.get(label, ""),
                            "note": note,
                            "source_category": label,
                            "pdf_page": pi + 1,
                            "printed_page": pi - 1,
                            "rect": [left, top, right, bottom],
                        }
                    )
        if not page_rows:
            raise ValueError(f"Dictionary page empty: {pi+1}")
        rows.extend(page_rows)
        counts[str(pi + 1)] = len(page_rows)
    return rows, counts


def calendar_days(path, profile, ocr_dir=None):
    import pymupdf
    import numpy as np
    import json, hashlib

    doc = pymupdf.open(path)
    result = {}
    audit = {
        "printed_dates": 0,
        "raster_dates": 0,
        "ocr_labels": 0,
        "ocr_unmatched": [],
        "hidden_unpainted_labels": [],
        "closed_dates": [],
        "simultaneous_dates": 0,
        "collection_counts": Counter(),
    }
    templates = {}
    pending = []
    expected_pages = 3 if profile == "shigenobu" else 2
    if len(doc) != expected_pages:
        raise ValueError("Calendar page count changed")
    for pi, p in enumerate(doc):
        spans = traces(p)
        w, h = p.rect.width, p.rect.height
        if "令和8年度" not in compact("".join(s["text"] for s in spans)):
            raise ValueError("Calendar fiscal year missing")
        suns = sorted(
            [s for s in spans if s["text"] == "日" and s["box"][1] > h * 0.15],
            key=lambda s: (round(s["box"][1] / 10), s["box"][0]),
        )
        expected = 4 if profile == "shigenobu" else 6
        if len(suns) != expected:
            raise ValueError(
                f"Month weekday rows missing {path.name} p{pi+1} {len(suns)}"
            )
        # Each label has an explicit vector fill, and an independent rendered
        # pixel background. A colour may intentionally represent several codes.
        drawings = p.get_drawings()
        fills = [
            (c[1], tuple(d["fill"]))
            for d in drawings
            if d["fill"]
            for c in d["items"]
            if c[0] == "re" and c[1].height > 2
        ]
        pix = p.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        pixels = np.frombuffer(pix.samples, np.uint8).reshape(
            pix.height, pix.width, pix.n
        )[:, :, :3]
        legend = {}
        raster_palette = {}
        for symbol, code in SYMBOLS.items():
            first = next(s for s in spans if compact(s["text"]) == symbol)
            x, y = (first["box"][0] + first["box"][2]) / 2, (
                first["box"][1] + first["box"][3]
            ) / 2
            backgrounds = [(r, c) for r, c in fills if r.contains(pymupdf.Point(x, y))]
            if not backgrounds:
                raise ValueError("Legend fill missing")
            r, c = min(backgrounds, key=lambda rc: rc[0].get_area())
            legend[code] = c
            patch = pixels[
                round(r.y0 * 2) + 1 : round(r.y1 * 2) - 1,
                round(r.x0 * 2) + 1 : round(r.x1 * 2) - 1,
            ]
            colors, counts = np.unique(patch.reshape(-1, 3), axis=0, return_counts=True)
            raster_palette[code] = colors[counts.argmax()].astype(int)
        ocr = None
        if ocr_dir:
            ocr = json.loads((ocr_dir / f"{path.stem}-{pi+1:02}.json").read_text())
            if ocr["source_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError("Stale OCR source")
        for mi, sun in enumerate(suns):
            month = (4 + pi * expected + mi - 1) % 12 + 1
            year = 2026 if month >= 4 else 2027
            sx = (sun["box"][0] + sun["box"][2]) / 2
            sy = sun["box"][1]
            nextcols = [
                (s["box"][0] + s["box"][2]) / 2
                for s in suns
                if abs(s["box"][1] - sy) < 2 and s["box"][0] > sun["box"][2]
            ]
            right_header = min(nextcols) - 5 if nextcols else sx + w * 0.43
            row = [
                s
                for s in spans
                if abs(s["box"][1] - sy) < 2
                and s["text"].strip() in list("日月火水木金土")
                and sx - 3 <= (s["box"][0] + s["box"][2]) / 2 < right_header
            ]
            centers = {s["text"].strip(): (s["box"][0] + s["box"][2]) / 2 for s in row}
            if "金" not in centers:
                raise ValueError("Weekday columns incomplete")
            centers.setdefault("土", centers["金"] + (centers["金"] - centers["木"]))
            xs = [centers[k] for k in "日月火水木金土"]
            edges = (
                [xs[0] - (xs[1] - xs[0]) / 2]
                + [(a + b) / 2 for a, b in zip(xs, xs[1:])]
                + [xs[-1] + (xs[-1] - xs[-2]) / 2]
            )
            nextrows = [
                s["box"][1]
                for s in suns
                if abs(s["box"][0] - sun["box"][0]) < w * 0.1 and s["box"][1] > sy + 5
            ]
            bottom = min(nextrows) - 5 if nextrows else h * 0.94
            body = [
                s
                for s in spans
                if sy + 8 < s["box"][1] < bottom
                and edges[0] < (s["box"][0] + s["box"][2]) / 2 < edges[-1]
            ]
            dates = [s for s in body if re.fullmatch(r"\d{1,2}", compact(s["text"]))]
            if len(dates) != __import__("calendar").monthrange(year, month)[1]:
                raise ValueError(f"Date count {path.name} {month} {len(dates)}")
            date_rows = sorted(set(round(s["box"][1], 1) for s in dates))
            date_rows = [
                y for i, y in enumerate(date_rows) if i == 0 or y - date_rows[i - 1] > 3
            ]
            if len(date_rows) < 4:
                raise ValueError("Date grid missing")
            gap = float(np.median(np.diff(date_rows)))
            # Month number lives in the vertical strip outside the Sunday col.
            marker = text_in(
                spans,
                pymupdf.Rect(
                    edges[0] - w * 0.06,
                    sy,
                    edges[0] - 2,
                    min(bottom, date_rows[-1] + gap),
                ),
            )
            if str(month) + "月" not in compact(marker):
                raise ValueError(
                    f"Month marker mismatch: {path.name} {month}: {marker}"
                )
            for ds in dates:
                day = int(compact(ds["text"]))
                dt = date(year, month, day)
                weekday = (dt.weekday() + 1) % 7
                x = (ds["box"][0] + ds["box"][2]) / 2
                y = ds["box"][1]
                if not edges[weekday] - 3 < x < edges[weekday + 1] + 3:
                    raise ValueError("Date weekday mismatch")
                rowindex = min(
                    range(len(date_rows)), key=lambda i: abs(date_rows[i] - y)
                )
                logical = ((date(year, month, 1).weekday() + 1) % 7 + day - 1) // 7
                if logical != rowindex:
                    raise ValueError("Date grid row mismatch")
                # Row heights vary with stacked collections (especially the
                # final Sunday). Use the painted grid border, never a median
                # extrapolation that could cut the bottom battery label off.
                bottom_edges = [
                    d["rect"].y0
                    for d in drawings
                    if d["fill"] == (0.0, 0.0, 0.0)
                    and d["rect"].height < 1.5
                    and d["rect"].width > 20
                    and d["rect"].x0 < x < d["rect"].x1
                    and y + 20 < d["rect"].y0 < bottom
                ]
                row_bottom = min(bottom_edges) if bottom_edges else y + gap - 1
                cell = pymupdf.Rect(
                    edges[weekday],
                    y - 1,
                    edges[weekday + 1],
                    (
                        date_rows[rowindex + 1] - 1
                        if rowindex + 1 < len(date_rows)
                        else row_bottom
                    ),
                )
                labels = [
                    s for s in body if inside(s, cell) and compact(s["text"]) in SYMBOLS
                ]
                codes = set()
                seen = set()
                for label in labels:
                    symbol = compact(label["text"])
                    code = SYMBOLS[symbol]
                    b = label["box"]
                    key = (symbol, tuple(round(v, 1) for v in b))
                    if key in seen:
                        continue
                    seen.add(key)
                    codes.add(code)
                    point = pymupdf.Point((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
                    backgrounds = [(r, c) for r, c in fills if r.contains(point)]
                    if not backgrounds:
                        patch = pixels[
                            round(b[1] * 2) : round(b[3] * 2),
                            round(b[0] * 2) : round(b[2] * 2),
                        ]
                        # White text retained in the PDF but not painted visibly
                        # must not become a collection. Require an empty raster.
                        if np.mean(np.min(patch, axis=-1) < 220) > 0.03:
                            raise ValueError(
                                f"Visible label without fill: {path.name} {dt} {symbol}"
                            )
                        codes.discard(code)
                        audit["hidden_unpainted_labels"].append(
                            {"date": dt.isoformat(), "symbol": symbol}
                        )
                        continue
                    rect, color = min(backgrounds, key=lambda rc: rc[0].get_area())
                    if max(abs(a - bb) for a, bb in zip(color, legend[code])) > 0.01:
                        raise ValueError("Symbol/vector legend colour mismatch")
                    patch = pixels[
                        round(rect.y0 * 2) + 1 : round(rect.y1 * 2) - 1,
                        round(rect.x0 * 2) + 1 : round(rect.x1 * 2) - 1,
                    ].astype(int)
                    target = raster_palette[code]
                    if (
                        not patch.size
                        or np.mean(np.max(abs(patch - target), axis=-1) < 10) < 0.18
                    ):
                        raise ValueError(
                            f"Symbol/raster colour mismatch {path.name} {dt} {symbol}"
                        )
                    if ocr:

                        def norm(text):
                            return compact(text).replace("・", "").replace("/", "")

                        box = pymupdf.Rect(b)
                        matches = [
                            o
                            for o in ocr["observations"]
                            if (
                                ob := pymupdf.Rect(
                                    o["box"][0] * w,
                                    o["box"][1] * h,
                                    o["box"][2] * w,
                                    o["box"][3] * h,
                                )
                            ).height
                            < box.height * 2.5
                            and (ob & box).get_area() > box.get_area() * 0.4
                        ]
                        patch = pixels[
                            round(b[1] * 2) : round(b[3] * 2),
                            round(b[0] * 2) : round(b[2] * 2),
                        ].astype(int)
                        ink = np.max(abs(patch - raster_palette[code]), axis=-1) > 70
                        yy, xx = np.where(ink)
                        if len(xx) == 0:
                            raise ValueError("Visible label has no rendered glyphs")
                        ink = ink[yy.min() : yy.max() + 1, xx.min() : xx.max() + 1]
                        ratio = ink.shape[1] / ink.shape[0]
                        signature = ink[
                            np.linspace(0, ink.shape[0] - 1, 24).astype(int)[:, None],
                            np.linspace(0, ink.shape[1] - 1, 96).astype(int)[None, :],
                        ]
                        if any(norm(symbol) in norm(o["text"]) for o in matches):
                            audit["ocr_labels"] += 1
                            templates.setdefault(code, []).append((ratio, signature))
                        else:
                            pending.append(
                                (
                                    code,
                                    ratio,
                                    signature,
                                    {
                                        "date": dt.isoformat(),
                                        "symbol": symbol,
                                        "page": pi + 1,
                                        "rect": list(b),
                                        "ocr": [o["text"] for o in matches],
                                    },
                                )
                            )
                # Reverse check: a painted collection block must have a
                # recognized visible label. Checking only extracted labels would
                # miss a coloured block whose PDF text is absent or unreadable.
                for rect, color in fills:
                    point = pymupdf.Point(
                        (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
                    )
                    if not cell.contains(point) or not any(
                        max(abs(a - bb) for a, bb in zip(color, shade)) < 0.01
                        for shade in legend.values()
                    ):
                        continue
                    if not any(
                        rect.contains(
                            pymupdf.Point(
                                (label["box"][0] + label["box"][2]) / 2,
                                (label["box"][1] + label["box"][3]) / 2,
                            )
                        )
                        and SYMBOLS[compact(label["text"])] in codes
                        for label in labels
                    ):
                        raise ValueError(
                            f"Painted collection block without a label: {path.name} {dt}"
                        )
                closed = any("収集休み" in s["text"] for s in body if inside(s, cell))
                if closed and codes:
                    raise ValueError("Closed day has collection labels")
                if closed:
                    audit["closed_dates"].append(dt.isoformat())
                if dt.isoformat() in result:
                    raise ValueError("Duplicate date")
                result[dt.isoformat()] = sorted(codes)
                audit["printed_dates"] += 1
                audit["raster_dates"] += 1
                audit["collection_counts"].update(codes)
                if len(codes) > 1:
                    audit["simultaneous_dates"] += 1
    if len(result) != 365:
        raise ValueError("Incomplete calendar year")
    audit["template_labels"] = 0
    for code, ratio, signature, record in pending:
        scores = {
            c: min(
                (
                    np.mean(signature != mask)
                    for aspect, mask in seeds
                    if abs(aspect - ratio) / ratio < 0.25
                ),
                default=1.0,
            )
            for c, seeds in templates.items()
        }
        ordered = sorted(scores, key=scores.get)
        if (
            ordered
            and ordered[0] == code
            and scores[code] < 0.18
            and (len(ordered) == 1 or scores[ordered[1]] - scores[code] > 0.015)
        ):
            audit["template_labels"] += 1
        else:
            audit["ocr_unmatched"].append(
                record
                | {"image_scores": {c: round(float(v), 4) for c, v in scores.items()}}
            )
    audit["collection_counts"] = dict(sorted(audit["collection_counts"].items()))
    return dict(sorted(result.items())), audit
