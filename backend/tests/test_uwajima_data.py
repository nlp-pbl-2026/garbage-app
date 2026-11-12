"""API-free fixtures for Uwajima extraction, scope and fail-closed generation."""

from datetime import date
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import uwajima_data as data
from uwajima_html import Document, content, expanded
from uwajima_pdf import cell_text
from uwajima_schedule import matches


def test_merged_html_scope_is_preserved_without_filling_unknown_cells():
    doc = Document(
        '<table><tr><td rowspan="2">島</td><td colspan="2">水曜日</td></tr><tr><td>月末</td><td></td></tr></table>'
    )
    rows = expanded(doc.tables[0])
    assert [[c["text"] for c in r] for r in rows] == [
        ["島", "水曜日", "水曜日"],
        ["島", "月末", ""],
    ]
    with pytest.raises(ValueError, match="nested"):
        Document("<table><table>")


def test_month_end_is_not_silently_the_last_calendar_day():
    assert not matches(date(2026, 4, 30), "月末")
    assert matches(date(2026, 4, 29), "第1・3・5水曜日")
    assert not matches(date(2026, 4, 22), "第1・3・5水曜日")
    assert matches(date(2026, 4, 22), "水曜日")


def test_coloured_icons_in_shared_diagonal_cell_keep_both_dates(tmp_path):
    import pymupdf
    from uwajima_pdf import calendar_image, PALETTE

    document = pymupdf.open()
    page = document.new_page(width=842, height=1191)
    for box, code in [
        ([334, 441, 339, 447], "burnable"),
        ([359, 459, 364, 465], "pet"),
    ]:
        page.draw_rect(
            pymupdf.Rect(box), fill=tuple(v / 255 for v in PALETTE[code]), color=None
        )
    path = tmp_path / "fixture.pdf"
    document.save(path)
    days, stats = calendar_image(path)
    assert days["2026-08-24"] == ["burnable"]
    assert days["2026-08-31"] == ["pet"]
    assert len(days) == 2 and stats["cells"] == 365


def test_only_current_official_article_body_is_hashed():
    a = "volatile<!-- main_bodyここから --><p>令和8年度</p><!-- main_bodyここまで -->footer"
    assert content(a.encode()) == "<p>令和8年度</p>".encode()
    assert content(a.replace("volatile", "new").encode()) == content(a.encode())
    with pytest.raises(ValueError, match="boundaries"):
        content(b"<body>no official boundaries</body>")


def test_changed_download_never_overwrites_reviewed_source(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "DATA", tmp_path)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/a.pdf").write_bytes(b"original")
    (tmp_path / "sources.json").write_text(
        json.dumps(
            dict(
                sources=[
                    dict(
                        file="a.pdf",
                        url="https://www.city.uwajima.ehime.jp/a.pdf",
                        sha256=hashlib.sha256(b"original").hexdigest(),
                    )
                ]
            )
        )
    )

    class Response:
        def read(self):
            return b"changed"

    monkeypatch.setattr(data, "urlopen", lambda *a, **k: Response())
    with pytest.raises(ValueError, match="source changed"):
        data.fetch()
    assert (tmp_path / "source/a.pdf").read_bytes() == b"original"


def test_dictionary_orders_displaced_punctuation_and_ignores_hidden_glyphs():
    class Page:
        def get_texttrace(self):
            def span(c, x, y=1, kind=0):
                return dict(
                    type=kind,
                    opacity=1,
                    chars=[(ord(c), 0, (x, y), (x, y, x + 1, y + 2))],
                )

            return [
                span("タ", 1),
                span("マ", 3),
                span("ー", 4, 2),
                span("イ", 2),
                span("タ", 1),
                span("古", 5, kind=3),
            ]

    assert cell_text(Page(), [0, 0, 10, 10]) == "タイマー"


def test_missing_index_cannot_register_city_or_alter_other_cities(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(data, "ROOT", tmp_path)
    path = tmp_path / "data/regions/catalog.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"municipalities":[{"id":"38201"},{"id":"38202"}]}')
    before = path.read_bytes()

    def fail():
        raise ValueError("missing dedicated index")

    monkeypatch.setattr(data, "verify", fail)
    with pytest.raises(ValueError, match="index"):
        data.activate()
    assert path.read_bytes() == before


def test_island_times_and_nonregular_disposal_are_not_made_regular(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(data, "DATA", tmp_path)
    cats = {
        "burnable": dict(
            name="可燃", collection_type_id="burnable", instructions="fixture"
        ),
        "bulky": dict(name="粗大", instructions="direct"),
        "clean_plastics": dict(name="拠点", instructions="dropoff"),
    }
    (tmp_path / "official_rules.json").write_text(
        json.dumps(
            dict(categories=cats, classification_rules="fixture", bulky_config={})
        )
    )
    selected = [
        dict(calendar_id="one", rule_profile_id="uwajima_islands"),
        dict(calendar_id="two", rule_profile_id="yoshida"),
    ]
    registry = data.registry_record(selected, {"one": {}, "two": {}})
    island = registry["rule_profiles"]["uwajima_islands"]
    main = registry["rule_profiles"]["yoshida"]
    assert island["categories"]["burnable"]["cutoff_status"] == "unverified"
    assert "cutoff" not in island["categories"]["burnable"]
    assert main["categories"]["burnable"]["cutoff"] == "08:30"
    assert "collection_type_id" not in main["categories"]["bulky"]
    assert "collection_type_id" not in main["categories"]["clean_plastics"]
    assert island["items_path"] == main["items_path"]
    assert island["embedding_index_path"] == main["embedding_index_path"]
