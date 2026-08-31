"""曖昧クエリを実APIへ送り、追加質問へLLMで回答して採点する。"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
import httpx

from evaluation.common import (
    DEFAULT_MODEL_ID,
    DEFAULT_REGION,
    append_jsonl,
    converse_json,
    read_jsonl,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_DIR = BACKEND_ROOT / "evaluation/artifacts/dataset"
DEFAULT_RUNS_DIR = BACKEND_ROOT / "evaluation/artifacts/runs"


def clarification_prompt(case: dict[str, Any], question: str) -> str:
    expected = case["expected"]
    return f"""
あなたはごみ分別サービスを試す利用者役です。想定した実物について、サービスからの追加質問に答えてください。

最初の入力: {case['query']}
想定した正解品目: {expected['item']}
実物の設定: {case['hidden_context']}
資料上の条件・注意: {expected.get('note') or 'なし'}
追加質問: {question}

規則:
- 実物の設定と正解品目に矛盾しない事実だけを答える。
- 質問の前提が実物設定と異なる場合は同意しない。例えば紙製品にプラマークがあるか聞かれたら、
  「いいえ、紙製です」のように誤った前提を訂正する。
- 質問された内容だけに、一般利用者らしい短い日本語で答える。
- 分類コード、正解分類名、評価用データであることは答えに含めない。
- 設定に直接書かれていなくても、正解品目から社会通念上明らかな事実は答えてよい。
- 本当に判断できない場合だけ「わかりません」と答える。

次のJSONだけを返してください。
{{"answer":"追加質問への回答"}}
""".strip()


def answer_review_prompt(
    case: dict[str, Any], question: str, proposed_answer: str
) -> str:
    return f"""
追加質問への回答が、想定した実物と矛盾しないか確認して修正してください。

正解品目: {case['expected']['item']}
実物の設定: {case['hidden_context']}
資料上の条件: {case['expected'].get('note') or 'なし'}
質問: {question}
回答案: {proposed_answer}

紙製品にプラマークがあると答える、PETボトルを単なるプラスチック容器とだけ答えるなど、
分類の決め手を失う回答は禁止です。質問に短く直接答え、必要なら誤った前提を訂正してください。
分類コードや分類名は書かないでください。

