#!/usr/bin/env python3
"""Download a version-consistent UI snapshot using Python's standard library only.

No AWS credentials, official source PDFs, CSVs, indices or Python backend setup
are needed. A new directory is created only after every response is validated.
"""

import argparse
from pathlib import Path
import shutil
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlencode
from urllib.request import HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/app/services"))
from frontend_data_contract import (
    decode,
    encode,
    digest,
    require,
    expected_files,
    descriptors,
    dataset_version,
    validate_assets,
)

MAX_RESPONSE = 5 * 1024**2
MAX_DATA = 64 * 1024**2


def local_url(url):
    return urlsplit(url).hostname in {"127.0.0.1", "localhost", "::1"}


def api_url(value):
    parsed = urlsplit(value)
    require(
        parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment,
        "Use an API base URL without credentials/query/fragment",
    )
    require(
        parsed.scheme == "https" or (parsed.scheme == "http" and local_url(value)),
        "HTTPS is required except for loopback development",
    )
    return value.rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("API redirects are not accepted")


def read_json(url):
    for attempt in range(3):
        try:
            with build_opener(NoRedirect).open(url, timeout=45) as response:
                body = response.read(MAX_RESPONSE + 1)
            require(len(body) <= MAX_RESPONSE, "API response exceeds size limit")
            return decode(body)
        except HTTPError as error:
            if error.code not in {429, 502, 503, 504} or attempt == 2:
                raise ValueError(
                    f"UI data API returned HTTP {error.code}; check endpoint, data and publication settings"
                ) from None
            time.sleep(0.5 * 2**attempt)
    raise ValueError("UI data API unavailable")


def fetch(
    base_url, output, *, expected_ids, allow_unreviewed_local=False, get=read_json
):
    base_url = api_url(base_url)
    output = Path(output).absolute()
    require(
        not output.exists() and not output.is_symlink(),
        "Choose a NEW output directory; existing assets are never overwritten",
    )
    output = output.resolve()
    require(
        not allow_unreviewed_local or local_url(base_url),
        "Unreviewed data is permitted only from loopback",
    )
    manifest_url = base_url + "/api/frontend-data/manifest"
    manifest = get(manifest_url)
    require(manifest["schema_version"] == 1, "Unsupported export manifest")
    status = manifest["redistribution_status"]
    publication = manifest.get("publication_status")
    require(
        (publication == "enabled" and status in {"approved", "pending"})
        or (publication is None and status == "approved")
        or (
            status == "unreviewed_local_only"
            and publication in {None, "local_only"}
            and allow_unreviewed_local
            and local_url(base_url)
        ),
        "Redistribution/publication is not enabled; local-only testing requires explicit opt-in",
    )
    catalog = manifest["catalog"]
    require(
        {c["id"] for c in catalog["municipalities"]} == set(expected_ids),
        "The API does not contain the expected municipality set",
    )
    owners = expected_files(catalog)
    description = manifest["files"]
    require(set(description) == set(owners), "Manifest asset references are incomplete")
    require(
        all(
            info.get("municipality_id") == owners[name]
            and type(info.get("bytes")) is int
            and 0 < info["bytes"] <= MAX_RESPONSE
            and isinstance(info.get("sha256"), str)
            and len(info["sha256"]) == 64
            for name, info in description.items()
        ),
        "Invalid file manifest",
    )
    require(
        sum(i["bytes"] for i in description.values()) <= MAX_DATA,
        "Dataset exceeds size limit",
    )
    version = manifest["dataset_version"]
    require(dataset_version(description) == version, "Manifest version/hash mismatch")
    files = {"municipality_catalog.json": encode(catalog)}
    for city in catalog["municipalities"]:
        time.sleep(0.25)  # Existing API Gateway limit is 5 req/s.
        bundle = get(
            base_url
            + f"/api/frontend-data/municipalities/{city['id']}?"
            + urlencode({"version": version})
        )
        require(
            bundle["schema_version"] == 1
            and bundle["dataset_version"] == version
            and bundle["municipality_id"] == city["id"],
            "Municipality response identity/version mismatch",
        )
        required = {name for name, owner in owners.items() if owner == city["id"]}
        require(
            set(bundle["files"]) == required and not set(files) & required,
            "Missing, duplicate or cross-city payload",
        )
        for name, content in bundle["files"].items():
            require(isinstance(content, str), "UI assets must be UTF-8 JSON")
            body = content.encode("utf-8")
            require(
                len(body) == description[name]["bytes"]
                and digest(body) == description[name]["sha256"],
                "Asset checksum/size mismatch",
            )
            files[name] = body
    require(descriptors(catalog, files) == description, "Downloaded manifest mismatch")
    validate_assets(catalog, files)
    final = get(manifest_url)
    require(
        final == manifest, "Data/policy changed during download; restart from manifest"
    )
    # Verify everything before any destination files appear. Refuse old folders,
    # including Git-managed metadata and already-installed untracked datasets.
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".ui-data-", dir=output.parent))
    try:
        for name, body in files.items():
            (temporary / name).write_bytes(body)
        (temporary / "frontend_data_manifest.json").write_bytes(encode(manifest))
        # mkdir is exclusive; unlike rename, it cannot replace an existing dir.
        output.mkdir()
        for path in temporary.iterdir():
            shutil.move(str(path), output / path.name)
    finally:
        shutil.rmtree(temporary)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-unreviewed-local", action="store_true")
    args = parser.parse_args()
    expected = {
        c["id"]
        for c in decode((ROOT / "data/regions/catalog.json").read_bytes())[
            "municipalities"
        ]
    }
    try:
        result = fetch(
            args.api_base_url,
            args.output,
            expected_ids=expected,
            allow_unreviewed_local=args.allow_unreviewed_local,
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"UI data download stopped: {type(error).__name__}: {error}\n")
    print(
        f"UI data ready: {len(result['catalog']['municipalities'])} municipalities, version {result['dataset_version']}"
    )


if __name__ == "__main__":
    main()
