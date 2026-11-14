"""Operator commands use sealed main inputs; no AWS/model/network calls in tests."""

import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import frontend as operator
from frontend_web_release import describe_site, digest, encode
from backend.tests.test_frontend_hosting import (
    TARGET,
    release,
)  # Reuse the validated synthetic UI fixture.


@pytest.fixture
def prepared(tmp_path, monkeypatch, release):
    run = tmp_path / "run"
    shutil.copytree(release[0], run / "release")
    source = run / "source"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts/deploy_frontend.py").write_text("# sealed test source\n")
    config = {
        "schema_version": 1,
        "target": TARGET,
        "api_base_url": release[1]["api_base_url"],
        "profile": "default",
    }
    before = {
        "distribution_etag": "cf-v1",
        "web_url": "https://web.cloudfront.net",
        "root": {
            "ETag": "old-etag",
            "VersionId": "old-version",
            "Metadata": {"release-id": "prior-release"},
        },
    }
    ready = {
        "schema_version": 1,
        "config": config,
        "preflight": before,
        "source_commit": release[1]["git_sha"],
        "release_id": release[1]["release_id"],
        "dataset_version": release[1]["dataset_version"],
        "source_files": operator.source_hashes(source),
        "release_manifest_sha256": digest((run / "release/release.json").read_bytes()),
    }
    operator.save(run / "target.json", TARGET)
    operator.save(run / "deployment-ready.json", ready)
    monkeypatch.setattr(operator, "main_commit", lambda: ready["source_commit"])
    monkeypatch.setattr(
        operator.deployment, "preflight", lambda *_: copy.deepcopy(before)
    )
    monkeypatch.setattr(operator.deployment, "check_api", lambda url, version: None)
    commands = []

    def invoke(source, script, args, folder):
        commands.append((script, list(map(str, args))))
        execute = "--execute" in args
        receipt = Path(args[args.index("--receipt") + 1])
        operator.save(
            receipt,
            {
                "status": "verified" if execute or args[0] == "verify" else "dry_run",
                "previous_root": before["root"],
                "web_url": before["web_url"],
            },
        )

    monkeypatch.setattr(operator, "invoke", invoke)
    return run, ready, commands


def test_configure_is_local_and_never_overwrites(tmp_path, monkeypatch):
    target = tmp_path / "target.json"
    target.write_bytes(encode(TARGET))
    config = tmp_path / "config.json"
    monkeypatch.setattr(
        operator.deployment.AWS, "call", lambda *_: pytest.fail("No AWS call")
    )
    operator.configure(target, "https://api.example.test/", "default", config)
    saved = config.read_bytes()
    assert json.loads(saved)["api_base_url"] == "https://api.example.test"
    assert config.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        operator.configure(target, "https://another.example.test", None, config)
    assert config.read_bytes() == saved


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000",
        "https://user:secret@host.test",
        "https://api.test?key=x",
    ],
)
def test_configure_rejects_unsafe_api_urls(tmp_path, url):
    target = tmp_path / "target.json"
    target.write_bytes(encode(TARGET))
    with pytest.raises(ValueError):
        operator.configure(target, url, None, tmp_path / "config.json")


def test_stale_main_stops_without_updating_worktree_or_refs(monkeypatch):
    commands = []

    def output(args, **kwargs):
        commands.append(args)
        return "a" * 40 + "\trefs/heads/main\n" if args[1] == "ls-remote" else "b" * 40

    monkeypatch.setattr(operator.subprocess, "check_output", output)
    with pytest.raises(ValueError, match="git fetch"):
        operator.main_commit()
    assert [c[1] for c in commands] == ["ls-remote", "rev-parse"]


def test_export_reads_committed_inputs_only_and_preserves_dirty_files(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()

    git("init", "-q")
    for name in operator.SOURCE_PATHS:
        path = repo / ("frontend/lib/main.dart" if name == "frontend" else name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("committed")
    # Historical tracked backend data must also stay outside the build archive.
    (repo / "data/regions/item_embeddings.npz").write_bytes(b"private-index")
    git("add", "frontend", "scripts", "backend", "data")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "commit",
        "-qm",
        "fixture",
    )
    commit = git("rev-parse", "HEAD")
    (repo / "frontend/lib/main.dart").write_text("dirty-user-code")
    ignored = repo / "frontend/assets/data/municipality_secret_calendar.json"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("local-only")
    before = git("status", "--porcelain")
    monkeypatch.setattr(operator, "ROOT", repo)
    destination = tmp_path / "source"
    operator.export_source(commit, destination)
    assert (destination / "frontend/lib/main.dart").read_text() == "committed"
    assert not (destination / ignored.relative_to(repo)).exists()
    assert not list(destination.rglob("*.npz"))
    assert not list(destination.rglob("*.csv"))
    assert (repo / "frontend/lib/main.dart").read_text() == "dirty-user-code"
    assert git("status", "--porcelain") == before


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.REGTYPE])
def test_archive_links_and_path_traversal_are_rejected(tmp_path, monkeypatch, kind):
    body = io.BytesIO()
    with tarfile.open(fileobj=body, mode="w") as tar:
        item = tarfile.TarInfo(
            "../escape" if kind == tarfile.REGTYPE else "frontend/link"
        )
        item.type, item.linkname = kind, "/private"
        tar.addfile(item)
    monkeypatch.setattr(
        operator.subprocess, "check_output", lambda *_a, **_k: body.getvalue()
    )
    with pytest.raises(ValueError, match="Unsafe"):
        operator.export_source("a" * 40, tmp_path / "source")
    assert not (tmp_path / "escape").exists()


