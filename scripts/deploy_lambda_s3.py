#!/usr/bin/env python3
"""Prepare, review, deploy or roll back existing Lambda CODE only.

prepare/deploy/rollback are read-only against AWS unless --execute is given to
deploy/rollback together with the exact --confirm-target printed by prepare.
No Terraform, configuration updates, model calls or infrastructure creation/deletion.
"""

import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import time
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MAX_UNZIPPED = 250 * 1024**2
# Match the code-only Lambda entrypoint and its local service dependencies.
# main.py/auth/database belong to the local FastAPI process, not this package.
RUNTIME_APP_FILES = {
    "app/__init__.py",
    "app/config.py",
    "app/schemas.py",
    "app/lambda_main.py",
    "app/routers/__init__.py",
    "app/routers/search_router.py",
    "app/routers/frontend_data_router.py",
    "app/services/__init__.py",
    *(
        f"app/services/{module}.py"
        for module in (
            "calendar_service",
            "search_log_service",
            "item_search_service",
            "embedding_search_service",
            "region_registry_service",
            "nakajima_search_service",
            "nakajima_rule_service",
            "matsuyama_prompt_rules",
            "waste_guide_service",
            "frontend_data_service",
            "frontend_data_contract",
        )
    ),
}
VOLATILE_CONFIG = {
    "CodeSha256",
    "CodeSize",
    "LastModified",
    "RevisionId",
    "LastUpdateStatus",
    "LastUpdateStatusReason",
    "LastUpdateStatusReasonCode",
    "State",
    "StateReason",
    "StateReasonCode",
    "Version",
}


class DeployError(RuntimeError):
    pass


class AwsError(DeployError):
    def __init__(self, operation, code):
        self.code = code
        super().__init__(
            f"AWS {operation} failed ({code}); no configuration changes attempted"
        )


def require(condition, message):
    if not condition:
        raise DeployError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def aws_sha(path):
    return base64.b64encode(bytes.fromhex(sha(path))).decode()


def fingerprint(config):
    stable = {k: v for k, v in config.items() if k not in VOLATILE_CONFIG}
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def runtime_management(aws, plan):
    result = aws.call(
        "lambda", "get-runtime-management-config", "--function-name", plan["function"]
    )
    arn = (
        f"arn:aws:lambda:{plan['region']}:{plan['account']}:function:{plan['function']}"
    )
    require(
        result.get("FunctionArn") in (arn, arn + ":$LATEST"),
        "Unexpected runtime management target",
    )
    require(
        result.get("UpdateRuntimeOn") in {"Auto", "FunctionUpdate", "Manual"},
        "Unknown runtime update mode",
    )
    # Auto/FunctionUpdate do not return the currently running patch ARN here.
    return {
        "UpdateRuntimeOn": result["UpdateRuntimeOn"],
        "RuntimeVersionArn": result.get("RuntimeVersionArn"),
    }


def same_configuration_after_update(config, baseline, management):
    """Permit only an AWS-managed patch ARN change, never Runtime/role/env drift.

    fingerprint() itself stays strict for old plans and all pre-update checks.
    RuntimeVersionConfig.Error and unknown/new fields are not ignored.
    """
    before = baseline.get("RuntimeVersionConfig") or {}
    after = config.get("RuntimeVersionConfig") or {}
    require(not after.get("Error"), "Lambda reports a runtime version error")
    if before != after:
        require(
            management["UpdateRuntimeOn"] in {"Auto", "FunctionUpdate"},
            "Runtime patch changed in Manual mode; stop for review",
        )
        for value in (before, after):
            arn = value.get("RuntimeVersionArn")
            require(
                isinstance(arn, str)
                and re.fullmatch(
                    r"arn:aws:lambda:"
                    + re.escape(config["FunctionArn"].split(":")[3])
                    + r"::runtime:[A-Za-z0-9]+",
                    arn,
                ),
                "Missing or invalid managed runtime version ARN",
            )
        require(
            {k: v for k, v in before.items() if k != "RuntimeVersionArn"}
            == {k: v for k, v in after.items() if k != "RuntimeVersionArn"},
            "Runtime version metadata changed; stop for review",
        )
    comparable = dict(config)
    if "RuntimeVersionConfig" in baseline:
        comparable["RuntimeVersionConfig"] = baseline["RuntimeVersionConfig"]
    else:
        comparable.pop("RuntimeVersionConfig", None)
    require(
        fingerprint(comparable) == fingerprint(baseline),
        "Lambda configuration changed beyond the managed runtime patch; stop for review",
    )


