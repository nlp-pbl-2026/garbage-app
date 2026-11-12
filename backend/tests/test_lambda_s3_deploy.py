"""Mocked control-plane tests. Never upload, update, invoke Lambda or call Bedrock."""

import copy
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import deploy_lambda_s3 as deploy

ACCOUNT, REGION, FUNCTION, BUCKET = (
    "123456789012",
    "ap-northeast-1",
    "test-api",
    "test-private-bucket",
)
ARN = f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{FUNCTION}"


class FakeAws:
    def __init__(self, original, candidate):
        self.config = dict(
            FunctionArn=ARN,
            Runtime="python3.12",
            Architectures=["arm64"],
            Handler="app.lambda_main.handler",
            PackageType="Zip",
            State="Active",
            LastUpdateStatus="Successful",
            RevisionId="before",
            CodeSha256=deploy.aws_sha(original),
            Environment={
                "Variables": {
                    "USE_BEDROCK_KNOWLEDGE_BASE": "false",
                    "LEXICAL_SEARCH_ENABLED": "false",
                    "SECRET": "do-not-print",
                }
            },
        )
        self.candidate = candidate
        self.original = original
        self.calls, self.objects = [], {}
        self.account = ACCOUNT
        self.public = False
        self.location = REGION
        self.drift_after_upload = False
        self.fail_put = False
        self.fail_update = False
        self.fail_wait = False
        self.bad_checksum = False
        self.management = {"UpdateRuntimeOn": "Auto", "RuntimeVersionArn": None}
        self.patch_after_update = False

    def call(self, service, operation, *args):
        args = list(map(str, args))
        self.calls.append((service, operation, args))
        if service == "sts":
            return {"Account": self.account}
        if service == "lambda":
            if operation == "get-runtime-management-config":
                return {"FunctionArn": ARN, **self.management}
            if operation == "get-function":
                return {
                    "Configuration": copy.deepcopy(self.config),
                    "Code": {"Location": "https://backup.test/?signed=do-not-print"},
                }
            if operation == "get-layer-version-by-arn":
                return {
                    "Content": {
                        "Location": "https://backup.test/layer",
                        "CodeSha256": deploy.aws_sha(self.original),
                    }
                }
            if operation == "update-function-code":
                if self.fail_update:
                    raise deploy.AwsError(operation, "PreconditionFailedException")
                assert (
                    args[args.index("--revision-id") + 1] == self.config["RevisionId"]
                )
                key = args[args.index("--s3-key") + 1]
                obj = self.objects[key]
                assert args[args.index("--s3-object-version") + 1] == obj["VersionId"]
                self.config["RevisionId"] += "-updated"
                self.config["CodeSha256"] = obj["ChecksumSHA256"]
                return copy.deepcopy(self.config)
            if operation == "wait":
                if self.fail_wait:
                    raise deploy.AwsError(operation, "WaiterFailure")
                if self.patch_after_update:
                    self.config["RuntimeVersionConfig"] = {
                        "RuntimeVersionArn": f"arn:aws:lambda:{REGION}::runtime:bbbb"
                    }
                return {}
        if service == "apigatewayv2":
            return {
                "Items": (
                    [{"IntegrationId": "i", "IntegrationUri": ARN}]
                    if operation == "get-integrations"
                    else [{"RouteKey": "$default", "Target": "integrations/i"}]
                )
            }
        if service == "s3api":
            if operation == "get-bucket-location":
                return {"LocationConstraint": self.location}
            if operation == "get-public-access-block":
                return {
                    "PublicAccessBlockConfiguration": {
                        k: not self.public
                        for k in (
                            "BlockPublicAcls",
                            "IgnorePublicAcls",
                            "BlockPublicPolicy",
                            "RestrictPublicBuckets",
                        )
                    }
                }
            if operation == "get-bucket-versioning":
                return {"Status": "Enabled"}
            if operation == "get-bucket-encryption":
                return {
                    "ServerSideEncryptionConfiguration": {
                        "Rules": [
                            {
                                "ApplyServerSideEncryptionByDefault": {
                                    "SSEAlgorithm": "AES256"
                                }
                            }
                        ]
                    }
                }
            if operation == "get-bucket-ownership-controls":
                return {
                    "OwnershipControls": {
                        "Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]
                    }
                }
            if operation == "get-bucket-policy-status":
                return {"PolicyStatus": {"IsPublic": False}}
            if operation == "put-object":
                if self.fail_put:
                    raise deploy.AwsError(operation, "AccessDenied")
                key = args[args.index("--key") + 1]
                if key in self.objects:
                    raise deploy.AwsError(operation, "PreconditionFailed")
                source = Path(args[args.index("--body") + 1])
                assert args[args.index("--if-none-match") + 1] == "*"
                assert args[args.index("--checksum-sha256") + 1] == deploy.aws_sha(
                    source
                )
                self.objects[key] = {
                    "VersionId": "v" + str(len(self.objects)),
                    "ChecksumSHA256": deploy.aws_sha(source),
                    "ContentLength": source.stat().st_size,
                    "ServerSideEncryption": "AES256",
                }
                return {"VersionId": self.objects[key]["VersionId"]}
            if operation == "head-object":
                key = args[args.index("--key") + 1]
                if self.drift_after_upload and "/backups/" not in key:
                    self.config["RevisionId"] = "someone-else"
                result = copy.deepcopy(self.objects[key])
                if self.bad_checksum:
                    result["ChecksumSHA256"] = "wrong"
                return result
        raise AssertionError((service, operation, args))

    @property
    def writes(self):
        return [
            (s, o)
            for s, o, _ in self.calls
            if o in ("put-object", "update-function-code")
        ]


