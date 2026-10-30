"""Build/review guards use synthetic records, without PDFs, network or Bedrock."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest


def pipeline():
    path = Path(__file__).resolve().parents[2] / "scripts/matsuyama_data.py"
    spec = importlib.util.spec_from_file_location("matsuyama_pipeline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validation():
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from matsuyama_validation import check_calendar_record
    return check_calendar_record


def test_build_requires_matching_review_and_emits_identical_bytes(tmp_path, monkeypatch):
    p = pipeline()
    monkeypatch.setattr(p, "ROOT", tmp_path)
    monkeypatch.setattr(p, "DATA", tmp_path / "data")
    (tmp_path / "frontend/assets/data").mkdir(parents=True)
    (p.DATA / "source").mkdir(parents=True)
    pdf = p.DATA / "source/test.pdf"
    pdf.write_bytes(b"synthetic source, never a real calendar")
    record = {"days": {"2026-04-01": ["paper", "bottles"]}, "exceptions": {},
              "source_sha256": p.sha256(pdf)}
    p.write_json(p.DATA / "source/extraction-review.json", {"calendars": {"test": record}, "failures": []})
    reviews = {"calendars": {"test": {"source_sha256": p.sha256(pdf),
               "normalized_sha256": p.normalized_hash(record), "verification_status": "checked"}}}
    p.write_json(p.DATA / "calendar_reviews.json", reviews)
    registry = {"schema_version": 1, "municipality_id": "test", "version": "test", "fiscal_year": 2026,
                "valid_from": "2026-04-01", "valid_to": "2027-03-31", "timezone": "Asia/Tokyo",
                "calendars": [{"id": "test", "file": "test.pdf", "url": "https://example.test/official"}]}
    p.build(registry)
    assert (p.DATA / "generated/calendar-2026.json").read_bytes() == (tmp_path / "frontend/assets/data/municipality_calendar.json").read_bytes()
    record["days"]["2026-04-01"] = ["combustible"]
    p.write_json(p.DATA / "source/extraction-review.json", {"calendars": {"test": record}, "failures": []})
    with pytest.raises(ValueError, match="Review/hash mismatch"):
        p.build(registry)


def test_validation_rejects_identically_corrupted_backend_and_flutter_bundles():
    p = pipeline()
    check = validation()
    extracted = {"days": {"2026-04-01": ["paper"]}, "exceptions": {}}
    review = {"normalized_sha256": p.normalized_hash(extracted)}
    record = {"days": {"2026-04-01": ["paper"]}, "exceptions": {}}
    check(record, extracted, review, "test")
    record["days"]["2026-04-01"] = ["combustible"]
    with pytest.raises(ValueError, match="differs from reviewed PDF extraction"):
        check(record, extracted, review, "test")