def saved_baseline(directory, plan):
    baseline = json.loads((directory / "configuration-before.json").read_text())
    same_function(baseline, plan["previous"])
    return baseline


def same_deployment(config, expected, baseline, management, *, permit_failed=False):
    require(
        config.get("State") == "Active"
        and config.get("LastUpdateStatus") != "InProgress"
        and (permit_failed or config.get("LastUpdateStatus") == "Successful"),
        "Lambda update is not complete; wait and verify again",
    )
    require(
        config["RevisionId"] == expected["revision_id"]
        and config["CodeSha256"] == expected["code_sha256"],
        "Lambda code or revision changed; stop for review",
    )
    require(
        expected["config_sha256"] == fingerprint(baseline),
        "Receipt configuration baseline mismatch",
    )
    same_configuration_after_update(config, baseline, management)


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temporary, path)


class Aws:
    def __init__(self, region, profile=None):
        self.region, self.profile = region, profile

    def call(self, service, operation, *args):
        cmd = ["aws", "--region", self.region, "--no-cli-pager", "--output", "json"]
        if self.profile:
            cmd += ["--profile", self.profile]
        env = {**os.environ, "AWS_PAGER": "", "AWS_CLI_AUTO_PROMPT": "off"}
        result = subprocess.run(
            cmd + [service, operation, *map(str, args)],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode:
            match = re.search(r"\(([^()]+)\) when calling", result.stderr)
            # Never echo credentials, signed URLs, configuration or raw CLI output.
            raise AwsError(
                operation, match[1] if match else "CLI/authentication/network error"
            )
        return json.loads(result.stdout) if result.stdout.strip() else {}


def download(url, target):
    require(urlparse(url).scheme == "https", "Backup download must use HTTPS")
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream, urlopen(url, timeout=90) as source:
            total = 0
            while block := source.read(1024 * 1024):
                total += len(block)
                require(total <= MAX_UNZIPPED, "Unexpectedly large backup download")
                stream.write(block)
    except Exception:
        raise DeployError("Backup download failed; signed URL omitted") from None


def zip_size(path):
    with zipfile.ZipFile(path) as archive:
        return sum(i.file_size for i in archive.infolist())


def validate_zip(path):
    # Existing runtime staging validation checks CSV/NPZ/manifest/calendar pairs.
    from package_backend_data import runtime_files
    from verify_municipality_data import verify

    report = verify()
    require(report["municipalities"] == 20, "All twenty municipalities are required")
    catalog = ROOT / "data/regions/catalog.json"
    sources = {
        "data/regions/" + str(p.relative_to(catalog.parent)): p
        for p in runtime_files(catalog)
        if p != catalog.resolve()
    }
    sources["data/regions/catalog.json"] = catalog
    with zipfile.ZipFile(path) as archive:
        seen = set()
        for entry in archive.infolist():
            name = entry.filename
            relative = PurePosixPath(name)
            require(
                not relative.is_absolute()
                and ".." not in relative.parts
                and "\\" not in name
                and ":" not in name
                and stat.S_IFMT(entry.external_attr >> 16)
                in (0, stat.S_IFREG, stat.S_IFDIR)
                and name not in seen,
                "Unsafe or duplicate ZIP entry",
            )
            seen.add(name)
            require(
                not (
                    "/source/" in name
                    or name.startswith(".env")
                    or name.endswith((".pdf", ".html", ".jsonl", ".png"))
                ),
                "Source documents, images, credentials or logs must not ship",
            )
            if name.startswith("app/") and name.endswith(".py"):
                local = ROOT / "backend" / name
                require(
                    local.is_file() and archive.read(name) == local.read_bytes(),
                    f"Packaged code differs from checkout: {name}",
                )
        for name, source in sources.items():
            require(
                name in seen and archive.read(name) == source.read_bytes(),
                f"Missing or stale packaged runtime data: {name}",
            )
        require(
            {n for n in seen if n.startswith("data/regions/") and not n.endswith("/")}
            == set(sources),
            "Unexpected municipality payload files",
        )
        require(RUNTIME_APP_FILES <= seen, "Missing Lambda runtime modules")
        require(
            all(
                f"{name}/__init__.py" in seen
                for name in (
                    "mangum",
                    "fastapi",
                    "pydantic",
                    "pydantic_core",
                    "boto3",
                    "botocore",
                    "numpy",
                )
            ),
            "Missing Lambda dependency packages",
        )
        size = sum(i.file_size for i in archive.infolist())
    require(size <= MAX_UNZIPPED, "ZIP exceeds Lambda's unzipped limit")
    return dict(
        zip_sha256=sha(path),
        code_sha256=aws_sha(path),
        compressed_bytes=Path(path).stat().st_size,
        uncompressed_bytes=size,
        municipalities=20,
        profiles=report["profiles"],
        indices=report["indices"],
        runtime_files=len(sources),
    )


def target_token(plan):
    return ":".join(plan[k] for k in ("account", "region", "function", "bucket"))


def preflight(aws, plan, *, permit_failed=False):
    identity = aws.call("sts", "get-caller-identity")
    require(identity["Account"] == plan["account"], "Unexpected AWS account")
    result = aws.call("lambda", "get-function", "--function-name", plan["function"])
    config = result["Configuration"]
    require(
        not (config.get("RuntimeVersionConfig") or {}).get("Error"),
        "Lambda reports a runtime version error",
    )
    management = runtime_management(aws, plan)
    if "runtime_management" in plan:
        require(
            management == plan["runtime_management"],
            "Runtime management mode changed; stop for review",
        )
    result["RuntimeManagement"] = management
    arn = (
        f"arn:aws:lambda:{plan['region']}:{plan['account']}:function:{plan['function']}"
    )
    require(config["FunctionArn"] == arn, "Unexpected Lambda ARN/region/account")
    require(
        config.get("Runtime") == "python3.12"
        and config.get("Architectures") == ["arm64"]
        and config.get("PackageType", "Zip") == "Zip"
        and config.get("Handler") == "app.lambda_main.handler",
        "Unexpected Lambda runtime/handler",
    )
    require(
        config.get("State") == "Active"
        and config.get("LastUpdateStatus") != "InProgress",
        "Lambda is not active or another update is in progress",
    )
    require(
        permit_failed or config.get("LastUpdateStatus") == "Successful",
        "Previous Lambda update failed",
    )
    env = config.get("Environment", {}).get("Variables", {})
    require(
        env.get("USE_BEDROCK_KNOWLEDGE_BASE") == "false"
        and env.get("LEXICAL_SEARCH_ENABLED") == "false",
        "Unexpected RAG search mode",
    )
    require(
        env.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0") == "amazon.nova-lite-v1:0"
        and env.get("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
        == "amazon.titan-embed-text-v2:0",
        "Unexpected RAG models",
    )
    standard_paths = {
        "MUNICIPALITY_CATALOG_PATH": "data/regions/catalog.json",
        "REGION_REGISTRY_PATH": "data/regions/matsuyama/registry.json",
        "KNOWLEDGE_ITEMS_PATH": "data/regions/matsuyama/common/knowledge/items.csv",
        "EMBEDDING_INDEX_PATH": "data/regions/matsuyama/common/knowledge/item_embeddings.npz",
        "CALENDAR_BUNDLE_PATH": "data/regions/matsuyama/generated/calendar-2026.json",
        "NAKAJIMA_ITEMS_PATH": "data/regions/matsuyama/generated/nakajima_items.csv",
    }
    for key, relative in standard_paths.items():
        require(
            not env.get(key) or env[key] in (relative, "/var/task/" + relative),
            f"Custom dataset override {key} needs review; configuration is never rewritten",
        )
    bucket = plan["bucket"]
    owner = ("--bucket", bucket, "--expected-bucket-owner", plan["account"])
    location = (
        aws.call("s3api", "get-bucket-location", *owner).get("LocationConstraint")
        or "us-east-1"
    )
    require(location == plan["region"], "S3 bucket must be in the Lambda region")
    public = aws.call("s3api", "get-public-access-block", *owner)[
        "PublicAccessBlockConfiguration"
    ]
    require(
        all(
            public.get(k) is True
            for k in (
                "BlockPublicAcls",
                "IgnorePublicAcls",
                "BlockPublicPolicy",
                "RestrictPublicBuckets",
            )
        ),
        "S3 public access is not fully blocked",
    )
    require(
        aws.call("s3api", "get-bucket-versioning", *owner).get("Status") == "Enabled",
        "Existing S3 versioning must be enabled; script never changes it",
    )
    rules = aws.call("s3api", "get-bucket-encryption", *owner)[
        "ServerSideEncryptionConfiguration"
    ]["Rules"]
    require(
        len(rules) == 1
        and rules[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256",
        "This workflow requires existing SSE-S3 encryption; review KMS separately",
    )
    ownership = aws.call("s3api", "get-bucket-ownership-controls", *owner)[
        "OwnershipControls"
    ]["Rules"]
    require(
        ownership == [{"ObjectOwnership": "BucketOwnerEnforced"}],
        "Review bucket ownership/ACL configuration",
    )
    try:
        policy = aws.call("s3api", "get-bucket-policy-status", *owner)
        require(policy["PolicyStatus"]["IsPublic"] is False, "Public S3 policy")
    except AwsError as error:
        if error.code != "NoSuchBucketPolicy":
            raise
    api = urlparse(plan["api_url"])
    match = re.fullmatch(
        r"([a-z0-9]+)\.execute-api\." + re.escape(plan["region"]) + r"\.amazonaws\.com",
        api.hostname or "",
    )
    require(
        api.scheme == "https"
        and match
        and not api.query
        and not api.fragment
        and not api.username
        and not api.password,
        "Use the explicit HTTPS API Gateway URL",
    )
    integrations = aws.call("apigatewayv2", "get-integrations", "--api-id", match[1])[
        "Items"
    ]
    allowed = {
        i["IntegrationId"]
        for i in integrations
        if i.get("IntegrationUri")
        in {
            arn,
            f"arn:aws:apigateway:{plan['region']}:lambda:path/2015-03-31/functions/{arn}/invocations",
        }
    }
    routes = aws.call("apigatewayv2", "get-routes", "--api-id", match[1])["Items"]
    require(
        any(
            r.get("RouteKey") == "$default"
            and r.get("Target", "").removeprefix("integrations/") in allowed
            for r in routes
        ),
        "API default route does not target this unqualified Lambda",
    )
    return result


def same_function(config, expected):
    require(
        config.get("State") == "Active"
        and config.get("LastUpdateStatus") != "InProgress"
        and config["RevisionId"] == expected["revision_id"]
        and config["CodeSha256"] == expected["code_sha256"]
        and fingerprint(config) == expected["config_sha256"],
        "Lambda code, revision or configuration changed; stop and prepare again",
    )


def prepare(args):
    require(
        re.fullmatch(r"\d{12}", args.account)
        and re.fullmatch(r"[A-Za-z0-9_-]+", args.function),
        "Supply the account and unqualified function name explicitly",
    )
    plan = dict(
        schema_version=1,
        account=args.account,
        region=args.region,
        function=args.function,
        bucket=args.bucket,
        api_url=args.api_url.rstrip("/"),
        profile=args.profile,
    )
    aws = Aws(args.region, args.profile)
    candidate = validate_zip(args.zip)
    result = preflight(aws, plan)
    config = result["Configuration"]
    directory = Path(args.backup_dir).resolve()
    if directory.is_relative_to(ROOT):
        require(
            subprocess.run(
                ["git", "check-ignore", "--quiet", str(directory)], cwd=ROOT
            ).returncode
            == 0,
            "Backup directory must be Git-ignored or outside the repository",
        )
    require(
        not directory.exists(),
        "Use a new backup directory; never overwrite a previous backup",
    )
    directory.mkdir(parents=True, mode=0o700)
    os.chmod(directory, 0o700)
    shutil.copyfile(args.zip, directory / "candidate.zip")
    os.chmod(directory / "candidate.zip", 0o600)
    require(
        aws_sha(directory / "candidate.zip") == candidate["code_sha256"],
        "ZIP changed while preparing",
    )
    download(result["Code"]["Location"], directory / "previous.zip")
    require(
        aws_sha(directory / "previous.zip") == config["CodeSha256"],
        "Downloaded backup hash mismatch",
    )
    save(directory / "configuration-before.json", config)
    layer_bytes = 0
    for index, layer in enumerate(config.get("Layers") or []):
        response = aws.call("lambda", "get-layer-version-by-arn", "--arn", layer["Arn"])
        target = directory / f"layer-{index}.zip"
        download(response["Content"]["Location"], target)
        require(
            aws_sha(target) == response["Content"]["CodeSha256"],
            "Layer backup hash mismatch",
        )
        layer_bytes += zip_size(target)
    require(
        candidate["uncompressed_bytes"] + layer_bytes <= MAX_UNZIPPED,
        "ZIP + Layers exceed 250 MiB",
    )
    same_function(
        aws.call("lambda", "get-function", "--function-name", args.function)[
            "Configuration"
        ],
        dict(
            revision_id=config["RevisionId"],
            code_sha256=config["CodeSha256"],
            config_sha256=fingerprint(config),
        ),
    )
    plan.update(
        candidate=candidate,
        layers_uncompressed_bytes=layer_bytes,
        previous=dict(
            revision_id=config["RevisionId"],
            code_sha256=config["CodeSha256"],
            config_sha256=fingerprint(config),
            zip_sha256=sha(directory / "previous.zip"),
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
        runtime_management=result["RuntimeManagement"],
    )
    require(
        runtime_management(aws, plan) == plan["runtime_management"],
        "Runtime management mode changed during prepare",
    )
    save(directory / "plan.json", plan)
    print(
        json.dumps(
            dict(
                plan=str(directory / "plan.json"),
                target=target_token(plan),
                candidate=candidate,
                layers_uncompressed_bytes=layer_bytes,
                previous_revision=config["RevisionId"],
                previous_code_sha256=config["CodeSha256"],
                aws_writes=0,
            ),
            indent=2,
        )
    )


def upload(aws, plan, path, key):
    args = (
        "--bucket",
        plan["bucket"],
        "--key",
        key,
        "--expected-bucket-owner",
        plan["account"],
    )
    try:
        aws.call(
            "s3api",
            "put-object",
            *args,
            "--body",
            path,
            "--if-none-match",
            "*",
            "--server-side-encryption",
            "AES256",
            "--checksum-algorithm",
            "SHA256",
            "--checksum-sha256",
            aws_sha(path),
            "--metadata",
            json.dumps({"sha256": sha(path)}),
        )
    except AwsError as error:
        if error.code != "PreconditionFailed":
            raise
    head = aws.call("s3api", "head-object", *args, "--checksum-mode", "ENABLED")
    require(
        head.get("VersionId") not in (None, "null")
        and head.get("ChecksumSHA256") == aws_sha(path)
        and head.get("ContentLength") == Path(path).stat().st_size
        and head.get("ServerSideEncryption") == "AES256",
        "S3 object/version/checksum mismatch",
    )
    return dict(key=key, version=head["VersionId"])


def update(aws, plan, obj, expected, desired_sha, directory, baseline, management):
    same_function(
        aws.call("lambda", "get-function", "--function-name", plan["function"])[
            "Configuration"
        ],
        expected,
    )
    require(
        runtime_management(aws, plan) == management,
        "Runtime management mode changed before code update",
    )
    response = aws.call(
        "lambda",
        "update-function-code",
        "--function-name",
        plan["function"],
        "--s3-bucket",
        plan["bucket"],
        "--s3-key",
        obj["key"],
        "--s3-object-version",
        obj["version"],
        "--revision-id",
        expected["revision_id"],
        "--no-publish",
    )
    receipt = dict(
        revision_id=response["RevisionId"],
        code_sha256=desired_sha,
        config_sha256=fingerprint(baseline),
        runtime_management=management,
        object=obj,
        status="update_requested",
    )
    save(directory / "receipt.json", receipt)
    aws.call("lambda", "wait", "function-updated", "--function-name", plan["function"])
    config = aws.call("lambda", "get-function", "--function-name", plan["function"])[
        "Configuration"
    ]
    require(
        runtime_management(aws, plan) == management,
        "Runtime management mode changed during code update",
    )
    same_deployment(config, receipt, baseline, management)
    require(
        config.get("LastUpdateStatus") == "Successful", "Lambda update did not succeed"
    )
    receipt["status"] = "updated"
    receipt["post_config_sha256"] = fingerprint(config)
    receipt["runtime_version"] = config.get("RuntimeVersionConfig")
    save(directory / "receipt.json", receipt)
    return receipt


def verify_api(plan):
    from app.routers.search_router import list_waste_items
    from app.services.region_registry_service import get_registry

    async def expected_checks():
        checks = [("/api/health", {"status": "ok"})]
        for city in get_registry().entries:
            registry = get_registry().registry(city)
            for pid, profile in registry.profiles.items():
                area = next(
                    a for a in registry.areas.values() if a["rule_profile_id"] == pid
                )
                category = next(iter(profile.categories))
                body = await list_waste_items(
                    city, category=category, search=None, district_id=area["id"]
                )
                path = f"/api/search/items/{city}?" + urlencode(
                    dict(district_id=area["id"], category=category)
                )
                checks.append((path, body.model_dump()))
        return checks

    checks = asyncio.run(expected_checks())
    for index, (path, expected) in enumerate(checks):
        if index:
            time.sleep(0.5)  # Stay below the existing API Gateway 5 req/s limit.
        with urlopen(plan["api_url"] + path, timeout=45) as response:
            payload = json.load(response)
        require(
            payload == expected,
            "Public API verification failed; use the saved rollback plan",
        )
    return len(checks)


def run_plan(args):
    path = Path(args.plan).resolve()
    directory = path.parent
    plan = json.loads(path.read_text())
    require(plan.get("schema_version") == 1, "Unsupported plan")
    aws = Aws(plan["region"], plan.get("profile"))
    result = preflight(aws, plan, permit_failed=args.command == "rollback")
    config = result["Configuration"]
    management = result["RuntimeManagement"]
    baseline = saved_baseline(directory, plan)
    require(
        sha(directory / "previous.zip") == plan["previous"]["zip_sha256"],
        "Backup ZIP changed",
    )
    if args.command == "verify":
        require(
            config["CodeSha256"] == plan["candidate"]["code_sha256"],
            "Candidate code is not installed; API verification would test a different release",
        )
        require(
            validate_zip(directory / "candidate.zip") == plan["candidate"],
            "Candidate ZIP/data changed",
        )
        require(
            (directory / "receipt.json").is_file(),
            "Receipt is missing; inspect update ownership before verification",
        )
        receipt = json.loads((directory / "receipt.json").read_text())
        require(
            receipt["code_sha256"] == plan["candidate"]["code_sha256"],
            "Receipt does not describe this deployment",
        )
        if "runtime_management" in receipt:
            require(
                management == receipt["runtime_management"],
                "Runtime management mode changed since update",
            )
        expected = dict(receipt)
        pinned_revision = getattr(args, "expected_revision_id", None)
        if pinned_revision:
            # Read-only acknowledgement, never used by deploy/rollback/CAS writes.
            expected["revision_id"] = pinned_revision
        same_deployment(config, expected, baseline, management)
        checks = verify_api(plan)
        final_config = aws.call(
            "lambda", "get-function", "--function-name", plan["function"]
        )["Configuration"]
        same_function(
            final_config,
            dict(
                revision_id=config["RevisionId"],
                code_sha256=config["CodeSha256"],
                config_sha256=fingerprint(config),
            ),
        )
        require(
            final_config.get("LastUpdateStatus") == "Successful",
            "Lambda update did not succeed",
        )
        require(
            runtime_management(aws, plan) == management,
            "Runtime management mode changed during verification",
        )
        report = dict(
            status="verified",
            target=target_token(plan),
            code_sha256=config["CodeSha256"],
            revision_id=config["RevisionId"],
            receipt_revision_id=receipt["revision_id"],
            revision_explicitly_pinned=bool(pinned_revision),
            runtime_management=management,
            runtime_management_baseline_recorded="runtime_management" in plan
            or "runtime_management" in receipt,
            runtime_version_before=baseline.get("RuntimeVersionConfig"),
            runtime_version_after=config.get("RuntimeVersionConfig"),
            read_only_api_checks=checks,
            bedrock_calls=0,
            aws_writes=0,
        )
        report_path = getattr(args, "report", None)
        if report_path:
            # A new report only. Never rewrite the original plan/receipt/backups.
            fd = os.open(Path(report_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(report, stream, indent=2)
                stream.write("\n")
        print(json.dumps(report, indent=2))
        return
    if args.command == "deploy":
        require(
            validate_zip(directory / "candidate.zip") == plan["candidate"],
            "Candidate ZIP/data changed",
        )
        same_function(config, plan["previous"])
        source, desired = directory / "candidate.zip", plan["candidate"]["code_sha256"]
        expected = plan["previous"]
    else:
        same_configuration_after_update(config, baseline, management)
        if config["CodeSha256"] == plan["previous"]["code_sha256"]:
            print("Original code is already installed; no AWS writes")
            return
        receipt_path = directory / "receipt.json"
        require(
            receipt_path.is_file(),
            "Update outcome is unknown; inspect Lambda before manual recovery",
        )
        expected = json.loads(receipt_path.read_text())
        if "runtime_management" in expected:
            require(
                management == expected["runtime_management"],
                "Runtime management mode changed since update",
            )
        same_deployment(config, expected, baseline, management, permit_failed=True)
        # The write still uses a strict snapshot and exact RevisionId.
        expected = {**expected, "config_sha256": fingerprint(config)}
        source, desired = directory / "previous.zip", plan["previous"]["code_sha256"]
    if not args.execute:
        print(
            json.dumps(
                dict(
                    mode="read-only review",
                    target=target_token(plan),
                    operation=args.command,
                    desired_code_sha256=desired,
                    aws_writes=0,
                ),
                indent=2,
            )
        )
        return
    require(
        args.confirm_target == target_token(plan),
        "Exact account:region:function:bucket confirmation is required",
    )
    prefix = f"deployments/lambda/{plan['function']}/"
    # Both archives must be available for recovery before replacing any code.
    backup = upload(
        aws,
        plan,
        directory / "previous.zip",
        prefix + "backups/" + plan["previous"]["zip_sha256"] + ".zip",
    )
    obj = (
        backup
        if args.command == "rollback"
        else upload(
            aws, plan, source, prefix + plan["candidate"]["zip_sha256"] + ".zip"
        )
    )
    receipt = update(aws, plan, obj, expected, desired, directory, baseline, management)
    if args.command == "deploy":
        try:
            receipt["api_checks"] = verify_api(plan)
            final_config = aws.call(
                "lambda", "get-function", "--function-name", plan["function"]
            )["Configuration"]
            same_function(
                final_config,
                {**receipt, "config_sha256": receipt["post_config_sha256"]},
            )
            require(
                final_config.get("LastUpdateStatus") == "Successful",
                "Lambda update did not succeed",
            )
            require(
                runtime_management(aws, plan) == management,
                "Runtime management mode changed during API verification",
            )
            receipt["status"] = "verified"
        except Exception:
            receipt["status"] = "api_verification_failed"
            save(directory / "receipt.json", receipt)
            raise DeployError(
                "API verification failed; code was updated. Review and run rollback using this plan"
            ) from None
        save(directory / "receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser(
        "prepare", help="Read-only AWS checks + private local backups"
    )
    for option in ("account", "region", "function", "bucket", "api-url", "backup-dir"):
        prep.add_argument("--" + option, required=True)
    prep.add_argument("--profile")
    prep.add_argument("--zip", type=Path, required=True)
    for command in ("deploy", "rollback", "verify"):
        child = sub.add_parser(command)
        child.add_argument("--plan", type=Path, required=True)
        if command == "verify":
            child.add_argument(
                "--expected-revision-id",
                help="Pin a reviewed current revision for read-only verification; never enables writes",
            )
            child.add_argument(
                "--report",
                type=Path,
                help="Create a NEW verification report without altering existing records",
            )
        else:
            child.add_argument("--execute", action="store_true")
            child.add_argument("--confirm-target")
    args = parser.parse_args()
    try:
        prepare(args) if args.command == "prepare" else run_plan(args)
    except (DeployError, OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        # No tracebacks or full AWS responses (which may include secrets/URLs).
        print(f"STOP: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "backend"))
    raise SystemExit(main())