@pytest.fixture
def context(tmp_path, monkeypatch):
    previous, candidate = tmp_path / "previous.zip", tmp_path / "candidate.zip"
    previous.write_bytes(b"old archive")
    candidate.write_bytes(b"new archive")
    aws = FakeAws(previous, candidate)
    monkeypatch.setattr(deploy, "Aws", lambda *args: aws)

    def validate(path):
        return dict(
            zip_sha256=deploy.sha(path),
            code_sha256=deploy.aws_sha(path),
            uncompressed_bytes=100,
        )

    monkeypatch.setattr(deploy, "validate_zip", validate)
    plan = dict(
        schema_version=1,
        account=ACCOUNT,
        region=REGION,
        function=FUNCTION,
        bucket=BUCKET,
        api_url=f"https://abc.execute-api.{REGION}.amazonaws.com",
        profile=None,
        candidate=validate(candidate),
        previous=dict(
            revision_id="before",
            code_sha256=deploy.aws_sha(previous),
            config_sha256=deploy.fingerprint(aws.config),
            zip_sha256=deploy.sha(previous),
        ),
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    (tmp_path / "configuration-before.json").write_text(json.dumps(aws.config))
    args = SimpleNamespace(
        command="deploy", plan=plan_path, execute=False, confirm_target=None
    )
    monkeypatch.setattr(deploy, "verify_api", lambda plan: 44)
    return SimpleNamespace(
        aws=aws,
        plan=plan,
        path=plan_path,
        args=args,
        directory=tmp_path,
        candidate=candidate,
        previous=previous,
        monkeypatch=monkeypatch,
    )


def execute(ctx, command="deploy"):
    ctx.args.command, ctx.args.execute = command, True
    ctx.args.confirm_target = deploy.target_token(ctx.plan)
    deploy.run_plan(ctx.args)


def test_review_defaults_to_no_aws_writes(context, capsys):
    deploy.run_plan(context.args)
    assert not context.aws.writes
    assert "do-not-print" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "kind",
    [
        "account",
        "region",
        "public",
        "runtime",
        "busy",
        "revision",
        "code",
        "environment",
        "dataset",
    ],
)
def test_unexpected_target_or_concurrent_changes_stop_before_writes(context, kind):
    a = context.aws
    if kind == "account":
        a.account = "999999999999"
    if kind == "region":
        a.location = "us-east-1"
    if kind == "public":
        a.public = True
    if kind == "runtime":
        a.config["Architectures"] = ["x86_64"]
    if kind == "busy":
        a.config["LastUpdateStatus"] = "InProgress"
    if kind == "revision":
        a.config["RevisionId"] = "changed"
    if kind == "code":
        a.config["CodeSha256"] = "changed"
    if kind == "environment":
        a.config["Environment"]["Variables"]["SECRET"] = "changed"
    if kind == "dataset":
        a.config["Environment"]["Variables"][
            "MUNICIPALITY_CATALOG_PATH"
        ] = "/tmp/old-catalog.json"
    with pytest.raises(deploy.DeployError):
        execute(context)
    assert not a.writes


