"""Synthetic Tobe source/PDF tests: no network, official files or Bedrock."""
from pathlib import Path
from types import SimpleNamespace
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import tobe_data
from tobe_pdf import category_code, collection_types, extract_calendar, extract_items


class FakeTable:
    def __init__(self, rows):
        self.rows = rows

    def extract(self):
        return self.rows


class FakePage:
    def __init__(self, tables):
        self.tables = tables

    def find_tables(self, **_kwargs):
        return SimpleNamespace(tables=[FakeTable(rows) for rows in self.tables])


def test_calendar_page_uses_current_fiscal_descending_block_only(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "calendar-page.html").write_text(
        '<a href="calendar10.pdf">くらしのカレンダー10月号</a>'
        '<a href="calendar09.pdf">くらしのカレンダー9月号</a>'
        '<a href="calendar08.pdf">くらしのカレンダー8月号</a>'
        '<a href="calendar07.pdf">くらしのカレンダー7月号</a>'
        '<a href="calendar06.pdf">くらしのカレンダー6月号</a>'
        '<a href="calendar05.pdf">くらしのカレンダー5月号</a>'
        '<a href="calendar04.pdf">くらしのカレンダー4月号</a>'
        '<a href="old03.pdf">くらしのカレンダー3月号</a>'
        '<a href="old02.pdf">くらしのカレンダー2月号</a>',
        encoding="utf-8",
    )
    entries = tobe_data.calendar_entries(tmp_path)
    assert [entry["month"] for entry in entries] == [4, 5, 6, 7, 8, 9, 10]
    assert all("old" not in entry["url"] for entry in entries)


def test_dictionary_categories_keep_all_tobe_streams_and_safe_destinations():
    assert category_code("プラ製 容器包装") == "plastic_packaging"
    assert category_code("雑誌 雑がみ") == "magazines"
    assert category_code("古着古布") == "textiles"
    assert category_code("美化センター") == "facility_dropoff"
    assert category_code("排出禁止物") == "not_collected"
    assert category_code("", "紙パック参照") == "paper_cartons"
    assert category_code("", "枝参照") == "pruning"


def test_dictionary_table_preserves_recycling_as_an_option_not_primary_category():
    page = FakePage([[
        ["品名", "備考", "分別", "リサイクル", "品名", "備考", "分別", "リサイクル"],
        ["カメラ", "電池を外す", "雑ごみ", "小型家電", "農機具", "販売店へ", "排出禁止物", ""],
    ]])
    rows = extract_items([page], minimum_rows=2)
    assert [(row["item"], row["category"]) for row in rows] == [
        ("カメラ", "miscellaneous"),
        ("農機具", "not_collected"),
    ]
    assert rows[0]["category_options"] == ["collection_box"]
    assert rows[1]["category_options"] == []


def test_hirota_weekly_one_does_not_receive_weekly_two_only_burnable():
    assert "burnable" in collection_types("可燃ごみ（週1・週2）", "hirota-weekly-1")
    assert "burnable" not in collection_types("可燃ごみ（週2）", "hirota-weekly-1")
    assert "burnable" in collection_types("可燃ごみ（週2）", "hirota-weekly-2")


def test_monthly_calendar_splits_base_weekly_and_special_areas():
    page = FakePage([[
        ["日", "曜", "麻生小校区", "宮内小・砥部小校区", "広田地域", "行事など"],
        ["1", "木", "プラ製容器包装", "可燃ごみ", "可燃ごみ（週2）\nプラ製容器包装", ""],
        ["2", "金", "可燃ごみ\n（田ノ浦）すべて", "プラ製容器包装", "プラ製容器包装", ""],
        ["8", "木", "プラ製容器包装", "可燃ごみ\n（大平）すべて", "可燃ごみ（週2）", ""],
        ["15", "木", "プラ製容器包装", "可燃ごみ\n（鵜ノ崎）すべて", "可燃ごみ（週2）", ""],
    ]])
    calendars, audit = extract_calendar([page], year=2026, month=10, minimum_rows=4)
    assert calendars["tobe-asou"]["2026-10-02"] == ["burnable"]
    assert calendars["tobe-tanoura"]["2026-10-02"]
    assert calendars["tobe-ohira"]["2026-10-08"]
    assert calendars["tobe-unosaki"]["2026-10-15"]
    assert calendars["tobe-hirota-weekly-1"]["2026-10-01"] == ["plastic_packaging"]
    assert calendars["tobe-hirota-weekly-2"]["2026-10-01"] == ["burnable", "plastic_packaging"]
    assert audit["dated_rows"] == 4


def test_tobe_workflow_never_imports_or_invokes_bedrock():
    source = (ROOT / "scripts/tobe_data.py").read_text(encoding="utf-8").lower()
    assert "boto3" not in source
    assert "invoke_model" not in source
    assert "build_regional_embeddings" not in source
