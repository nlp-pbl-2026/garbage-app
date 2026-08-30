"""RAG検索脚のアブレーション評価（Hybrid / Embedding単体 / Text単体）。

判定LLM(Nova)・プロンプト・追加質問シミュレータを固定し、検索の脚だけを
切り替えて同一のtestデータで比較する。パイプラインはローカルで実行し、
意味検索は自前Embedding索引（Titan）を用いる。

    uv run python -m evaluation.run_ablation --split test --mode hybrid
    uv run python -m evaluation.run_ablation --split test --mode embedding
    uv run python -m evaluation.run_ablation --split test --mode lexical
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import boto3

from app import config
from app.services.embedding_search_service import EmbeddingSearchService
from app.services.item_search_service import ItemSearchService
from app.services.waste_guide_service import BedrockGateway, WasteGuideService
from evaluation.common import DEFAULT_MODEL_ID, DEFAULT_REGION, read_jsonl
from evaluation.run_evaluation import build_report, render_markdown, simulate_answer

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_DIR = BACKEND_ROOT / "evaluation/artifacts/dataset"
DEFAULT_RUNS_DIR = BACKEND_ROOT / "evaluation/artifacts/runs"
MUNICIPALITY_ID = "38201"
DISTRICT_ID = "38201-08"


class _EmptySearch:
    """検索脚を無効化するためのスタブ。"""

    def search(self, query, *, limit=None):
        return []


def build_service(mode: str) -> WasteGuideService:
    use_lexical = mode in ("hybrid", "lexical")
    use_embedding = mode in ("hybrid", "embedding")
    # retrieve()はconfig.LEXICAL_SEARCH_ENABLEDを見るため、モードに合わせて上書き。
    config.LEXICAL_SEARCH_ENABLED = use_lexical
    lexical = ItemSearchService() if use_lexical else _EmptySearch()
    embedding = EmbeddingSearchService() if use_embedding else _EmptySearch()
    gateway = BedrockGateway(embedding_search=embedding)
    return WasteGuideService(gateway=gateway, item_search=lexical)


def evaluate_case(
    service: WasteGuideService,
    bedrock_client,
    case: dict,
    *,
    simulator_model_id: str,
    max_turns: int,
) -> dict:
    expected = case["expected"]["category_code"]
    clarifications: list[dict[str, str]] = []
    started = time.monotonic()
    try:
        result = None
        for turn in range(max_turns + 1):
            result = service.query(
                query=case["query"],
                municipality_id=MUNICIPALITY_ID,
                district_id=DISTRICT_ID,
                clarifications=clarifications,
            )
            if result.status != "needs_clarification":
                break
            question = (result.follow_up_question or "").strip()
            if not question or turn >= max_turns:
                break
            answer = simulate_answer(
                bedrock_client, case, question, model_id=simulator_model_id
            )
            clarifications.append({"question": question, "answer": answer})

        decision = result.decision
        predicted = decision.category_code if decision else None
        status = result.status
        correct = status == "answered" and predicted == expected
        outcome = (
            "correct"
            if correct
            else ("wrong_category" if status == "answered" else "unresolved")
        )
        return {
            "case_id": case["case_id"],
            "split": case.get("split"),
            "query": case["query"],
            "ambiguity_type": case.get("ambiguity_type"),
            "expected": case["expected"],
            "predicted_category_code": predicted or None,
            "predicted_item": decision.item_name if decision else None,
            "confidence": decision.confidence if decision else None,
            "final_status": status,
            "outcome": outcome,
            "correct": correct,
            "clarification_count": len(clarifications),
            "clarifications": clarifications,
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as error:  # 個別失敗でも継続。
        return {
            "case_id": case["case_id"],
            "split": case.get("split"),
            "query": case["query"],
            "ambiguity_type": case.get("ambiguity_type"),
            "expected": case["expected"],
            "predicted_category_code": None,
            "final_status": "error",
            "outcome": "error",
            "correct": False,
            "clarification_count": len(clarifications),
            "clarifications": clarifications,
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
            "error": f"{type(error).__name__}: {error}",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "test"), default="test")
    parser.add_argument(
        "--mode", choices=("hybrid", "embedding", "lexical"), required=True
    )
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--simulator-model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--region", default=DEFAULT_REGION)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = read_jsonl(args.dataset_dir / f"{args.split}.jsonl")
    if args.limit > 0:
        cases = cases[: args.limit]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        args.output_dir
        or DEFAULT_RUNS_DIR / f"ablation-{args.mode}-{args.split}-{timestamp}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    service = build_service(args.mode)
    bedrock_client = boto3.client("bedrock-runtime", region_name=args.region)
    results: list[dict] = []
    for index, case in enumerate(cases, start=1):
        result = evaluate_case(
            service,
            bedrock_client,
            case,
            simulator_model_id=args.simulator_model_id,
            max_turns=args.max_turns,
        )
        results.append(result)
        mark = "OK" if result["correct"] else "NG"
        print(
            f"[{index}/{len(cases)}] {mark} {case['query'][:36]} "
            f"exp={case['expected']['category_code']} "
            f"got={result.get('predicted_category_code')} "
            f"turns={result['clarification_count']}"
        )
        if index < len(cases) and args.delay:
            time.sleep(args.delay)

    report = build_report(results)
    report.update(
        {
            "created_at": datetime.now(UTC).isoformat(),
            "split": args.split,
            "mode": args.mode,
            "retrieval": {
                "hybrid": "lexical + embedding",
                "embedding": "embedding only",
                "lexical": "text (lexical) only",
            }[args.mode],
            "note": "RAG脚のアブレーション。判定LLM(Nova)・プロンプト・追加質問は固定。",
        }
    )
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(
        render_markdown(report, results), encoding="utf-8"
    )
    with (output_dir / "results.jsonl").open("w", encoding="utf-8") as file:
        for row in results:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(
        f"[{args.mode}] accuracy {report['accuracy']*100:.1f}% "
        f"({report['correct']}/{report['total']})  "
        f"avg {report['average_duration_ms']/1000:.1f}s"
    )
    print(f"report: {output_dir / 'report.md'}")


if __name__ == "__main__":
    main()