次のJSONだけを返してください。
{{"answer":"検証済みの短い回答"}}
""".strip()


def simulate_answer(
    client, case: dict[str, Any], question: str, *, model_id: str
) -> str:
    value = converse_json(
        client,
        model_id=model_id,
        prompt=clarification_prompt(case, question),
        max_tokens=180,
        temperature=0.0,
    )
    answer = str(value.get("answer", "")).strip()
    if not answer:
        raise ValueError("追加質問シミュレーターが空の回答を返しました")
    reviewed = converse_json(
        client,
        model_id=model_id,
        prompt=answer_review_prompt(case, question, answer),
        max_tokens=180,
        temperature=0.0,
    )
    verified_answer = str(reviewed.get("answer", "")).strip()
    if not verified_answer:
        raise ValueError("追加質問回答の検証結果が空でした")
    return verified_answer


def post_classification(
    client: httpx.Client,
    *,
    api_url: str,
    query: str,
    clarifications: list[dict[str, str]],
    retries: int = 3,
) -> dict[str, Any]:
    payload = {
        "query": query,
        "municipality_id": "38201",
        "municipality_name": "松山市",
        "district_id": "38201-08",
        "district_name": "清水",
        "clarifications": clarifications,
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.post(
                f"{api_url.rstrip('/')}/api/search/classify", json=payload
            )
            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            if response.status_code >= 400:
                raise RuntimeError(
                    f"API {response.status_code}: {response.text[:500]}"
                )
            return response.json()
        except (httpx.HTTPError, RuntimeError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"分類APIへの接続に失敗しました: {last_error}")


def evaluate_case(
    case: dict[str, Any],
    *,
    http_client: httpx.Client,
    bedrock_client,
    api_url: str,
    simulator_model_id: str,
    max_turns: int,
) -> dict[str, Any]:
    clarifications: list[dict[str, str]] = []
    transcript: list[dict[str, Any]] = []
    started = time.monotonic()
    try:
        for turn in range(max_turns + 1):
            response = post_classification(
                http_client,
                api_url=api_url,
                query=case["query"],
                clarifications=clarifications,
            )
            transcript.append({"turn": turn, "response": response})
            if response.get("status") != "needs_clarification":
                break
            question = str(response.get("follow_up_question") or "").strip()
            if not question or turn >= max_turns:
                break
            answer = simulate_answer(
                bedrock_client,
                case,
                question,
                model_id=simulator_model_id,
            )
            clarifications.append({"question": question, "answer": answer})
            transcript[-1]["simulated_answer"] = answer

        final = transcript[-1]["response"]
        classification = final.get("classification") or {}
        predicted = classification.get("category_code")
        expected = case["expected"]["category_code"]
        status = final.get("status")
        correct = status == "answered" and predicted == expected
        if correct:
            outcome = "correct"
        elif status == "answered":
            outcome = "wrong_category"
        else:
            outcome = "unresolved"
        return {
            "case_id": case["case_id"],
            "split": case.get("split"),
            "query": case["query"],
            "ambiguity_type": case.get("ambiguity_type"),
            "expected": case["expected"],
            "predicted_category_code": predicted,
            "predicted_item": classification.get("item_name"),
            "confidence": classification.get("confidence"),
            "final_status": status,
            "outcome": outcome,
            "correct": correct,
            "clarification_count": len(clarifications),
            "clarifications": clarifications,
            "rewritten_query": final.get("rewritten_query"),
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
            "transcript": transcript,
        }
    except Exception as error:  # 継続評価のため、個別ケースの失敗を記録する。
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
            "transcript": transcript,
        }


def safe_rate(correct: int, total: int) -> float:
    return round(correct / total, 4) if total else 0.0


def build_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    correct = sum(bool(row["correct"]) for row in results)
    outcomes = Counter(row["outcome"] for row in results)
    category_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ambiguity_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        category_rows[row["expected"]["category_code"]].append(row)
        ambiguity_rows[str(row.get("ambiguity_type") or "その他")].append(row)

    def breakdown(groups: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        return {
            key: {
                "total": len(rows),
                "correct": sum(bool(row["correct"]) for row in rows),
                "accuracy": safe_rate(
                    sum(bool(row["correct"]) for row in rows), len(rows)
                ),
            }
            for key, rows in sorted(groups.items())
        }

    confidences = [
        float(row["confidence"])
        for row in results
        if row.get("confidence") is not None
    ]
    durations = sorted(float(row["duration_ms"]) for row in results)

    def percentile(values: list[float], fraction: float) -> float:
        if not values:
            return 0.0
        index = min(len(values) - 1, int(round(fraction * (len(values) - 1))))
        return round(values[index], 1)

    return {
        "total": total,
        "correct": correct,
        "accuracy": safe_rate(correct, total),
        "outcomes": dict(sorted(outcomes.items())),
        "average_clarifications": round(
            statistics.fmean(row["clarification_count"] for row in results), 3
        )
        if results
        else 0.0,
        "average_confidence": round(statistics.fmean(confidences), 3)
        if confidences
        else None,
        "average_duration_ms": round(statistics.fmean(durations), 1)
        if durations
        else 0.0,
        "duration_ms_stats": {
            "min": round(durations[0], 1) if durations else 0.0,
            "median": percentile(durations, 0.5),
            "p95": percentile(durations, 0.95),
            "max": round(durations[-1], 1) if durations else 0.0,
        },
        "by_category": breakdown(category_rows),
        "by_ambiguity_type": breakdown(ambiguity_rows),
    }


def render_markdown(report: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines = [
        "# あいまい検索 評価レポート",
        "",
        f"- 件数: {report['total']}",
        f"- 正解: {report['correct']}",
        f"- 分類精度: {report['accuracy']:.1%}",
        f"- 平均追加質問数: {report['average_clarifications']}",
        f"- 平均確信度: {report['average_confidence']}",
        f"- 平均応答時間: {report['average_duration_ms']} ms",
        (
            f"- 応答時間 min/median/p95/max: "
            f"{report['duration_ms_stats']['min']} / "
            f"{report['duration_ms_stats']['median']} / "
            f"{report['duration_ms_stats']['p95']} / "
            f"{report['duration_ms_stats']['max']} ms"
        ),
        "",
        "## 結果内訳",
        "",
    ]
    for outcome, count in report["outcomes"].items():
        lines.append(f"- {outcome}: {count}")
    lines.extend(["", "## カテゴリ別", "", "| 分類 | 正解/件数 | 精度 |", "| --- | ---: | ---: |"])
    for category, values in report["by_category"].items():
        lines.append(
            f"| {category} | {values['correct']}/{values['total']} | "
            f"{values['accuracy']:.1%} |"
        )
    lines.extend(["", "## 失敗例", ""])
    failures = [row for row in results if not row["correct"]]
    if not failures:
        lines.append("なし")
    for row in failures[:20]:
        lines.extend(
            [
                f"### {row['case_id']}: {row['query']}",
                "",
                f"- 正解: {row['expected']['item']} / {row['expected']['category_code']}",
                f"- 予測: {row.get('predicted_item') or '-'} / {row.get('predicted_category_code') or '-'}",
                f"- 結果: {row['outcome']}",
                f"- 言い換え: {row.get('rewritten_query') or '-'}",
                f"- 追加質問: {json.dumps(row.get('clarifications', []), ensure_ascii=False)}",
                f"- エラー: {row.get('error') or '-'}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "test"), required=True)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--api-url", default=os.getenv("EVAL_API_BASE_URL", ""))
    parser.add_argument(
        "--simulator-model-id",
        default=os.getenv("EVAL_SIMULATOR_MODEL_ID", DEFAULT_MODEL_ID),
    )
    parser.add_argument("--region", default=os.getenv("AWS_REGION", DEFAULT_REGION))
    args = parser.parse_args()
    if not args.api_url:
        parser.error("--api-url または EVAL_API_BASE_URL を指定してください")
    return args


def main() -> None:
    args = parse_args()
    cases = read_jsonl(args.dataset_dir / f"{args.split}.jsonl")
    if args.limit > 0:
        cases = cases[: args.limit]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or DEFAULT_RUNS_DIR / f"{args.split}-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "results.jsonl"
    results_path.unlink(missing_ok=True)

    bedrock_client = boto3.client("bedrock-runtime", region_name=args.region)
    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=70.0) as http_client:
        for index, case in enumerate(cases, start=1):
            result = evaluate_case(
                case,
                http_client=http_client,
                bedrock_client=bedrock_client,
                api_url=args.api_url,
                simulator_model_id=args.simulator_model_id,
                max_turns=args.max_turns,
            )
            results.append(result)
            append_jsonl(results_path, result)
            mark = "OK" if result["correct"] else "NG"
            print(
                f"[{index}/{len(cases)}] {mark} {case['query']} "
                f"expected={case['expected']['category_code']} "
                f"actual={result.get('predicted_category_code')} "
                f"turns={result['clarification_count']}"
            )
            if index < len(cases) and args.delay:
                time.sleep(args.delay)

    report = build_report(results)
    report.update(
        {
            "created_at": datetime.now(UTC).isoformat(),
            "split": args.split,
            "api_url": args.api_url,
            "simulator_model_id": args.simulator_model_id,
        }
    )
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(
        render_markdown(report, results), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {output_dir / 'report.md'}")


if __name__ == "__main__":
    main()
