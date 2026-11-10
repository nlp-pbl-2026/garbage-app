#!/usr/bin/env python3
"""Extract the 1,293-row Seiyo dictionary after local Windows OCR.

Render ``dictionary.pdf`` to 300-dpi PNG files named ``dictionary-01.png``
through ``dictionary-26.png``. Run ``seiyo_windows_ocr.ps1`` for the top and
bottom halves, then use this script to recover the official table cells and
their category colors. OCR is only transcription assistance; reviewed
normalization remains in ``seiyo_data.py``.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BASE_SIDES = {
    "left": (77, 429, 531, 812),
    "right": (825, 1177, 1279, 1560),
}


def groups(values: np.ndarray) -> list[tuple[int, int]]:
    if not len(values):
        return []
    result: list[tuple[int, int]] = []
    start = previous = int(values[0])
    for raw in values[1:]:
        value = int(raw)
        if value != previous + 1:
            result.append((start, previous))
            start = value
        previous = value
    result.append((start, previous))
    return result


def cell_text(words: list[dict], x0: int, x1: int, y0: int, y1: int) -> str:
    selected = []
    for word in words:
        cx = word["x"] + word["width"] / 2
        cy = word["y"] + word["height"] / 2
        if x0 + 3 < cx < x1 - 3 and y0 + 2 < cy < y1 - 2:
            selected.append(word)
    if not selected:
        return ""
    tolerance = max(10, int(np.median([word["height"] for word in selected]) * 0.65))
    visual_lines: list[list[dict]] = []
    for word in sorted(selected, key=lambda value: (value["y"], value["x"])):
        cy = word["y"] + word["height"] / 2
        if not visual_lines:
            visual_lines.append([word])
            continue
        centers = [item["y"] + item["height"] / 2 for item in visual_lines[-1]]
        if abs(cy - float(np.median(centers))) <= tolerance:
            visual_lines[-1].append(word)
        else:
            visual_lines.append([word])
    return "".join(
        "".join(item["text"] for item in sorted(line, key=lambda value: value["x"]))
        for line in visual_lines
    ).replace(" ", "")


def dominant_color(image: np.ndarray, x0: int, x1: int, y0: int, y1: int) -> tuple[int, int, int]:
    crop = image[y0 + 4:y1 - 4, x0 + 4:x1 - 4]
    flat = crop.reshape(-1, 3)
    row_blue = np.array([203, 216, 241])
    mask = (
        (flat.max(axis=1) > 80)
        & ~((flat.min(axis=1) > 242) & (flat.max(axis=1) > 242))
        & (np.linalg.norm(flat.astype(float) - row_blue, axis=1) > 18)
    )
    colors = Counter(map(tuple, flat[mask].tolist()))
    return colors.most_common(1)[0][0] if colors else (0, 0, 0)


def ocr_words(ocr_dir: Path, stem: str, split: int, overlap: int) -> list[dict]:
    top = json.loads((ocr_dir / f"{stem}-top.json").read_text(encoding="utf-8-sig"))
    bottom = json.loads(
        (ocr_dir / f"{stem}-bottom-y{split - overlap}.json").read_text(encoding="utf-8-sig")
    )
    words = []
    for line in top["lines"]:
        for word in line["words"]:
            if word["y"] + word["height"] / 2 < split:
                words.append(word)
    for line in bottom["lines"]:
        for source_word in line["words"]:
            word = dict(source_word)
            word["y"] += split - overlap
            if word["y"] + word["height"] / 2 >= split:
                words.append(word)
    return words


def extract_page(page: int, image_dir: Path, ocr_dir: Path) -> tuple[list[dict], list[str]]:
    stem = f"dictionary-{page:02d}"
    image = np.array(Image.open(image_dir / f"{stem}.png").convert("RGB"))
    gray = image.mean(axis=2)
    split = image.shape[0] // 2
    overlap = 100
    words = ocr_words(ocr_dir, stem, split, overlap)
    records: list[dict] = []
    diagnostics: list[str] = []
    scale = image.shape[1] / 1654
    sides = {
        name: tuple(round(value * scale) for value in bounds)
        for name, bounds in BASE_SIDES.items()
    }
    for side, (x0, x_name, x_category, x1) in sides.items():
        coverage = (gray[:, x0:x1 + 1] < 80).sum(axis=1)
        horizontal = groups(np.where(coverage >= int((x1 - x0) * 0.88))[0])
        header_indices = []
        for index in range(len(horizontal) - 1):
            y0 = horizontal[index][1] + 2
            y1 = horizontal[index + 1][0] - 1
            if y1 <= y0:
                continue
            sample = image[y0:y1, x0 + round(15 * scale):x0 + round(100 * scale)]
            median = np.median(sample.reshape(-1, 3), axis=0)
            if np.linalg.norm(median - np.array([188, 163, 154])) < 25:
                header_indices.append(index)
        table_ranges = []
        for position, header_index in enumerate(header_indices):
            last_index = header_indices[position + 1] - 1 if position + 1 < len(header_indices) else len(horizontal) - 1
            table_ranges.append((horizontal[header_index][0], horizontal[last_index][1]))
        diagnostics.append(f"{stem} {side} headers={header_indices}")
        for table_index, (table_start, table_end) in enumerate(table_ranges):
            lines = [
                (begin + end) // 2
                for begin, end in horizontal
                if begin >= table_start and end <= table_end
            ]
            if len(lines) < 3:
                diagnostics.append(f"WARN short table: {stem} {side} {table_start}:{table_end}")
                continue
            for row_index, (y0, y1) in enumerate(zip(lines[1:-1], lines[2:]), start=1):
                name = cell_text(words, x0, x_name, y0, y1)
                category_text = cell_text(words, x_name, x_category, y0, y1)
                note = cell_text(words, x_category, x1, y0, y1)
                color = dominant_color(image, x_name, x_category, y0, y1)
                if not name:
                    diagnostics.append(f"WARN empty name: {stem} {side} y={y0}:{y1}")
                records.append({
                    "page": page,
                    "side": side,
                    "table": table_index + 1,
                    "row": row_index,
                    "name": name,
                    "category_text": category_text,
                    "category_color": "#%02X%02X%02X" % color,
                    "note": note,
                    "name_bounds": [x0, x_name, y0, y1],
                })
    return records, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-directory", type=Path, default=ROOT / "tmp/seiyo-source/render/dictionary-300")
    parser.add_argument("--ocr-directory", type=Path, default=ROOT / "tmp/seiyo-source/ocr-dictionary-300-halves")
    parser.add_argument("--output", type=Path, default=ROOT / "data/regions/seiyo/source/dictionary-extracted.json")
    args = parser.parse_args()
    records: list[dict] = []
    diagnostics: list[str] = []
    for page in range(1, 27):
        page_records, page_diagnostics = extract_page(page, args.image_directory, args.ocr_directory)
        records.extend(page_records)
        diagnostics.extend(page_diagnostics)
    if len(records) != 1293:
        raise ValueError(f"Expected 1,293 Seiyo dictionary rows, found {len(records)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"records={len(records)} output={args.output}")
    for color, count in Counter(record["category_color"] for record in records).most_common():
        print(f"{color}: {count}")
    print("\n".join(diagnostics))


if __name__ == "__main__":
    main()
