"""事前計算した品目Embeddingとクエリのコサイン類似度で検索する。

マネージドKnowledge Baseのチャンク分割（1チャンクに複数品目が混ざる問題）を
避け、1品目=1ベクトルの自前インデックスで曖昧クエリを意味検索する。
インデックスは build_item_embeddings.py が生成する .npz。
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

import boto3
import numpy as np
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from .. import config
from .item_search_service import ItemMatch

logger = logging.getLogger(__name__)


class EmbeddingSearchService:
    """クエリEmbeddingと品目Embeddingのコサイン類似度で上位k件を返す。"""

    def __init__(
        self,
        embeddings_path: Path | None = None,
        items_path: Path | None = None,
        runtime_client=None,
        model_id: str | None = None,
        dimensions: int | None = None,
    ):
        self._embeddings_path = embeddings_path or self._detect_path(
            config.EMBEDDING_INDEX_PATH,
            "data/regions/matsuyama/common/knowledge/item_embeddings.npz",
        )
        self._items_path = items_path or self._detect_path(
            config.KNOWLEDGE_ITEMS_PATH,
            "data/regions/matsuyama/common/knowledge/items.csv",
        )
        self._model_id = model_id or config.BEDROCK_EMBEDDING_MODEL_ID
        self._dimensions = dimensions or config.EMBEDDING_DIMENSIONS
        self._runtime = runtime_client
        self._vectors: np.ndarray | None = None
        self._item_ids: list[str] = []
        self._meta: dict[str, dict[str, str]] = {}
        self._load_index()

    @staticmethod
    def _detect_path(configured: str, relative: str) -> Path:
        if configured:
            return Path(configured)
        relative_path = Path(relative)
        candidates = [
            Path(__file__).resolve().parents[3] / relative_path,
            Path(__file__).resolve().parents[2] / relative_path,
        ]
        return next((path for path in candidates if path.exists()), candidates[0])

    def _load_index(self) -> None:
        if not self._embeddings_path.exists():
            logger.warning(
                "Embedding index not found at %s; embedding search disabled",
                self._embeddings_path,
            )
            return
        data = np.load(self._embeddings_path, allow_pickle=False)
        self._vectors = data["vectors"].astype(np.float32)
        self._item_ids = [str(value) for value in data["item_ids"].tolist()]
        if "model_id" in data:
            self._model_id = str(data["model_id"])
        if "dimensions" in data:
            self._dimensions = int(data["dimensions"])
        self._meta = self._load_items_metadata()

    def _load_items_metadata(self) -> dict[str, dict[str, str]]:
        if not self._items_path.exists():
            return {}
        with self._items_path.open(encoding="utf-8-sig", newline="") as file:
            return {
                row["item_id"]: row
                for row in csv.DictReader(file)
                if row.get("item_id")
            }

    @property
    def is_ready(self) -> bool:
        return self._vectors is not None and len(self._item_ids) > 0

    def _client(self):
        if self._runtime is None:
            self._runtime = boto3.client(
                "bedrock-runtime", region_name=config.AWS_REGION
            )
        return self._runtime

    def _embed_query(self, query: str) -> np.ndarray | None:
        try:
            response = self._client().invoke_model(
                modelId=self._model_id,
                body=json.dumps(
                    {
                        "inputText": query,
                        "dimensions": self._dimensions,
                        "normalize": True,
                    }
                ),
            )
            vector = json.loads(response["body"].read())["embedding"]
        except (BotoCoreError, ClientError, NoCredentialsError, KeyError, ValueError) as error:
            logger.warning("Query embedding failed: %s", error)
            return None
        array = np.asarray(vector, dtype=np.float32)
        norm = np.linalg.norm(array)
        if norm == 0:
            return None
        return array / norm

    def search(self, query: str, *, limit: int | None = None) -> list[ItemMatch]:
        if not self.is_ready or not query.strip():
            return []
        limit = limit or config.EMBEDDING_SEARCH_TOP_K
        query_vector = self._embed_query(query)
        if query_vector is None:
            return []
        assert self._vectors is not None
        # ベクトルは正規化済みなので内積がコサイン類似度に一致する。
        scores = self._vectors @ query_vector
        top_count = min(limit, scores.shape[0])
        # 部分ソートで上位候補だけ抽出してから厳密に並べ替える。
        top_indices = np.argpartition(-scores, top_count - 1)[:top_count]
        top_indices = top_indices[np.argsort(-scores[top_indices])]

        matches: list[ItemMatch] = []
        for index in top_indices:
            score = float(scores[index])
            if score < config.EMBEDDING_SEARCH_MIN_SCORE:
                continue
            item_id = self._item_ids[index]
            row = self._meta.get(item_id, {})
            matches.append(
                ItemMatch(
                    item_id=item_id,
                    item=row.get("item", ""),
                    category=row.get("category", ""),
                    category_display=row.get("category_display", ""),
                    note=row.get("note", ""),
                    score=score,
                    ranking_score=score,
                )
            )
        return matches
