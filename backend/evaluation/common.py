"""評価データ生成と追加質問シミュレーションで共有する処理。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"
DEFAULT_REGION = "ap-northeast-1"
VALID_CATEGORIES = {
    "可燃",
    "埋立",
    "金・ガ",
    "紙類",
    "ペット",
    "プラ",
    "水銀",
    "粗大",
    "禁止",
}


def extract_json(text: str) -> dict[str, Any]:
    """モデル出力の前後に説明が混ざっても最初のJSON objectを取り出す。"""

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("モデル応答にJSON objectがありません")
    value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("モデル応答のJSONがobjectではありません")
    return value


def converse_json(
    client,
    *,
    model_id: str,
    prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.0,
) -> dict[str, Any]:
    """Bedrock Converse APIを呼び、JSON objectとして返す。"""

    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": temperature,
            "topP": 0.9,
        },
    )
    content = response.get("output", {}).get("message", {}).get("content", [])
    text = "".join(part.get("text", "") for part in content).strip()
    return extract_json(text)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")
