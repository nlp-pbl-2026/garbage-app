"""Web hosting safety tests: synthetic UI assets, in-memory S3, no AWS calls."""

import base64
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_frontend_release as builder
import deploy_frontend as deploy
from frontend_web_release import (
    FLUTTER_VERSION,
    UI_PATH,
    ENTRY_CACHE,
    IMMUTABLE_CACHE,
    describe_site,
    descriptors,
    dataset_version,
    digest,
    encode,
    validate_release,
)

TARGET = {
    "account": "088066169748",
    "region": "ap-northeast-1",
    "bucket": "garbage-guide-web-dev-088066169748-ap-northeast-1",
    "distribution_id": "NEWFRONTEND",
    "environment": "dev",
    "project_tag": "U-22",
}


@pytest.fixture
def release(tmp_path):
    folder = tmp_path / "release"
    site = folder / "site"
    ui_root = site / UI_PATH
    ui_root.mkdir(parents=True)
    cities, files = [], {}
    for city in json.loads((ROOT / "data/regions/catalog.json").read_text())[
        "municipalities"
    ]:
        cid = city["id"]
        reg_name, cal_name = (
            f"municipality_{cid}_registry.json",
            f"municipality_{cid}_0_calendar.json",
        )
        cities.append(
            {
                "id": cid,
                "name": "試験市町",
                "version": "v1",
                "registry_asset": "assets/data/" + reg_name,
                "profiles": {
                    "standard": {
                        "calendar_asset": "assets/data/" + cal_name,
                        "categories": {
                            "burn": {
                                "name": "燃えるごみ",
                                "collection_type_id": "burn",
                                "cutoff": "08:00",
                            }
                        },
                    }
                },
            }
        )
        files[reg_name] = encode(
            {
                "municipality_id": cid,
                "version": "v1",
                "valid_from": "2026-04-01",
                "valid_to": "2027-03-31",
                "collection_areas": [
                    {
                        "id": "area",
                        "name": "試験地区",
                        "rule_profile_id": "standard",
                        "calendar_id": "cal",
                    }
                ],
                "calendars": [{"id": "cal", "rule_profile_id": "standard"}],
            }
        )
        files[cal_name] = encode(
            {
                "municipality_id": cid,
                "version": "v1",
                "valid_from": "2026-04-01",
                "valid_to": "2027-03-31",
                "calendars": {
                    "cal": {
                        "verification_status": "checked",
                        "days": {"2026-11-14": ["burn"]},
                    }
                },
            }
        )
    catalog = {"schema_version": 1, "municipalities": cities}
    files["municipality_catalog.json"] = encode(catalog)
    desc = descriptors(catalog, files)
    version = dataset_version(desc)
    ui = {
        "schema_version": 1,
        "publication_status": "enabled",
        "redistribution_status": "pending",
        "dataset_version": version,
        "catalog": catalog,
        "files": desc,
    }
    for name, body in files.items():
        (ui_root / name).write_bytes(body)
    (ui_root / "frontend_data_manifest.json").write_bytes(encode(ui))
    (site / "index.html").write_text(
        '<base href="/releases/release-test/"><script src="flutter_bootstrap.js"></script>'
    )
    (site / "flutter_bootstrap.js").write_text("console.log('synthetic bootstrap')")
    (site / "main.dart.js").write_text("console.log('synthetic app')")
    (site / "manifest.json").write_bytes(
        encode({"id": "/", "start_url": "/", "scope": "/"})
    )
    manifest = {
        "schema_version": 1,
        "release_id": "release-test",
        "git_sha": "a" * 40,
        "flutter_version": FLUTTER_VERSION,
        "api_base_url": "https://api.example.test",
        "dataset_version": version,
        "files": describe_site(site),
    }
    (folder / "release.json").write_bytes(encode(manifest))
    return folder, manifest


