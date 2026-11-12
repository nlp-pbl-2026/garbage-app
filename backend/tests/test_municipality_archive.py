"""Reject unsafe or conflicting shared data before writing into a checkout."""

import hashlib
import json
from pathlib import Path
import stat
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import import_municipality_archive as importer


@pytest.mark.parametrize(
    "name",
    [
        "../outside.csv",
        "/outside.csv",
        "data/regions/../outside.csv",
        "data\\regions\\outside.csv",
    ],
)
def test_unsafe_archive_paths_are_rejected_before_extraction(tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr(name, b"unsafe")
    with pytest.raises(ValueError, match="Unsafe ZIP entry"):
        importer.inspect_archive(archive, install=True)
    assert not (tmp_path / "outside.csv").exists()


def test_symlink_entry_is_rejected(tmp_path):
    archive = tmp_path / "link.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        info = zipfile.ZipInfo("data/regions/ozu/source/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        stream.writestr(info, "/outside")
    with pytest.raises(ValueError, match="Unsafe ZIP entry"):
        importer.inspect_archive(archive)


def bundle(path, *, wrong_hash=False):
    files = {
        "README.md": b"fixture",
        "PACKAGE_MANIFEST.json": json.dumps({}).encode(),
        "data/regions/ozu/knowledge/items.csv": b"new data",
    }
    sums = "".join(
        f"{hashlib.sha256(body).hexdigest()}  {name}\n" for name, body in files.items()
    )
    if wrong_hash:
        files["data/regions/ozu/knowledge/items.csv"] = b"tampered data"
    with zipfile.ZipFile(path, "w") as stream:
        for name, body in files.items():
            stream.writestr(name, body)
        stream.writestr("SHA256SUMS.txt", sums)


def test_existing_different_file_and_root_readme_are_never_overwritten(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(importer, "ROOT", tmp_path)
    existing = tmp_path / "data/regions/ozu/knowledge/items.csv"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"keep original")
    (tmp_path / "README.md").write_bytes(b"keep project readme")
    archive = tmp_path / "conflict.zip"
    bundle(archive)
    with pytest.raises(ValueError, match="Existing file differs"):
        importer.inspect_archive(archive, install=True)
    assert existing.read_bytes() == b"keep original"
    assert (tmp_path / "README.md").read_bytes() == b"keep project readme"


def test_tampered_payload_fails_checksum_before_install(tmp_path, monkeypatch):
    monkeypatch.setattr(importer, "ROOT", tmp_path)
    archive = tmp_path / "tampered.zip"
    bundle(archive, wrong_hash=True)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        importer.inspect_archive(archive, install=True)
    assert not (tmp_path / "data").exists()
