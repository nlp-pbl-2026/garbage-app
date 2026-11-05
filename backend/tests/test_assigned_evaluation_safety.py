"""The paid assigned-municipality evaluator keeps a cross-run hard limit."""

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "assigned_municipalities_evaluate",
    ROOT / "scripts/assigned_municipalities_evaluate.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_journal(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def test_evaluation_usage_is_aggregated_across_retry_runs(tmp_path, monkeypatch):
    write_journal(
        tmp_path / "initial/calls.jsonl",
        [
            {"event": "reserve", "id": "initial-nova-1", "reserved_usd": 0.10},
            {"event": "settle", "id": "initial-nova-1", "estimated_usd": 0.02},
        ],
    )
    write_journal(
        tmp_path / "retry/calls.jsonl",
        [{"event": "reserve", "id": "retry-titan-2", "reserved_usd": 0.10}],
    )
    monkeypatch.setattr(module, "ARTIFACTS", tmp_path)

    records = module.all_evaluation_records()

    assert sum(record["event"] == "reserve" for record in records) == 2
    assert module.settled_cost(records) == pytest.approx(0.12)
    assert module.MAX_APPROVED_BUDGET_USD == 0.60
    assert module.MAX_EVALUATION_CALLS == 126
    assert module.MAX_TOTAL_CALLS == 7726
