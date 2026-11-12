"""Independent, offline OCR verification of the raster calendar's date labels.

The extraction uses coloured icons; this audit checks the printed numbers and
captions. Unreadable numbers remain unresolved until a separate enlarged crop
is checked. Merely reproducing the same JSON is not a visual verification.
"""

from collections import Counter
import json
from pathlib import Path
import re
import subprocess

from uwajima_data import digest, read, sources, write
from uwajima_pdf import calendar_image


def prepare(data):
    import pymupdf

    manifest = []
    seen = set()
    root = data / "generated/renders"
    root.mkdir(parents=True, exist_ok=True)

    def render(page, key, sha):
        out = root / (key + ".png")
        page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).save(out)
        manifest.append(
            dict(
                id=key,
                image=str(out.resolve()),
                source_sha256=sha,
                image_sha256=digest(out),
            )
        )

    for s in read(data / "sources.json")["sources"]:
        if (
            not (s["file"].startswith("calendar-") and s["file"].endswith(".pdf"))
            or s["sha256"] in seen
        ):
            continue
        seen.add(s["sha256"])
        render(
            pymupdf.open(data / "source" / s["file"])[0], s["file"][:-4], s["sha256"]
        )
    write(data / "generated/ocr-manifest.json", manifest)
    manifest = []
    source = data / "source/document-55088.pdf"
    doc = pymupdf.open(source)
    for pi in range(1, len(doc)):
        render(doc[pi], f"dictionary-{pi+1:02}", digest(source))
    write(data / "generated/dictionary-ocr-manifest.json", manifest)


def run_ocr(data):
    """Local macOS OCR only; no AWS credentials or model calls."""
    prepare(data)
    root = Path(__file__).resolve().parents[1]
    binary = "/private/tmp/uwajima-ocr"
    subprocess.run(
        [
            "swiftc",
            "-module-cache-path",
            "/private/tmp/uwajima-swift-cache",
            str(root / "scripts/toon_ocr.swift"),
            "-o",
            binary,
        ],
        check=True,
    )
    out = data / "generated/ocr"
    out.mkdir(parents=True, exist_ok=True)
    for name in ["ocr-manifest.json", "dictionary-ocr-manifest.json"]:
        subprocess.run([binary, str(data / "generated" / name), str(out)], check=True)
    audit(data, base_only=True)
    refine(data)
    subprocess.run(
        [binary, str(data / "generated/date-refine-ocr-input.json"), str(out)],
        check=True,
    )
    return audit(data)


def audit_dictionary(data):
    """Compare traced table text with independently drawn category rectangles."""
    import pymupdf
    from uwajima_pdf import dictionary

    palette = {
        "bulky": (149, 149, 149),
        "burnable": (255, 153, 0),
        "non_burnable": (51, 102, 255),
        "not_collected": (255, 0, 0),
        "paper": (255, 255, 255),
        "dropoff": (255, 128, 128),
        "bottles_cans": (153, 51, 0),
        "pet": (51, 153, 102),
    }
    rows, counts = dictionary(data / "source/document-55088.pdf")
    doc = pymupdf.open(data / "source/document-55088.pdf")
    checked = 0
    unresolved = []
    for pi, page in enumerate(doc):
        if pi == 0:
            continue
        rr = [r for r in rows if r["pdf_page"] == pi + 1]
        fills = [
            d
            for d in page.get_drawings()
            if d["fill"] is not None
            and 235 < d["rect"].x0 < 237
            and 269 < d["rect"].x1 < 271
            and d["rect"].height > 5
            and max(abs(v - 0.75294) for v in d["fill"]) > 0.01
            and max(abs(v - t) for v, t in zip(d["fill"], (1, 1, 0.6))) > 0.01
        ]
        if len(fills) != len(rr):
            raise ValueError(
                f"Dictionary rendered row count mismatch p{pi+1}: {len(fills)}/{len(rr)}"
            )
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
        for row in rr:
            x0, y0, x1, y1 = row["category_rect"]
            fill = next(
                (
                    d
                    for d in fills
                    if abs(d["rect"].y0 - y0) < 0.3 and abs(d["rect"].y1 - y1) < 0.3
                ),
                None,
            )
            if fill is None:
                raise ValueError("No independent item background")
            color = pix.pixel(round((x0 + 2) * 2), round((y0 + 2) * 2))[:3]
            category = min(
                palette,
                key=lambda c: sum((a - b) ** 2 for a, b in zip(color, palette[c])),
            )
            if (
                category != row["category"]
                or sum((a - b) ** 2 for a, b in zip(color, palette[category])) > 200
            ):
                unresolved.append(
                    dict(
                        id=row["item_id"],
                        expected=row["category"],
                        colour=color,
                        rendered=category,
                    )
                )
            else:
                checked += 1
    report = dict(
        source_sha256=digest(data / "source/document-55088.pdf"),
        rendered_rows=checked,
        method="visible glyph positions, independent filled row rectangles and rendered background colours",
        page_counts=counts,
        unresolved=unresolved,
    )
    write(data / "generated/dictionary-image-review.json", report)
    return report


