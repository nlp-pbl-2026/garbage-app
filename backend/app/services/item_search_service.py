"""構造化された品目辞典を、決定的な文字列類似度で検索する。"""

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .. import config


@dataclass(frozen=True)
class ItemMatch:
    item_id: str
    item: str
    category: str
    category_display: str
    note: str
    score: float

    @property
    def evidence_text(self) -> str:
        lines = [
            f"品目: {self.item}",
            f"分類コード: {self.category}",
            f"分類: {self.category_display}",
        ]
        if self.note:
            lines.append(f"出し方・注意: {self.note}")
        return "\n".join(lines)


class ItemSearchService:
    """CSVの各行を独立した品目として検索し、RAGの取りこぼしを補う。"""

    _ignored_phrases = (
        "松山市",
        "清水地区",
        "ごみ分別",
        "ゴミ分別",
        "分別データ",
        "分別",
        "品目",
        "素材",
        "大きさ",
        "用途",
        "汚れの状態",
        "これは何ごみ",
        "何ごみ",
    )

    def __init__(self, items_path: Path | None = None):
        configured = (
            Path(config.KNOWLEDGE_ITEMS_PATH) if config.KNOWLEDGE_ITEMS_PATH else None
        )
        relative_path = Path("data/regions/matsuyama/common/knowledge/items.csv")
        candidates = [
            Path(__file__).resolve().parents[3] / relative_path,
            Path(__file__).resolve().parents[2] / relative_path,
        ]
        detected = next((path for path in candidates if path.exists()), candidates[0])
        self._items_path = items_path or configured or detected
        self._items = self._load_items()

    def _load_items(self) -> list[dict[str, str]]:
        with self._items_path.open(encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))

    def search(self, query: str, *, limit: int = 5) -> list[ItemMatch]:
        normalized_query = self._normalize(query)
        if len(normalized_query) < 2:
            return []
        query_grams = self._bigrams(normalized_query)
        matches: list[ItemMatch] = []
        for row in self._items:
            item = row.get("item", "")
            searchable = " ".join(
                value
                for value in (item, row.get("note", ""), row.get("search_text", ""))
                if value
            )
            normalized_item = self._normalize(item)
            item_grams = self._bigrams(normalized_item)
            candidate_grams = self._bigrams(self._normalize(searchable))
            if not item_grams:
                continue
            item_overlap = len(query_grams & item_grams) / max(len(query_grams), 1)
            context_overlap = len(query_grams & candidate_grams) / max(
                len(query_grams), 1
            )
            containment_bonus = 0.35 if (
                normalized_item in normalized_query or normalized_query in normalized_item
            ) else 0.0
            # 品目名そのものの一致を重視し、備考だけに同じ素材語がある品目は
            # 上位へ出過ぎないようにする。
            score = (item_overlap * 0.85) + (context_overlap * 0.15)
            score += containment_bonus
            if "弁当" in normalized_query and "弁当" in normalized_item:
                score += 0.2
            if "ふた" in normalized_query and "ふた" in normalized_item:
                score += 0.08
            # 「弁当の透明なふた」は、通常は再利用する弁当箱ではなく
            # 使い捨ての弁当・惣菜容器の透明なふたを指す。弁当箱と容器が
            # 同点になると分類が不必要に曖昧になるため、用途・外見を使って
            # 地域資料内のより具体的な候補を優先する。
            if all(
                marker in normalized_query for marker in ("弁当", "透明", "ふた")
            ):
                if "容器" in normalized_item and row.get("category") == "プラ":
                    score += 0.35
                if "弁当箱" in normalized_item or "紙製" in normalized_item:
                    score -= 0.15
            score = min(score, 1.0)
            if score < config.LEXICAL_SEARCH_MIN_SCORE:
                continue
            matches.append(
                ItemMatch(
                    item_id=row.get("item_id", ""),
                    item=item,
                    category=row.get("category", ""),
                    category_display=row.get("category_display", ""),
                    note=row.get("note", ""),
                    score=score,
                )
            )
        matches.sort(key=lambda match: (-match.score, len(match.item), match.item_id))
        return matches[:limit]

    @classmethod
    def _normalize(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).lower()
        normalized = normalized.replace("フタ", "ふた").replace("蓋", "ふた")
        for phrase in cls._ignored_phrases:
            normalized = normalized.replace(phrase.lower(), "")
        normalized = re.sub(r"[\s\W_]+", "", normalized)
        return normalized.replace("の", "")

    @staticmethod
    def _bigrams(value: str) -> set[str]:
        return {value[index : index + 2] for index in range(len(value) - 1)}
