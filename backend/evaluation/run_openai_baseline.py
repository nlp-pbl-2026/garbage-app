"""OpenAI(ChatGPT)単体を、実際の利用シーンに近い形で評価する比較ベースライン。

利用者が普通にChatGPTへ聞く自然文（「愛媛県松山市において『X』は何ゴミ？」）を投げ、
返ってきた自由文の回答を、事後的に9分類コードへLLMでマッピングして採点する。
RAG検索は使わない「素のLLMに聞いた場合」の性能を測る。

    export OPENAI_API_KEY=sk-...   # または backend/.env に記載
    uv run python -m evaluation.run_openai_baseline --model gpt-5.6-sol --reasoning-effort middle
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import UTC, datetime
from pathlib import Path

from openai import OpenAI

from evaluation.common import VALID_CATEGORIES, extract_json, read_jsonl
from evaluation.run_evaluation import build_report, render_markdown

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_DIR = BACKEND_ROOT / "evaluation/artifacts/dataset"
DEFAULT_RUNS_DIR = BACKEND_ROOT / "evaluation/artifacts/runs"
# データ不良として比較から除外するケース。
DEFAULT_EXCLUDE = ("item_0188",)

CATEGORY_GUIDE = """\
分類コードと対象の目安（松山市）:
- 可燃: 可燃ごみ。紙くず・木・布・革・ゴム、プラスチック製の「製品」（おもちゃ・造花等）など燃やせるもの。
- 埋立: 埋立ごみ。陶器・ガラス製食器・土・砂・粘土・石など、燃えず金属でもないもの。
- 金・ガ: 金物・ガラス類。金属製品・刃物・包丁・工具・ガラス製品など。
- 紙類: 新聞・雑誌・段ボール・紙パック・紙製の箱や容器など資源の紙。
- ペット: ペットボトル（PETマークのある飲料等のボトル）。
- プラ: プラスチック製容器包装（プラマークのある容器・包装。商品を包んでいたもの）。
- 水銀: 水銀を使う品（蛍光管・水銀体温計・水銀血圧計・ハロゲンランプ等）。
- 粗大: 粗大ごみ。指定ごみ袋に入らない大型のもの・家具・家電など。
- 禁止: 市が収集しないもの。ピアノ・消火器・タイヤ・バッテリー・電池・農機具など（販売店/専門業者へ）。
"""


def natural_question_prompt(query: str) -> str:
    """実際の利用者がChatGPTへ聞くような自然文。分類コードもJSONも指定しない。"""

    return f"愛媛県松山市において、「{query}」は何ゴミに分類されますか？"


def judge_prompt(query: str, answer_text: str) -> str:
    """ChatGPTの自由文回答を、松山市の9分類コードへ事後マッピングする判定器用。"""

    return f"""
次の文章は、松山市のごみ分別に関する質問への回答です。この回答が実質的に指している
分別区分を、下記の分類コードから1つだけ選んでください。回答が曖昧・複数区分に言及する
場合は、最も主要に推している区分を選びます。回答の言葉を分類コードへ翻訳するだけで、
あなた自身の分別知識で上書きしないでください。

{CATEGORY_GUIDE}

対象の品物（利用者の入力）: {query}
回答文:
{answer_text}