def nearby(observations, box, width, height):
    return [
        o
        for o in observations
        if box[0] <= (o["box"][0] + o["box"][2]) / 2 * width < box[2]
        and box[1] <= (o["box"][1] + o["box"][3]) / 2 * height < box[3]
    ]


def audit(data, *, base_only=False):
    import pymupdf
    import numpy as np
    from PIL import Image

    stats = Counter()
    unresolved = []
    results = []
    templates = {}
    entries = []
    refined = {}
    refine_manifest = data / "generated/date-refine-manifest.json"
    if refine_manifest.exists() and not base_only:
        for spec in read(refine_manifest):
            result_path = data / "generated/ocr" / (spec["id"] + ".json")
            if not result_path.exists():
                continue
            result = read(result_path)
            if (
                result["image_sha256"] != digest(Path(spec["image"]))
                or result["source_sha256"] != spec["source_sha256"]
            ):
                raise ValueError("Stale enlarged OCR evidence")
            for c in spec["cells"]:
                obs = nearby(
                    result["observations"],
                    c["sheet_box"],
                    spec["width"],
                    spec["height"],
                )
                refined[(c["file"], c["date"])] = [o["text"] for o in obs]
    manifest = read(data / "generated/ocr-manifest.json")
    manual_path = data / "manual_image_reviews.json"
    manual = read(manual_path) if manual_path.exists() and not base_only else {}
    for name, sha in manual.get("source_sha256", {}).items():
        if digest(data / "source" / name) != sha:
            raise ValueError("Manual image review source changed")
    for spec in manifest:
        source = data / "source" / (spec["id"] + ".pdf")
        result = read(data / "generated/ocr" / (spec["id"] + ".json"))
        if result["source_sha256"] != digest(source) or result[
            "image_sha256"
        ] != digest(Path(spec["image"])):
            raise ValueError("Stale OCR evidence")
        pg = pymupdf.open(source)[0]
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(3, 3))
        rendered = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        days, review, cells = calendar_image(source, include_cells=True)
        for cell in cells:
            x0, y0, x1, y1 = cell["box"]
            box = cell["box"] if cell["shared"] else [x0, y0, x0 + 19, y0 + 14]
            obs = nearby(result["observations"], box, pg.rect.width, pg.rect.height)
            expected = str(int(cell["date"][-2:]))
            numbers = [o["text"] for o in obs if re.fullmatch(r"\d{1,2}", o["text"])]
            passed = expected in numbers or expected in refined.get(
                (source.name, cell["date"]), []
            )
            bitmap = None
            if not cell["shared"]:
                a = np.asarray(
                    rendered.crop(
                        tuple(
                            round(v * 3) for v in [x0 + 1.5, y0 + 1.5, x0 + 19, y0 + 13]
                        )
                    )
                ).astype(int)
                mask = (
                    (a.max(2) < 120)
                    | ((a[:, :, 0] > 170) & (a[:, :, 1] < 90) & (a[:, :, 2] < 100))
                    | ((a[:, :, 0] < 30) & (a[:, :, 1] > 90) & (a[:, :, 2] > 150))
                )
                yy, xx = np.where(mask)
                if len(xx):
                    mask = mask[yy.min() : yy.max() + 1, xx.min() : xx.max() + 1]
                    bitmap = (
                        np.asarray(
                            Image.fromarray((mask * 255).astype("uint8")).resize(
                                (45, 35), Image.Resampling.BILINEAR
                            )
                        ).astype(float)
                        / 255
                    )
                if (
                    passed
                    and bitmap is not None
                    and len(templates.setdefault(expected, [])) < 24
                ):
                    templates[expected].append(bitmap)
            if passed:
                stats["printed_date_labels"] += 1
            else:
                entries.append(
                    (
                        dict(
                            file=source.name,
                            date=cell["date"],
                            kind="date",
                            observed=[o["text"] for o in obs],
                            box=box,
                        ),
                        bitmap,
                    )
                )
        stats["calendar_cells"] += len(cells)
        stats["collection_marks"] += review["events"]
        results.append(
            dict(file=source.name, source_sha256=spec["source_sha256"], **review)
        )
    for record, bitmap in entries:
        nearest = (
            min(
                (float(np.abs(bitmap - value).mean()), label)
                for label, values in templates.items()
                for value in values
            )
            if bitmap is not None
            else None
        )
        if (
            not base_only
            and nearest
            and nearest[1] == str(int(record["date"][-2:]))
            and nearest[0] < 0.12
        ):
            stats["printed_date_template"] += 1
        elif manual.get("dates", {}).get(record["file"] + ":" + record["date"]) == str(
            int(record["date"][-2:])
        ):
            stats["printed_date_visual_review"] += 1
        else:
            record["nearest"] = nearest
            unresolved.append(record)
    dictionary_review = audit_dictionary(data)
    unresolved.extend(dictionary_review["unresolved"])
    report = dict(
        method="rendered exact icon colours plus independent Apple Vision date labels; HTML recurrences are a separate comparison",
        status="checked" if not unresolved else "needs_review",
        counts=dict(stats),
        dictionary=dictionary_review,
        pdfs=results,
        unresolved=unresolved,
    )
    write(data / "generated/image-review-candidate.json", report)
    return report


