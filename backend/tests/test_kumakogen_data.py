"""Synthetic extraction/recurrence regressions; no official files or paid API."""

from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import kumakogen_data as data
from kumakogen_pdf import compact, month_date, spans, expand_ics


def test_offset_bottom_border_keeps_last_dictionary_item():
    from types import SimpleNamespace
    from kumakogen_pdf import dictionary_borders

    drawings = [
        {"color": (0, 0, 0), "rect": SimpleNamespace(y0=y, height=0, width=w, x0=x)}
        for x, y, w in [
            (37.84, 770.10, 112.89),
            (37.84, 788.53, 112.89),
            (36.85, 806.95, 113.88),
        ]
    ]
    assert dictionary_borders(drawings, 37.35) == [770.1, 788.53, 806.95]


@pytest.mark.parametrize(
    "value,column,expected",
    [
        ("２２", 12, "2026-12-22"),
        ("5", 1, "2027-01-05"),
        ("7月2日", 6, "2026-07-02"),
        ("10月1日", 9, "2026-10-01"),
        ("5月1日", 4, "2026-05-01"),
        ("7月3日", 6, "2026-07-03"),
    ],
)
def test_printed_month_takes_precedence_over_table_column(value, column, expected):
    assert month_date(value, column) == expected


@pytest.mark.parametrize("value", ["0", "32", "2月30日", "休み", "４・５"])
def test_unconfirmed_or_invalid_cell_is_never_guessed(value):
    with pytest.raises(ValueError):
        month_date(value, 4)


@pytest.mark.parametrize(
    "note,primary,expected",
    [
        ("袋に入らないものは「粗大ごみ」", "burnable", ["bulky"]),
        ("袋に入れば「燃えないごみ」", "bulky", ["non_burnable"]),
        ("プラ製のものは「プラ類」", "metals", ["plastic_packaging"]),
        ("金属製は「金属類」", "burnable", ["metals"]),
        ("キャップははずして「プラ類」", "pet_bottles", []),
        ("チューブは「燃えるごみ」", "bulky", []),
        ("袋に入れば素材に応じて", "bulky", ["burnable", "non_burnable"]),
    ],
)
def test_whole_item_alternatives_do_not_authorize_accessory_classification(
    note, primary, expected
):
    assert data.classification_options(note, primary) == expected


def test_icalendar_exclusions_overrides_and_fiscal_boundary(tmp_path):
    p = tmp_path / "official.ics"
    p.write_text("""BEGIN:VCALENDAR
BEGIN:VEVENT
UID:weekly
DTSTART;VALUE=DATE:20230407
RRULE:FREQ=WEEKLY;BYDAY=FR
EXDATE;VALUE=DATE:20270101
SUMMARY:可燃ごみ（燃えるごみ）
END:VEVENT
BEGIN:VEVENT
UID:monthly
DTSTART;VALUE=DATE:20260331
RRULE:FREQ=MONTHLY;BYMONTHDAY=31
SUMMARY:資源ごみ（すべて）
END:VEVENT
BEGIN:VEVENT
UID:monthly
RECURRENCE-ID;VALUE=DATE:20260331
DTSTART;VALUE=DATE:20260402
SUMMARY:資源ごみ（すべて）
END:VEVENT
BEGIN:VEVENT
UID:weekly
RECURRENCE-ID;VALUE=DATE:20261225
DTSTART;VALUE=DATE:20261224
SUMMARY:可燃ごみ（燃えるごみ）
END:VEVENT
END:VCALENDAR
""")
    result = expand_ics(p)
    assert "2027-01-01" not in result["burnable"]
    assert "2026-12-25" not in result["burnable"]
    assert "2026-12-24" in result["burnable"]
    assert "2026-04-02" in result["all_resources"]
    assert all("2026-04-01" <= d <= "2027-03-31" for ds in result.values() for d in ds)


def test_fetch_refuses_changed_source_without_overwriting(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "DATA", tmp_path)
    source = tmp_path / "source/paper.pdf"
    source.parent.mkdir()
    source.write_bytes(b"old")
    (tmp_path / "sources.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "file": "paper.pdf",
                        "url": "https://www.kumakogen.jp/uploaded/attachment/test.pdf",
                        "sha256": "wrong",
                    }
                ]
            }
        )
    )

    class Response:
        def read(self):
            return b"changed"

    monkeypatch.setattr(data, "urlopen", lambda *a, **k: Response())
    with pytest.raises(ValueError, match="source changed"):
        data.fetch()
    assert source.read_bytes() == b"old"


def test_only_volatile_calendar_stamp_is_normalized():
    raw = b"BEGIN:VCALENDAR\r\nDTSTAMP:20261111T000000Z\r\nEXDATE;VALUE=DATE:20270101\r\nEND:VCALENDAR\r\n"
    normalized = data.normalize_source(
        raw, {"canonicalization": "icalendar_without_dtstamp_lf"}
    )
    assert normalized == b"BEGIN:VCALENDAR\nEXDATE;VALUE=DATE:20270101\nEND:VCALENDAR\n"
    assert data.normalize_source(raw, {}) == raw


def test_public_calendar_event_order_does_not_break_reproduction():
    a = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:a\nDTSTART;VALUE=DATE:20261230\nEXDATE;VALUE=DATE:20270101\nEND:VEVENT\nBEGIN:VEVENT\nUID:b\nSUMMARY:資源ごみ\nEND:VEVENT\nEND:VCALENDAR\n"
    b = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:資源ごみ\nUID:b\nEND:VEVENT\nBEGIN:VEVENT\nEXDATE;VALUE=DATE:20270101\nDTSTART;VALUE=DATE:20261230\nUID:a\nEND:VEVENT\nEND:VCALENDAR\n"
    config = {"canonicalization": "icalendar_unfold_sort_events_without_dtstamp_lf"}
    assert data.normalize_source(a.encode(), config) == data.normalize_source(
        b.encode(), config
    )
    assert b"EXDATE;VALUE=DATE:20270101" in data.normalize_source(a.encode(), config)


def test_glyph_reader_excludes_hidden_and_duplicate_text():
    class Page:
        def get_texttrace(self):
            char = (ord("７"), 0, (1, 1), (0, 0, 10, 10))
            return [
                {"type": 0, "opacity": 1, "chars": [char]},
                {"type": 0, "opacity": 1, "chars": [char]},
                {
                    "type": 3,
                    "opacity": 1,
                    "chars": [(ord("９"), 0, (1, 1), (0, 0, 10, 10))],
                },
            ]

    assert compact("".join(c for c, _ in spans(Page()))) == "7"