class MemoryAWS:
    def __init__(self):
        self.objects, self.versions, self.calls = {}, {}, []
        self.counter = 0
        self.fail_key = None
        self.unknown_activation = False
        self.before_entry_put = None

    def seed(self, key, body, metadata=None, cache=ENTRY_CACHE):
        self.counter += 1
        value = {
            "ETag": '"' + hashlib.md5(body).hexdigest() + '"',
            "VersionId": str(self.counter),
            "ContentLength": len(body),
            "ChecksumSHA256": base64.b64encode(hashlib.sha256(body).digest()).decode(),
            "ContentType": "text/html; charset=utf-8",
            "CacheControl": cache,
            "Metadata": metadata or {},
        }
        self.objects[key] = (value, body)
        self.versions[value["VersionId"]] = (value, body)
        return copy.deepcopy(value)

    def call(self, service, operation, *args):
        args = list(map(str, args))
        self.calls.append((service, operation, args))

        def arg(name):
            return args[args.index(name) + 1]

        key = arg("--key")
        if operation == "head-object":
            if key not in self.objects:
                raise deploy.AwsError("An error occurred (404)")
            return copy.deepcopy(self.objects[key][0])
        if operation == "get-object":
            value, body = (
                self.versions[arg("--version-id")]
                if "--version-id" in args
                else self.objects[key]
            )
            Path(args[-1]).write_bytes(body)
            return copy.deepcopy(value)
        assert (service, operation) == ("s3api", "put-object")
        if key == "index.html" and self.before_entry_put:
            callback, self.before_entry_put = self.before_entry_put, None
            callback()
        if key == self.fail_key:
            raise deploy.AwsError("An error occurred (AccessDenied)")
        if "--if-none-match" in args and key in self.objects:
            raise deploy.AwsError("An error occurred (PreconditionFailed)")
        if "--if-match" in args and (
            key not in self.objects or self.objects[key][0]["ETag"] != arg("--if-match")
        ):
            raise deploy.AwsError("An error occurred (PreconditionFailed)")
        assert "--if-none-match" in args or "--if-match" in args
        body = Path(arg("--body")).read_bytes()
        value = self.seed(
            key, body, json.loads(arg("--metadata")), arg("--cache-control")
        )
        value["ContentType"] = arg("--content-type")
        assert value["ChecksumSHA256"] == arg("--checksum-sha256")
        self.objects[key] = (value, body)
        self.versions[value["VersionId"]] = (value, body)
        if self.unknown_activation and key == "index.html":
            raise deploy.AwsError("An error occurred (RequestTimeout)")
        return copy.deepcopy(value)


@pytest.fixture
def runtime(monkeypatch):
    aws = MemoryAWS()

    def preflight(client, target):
        assert target == TARGET
        return {
            "distribution_etag": "cf-v1",
            "web_url": "https://web.cloudfront.net",
            "root": copy.deepcopy(client.objects.get("index.html", (None,))[0]),
        }

    monkeypatch.setattr(deploy, "preflight", preflight)
    monkeypatch.setattr(deploy, "check_api", lambda *_: {})
    monkeypatch.setattr(deploy, "invalidate", lambda *_: None)
    monkeypatch.setattr(deploy, "verify_public", lambda *_: None)
    monkeypatch.setattr(deploy, "public_bytes", lambda _: aws.objects["index.html"][1])
    return aws


def publish(aws, release, **kwargs):
    folder, manifest = release
    return deploy.publish(
        aws,
        TARGET,
        folder,
        manifest,
        manifest["dataset_version"],
        kwargs.pop("execute", True),
        kwargs.pop("confirm", deploy.target_token(TARGET)),
        **kwargs,
    )


def test_release_is_complete_and_ui_only(release):
    folder, manifest = release
    assert validate_release(folder) == manifest
    assert len(manifest["files"]) > 40


def test_web_manifest_does_not_pin_installed_apps_to_old_release(release):
    from frontend_web_release import prepare_web_manifest

    path = release[0] / "site/manifest.json"
    path.write_bytes(encode({"name": "ごみサポ", "start_url": "."}))
    prepare_web_manifest(path.parent)
    result = json.loads(path.read_text())
    assert result["name"] == "ごみサポ"
    assert result["id"] == result["start_url"] == result["scope"] == "/"


@pytest.mark.parametrize(
    "case", ["bytes", "base", "ui-version", "source-data", "symlink"]
)
def test_invalid_artifact_is_rejected(release, case):
    folder, manifest = release
    if case == "bytes":
        (folder / "site/main.dart.js").write_text("tampered")
    elif case == "base":
        (folder / "site/index.html").write_text(
            '<base href="/"><script src="flutter_bootstrap.js"></script>'
        )
        manifest["files"] = describe_site(folder / "site")
    elif case == "ui-version":
        manifest["dataset_version"] = "0" * 64
    elif case == "source-data":
        (folder / "site/items.csv").write_text("must never ship")
    else:
        (folder / "site/secret").symlink_to(folder / "release.json")
    (folder / "release.json").write_bytes(encode(manifest))
    with pytest.raises(ValueError):
        validate_release(folder)


