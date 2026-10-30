#!/usr/bin/env python3
"""Count FY2026 Nakajima rule eligibility without Bedrock or file writes.

An eligible dictionary row is not a successful search or a confirmed answer:
retrieval rank, user-supplied conditions and classification remain separate.
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.item_search_service import ItemMatch  # noqa: E402
from app.services.nakajima_rule_service import resolve_shared_item  # noqa: E402


def main() -> None:
    source = ROOT / "data/regions/matsuyama/common/knowledge/items.csv"
    with source.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    counts: Counter[str] = Counter()
    for row in rows:
        match = ItemMatch(
            item_id=row["item_id"], item=row["item"],
            category=row["category"], category_display=row["category_display"],
            note=row["note"], score=0,
        )
        result = resolve_shared_item(match)
        counts[result.status] += 1
    print(json.dumps({
        "catalog_rows": len(rows),
        "eligible_for_regional_evidence": counts["common_rule"] + counts["split_rule"],
        "needs_condition_or_source_review": counts["conditional"] + counts["unverified"],
        "by_status": dict(counts),
        "caution": "Eligibility is not a count of successful user queries or item-by-item official confirmation.",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
