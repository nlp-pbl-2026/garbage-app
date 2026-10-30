"""Derive Nakajima's evidence and official address mapping from local sources."""
from __future__ import annotations

import csv
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata


class _Table(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def norm(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace(" ", "").replace("　", "")


def build_addresses(source_dir: Path, registry: dict) -> dict:
    area_ids = {a["name"]: a["id"] for a in registry["collection_areas"]}
    entries, warnings = [], []
    for kana in ["a", "ka", "sa", "ta", "na", "ha", "ma", "yarawa"]:
        name = f"chikukensaku-{kana}.html"
        path = source_dir / name
        parser = _Table()
        parser.feed(path.read_text(encoding="utf-8"))
        for cells in parser.rows:
            if len(cells) != 4 or cells[0] == "住所" or not cells[0]:
                continue
            area = cells[2].removesuffix("地区").strip()
            if area not in area_ids:
                warnings.append((name, cells))
                continue
            town = norm(cells[0])
            base_town = re.sub(r"[（(][0-9]+[）)]$", "", town)
            entries.append({"town": town, "lookup_town": base_town,
                            "area_id": area_ids[area], "bulky_group": cells[3] if cells[3] in "ABCD" else None,
                            "source_url": "https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/" + name,
                            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if warnings:
        raise ValueError(f"Unknown official area labels: {warnings[:8]}")
    if len(entries) < 600:
        raise ValueError(f"Unexpectedly short official address list: {len(entries)}")
    return {"schema_version": 1, "municipality_id": "38201", "version": registry["version"],
            "verification_status": "official_html_table_checked", "entries": entries}


_SECTION_RECTS = {
    "可燃": (18, 890, 188, 1640), "プラ": (189, 890, 350, 1307),
    "びん": (352, 890, 509, 1127), "紙類": (352, 1127, 509, 1640),
    "ペット": (189, 1307, 350, 1640),
    "粗大": (513, 890, 674, 1172), "金・ガ": (513, 1172, 674, 1535),
    "缶": (675, 890, 835, 1172), "埋立": (675, 1172, 835, 1640),
    "水銀": (836, 890, 993, 1290),
}


def build_nakajima_items(source_pdf: Path, output: Path, registry: dict) -> dict:
    import pymupdf

    page = pymupdf.open(source_pdf)[0]
    names = {"可燃": "可燃ごみ", "プラ": "プラスチック製容器包装", "びん": "びん類",
             "紙類": "紙類", "ペット": "ペットボトル", "粗大": "粗大ごみ",
             "金・ガ": "金物・ガラス類", "缶": "缶類", "埋立": "埋立ごみ", "水銀": "水銀ごみ"}
    rows = []
    source_url = next(c["url"] for c in registry["calendars"] if c["file"] == source_pdf.name)
    for category, rect in _SECTION_RECTS.items():
        text = page.get_text(clip=pymupdf.Rect(rect), sort=True)
        text = re.sub(r"第\s*[1-5１-５]\s*[月火水木金土日]\s*曜\s*日?", "収集日は地区別カレンダーを確認", text)
        if norm(names[category]) not in norm(text):
            raise ValueError(f"Official Nakajima section not found: {category}")
        # The whole section is the evidence. Only explicit bullet examples become items.
        rows.append({"item_id": "nk-rule-" + hashlib.sha256(category.encode()).hexdigest()[:12],
                     "item": names[category], "reading": "", "search_text": names[category],
                     "category": category, "category_display": names[category], "note": text.strip(),
                     "rule_ref": "中島地域2026年度カレンダー掲載の分別説明", "source_url": source_url,
                     "verification_status": "official_section_checked"})
        for line in text.splitlines():
            bullet = re.match(r"\s*●\s*(.+)", line)
            if not bullet:
                continue
            item = " ".join(bullet[1].strip().split())
            if len(item) < 2 or len(item) > 65:
                continue
            rows.append({"item_id": "nk-item-" + hashlib.sha256((category + item).encode()).hexdigest()[:12],
                         "item": item, "reading": "", "search_text": item,
                         "category": category, "category_display": names[category], "note": text.strip(),
                         "rule_ref": "中島地域2026年度カレンダー掲載の品目例", "source_url": source_url,
                         "verification_status": "official_bullet_checked"})
    # Explicit negative rules are evidence but not a scheduled collection type.
    prohibition = page.get_text(clip=pymupdf.Rect(828, 1365, 1165, 1630), sort=True)
    if "出してはいけない" not in prohibition:
        raise ValueError("Missing island prohibition section")
    rows.append({"item_id": "nk-rule-not-collected", "item": "市で収集しないもの",
                 "reading": "", "search_text": "排出禁止 収集しない", "category": "禁止",
                 "category_display": "市で収集しないもの", "note": prohibition,
                 "rule_ref": "中島地域2026年度カレンダー掲載の排出禁止案内", "source_url": source_url,
                 "verification_status": "official_section_checked"})
    if len({r["item_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate Nakajima item ID")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {"source_url": source_url, "source_sha256": hashlib.sha256(source_pdf.read_bytes()).hexdigest(),
            "item_count": len(rows), "category_codes": sorted({r["category"] for r in rows}),
            "verification_status": "official_sections_and_bullets_checked",
            "scope": "Calendar guide sections and examples; not a complete Nakajima item dictionary"}
