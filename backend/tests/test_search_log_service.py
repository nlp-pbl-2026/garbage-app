from decimal import Decimal

from app.services.search_log_service import SearchLogService


class FakeTable:
    def __init__(self, pages=None):
        self.pages = list(pages or [])
        self.put_items = []
        self.scan_calls = []

    def put_item(self, *, Item):
        self.put_items.append(Item)

    def scan(self, **kwargs):
        self.scan_calls.append(kwargs)
        return self.pages.pop(0)


def test_record_converts_float_for_dynamodb():
    table = FakeTable()
    service = SearchLogService(table=table)

    service.record(
        {
            "event_type": "search",
            "request_id": "request-1",
            "confidence": 0.91,
        }
    )

    assert table.put_items[0]["confidence"] == Decimal("0.91")
    assert "expires_at" in table.put_items[0]


def test_summary_reads_paginated_dynamodb_logs():
    table = FakeTable(
        pages=[
            {
                "Items": [
                    {
                        "event_type": "search",
                        "created_at": "2026-08-24T13:00:00Z",
                        "status": "needs_clarification",
                        "confidence": Decimal("0.4"),
                        "duration_ms": Decimal("900"),
                    }
                ],
                "LastEvaluatedKey": {"request_id": "request-1"},
            },
            {
                "Items": [
                    {
                        "event_type": "search",
                        "created_at": "2026-08-24T14:00:00Z",
                        "status": "answered",
                        "category_name": "可燃ごみ",
                        "confidence": Decimal("0.9"),
                        "duration_ms": Decimal("1100"),
                    }
                ]
            },
        ]
    )

    summary = SearchLogService(table=table).summary()

    assert summary["total_searches"] == 2
    assert summary["answered_count"] == 1
    assert summary["clarification_count"] == 1
    assert summary["average_confidence"] == 0.65
    assert summary["average_duration_ms"] == 1000
    assert summary["categories"] == {"可燃ごみ": 1}
    assert len(table.scan_calls) == 2
    assert table.scan_calls[1]["ExclusiveStartKey"] == {
        "request_id": "request-1"
    }
