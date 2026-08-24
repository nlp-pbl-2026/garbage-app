"""検索結果を分析可能な構造で保存・集計する。"""

import json
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr

from .. import config

logger = logging.getLogger(__name__)
_file_lock = Lock()


class SearchLogService:
    """DynamoDBまたはローカルJSONLへ検索イベントを保存する。"""

    def __init__(self, table=None, file_path: Path | None = None):
        self._table = table
        if self._table is None and config.SEARCH_LOG_TABLE:
            self._table = boto3.resource(
                "dynamodb", region_name=config.AWS_REGION
            ).Table(config.SEARCH_LOG_TABLE)
        self._file_path = file_path or Path(config.SEARCH_LOG_FILE)

    def record(self, event: dict[str, Any]) -> None:
        event = dict(event)
        event["expires_at"] = int(
            (
                datetime.now(UTC)
                + timedelta(days=config.SEARCH_LOG_RETENTION_DAYS)
            ).timestamp()
        )
        logger.info("search_event=%s", json.dumps(event, ensure_ascii=False))
        try:
            if self._table is not None:
                self._table.put_item(
                    Item=json.loads(json.dumps(event), parse_float=Decimal)
                )
                return
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with _file_lock, self._file_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            # 分析ログ障害で利用者向け検索を失敗させない。
            logger.exception("Failed to persist search analytics event")

    def list_recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if self._table is not None:
            items = []
            scan_options: dict[str, Any] = {
                "Limit": min(limit, 100),
                "FilterExpression": Attr("event_type").eq("search"),
            }
            while len(items) < limit:
                response = self._table.scan(**scan_options)
                items.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                scan_options["ExclusiveStartKey"] = last_key
        elif self._file_path.exists():
            with _file_lock, self._file_path.open(encoding="utf-8") as stream:
                items = [json.loads(line) for line in stream if line.strip()]
        else:
            items = []
        return sorted(
            items,
            key=lambda item: str(item.get("created_at", "")),
            reverse=True,
        )[:limit]

    def summary(self, *, limit: int = 500) -> dict[str, Any]:
        items = self.list_recent(limit=limit)
        categories = Counter(
            str(item["category_name"])
            for item in items
            if item.get("category_name")
        )
        answered = sum(item.get("status") == "answered" for item in items)
        confidences = [
            float(item["confidence"])
            for item in items
            if item.get("confidence") is not None
        ]
        durations = [float(item.get("duration_ms", 0)) for item in items]
        return {
            "total_searches": len(items),
            "answered_count": answered,
            "clarification_count": len(items) - answered,
            "average_confidence": (
                sum(confidences) / len(confidences) if confidences else None
            ),
            "average_duration_ms": (
                sum(durations) / len(durations) if durations else None
            ),
            "categories": dict(categories.most_common()),
            "recent": items[:50],
        }
