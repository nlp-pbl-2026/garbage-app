"""Independent offline OCR / rendered-glyph checks of the Imabari sources.

Only OCR-labelled templates train the glyph matcher. Uncertain dates fail the
build; JSON equality is never treated as evidence of a correct PDF extraction.
"""

from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess

from imabari_pdf import (
    compact,
    mainland_dictionary,
    sekizen_dictionary,
    month_cells,
    numbered_calendar,
    glyphs,
    text_in,
)


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_ocr(data):
    import pymupdf

    out = data / "generated/ocr"
    out.mkdir(parents=True, exist_ok=True)
    manifest = []

    def render(page, rect, key, source):
        target = out / (key + ".png")
        page.get_pixmap(
            matrix=pymupdf.Matrix(3, 3), clip=pymupdf.Rect(rect), alpha=False
        ).save(target)
        manifest.append(
            dict(
                id=key,
                image=str(target.resolve()),
                image_sha256=digest(target),
                source_sha256=digest(source),
            )
        )

    for source in sorted((data / "source").glob("calendar-*.pdf")):
        page = pymupdf.open(source)[0]
        key = source.stem
        if "tokku" in key:
            render(page, page.rect, key, source)
        else:
            for month in [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]:
                render(page, month_rect(month), f"{key}-m{month:02}", source)
            render(page, [0, 0, 842, 299], key + "-legend", source)
    for filename, pages in [
        ("gomi_bunbetu.pdf", range(1, 15)),
        ("gomi_hayamihyo_sekizen_2019.pdf", range(8)),
        ("sakuin.pdf", range(4)),
        ("gomi_guide.pdf", range(16)),
        ("dasikata_sekizen01.pdf", [0]),
        ("dasikata_sekizen02.pdf", [0]),
    ]:
        source = data / "source" / filename
        doc = pymupdf.open(source)
        for pi in pages:
            render(doc[pi], doc[pi].rect, f"{source.stem}-p{pi+1:02}", source)
    write(out / "manifest.json", manifest)
    root = Path(__file__).resolve().parents[1]
    binary = "/private/tmp/imabari-ocr"
    subprocess.run(
        [
            "swiftc",
            "-module-cache-path",
            "/private/tmp/imabari-swift-cache",
            str(root / "scripts/toon_ocr.swift"),
            "-o",
            binary,
        ],
        check=True,
    )
    subprocess.run([binary, str(out / "manifest.json"), str(out)], check=True)
    refine_ocr(data)


def refine_ocr(data):
    """Re-render only uncertain cells at larger scale; still entirely offline."""
    import pymupdf

    candidate = audit(data, inspect_only=True, ignore_refine=True)
    out = data / "generated/ocr"
    manifest = []
    rows = {
        r["item_id"]: (r, n)
        for reader, n in [
            (mainland_dictionary, "gomi_bunbetu.pdf"),
            (sekizen_dictionary, "gomi_hayamihyo_sekizen_2019.pdf"),
        ]
        for r in reader(data / "source" / n)[0]
    }
    for value in candidate["unresolved"]:
        if value["kind"] == "date":
            number, day = value["id"].split(":")
            filename = f"calendar-{number}.pdf"
            page = pymupdf.open(data / "source" / filename)[0]
            rect = next(r for d, r, o in month_cells(int(day[5:7])) if d == day)
            key = "refine-date-" + value["id"].replace(":", "-")
        elif value["kind"] == "dictionary":
            row, filename = rows[value["id"]]
            page = pymupdf.open(data / "source" / filename)[row["pdf_page"] - 1]
            x0, y0, x1, y1 = row["category_rect"]
            rect = [x0 - 2, y0 - 2, x1 + 2, y1 + 2]
            key = "refine-" + value["id"]
        else:
            continue
        target = out / (key + ".png")
        page.get_pixmap(
            matrix=pymupdf.Matrix(8, 8), clip=pymupdf.Rect(rect), alpha=False
        ).save(target)
        manifest.append(
            dict(
                id=key,
                image=str(target.resolve()),
                image_sha256=digest(target),
                source_sha256=digest(data / "source" / filename),
            )
        )
    write(out / "refine-manifest.json", manifest)
    subprocess.run(
        ["/private/tmp/imabari-ocr", str(out / "refine-manifest.json"), str(out)],
        check=True,
    )