次のJSONだけを返してください。
{{"category_code":"上記のいずれか1つ"}}
""".strip()


def load_env_key() -> None:
    if os.getenv("OPENAI_API_KEY"):
        return
    env_path = BACKEND_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def call_with_retry(fn, *, retries: int = 6, base: float = 5.0):
    """OpenAIのレート制限(429 rate)を指数バックオフで再試行する。

    残高不足(insufficient_quota)は再試行しても無意味なので即座に投げる。
    """

    for attempt in range(retries):
        try:
            return fn()
        except Exception as error:  # noqa: BLE001 - 型に依らずメッセージで判定
            message = str(error)
            retryable = (
                type(error).__name__
                in ("RateLimitError", "APITimeoutError", "InternalServerError", "APIError")
                and "insufficient_quota" not in message
                and "credit" not in message.lower()
            )
            if not retryable or attempt == retries - 1:
                raise
            time.sleep(base * (2**attempt) + random.uniform(0, 1.5))


def ask_chatgpt(
    client: OpenAI,
    model: str,
    query: str,
    reasoning_effort: str | None,
    web_search: bool = False,
) -> str:
    """自然文で質問し、ChatGPTの自由文回答をそのまま返す。

    web_search=True のときは Responses API の web_search ツールを使い、
    Web上の情報（松山市公式ページ等）を参照させる。
    """

    prompt = natural_question_prompt(query)
    if web_search:
        kwargs: dict = {
            "model": model,
            "tools": [{"type": "web_search"}],
            "input": prompt,
        }
        if reasoning_effort:
            kwargs["reasoning"] = {"effort": reasoning_effort}
        response = call_with_retry(lambda: client.responses.create(**kwargs))
        return response.output_text or ""

    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if reasoning_effort:
        # reasoningモデル(gpt-5.x, o系)はtemperature非対応でreasoning_effortを使う。
        kwargs["reasoning_effort"] = reasoning_effort
    else:
        kwargs["temperature"] = 0
    response = call_with_retry(lambda: client.chat.completions.create(**kwargs))
    return response.choices[0].message.content or ""


def judge_category(client: OpenAI, judge_model: str, query: str, answer_text: str) -> str:
    """自由文回答を9分類コードへマッピング（事後判定）。temperature0で決定的に。"""

    response = call_with_retry(
        lambda: client.chat.completions.create(
            model=judge_model,
            messages=[{"role": "user", "content": judge_prompt(query, answer_text)}],
            temperature=0,
        )
    )
    payload = extract_json(response.choices[0].message.content or "")
    code = str(payload.get("category_code", "")).strip()
    return code if code in VALID_CATEGORIES else ""


def evaluate_case(
    client: OpenAI,
    model: str,
    judge_model: str,
    case: dict,
    reasoning_effort: str | None,
    web_search: bool = False,
) -> dict:
    expected = case["expected"]["category_code"]
    started = time.monotonic()
    try:
        answer_text = ask_chatgpt(
            client, model, case["query"], reasoning_effort, web_search
        )
        predicted = judge_category(client, judge_model, case["query"], answer_text)
        correct = predicted == expected
        return {
            "case_id": case["case_id"],
            "split": case.get("split"),
            "query": case["query"],
            "ambiguity_type": case.get("ambiguity_type"),
            "expected": case["expected"],
            "predicted_category_code": predicted or None,
            "predicted_item": None,
            "confidence": None,
            "final_status": "answered" if predicted else "unresolved",
            "outcome": "correct" if correct else "wrong_category",
            "correct": correct,
            "clarification_count": 0,
            "clarifications": [],
            "chatgpt_answer": answer_text,
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
            "clarification_count": 0,
            "clarifications": [],
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
            "error": f"{type(error).__name__}: {error}",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "test"), default="test")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument(
        "--reasoning-effort",
        default=os.getenv("OPENAI_REASONING_EFFORT"),
        help="reasoningモデルの推論強度(minimal|low|medium|high)。middleはmediumに正規化。",
    )
    parser.add_argument(
        "--judge-model",
        default=os.getenv("OPENAI_JUDGE_MODEL", "gpt-4o-mini"),
        help="自由文回答を分類コードへ事後マッピングする判定モデル。",
    )
    parser.add_argument(
        "--web-search",
        action="store_true",
        help="Responses APIのweb_searchツールでWeb上の情報を参照させる。",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=list(DEFAULT_EXCLUDE),
        help="採点から除外するcase_id（データ不良など）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_key()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY が未設定です。環境変数か backend/.env に設定してください。"
        )
    cases = read_jsonl(args.dataset_dir / f"{args.split}.jsonl")
    excluded = set(args.exclude)
    cases = [c for c in cases if c["case_id"] not in excluded]
    if args.limit > 0:
        cases = cases[: args.limit]

    effort = args.reasoning_effort
    if effort and effort.lower() == "middle":
        effort = "medium"

    client = OpenAI()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_model = args.model.replace("/", "_")
    suffix = "-websearch" if args.web_search else ""
    output_dir = (
        args.output_dir
        or DEFAULT_RUNS_DIR / f"openai-{safe_model}{suffix}-{timestamp}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for index, case in enumerate(cases, start=1):
        result = evaluate_case(
            client, args.model, args.judge_model, case, effort, args.web_search
        )
        results.append(result)
        mark = "OK" if result["correct"] else "NG"
        print(
            f"[{index}/{len(cases)}] {mark} {case['query'][:40]} "
            f"exp={case['expected']['category_code']} "
            f"got={result.get('predicted_category_code')}"
        )
        if index < len(cases) and args.delay:
            time.sleep(args.delay)

    report = build_report(results)
    report.update(
        {
            "created_at": datetime.now(UTC).isoformat(),
            "split": args.split,
            "provider": "openai",
            "model": args.model,
            "judge_model": args.judge_model,
            "reasoning_effort": effort,
            "web_search": args.web_search,
            "excluded_case_ids": sorted(excluded),
            "note": (
                "自然文でChatGPTに質問→自由文回答を事後的に分類コードへLLMマッピング。"
                "RAGなし・追加質問なし。"
            ),
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
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {output_dir / 'report.md'}")


if __name__ == "__main__":
    main()
