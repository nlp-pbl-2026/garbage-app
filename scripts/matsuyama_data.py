#!/usr/bin/env python3
"""Fetch, inspect and build Matsuyama data without calling a paid API.

Registry/review metadata is tracked; official PDFs and derived records are not.
Run with backend/.venv/bin/python; extraction additionally needs PyMuPDF.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/matsuyama"
REGISTRY = DATA / "registry.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    parser.add_argument("command", choices=["fetch"])
    args = parser.parse_args()
    registry = read_json(REGISTRY)
    if args.command == "fetch":
        fetch_sources(registry)


if __name__ == "__main__":
    main()
