#!/usr/bin/env python3
"""Explicit PAID Uwajima API evaluation, only after budget approval.

No deployment/resource operations. Journals bound normal runs to 112 cases, 350 inference calls,
and a combined conservative USD1 index/evaluation reserve.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/uwajima"


def lines(path):
    return (
        [json.loads(v) for v in path.read_text().splitlines()] if path.exists() else []
    )


def append(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def settled_cost(records):
    values = {r["id"]: r["reserved_usd"] for r in records if r["event"] == "reserve"}
    for record in records:
        if record["event"] == "settle":
            values[record["id"]] = record["upper_usd"]
    return sum(values.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-paid", action="store_true", required=True)
    parser.add_argument("--budget-usd", type=float, default=1)
    parser.add_argument("--run", default="initial")
    parser.add_argument("--repeat-cases", type=int, nargs="*", default=[])
    args = parser.parse_args()
    if not args.confirm_paid or not 0 < args.budget_usd <= 1:
        raise ValueError("Paid approval and budget up to USD1 required")
    os.environ["USE_BEDROCK_KNOWLEDGE_BASE"] = "false"
    os.environ["LEXICAL_SEARCH_ENABLED"] = "false"
    sys.path.insert(0, str(ROOT / "backend"))
    import boto3
    from botocore.config import Config
    from httpx import AsyncClient, ASGITransport
    from app import config
    from app.main import app
    from app.services.calendar_service import CalendarService
    from app.services.region_registry_service import get_registry
    from app.services.waste_guide_service import WasteGuideService, BedrockGateway

    settings = (
        config.BEDROCK_MODEL_ID,
        config.BEDROCK_EMBEDDING_MODEL_ID,
        config.EMBEDDING_SEARCH_TOP_K,
        config.EMBEDDING_SEARCH_MIN_SCORE,
        config.CLASSIFICATION_CONFIDENCE_THRESHOLD,
        config.USE_BEDROCK_KNOWLEDGE_BASE,
        config.LEXICAL_SEARCH_ENABLED,
    )
    if settings != (
        "amazon.nova-lite-v1:0",
        "amazon.titan-embed-text-v2:0",
        8,
        0.15,
        0.75,
        False,
        False,
    ):
        raise ValueError("Unexpected RAG model/settings")
    fixture_path = DATA / "search_cases.json"
    fixture = json.loads(fixture_path.read_text())
    cases = fixture["cases"]
    if len(cases) != 48 or [c["case"] for c in cases] != list(range(1, 49)):
        raise ValueError("48 source-backed reviewed cases required")
    import re

    if not re.fullmatch(r"initial|retry-[0-9]+|final-[0-9]+", args.run):
        raise ValueError("Invalid evaluation phase")
    max_cases = 112
    max_calls = 350
    max_retry_cases = 16
    if args.run.startswith("retry"):
        if not 0 < len(set(args.repeat_cases)) <= 16 or not set(
            args.repeat_cases
        ) <= set(range(1, 49)):
            raise ValueError("At most 16 approved follow-up cases")
        cases = [c for c in cases if c["case"] in args.repeat_cases]
    elif args.repeat_cases:
        raise ValueError("Only retry phases accept a subset")
    output = DATA / "generated" / ("live-eval-" + args.run)
    output.mkdir(parents=True, exist_ok=True)
    now = datetime.fromisoformat(fixture["evaluation_time"])
    manifest = {
        "case_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "model_settings": list(settings),
        "evaluation_time": now.isoformat(),
        "budget_usd": args.budget_usd,
        "max_calls": max_calls,
        "max_cases": max_cases,
        "case_ids": [c["case"] for c in cases],
        "dataset_sha256": {
            name: hashlib.sha256((DATA / name).read_bytes()).hexdigest()
            for name in [
                "registry.json",
                "knowledge/items.csv",
                "knowledge/item_embeddings.npz",
            ]
        },
        "implementation_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in [
                "backend/app/services/waste_guide_service.py",
                "backend/app/services/embedding_search_service.py",
                "backend/app/services/calendar_service.py",
            ]
        },
    }
    target = output / "manifest.json"
    if target.exists() and json.loads(target.read_text()) != manifest:
        raise ValueError("Run inputs changed; preserve original journal")
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    class Meter:
        def __init__(self):
            credentials = boto3.Session().get_credentials()
            if credentials is None:
                raise RuntimeError("AWS credentials missing")
            credentials.get_frozen_credentials()
            self.client = boto3.client(
                "bedrock-runtime",
                region_name="ap-northeast-1",
                config=Config(
                    retries={"total_max_attempts": 1},
                    connect_timeout=10,
                    read_timeout=45,
                ),
            )

        def reserve(self, kind, cost):
            journals = [
                lines(p) for p in (DATA / "generated").glob("live-eval-*/calls.jsonl")
            ]
            index_cost = sum(
                r.get("reserved_usd", 0)
                for p in (DATA / "generated").glob("titan-*.jsonl")
                for r in lines(p)
            )
            calls = sum(r["event"] == "reserve" for j in journals for r in j)
            if (
                calls >= max_calls
                or index_cost + sum(settled_cost(j) for j in journals) + cost
                > args.budget_usd
            ):
                raise RuntimeError("Approved combined cost/call limit reached")
            key = f"{kind}-{calls+1}"
            append(
                output / "calls.jsonl",
                {"event": "reserve", "id": key, "kind": kind, "reserved_usd": cost},
            )
            return key

        def invoke_model(self, **kwargs):
            text = json.loads(kwargs["body"])["inputText"]
            self.reserve("titan", (len(text.encode()) + 128) * 0.0002 / 1000)
            return self.client.invoke_model(**kwargs)

        def converse(self, **kwargs):
            content = [c for m in kwargs["messages"] for c in m["content"]]
            cost = (
                sum(len(c.get("text", "").encode()) for c in content)
                + 10000 * sum("image" in c for c in content)
                + kwargs["inferenceConfig"]["maxTokens"]
            ) / 1e6
            key = self.reserve("nova", cost)
            result = self.client.converse(**kwargs)
            usage = result["usage"]
            append(
                output / "calls.jsonl",
                {
                    "event": "settle",
                    "id": key,
                    "upper_usd": (usage["inputTokens"] + usage["outputTokens"]) / 1e6,
                    "usage": usage,
                },
            )
            append(
                output / "nova-responses.jsonl",
                {"id": key, "output": result.get("output"), "usage": usage},
            )
            return result

    class RecordedService(WasteGuideService):
        def retrieve(self, **kwargs):
            documents = super().retrieve(**kwargs)
            append(
                output / "retrievals.jsonl",
                {
                    "case": self.current_case,
                    "query": kwargs,
                    "documents": [asdict(d) for d in documents],
                },
            )
            return documents

    service = RecordedService(
        gateway=BedrockGateway(runtime_client=Meter(), agent_runtime_client=object()),
        now_provider=lambda: now,
    )

    async def run():
        with patch(
            "app.routers.search_router.WasteGuideService", return_value=service
        ), patch("app.routers.search_router.SearchLogService"):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://local"
            ) as client:
                for case in cases:
                    if case["case"] in {
                        r["case"] for r in lines(output / "attempts.jsonl")
                    }:
                        continue
                    journals = [
                        lines(p)
                        for p in (DATA / "generated").glob("live-eval-*/attempts.jsonl")
                    ]
                    if sum(map(len, journals)) >= max_cases or (
                        args.run.startswith("retry")
                        and sum(
                            len(lines(p))
                            for p in (DATA / "generated").glob(
                                "live-eval-retry-*/attempts.jsonl"
                            )
                        )
                        >= max_retry_cases
                    ):
                        raise RuntimeError("Approved case count reached")
                    service.current_case = case["case"]
                    current_time = datetime.fromisoformat(
                        case.get("evaluation_time", fixture["evaluation_time"])
                    )
                    service._now_provider = lambda: current_time
                    append(output / "attempts.jsonl", case)
                    payload = dict(case["input"])
                    if case.get("image_source"):
                        import pymupdf

                        image = case["image_source"]
                        page = pymupdf.open(DATA / "source" / image["file"])[
                            image["page"] - 1
                        ]
                        pix = page.get_pixmap(
                            matrix=pymupdf.Matrix(3, 3),
                            clip=pymupdf.Rect(image["rect"]),
                            alpha=False,
                        )
                        payload["image"] = {
                            "data_base64": base64.b64encode(
                                pix.tobytes("png")
                            ).decode(),
                            "media_type": "image/png",
                        }
                    response = await client.post("/api/search/classify", json=payload)
                    result = response.json()
                    got = (result.get("classification") or {}).get("category_code")
                    ok = response.status_code == 200
                    if case["check_type"] == "classification":
                        ok = (
                            ok
                            and result.get("status") == "answered"
                            and got
                            in (
                                case["expected"]
                                if isinstance(case["expected"], list)
                                else [case["expected"]]
                            )
                        )
                    elif case["check_type"] == "hold":
                        ok = (
                            ok
                            and result.get("status") == "unable_to_determine"
                            and result.get("classification") is None
                            and result.get("next_collection") is None
                        )
                    else:
                        ok = (
                            ok
                            and result.get("status") == "needs_clarification"
                            and bool(result.get("follow_up_question"))
                            and result.get("classification") is None
                            and result.get("next_collection") is None
                        )
                    if result.get("status") == "answered":
                        region = get_registry().resolve(
                            case["input"]["municipality_id"],
                            case["input"]["district_id"],
                        )
                        cal = CalendarService(region=region)
                        next_date = cal.next_collection(got, at=current_time)
                        ok = ok and (result.get("next_collection") or {}).get(
                            "date"
                        ) == (next_date.date.isoformat() if next_date else None)
                        ok = (
                            ok
                            and (result.get("collection_status") or {}).get("status")
                            == cal.collection_status(got, next_date).status
                        )
                        if region.municipality_id != "38201":
                            ok = (
                                ok
                                and bool(result.get("sources"))
                                and all(
                                    (s.get("uri") or "").startswith(
                                        region.evidence_prefix
                                    )
                                    for s in result["sources"]
                                )
                            )
                    if "expected_collection_date" in case:
                        ok = (
                            ok
                            and (result.get("next_collection") or {}).get("date")
                            == case["expected_collection_date"]
                        )
                    if "expected_collection_status" in case:
                        ok = (
                            ok
                            and (result.get("collection_status") or {}).get("status")
                            == case["expected_collection_status"]
                        )
                    append(
                        output / "results.jsonl",
                        {
                            "case": case["case"],
                            "http": response.status_code,
                            "pass": bool(ok),
                            "response": result,
                        },
                    )
                    print(
                        case["case"],
                        bool(ok),
                        response.status_code,
                        result.get("status"),
                        got,
                        result.get("follow_up_question"),
                        flush=True,
                    )
                    if response.status_code != 200:
                        raise RuntimeError(
                            "API/system error: stopped without automatic retries"
                        )

    asyncio.run(run())
    index_cost = sum(
        r.get("reserved_usd", 0)
        for p in (DATA / "generated").glob("titan-*.jsonl")
        for r in lines(p)
    )
    print(
        "Combined conservative cost USD",
        index_cost
        + sum(
            settled_cost(lines(p))
            for p in (DATA / "generated").glob("live-eval-*/calls.jsonl")
        ),
    )


if __name__ == "__main__":
    main()
