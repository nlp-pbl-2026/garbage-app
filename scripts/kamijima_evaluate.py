#!/usr/bin/env python3
"""Run the explicitly approved real Bedrock evaluation for Kamijima Town.

This script performs no AWS resource operation or deployment. It journals each
paid model call before inference, disables SDK retries, and enforces the
approved 42-call / USD0.07 combined index-and-evaluation ceiling.
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
DATA = ROOT / "data/regions/kamijima"
CITY = "38356"
CASES_PATH = DATA / "search_cases.json"
REVIEW_PATH = DATA / "search_evaluation.json"
ARTIFACTS = DATA / "generated/live-eval"
CHECKPOINT = DATA / "generated/titan-checkpoint.jsonl"
MANIFEST = DATA / "knowledge/index_manifest.json"
MAX_EVALUATION_CALLS = 42
MAX_APPROVED_BUDGET_USD = 0.07
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


def index_usage() -> tuple[int, int, float, float]:
    records = read_lines(CHECKPOINT)
    successful = [record for record in records if record.get("input_tokens") is not None]
    tokens = sum(int(record["input_tokens"]) for record in successful)
    reserve = float(json.loads(MANIFEST.read_text(encoding="utf-8"))["generation_budget_reserve_usd"])
    return len(successful), tokens, tokens / 1000 * TITAN_PRICE_PER_1000_INPUT, reserve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-paid", action="store_true", required=True)
    parser.add_argument("--budget-usd", type=float, default=MAX_APPROVED_BUDGET_USD)
    parser.add_argument("--rerun-case", type=int)
    args = parser.parse_args()
    if not args.confirm_paid:
        raise ValueError("Explicit paid approval is required")
    if not 0 < args.budget_usd <= MAX_APPROVED_BUDGET_USD:
        raise ValueError(
            f"Budget must not exceed the approved USD{MAX_APPROVED_BUDGET_USD:.2f}"
        )

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
    if len(cases) != 14 or [case["case"] for case in cases] != list(range(1, 15)):
        raise ValueError("Reviewed evaluation must contain cases 1 through 14")
    if args.rerun_case is not None and args.rerun_case not in range(1, 15):
        raise ValueError("rerun-case must be between 1 and 14")
    get_registry.cache_clear()
    registry = get_registry()
    for case in cases:
        region = registry.resolve(CITY, case["input"]["district_id"])
        expected_category = case.get("expected_category")
        if expected_category and expected_category not in region.category_codes:
            raise ValueError(f"Case {case['case']} expects an unknown category")
        if not case["source_url"].startswith("https://"):
            raise ValueError(f"Case {case['case']} lacks an official HTTPS source")

    datasets = {}
    for relative in (
        "registry.json",
        "knowledge/items.csv",
        "knowledge/item_embeddings.npz",
    ):
        path = DATA / relative
        datasets[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    run_manifest = {
        "case_sha256": hashlib.sha256(CASES_PATH.read_bytes()).hexdigest(),
        "model_settings": list(settings),
        "evaluation_time": fixture["evaluation_time"],
        "combined_budget_usd": args.budget_usd,
        "max_evaluation_calls": MAX_EVALUATION_CALLS,
        "datasets": datasets,
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    run_manifest_path = ARTIFACTS / "manifest.json"
    if run_manifest_path.exists():
        previous_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
        if previous_manifest != run_manifest:
            retry_mutable = {"max_evaluation_calls", "datasets"}
            previous_without_limit = {key: value for key, value in previous_manifest.items()
                                      if key not in retry_mutable}
            current_without_limit = {key: value for key, value in run_manifest.items()
                                     if key not in retry_mutable}
            previous_datasets = previous_manifest.get("datasets", {})
            current_datasets = run_manifest.get("datasets", {})
            approved_retry = (
                args.rerun_case is not None
                and previous_without_limit == current_without_limit
                and previous_manifest.get("max_evaluation_calls", 0) < MAX_EVALUATION_CALLS
                and set(previous_datasets) == set(current_datasets)
                and previous_datasets.get("registry.json") == current_datasets.get("registry.json")
            )
            if not approved_retry:
                raise ValueError("Evaluation inputs changed; review before another paid run")
    run_manifest_path.write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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
            records = read_lines(ARTIFACTS / "calls.jsonl")
            calls = sum(record.get("event") == "reserve" for record in records)
            _, _, _, index_reserve = index_usage()
            if (
                calls >= MAX_EVALUATION_CALLS
                or index_reserve + settled_cost(records) + amount > args.budget_usd
            ):
                raise RuntimeError("Approved total cost/call limit reached")
            key = f"{kind}-{calls + 1}"
            append(
                ARTIFACTS / "calls.jsonl",
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
                ARTIFACTS / "calls.jsonl",
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
                "nova", (size + kwargs["inferenceConfig"]["maxTokens"]) / 1_000_000
            )
            response = self.client.converse(**kwargs)
            usage = response["usage"]
            estimated = (
                usage["inputTokens"] / 1000 * NOVA_INPUT_PRICE_PER_1000
                + usage["outputTokens"] / 1000 * NOVA_OUTPUT_PRICE_PER_1000
            )
            append(
                ARTIFACTS / "calls.jsonl",
                {
                    "event": "settle",
                    "id": key,
                    "usage": usage,
                    "estimated_usd": estimated,
                },
            )
            append(
                ARTIFACTS / "nova-responses.jsonl",
                {"id": key, "output": response.get("output"), "usage": usage},
            )
            return response

    service = WasteGuideService(
        gateway=BedrockGateway(runtime_client=Meter(), agent_runtime_client=object()),
        now_provider=lambda: datetime.fromisoformat(fixture["evaluation_time"]),
    )

    async def run() -> None:
        responses_path = ARTIFACTS / "responses.jsonl"
        completed = {record["case"] for record in read_lines(responses_path)}
        if args.rerun_case is not None:
            completed = set(range(1, 15)) - {args.rerun_case}
        with patch(
            "app.routers.search_router.WasteGuideService", return_value=service
        ), patch("app.routers.search_router.SearchLogService"):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://local"
            ) as client:
                for case in cases:
                    if case["case"] in completed:
                        continue
                    append(ARTIFACTS / "attempts.jsonl", case)
                    response = await client.post("/api/search/classify", json=case["input"])
                    append(
                        responses_path,
                        {
                            "case": case["case"],
                            "http_status": response.status_code,
                            "body": response.json(),
                        },
                    )
                    print(case["case"], response.status_code, flush=True)
                    if response.status_code != 200:
                        print("Stopped at API/system error; no automatic retry", flush=True)
                        break

    asyncio.run(run())

    responses = {
        record["case"]: record for record in read_lines(ARTIFACTS / "responses.jsonl")
    }
    results = []
    for case in cases:
        response = responses.get(case["case"])
        body = (response or {}).get("body", {})
        status = body.get("status")
        category = (body.get("classification") or {}).get("category_code")
        question = body.get("follow_up_question") or ""
        passed = bool(response and response["http_status"] == 200)
        passed = passed and status == case["expected_status"]
        if case.get("expected_category"):
            passed = passed and category == case["expected_category"]
        if case.get("question_contains_any"):
            passed = passed and any(word in question for word in case["question_contains_any"])
        results.append(
            {
                "case": case["case"],
                "kind": case["kind"],
                "query": case["input"]["query"],
                "source_url": case["source_url"],
                "official_expected": {
                    "status": case["expected_status"],
                    "category": case.get("expected_category"),
                    "reason": case["official_reason"],
                },
                "actual": {
                    "http_status": (response or {}).get("http_status"),
                    "status": status,
                    "category": category,
                    "follow_up_question": question or None,
                    "answer": body.get("answer"),
                },
                "passed": passed,
            }
        )

    records = read_lines(ARTIFACTS / "calls.jsonl")
    evaluation_calls = [record for record in records if record.get("event") == "reserve"]
    index_calls, index_tokens, index_actual, index_reserve = index_usage()
    review = {
        "schema_version": 1,
        "case_sha256": run_manifest["case_sha256"],
        "dataset_sha256": datasets,
        "model_ids": {"rewrite_and_decide": settings[0], "embedding": settings[1]},
        "summary": {
            "cases": len(results),
            "passed": sum(result["passed"] for result in results),
            "failed": sum(not result["passed"] for result in results),
        },
        "usage": {
            "embedding_generation_model_calls": index_calls,
            "embedding_input_tokens": index_tokens,
            "evaluation_model_calls": len(evaluation_calls),
            "evaluation_nova_calls": sum(record["kind"] == "nova" for record in evaluation_calls),
            "evaluation_titan_calls": sum(record["kind"] == "titan" for record in evaluation_calls),
            "estimated_actual_usd": index_actual + settled_cost(records),
            "conservative_reserved_usd": index_reserve + settled_cost(records),
            "approved_limit_usd": args.budget_usd,
        },
        "partial_rerun_cases": [args.rerun_case] if args.rerun_case is not None else [],
        "results": results,
    }
    REVIEW_PATH.write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(review["summary"], ensure_ascii=False))
    print(json.dumps(review["usage"], ensure_ascii=False))


if __name__ == "__main__":
    main()
