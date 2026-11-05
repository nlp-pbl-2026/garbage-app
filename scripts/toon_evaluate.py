#!/usr/bin/env python3
"""Explicit PAID 33-case Toon API evaluation; requires separate user approval.

No AWS resource operations. No index generation. Calls are journalled before
inference, with no SDK retries and a combined index/evaluation budget guard.
Raw model responses stay in ignored generated/; publish only reviewed summaries.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/regions/toon"


def lines(path):
    return (
        [json.loads(line) for line in path.read_text().splitlines()]
        if path.exists()
        else []
    )


def append(path, record):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def settled_cost(records):
    amounts = {r["id"]: r["reserved_usd"] for r in records if r["event"] == "reserve"}
    for record in records:
        if record["event"] == "settle":
            amounts[record["id"]] = record["upper_usd"]
    return sum(amounts.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-paid", action="store_true", required=True)
    parser.add_argument("--budget-usd", type=float, default=1)
    parser.add_argument("--repeat-cases", type=int, nargs="*", default=[])
    parser.add_argument(
        "--run",
        choices=["initial", "condition-fix", "final", "metadata-fix"],
        default="initial",
    )
    args = parser.parse_args()
    if not args.confirm_paid or not 0 < args.budget_usd <= 1:
        raise ValueError("Separate paid approval and a budget up to USD1 required")
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
    from app.services.waste_guide_service import BedrockGateway, WasteGuideService

    config_values = (
        config.BEDROCK_MODEL_ID,
        config.BEDROCK_EMBEDDING_MODEL_ID,
        config.EMBEDDING_SEARCH_TOP_K,
        config.EMBEDDING_SEARCH_MIN_SCORE,
        config.CLASSIFICATION_CONFIDENCE_THRESHOLD,
        config.USE_BEDROCK_KNOWLEDGE_BASE,
        config.LEXICAL_SEARCH_ENABLED,
    )
    if config_values != (
        "amazon.nova-lite-v1:0",
        "amazon.titan-embed-text-v2:0",
        8,
        0.15,
        0.75,
        False,
        False,
    ):
        raise ValueError("RAG configuration differs from the reviewed evaluation")
    output = DATA / "generated" / ("live-eval-" + args.run)
    output.mkdir(parents=True, exist_ok=True)
    cases_path = DATA / "search_cases.json"
    fixture = json.loads(cases_path.read_text())
    now = datetime.fromisoformat(fixture["evaluation_time"])
    cases = fixture["cases"]
    if len(cases) != 33 or [c["case"] for c in cases] != list(range(1, 34)):
        raise ValueError("Approved evaluation contains exactly 33 cases")
    if args.run in {"condition-fix", "metadata-fix"}:
        # The approved overall allowance includes at most eight repeat cases.
        if not 0 < len(set(args.repeat_cases)) <= 8:
            raise ValueError("At most eight approved repeat cases")
        if args.run == "metadata-fix":
            follow_up = fixture.get("follow_up_cases", [])
            if len(follow_up) != 4 or [c["case"] for c in follow_up] != [
                34,
                35,
                36,
                37,
            ]:
                raise ValueError(
                    "Only the four reviewed supplemental cases are allowed"
                )
            cases = follow_up
        if not set(args.repeat_cases) <= {c["case"] for c in cases}:
            raise ValueError("Unknown evaluation case")
        cases = [c for c in cases if c["case"] in args.repeat_cases]
    manifest = {
        "case_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "model_settings": list(config_values),
        "evaluation_time": now.isoformat(),
        "combined_budget_usd": args.budget_usd,
        "max_evaluation_calls": 240,
        "index_regenerated": False,
        "case_ids": [c["case"] for c in cases],
        "dataset_sha256": {
            str(p.relative_to(DATA)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                DATA / "registry.json",
                DATA / "knowledge/items.csv",
                DATA / "knowledge/item_embeddings.npz",
            )
        },
    }
    manifest_path = output / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise ValueError("Evaluation inputs changed; review before another paid run")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    class Meter:
        def __init__(self):
            credentials = boto3.Session().get_credentials()
            if credentials is None:
                raise RuntimeError("AWS credentials unavailable")
            credentials.get_frozen_credentials()  # Stop once before recording/attempting cases.
            self.client = boto3.client(
                "bedrock-runtime",
                region_name="ap-northeast-1",
                config=Config(
                    retries={"total_max_attempts": 1},
                    connect_timeout=10,
                    read_timeout=45,
                ),
            )

        def reserve(self, kind, amount):
            journals = [
                lines(p) for p in (DATA / "generated").glob("live-eval*/calls.jsonl")
            ]
            index_cost = sum(
                r.get("reserved_usd", 0)
                for r in lines(DATA / "generated/titan-checkpoint.jsonl")
            )
            calls = sum(
                r["event"] == "reserve" for journal in journals for r in journal
            )
            if (
                calls >= 240
                or index_cost + sum(settled_cost(j) for j in journals) + amount
                > args.budget_usd
            ):
                raise RuntimeError("Approved total cost/call limit reached")
            key = f"{kind}-{calls+1}"
            append(
                output / "calls.jsonl",
                {"event": "reserve", "id": key, "kind": kind, "reserved_usd": amount},
            )
            return key

        def invoke_model(self, **kwargs):
            text = json.loads(kwargs["body"])["inputText"]
            self.reserve("titan", (len(text.encode()) + 128) * 0.0002 / 1000)
            return self.client.invoke_model(**kwargs)

        def converse(self, **kwargs):
            content = [c for m in kwargs["messages"] for c in m["content"]]
            size = sum(len(c.get("text", "").encode()) for c in content)
            # USD1/M for all tokens is a deliberately conservative budget rate;
            # UTF-8 bytes and 10000/image are reserved, actual usage settles success.
            key = self.reserve(
                "nova",
                (
                    size
                    + 10000 * sum("image" in c for c in content)
                    + kwargs["inferenceConfig"]["maxTokens"]
                )
                / 1e6,
            )
            response = self.client.converse(**kwargs)
            usage = response["usage"]
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
                {"id": key, "output": response.get("output"), "usage": usage},
            )
            return response

    service = WasteGuideService(
        gateway=BedrockGateway(runtime_client=Meter(), agent_runtime_client=object()),
        now_provider=lambda: now,
    )

    async def run():
        # No lifespan/database initialization or search-log writes.
        with patch(
            "app.routers.search_router.WasteGuideService", return_value=service
        ), patch("app.routers.search_router.SearchLogService"):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://local"
            ) as client:
                attempted = {r["case"] for r in lines(output / "attempts.jsonl")}
                for case in cases:
                    if case["case"] in attempted:
                        continue
                    body = dict(case["input"])
                    journals = [
                        lines(p)
                        for p in (DATA / "generated").glob("live-eval*/attempts.jsonl")
                    ]
                    if sum(len(j) for j in journals) >= 74:
                        raise RuntimeError("Approved 74-case limit reached")
                    if (
                        args.run == "condition-fix"
                        and len(lines(output / "attempts.jsonl")) >= 8
                    ):
                        raise RuntimeError("Approved eight-repeat limit reached")
                    append(output / "attempts.jsonl", case)
                    response = await client.post("/api/search/classify", json=body)
                    result = response.json()
                    got = (result.get("classification") or {}).get("category_code")
                    ok = response.status_code == 200
                    if case["check_type"] == "classification":
                        ok = (
                            ok
                            and result.get("status") == "answered"
                            and got == case["expected"]
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
                            body["municipality_id"], body["district_id"]
                        )
                        cal = CalendarService(region=region)
                        next_date = cal.next_collection(got, at=now)
                        ok = ok and (result.get("next_collection") or {}).get(
                            "date"
                        ) == (next_date.date.isoformat() if next_date else None)
                        ok = (
                            ok
                            and (result.get("collection_status") or {}).get("status")
                            == cal.collection_status(got, next_date).status
                        )
                        if body["municipality_id"] != "38201":
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
                        print(
                            "Stopped at API/system error; no automatic retries",
                            flush=True,
                        )
                        break

    asyncio.run(run())
    index_cost = sum(
        r.get("reserved_usd", 0)
        for r in lines(DATA / "generated/titan-checkpoint.jsonl")
    )
    print(
        "Combined conservative cost USD",
        index_cost
        + sum(
            settled_cost(lines(p))
            for p in (DATA / "generated").glob("live-eval*/calls.jsonl")
        ),
    )


if __name__ == "__main__":
    main()
