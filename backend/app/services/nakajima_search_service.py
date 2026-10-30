"""Search only the explicitly documented examples and rules for Nakajima."""

import csv
from pathlib import Path
import re
import unicodedata

from .. import config


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).lower()


_OFFICIAL_EXAMPLE_STEMS = {"家具類": "家具"}


class NakajimaSearchService:
    def __init__(self, path: Path | None = None):
        relative = Path("data/regions/matsuyama/generated/nakajima_items.csv")
        candidates = [Path(__file__).resolve().parents[level] / relative for level in (3, 2)]
        default = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
        self.path = path or Path(config.NAKAJIMA_ITEMS_PATH or default)
        if not self.path.exists():
            raise FileNotFoundError(f"Verified Nakajima evidence is missing: {self.path}")
        with self.path.open(encoding="utf-8", newline="") as stream:
            self.rows = list(csv.DictReader(stream))

    def search(self, query: str) -> list[dict]:
        words = [_norm(word) for word in re.findall(r"[\w一-龥ぁ-んァ-ンー・]+", query) if len(word) > 1]
        normalized_query = _norm(query)
        ranked = []
        for row in self.rows:
            name = _norm(row["item"])
            if row["item"] == "家具類" and "スプリングマットレス" in normalized_query:
                # The same official calendar explicitly excludes this item.
                continue
            if row["item_id"].startswith("nk-rule-"):
                # A broad category section is not evidence for an unrelated item.
                code = _norm(row["category"])
                score = .8 if (name in normalized_query or
                                 (len(code) >= 2 and code in normalized_query)) else 0
            else:
                # The official example is "家具類"; ordinary queries say "家具".
                # Keep this alias specific to that verified example so broad
                # suffix stripping cannot mislabel unrelated plastic "ネット類".
                stem = _OFFICIAL_EXAMPLE_STEMS.get(row["item"], "")
                score = (1.0 if name in normalized_query else
                         .9 if stem and stem in normalized_query else
                         sum(.15 for word in words if word in name))
            if score:
                ranked.append((min(score, 1.0), row))
        ranked.sort(key=lambda item: (-item[0], item[1]["item_id"]))
        return [row | {"score": score} for score, row in ranked[:config.RAG_TOP_K]]
