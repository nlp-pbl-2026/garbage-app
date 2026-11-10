#!/usr/bin/env python3
"""Run an approved real Bedrock evaluation for Seiyo City only."""
import kamijima_evaluate as evaluator


evaluator.DATA = evaluator.ROOT / "data/regions/seiyo"
evaluator.CITY = "38214"
evaluator.CASES_PATH = evaluator.DATA / "search_cases.json"
evaluator.REVIEW_PATH = evaluator.DATA / "search_evaluation.json"
evaluator.ARTIFACTS = evaluator.DATA / "generated/live-eval"
evaluator.CHECKPOINT = evaluator.DATA / "generated/titan-checkpoint.jsonl"
evaluator.MANIFEST = evaluator.DATA / "knowledge/index_manifest.json"
evaluator.MAX_EVALUATION_CALLS = 48
evaluator.MAX_APPROVED_BUDGET_USD = 0.15


if __name__ == "__main__":
    evaluator.main()
