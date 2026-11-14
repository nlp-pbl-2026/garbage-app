import json
import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest

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
    assert table.scan_calls[1]["ExclusiveStartKey"] == {"request_id": "request-1"}


def test_research_text_is_stored_but_not_duplicated_in_application_logs(caplog):
    table = FakeTable()
    with caplog.at_level(logging.INFO):
        SearchLogService(table=table).record(
            {
                "event_type": "search",
                "status": "answered",
                "duration_ms": 10,
                "municipality_id": "38201",
                "district_id": "private-area",
                "query": "private-query",
                "rewritten_query": "private-rewrite",
                "clarifications": [
                    {
                        "question": "private-question",
                        "answer": "private-answer",
                        "token": "not-for-storage",
                    }
                ],
                "answer": "private-generated",
                "follow_up_question": "private-follow-up",
                "image": "private-image",
                "unknown": "private-extra",
                "has_image": True,
                "image_media_type": "image/png",
                "image_size_bytes": 12,
            }
        )
    stored = table.put_items[0]
    assert stored["query"] == "private-query"
    assert stored["rewritten_query"] == "private-rewrite"
    assert stored["district_id"] == "private-area"
    assert stored["answer"] == "private-generated"
    assert stored["follow_up_question"] == "private-follow-up"
    assert stored["clarifications"] == [
        {"question": "private-question", "answer": "private-answer"}
    ]
    assert stored["duration_ms"] == 10
    assert stored["image_size_bytes"] == 12
    assert "image" not in stored and "unknown" not in stored
    assert "private-" not in caplog.text
    table.pages = [{"Items": table.put_items}]
    assert SearchLogService(table=table).summary()["recent"][0] == stored


def test_legacy_logs_keep_text_on_admin_read_without_rewriting(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.SEARCH_LOG_TABLE", "")
    path = tmp_path / "existing.jsonl"
    path.write_text(
        json.dumps(
            {
                "event_type": "search",
                "query": "private-query",
                "answer": "private-answer",
                "district_id": "private-area",
                "created_at": "2026-11-01T00:00:00Z",
                "status": "answered",
                "category_name": "可燃ごみ",
            }
        )
        + "\n"
    )
    before = path.read_bytes()
    summary = SearchLogService(file_path=path).summary()
    assert summary["recent"][0]["query"] == "private-query"
    assert summary["recent"][0]["answer"] == "private-answer"
    assert summary["recent"][0]["district_id"] == "private-area"
    assert summary["answered_count"] == 1
    assert summary["categories"] == {"可燃ごみ": 1}
    assert path.read_bytes() == before


def test_local_roundtrip_keeps_text_and_configured_retention(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.SEARCH_LOG_TABLE", "")
    monkeypatch.setattr("app.config.SEARCH_LOG_RETENTION_DAYS", 17)
    service = SearchLogService(file_path=tmp_path / "search.jsonl")
    before = int(datetime.now(UTC).timestamp())
    service.record(
        {"event_type": "search", "query": "缶の捨て方は？", "answer": "缶類です。"}
    )
    after = int(datetime.now(UTC).timestamp())
    item = service.list_recent()[0]
    assert item["query"] == "缶の捨て方は？"
    assert item["answer"] == "缶類です。"
    assert before + 17 * 86400 <= item["expires_at"] <= after + 17 * 86400


def test_metrics_only_records_are_not_given_invented_text(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.SEARCH_LOG_TABLE", "")
    service = SearchLogService(file_path=tmp_path / "search.jsonl")
    service.record(
        {
            "event_type": "search",
            "text_retained": False,
            "query": "（入力文は保存していません）",
            "status": "answered",
        }
    )
    item = service.summary()["recent"][0]
    assert item["text_retained"] is False
    assert item["query"] == "（入力文は保存していません）"
    assert "answer" not in item


@pytest.mark.parametrize("use_file", [True, False])
def test_persistence_failure_does_not_expose_text_or_break_search(
    tmp_path, monkeypatch, caplog, use_file
):
    monkeypatch.setattr("app.config.SEARCH_LOG_TABLE", "")
    table = FakeTable()

    def fail(*args, **kwargs):
        raise RuntimeError("private-query private-generated-answer")

    monkeypatch.setattr(table, "put_item", fail)
    path = tmp_path / "blocked"
    if use_file:
        path.mkdir()
        # Use a synthetic failure: real provider/filesystem errors may echo input.
        monkeypatch.setattr("pathlib.Path.open", fail)
    with caplog.at_level(logging.INFO):
        SearchLogService(table=None if use_file else table, file_path=path).record(
            {
                "event_type": "search",
                "query": "private-query",
                "answer": "private-generated-answer",
            }
        )
    assert "Failed to persist" in caplog.text
    assert "private-" not in caplog.text
    assert "event recorded" not in caplog.text
