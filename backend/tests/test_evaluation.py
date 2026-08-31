import json

import pytest

from evaluation.build_dataset import (
    balanced_order,
    recognition_candidates,
    stratified_split,
)
from evaluation.common import extract_json, read_jsonl, write_jsonl
from evaluation.run_evaluation import build_report


def _row(item_id: str, category: str) -> dict[str, str]:
    return {
        "item_id": item_id,
        "item": f"品目{item_id}",
        "category": category,
    }


def test_extract_json_accepts_surrounding_text():
    assert extract_json('説明です\n{"answer":"木製です"}\n以上') == {
        "answer": "木製です"
    }


def test_stratified_split_is_stable_and_disjoint():
    rows = [
        *[_row(f"burnable-{index}", "可燃") for index in range(10)],
        *[_row(f"metal-{index}", "金・ガ") for index in range(10)],
    ]
    first = stratified_split(rows, test_ratio=0.2, seed=42)
    second = stratified_split(rows, test_ratio=0.2, seed=42)

    assert first == second
    train_ids = {row["item_id"] for row in first["train"]}
    test_ids = {row["item_id"] for row in first["test"]}
    assert train_ids.isdisjoint(test_ids)
    assert len(test_ids) == 4
    assert {row["category"] for row in first["test"]} == {"可燃", "金・ガ"}


def test_balanced_order_front_slice_is_category_balanced():
    rows = [
        *[_row(f"a-{index}", "可燃") for index in range(5)],
        *[_row(f"b-{index}", "粗大") for index in range(5)],
        *[_row(f"c-{index}", "埋立") for index in range(5)],
    ]
    ordered = balanced_order(rows, seed=1)
    # 全候補を返し、先頭からlimit件を採るとカテゴリ均衡になる。
    assert len(ordered) == len(rows)
    counts = {category: 0 for category in ("可燃", "粗大", "埋立")}
    for row in ordered[:6]:
        counts[row["category"]] += 1
    assert counts == {"可燃": 2, "粗大": 2, "埋立": 2}


def test_recognition_candidates_include_expected_and_similar_distractors():
    expected = {"item_id": "1", "item": "血圧計（水銀式）", "category": "水銀"}
    rows = [
        expected,
        {"item_id": "2", "item": "体温計（水銀式）", "category": "水銀"},
        {"item_id": "3", "item": "体重計", "category": "粗大"},
        {"item_id": "4", "item": "自転車", "category": "粗大"},
    ]

    candidates = recognition_candidates(expected, rows, limit=3)
    ids = {row["item_id"] for row in candidates}

    assert ids == {"1", "2", "3"}


def test_jsonl_round_trip(tmp_path):
    path = tmp_path / "cases.jsonl"
    rows = [{"query": "長い雨の日のやつ"}, {"query": "冷たくする袋"}]
    write_jsonl(path, rows)
    assert read_jsonl(path) == rows
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_report_counts_wrong_and_unresolved():
    base = {
        "expected": {"category_code": "可燃"},
        "clarification_count": 1,
        "duration_ms": 1000,
        "ambiguity_type": "用途表現",
    }
    results = [
        {**base, "correct": True, "outcome": "correct", "confidence": 0.9},
        {
            **base,
            "correct": False,
            "outcome": "wrong_category",
            "confidence": 0.8,
        },
        {
            **base,
            "correct": False,
            "outcome": "unresolved",
            "confidence": None,
        },
    ]
    report = build_report(results)
    assert report["accuracy"] == pytest.approx(1 / 3, abs=0.0001)
    assert report["outcomes"] == {
        "correct": 1,
        "unresolved": 1,
        "wrong_category": 1,
    }
    assert report["average_clarifications"] == 1
    assert report["average_confidence"] == 0.85