def test_prepare_seals_live_version_clean_source_and_dry_run(
    prepared, monkeypatch, tmp_path, release
):
    _, previous, commands = prepared
    monkeypatch.setattr(operator, "ROOT", tmp_path / "project")
    operator.ROOT.mkdir()
    config = tmp_path / "config.json"
    config.write_bytes(encode(previous["config"]))
    monkeypatch.setattr(operator, "api_version", lambda _: previous["dataset_version"])
    monkeypatch.setattr(
        operator.subprocess,
        "check_output",
        lambda *_: encode(
            {
                "frameworkVersion": operator.FLUTTER_VERSION,
                "frameworkRevision": operator.FLUTTER_REVISION,
            }
        ),
    )

    def export(commit, path):
        path.mkdir()
        (path / "marker.txt").write_text(commit)

    monkeypatch.setattr(operator, "export_source", export)
    old_invoke = operator.invoke

    def invoke(source, script, args, folder):
        if script == "build_frontend_release.py":
            commands.append((script, list(map(str, args))))
            output = Path(args[args.index("--output") + 1])
            shutil.copytree(release[0], output)
            manifest = copy.deepcopy(release[1])
            rid = args[args.index("--release-id") + 1]
            manifest["release_id"] = rid
            index = output / "site/index.html"
            index.write_text(index.read_text().replace("release-test", rid))
            manifest["files"] = describe_site(output / "site")
            (output / "release.json").write_bytes(encode(manifest))
        else:
            old_invoke(source, script, args, folder)

    monkeypatch.setattr(operator, "invoke", invoke)
    run = operator.prepare(config)
    ready = json.loads((run / "deployment-ready.json").read_text())
    assert ready["dataset_version"] == previous["dataset_version"]
    assert ready["source_commit"] == previous["source_commit"]
    assert ready["source_files"] == operator.source_hashes(run / "source")
    assert [s for s, _ in commands] == [
        "build_frontend_release.py",
        "deploy_frontend.py",
    ]
    assert all("--execute" not in args for _, args in commands)
    assert not (run / "deploy-started.json").exists()
    assert json.loads((run / "dry-run/receipt.json").read_text())["status"] == "dry_run"


@pytest.mark.parametrize("operation", ["deploy", "rollback", "verify"])
def test_default_actions_never_enable_aws_writes(prepared, operation):
    run, ready, commands = prepared
    operator.action(run, operation)
    args = commands[0][1]
    assert args[0] == operation and "--execute" not in args
    assert "--profile" in args and "default" in args
    assert not (run / f"{operation}-started.json").exists()
    if operation == "rollback":
        assert args[args.index("--release-id") + 1] == "prior-release"
        assert (
            args[args.index("--expected-current-release-id") + 1] == ready["release_id"]
        )


def test_wrong_confirmation_and_noninteractive_execution_do_not_publish(
    prepared, monkeypatch
):
    run, _, commands = prepared
    with pytest.raises(ValueError, match="confirmation"):
        operator.action(run, "deploy", True, "wrong-target")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    with pytest.raises(ValueError, match="Interactive"):
        operator.action(run, "deploy", True)
    assert not commands and not (run / "deploy-started.json").exists()


def test_execution_is_once_only_and_verify_can_resume_read_only(prepared):
    run, ready, commands = prepared
    token = operator.deployment.target_token(TARGET)
    attempt = operator.action(run, "deploy", True, token)
    assert commands[0][1][-2:] == ["--receipt", str(attempt / "receipt.json")]
    assert "--execute" in commands[0][1]
    with pytest.raises(ValueError, match="already attempted"):
        operator.action(run, "deploy", True, token)
    before = (attempt / "receipt.json").read_bytes()
    operator.action(run, "verify")
    assert "--execute" not in commands[-1][1]
    assert (attempt / "receipt.json").read_bytes() == before
    assert len(commands) == 2


