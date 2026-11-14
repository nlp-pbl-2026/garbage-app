#!/usr/bin/env python3
"""Deploy/verify/restore immutable Web releases. Writes require --execute + target.

Only a tagged frontend bucket and its tagged CloudFront distribution are allowed.
No Terraform, IAM changes, Lambda operations, sync --delete or paid models.
"""

import argparse
import base64
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener

from fetch_frontend_data import NoRedirect, read_json
from frontend_web_release import (
    ENTRY_CACHE,
    IMMUTABLE_CACHE,
    UI_PATH,
    api_url,
    decode,
    digest,
    encode,
    require,
    release_id,
    safe_path,
    validate_release,
)


class AwsError(RuntimeError):
    def __init__(self, message):
        super().__init__(message)
        match = re.search(r"\(([^)]+)\)", message)
        self.code = match[1] if match else "Unknown"


class DeploymentFailure(RuntimeError):
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


class AWS:
    READS = {
        ("sts", "get-caller-identity"),
        *(
            ("s3api", op)
            for op in (
                "get-bucket-location",
                "get-bucket-tagging",
                "get-bucket-versioning",
                "get-public-access-block",
                "get-bucket-encryption",
                "get-bucket-ownership-controls",
                "get-bucket-policy-status",
                "head-object",
                "get-object",
            )
        ),
        *(
            ("cloudfront", op)
            for op in (
                "get-distribution",
                "list-tags-for-resource",
                "get-origin-access-control",
                "get-cache-policy",
                "wait",
            )
        ),
    }
    WRITES = {("s3api", "put-object"), ("cloudfront", "create-invalidation")}

    def __init__(self, region, *, profile=None, execute=False):
        self.region, self.profile, self.execute = region, profile, execute

    def call(self, service, operation, *args):
        pair = (service, operation)
        require(
            pair in self.READS or (self.execute and pair in self.WRITES),
            f"AWS operation not permitted in this mode: {service}/{operation}",
        )
        command = [
            "aws",
            "--no-cli-pager",
            "--region",
            self.region,
            "--cli-connect-timeout",
            "10",
            "--cli-read-timeout",
            "60",
        ]
        if self.profile:
            command += ["--profile", self.profile]
        command += [service, operation, *map(str, args), "--output", "json"]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise AwsError(result.stderr.strip()[:1000])
        return decode(result.stdout) if result.stdout.strip() else {}


def check_cli_capabilities():
    # Skeleton generation reads the local CLI model, without AWS requests.
    result = subprocess.run(
        ["aws", "s3api", "put-object", "--generate-cli-skeleton", "input"],
        capture_output=True,
        text=True,
        check=True,
    )
    require(
        {"IfMatch", "IfNoneMatch", "ChecksumSHA256", "ExpectedBucketOwner"}
        <= set(decode(result.stdout)),
        "Upgrade AWS CLI v2: conditional/checksummed PUT is required",
    )


def target_token(target):
    return ":".join(
        target[k] for k in ("account", "region", "bucket", "distribution_id")
    )


def validate_target(target):
    require(re.fullmatch(r"[0-9]{12}", target["account"]), "Invalid AWS account")
    require(
        re.fullmatch(r"[a-z]{2}-[a-z]+-[0-9]+", target["region"]), "Invalid AWS region"
    )
    require(
        re.fullmatch(r"garbage-guide-web-[a-z0-9-]+", target["bucket"])
        and target["account"] in target["bucket"],
        "Use the dedicated frontend bucket",
    )
    require(
        re.fullmatch(r"[A-Z0-9]+", target["distribution_id"]), "Invalid distribution"
    )
    require(
        target.get("environment") and target.get("project_tag"),
        "Missing ownership tags",
    )


def owner(target):
    return ["--bucket", target["bucket"], "--expected-bucket-owner", target["account"]]


def head(aws, target, key):
    try:
        return aws.call(
            "s3api",
            "head-object",
            *owner(target),
            "--key",
            key,
            "--checksum-mode",
            "ENABLED",
        )
    except AwsError as error:
        if error.code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def root_identity(value):
    return (value["ETag"], value["VersionId"]) if value else None


