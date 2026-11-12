#!/usr/bin/env python3
"""Fetch UI data, then run Flutter in a fresh isolated workspace.

Example: python3 scripts/flutter_with_data.py --api-base-url https://... -- run -d chrome
The original frontend, ignored municipality data and lockfile are never changed.
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

from fetch_frontend_data import ROOT, fetch, api_url, decode, require


def prepare_workspace(base_url, destination, *, allow_unreviewed_local=False):
    destination = Path(destination).absolute()
    require(
        not destination.exists() and not destination.is_symlink(),
        "Choose a NEW workspace; existing directories are never replaced",
    )
    destination = destination.resolve()
    require(
        not destination.is_relative_to((ROOT / "frontend").resolve()),
        "Workspace must be outside the source frontend directory",
    )
    # Fetch first into a private temporary folder, before creating the workspace.
    expected = {
        c["id"]
        for c in decode((ROOT / "data/regions/catalog.json").read_bytes())[
            "municipalities"
        ]
    }
    with tempfile.TemporaryDirectory(prefix="gomisapo-fetch-") as folder:
        data = Path(folder) / "data"
        manifest = fetch(
            base_url,
            data,
            expected_ids=expected,
            allow_unreviewed_local=allow_unreviewed_local,
        )
        destination.mkdir(parents=True)
        target = destination / "frontend"
        ignored = {
            "build",
            ".dart_tool",
            ".gradle",
            ".symlinks",
            "Pods",
            "ephemeral",
            ".flutter-plugins",
            ".flutter-plugins-dependencies",
        }

        def ignore(directory, names):
            result = set(names) & ignored
            if Path(directory) == ROOT / "frontend/assets/data":
                result |= {
                    n
                    for n in names
                    if n.startswith("municipality_")
                    or n == "frontend_data_manifest.json"
                }
            return result

        shutil.copytree(ROOT / "frontend", target, ignore=ignore)
        for path in data.iterdir():
            shutil.copyfile(path, target / "assets/data" / path.name)
    (destination / "README.txt").write_text(
        f"Generated isolated frontend workspace.\nUI dataset: {manifest['dataset_version']}\n"
        f"Publication: {manifest.get('publication_status', 'legacy')}\n"
        f"Source-license review: {manifest['redistribution_status']}\n"
        "Do not publish unreviewed_local_only assets.\n"
    )
    return target, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--allow-unreviewed-local", action="store_true")
    parser.add_argument("flutter_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.flutter_args
    if command[:1] == ["--"]:
        command = command[1:]
    try:
        require(
            command and command[0] in {"run", "build", "test", "analyze"},
            "Use -- run/build/test/analyze followed by Flutter arguments",
        )
        require(
            not any("API_BASE_URL" in a for a in command),
            "API URL is set by --api-base-url only",
        )
        url = api_url(args.api_base_url)
        directory = args.work_dir or (
            Path(tempfile.mkdtemp(prefix="gomisapo-work-")) / "workspace"
        )
        frontend, manifest = prepare_workspace(
            url, directory, allow_unreviewed_local=args.allow_unreviewed_local
        )
        print(
            f"Workspace: {frontend}\nUI dataset: {manifest['dataset_version']}",
            flush=True,
        )
        subprocess.run(["flutter", "pub", "get"], cwd=frontend, check=True)
        if command[0] in {"run", "build", "test"}:
            command.append(f"--dart-define=API_BASE_URL={url}")
        return subprocess.run(["flutter", *command], cwd=frontend).returncode
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.CalledProcessError,
    ) as error:
        parser.exit(
            1, f"Flutter preparation stopped: {type(error).__name__}: {error}\n"
        )


if __name__ == "__main__":
    sys.exit(main())