def test_execute_needs_exact_confirmation(context):
    context.args.execute = True
    context.args.confirm_target = ACCOUNT
    with pytest.raises(deploy.DeployError, match="confirmation"):
        deploy.run_plan(context.args)
    assert not context.aws.writes


def test_modified_local_candidate_and_backup_are_rejected(context):
    context.candidate.write_bytes(b"tampered")
    with pytest.raises(deploy.DeployError, match="Candidate"):
        execute(context)
    assert not context.aws.writes
    context.previous.write_bytes(b"tampered")
    with pytest.raises(deploy.DeployError, match="Backup"):
        execute(context)
    assert not context.aws.writes


def test_deploy_uses_version_checksum_revision_and_never_changes_configuration(context):
    before = deploy.fingerprint(context.aws.config)
    execute(context)
    assert deploy.fingerprint(context.aws.config) == before
    writes = context.aws.writes
    assert writes == [
        ("s3api", "put-object"),
        ("s3api", "put-object"),
        ("lambda", "update-function-code"),
    ]
    command = next(
        args for _, op, args in context.aws.calls if op == "update-function-code"
    )
    assert (
        "--s3-object-version" in command
        and "--revision-id" in command
        and "--no-publish" in command
    )
    assert not {"--zip-file", "--environment", "--architectures"}.intersection(command)
    receipt = json.loads((context.directory / "receipt.json").read_text())
    assert receipt["status"] == "verified" and receipt["api_checks"] == 44
    assert (context.directory / "receipt.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("failure", ["fail_put", "bad_checksum", "drift_after_upload"])
def test_s3_failure_or_drift_after_upload_does_not_update_lambda(context, failure):
    setattr(context.aws, failure, True)
    with pytest.raises(deploy.DeployError):
        execute(context)
    assert ("lambda", "update-function-code") not in context.aws.writes


def test_aws_revision_precondition_is_used_for_the_final_race(context):
    context.aws.fail_update = True
    with pytest.raises(deploy.AwsError):
        execute(context)
    assert context.aws.config["RevisionId"] == "before"
    assert not (context.directory / "receipt.json").exists()


def test_wait_failure_keeps_a_recovery_receipt(context):
    context.aws.fail_wait = True
    with pytest.raises(deploy.AwsError):
        execute(context)
    assert (
        json.loads((context.directory / "receipt.json").read_text())["status"]
        == "update_requested"
    )


def test_api_failure_is_explicit_and_manual_rollback_restores_code_only(context):
    def fail(_):
        raise ValueError("HTTP failed")

    context.monkeypatch.setattr(deploy, "verify_api", fail)
    with pytest.raises(deploy.DeployError, match="code was updated"):
        execute(context)
    assert (
        json.loads((context.directory / "receipt.json").read_text())["status"]
        == "api_verification_failed"
    )
    execute(context, "rollback")
    assert context.aws.config["CodeSha256"] == context.plan["previous"]["code_sha256"]
    assert (
        deploy.fingerprint(context.aws.config)
        == context.plan["previous"]["config_sha256"]
    )


def test_rollback_refuses_to_overwrite_another_actors_revision(context):
    execute(context)
    context.aws.config["RevisionId"] = "another-actor"
    before = len(context.aws.writes)
    with pytest.raises(deploy.DeployError, match="changed"):
        execute(context, "rollback")
    assert len(context.aws.writes) == before


def test_concurrent_update_during_api_checks_is_not_reported_as_verified(context):
    def another_update(_):
        context.aws.config["RevisionId"] = "another-actor"
        return 44

    context.monkeypatch.setattr(deploy, "verify_api", another_update)
    with pytest.raises(deploy.DeployError, match="code was updated"):
        execute(context)
    assert (
        json.loads((context.directory / "receipt.json").read_text())["status"]
        == "api_verification_failed"
    )
    with pytest.raises(deploy.DeployError, match="changed"):
        execute(context, "rollback")


def test_rollback_on_original_code_does_nothing(context):
    execute(context, "rollback")
    assert not context.aws.writes


def test_verify_refuses_to_test_the_old_release(context):
    context.args.command = "verify"
    with pytest.raises(deploy.DeployError, match="not installed"):
        deploy.run_plan(context.args)


def test_prepare_only_reads_aws_and_creates_private_local_backup(context, capsys):
    folder = context.directory / "private-backup"
    context.monkeypatch.setattr(
        deploy,
        "download",
        lambda url, path: Path(path).write_bytes(context.previous.read_bytes()),
    )
    args = SimpleNamespace(
        account=ACCOUNT,
        region=REGION,
        function=FUNCTION,
        bucket=BUCKET,
        api_url=context.plan["api_url"],
        profile=None,
        zip=context.candidate,
        backup_dir=folder,
    )
    deploy.prepare(args)
    assert not context.aws.writes
    assert folder.stat().st_mode & 0o777 == 0o700
    assert (folder / "configuration-before.json").stat().st_mode & 0o777 == 0o600
    assert "do-not-print" not in capsys.readouterr().out
    with pytest.raises(deploy.DeployError, match="new backup"):
        deploy.prepare(args)


def test_layer_size_is_added_to_the_package_limit(context):
    context.aws.config["Layers"] = [{"Arn": "test-layer"}]
    context.monkeypatch.setattr(
        deploy,
        "download",
        lambda url, path: Path(path).write_bytes(context.previous.read_bytes()),
    )
    context.monkeypatch.setattr(deploy, "zip_size", lambda path: deploy.MAX_UNZIPPED)
    args = SimpleNamespace(
        account=ACCOUNT,
        region=REGION,
        function=FUNCTION,
        bucket=BUCKET,
        api_url=context.plan["api_url"],
        profile=None,
        zip=context.candidate,
        backup_dir=context.directory / "too-large",
    )
    with pytest.raises(deploy.DeployError, match="Layers exceed"):
        deploy.prepare(args)
    assert not context.aws.writes


@pytest.mark.parametrize("incorrect", [False, True])
def test_public_api_checks_compare_local_profile_data_without_model_calls(
    monkeypatch, incorrect
):
    from app.routers import search_router
    from app.services import region_registry_service

    area = {"id": "test-area", "rule_profile_id": "test-profile"}
    registry = SimpleNamespace(
        areas={"test-area": area},
        profiles={"test-profile": SimpleNamespace(categories={"burn": "燃えるごみ"})},
    )
    catalog = SimpleNamespace(entries={"test-city": {}}, registry=lambda city: registry)
    monkeypatch.setattr(region_registry_service, "get_registry", lambda: catalog)
    expected = {
        "municipality_id": "test-city",
        "items": [{"item_id": "one"}],
        "total": 1,
    }

    async def items(city, category, search, district_id):
        assert (city, category, search, district_id) == (
            "test-city",
            "burn",
            None,
            "test-area",
        )
        return SimpleNamespace(model_dump=lambda: expected)

    monkeypatch.setattr(search_router, "list_waste_items", items)
    monkeypatch.setattr(deploy.time, "sleep", lambda _: None)
    requests = []

    def get(url, **kwargs):
        requests.append(url)
        body = {"status": "ok"} if url.endswith("/api/health") else dict(expected)
        if incorrect and not url.endswith("/api/health"):
            body["municipality_id"] = "different-city"
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(deploy, "urlopen", get)
    if incorrect:
        with pytest.raises(deploy.DeployError, match="verification failed"):
            deploy.verify_api({"api_url": "https://example.test"})
    else:
        assert deploy.verify_api({"api_url": "https://example.test"}) == 2
    assert len(requests) == 2
    assert "/items/test-city?" in requests[1]


@pytest.mark.parametrize(
    "failure", [None, "missing-module", "stale-data", "unsafe-path", "source-pdf"]
)
def test_archive_review_rejects_incomplete_stale_or_unsafe_payload(
    tmp_path, monkeypatch, failure
):
    import package_backend_data
    import verify_municipality_data

    monkeypatch.setattr(deploy, "ROOT", tmp_path)
    catalog = tmp_path / "data/regions/catalog.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes(b"catalog")
    payload = tmp_path / "data/regions/example/generated/calendar.json"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"reviewed calendar")
    monkeypatch.setattr(
        package_backend_data, "runtime_files", lambda _: {catalog, payload}
    )
    monkeypatch.setattr(
        verify_municipality_data,
        "verify",
        lambda: {"municipalities": 20, "profiles": 43, "indices": 21},
    )
    entries = {
        "data/regions/catalog.json": catalog.read_bytes(),
        "data/regions/example/generated/calendar.json": payload.read_bytes(),
    }
    for name in deploy.RUNTIME_APP_FILES:
        source = tmp_path / "backend" / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"# reviewed code\n")
        entries[name] = source.read_bytes()
    entries.update(
        {
            f"{p}/__init__.py": b""
            for p in (
                "mangum",
                "fastapi",
                "pydantic",
                "pydantic_core",
                "boto3",
                "botocore",
                "numpy",
            )
        }
    )
    if failure == "missing-module":
        entries.pop("app/services/waste_guide_service.py")
    if failure == "stale-data":
        entries["data/regions/example/generated/calendar.json"] = b"old calendar"
    if failure == "unsafe-path":
        entries["../escape"] = b"unsafe"
    if failure == "source-pdf":
        entries["data/regions/example/source/calendar.pdf"] = b"source"
    path = tmp_path / "package.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in entries.items():
            archive.writestr(name, body)
    if failure:
        with pytest.raises(deploy.DeployError):
            deploy.validate_zip(path)
    else:
        result = deploy.validate_zip(path)
        assert result["runtime_files"] == 2 and result["municipalities"] == 20


