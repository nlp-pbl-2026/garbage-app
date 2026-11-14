#!/usr/bin/env python3
"""Prepare a clean main release, then explicitly deploy it with local AWS credentials.

configure/prepare/verify and deploy/rollback without --execute never write to AWS.
The existing build_frontend_release.py and deploy_frontend.py own build/publication.
"""

import argparse
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

import deploy_frontend as deployment
from fetch_frontend_data import ROOT, read_json
from frontend_web_release import (
    FLUTTER_VERSION,
    api_url,
    decode,
    digest,
    encode,
    require,
)

CONFIG = ROOT / ".frontend-releases/deploy-config.json"
FLUTTER_REVISION = "6655482ec06e547f90abf8ae7590466f4415978d"
# Export only tracked build inputs. In particular, never archive data/regions as
# a whole: Matsuyama has a historical tracked NPZ, and other data is ignored.
SOURCE_PATHS = (
    "frontend",
    "data/regions/catalog.json",
    "backend/app/services/frontend_data_contract.py",
    "scripts/build_frontend_release.py",
    "scripts/deploy_frontend.py",
    "scripts/frontend_web_release.py",
    "scripts/flutter_with_data.py",
    "scripts/fetch_frontend_data.py",
)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as f:
        f.write(encode(value).decode())


def validate_config(value):
    require(value["schema_version"] == 1, "Unsupported deployment config")
    deployment.validate_target(value["target"])
    require(
        api_url(value["api_base_url"]) == value["api_base_url"]
        and value["api_base_url"].startswith("https://"),
        "Use the verified HTTPS API base URL",
    )
    require(
        value.get("profile") is None
        or (isinstance(value["profile"], str) and value["profile"]),
        "Invalid AWS CLI profile",
    )
    return value


def configure(target_path, url, profile, output):
    value = validate_config(
        {
            "schema_version": 1,
            "target": decode(Path(target_path).read_bytes()),
            "api_base_url": api_url(url),
            "profile": profile,
        }
    )
    save(output, value)
    print(
        f"Saved local config: {output}\nTarget: {deployment.target_token(value['target'])}"
    )


def main_commit():
    remote = subprocess.check_output(
        ["git", "ls-remote", "--exit-code", "origin", "refs/heads/main"],
        cwd=ROOT,
        text=True,
    ).split()
    require(
        len(remote) == 2 and re.fullmatch(r"[0-9a-f]{40}", remote[0]),
        "Cannot verify origin/main",
    )
    local = subprocess.check_output(
        ["git", "rev-parse", "refs/remotes/origin/main"], cwd=ROOT, text=True
    ).strip()
    require(
        local == remote[0],
        "origin/main is stale. Run git fetch origin main, then prepare again",
    )
    return local


def export_source(commit, destination):
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar", commit, "--", *SOURCE_PATHS], cwd=ROOT
    )
    # Do not follow repository symlinks or submodules into a local worktree.
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            name = member.name.rstrip("/")
            require(
                not member.name.startswith("/")
                and all(p not in {"", ".", ".."} for p in name.split("/"))
                and (member.isfile() or member.isdir()),
                "Unsafe build source archive entry",
            )
            path = destination / name
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as out:
                    out.write(tar.extractfile(member).read())


def source_hashes(source):
    require(source.is_dir() and not source.is_symlink(), "Missing/linked build source")
    paths = sorted(source.rglob("*"))
    require(not any(p.is_symlink() for p in paths), "Build source contains a symlink")
    return {
        p.relative_to(source).as_posix(): digest(p.read_bytes())
        for p in paths
        if p.is_file()
    }


def invoke(source, script, args, folder):
    """A new log/receipt per invocation, including failures before receipt creation."""
    command = [sys.executable, "-B", str(source / "scripts" / script), *map(str, args)]
    save(folder / "command.json", command)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    print(f"Running {script}; log: {folder / 'command.log'}", flush=True)
    with (folder / "command.log").open("x") as log:
        result = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=log)
    save(folder / "result.json", {"exit_code": result.returncode})
    require(
        result.returncode == 0,
        f"Stopped (exit {result.returncode}); inspect {folder}. Do not blindly retry writes",
    )


