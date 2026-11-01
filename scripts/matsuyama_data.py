#!/usr/bin/env python3
"""Fetch, inspect and build Matsuyama data without calling a paid API.

Registry/review metadata is tracked; official PDFs and derived records are not.
Run with backend/.venv/bin/python; extraction additionally needs PyMuPDF.
"""
from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/matsuyama"
REGISTRY = DATA / "registry.json"
GUIDE_URL = "https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/bunbetsu_jiten_katei.files/R7.4gomibunbeturyouP16-44.pdf"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_auxiliary_source(path: Path, expected: str) -> dict:
    """Check full bytes, allowing only the CMS's unrelated recommendation block.

    These two reviewed HTML snapshots had an empty recommendation line. Keep
    the downloaded bytes intact and compare the rest byte-for-byte with that
    snapshot; never normalize the actual disposal rules or address tables.
    """
    content = path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    normalization = "none"
    if actual != expected:
        if path.name not in {"kateigomi_matsuyama.html", "kateigomi_nakajima.html"}:
            raise ValueError(f"Official auxiliary source changed; review required: {path.name}")
        normalized, count = re.subn(rb'<div id="lorecommend">[^\r\n]*?</div>', b"", content)
        if count != 1 or hashlib.sha256(normalized).hexdigest() != expected:
            raise ValueError(f"Official auxiliary source changed; review required: {path.name}")
        normalization = "remove_single_line_cms_lorecommend"
    return {"file": path.name, "source_sha256": actual,
            "verified_content_sha256": expected, "normalization": normalization}


def normalized_hash(record) -> str:
    payload = {k: record[k] for k in ("days", "exceptions")}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def restore_legacy():
    """Recover the exact ignored source matching the existing index IDs; no API."""
    import numpy as np
    source = DATA / "common/knowledge/items.csv"
    content = subprocess.check_output(["git", "show", "d28ea90:data/regions/matsuyama/common/knowledge/items.csv"], cwd=ROOT)
    if not source.exists():
        source.write_bytes(content)
    elif source.read_bytes() != content:
        raise ValueError("Existing CSV differs from the legacy source; refusing to adopt it with old vectors")
    rows = list(csv.DictReader(source.open(encoding="utf-8-sig", newline="")))
    index_path = source.parent / "item_embeddings.npz"
    with np.load(index_path, allow_pickle=False) as index:
        ids = list(map(str, index["item_ids"]))
        if len(rows) != 1756 or len(set(ids)) != len(ids) or ids != [r["item_id"] for r in rows]:
            raise ValueError("Legacy CSV/index IDs or ordering do not match")
        vectors = index["vectors"]
        if vectors.shape != (1756, 1024) or not np.isfinite(vectors).all():
            raise ValueError("Invalid legacy vectors")
        if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=.002):
            raise ValueError("Legacy vectors are not normalized")
        manifest = {"schema_version": 1, "profile_id": "matsuyama_hojo", "source_sha256": sha256(source),
                    "index_sha256": sha256(index_path), "model_id": str(index["model_id"]),
                    "dimensions": int(index["dimensions"]), "item_count": len(ids),
                    "legacy_origin_commit": "d28ea90", "source_hash_recorded_at_creation": False,
                    "verification": "ids_order_model_dimensions_finite_normalized_checked",
                    "official_source_url": GUIDE_URL,
                    "unclassified_items": [r["item_id"] for r in rows if not r["category"]]}
    write_json(source.parent / "index_manifest.json", manifest)
    print(f"Checked {len(rows)} legacy rows/vectors; {len(manifest['unclassified_items'])} rows retain conditional/blank categories")


def fetch_auxiliary():
    base = "https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/"
    urls = [base + "chikukensaku-" + kana + ".html" for kana in ["a", "ka", "sa", "ta", "na", "ha", "ma", "yarawa"]]
    urls += [GUIDE_URL, base + "kateigomi_matsuyama.html", base + "kateigomi_nakajima.html"]
    expected = read_json(DATA / "auxiliary_sources.json")["sources"]
    if set(expected) != {url.rsplit("/", 1)[-1] for url in urls}:
        raise ValueError("Unreviewed auxiliary source list")
    records = []
    for url in urls:
        target = DATA / "source" / url.rsplit("/", 1)[-1]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            subprocess.run(["curl", "-fsSL", "--retry", "2", "--max-time", "45", url, "-o", str(target)], check=True)
        records.append({**check_auxiliary_source(target, expected[target.name]), "url": url})
    write_json(DATA / "source/auxiliary-verification.json", {"sources": records})
    print(f"Checked {len(urls)} official address/rule/dictionary sources")