def runtime_baseline(ctx, mode="Auto"):
    ctx.aws.config["RuntimeVersionConfig"] = {
        "RuntimeVersionArn": f"arn:aws:lambda:{REGION}::runtime:aaaa"
    }
    ctx.aws.management["UpdateRuntimeOn"] = mode
    if mode == "Manual":
        ctx.aws.management["RuntimeVersionArn"] = ctx.aws.config[
            "RuntimeVersionConfig"
        ]["RuntimeVersionArn"]
    ctx.plan["previous"]["config_sha256"] = deploy.fingerprint(ctx.aws.config)
    ctx.path.write_text(json.dumps(ctx.plan))
    (ctx.directory / "configuration-before.json").write_text(json.dumps(ctx.aws.config))


def pending_legacy_deployment(ctx):
    runtime_baseline(ctx)
    receipt = dict(
        revision_id="installed",
        code_sha256=ctx.plan["candidate"]["code_sha256"],
        config_sha256=ctx.plan["previous"]["config_sha256"],
        status="update_requested",
    )
    (ctx.directory / "receipt.json").write_text(json.dumps(receipt))
    ctx.aws.config.update(
        RevisionId="installed",
        CodeSha256=receipt["code_sha256"],
        RuntimeVersionConfig={
            "RuntimeVersionArn": f"arn:aws:lambda:{REGION}::runtime:bbbb"
        },
    )
    ctx.args.command = "verify"
    return receipt


