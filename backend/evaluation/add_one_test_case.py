"""不良ケースを除外しつつ、新規のtestケースを指定件数ぶん生成して追記する。

seedはmanifestと同じ。testの層化分割からbalanced_order順に、既存test.jsonlに
未使用かつ除外対象でない品目を選び、品質ゲート付きで生成して追記する。

    uv run python -m evaluation.add_one_test_case --count 20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import boto3

from evaluation.build_dataset import (
    DEFAULT_SOURCE,
    balanced_order,
    generate_case,
    load_items,
    stratified_split,
)
from evaluation.common import DEFAULT_MODEL_ID, DEFAULT_REGION

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_PATH = BACKEND_ROOT / "evaluation/artifacts/dataset/test.jsonl"
SEED = 20260901
TEST_RATIO = 0.2
REMOVE_IDS = {"item_0188"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1, help="追加する新規ケース数")
    args = parser.parse_args()

    existing = [
        json.loads(l)
        for l in TEST_PATH.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    kept = [c for c in existing if c["case_id"] not in REMOVE_IDS]
    used_ids = {c["case_id"] for c in kept}
    print(f"既存 {len(existing)}件 → 除外後 {len(kept)}件、目標 +{args.count}件")

    rows = load_items(DEFAULT_SOURCE)
    splits = stratified_split(rows, test_ratio=TEST_RATIO, seed=SEED)
    candidates = balanced_order(splits["test"], seed=SEED + len("test"))

    client = boto3.client("bedrock-runtime", region_name=DEFAULT_REGION)
    added = 0
    for row in candidates:
        if added >= args.count:
            break
        if row["item_id"] in used_ids or row["item_id"] in REMOVE_IDS:
            continue
        try:
            case = generate_case(client, row, all_rows=rows, model_id=DEFAULT_MODEL_ID)
        except (ValueError, json.JSONDecodeError) as error:
            print(f"skip {row['item_id']} {row['item']}: {error}")
            continue
        case["split"] = "test"
        kept.append(case)
        used_ids.add(row["item_id"])
        added += 1
        print(f"[{added}/{args.count}] 追加: {row['item']} -> {case['query']}")

    if added < args.count:
        print(f"注意: 目標{args.count}件に対し{added}件のみ追加できました")

    with TEST_PATH.open("w", encoding="utf-8") as file:
        for c in kept:
            file.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"最終 test 件数: {len(kept)}")


if __name__ == "__main__":
    main()