def preflight(aws, target):
    validate_target(target)
    require(
        aws.call("sts", "get-caller-identity")["Account"] == target["account"],
        "Unexpected AWS account",
    )
    location = (
        aws.call("s3api", "get-bucket-location", *owner(target)).get(
            "LocationConstraint"
        )
        or "us-east-1"
    )
    require(location == target["region"], "Wrong bucket region")
    tags = {
        t["Key"]: t["Value"]
        for t in aws.call("s3api", "get-bucket-tagging", *owner(target))["TagSet"]
    }
    expected = {
        "Component": "frontend",
        "Application": "garbage-guide",
        "ManagedBy": "Terraform",
        "Environment": target["environment"],
        "Project": target["project_tag"],
    }
    require(
        all(tags.get(k) == v for k, v in expected.items()),
        "Frontend bucket ownership mismatch",
    )
    block = aws.call("s3api", "get-public-access-block", *owner(target))[
        "PublicAccessBlockConfiguration"
    ]
    require(
        all(
            block.get(k) is True
            for k in (
                "BlockPublicAcls",
                "IgnorePublicAcls",
                "BlockPublicPolicy",
                "RestrictPublicBuckets",
            )
        ),
        "Public S3 bucket",
    )
    require(
        aws.call("s3api", "get-bucket-policy-status", *owner(target))["PolicyStatus"][
            "IsPublic"
        ]
        is False,
        "Public bucket policy",
    )
    require(
        aws.call("s3api", "get-bucket-versioning", *owner(target)).get("Status")
        == "Enabled",
        "Bucket versioning must be enabled",
    )
    encryption = aws.call("s3api", "get-bucket-encryption", *owner(target))[
        "ServerSideEncryptionConfiguration"
    ]["Rules"]
    require(
        len(encryption) == 1
        and encryption[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
        == "AES256",
        "Expected SSE-S3 encryption",
    )
    ownership = aws.call("s3api", "get-bucket-ownership-controls", *owner(target))[
        "OwnershipControls"
    ]["Rules"]
    require(
        ownership == [{"ObjectOwnership": "BucketOwnerEnforced"}],
        "Expected disabled S3 ACLs",
    )
    response = aws.call(
        "cloudfront", "get-distribution", "--id", target["distribution_id"]
    )
    distribution = response["Distribution"]
    config = distribution["DistributionConfig"]
    require(
        distribution["ARN"]
        == f"arn:aws:cloudfront::{target['account']}:distribution/{target['distribution_id']}",
        "Distribution account mismatch",
    )
    cf_tags = {
        t["Key"]: t["Value"]
        for t in aws.call(
            "cloudfront", "list-tags-for-resource", "--resource", distribution["ARN"]
        )["Tags"]["Items"]
    }
    require(
        all(cf_tags.get(k) == v for k, v in expected.items()),
        "Frontend distribution ownership mismatch",
    )
    require(
        distribution["Status"] == "Deployed"
        and config["Enabled"] is True
        and config["DefaultRootObject"] == "index.html"
        and not config.get("Aliases", {}).get("Items")
        and config["ViewerCertificate"].get("CloudFrontDefaultCertificate") is True,
        "Unexpected distribution state/domain configuration",
    )
    require(
        not config.get("CacheBehaviors", {}).get("Items")
        and not config.get("CustomErrorResponses", {}).get("Items")
        and not config.get("OriginGroups", {}).get("Items")
        and not config.get("ContinuousDeploymentPolicyId")
        and not config.get("Staging")
        and not config.get("ConnectionFunctionAssociation"),
        "Unexpected routing/error overrides or staged distribution",
    )
    origins = config["Origins"]["Items"]
    require(len(origins) == 1, "Expected only the frontend S3 origin")
    origin = origins[0]
    require(
        origin["DomainName"]
        == f"{target['bucket']}.s3.{target['region']}.amazonaws.com"
        and not origin.get("OriginPath")
        and origin.get("OriginAccessControlId"),
        "Wrong frontend origin",
    )
    oac = aws.call(
        "cloudfront",
        "get-origin-access-control",
        "--id",
        origin["OriginAccessControlId"],
    )["OriginAccessControl"]["OriginAccessControlConfig"]
    require(
        oac["SigningBehavior"] == "always"
        and oac["SigningProtocol"] == "sigv4"
        and oac["OriginAccessControlOriginType"] == "s3",
        "Unsigned/non-S3 origin",
    )
    behavior = config["DefaultCacheBehavior"]
    require(
        behavior["TargetOriginId"] == origin["Id"]
        and behavior["ViewerProtocolPolicy"] == "redirect-to-https"
        and set(behavior["AllowedMethods"]["Items"]) == {"GET", "HEAD"},
        "Unexpected cache behavior",
    )
    require(
        not behavior.get("FunctionAssociations", {}).get("Items")
        and not behavior.get("LambdaFunctionAssociations", {}).get("Items")
        and not behavior.get("OriginRequestPolicyId")
        and not behavior.get("TrustedSigners", {}).get("Items")
        and not behavior.get("TrustedKeyGroups", {}).get("Items"),
        "Unexpected response/request rewriting or private viewer access",
    )
    cache = aws.call(
        "cloudfront", "get-cache-policy", "--id", behavior["CachePolicyId"]
    )["CachePolicy"]["CachePolicyConfig"]
    require(
        cache["MinTTL"] == 0 and cache["DefaultTTL"] == 0, "Root HTML must revalidate"
    )
    require(
        re.fullmatch(r"[a-z0-9]+\.cloudfront\.net", distribution["DomainName"]),
        "Unexpected Web domain",
    )
    return {
        "distribution_etag": response["ETag"],
        "web_url": "https://" + distribution["DomainName"],
        "root": head(aws, target, "index.html"),
    }


def check_api(url, version):
    require(
        api_url(url) == url and urlsplit(url).scheme == "https",
        "Use the verified HTTPS API URL",
    )
    require(
        read_json(url + "/api/health").get("status") == "ok", "API health check failed"
    )
    manifest = read_json(url + "/api/frontend-data/manifest")
    require(
        manifest.get("publication_status") == "enabled"
        and manifest["dataset_version"] == version,
        "Backend UI data changed; verify the backend and build again",
    )
    return manifest


def verify_object(value, info, cache):
    expected = base64.b64encode(bytes.fromhex(info["sha256"])).decode()
    require(
        value
        and value.get("VersionId") not in {None, "", "null"}
        and value.get("ChecksumSHA256") == expected
        and value["ContentLength"] == info["bytes"]
        and value["ContentType"] == info["content_type"]
        and value["CacheControl"] == cache,
        "Missing/stale S3 object checksum or metadata",
    )


def put(aws, target, key, path, info, metadata, *, previous=None, immutable=False):
    condition = (
        ["--if-none-match", "*"]
        if immutable or previous is None
        else ["--if-match", previous["ETag"]]
    )
    return aws.call(
        "s3api",
        "put-object",
        *owner(target),
        "--key",
        key,
        "--body",
        path,
        "--content-type",
        info["content_type"],
        "--cache-control",
        IMMUTABLE_CACHE if immutable else ENTRY_CACHE,
        "--server-side-encryption",
        "AES256",
        "--checksum-algorithm",
        "SHA256",
        "--checksum-sha256",
        base64.b64encode(bytes.fromhex(info["sha256"])).decode(),
        "--metadata",
        encode(metadata).decode().strip(),
        *condition,
    )


def get_file(aws, target, key, destination, *, version=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    args = [*owner(target), "--key", key, "--checksum-mode", "ENABLED"]
    if version:
        args += ["--version-id", version]
    return aws.call("s3api", "get-object", *args, destination)


def load_remote(aws, target, rid, folder):
    release_id(rid)
    folder.mkdir()
    get_file(aws, target, f"releases/{rid}/release.json", folder / "release.json")
    manifest = decode((folder / "release.json").read_bytes())
    require(
        manifest["release_id"] == rid
        and len(manifest["files"]) <= 3000
        and sum(v["bytes"] for v in manifest["files"].values()) < 512 * 1024**2,
        "Invalid remote release manifest",
    )
    for name, info in manifest["files"].items():
        safe_path(name)
        get_file(aws, target, f"releases/{rid}/{name}", folder / "site" / name)
        verify_object(
            head(aws, target, f"releases/{rid}/{name}"), info, IMMUTABLE_CACHE
        )
    return validate_release(folder)


def invalidate(aws, target):
    result = aws.call(
        "cloudfront",
        "create-invalidation",
        "--distribution-id",
        target["distribution_id"],
        "--paths",
        "/",
        "/index.html",
    )
    identifier = result["Invalidation"]["Id"]
    aws.call(
        "cloudfront",
        "wait",
        "invalidation-completed",
        "--distribution-id",
        target["distribution_id"],
        "--id",
        identifier,
    )


def public_bytes(url):
    with build_opener(NoRedirect).open(
        Request(url, headers={"Cache-Control": "no-cache"}), timeout=45
    ) as response:
        body = response.read(32 * 1024**2 + 1)
    require(len(body) <= 32 * 1024**2, "Oversized public asset")
    return body


def verify_public(web_url, manifest):
    require(
        digest(public_bytes(web_url + "/"))
        == manifest["files"]["index.html"]["sha256"],
        "Public entry point mismatch",
    )
    for name, info in manifest["files"].items():
        if name.startswith(UI_PATH.as_posix() + "/") or name in {
            "main.dart.js",
            "flutter_bootstrap.js",
        }:
            time.sleep(0.05)
            require(
                digest(
                    public_bytes(
                        f"{web_url}/releases/{manifest['release_id']}/{quote(name, safe='/')}"
                    )
                )
                == info["sha256"],
                f"Public asset mismatch: {name}",
            )


def verify_active(aws, target, manifest, expected):
    """Read-only verification, including backend stability through the CDN check."""
    require(manifest["dataset_version"] == expected, "Release version mismatch")
    before = preflight(aws, target)
    require(
        before["root"]
        and before["root"].get("Metadata", {}).get("release-id")
        == manifest["release_id"],
        "This release is not active",
    )
    verify_object(before["root"], manifest["files"]["index.html"], ENTRY_CACHE)
    check_api(manifest["api_base_url"], expected)
    verify_public(before["web_url"], manifest)
    check_api(manifest["api_base_url"], expected)
    after = preflight(aws, target)
    require(after == before, "Deployment changed during verification")
    return {"status": "verified", "release_id": manifest["release_id"]}


def publish(
    aws,
    target,
    folder,
    manifest,
    expected,
    execute,
    confirm,
    *,
    upload=True,
    expected_current=None,
):
    require(
        manifest["dataset_version"] == expected,
        "Release dataset differs from the verified backend",
    )
    before = preflight(aws, target)
    if expected_current is not None:
        require(
            before["root"]
            and before["root"].get("Metadata", {}).get("release-id")
            == expected_current,
            "The active release differs from the rollback target confirmation",
        )
    check_api(manifest["api_base_url"], expected)
    report = {
        "status": "dry_run",
        "target": target_token(target),
        "release_id": manifest["release_id"],
        "dataset_version": expected,
        "previous_root": before["root"],
        "web_url": before["web_url"],
    }
    if not execute:
        return report
    require(
        confirm == target_token(target),
        "Confirm the exact account:region:bucket:distribution target",
    )
    rid = manifest["release_id"]
    metadata = {
        "release-id": rid,
        "dataset-version": expected,
        "git-sha": manifest["git_sha"],
    }
    prefix = f"releases/{rid}/"
    if upload:
        files = {
            **manifest["files"],
            "release.json": {
                "sha256": digest((folder / "release.json").read_bytes()),
                "bytes": (folder / "release.json").stat().st_size,
                "content_type": "application/json",
            },
        }
        for name, info in files.items():
            path = (
                folder / "release.json"
                if name == "release.json"
                else folder / "site" / name
            )
            current = head(aws, target, prefix + name)
            if current is None:
                try:
                    put(
                        aws, target, prefix + name, path, info, metadata, immutable=True
                    )
                except AwsError:
                    # A timeout/concurrent identical upload is safe only if the stored bytes match.
                    verify_object(
                        head(aws, target, prefix + name), info, IMMUTABLE_CACHE
                    )
            verify_object(head(aws, target, prefix + name), info, IMMUTABLE_CACHE)
    current = preflight(aws, target)
    require(
        current["distribution_etag"] == before["distribution_etag"]
        and root_identity(current["root"]) == root_identity(before["root"]),
        "Concurrent Web update; stop",
    )
    check_api(manifest["api_base_url"], expected)
    previous = before["root"]
    with tempfile.TemporaryDirectory(prefix="gomisapo-web-rollback-") as backup:
        old = Path(backup) / "index.html"
        if previous:
            get_file(aws, target, "index.html", old, version=previous["VersionId"])
            verify_object(
                previous,
                {
                    "sha256": digest(old.read_bytes()),
                    "bytes": old.stat().st_size,
                    "content_type": "text/html; charset=utf-8",
                },
                ENTRY_CACHE,
            )
        else:
            old.write_text(
                '<!doctype html><meta charset="UTF-8"><title>ごみサポ</title><p>ただいま公開の準備中です。</p>'
            )
        activated = None
        try:
            activation = put(
                aws,
                target,
                "index.html",
                folder / "site/index.html",
                manifest["files"]["index.html"],
                metadata,
                previous=previous,
            )
            activated = root_identity(activation)
            report["status"] = "activated"
            report["active_root"] = activation
            verify_object(
                head(aws, target, "index.html"),
                manifest["files"]["index.html"],
                ENTRY_CACHE,
            )
            invalidate(aws, target)
            verify_public(before["web_url"], manifest)
            check_api(manifest["api_base_url"], expected)
            after = preflight(aws, target)
            require(
                after["distribution_etag"] == before["distribution_etag"]
                and root_identity(after["root"]) == activated,
                "Deployment changed during verification",
            )
            report["status"] = "verified"
            return report
        except Exception as error:
            # Never replace another deployer's winning root. ETag CAS protects the compensation too.
            report["error"] = str(error)
            try:
                restoration_target = preflight(aws, target)
                current_root = restoration_target["root"]
                if (
                    activated
                    and root_identity(current_root) == activated
                    and restoration_target["distribution_etag"]
                    == before["distribution_etag"]
                ):
                    info = {
                        "sha256": digest(old.read_bytes()),
                        "bytes": old.stat().st_size,
                        "content_type": "text/html; charset=utf-8",
                    }
                    old_metadata = (
                        previous.get("Metadata", {})
                        if previous
                        else {"deployment-status": "maintenance"}
                    )
                    restored = put(
                        aws,
                        target,
                        "index.html",
                        old,
                        info,
                        old_metadata,
                        previous=current_root,
                    )
                    report["status"] = "entry_restored"
                    invalidate(aws, target)
                    require(
                        digest(public_bytes(before["web_url"] + "/"))
                        == digest(old.read_bytes()),
                        "Restored entry point needs public verification",
                    )
                    restored_state = preflight(aws, target)
                    require(
                        root_identity(restored_state["root"])
                        == root_identity(restored)
                        and restored_state["distribution_etag"]
                        == before["distribution_etag"],
                        "Deployment changed during restoration verification",
                    )
                    raise DeploymentFailure(
                        "Web verification failed; previous entry point restored (first release: maintenance page)",
                        report,
                    ) from error
                report["status"] = "needs_review"
            except DeploymentFailure:
                raise
            except Exception as restoration_error:
                report["status"] = "restore_needs_review"
                report["restoration_error"] = str(restoration_error)
            raise DeploymentFailure(
                "Web update stopped; inspect the receipt and current root. No other deployment was overwritten",
                report,
            ) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["deploy", "rollback", "verify"])
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--expected-dataset-version", required=True)
    parser.add_argument("--release", type=Path)
    parser.add_argument("--release-id")
    parser.add_argument("--expected-current-release-id")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-target")
    parser.add_argument("--profile")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        require(
            not args.receipt or not args.receipt.exists(), "Choose a NEW receipt file"
        )
        require(not args.execute or args.command != "verify", "Verify is read-only")
        target = decode(args.target.read_bytes())
        validate_target(target)
        if args.execute:
            check_cli_capabilities()
        aws = AWS(target["region"], profile=args.profile, execute=args.execute)
        with tempfile.TemporaryDirectory(prefix="gomisapo-web-release-") as work:
            folder = args.release
            if args.command == "deploy":
                require(folder is not None, "Deploy requires --release")
                manifest = validate_release(folder)
            else:
                require(args.release_id is not None, "Specify the stored --release-id")
                if args.command == "rollback":
                    require(
                        args.expected_current_release_id is not None,
                        "Rollback requires --expected-current-release-id",
                    )
                    release_id(args.expected_current_release_id)
                initial = preflight(aws, target)
                if args.command == "rollback":
                    require(
                        initial["root"]
                        and initial["root"].get("Metadata", {}).get("release-id")
                        == args.expected_current_release_id,
                        "The active release differs from the rollback confirmation",
                    )
                folder = Path(work) / "release"
                manifest = load_remote(aws, target, args.release_id, folder)
            require(
                manifest["api_base_url"] == api_url(args.api_base_url),
                "Release API URL mismatch",
            )
            if args.command == "verify":
                report = verify_active(
                    aws, target, manifest, args.expected_dataset_version
                )
            else:
                report = publish(
                    aws,
                    target,
                    folder,
                    manifest,
                    args.expected_dataset_version,
                    args.execute,
                    args.confirm_target,
                    upload=args.command == "deploy",
                    expected_current=(
                        args.expected_current_release_id
                        if args.command == "rollback"
                        else None
                    ),
                )
        print(encode(report).decode())
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            with args.receipt.open("x") as stream:
                stream.write(encode(report).decode())
            args.receipt.chmod(0o600)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        subprocess.CalledProcessError,
    ) as error:
        if isinstance(error, DeploymentFailure) and args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            with args.receipt.open("x") as stream:
                stream.write(encode(error.report).decode())
            args.receipt.chmod(0o600)
        parser.exit(1, f"Web deployment stopped: {error}\n")


if __name__ == "__main__":
    main()
