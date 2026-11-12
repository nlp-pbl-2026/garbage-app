"""UI-only export. Unreviewed redistribution is blocked outside loopback tests."""

import os

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..services.frontend_data_contract import decode, encode, day, require
from ..services.frontend_data_service import (
    build_snapshot,
    policy_path,
    default_catalog_path,
)
from ..services.region_registry_service import MunicipalityCatalog

router = APIRouter(prefix="/api/frontend-data", tags=["frontend-data"])


def catalog_path():
    return default_catalog_path()


def export_status(request, catalog):
    policy = decode(policy_path(catalog).read_bytes())
    require(
        policy.get("schema_version") == 1
        and policy.get("scope") == "flutter_ui_json_redistribution",
        "Invalid export policy",
    )
    cities = set(MunicipalityCatalog(catalog).entries)
    require(set(policy["municipalities"]) == cities, "Incomplete export policy")
    approved = True
    for review in policy["municipalities"].values():
        require(
            review["status"] in {"approved", "pending"},
            "Unknown redistribution review status",
        )
        if review["status"] != "approved":
            approved = False
            continue
        require(
            isinstance(review.get("evidence_url"), str)
            and review["evidence_url"].startswith("https://")
            and bool(review.get("reviewed_by")),
            "Missing redistribution evidence",
        )
        day(review["reviewed_on"])
    if approved:
        return "approved"
    local = (
        os.getenv("FRONTEND_DATA_ALLOW_UNREVIEWED_LOCAL") == "1"
        and not os.getenv("AWS_LAMBDA_FUNCTION_NAME")
        and not os.getenv("AWS_LAMBDA_RUNTIME_API")
        and request.client
        and request.client.host in {"127.0.0.1", "::1"}
        and request.url.hostname in {"localhost", "127.0.0.1", "::1"}
        and not any(
            h in request.headers
            for h in ("forwarded", "x-forwarded-for", "x-forwarded-host")
        )
    )
    if local:
        return "unreviewed_local_only"
    raise HTTPException(
        status_code=503,
        detail="Flutter用データの利用・再配布条件を確認中です。公開配信は有効になっていません。",
    )


def snapshot(request):
    try:
        path = catalog_path()
        status = export_status(request, path)
        manifest, files = build_snapshot(path)
        manifest["redistribution_status"] = status
        return manifest, files
    except HTTPException:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=503,
            detail="Flutter用データが不足しているか、整合性を確認できません。",
        ) from None


@router.get("/manifest")
def manifest(request: Request):
    data, _ = snapshot(request)
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/municipalities/{municipality_id}")
def municipality(
    request: Request,
    municipality_id: str,
    version: str = Query(pattern=r"^[0-9a-f]{64}$"),
):
    data, files = snapshot(request)
    if version != data["dataset_version"]:
        raise HTTPException(
            status_code=409,
            detail="データ版が変更されています。manifestから取得し直してください。",
        )
    names = [
        name
        for name, info in data["files"].items()
        if info["municipality_id"] == municipality_id
    ]
    if not names:
        raise HTTPException(status_code=404, detail="指定された自治体は未対応です。")
    body = {
        "schema_version": 1,
        "dataset_version": version,
        "municipality_id": municipality_id,
        "files": {name: files[name].decode("utf-8") for name in names},
    }
    if len(encode(body)) >= 5 * 1024**2:
        raise HTTPException(
            status_code=503, detail="Flutter用データがAPIの配信容量上限を超えています。"
        )
    return JSONResponse(body, headers={"Cache-Control": "no-store"})