@pytest.mark.parametrize("mode", ["Auto", "FunctionUpdate"])
def test_managed_patch_during_own_update_succeeds_and_rolls_back_without_env_changes(
    context, mode
):
    runtime_baseline(context, mode)
    context.plan["runtime_management"] = dict(context.aws.management)
    context.path.write_text(json.dumps(context.plan))
    before = copy.deepcopy(context.aws.config["Environment"])
    context.aws.patch_after_update = True
    execute(context)
    receipt = json.loads((context.directory / "receipt.json").read_text())
    assert receipt["status"] == "verified"
    assert receipt["config_sha256"] == context.plan["previous"]["config_sha256"]
    assert receipt["post_config_sha256"] == deploy.fingerprint(context.aws.config)
    execute(context, "rollback")
    assert context.aws.config["CodeSha256"] == context.plan["previous"]["code_sha256"]
    assert context.aws.config["Environment"] == before


def test_runtime_patch_drift_before_update_is_still_rejected(context):
    runtime_baseline(context)
    context.aws.config["RuntimeVersionConfig"][
        "RuntimeVersionArn"
    ] = f"arn:aws:lambda:{REGION}::runtime:bbbb"
    with pytest.raises(deploy.DeployError, match="changed"):
        execute(context)
    assert not context.aws.writes


