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


def analytics_event(event: dict[str, Any]) -> dict[str, Any]:
    """Keep research text and metrics for protected storage/admin reads only.

    Image payloads, credentials and unrelated fields are never retained.
    Existing records are not rewritten or deleted when read.
    """
    allowed = {
        "event_type",
        "request_id",
        "created_at",
        "municipality_id",
        "district_id",
        "query",
        "rewritten_query",
        "answer",
        "follow_up_question",
        "text_retained",
        "has_image",
        "image_media_type",
        "image_size_bytes",
        "status",
        "category_code",
        "category_name",
        "confidence",
        "next_collection_date",
        "rag_scores",
        "duration_ms",
        "expires_at",
    }
    result = {key: value for key, value in event.items() if key in allowed}
    if isinstance(event.get("clarifications"), list):
        result["clarifications"] = [
            {key: item[key] for key in ("question", "answer") if key in item}
            for item in event["clarifications"]
            if isinstance(item, dict)
        ]
    return result


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
        event = analytics_event(event)
        event["expires_at"] = int(
            (
                datetime.now(UTC) + timedelta(days=config.SEARCH_LOG_RETENTION_DAYS)
            ).timestamp()
        )
        try:
            if self._table is not None:
                self._table.put_item(
                    Item=json.loads(json.dumps(event), parse_float=Decimal)
                )
            else:
                self._file_path.parent.mkdir(parents=True, exist_ok=True)
                with _file_lock, self._file_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            # CloudWatch is operational logging, not a second copy of research text.
            logger.info("Search analytics event recorded")
        except Exception as error:
            # 分析ログ障害で利用者向け検索を失敗させない。
            # SDK/file errors may include request text; do not log their bodies.
            logger.error(
                "Failed to persist search analytics event (%s)", type(error).__name__
            )

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
            [analytics_event(item) for item in items],
            key=lambda item: str(item.get("created_at", "")),
            reverse=True,
        )[:limit]

    def summary(self, *, limit: int = 500) -> dict[str, Any]:
        items = self.list_recent(limit=limit)
        categories = Counter(
            str(item["category_name"]) for item in items if item.get("category_name")
        )
        answered = sum(item.get("status") == "answered" for item in items)
        unable = sum(item.get("status") == "unable_to_determine" for item in items)
        confidences = [
            float(item["confidence"])
            for item in items
            if item.get("confidence") is not None
        ]
        durations = [float(item.get("duration_ms", 0)) for item in items]
        return {
            "total_searches": len(items),
            "answered_count": answered,
            "clarification_count": sum(
                item.get("status") == "needs_clarification" for item in items
            ),
            "unable_count": unable,
            "average_confidence": (
                sum(confidences) / len(confidences) if confidences else None
            ),
            "average_duration_ms": (
                sum(durations) / len(durations) if durations else None
            ),
            "categories": dict(categories.most_common()),
            "recent": items[:50],
        }