def test_wrong_sdk_or_backend_version_stops_before_build(
    release, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        builder.subprocess,
        "check_output",
        lambda _: encode({"frameworkVersion": "wrong"}),
    )
    with pytest.raises(ValueError, match="Flutter"):
        builder.build(
            "https://api.example.test",
            "a" * 64,
            "release-test",
            "a" * 40,
            tmp_path / "out",
        )
    monkeypatch.setattr(
        builder.subprocess,
        "check_output",
        lambda _: encode({"frameworkVersion": FLUTTER_VERSION}),
    )
    monkeypatch.setattr(
        builder,
        "prepare_workspace",
        lambda *_: (
            tmp_path,
            {"publication_status": "enabled", "dataset_version": "b" * 64},
        ),
    )
    monkeypatch.setattr(
        builder.subprocess, "run", lambda *_a, **_k: pytest.fail("No build expected")
    )
    with pytest.raises(ValueError, match="Backend version"):
        builder.build(
            "https://api.example.test",
            "a" * 64,
            "release-test",
            "a" * 40,
            tmp_path / "out",
        )


def test_no_write_by_default_and_no_backend_operations(monkeypatch):
    monkeypatch.setattr(
        deploy.subprocess, "run", lambda *_a, **_kw: pytest.fail("No process expected")
    )
    with pytest.raises(ValueError):
        deploy.AWS("ap-northeast-1").call("s3api", "put-object")
    with pytest.raises(ValueError):
        deploy.AWS("ap-northeast-1", execute=True).call(
            "lambda", "update-function-code"
        )


def test_old_cli_is_rejected_without_aws_calls(monkeypatch):
    class Result:
        stdout = '{"IfNoneMatch": ""}'

    monkeypatch.setattr(deploy.subprocess, "run", lambda *_a, **_kw: Result())
    with pytest.raises(ValueError, match="Upgrade AWS CLI"):
        deploy.check_cli_capabilities()


def test_unversioned_staged_object_is_not_publishable():
    aws = MemoryAWS()
    value = aws.seed("file", b"data", cache=IMMUTABLE_CACHE)
    value["VersionId"] = "null"
    with pytest.raises(ValueError):
        deploy.verify_object(
            value,
            {
                "sha256": digest(b"data"),
                "bytes": 4,
                "content_type": "text/html; charset=utf-8",
            },
            IMMUTABLE_CACHE,
        )


def test_dry_run_and_wrong_target_do_not_upload(runtime, release):
    assert publish(runtime, release, execute=False)["status"] == "dry_run"
    with pytest.raises(ValueError, match="Confirm"):
        publish(runtime, release, confirm="wrong-account")
    assert not runtime.calls


def test_publish_uploads_immutable_files_before_root(runtime, release):
    runtime.seed("index.html", b"previous", {"release-id": "previous-release"})
    result = publish(runtime, release)
    assert result["status"] == "verified"
    puts = [args for _, op, args in runtime.calls if op == "put-object"]
    assert all(
        args[args.index("--key") + 1].startswith("releases/") for args in puts[:-1]
    )
    assert puts[-1][puts[-1].index("--key") + 1] == "index.html"
    assert "--if-match" in puts[-1]
    assert (
        runtime.objects["index.html"][1]
        == (release[0] / "site/index.html").read_bytes()
    )


def test_read_only_verification_checks_backend_before_and_after_cdn(
    runtime, release, monkeypatch
):
    publish(runtime, release)
    runtime.calls.clear()
    events = []
    monkeypatch.setattr(deploy, "check_api", lambda *_: events.append("api"))
    monkeypatch.setattr(deploy, "verify_public", lambda *_: events.append("cdn"))
    result = deploy.verify_active(
        runtime, TARGET, release[1], release[1]["dataset_version"]
    )
    assert result["status"] == "verified"
    assert events == ["api", "cdn", "api"]
    assert not runtime.calls