def test_manual_patch_change_during_update_is_not_accepted(context):
    runtime_baseline(context, "Manual")
    context.aws.patch_after_update = True
    with pytest.raises(deploy.DeployError, match="Manual"):
        execute(context)
    assert (
        json.loads((context.directory / "receipt.json").read_text())["status"]
        == "update_requested"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("Runtime", "python3.13"),
        ("Handler", "other.handler"),
        ("Architectures", ["x86_64"]),
        ("Environment", {"Variables": {"SECRET": "different"}}),
        ("Role", "other-role"),
        ("Layers", [{"Arn": "other-layer"}]),
        ("MemorySize", 1024),
        ("Timeout", 90),
        ("RuntimeVersionConfig", {"RuntimeVersionArn": None}),
        (
            "RuntimeVersionConfig",
            {"RuntimeVersionArn": "arn:aws:lambda:us-east-1::runtime:bbbb"},
        ),
        (
            "RuntimeVersionConfig",
            {
                "RuntimeVersionArn": f"arn:aws:lambda:{REGION}::runtime:bbbb",
                "Error": {"ErrorCode": "Error", "Message": "do-not-print"},
            },
        ),
        (
            "RuntimeVersionConfig",
            {
                "RuntimeVersionArn": f"arn:aws:lambda:{REGION}::runtime:bbbb",
                "FutureField": True,
            },
        ),
    ],
)
def test_resume_rejects_unexpected_configuration_even_with_explicit_revision(
    context, field, value
):
    pending_legacy_deployment(context)
    context.aws.config[field] = value
    context.args.expected_revision_id = "installed"
    with pytest.raises(deploy.DeployError):
        deploy.run_plan(context.args)
    assert not context.aws.writes


def test_read_only_resume_uses_old_plan_and_never_rewrites_original_records(
    context, capsys
):
    pending_legacy_deployment(context)
    protected = {p: p.read_bytes() for p in context.directory.iterdir() if p.is_file()}
    context.args.report = context.directory / "verification-new.json"
    deploy.run_plan(context.args)
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "verified" and report["read_only_api_checks"] == 44
    assert not report["runtime_management_baseline_recorded"]
    assert context.args.report.stat().st_mode & 0o777 == 0o600
    assert all(p.read_bytes() == body for p, body in protected.items())
    assert not context.aws.writes
    context.args.report = context.directory / "receipt.json"
    with pytest.raises(FileExistsError):
        deploy.run_plan(context.args)
    assert all(p.read_bytes() == body for p, body in protected.items())


