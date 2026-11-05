#!/usr/bin/env python3
"""Generate only the seven assigned municipality indexes after paid approval.

The per-municipality builder keeps resumable checkpoints.  This wrapper adds a
combined call and conservative budget ceiling so retries in one municipality
cannot consume the allowance reserved for the others.  It never edits AWS
resources and never reads or regenerates another municipality's index.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_regional_embeddings", ROOT / "scripts/build_regional_embeddings.py"
)
BUILDER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BUILDER)

MUNICIPALITIES = (
    ("ozu", "38207"),
    ("tobe", "38402"),
    ("ainan", "38506"),
    ("kihoku", "38488"),
    ("matsuno", "38484"),
    ("uchiko", "38422"),
    ("masaki", "38401"),
)
MAX_APPROVED_CALLS = 7600
MAX_APPROVED_BUDGET_USD = 0.48


def checkpoint_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def usage() -> tuple[int, float]:
    calls = 0
    reserve = 0.0
    for slug, _ in MUNICIPALITIES:
        records = checkpoint_records(
            ROOT / f"data/regions/{slug}/generated/titan-checkpoint.jsonl"
        )
        calls += sum(int(record.get("calls", 0)) for record in records)
        reserve += sum(float(record.get("reserved_usd", 0)) for record in records)
    return calls, reserve


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-paid", action="store_true", required=True)
    parser.add_argument("--max-calls", type=int, default=MAX_APPROVED_CALLS)
    parser.add_argument("--budget-usd", type=float, default=MAX_APPROVED_BUDGET_USD)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--only",
        choices=[slug for slug, _ in MUNICIPALITIES],
        help="Resume one municipality while retaining the combined ceilings.",
    )
    args = parser.parse_args()
    if not args.confirm_paid:
        raise ValueError("Explicit paid approval is required")
    if not 0 < args.max_calls <= MAX_APPROVED_CALLS:
        raise ValueError(f"Call limit must not exceed {MAX_APPROVED_CALLS}")
    if not 0 < args.budget_usd <= MAX_APPROVED_BUDGET_USD:
        raise ValueError(f"Budget must not exceed USD {MAX_APPROVED_BUDGET_USD:.2f}")
    if not 1 <= args.workers <= 8:
        raise ValueError("workers must be between 1 and 8")

    selected = [entry for entry in MUNICIPALITIES if not args.only or entry[0] == args.only]
    for slug, municipality_id in selected:
        calls_before, reserve_before = usage()
        data = ROOT / "data/regions" / slug
        checkpoint = data / "generated/titan-checkpoint.jsonl"
        city_records = checkpoint_records(checkpoint)
        city_calls = sum(int(record.get("calls", 0)) for record in city_records)
        city_reserve = sum(float(record.get("reserved_usd", 0)) for record in city_records)
        remaining_calls_for_city = args.max_calls - (calls_before - city_calls)
        remaining_budget_for_city = args.budget_usd - (reserve_before - city_reserve)
        if remaining_calls_for_city <= 0 or remaining_budget_for_city <= 0:
            raise RuntimeError("Combined approved call/budget limit reached")
        BUILDER.build(
            data / "knowledge/items.csv",
            data / "knowledge/item_embeddings.npz",
            municipality_id,
            "citywide",
            checkpoint,
            max_calls=remaining_calls_for_city,
            budget=remaining_budget_for_city,
            workers=args.workers,
        )
        calls_after, reserve_after = usage()
        print(
            f"combined usage after {slug}: {calls_after}/{args.max_calls} attempts; "
            f"conservative reserve ${reserve_after:.6f}/${args.budget_usd:.2f}",
            flush=True,
        )


if __name__ == "__main__":
    main()