def month_rect(month):
    rects = [r for d, r, o in month_cells(month)]
    return [
        min(r[0] for r in rects),
        min(r[1] for r in rects) - 32,
        max(r[2] for r in rects),
        max(r[3] for r in rects) + 0.5,
    ]


def nearby(observations, rect, image_rect):
    ox, oy, x1, y1 = image_rect
    w, h = x1 - ox, y1 - oy
    return [
        o
        for o in observations
        if rect[0] <= ox + (o["box"][0] + o["box"][2]) / 2 * w < rect[2]
        and rect[1] <= oy + (o["box"][1] + o["box"][3]) / 2 * h < rect[3]
    ]


def audit(data, *, inspect_only=False, ignore_refine=False):
    import numpy as np
    import pymupdf
    from PIL import Image

    root = data / "generated/ocr"
    meta = {r["id"]: r for r in read(root / "manifest.json")}
    if not ignore_refine and (root / "refine-manifest.json").exists():
        meta.update({r["id"]: r for r in read(root / "refine-manifest.json")})
    checked = set()

    def obs(key, source):
        record = read(root / (key + ".json"))
        if key not in checked:
            if (
                record["source_sha256"] != digest(source)
                or record["image_sha256"] != digest(root / (key + ".png"))
                or meta[key]["image_sha256"] != record["image_sha256"]
            ):
                raise ValueError("Stale OCR: " + key)
            checked.add(key)
        return record["observations"]

    cache = [None, None]

    def shape(page, rect, kind="number"):
        key = page.parent.name, page.number
        if cache[0] != key:
            p = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=False)
            cache[:] = [key, Image.frombytes("RGB", (p.width, p.height), p.samples)]
        a = np.asarray(cache[1].crop(tuple(round(v * 3) for v in rect))).astype(int)
        if not a.size:
            return None
        if kind in {"category", "white_category"}:
            corner = a[1, 1]
            mask = (
                (np.min(a, axis=2) > 200)
                if kind == "white_category" or max(corner) < 100
                else (np.max(a, axis=2) < 130)
            )
            size = (25, 55)
        else:
            mask = (
                (np.max(a, axis=2) < 110)
                | ((a[:, :, 0] > 180) & (a[:, :, 1] < 90) & (a[:, :, 2] < 100))
                | ((a[:, :, 0] < 60) & (a[:, :, 1] > 90) & (a[:, :, 2] > 150))
            )
            size = (45, 35)
        yy, xx = np.where(mask)
        if not len(xx):
            return None
        mask = mask[yy.min() : yy.max() + 1, xx.min() : xx.max() + 1]
        return (
            np.asarray(
                Image.fromarray((mask * 255).astype("uint8")).resize(
                    size, Image.Resampling.BILINEAR
                )
            ).astype(float)
            / 255
        )

    def nearest(value, templates):
        if value is None:
            return None
        return min(
            (float(np.mean(np.abs(value - bitmap))), label)
            for label, bitmaps in templates.items()
            for bitmap in bitmaps
        )

    stats = Counter()
    unresolved = []
    date_entries = []
    templates = {}
    source_specs = {s["file"]: s for s in read(data / "sources.json")["sources"]}
    for n in range(1, 43):
        source = data / "source" / f"calendar-{n:02}.pdf"
        page = pymupdf.open(source)[0]
        native = glyphs(page)
        caption = (
            text_in(native, [0, 0, 842, 90])
            if native
            else "".join(o["text"] for o in obs(f"calendar-{n:02}-legend", source))
        )
        expected_caption = re.sub(
            r"地区[（(]PDF.*$", "", source_specs[source.name]["label"]
        ).strip()
        if compact(expected_caption) not in compact(
            caption
        ) or "令和8年度" not in compact(caption):
            unresolved.append(
                dict(
                    kind="calendar_caption",
                    id=str(n),
                    expected=expected_caption,
                    actual=caption[:120],
                )
            )
        else:
            stats["calendar_captions"] += 1
        number_spans = [
            s
            for b in page.get_text("dict")["blocks"]
            for l in b.get("lines", [])
            for s in l["spans"]
            if re.fullmatch(r"\d{1,2}", s["text"]) and s["size"] > 7
        ]
        # Date checks do not use the extracted collection JSON.
        for month in [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]:
            seen = obs(f"calendar-{n:02}-m{month:02}", source)
            image_rect = month_rect(month)
            for day, rect, overflow in month_cells(month):
                d = date.fromisoformat(day)
                expected = str(d.day)
                cell_seen = nearby(
                    seen, [rect[0], rect[1] - 4, rect[2], rect[3] - 8], image_rect
                )
                numbers = [
                    number
                    for o in cell_seen
                    for number in re.findall(r"\d+", compact(o["text"]))
                ]
                passed = expected in numbers
                first = (date(d.year, d.month, 1).weekday() + 1) % 7
                shared = (
                    d.day + 7 <= __import__("calendar").monthrange(d.year, d.month)[1]
                    and (d.day + first - 1) // 7 == 4
                ) or overflow
                number_rect = [rect[0] + 2, rect[1] + 1, rect[2] - 2, rect[1] + 23]
                if shared:
                    if d.weekday() == 6:
                        number_rect = [
                            rect[0] + (18 if overflow else 1),
                            rect[1] + 1,
                            rect[2] - (1 if overflow else 18),
                            rect[1] + 17,
                        ]
                    else:
                        number_rect = [
                            rect[0] + 1,
                            rect[1] + (19 if overflow else 1),
                            rect[0] + 17,
                            rect[1] + (34 if overflow else 17),
                        ]
                bitmap = shape(page, number_rect)
                alternatives = []
                if not passed:
                    for span in number_spans:
                        x0, y0, x1, y1 = span["bbox"]
                        if (
                            span["text"] == expected
                            and rect[0] <= (x0 + x1) / 2 < rect[2]
                            and rect[1] - 4 <= (y0 + y1) / 2 < rect[3] - 6
                        ):
                            value = shape(
                                page,
                                [
                                    x0 - 0.5,
                                    max(y0 + 3, rect[1] + 2),
                                    x1 + 0.5,
                                    min(y1 - 1, rect[3] - 6),
                                ],
                            )
                            if value is not None:
                                alternatives.append(value)
                # Do not mix the normal and condensed shared-cell typefaces.
                family = "shared" if shared else "normal"
                if passed and bitmap is not None:
                    bank = templates.setdefault(family, {})
                    if len(bank.setdefault(expected, [])) < 8:
                        bank[expected].append(bitmap)
                date_entries.append(
                    (
                        f"{n:02}:{day}",
                        expected,
                        passed,
                        [bitmap, *alternatives],
                        family,
                        numbers,
                    )
                )
    manual = (
        read(data / "manual_image_reviews.json")
        if not ignore_refine and (data / "manual_image_reviews.json").exists()
        else {}
    )
    for name, sha in manual.get("source_sha256", {}).items():
        if digest(data / "source" / name) != sha:
            raise ValueError("Manual review source changed")
    for key, label, passed, bitmaps, family, numbers in date_entries:
        if passed:
            stats["date_ocr"] += 1
            continue
        refine = "refine-date-" + key.replace(":", "-")
        if not ignore_refine and refine in meta:
            source = data / "source" / ("calendar-" + key.split(":")[0] + ".pdf")
            numbers = [
                v
                for o in obs(refine, source)
                for v in re.findall(r"\d+", compact(o["text"]))
            ]
            if label in numbers:
                stats["date_enlarged_ocr"] += 1
                continue
        candidates = [
            nearest(bitmap, templates.get(family, {}))
            for bitmap in bitmaps
            if bitmap is not None
        ]
        match = min(candidates) if candidates else None
        if match and match[1] == label and match[0] < 0.16:
            stats["date_raster_template"] += 1
        elif manual.get("dates", {}).get(key) == label:
            stats["date_manual"] += 1
        else:
            unresolved.append(
                dict(kind="date", id=key, label=label, ocr=numbers, nearest=match)
            )
    entries = []
    templates = {}
    cat_labels = {
        "burnable": "可燃",
        "non_burnable": "不燃",
        "plastics": "プラ",
        "resources": "資源",
        "bulky": "粗大",
        "hazardous": "有害",
        "dangerous": "危険",
        "not_collected": "禁止",
        "consult": "ー",
    }
    for profile, reader, filename in [
        ("mainland", mainland_dictionary, "gomi_bunbetu.pdf"),
        ("sekizen", sekizen_dictionary, "gomi_hayamihyo_sekizen_2019.pdf"),
    ]:
        source = data / "source" / filename
        doc = pymupdf.open(source)
        rows, _ = reader(source)
        for row in rows:
            page = doc[row["pdf_page"] - 1]
            rect = row["category_rect"]
            seen = obs(f'{source.stem}-p{row["pdf_page"]:02}', source)
            text = compact(
                "".join(o["text"] for o in nearby(seen, rect, list(page.rect)))
            )
            label = row["category"]
            if profile == "mainland":
                expected = cat_labels[label]
            else:
                expected = {
                    "burnable": "燃える",
                    "non_burnable": "燃えない",
                    "resources": "資源",
                    "bulky": "粗大",
                    "hazardous_dangerous": "有害危険",
                    "not_collected": "―",
                }[label]
            passed = expected in text
            refine = "refine-" + row["item_id"]
            if not ignore_refine and refine in meta:
                refined = compact("".join(o["text"] for o in obs(refine, source)))
                if expected in refined or (
                    profile == "sekizen"
                    and label == "not_collected"
                    and re.search(r"[-―—ー]", refined)
                ):
                    passed = True
            bitmap = shape(
                page,
                [rect[0] + 1, rect[1] + 1, rect[2] - 1, rect[3] - 1],
                kind=(
                    "white_category"
                    if profile == "mainland"
                    and label in {"not_collected", "dangerous", "hazardous"}
                    else "category"
                ),
            )
            family = profile
            if passed and bitmap is not None:
                bank = templates.setdefault(family, {})
                if len(bank.setdefault(label, [])) < 12:
                    bank[label].append(bitmap)
            entries.append((row["item_id"], label, passed, bitmap, family, text))
    for key, label, passed, bitmap, family, text in entries:
        if passed:
            stats["dictionary_category_ocr"] += 1
            continue
        match = nearest(bitmap, templates.get(family, {}))
        if match and match[1] == label and match[0] < 0.14:
            stats["dictionary_category_raster"] += 1
        elif manual.get("dictionary", {}).get(key) == label:
            stats["dictionary_category_manual"] += 1
        else:
            unresolved.append(
                dict(kind="dictionary", id=key, label=label, ocr=text, nearest=match)
            )
    # Special PDFs print rules instead of 365 date cells. Verify the independent
    # OCR against all rule/exception tokens used by the expansion, not against
    # our own generated dates.
    special_tokens = {
        "12_tokku": [
            "毎週水曜日",
            "祝日が水曜日",
            "翌日の木曜日",
            "毎月1回",
            "第2金曜日",
            "8：40",
            "出航時刻",
        ],
        "36_tokku": [
            "毎週金曜日",
            "1月1日～3日",
            "5月5日",
            "8月4日",
            "11月3日",
            "2月2日",
            "8：30",
        ],
    }
    for key, tokens in special_tokens.items():
        text = compact(
            "".join(
                o["text"]
                for o in obs(
                    "calendar-" + key, data / "source" / ("calendar-" + key + ".pdf")
                )
            )
        )
        caption = "来島・馬島・小島地区" if key == "12_tokku" else "鵜島地区"
        if compact(caption) not in text or "令和8年度" not in text:
            unresolved.append(dict(kind="special_caption", id=key, expected=caption))
        else:
            stats["calendar_captions"] += 1
        for token in tokens:
            if compact(token) not in text:
                unresolved.append(dict(kind="special_rule", id=key, token=token))
            else:
                stats["special_rule_tokens_ocr"] += 1
    result = dict(
        method="Apple Vision rendered-PDF OCR + OCR-seeded glyph templates; category colours from visible legend",
        numbered_calendar_dates=len(date_entries),
        dictionary_rows=len(entries),
        ocr_images=len(checked),
        counts=dict(stats),
        unresolved=unresolved,
    )
    write(data / "generated/image-audit-candidate.json", result)
    if unresolved and not inspect_only:
        raise ValueError(
            f"{len(unresolved)} unresolved PDF image checks; see generated/image-audit-candidate.json"
        )
    if not inspect_only and result != read(data / "image_reviews.json"):
        raise ValueError("Image review differs")
    return result