def refine(data):
    """Make contact sheets of enlarged unresolved numbers, with no answer labels."""
    from PIL import Image
    import numpy as np
    import pymupdf

    candidates = read(data / "generated/image-review-candidate.json")["unresolved"]
    manifest = []
    page_cache = {}
    for start in range(0, len(candidates), 40):
        batch = candidates[start : start + 40]
        canvas = Image.new("RGB", (1500, 1200), "white")
        cells = []
        source_hashes = {}
        for index, c in enumerate(batch):
            source = data / "source" / c["file"]
            source_hashes[c["file"]] = digest(source)
            if c["file"] not in page_cache:
                page_cache.clear()  # at most one full-resolution page in memory
                p = pymupdf.open(source)[0].get_pixmap(matrix=pymupdf.Matrix(6, 6))
                page_cache[c["file"]] = Image.frombytes(
                    "RGB", (p.width, p.height), p.samples
                )
            box = list(c["box"])
            if box[3] - box[1] < 20:
                box = [box[0] + 1.5, box[1] + 1.5, box[2], box[3] - 1]
            im = page_cache[c["file"]].crop(tuple(round(v * 6) for v in box))
            # Mask the other printed triangle in the shared fifth/sixth-week cell.
            if box[3] - box[1] > 20:
                a = np.array(im)
                yy, xx = np.indices(a.shape[:2])
                upper = (xx + 0.5) / a.shape[1] + (yy + 0.5) / a.shape[0] < 1
                day = int(c["date"][-2:])
                shared_late = day >= 29
                a[upper if shared_late else ~upper] = 255
                im = Image.fromarray(a)
            im.thumbnail((220, 100))
            x = (index % 5) * 300 + 40
            y = (index // 5) * 150 + 20
            canvas.paste(im, (x, y))
            cells.append(
                dict(
                    file=c["file"],
                    date=c["date"],
                    source_box=box,
                    sheet_box=[x - 5, y - 5, x + im.width + 5, y + im.height + 5],
                )
            )
        key = f"date-refine-{start//40:03}"
        out = data / "generated/renders" / (key + ".png")
        canvas.save(out)
        import hashlib

        manifest.append(
            dict(
                id=key,
                image=str(out.resolve()),
                image_sha256=digest(out),
                source_sha256=hashlib.sha256(
                    json.dumps(source_hashes, sort_keys=True).encode()
                ).hexdigest(),
                source_hashes=source_hashes,
                cells=cells,
                width=canvas.width,
                height=canvas.height,
            )
        )
    write(data / "generated/date-refine-manifest.json", manifest)
    write(
        data / "generated/date-refine-ocr-input.json",
        [
            {k: r[k] for k in ["id", "image", "image_sha256", "source_sha256"]}
            for r in manifest
        ],
    )
    print(len(manifest), "enlarged contact sheets")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/regions/uwajima",
    )
    p.add_argument("--refine", action="store_true")
    p.add_argument("--ocr", action="store_true")
    args = p.parse_args()
    if args.ocr:
        r = run_ocr(args.data_dir)
        print(r["counts"], "unresolved", len(r["unresolved"]))
    elif args.refine:
        refine(args.data_dir)
    else:
        r = audit(args.data_dir)
        print(r["counts"], "unresolved", len(r["unresolved"]))
