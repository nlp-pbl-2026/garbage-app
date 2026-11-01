"""Synthetic rules only: no municipality data, network or Bedrock required."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('recurrence', Path(__file__).resolve().parents[2] / 'scripts/collection_recurrence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
expand = module.expand


def test_nth_weekday_and_nonexistent_fifth():
    rules = [{'weekdays': [1], 'occurrences': [4], 'types': ['paper']},
             {'weekdays': [1], 'occurrences': [5], 'types': ['plastic']}]
    days = expand('2026-08-01', '2026-09-30', rules, collection_types=['paper', 'plastic'])
    assert days['2026-08-24'] == ['paper']
    assert days['2026-08-31'] == ['plastic']
    assert days['2026-09-28'] == ['paper']
    assert sum('plastic' in codes for codes in days.values()) == 1


def test_closed_dates_replacements_same_day_and_fiscal_boundary():
    rules = [{'weekdays': [1, 5], 'types': ['burnable']}]
    days = expand('2026-04-01', '2027-03-31', rules,
                  closed_dates=['2027-01-01'], replacements={'2026-12-30': ['plastic', 'cans']},
                  collection_types=['burnable', 'plastic', 'cans'])
    assert len(days) == 365
    assert days['2026-05-04'] == ['burnable']  # no implicit holiday cancellation
    assert days['2027-01-01'] == []
    assert days['2026-12-30'] == ['cans', 'plastic']
    assert '2027-04-01' not in days


@pytest.mark.parametrize('rule', [
    {'weekdays': [0], 'types': ['paper']}, {'weekdays': [1], 'occurrences': [6], 'types': ['paper']},
    {'weekdays': [1], 'types': ['unknown']}, {'weekdays': [1], 'types': ['paper'], 'weeks': [2]}])
def test_invalid_rules_fail_closed(rule):
    with pytest.raises(ValueError):
        expand('2026-04-01', '2027-03-31', [rule], collection_types=['paper'])


def test_out_of_period_or_conflicting_exceptions_fail():
    with pytest.raises(ValueError):
        expand('2026-04-01', '2027-03-31', [], replacements={'2027-04-01': []}, collection_types=['paper'])
    with pytest.raises(ValueError):
        expand('2026-04-01', '2027-03-31', [], closed_dates=['2027-01-01'],
               replacements={'2027-01-01': ['paper']}, collection_types=['paper'])