def test_read_only_verification_rejects_backend_change_during_cdn_check(
    runtime, release, monkeypatch
):
    publish(runtime, release)
    runtime.calls.clear()
    checked = []

    def api(*_):
        checked.append(True)
        if len(checked) == 2:
            raise ValueError("Backend UI data changed")

    monkeypatch.setattr(deploy, "check_api", api)
    with pytest.raises(ValueError, match="Backend UI data changed"):
        deploy.verify_active(
            runtime, TARGET, release[1], release[1]["dataset_version"]
        )
    assert not runtime.calls


def test_read_only_verification_rejects_peer_update(runtime, release, monkeypatch):
    publish(runtime, release)
    runtime.calls.clear()
    monkeypatch.setattr(
        deploy,
        "verify_public",
        lambda *_: runtime.seed(
            "index.html", b"peer", {"release-id": "peer-release"}
        ),
    )
    with pytest.raises(ValueError, match="Deployment changed"):
        deploy.verify_active(
            runtime, TARGET, release[1], release[1]["dataset_version"]
        )
    assert not runtime.calls
    assert runtime.objects["index.html"][1] == b"peer"


def test_read_only_verification_rejects_inactive_release(runtime, release):
    runtime.seed("index.html", b"peer", {"release-id": "peer-release"})
    with pytest.raises(ValueError, match="not active"):
        deploy.verify_active(
            runtime, TARGET, release[1], release[1]["dataset_version"]
        )
    assert not runtime.calls


def test_read_only_verification_rejects_stale_root_metadata(runtime, release):
    publish(runtime, release)
    runtime.objects["index.html"][0]["CacheControl"] = IMMUTABLE_CACHE
    with pytest.raises(ValueError, match="metadata"):
        deploy.verify_active(
            runtime, TARGET, release[1], release[1]["dataset_version"]
        )


def test_partial_upload_does_not_change_visible_release(runtime, release):
    previous = runtime.seed(
        "index.html", b"previous", {"release-id": "previous-release"}
    )
    runtime.fail_key = "releases/release-test/flutter_bootstrap.js"
    with pytest.raises(ValueError):
        publish(runtime, release)
    assert runtime.objects["index.html"][0] == previous


def test_backend_change_before_activation_does_not_switch_root(
    runtime, release, monkeypatch
):
    previous = runtime.seed(
        "index.html", b"previous", {"release-id": "previous-release"}
    )
    calls = []

    def api(*_):
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("Backend changed")

    monkeypatch.setattr(deploy, "check_api", api)
    with pytest.raises(ValueError, match="Backend changed"):
        publish(runtime, release)
    assert runtime.objects["index.html"][0] == previous


def test_concurrent_update_before_activation_is_preserved(
    runtime, release, monkeypatch
):
    runtime.seed("index.html", b"previous", {"release-id": "previous-release"})
    actual = deploy.preflight
    calls = []

    def preflight(*args):
        calls.append(1)
        if len(calls) == 2:
            runtime.seed("index.html", b"peer", {"release-id": "peer-release"})
        return actual(*args)

    monkeypatch.setattr(deploy, "preflight", preflight)
    with pytest.raises(ValueError, match="Concurrent"):
        publish(runtime, release)
    assert runtime.objects["index.html"][1] == b"peer"


def test_failed_public_verification_restores_previous_entry(
    runtime, release, monkeypatch
):
    runtime.seed("index.html", b"previous", {"release-id": "previous-release"})
    monkeypatch.setattr(
        deploy, "verify_public", lambda *_: (_ for _ in ()).throw(ValueError("bad CDN"))
    )
    with pytest.raises(deploy.DeploymentFailure) as failure:
        publish(runtime, release)
    assert failure.value.report["status"] == "entry_restored"
    assert runtime.objects["index.html"][1] == b"previous"


def test_first_failed_release_returns_maintenance_page(runtime, release, monkeypatch):
    monkeypatch.setattr(
        deploy, "verify_public", lambda *_: (_ for _ in ()).throw(ValueError("bad CDN"))
    )
    with pytest.raises(deploy.DeploymentFailure) as failure:
        publish(runtime, release)
    assert failure.value.report["status"] == "entry_restored"
    assert runtime.objects["index.html"][0]["Metadata"] == {
        "deployment-status": "maintenance"
    }