def client(config):
    # This wrapper only performs read-only preflight. All writes belong to the
    # existing deploy_frontend child, and require its exact --confirm-target.
    return deployment.AWS(config["target"]["region"], profile=config.get("profile"))


def api_version(url):
    manifest = read_json(url + "/api/frontend-data/manifest")
    version = manifest["dataset_version"]
    require(
        isinstance(version, str) and re.fullmatch(r"[0-9a-f]{64}", version),
        "Invalid dataset version",
    )
    deployment.check_api(url, version)
    return version


def prepare(config_path):
    config = validate_config(decode(Path(config_path).read_bytes()))
    commit = main_commit()
    sdk = decode(subprocess.check_output(["flutter", "--version", "--machine"]))
    require(
        sdk["frameworkVersion"] == FLUTTER_VERSION
        and sdk["frameworkRevision"] == FLUTTER_REVISION,
        f"Use Flutter {FLUTTER_VERSION} / {FLUTTER_REVISION}",
    )
    before = deployment.preflight(client(config), config["target"])
    version = api_version(config["api_base_url"])
    parent = ROOT / ".frontend-releases"
    parent.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run = Path(tempfile.mkdtemp(prefix=f"manual-{commit[:12]}-{stamp}-", dir=parent))
    print(f"Run directory: {run}", flush=True)
    try:
        source = run / "source"
        export_source(commit, source)
        hashes = source_hashes(source)
        rid = run.name
        save(run / "target.json", config["target"])
        invoke(
            source,
            "build_frontend_release.py",
            [
                "--api-base-url",
                config["api_base_url"],
                "--expected-dataset-version",
                version,
                "--release-id",
                rid,
                "--git-sha",
                commit,
                "--output",
                run / "release",
            ],
            run / "build",
        )
        ready = {
            "schema_version": 1,
            "config": config,
            "source_commit": commit,
            "release_id": rid,
            "dataset_version": version,
            "preflight": before,
            "source_files": hashes,
            "release_manifest_sha256": digest(
                (run / "release/release.json").read_bytes()
            ),
        }
        invoke(
            source,
            "deploy_frontend.py",
            deploy_args(run, ready, "deploy")
            + [
                "--receipt",
                run / "dry-run/receipt.json",
            ],
            run / "dry-run",
        )
        report = decode((run / "dry-run/receipt.json").read_bytes())
        require(report["status"] == "dry_run", "Dry-run did not complete")
        require(
            deployment.preflight(client(config), config["target"]) == before
            and report["previous_root"] == before["root"]
            and report["web_url"] == before["web_url"],
            "AWS target changed during preparation; prepare again",
        )
        require(
            main_commit() == commit, "main changed during preparation; prepare again"
        )
        require(
            source_hashes(source) == hashes, "Build source changed during preparation"
        )
        save(run / "deployment-ready.json", ready)
    except Exception as error:
        save(run / "preparation-failed.json", {"error": str(error)})
        raise
    show(ready)
    print(
        f"Ready (no AWS writes). Next:\npython3 scripts/frontend.py deploy {run} --execute"
    )
    return run


def deploy_args(run, ready, operation):
    config = ready["config"]
    args = [
        operation,
        "--target",
        run / "target.json",
        "--api-base-url",
        config["api_base_url"],
        "--expected-dataset-version",
        ready["dataset_version"],
    ]
    if config.get("profile"):
        args += ["--profile", config["profile"]]
    if operation == "deploy":
        args += ["--release", run / "release"]
    elif operation == "verify":
        args += ["--release-id", ready["release_id"]]
    else:
        old = (ready["preflight"]["root"] or {}).get("Metadata", {}).get("release-id")
        require(
            old, "No previous release in this plan; inspect the receipt before recovery"
        )
        args += [
            "--release-id",
            old,
            "--expected-current-release-id",
            ready["release_id"],
        ]
    return args


def show(ready):
    print(
        f"Target: {deployment.target_token(ready['config']['target'])}\n"
        f"Web: {ready['preflight']['web_url']}\nAPI: {ready['config']['api_base_url']}\n"
        f"main: {ready['source_commit']}\nRelease: {ready['release_id']}\n"
        f"Dataset: {ready['dataset_version']}",
        flush=True,
    )


