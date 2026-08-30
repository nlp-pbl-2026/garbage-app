"""松山市品目辞典から、曖昧検索のtrain/testデータを生成する。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3

from evaluation.common import (
    DEFAULT_MODEL_ID,
    DEFAULT_REGION,
    VALID_CATEGORIES,
    converse_json,
    write_jsonl,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_SOURCE = (
    PROJECT_ROOT / "data/regions/matsuyama/common/knowledge/items.csv"
)
DEFAULT_OUTPUT = BACKEND_ROOT / "evaluation/artifacts/dataset"


def load_items(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return [
        row
        for row in rows
        if row.get("item_id")
        and row.get("item")
        and row.get("category") in VALID_CATEGORIES
    ]


def stable_score(item_id: str, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{item_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def stratified_split(
    rows: list[dict[str, str]], *, test_ratio: float, seed: int
) -> dict[str, list[dict[str, str]]]:
    """同じ品目が両方へ入らない、カテゴリ層化の固定分割。"""

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)

    result: dict[str, list[dict[str, str]]] = {"train": [], "test": []}
    for category_rows in grouped.values():
        ordered = sorted(
            category_rows, key=lambda row: stable_score(row["item_id"], seed)
        )
        test_count = max(1, round(len(ordered) * test_ratio))
        result["test"].extend(ordered[:test_count])
        result["train"].extend(ordered[test_count:])

    for split in result:
        result[split].sort(key=lambda row: stable_score(row["item_id"], seed + 1))
    return result


def balanced_order(
    rows: list[dict[str, str]], *, seed: int
) -> list[dict[str, str]]:
    """全候補をカテゴリ横断のラウンドロビン順に並べる。

    先頭からlimit件を採る通常運用ではカテゴリ均衡になり、生成に失敗した
    品目を飛ばして後続へ補充してもカテゴリ偏りが最小になる。
    """

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)
    rng = random.Random(seed)
    for values in grouped.values():
        rng.shuffle(values)
    categories = sorted(grouped)
    ordered: list[dict[str, str]] = []
    while categories:
        next_categories: list[str] = []
        for category in categories:
            values = grouped[category]
            if values:
                ordered.append(values.pop())
            if values:
                next_categories.append(category)
        categories = next_categories
    return ordered


def normalize_item_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[\s\W_]+", "", value)


def item_name_similarity(left: str, right: str) -> float:
    left_value = normalize_item_name(left)
    right_value = normalize_item_name(right)
    left_grams = {
        left_value[index : index + 2] for index in range(len(left_value) - 1)
    }
    right_grams = {
        right_value[index : index + 2] for index in range(len(right_value) - 1)
    }
    if not left_grams or not right_grams:
        return 0.0
    return len(left_grams & right_grams) / len(left_grams | right_grams)


def recognition_candidates(
    expected: dict[str, str], rows: list[dict[str, str]], *, limit: int = 8
) -> list[dict[str, str]]:
    """正解と名前が近い難しい選択肢を作り、生成文の往復同定に使う。"""

    distractors = sorted(
        (row for row in rows if row["item_id"] != expected["item_id"]),
        key=lambda row: (
            -item_name_similarity(expected["item"], row["item"]),
            row["item_id"],
        ),
    )[: max(0, limit - 1)]
    candidates = [expected, *distractors]
    return sorted(
        candidates,
        key=lambda row: stable_score(row["item_id"], 20260830),
    )


def generation_prompt(row: dict[str, str], feedback: str = "") -> str:
    return f"""
あなたは松山市のごみ分別検索を評価するデータ作成者です。
次の正解品目について、一般利用者が名前を思い出せない場面の短い検索文を1件作ってください。

正解品目: {row['item']}
読み: {row.get('reading') or 'なし'}
正解分類コード: {row['category']}
正解分類名: {row.get('category_display') or ''}
条件・出し方: {row.get('note') or 'なし'}

要件:
- 正式な品目名をそのまま質問文に書かず、用途、形、使う場面、見た目などで曖昧に表現する。
- ただし無関係な物にも広く当てはまる一語だけにはしない。
- 素材や大きさ等で分類が分岐する品目では、正解分類と矛盾しない具体的な実物を想定する。
- 分類に必要な条件をあえて一部省略してよい。システムから聞かれたら回答できるよう、
  hidden_contextには想定した実物の素材、大きさ、用途、状態、表示などを明記する。
