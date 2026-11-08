#!/usr/bin/env python3
"""Run the approved real Bedrock evaluation for Shikokuchuo City.

The metered implementation is shared with the reviewed Kamijima evaluator;
only municipality-owned paths, identity and the approved USD0.08 ceiling are
changed. No AWS resource operation or deployment is performed.
"""
import kamijima_evaluate as evaluator


evaluator.DATA = evaluator.ROOT / "data/regions/shikokuchuo"
evaluator.CITY = "38213"
evaluator.CASES_PATH = evaluator.DATA / "search_cases.json"
evaluator.REVIEW_PATH = evaluator.DATA / "search_evaluation.json"
evaluator.ARTIFACTS = evaluator.DATA / "generated/live-eval"
evaluator.CHECKPOINT = evaluator.DATA / "generated/titan-checkpoint.jsonl"
evaluator.MANIFEST = evaluator.DATA / "knowledge/index_manifest.json"
evaluator.MAX_EVALUATION_CALLS = 45
evaluator.MAX_APPROVED_BUDGET_USD = 0.08


if __name__ == "__main__":
    evaluator.main()
