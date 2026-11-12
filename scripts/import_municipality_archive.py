#!/usr/bin/env python3
"""Inspect the assigned ten-municipality ZIP; --install copies missing ignored files only."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import unicodedata
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SLUGS = {
    "ozu",
    "tobe",
    "ainan",
    "kihoku",
    "matsuno",
    "uchiko",
    "masaki",
    "kamijima",
    "shikokuchuo",
    "seiyo",
}
METADATA = {"README.md", "PACKAGE_MANIFEST.json", "SHA256SUMS.txt"}


def inspect_archive(path, install=False):
    digest = lambda body: hashlib.sha256(body).hexdigest()
    with zipfile.ZipFile(path) as archive:
        entries, seen = {}, set()
        for info in archive.infolist():
            name = info.filename
            relative = PurePosixPath(name)
            key = unicodedata.normalize("NFC", name).casefold()
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or "\\" in name
                or ":" in name
                or key in seen
                or info.orig_filename != name
                or str(relative) != name.rstrip("/")
                or info.flag_bits & 1
                or stat.S_IFMT(info.external_attr >> 16)
                not in (0, stat.S_IFREG, stat.S_IFDIR)
            ):
                raise ValueError(f"Unsafe ZIP entry: {name!r}")
            seen.add(key)
            if not info.is_dir():
                if info.file_size > 64 * 1024**2:
                    raise ValueError(f"Unexpectedly large entry: {name}")
                entries[name] = info
        if sum(e.file_size for e in entries.values()) > 512 * 1024**2:
            raise ValueError("Archive exceeds the reviewed bundle size allowance")
        expected = {}
        for line in archive.read("SHA256SUMS.txt").decode("utf-8-sig").splitlines():
            sha, name = line.split("  ", 1)
            if (
                name in expected
                or len(sha) != 64
                or any(c not in "0123456789abcdef" for c in sha)
            ):
                raise ValueError("Invalid SHA256SUMS entry")
            expected[name] = sha
        if set(expected) != set(entries) - {"SHA256SUMS.txt"}:
            raise ValueError("ZIP and SHA256SUMS file lists differ")
        actual, new, identical = {}, [], []
        for name, entry in entries.items():
            actual[name] = digest(archive.read(entry))  # also verifies ZIP CRC
            if name in expected and actual[name] != expected[name]:
                raise ValueError(f"SHA-256 mismatch: {name}")
            if name in METADATA:
                continue
            parts = PurePosixPath(name).parts
            if (
                len(parts) < 4
                or parts[:2] != ("data", "regions")
                or parts[2] not in SLUGS
            ):
                raise ValueError(f"Unexpected payload path: {name}")
            target = ROOT / name
            if any(p.is_symlink() for p in (target, *target.parents)):
                raise ValueError(f"Symlink destination: {name}")
            if target.exists():
                if digest(target.read_bytes()) != actual[name]:
                    raise ValueError(
                        f"Existing file differs; review before overwriting: {name}"
                    )
                identical.append(name)
            else:
                if subprocess.run(
                    ["git", "check-ignore", "--quiet", name], cwd=ROOT
                ).returncode:
                    raise ValueError(f"New file is not Git-ignored: {name}")
                new.append(name)
        package = json.loads(archive.read("PACKAGE_MANIFEST.json"))
        if (
            package["municipality_count"] != 10
            or {c["slug"] for c in package["municipalities"]} != SLUGS
        ):
            raise ValueError("Expected the assigned ten municipalities")
        for city in package["municipalities"]:
            base = f"data/regions/{city['slug']}"
            registry = json.loads((ROOT / base / "registry.json").read_text())
            for key in ("municipality_id", "version", "valid_from", "valid_to"):
                if registry[key] != city[key]:
                    raise ValueError(f"Registry/package mismatch: {base}/{key}")
            for profile in registry["rule_profiles"].values():
                csv_path, npz_path = (
                    f"{base}/{profile[k]}"
                    for k in ("items_path", "embedding_index_path")
                )
                manifest_path = str(
                    PurePosixPath(csv_path).parent / "index_manifest.json"
                )
                manifest = json.loads(archive.read(manifest_path))
                if (
                    manifest["source_sha256"] != actual[csv_path]
                    or manifest["index_sha256"] != actual[npz_path]
                    or manifest["item_count"] != city["item_count"]
                    or manifest["model_id"] != city["embedding_model"]
                    or manifest["dimensions"] != city["embedding_dimensions"]
                ):
                    raise ValueError(f"CSV/index/package mismatch: {base}")
                if f"{base}/{profile['calendar_path']}" not in entries:
                    raise ValueError(f"Missing calendar: {base}")
        # All checks complete before creating any repository file. Metadata is never installed.
        if install:
            for name in new:
                target = ROOT / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(archive.read(name))
        return dict(
            archive_sha256=digest(Path(path).read_bytes()),
            files=len(entries),
            archive_bytes=Path(path).stat().st_size,
            uncompressed_bytes=sum(e.file_size for e in entries.values()),
            sha256_checked=len(expected),
            crc_checked=len(entries),
            new_files=len(new),
            identical_files=len(identical),
            installed_files=len(new) if install else 0,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            inspect_archive(args.zip_path, args.install), ensure_ascii=False, indent=2
        )
    )