@pytest.mark.parametrize("peer_change", ["root", "distribution"])
def test_restoration_detects_concurrent_change_before_reporting_success(
    runtime, release, monkeypatch, peer_change
):
    runtime.seed("index.html", b"previous", {"release-id": "previous-release"})
    actual = deploy.preflight
    changed = []

    def read_restored(_):
        body = runtime.objects["index.html"][1]
        if peer_change == "root":
            runtime.seed("index.html", b"peer", {"release-id": "peer-release"})
        changed.append(True)
        return body

    def preflight(*args):
        value = actual(*args)
        if changed and peer_change == "distribution":
            value["distribution_etag"] = "peer-config"
        return value

    monkeypatch.setattr(
        deploy, "verify_public", lambda *_: (_ for _ in ()).throw(ValueError("bad CDN"))
    )
    monkeypatch.setattr(deploy, "public_bytes", read_restored)
    monkeypatch.setattr(deploy, "preflight", preflight)
    with pytest.raises(deploy.DeploymentFailure) as failure:
        publish(runtime, release)
    assert failure.value.report["status"] == "restore_needs_review"
    assert "changed during restoration" in failure.value.report["restoration_error"]
    assert runtime.objects["index.html"][1] == (
        b"peer" if peer_change == "root" else b"previous"
    )
    assert (
        sum(
            op == "put-object" and "index.html" in args
            for _, op, args in runtime.calls
        )
        == 2
    )


def test_peer_winning_restoration_race_is_never_overwritten(
    runtime, release, monkeypatch
):
    runtime.seed("index.html", b"previous", {"release-id": "previous-release"})

    def fail_public(*_):
        runtime.before_entry_put = lambda: runtime.seed(
            "index.html", b"peer", {"release-id": "peer-release"}
        )
        raise ValueError("bad CDN")

    monkeypatch.setattr(deploy, "verify_public", fail_public)
    with pytest.raises(deploy.DeploymentFailure) as failure:
        publish(runtime, release)
    assert failure.value.report["status"] == "restore_needs_review"
    assert runtime.objects["index.html"][1] == b"peer"


def test_concurrent_update_after_activation_is_not_rolled_back(
    runtime, release, monkeypatch
):
    runtime.seed("index.html", b"previous", {"release-id": "previous-release"})

    def peer(*_):
        runtime.seed("index.html", b"peer", {"release-id": "peer-release"})
        raise ValueError("peer updated")

    monkeypatch.setattr(deploy, "verify_public", peer)
    with pytest.raises(deploy.DeploymentFailure) as failure:
        publish(runtime, release)
    assert failure.value.report["status"] == "needs_review"
    assert runtime.objects["index.html"][1] == b"peer"


def test_timeout_does_not_blindly_repeat_activation(runtime, release):
    runtime.unknown_activation = True
    with pytest.raises(deploy.DeploymentFailure) as failure:
        publish(runtime, release)
    assert failure.value.report["status"] == "needs_review"
    roots = [
        a
        for _, op, a in runtime.calls
        if op == "put-object" and a[a.index("--key") + 1] == "index.html"
    ]
    assert len(roots) == 1


def test_conditional_write_rejects_a_race_after_last_preflight(runtime, release):
    runtime.seed("index.html", b"previous", {"release-id": "previous-release"})
    runtime.before_entry_put = lambda: runtime.seed(
        "index.html", b"peer", {"release-id": "peer-release"}
    )
    with pytest.raises(deploy.DeploymentFailure) as failure:
        publish(runtime, release)
    assert failure.value.report["status"] == "needs_review"
    assert runtime.objects["index.html"][1] == b"peer"


def test_changed_cloudfront_configuration_is_not_compensated(
    runtime, release, monkeypatch
):
    actual = deploy.preflight
    changed = []

    def verify(*_):
        changed.append(True)

    def preflight(*args):
        result = actual(*args)
        if changed:
            result["distribution_etag"] = "peer-config"
        return result

    monkeypatch.setattr(deploy, "verify_public", verify)
    monkeypatch.setattr(deploy, "preflight", preflight)
    with pytest.raises(deploy.DeploymentFailure) as failure:
        publish(runtime, release)
    assert failure.value.report["status"] == "needs_review"
    assert (
        runtime.objects["index.html"][1]
        == (release[0] / "site/index.html").read_bytes()
    )


