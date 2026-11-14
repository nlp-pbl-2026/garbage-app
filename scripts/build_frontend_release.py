#!/usr/bin/env python3
"""Build an immutable release in a NEW directory; never alter the source frontend."""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from flutter_with_data import prepare_workspace
from frontend_web_release import (
    FLUTTER_VERSION,
    api_url,
    decode,
    describe_site,
    encode,
    require,
    release_id,
    prepare_web_manifest,
    validate_release,
)


def build(base_url, expected_version, rid, git_sha, output):
    output = Path(output).absolute()
    require(
        not output.exists() and not output.is_symlink(), "Choose a NEW release output"
    )
    release_id(rid)
    import re

    require(
        re.fullmatch(r"[0-9a-f]{64}", expected_version),
        "Specify the verified backend dataset version",
    )
    require(re.fullmatch(r"[0-9a-f]{40}", git_sha), "Specify the source commit")
    sdk = decode(subprocess.check_output(["flutter", "--version", "--machine"]))
    require(
        sdk["frameworkVersion"] == FLUTTER_VERSION, f"Use Flutter {FLUTTER_VERSION}"
    )
    url = api_url(base_url)
    with tempfile.TemporaryDirectory(prefix="gomisapo-web-build-") as work:
        frontend, ui = prepare_workspace(url, Path(work) / "workspace")
        require(
            ui.get("publication_status") == "enabled"
            and ui["dataset_version"] == expected_version,
            "Backend version/publication differs from the verified release",
        )
        subprocess.run(["flutter", "pub", "get"], cwd=frontend, check=True)
        subprocess.run(
            [
                "flutter",
                "build",
                "web",
                "--release",
                f"--base-href=/releases/{rid}/",
                "--no-web-resources-cdn",
                f"--dart-define=API_BASE_URL={url}",
            ],
            cwd=frontend,
            check=True,
        )
        staged = Path(work) / "release"
        staged.mkdir()
        shutil.copytree(
            frontend / "build/web",
            staged / "site",
            ignore=shutil.ignore_patterns(".last_build_id"),
        )
        prepare_web_manifest(staged / "site")
        manifest = {
            "schema_version": 1,
            "release_id": rid,
            "git_sha": git_sha,
            "dataset_version": ui["dataset_version"],
            "api_base_url": url,
            "flutter_version": FLUTTER_VERSION,
            "files": describe_site(staged / "site"),
        }
        (staged / "release.json").write_bytes(encode(manifest))
        validate_release(staged)
        output.mkdir(parents=True)
        for path in staged.iterdir():
            shutil.move(str(path), output / path.name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--expected-dataset-version", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = build(
            args.api_base_url,
            args.expected_dataset_version,
            args.release_id,
            args.git_sha,
            args.output,
        )
        print(
            f"Release ready: {manifest['release_id']} / {manifest['dataset_version']}"
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.CalledProcessError,
    ) as error:
        parser.exit(1, f"Web build stopped: {error}\n")


if __name__ == "__main__":
    main()
