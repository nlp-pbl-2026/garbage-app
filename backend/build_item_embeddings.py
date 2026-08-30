"""松山市品目辞典の各行を事前にEmbedding化し、ベクトル配列を保存する。

マネージドKnowledge Baseのチャンク分割に依存せず、1品目=1ベクトルの
自前インデックスを作る。実行時はクエリだけをEmbeddingし、コサイン類似度で
上位k件を返す（EmbeddingSearchService）。items.csvを更新したら再実行する。

    uv run python build_item_embeddings.py
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import boto3
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_SOURCE = PROJECT_ROOT / "data/regions/matsuyama/common/knowledge/items.csv"
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "data/regions/matsuyama/common/knowledge/item_embeddings.npz"
)
DEFAULT_MODEL_ID = "amazon.titan-embed-text-v2:0"
DEFAULT_DIMENSIONS = 1024
DEFAULT_REGION = "ap-northeast-1"


def embed_text(client, text: str, *, model_id: str, dimensions: int) -> list[float]:
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(
            {"inputText": text, "dimensions": dimensions, "normalize": True}
        ),
    )
    return json.loads(response["body"].read())["embedding"]


def build_document(row: dict[str, str]) -> str:
    """Embedding対象の文字列。品目名・読み・注意書きを結合し検索語面を広げる。"""

    parts = [
        row.get("item", "").strip(),
        row.get("reading", "").strip(),
        row.get("search_text", "").strip(),
        row.get("note", "").strip(),
    ]
    # 重複を除きつつ順序を保つ。
    seen: dict[str, None] = {}
    for part in parts:
        if part and part not in seen:
            seen[part] = None
    return "。".join(seen)


def load_items(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return [row for row in rows if row.get("item_id") and row.get("item")]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--dimensions", type=int, default=DEFAULT_DIMENSIONS)
    parser.add_argument("--region", default=DEFAULT_REGION)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_items(args.source)
    client = boto3.client("bedrock-runtime", region_name=args.region)

    item_ids: list[str] = []
    vectors: list[list[float]] = []
    for index, row in enumerate(rows, start=1):
        document = build_document(row)
        for attempt in range(3):
            try:
                vector = embed_text(
                    client,
                    document,
                    model_id=args.model_id,
                    dimensions=args.dimensions,
                )
                break
            except Exception as error:  # 一過性エラーは指数バックオフで再試行。
                if attempt == 2:
                    raise
                print(f"  retry {row['item_id']}: {error}")
                time.sleep(2**attempt)
        item_ids.append(row["item_id"])
        vectors.append(vector)
        if index % 100 == 0 or index == len(rows):
            print(f"[{index}/{len(rows)}] embedded")

    matrix = np.asarray(vectors, dtype=np.float32)
    # Titan側でnormalize=True済みだが、コサイン=内積を保証するため念のため再正規化。
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    matrix = matrix / norms

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        vectors=matrix,
        item_ids=np.asarray(item_ids),
        model_id=np.asarray(args.model_id),
        dimensions=np.asarray(args.dimensions),
    )
    print(
        f"saved {matrix.shape[0]} vectors x {matrix.shape[1]} dims -> "
        f"{args.output} ({args.output.stat().st_size / 1024:.0f} KiB)"
    )


if __name__ == "__main__":
    main()