def action(run, operation, execute=False, confirm=None):
    run = Path(run).resolve()
    ready = decode((run / "deployment-ready.json").read_bytes())
    require(ready["schema_version"] == 1, "Unsupported preparation record")
    config = validate_config(ready["config"])
    require(
        decode((run / "target.json").read_bytes()) == config["target"], "Target changed"
    )
    require(
        source_hashes(run / "source") == ready["source_files"],
        "Prepared source changed",
    )
    manifest = deployment.validate_release(run / "release")
    require(
        digest((run / "release/release.json").read_bytes())
        == ready["release_manifest_sha256"]
        and manifest["git_sha"] == ready["source_commit"]
        and manifest["release_id"] == ready["release_id"]
        and manifest["dataset_version"] == ready["dataset_version"]
        and manifest["api_base_url"] == config["api_base_url"],
        "Prepared release changed",
    )
    require(not execute or operation != "verify", "Verify is read-only")
    show(ready)
    args = deploy_args(run, ready, operation)
    if operation == "deploy":
        require(main_commit() == ready["source_commit"], "main changed; prepare again")
        current = deployment.preflight(client(config), config["target"])
        require(
            current == ready["preflight"],
            "AWS target/root changed; inspect receipts and prepare again",
        )
    deployment.check_api(config["api_base_url"], ready["dataset_version"])
    if execute:
        token = deployment.target_token(config["target"])
        require(
            not (run / f"{operation}-started.json").exists(),
            "Write already attempted; inspect receipt and use verify/recovery",
        )
        if confirm is None:
            require(
                sys.stdin.isatty(),
                "Interactive confirmation required (or supply --confirm-target)",
            )
            answer = input(
                f"上記の宛先・データ版でAWSへ{operation}します。実行するには {operation} と入力: "
            )
            require(answer == operation, "Confirmation did not match; no AWS writes")
        else:
            require(
                confirm == token, "Target confirmation did not match; no AWS writes"
            )
        # Reserve before spawning: a timeout, interrupt or a receipt failure is
        # never interpreted as permission to repeat a potentially successful PUT.
        save(
            run / f"{operation}-started.json",
            {"target": token, "release_id": ready["release_id"]},
        )
        args += ["--execute", "--confirm-target", token]
    attempt = Path(tempfile.mkdtemp(prefix=f"{operation}-", dir=run))
    invoke(
        run / "source",
        "deploy_frontend.py",
        args + ["--receipt", attempt / "receipt.json"],
        attempt,
    )
    report = decode((attempt / "receipt.json").read_bytes())
    require(
        report["status"]
        == ("verified" if execute or operation == "verify" else "dry_run"),
        "Inspect deployment receipt",
    )
    print(f"Status: {report['status']}\nReceipt: {attempt / 'receipt.json'}")
    return attempt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser(
        "configure", help="Save a NEW local target/API config, without AWS calls"
    )
    config.add_argument("--target", type=Path, required=True)
    config.add_argument("--api-base-url", required=True)
    config.add_argument("--profile")
    config.add_argument("--config", type=Path, default=CONFIG)
    prep = commands.add_parser(
        "prepare", help="Build origin/main and dry-run; no AWS writes"
    )
    prep.add_argument("--config", type=Path, default=CONFIG)
    for name in ("deploy", "verify", "rollback"):
        command = commands.add_parser(name)
        command.add_argument(
            "run", type=Path, help="Prepared run directory printed by prepare"
        )
        if name != "verify":
            command.add_argument("--execute", action="store_true")
            command.add_argument(
                "--confirm-target",
                help="Explicit account:region:bucket:distribution instead of a TTY prompt",
            )
    args = parser.parse_args()
    try:
        if args.command == "configure":
            configure(args.target, args.api_base_url, args.profile, args.config)
        elif args.command == "prepare":
            prepare(args.config)
        else:
            action(
                args.run,
                args.command,
                getattr(args, "execute", False),
                getattr(args, "confirm_target", None),
            )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        EOFError,
        subprocess.CalledProcessError,
    ) as error:
        parser.exit(1, f"Frontend operation stopped: {error}\n")


if __name__ == "__main__":
    main()