- 正解が容器、箱、ふた、芯、電球などの部品である場合、その部品だけを捨てる状況にする。
  製品本体や器具全体を捨てるように読めるqueryやhidden_contextにしない。
- PET、プラマーク、素材、袋に入る大きさなどが分類の決め手なら、hidden_contextへ必ず明記する。
- 元資料にない用途や中身を作らない。よく知らない品目を別の薬品・製品に置き換えない。
- hidden_contextに分類コードや正解ラベルそのものは書かない。
- 松山市、ごみ、捨て方、分別など、検索意図を直接説明する語はqueryへ入れない。
- 日本語として自然な、利用者が実際に入力しそうな表現にする。
{f'- 前回の品質確認での問題: {feedback}' if feedback else ''}

次のJSONだけを返してください。
{{
  "query": "曖昧な検索文",
  "hidden_context": "追加質問へ答えるための具体的な実物設定",
  "ambiguity_type": "用途表現|外見表現|使用場面|俗称|機能表現|その他"
}}
""".strip()


def blind_recognition_prompt(
    generated: dict[str, Any], candidates: list[dict[str, str]]
) -> str:
    candidate_text = "\n".join(
        f"- {candidate['item_id']}: {candidate['item']}" for candidate in candidates
    )
    return f"""
次の利用者入力と実物設定が、具体的に何を指すか推定してください。
正解は候補のいずれかです。分類名ではなく、捨てる対象そのものを選んでください。

利用者入力: {generated.get('query') or ''}
実物の設定: {generated.get('hidden_context') or ''}

製品本体ではなく箱・容器・ふた・芯・電球などの部品を捨てている場合は、
その部品まで含めた具体名を答えてください。

候補:
{candidate_text}

次のJSONだけを返してください。
{{"selected_item_id":"選んだitem_id","inferred_item":"推定した具体的な品目","reason":"推定理由"}}
""".strip()


def quality_prompt(
    row: dict[str, str],
    generated: dict[str, Any],
    blind_recognition: dict[str, Any],
) -> str:
    return f"""
あなたはごみ分別評価データの厳格なレビュアーです。

正解品目: {row['item']}
正解分類コード: {row['category']}
資料上の条件・出し方: {row.get('note') or 'なし'}
生成query: {generated.get('query') or ''}
生成hidden_context: {generated.get('hidden_context') or ''}
正解を見ない別モデルが推定した品目: {blind_recognition.get('inferred_item') or ''}
その推定理由: {blind_recognition.get('reason') or ''}

次の全条件を満たす場合だけvalid=trueにしてください。
1. queryが指す実物は正解品目として自然で、別品目へ置き換わっていない。
   正解を見ない推定結果が別品目なら、原則としてinvalidにする。
2. 箱・容器・ふた・芯・電球等が正解なら、製品本体や器具全体ではなくその部品を捨てている。
3. hidden_contextはqueryと矛盾せず、素材・表示・大きさ等の追加質問に正解品目として答えられる。
4. 正解分類を決める条件がhidden_contextにあり、別分類へ分岐する実物設定ではない。
5. queryは正式品目名の単純な言い換えではなく、用途・外見・使用場面等による曖昧表現である。
6. queryだけでは不足する情報があっても、適切な追加質問によって正解へ到達できる。

