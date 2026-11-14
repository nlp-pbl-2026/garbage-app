"""Shared, dependency-free contract for immutable Flutter Web releases."""

import mimetypes
from pathlib import Path, PurePosixPath
import re

from fetch_frontend_data import (
    ROOT,
    api_url,
    decode,
    encode,
    digest,
    require,
    dataset_version,
    descriptors,
    validate_assets,
    expected_files,
)

FLUTTER_VERSION = "3.47.1"
IMMUTABLE_CACHE = "public,max-age=31536000,immutable"
ENTRY_CACHE = "no-cache,max-age=0,must-revalidate"
UI_PATH = Path("assets/assets/data")


def release_id(value):
    require(
        isinstance(value, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{5,99}", value),
        "Invalid release ID",
    )
    return value


def safe_path(value):
    require(
        isinstance(value, str) and value and "\\" not in value, "Unsafe release path"
    )
    path = PurePosixPath(value)
    require(
        not path.is_absolute()
        and all(p not in {".", "..", ""} for p in value.split("/")),
        "Unsafe release path",
    )
    require(not any(p.startswith(".") for p in path.parts), "Hidden release file")
    require(
        path.suffix.lower()
        not in {".npz", ".pdf", ".db", ".sqlite", ".jsonl", ".tfstate"}
        and path.name not in {"items.csv", "credentials", "config-before.json"},
        "Backend/source data must not be published",
    )
    return value


def content_type(name):
    return {
        ".js": "application/javascript",
        ".mjs": "application/javascript",
        ".wasm": "application/wasm",
        ".json": "application/json",
        ".html": "text/html; charset=utf-8",
    }.get(
        Path(name).suffix, mimetypes.guess_type(name)[0] or "application/octet-stream"
    )


def prepare_web_manifest(site):
    # The HTML base points at immutable assets, but installed apps must reopen
    # the current root entry rather than being pinned to an old release URL.
    path = Path(site) / "manifest.json"
    value = decode(path.read_bytes())
    value.update(id="/", start_url="/", scope="/")
    path.write_bytes(encode(value))


def describe_site(site):
    result = {}
    for path in sorted(site.rglob("*")):
        require(not path.is_symlink(), "Release symlinks are not accepted")
        if path.is_file():
            name = safe_path(path.relative_to(site).as_posix())
            body = path.read_bytes()
            result[name] = {
                "sha256": digest(body),
                "bytes": len(body),
                "content_type": content_type(name),
            }
    require(
        result
        and len(result) <= 3000
        and sum(d["bytes"] for d in result.values()) < 512 * 1024**2,
        "Missing/oversized web build",
    )
    require(
        "release.json" not in result, "release.json is reserved for deployment metadata"
    )
    return result


def validate_release(folder):
    folder = Path(folder)
    require(not folder.is_symlink(), "Release directory must not be a symlink")
    require(
        not (folder / "release.json").is_symlink(), "Manifest must not be a symlink"
    )
    manifest = decode((folder / "release.json").read_bytes())
    require(manifest["schema_version"] == 1, "Unsupported web release")
    rid = release_id(manifest["release_id"])
    require(re.fullmatch(r"[0-9a-f]{40}", manifest["git_sha"]), "Invalid source commit")
    require(manifest["flutter_version"] == FLUTTER_VERSION, "Unexpected Flutter SDK")
    require(
        api_url(manifest["api_base_url"]) == manifest["api_base_url"], "Invalid API URL"
    )
    site = folder / "site"
    require(site.is_dir() and not site.is_symlink(), "Missing web build")
    require(describe_site(site) == manifest["files"], "Web release checksum mismatch")
    index = (site / "index.html").read_text()
    require(f'<base href="/releases/{rid}/">' in index, "Release base href mismatch")
    require('src="flutter_bootstrap.js"' in index, "Unexpected Flutter entry point")
    web_manifest = decode((site / "manifest.json").read_bytes())
    require(
        all(web_manifest.get(k) == "/" for k in ("id", "start_url", "scope")),
        "Installed apps must reopen the current root release",
    )
    ui_root = site / UI_PATH
    ui = decode((ui_root / "frontend_data_manifest.json").read_bytes())
    require(
        ui.get("publication_status") == "enabled",
        "Only public UI snapshots may be deployed",
    )
    require(
        ui["dataset_version"]
        == manifest["dataset_version"]
        == dataset_version(ui["files"]),
        "UI release version mismatch",
    )
    expected = {
        c["id"]
        for c in decode((ROOT / "data/regions/catalog.json").read_bytes())[
            "municipalities"
        ]
    }
    require(
        len(expected) == 20
        and {c["id"] for c in ui["catalog"]["municipalities"]} == expected,
        "All twenty municipalities are required",
    )
    require(
        set(ui["files"]) == set(expected_files(ui["catalog"])), "Unexpected UI paths"
    )
    files = {name: (ui_root / name).read_bytes() for name in ui["files"]}
    validate_assets(ui["catalog"], files)
    require(
        descriptors(ui["catalog"], files) == ui["files"], "Bundled UI asset mismatch"
    )
    return manifest
