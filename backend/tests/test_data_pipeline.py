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


@pytest.mark.parametrize('name', ['kateigomi_matsuyama.html', 'kateigomi_nakajima.html'])
def test_auxiliary_recommendations_can_change_without_changing_reviewed_rules(tmp_path, name):
    import hashlib
    p = pipeline()
    original = b'<main>reviewed disposal rules</main>\n\n<footer>official</footer>'
    current = original.replace(b'\n\n', b'\n<div id="lorecommend"><h2>Recommendations</h2><ul><li>unrelated</li></ul></div>\n')
    path = tmp_path / name
    path.write_bytes(current)
    record = p.check_auxiliary_source(path, hashlib.sha256(original).hexdigest())
    assert record['normalization'] == 'remove_single_line_cms_lorecommend'
    assert record['source_sha256'] == hashlib.sha256(current).hexdigest()
    assert record['verified_content_sha256'] == hashlib.sha256(original).hexdigest()
    assert path.read_bytes() == current  # Keep the actual downloaded source intact.


@pytest.mark.parametrize('name', ['kateigomi_matsuyama.html', 'kateigomi_nakajima.html'])
def test_disposal_rule_change_is_not_hidden_by_recommendation_normalization(tmp_path, name):
    import hashlib
    p = pipeline()
    path = tmp_path / name
    original = b'<main>collect at 8</main>\n\n'
    current = b'<main>collect at 9</main>\n<div id="lorecommend">unrelated</div>\n'
    path.write_bytes(current)
    with pytest.raises(ValueError, match='review required'):
        p.check_auxiliary_source(path, hashlib.sha256(original).hexdigest())


def test_address_tables_still_require_exact_bytes(tmp_path):
    import hashlib
    p = pipeline()
    original = b'<table>reviewed address</table>\n\n'
    path = tmp_path / 'chikukensaku-a.html'
    path.write_bytes(original)
    assert p.check_auxiliary_source(path, hashlib.sha256(original).hexdigest())['normalization'] == 'none'
    path.write_bytes(original + b'<div id="lorecommend">unrelated</div>')
    with pytest.raises(ValueError, match='review required'):
        p.check_auxiliary_source(path, hashlib.sha256(original).hexdigest())


def test_unexpected_recommendation_layout_still_requires_review(tmp_path):
    import hashlib
    p = pipeline()
    path = tmp_path / 'kateigomi_matsuyama.html'
    path.write_bytes(b'<main>reviewed</main>\n<div id="lorecommend">\nunknown layout\n</div>\n')
    with pytest.raises(ValueError, match='review required'):
        p.check_auxiliary_source(path, hashlib.sha256(b'<main>reviewed</main>\n\n').hexdigest())