def test_immutable_collision_and_wrong_rollback_confirmation_stop(runtime, release):
    runtime.seed(
        "releases/release-test/main.dart.js", b"different", cache=IMMUTABLE_CACHE
    )
    with pytest.raises(ValueError, match="checksum"):
        publish(runtime, release)
    assert "index.html" not in runtime.objects
    with pytest.raises(ValueError, match="active release"):
        publish(runtime, release, upload=False, expected_current="other-release")


def test_manual_workflow_has_no_push_trigger_and_limits_oidc():
    # BaseLoader keeps the YAML key 'on' as a string rather than YAML 1.1 boolean.
    value = yaml.load(
        (ROOT / ".github/workflows/deploy-frontend.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    assert set(value["on"]) == {"workflow_dispatch"}
    assert value["concurrency"]["cancel-in-progress"] == "false"
    assert "id-token" not in value["jobs"]["build"].get("permissions", {})
    for name in ("deploy", "rollback"):
        job = value["jobs"][name]
        assert "refs/heads/main" in job["if"]
        assert job["environment"] == "frontend-production"
        assert job["permissions"]["id-token"] == "write"
    for job in value["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                assert len(step["uses"].split("@")[1]) == 40


def test_stored_release_can_be_loaded_without_regeneration(runtime, release, tmp_path):
    publish(runtime, release)
    loaded = deploy.load_remote(runtime, TARGET, "release-test", tmp_path / "download")
    assert loaded == release[1]


class ConfigAWS:
    def __init__(self):
        arn = f"arn:aws:cloudfront::{TARGET['account']}:distribution/{TARGET['distribution_id']}"
        tags = [
            {"Key": k, "Value": v}
            for k, v in {
                "Component": "frontend",
                "Application": "garbage-guide",
                "ManagedBy": "Terraform",
                "Environment": "dev",
                "Project": "U-22",
            }.items()
        ]
        self.responses = {
            "get-caller-identity": {"Account": TARGET["account"]},
            "get-bucket-location": {"LocationConstraint": TARGET["region"]},
            "get-bucket-tagging": {"TagSet": tags},
            "get-public-access-block": {
                "PublicAccessBlockConfiguration": dict.fromkeys(
                    [
                        "BlockPublicAcls",
                        "IgnorePublicAcls",
                        "BlockPublicPolicy",
                        "RestrictPublicBuckets",
                    ],
                    True,
                )
            },
            "get-bucket-policy-status": {"PolicyStatus": {"IsPublic": False}},
            "get-bucket-versioning": {"Status": "Enabled"},
            "get-bucket-encryption": {
                "ServerSideEncryptionConfiguration": {
                    "Rules": [
                        {
                            "ApplyServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "AES256"
                            }
                        }
                    ]
                }
            },
            "get-bucket-ownership-controls": {
                "OwnershipControls": {
                    "Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]
                }
            },
            "list-tags-for-resource": {"Tags": {"Items": tags}},
            "get-origin-access-control": {
                "OriginAccessControl": {
                    "OriginAccessControlConfig": {
                        "SigningBehavior": "always",
                        "SigningProtocol": "sigv4",
                        "OriginAccessControlOriginType": "s3",
                    }
                }
            },
            "get-cache-policy": {
                "CachePolicy": {"CachePolicyConfig": {"MinTTL": 0, "DefaultTTL": 0}}
            },
            "get-distribution": {
                "ETag": "cf-v1",
                "Distribution": {
                    "ARN": arn,
                    "Status": "Deployed",
                    "DomainName": "test.cloudfront.net",
                    "DistributionConfig": {
                        "Enabled": True,
                        "DefaultRootObject": "index.html",
                        "ViewerCertificate": {"CloudFrontDefaultCertificate": True},
                        "Origins": {
                            "Items": [
                                {
                                    "Id": "web",
                                    "DomainName": f"{TARGET['bucket']}.s3.{TARGET['region']}.amazonaws.com",
                                    "OriginAccessControlId": "oac",
                                }
                            ]
                        },
                        "DefaultCacheBehavior": {
                            "TargetOriginId": "web",
                            "ViewerProtocolPolicy": "redirect-to-https",
                            "AllowedMethods": {"Items": ["GET", "HEAD"]},
                            "CachePolicyId": "cache",
                        },
                    },
                },
            },
        }

    def call(self, _service, operation, *_args):
        if operation == "head-object":
            raise deploy.AwsError("An error occurred (404)")
        assert operation in self.responses, operation
        return copy.deepcopy(self.responses[operation])


def test_target_preflight_accepts_only_dedicated_private_frontend():
    assert (
        deploy.preflight(ConfigAWS(), TARGET)["web_url"]
        == "https://test.cloudfront.net"
    )


def test_preflight_accepts_empty_aws_associations():
    aws = ConfigAWS()
    config = aws.responses["get-distribution"]["Distribution"]["DistributionConfig"]
    for key in ("CacheBehaviors", "CustomErrorResponses", "OriginGroups"):
        config[key] = {"Quantity": 0}
    for key in (
        "FunctionAssociations",
        "LambdaFunctionAssociations",
        "TrustedSigners",
        "TrustedKeyGroups",
    ):
        config["DefaultCacheBehavior"][key] = {"Quantity": 0}
    config.update(Staging=False, ContinuousDeploymentPolicyId="")
    deploy.preflight(aws, TARGET)


@pytest.mark.parametrize(
    "key",
    [
        "CacheBehaviors",
        "CustomErrorResponses",
        "OriginGroups",
        "ContinuousDeploymentPolicyId",
        "Staging",
        "ConnectionFunctionAssociation",
    ],
)
def test_preflight_rejects_unexpected_distribution_routing(key):
    aws = ConfigAWS()
    config = aws.responses["get-distribution"]["Distribution"]["DistributionConfig"]
    if key == "Staging":
        config[key] = True
    elif key == "ContinuousDeploymentPolicyId":
        config[key] = "unexpected-policy"
    elif key == "ConnectionFunctionAssociation":
        config[key] = {"Id": "unexpected-function"}
    else:
        config[key] = {"Quantity": 1, "Items": [{"unexpected": "override"}]}
    with pytest.raises(ValueError, match="routing/error"):
        deploy.preflight(aws, TARGET)


@pytest.mark.parametrize(
    "key",
    [
        "FunctionAssociations",
        "LambdaFunctionAssociations",
        "OriginRequestPolicyId",
        "TrustedSigners",
        "TrustedKeyGroups",
    ],
)
def test_preflight_rejects_edge_rewrites_and_private_viewer_policies(key):
    aws = ConfigAWS()
    config = aws.responses["get-distribution"]["Distribution"]["DistributionConfig"]
    config["DefaultCacheBehavior"][key] = (
        "unexpected-policy"
        if key == "OriginRequestPolicyId"
        else {"Quantity": 1, "Items": [{"unexpected": "override"}]}
    )
    with pytest.raises(ValueError, match="rewriting or private"):
        deploy.preflight(aws, TARGET)


@pytest.mark.parametrize(
    "case",
    [
        "account",
        "region",
        "tags",
        "public",
        "versioning",
        "origin",
        "oac",
        "ttl",
        "pending",
    ],
)
def test_target_preflight_rejects_unexpected_resources(case):
    aws = ConfigAWS()
    r = aws.responses
    if case == "account":
        r["get-caller-identity"]["Account"] = "999999999999"
    elif case == "region":
        r["get-bucket-location"]["LocationConstraint"] = "us-west-2"
    elif case == "tags":
        r["get-bucket-tagging"]["TagSet"] = []
    elif case == "public":
        r["get-public-access-block"]["PublicAccessBlockConfiguration"][
            "BlockPublicPolicy"
        ] = False
    elif case == "versioning":
        r["get-bucket-versioning"]["Status"] = "Suspended"
    elif case == "origin":
        r["get-distribution"]["Distribution"]["DistributionConfig"]["Origins"]["Items"][
            0
        ]["DomainName"] = "existing-backend.internal"
    elif case == "oac":
        r["get-origin-access-control"]["OriginAccessControl"][
            "OriginAccessControlConfig"
        ]["SigningBehavior"] = "never"
    elif case == "ttl":
        r["get-cache-policy"]["CachePolicy"]["CachePolicyConfig"]["MinTTL"] = 60
    else:
        r["get-distribution"]["Distribution"]["Status"] = "InProgress"
    with pytest.raises(ValueError):
        deploy.preflight(aws, TARGET)