def test_verify_remains_read_only_after_main_advances(prepared, monkeypatch):
    run, _, commands = prepared
    monkeypatch.setattr(
        operator,
        "main_commit",
        lambda: pytest.fail("Verification must not require old main"),
    )
    operator.action(run, "verify")
    assert "--execute" not in commands[0][1]


def test_failed_write_keeps_marker_and_does_not_repeat(prepared, monkeypatch):
    run, _, _ = prepared
    token = operator.deployment.target_token(TARGET)

    def fail(*_):
        raise ValueError("timeout after activation; inspect receipt")

    monkeypatch.setattr(operator, "invoke", fail)
    with pytest.raises(ValueError, match="timeout"):
        operator.action(run, "deploy", True, token)
    assert (run / "deploy-started.json").exists()
    with pytest.raises(ValueError, match="already attempted"):
        operator.action(run, "deploy", True, token)


def test_interactive_confirmation_and_rollback_preserve_the_pinned_target(
    prepared, monkeypatch
):
    run, ready, commands = prepared
    token = operator.deployment.target_token(TARGET)

    class Terminal(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", Terminal())
    monkeypatch.setattr("builtins.input", lambda _: "rollback")
    operator.action(run, "rollback", True)
    args = commands[0][1]
    assert "--execute" in args
    assert args[args.index("--release-id") + 1] == "prior-release"
    assert args[args.index("--expected-current-release-id") + 1] == ready["release_id"]
    with pytest.raises(ValueError, match="already attempted"):
        operator.action(run, "rollback", True, token)


def test_first_release_cannot_guess_a_rollback_target(prepared):
    run, ready, commands = prepared
    ready["preflight"]["root"] = None
    (run / "deployment-ready.json").write_bytes(encode(ready))
    with pytest.raises(ValueError, match="No previous release"):
        operator.action(run, "rollback", True, operator.deployment.target_token(TARGET))
    assert not commands and not (run / "rollback-started.json").exists()


@pytest.mark.parametrize("version", ["past-version", "a" * 63, None])
def test_invalid_live_version_is_not_used(monkeypatch, version):
    monkeypatch.setattr(operator, "read_json", lambda _: {"dataset_version": version})
    monkeypatch.setattr(
        operator.deployment,
        "check_api",
        lambda *_: pytest.fail("Stop before API check"),
    )
    with pytest.raises(ValueError, match="Invalid dataset"):
        operator.api_version("https://api.example.test")


@pytest.mark.parametrize(
    "change",
    ["main", "source", "target", "artifact", "backend", "root", "distribution"],
)
def test_changes_since_prepare_stop_before_publishing(prepared, monkeypatch, change):
    run, ready, commands = prepared
    if change == "main":
        monkeypatch.setattr(operator, "main_commit", lambda: "b" * 40)
    elif change == "source":
        (run / "source/scripts/deploy_frontend.py").write_text("changed")
    elif change == "target":
        value = copy.deepcopy(TARGET)
        value["distribution_id"] = "ANOTHER"
        (run / "target.json").write_bytes(encode(value))
    elif change == "artifact":
        (run / "release/site/main.dart.js").write_text("changed")
    elif change == "backend":

        def reject(*_):
            raise ValueError("Backend version changed")

        monkeypatch.setattr(operator.deployment, "check_api", reject)
    else:
        current = copy.deepcopy(ready["preflight"])
        if change == "root":
            current["root"]["VersionId"] = "peer-version"
        else:
            current["distribution_etag"] = "peer-config"
        monkeypatch.setattr(operator.deployment, "preflight", lambda *_: current)
    with pytest.raises(ValueError):
        operator.action(run, "deploy", True, operator.deployment.target_token(TARGET))
    assert not commands and not (run / "deploy-started.json").exists()


def test_invoke_records_failure_without_rewriting_logs(tmp_path):
    source = tmp_path / "source"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts/fail.py").write_text(
        "print('partial failure'); raise SystemExit(3)"
    )
    attempt = tmp_path / "attempt"
    with pytest.raises(ValueError, match="Stopped"):
        operator.invoke(source, "fail.py", [], attempt)
    assert json.loads((attempt / "result.json").read_text())["exit_code"] == 3
    assert "partial failure" in (attempt / "command.log").read_text()
    with pytest.raises(FileExistsError):
        operator.invoke(source, "fail.py", [], attempt)


def test_backend_example_preserves_state_location_and_checks_account():
    text = (operator.ROOT / "infra/frontend/backend.hcl.example").read_text()
    assert 'allowed_account_ids = ["088066169748"]' in text
    assert "expected_bucket_owner" not in text
    assert 'key                 = "frontend/dev/terraform.tfstate"' in text
    assert "use_lockfile        = true" in text