def test_new_plans_detect_runtime_management_mode_changes(context):
    pending_legacy_deployment(context)
    context.plan["runtime_management"] = dict(context.aws.management)
    context.path.write_text(json.dumps(context.plan))
    context.aws.management["UpdateRuntimeOn"] = "FunctionUpdate"
    with pytest.raises(deploy.DeployError, match="mode changed"):
        deploy.run_plan(context.args)
    assert not context.aws.writes


def test_revision_override_is_explicit_read_only_and_still_detects_further_changes(
    context,
):
    pending_legacy_deployment(context)
    context.aws.config["RevisionId"] = "reviewed-revision"
    with pytest.raises(deploy.DeployError, match="revision changed"):
        deploy.run_plan(context.args)
    context.args.expected_revision_id = "reviewed-revision"
    deploy.run_plan(context.args)
    assert not context.aws.writes

    def race(_):
        context.aws.config["RevisionId"] = "someone-else"
        return 44

    context.monkeypatch.setattr(deploy, "verify_api", race)
    with pytest.raises(deploy.DeployError, match="changed"):
        deploy.run_plan(context.args)
    context.args.command = "rollback"
    with pytest.raises(deploy.DeployError, match="revision changed"):
        deploy.run_plan(context.args)
    assert not context.aws.writes


@pytest.mark.parametrize("status", ["InProgress", "Failed"])
def test_resume_requires_completed_update(context, status):
    pending_legacy_deployment(context)
    context.aws.config["LastUpdateStatus"] = status
    with pytest.raises(deploy.DeployError):
        deploy.run_plan(context.args)
    assert not context.aws.writes


def test_runtime_management_read_access_denied_fails_closed(context):
    call = context.aws.call

    def denied(service, op, *args):
        if op == "get-runtime-management-config":
            raise deploy.AwsError(op, "AccessDeniedException")
        return call(service, op, *args)

    context.monkeypatch.setattr(context.aws, "call", denied)
    with pytest.raises(deploy.AwsError):
        execute(context)
    assert not context.aws.writes


def test_unchanged_manual_runtime_is_supported(context):
    runtime_baseline(context, "Manual")
    execute(context)
    assert (
        json.loads((context.directory / "receipt.json").read_text())["status"]
        == "verified"
    )


def test_mode_change_during_read_only_verification_is_detected(context):
    pending_legacy_deployment(context)

    def changed_mode(_):
        context.aws.management["UpdateRuntimeOn"] = "Manual"
        return 44

    context.monkeypatch.setattr(deploy, "verify_api", changed_mode)
    with pytest.raises(deploy.DeployError, match="mode changed during verification"):
        deploy.run_plan(context.args)
    assert not context.aws.writes


def test_failed_read_only_api_verification_leaves_old_receipt_intact(context):
    pending_legacy_deployment(context)
    before = (context.directory / "receipt.json").read_bytes()

    def failed(_):
        raise deploy.DeployError("API verification failed")

    context.monkeypatch.setattr(deploy, "verify_api", failed)
    with pytest.raises(deploy.DeployError, match="API verification failed"):
        deploy.run_plan(context.args)
    assert (context.directory / "receipt.json").read_bytes() == before
    assert not context.aws.writes


@pytest.mark.parametrize("command", ["deploy", "rollback"])
def test_revision_pin_cannot_be_used_for_aws_writes(context, command):
    context.monkeypatch.setattr(
        sys,
        "argv",
        [
            "deploy_lambda_s3.py",
            command,
            "--plan",
            str(context.path),
            "--expected-revision-id",
            "changed",
        ],
    )
    with pytest.raises(SystemExit) as error:
        deploy.main()
    assert error.value.code == 2
    assert not context.aws.writes