def build(registry):
    extraction = read_json(DATA / "source/extraction-review.json")
    reviews = read_json(DATA / "calendar_reviews.json")
    if extraction["failures"] or len(extraction["calendars"]) != len(registry["calendars"]):
        raise ValueError("Unresolved extraction failures")
    calendars = {}
    for source in registry["calendars"]:
        record = extraction["calendars"][source["id"]]
        review = reviews["calendars"][source["id"]]
        if (review["source_sha256"] != sha256(DATA / "source" / source["file"])
                or review["source_sha256"] != record["source_sha256"]
                or review["normalized_sha256"] != normalized_hash(record)
                or review["verification_status"] != "checked"):
            raise ValueError(f"Review/hash mismatch: {source['id']}")
        calendars[source["id"]] = {"days": record["days"], "exceptions": record["exceptions"],
                                    "source_url": source["url"], "source_sha256": record["source_sha256"],
                                    "verification_status": "checked"}
    bundle = {key: registry[key] for key in ["schema_version", "municipality_id", "version", "fiscal_year", "valid_from", "valid_to", "timezone"]}
    bundle["calendars"] = calendars
    path = DATA / "generated/calendar-2026.json"
    write_json(path, bundle)
    (ROOT / "frontend/assets/data/municipality_calendar.json").write_bytes(path.read_bytes())
    write_json(ROOT / "frontend/assets/data/municipality_registry.json", registry)
    print(f"Built identical backend/Flutter calendar bundles: {sha256(path)}")


def fetch_sources(registry):
    def download(source):
        path = DATA / "source" / source["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temporary = path.with_suffix(path.suffix + ".part")
            subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                            "--retry", "2", "--max-time", "45", source["url"],
                            "--output", str(temporary)], check=True)
            temporary.replace(path)
        digest = sha256(path)
        expected = source.get("sha256")
        if expected and expected != digest:
            raise ValueError(f"Official source changed; review required: {source['file']}")
        return {"file": source["file"], "url": source["url"], "sha256": digest,
                "retrieved_on": date.today().isoformat()}
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(download, registry["calendars"]))
    write_json(DATA / "source/downloads.json", records)
    print(f"Fetched/checked {len(records)} official calendars")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "fetch-aux", "extract", "restore-legacy", "build", "build-knowledge"])
    args = parser.parse_args()
    registry = read_json(REGISTRY)
    if args.command == "fetch":
        fetch_sources(registry)
    elif args.command == "fetch-aux":
        fetch_auxiliary()
    elif args.command == "restore-legacy":
        restore_legacy()
    elif args.command == "build":
        build(registry)
    elif args.command == "build-knowledge":
        from matsuyama_knowledge import build_addresses, build_nakajima_items
        for filename, digest in read_json(DATA / "auxiliary_sources.json")["sources"].items():
            check_auxiliary_source(DATA / "source" / filename, digest)
        address_data = build_addresses(DATA / "source", registry)
        with tempfile.TemporaryDirectory() as scratch:
            draft_items = Path(scratch) / "nakajima_items.csv"
            manifest = build_nakajima_items(
                DATA / "source/2026nakajimaoura.pdf", draft_items, registry)
            review = {
                "schema_version": 1,
                "version": registry["version"],
                "retrieved_on": registry["retrieved_on"],
                "address_entries": len(address_data["entries"]),
                "address_area_count": len({row["area_id"] for row in address_data["entries"]}),
                "address_source_sha256": {name: sha256(DATA / "source" / name)
                                          for name in [f"chikukensaku-{kana}.html" for kana in
                                                       ["a", "ka", "sa", "ta", "na", "ha", "ma", "yarawa"]]},
                "nakajima": manifest,
                "redistribution_status": "not_confirmed",
            }
            if read_json(DATA / "knowledge_reviews.json") != review:
                raise ValueError("Generated knowledge differs from reviewed metadata; inspect official sources")
            write_json(DATA / "generated/addresses.json", address_data)
            write_json(ROOT / "frontend/assets/data/municipality_addresses.json", address_data)
            output_items = DATA / "generated/nakajima_items.csv"
            output_items.write_bytes(draft_items.read_bytes())
            write_json(DATA / "generated/nakajima_items_manifest.json", manifest)
        print(f"Built {len(address_data['entries'])} address rows and {manifest['item_count']} Nakajima evidence rows")
    elif args.command == "extract":
        from matsuyama_pdf import read_calendar
        records, failures = {}, []
        for source in registry["calendars"]:
            try:
                record = read_calendar(DATA / "source" / source["file"], source["rule_profile_id"])
                record["source_sha256"] = sha256(DATA / "source" / source["file"])
                records[source["id"]] = record
            except (ValueError, KeyError) as error:
                failures.append({"calendar_id": source["id"], "error": str(error)})
        write_json(DATA / "source/extraction-review.json", {"calendars": records, "failures": failures})
        print(f"Extracted {len(records)}/43 calendars; failures={len(failures)}")
        for failure in failures:
            print(failure["calendar_id"], failure["error"])
        if failures:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
