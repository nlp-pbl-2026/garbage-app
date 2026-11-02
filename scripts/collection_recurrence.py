"""Offline expansion of reviewed weekly/Nth-weekday collection rules.

Weekdays are ISO (Monday=1). Occurrences count that weekday within its month,
not ISO weeks. Holidays are ordinary dates unless explicitly excluded. Runtime
clients continue to consume explicit dates; they never extrapolate these rules.
"""
from datetime import date, timedelta


def expand(start, end, rules, *, closed_dates=(), replacements=None, collection_types):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if end < start:
        raise ValueError('Invalid validity period')
    known = set(collection_types)
    for rule in rules:
        if set(rule) - {'weekdays', 'occurrences', 'types'}:
            raise ValueError('Unknown recurrence field')
        weekdays = rule.get('weekdays', [])
        occurrences = rule.get('occurrences', [1, 2, 3, 4, 5])
        if (not weekdays or any(type(w) is not int or not 1 <= w <= 7 for w in weekdays)
                or not occurrences or any(type(n) is not int or not 1 <= n <= 5 for n in occurrences)
                or not rule.get('types') or not set(rule['types']) <= known):
            raise ValueError('Invalid recurrence')
    closed = {date.fromisoformat(d) for d in closed_dates}
    overrides = {date.fromisoformat(d): set(v) for d, v in (replacements or {}).items()}
    if (any(d < start or d > end for d in closed | overrides.keys())
            or any(not codes <= known for codes in overrides.values())
            or any(overrides.get(d) for d in closed)):
        raise ValueError('Invalid exception or collection on a closed date')
    result = {}
    day = start
    while day <= end:
        codes = set()
        if day not in closed:
            for rule in rules:
                if day.isoweekday() in rule['weekdays'] and (day.day-1)//7+1 in rule.get('occurrences', [1, 2, 3, 4, 5]):
                    codes.update(rule['types'])
            codes = overrides.get(day, codes)
        result[day.isoformat()] = sorted(codes)
        day += timedelta(days=1)
    return result
