#!/usr/bin/env python3
"""Run the approved real Bedrock/API evaluation for the seven assigned areas.

Raw responses and call journals stay under the ignored evaluation artifacts
directory.  The reviewed, compact result is written to
``data/regions/assigned_search_review.json``.  This script does not deploy or
modify AWS resources and refuses to run without the explicit paid flag.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "data/regions/assigned_search_cases.json"
REVIEW_PATH = ROOT / "data/regions/assigned_search_review.json"
ARTIFACTS = ROOT / "backend/evaluation/artifacts/assigned-municipalities"
MUNICIPALITY_SLUGS = ("ozu", "tobe", "ainan", "kihoku", "matsuno", "uchiko", "masaki")
MAX_TOTAL_CALLS = 7726
MAX_EVALUATION_CALLS = 126
MAX_APPROVED_BUDGET_USD = 0.60
TITAN_PRICE_PER_1000_INPUT = 0.00002
NOVA_INPUT_PRICE_PER_1000 = 0.00006
NOVA_OUTPUT_PRICE_PER_1000 = 0.00024


def read_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def index_records() -> list[dict]:
    return [
        record
        for slug in MUNICIPALITY_SLUGS
        for record in read_lines(
            ROOT / f"data/regions/{slug}/generated/titan-checkpoint.jsonl"
        )
    ]


def index_usage() -> tuple[int, float, int, float]:
    records = index_records()
    calls = sum(int(record.get("calls", 0)) for record in records)
    reserve = sum(float(record.get("reserved_usd", 0)) for record in records)
    tokens = sum(int(record.get("input_tokens", 0) or 0) for record in records)
    estimated = tokens / 1000 * TITAN_PRICE_PER_1000_INPUT
    return calls, reserve, tokens, estimated


def settled_cost(records: list[dict]) -> float:
    amounts = {
        record["id"]: float(record["reserved_usd"])
        for record in records
        if record.get("event") == "reserve"
    }
    for record in records:
        if record.get("event") == "settle":
            amounts[record["id"]] = float(record["estimated_usd"])
    return sum(amounts.values())


def all_evaluation_records() -> list[dict]:
    if not ARTIFACTS.exists():
        return []
    return [
        record
        for journal in sorted(ARTIFACTS.glob("*/calls.jsonl"))
        for record in read_lines(journal)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-paid", action="store_true", required=True)
    parser.add_argument("--budget-usd", type=float, default=MAX_APPROVED_BUDGET_USD)
    parser.add_argument("--run-id", default="initial")
    parser.add_argument("--case", action="append", type=int, dest="case_ids",
                        help="Evaluate only this reviewed case number (repeatable)")
    args = parser.parse_args()
    if not args.confirm_paid:
        raise ValueError("Explicit paid approval is required")
    if not 0 < args.budget_usd <= MAX_APPROVED_BUDGET_USD:
        raise ValueError(f"Budget must not exceed USD {MAX_APPROVED_BUDGET_USD:.2f}")
    if not args.run_id.replace("-", "").isalnum():
        raise ValueError("run-id must contain only letters, numbers, and hyphens")

    os.environ["USE_BEDROCK_KNOWLEDGE_BASE"] = "false"
    os.environ["LEXICAL_SEARCH_ENABLED"] = "false"
    sys.path.insert(0, str(ROOT / "backend"))
    import boto3
    from botocore.config import Config
    from httpx import ASGITransport, AsyncClient
    from app import config
    from app.main import app
    from app.services.region_registry_service import get_registry
    from app.services.waste_guide_service import BedrockGateway, WasteGuideService

    settings = (
        config.BEDROCK_MODEL_ID,
        config.BEDROCK_EMBEDDING_MODEL_ID,
        config.EMBEDDING_SEARCH_TOP_K,
        config.EMBEDDING_SEARCH_MIN_SCORE,
        config.CLASSIFICATION_CONFIDENCE_THRESHOLD,
        config.USE_BEDROCK_KNOWLEDGE_BASE,
        config.LEXICAL_SEARCH_ENABLED,
    )
    expected_settings = (
        "amazon.nova-lite-v1:0",
        "amazon.titan-embed-text-v2:0",
        8,
        0.15,
        0.75,
        False,
        False,
    )
    if settings != expected_settings:
        raise ValueError("RAG configuration differs from the reviewed evaluation")

    fixture = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    if len(cases) != 42 or [case["case"] for case in cases] != list(range(1, 43)):
        raise ValueError("Reviewed evaluation must contain cases 1 through 42")
    if args.case_ids:
        requested = set(args.case_ids)
        unknown = requested - set(range(1, 43))
        if unknown:
            raise ValueError(f"Unknown reviewed cases: {sorted(unknown)}")
        cases = [case for case in cases if case["case"] in requested]
    output = ARTIFACTS / args.run_id
    output.mkdir(parents=True, exist_ok=True)
    datasets = {}
    for slug in MUNICIPALITY_SLUGS:
        base = ROOT / "data/regions" / slug
        for relative in ("registry.json", "knowledge/items.csv", "knowledge/item_embeddings.npz"):
            path = base / relative
            datasets[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    catalog = get_registry()
    for case in cases:
        region = catalog.resolve(
            case["input"]["municipality_id"], case["input"]["district_id"]
        )
        expected_category = case.get("expected_category")
        if expected_category and expected_category not in region.category_codes:
            raise ValueError(
                f"Case {case['case']} expects unknown category {expected_category}"
            )
        if not case["source_url"].startswith("https://"):
            raise ValueError(f"Case {case['case']} does not cite an HTTPS source")
    manifest = {
        "case_sha256": hashlib.sha256(CASES_PATH.read_bytes()).hexdigest(),
        "model_settings": list(settings),
        "evaluation_time": fixture["evaluation_time"],
        "combined_budget_usd": args.budget_usd,
        "max_total_calls": MAX_TOTAL_CALLS,
        "max_evaluation_calls": MAX_EVALUATION_CALLS,
        "selected_cases": [case["case"] for case in cases],
        "datasets": datasets,
    }
    manifest_path = output / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
        raise ValueError("Evaluation inputs changed; use a new reviewed run-id")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    class Meter:
        def __init__(self):
            credentials = boto3.Session().get_credentials()
            if credentials is None:
                raise RuntimeError("AWS credentials unavailable")
            credentials.get_frozen_credentials()
            self.client = boto3.client(
                "bedrock-runtime",
                region_name="ap-northeast-1",
                config=Config(
                    retries={"total_max_attempts": 1},
                    connect_timeout=10,
                    read_timeout=60,
                ),
            )

        def reserve(self, kind: str, amount: float) -> str:
            calls_path = output / "calls.jsonl"
            evaluation_records = all_evaluation_records()
            evaluation_calls = sum(
                record.get("event") == "reserve" for record in evaluation_records
            )
            index_calls, index_reserve, _, _ = index_usage()
            if (
                evaluation_calls >= MAX_EVALUATION_CALLS
                or index_calls + evaluation_calls >= MAX_TOTAL_CALLS
                or index_reserve + settled_cost(evaluation_records) + amount
                > args.budget_usd
            ):
                raise RuntimeError("Approved total cost/call limit reached")
            key = f"{args.run_id}-{kind}-{evaluation_calls + 1}"
            append(
                calls_path,
                {"event": "reserve", "id": key, "kind": kind, "reserved_usd": amount},
            )
            return key

        def invoke_model(self, **kwargs):
            text = json.loads(kwargs["body"])["inputText"]
            key = self.reserve(
                "titan", (len(text.encode("utf-8")) + 128) * 0.0002 / 1000
            )
            response = self.client.invoke_model(**kwargs)
            raw = response["body"].read()
            body = json.loads(raw)
            tokens = int(body.get("inputTextTokenCount", 0) or 0)
            append(
                output / "calls.jsonl",
                {
                    "event": "settle",
                    "id": key,
                    "input_tokens": tokens,
                    "estimated_usd": tokens / 1000 * TITAN_PRICE_PER_1000_INPUT,
                },
            )
            response["body"] = io.BytesIO(raw)
            return response

        def converse(self, **kwargs):
            content = [block for message in kwargs["messages"] for block in message["content"]]
            size = sum(len(block.get("text", "").encode("utf-8")) for block in content)
            key = self.reserve(
                "nova",
                (size + kwargs["inferenceConfig"]["maxTokens"]) / 1_000_000,
            )
            response = self.client.converse(**kwargs)
            usage = response["usage"]
            estimated = (
                usage["inputTokens"] / 1000 * NOVA_INPUT_PRICE_PER_1000
                + usage["outputTokens"] / 1000 * NOVA_OUTPUT_PRICE_PER_1000
            )
            append(
                output / "calls.jsonl",
                {
                    "event": "settle",
                    "id": key,
                    "usage": usage,
                    "estimated_usd": estimated,
                },
            )
            append(
                output / "nova-responses.jsonl",
                {"id": key, "output": response.get("output"), "usage": usage},
            )
            return response

    get_registry.cache_clear()
    service = WasteGuideService(
        gateway=BedrockGateway(runtime_client=Meter(), agent_runtime_client=object()),
        now_provider=lambda: datetime.fromisoformat(fixture["evaluation_time"]),
    )

    async def run() -> None:
        responses_path = output / "responses.jsonl"
        completed = {record["case"] for record in read_lines(responses_path)}
        with patch(
            "app.routers.search_router.WasteGuideService", return_value=service
        ), patch("app.routers.search_router.SearchLogService"):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://local"
            ) as client:
                for case in cases:
                    if case["case"] in completed:
                        continue
                    append(output / "attempts.jsonl", case)
                    response = await client.post("/api/search/classify", json=case["input"])
                    append(
                        responses_path,
                        {
                            "case": case["case"],
                            "http_status": response.status_code,
                            "body": response.json(),
                        },
                    )

    asyncio.run(run())

    responses = {record["case"]: record for record in read_lines(output / "responses.jsonl")}
    results = []
    for case in cases:
        response = responses.get(case["case"])
        body = (response or {}).get("body", {})
        status = body.get("status")
        category = (body.get("classification") or {}).get("category_code")
        question = body.get("follow_up_question") or ""
        ok = bool(response and response["http_status"] == 200)
        ok = ok and status == case["expected_status"]
        if case.get("expected_category"):
            ok = ok and category == case["expected_category"]
        if case.get("question_contains_any"):
            ok = ok and any(word in question for word in case["question_contains_any"])
        results.append(
            {
                "case": case["case"],
                "municipality": case["municipality"],
                "kind": case["kind"],
                "input": case["input"],
                "source_url": case["source_url"],
                "expected": {
                    "status": case["expected_status"],
                    "category": case.get("expected_category"),
                    "question_contains_any": case.get("question_contains_any", []),
                },
                "actual": {
                    "http_status": (response or {}).get("http_status"),
                    "status": status,
                    "category": category,
                    "follow_up_question": question or None,
                    "answer": body.get("answer"),
                },
                "passed": ok,
            }
        )
    call_records = read_lines(output / "calls.jsonl")
    all_call_records = all_evaluation_records()
    index_calls, index_reserve, index_tokens, index_estimated = index_usage()
    evaluation_calls = [record for record in call_records if record.get("event") == "reserve"]
    if args.case_ids and REVIEW_PATH.exists():
        previous = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
        merged_results = {result["case"]: result for result in previous.get("results", [])}
        merged_results.update({result["case"]: result for result in results})
        results = [merged_results[key] for key in sorted(merged_results)]
    all_evaluation_calls = [
        record for record in all_call_records if record.get("event") == "reserve"
    ]
    review = {
        "schema_version": 1,
        "run_id": args.run_id,
        "case_sha256": manifest["case_sha256"],
        "dataset_sha256": datasets,
        "model_ids": {"rewrite_and_decide": settings[0], "embedding": settings[1]},
        "summary": {
            "cases": len(results),
            "passed": sum(result["passed"] for result in results),
            "failed": sum(not result["passed"] for result in results),
        },
        "usage": {
            "embedding_generation_calls": index_calls,
            "embedding_input_tokens": index_tokens,
            "evaluation_model_calls": len(all_evaluation_calls),
            "evaluation_nova_calls": sum(r["kind"] == "nova" for r in all_evaluation_calls),
            "evaluation_titan_calls": sum(r["kind"] == "titan" for r in all_evaluation_calls),
            "estimated_actual_usd": index_estimated + settled_cost(all_call_records),
            "conservative_reserved_usd": index_reserve + settled_cost(all_call_records),
            "approved_limit_usd": args.budget_usd,
        },
        "results": results,
    }
    REVIEW_PATH.write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(review["summary"], ensure_ascii=False))
    print(json.dumps(review["usage"], ensure_ascii=False))


if __name__ == "__main__":
    main()