次のJSONだけを返してください。
{{"valid":true,"reason":"判定理由"}}
""".strip()


def generate_case(
    client,
    row: dict[str, str],
    *,
    all_rows: list[dict[str, str]],
    model_id: str,
) -> dict[str, Any]:
    feedback = ""
    generated: dict[str, Any] = {}
    blind_recognition: dict[str, Any] = {}
    review: dict[str, Any] = {}
    candidates = recognition_candidates(row, all_rows)
    for _ in range(3):
        try:
            generated = converse_json(
                client,
                model_id=model_id,
                prompt=generation_prompt(row, feedback),
                max_tokens=450,
                temperature=0.7,
            )
            blind_recognition = converse_json(
                client,
                model_id=model_id,
                prompt=blind_recognition_prompt(generated, candidates),
                max_tokens=220,
                temperature=0.0,
            )
            if blind_recognition.get("selected_item_id") != row["item_id"]:
                feedback = (
                    "正解を伏せた往復確認で別品目が選ばれた: "
                    f"{blind_recognition.get('inferred_item') or '不明'}"
                )
                continue
            review = converse_json(
                client,
                model_id=model_id,
                prompt=quality_prompt(row, generated, blind_recognition),
                max_tokens=220,
                temperature=0.0,
            )
        except (ValueError, json.JSONDecodeError) as error:
            feedback = f"JSON生成または品質確認に失敗: {error}"
            continue
        if review.get("valid") is True:
            break
        feedback = str(review.get("reason") or "正解品目との対応が不十分")
    else:
        raise ValueError(
            f"品質条件を満たす曖昧クエリを生成できません: "
            f"{row['item_id']} {feedback}"
        )

    query = str(generated.get("query", "")).strip()
    hidden_context = str(generated.get("hidden_context", "")).strip()
    if not query or not hidden_context:
        raise ValueError(f"生成データが不完全です: {row['item_id']}")
    return {
        "case_id": row["item_id"],
        "query": query,
        "hidden_context": hidden_context,
        "ambiguity_type": str(generated.get("ambiguity_type", "その他")),
        "quality_review": str(review.get("reason", "")),
        "blind_inferred_item": str(blind_recognition.get("inferred_item", "")),
        "expected": {
            "item_id": row["item_id"],
            "item": row["item"],
            "category_code": row["category"],
            "category_name": row.get("category_display", ""),
            "note": row.get("note", ""),
        },
        "source": {
            "section": row.get("source_section", ""),
            "pdf_page": row.get("source_pdf_page", ""),
            "printed_page": row.get("source_printed_page", ""),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--train-limit", type=int, default=90)
    parser.add_argument("--test-limit", type=int, default=45)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument(
        "--model-id", default=os.getenv("EVAL_GENERATOR_MODEL_ID", DEFAULT_MODEL_ID)
    )
    parser.add_argument("--region", default=os.getenv("AWS_REGION", DEFAULT_REGION))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_items(args.source)
    splits = stratified_split(rows, test_ratio=args.test_ratio, seed=args.seed)
    client = boto3.client("bedrock-runtime", region_name=args.region)
    generated_counts: dict[str, int] = {}

    skipped_counts: dict[str, int] = {}
    for split, limit in (("train", args.train_limit), ("test", args.test_limit)):
        candidates = balanced_order(splits[split], seed=args.seed + len(split))
        target = limit if limit > 0 else len(candidates)
        cases: list[dict[str, Any]] = []
        skipped = 0
        for row in candidates:
            if len(cases) >= target:
                break
            # 1品目が品質ゲートを通らなくても全体を止めず、次の候補で補充する。
            try:
                case = generate_case(
                    client,
                    row,
                    all_rows=rows,
                    model_id=args.model_id,
                )
            except (ValueError, json.JSONDecodeError) as error:
                skipped += 1
                print(f"[{split} skip] {row['item_id']} {row['item']}: {error}")
                continue
            case["split"] = split
            cases.append(case)
            if split == "train":
                print(f"[{split} {len(cases)}/{target}] {row['item']} -> {case['query']}")
            else:
                print(f"[{split} {len(cases)}/{target}] generated {row['item_id']}")
        if len(cases) < target:
            print(
                f"[{split}] 目標{target}件に対し{len(cases)}件のみ生成"
                f"（候補{len(candidates)}件、スキップ{skipped}件）"
            )
        write_jsonl(args.output_dir / f"{split}.jsonl", cases)
        generated_counts[split] = len(cases)
        skipped_counts[split] = skipped

    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "municipality": "松山市",
        "generator_model_id": args.model_id,
        "seed": args.seed,
        "test_ratio": args.test_ratio,
        "source_path": str(args.source.relative_to(PROJECT_ROOT)),
        "source_reference": (
            "松山市『ごみ分別はやわかり帳（家庭用）』ごみ分別辞典"
        ),
        "counts": generated_counts,
        "skipped": skipped_counts,
        "note": "生成データはGit追跡外。testは最終評価まで改善判断に使用しない。",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
