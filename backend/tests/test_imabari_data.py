"""API-free small fixtures for Imabari generation and activation safeguards."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import imabari_data as data
from imabari_pdf import glyphs, month_cells


def test_special_islands_are_not_replaced_with_mainland_weekdays():
    hat = data.special_calendar("12_tokku")["days"]
    ushi = data.special_calendar("36_tokku")["days"]
    assert len(hat) == len(ushi) == 365
    assert hat["2026-04-29"] == []
    assert hat["2026-04-30"] == ["burnable", "non_burnable"]
    assert hat["2026-05-06"] == []
    assert hat["2026-05-07"] == ["burnable", "non_burnable"]
    assert hat["2026-09-23"] == []
    assert hat["2026-09-24"] == ["burnable", "non_burnable"]
    assert hat["2026-04-10"] == ["plastics", "resources"]
    assert ushi["2026-05-05"] == ["plastics", "resources"]
    assert ushi["2026-04-10"] == ["burnable", "non_burnable"]
    assert ushi["2027-01-01"] == []
    assert not any("bulky" in codes for codes in [*hat.values(), *ushi.values()])
    assert not any(d.startswith("2027-04") for d in hat)


def test_shared_printed_cell_does_not_lose_either_date():
    august = list(month_cells(8))
    a = next(v for v in august if v[0] == "2026-08-24")
    b = next(v for v in august if v[0] == "2026-08-31")
    assert a[1] == b[1]
    assert a[2] is False and b[2] is True
    assert len(august) == 31


def test_zero_opacity_and_hidden_text_do_not_become_dictionary_items():
    class Page:
        def get_texttrace(self):
            def s(c, kind=0, opacity=1):
                return dict(
                    type=kind,
                    opacity=opacity,
                    chars=[(ord(c), 0, (0, 0), (0, 0, 8, 8))],
                )

            return [s("缶"), s("缶"), s("瓶", 3), s("紙", opacity=0)]

    assert [c for c, b in glyphs(Page())] == ["缶"]


def test_updated_sources_stop_without_overwriting_original(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "DATA", tmp_path)
    (tmp_path / "source").mkdir()
    (tmp_path / "source/a.pdf").write_bytes(b"original")
    (tmp_path / "sources.json").write_text(
        json.dumps(
            dict(
                sources=[
                    dict(
                        file="a.pdf",
                        url="https://www.city.imabari.ehime.jp/a.pdf",
                        sha256="wrong",
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


def test_missing_verified_index_prevents_activation(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "ROOT", tmp_path)
    target = tmp_path / "data/regions/catalog.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"municipalities":[{"id":"38201"},{"id":"38206"}]}')
    before = target.read_bytes()

    def fail():
        raise ValueError("missing dedicated index")

    monkeypatch.setattr(data, "verify", fail)
    with pytest.raises(ValueError, match="dedicated index"):
        data.activate()
    assert target.read_bytes() == before


def test_profile_clocks_and_indices_are_separated(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "DATA", tmp_path)
    categories = {
        c: dict(
            name=c,
            color="#888888",
            collection_type_id=c,
            instructions="fixture",
            source_url="https://example.test",
        )
        for c in ["burnable", "non_burnable", "resources", "plastics"]
    }
    rules = {
        k: dict(categories=categories, classification_rules=k, bulky_config={})
        for k in ["mainland", "sekizen"]
    }
    (tmp_path / "official_rules.json").write_text(json.dumps(dict(profiles=rules)))
    areas = [
        dict(calendar_id=k, rule_profile_id=p)
        for k, p in [
            ("one", "mainland"),
            ("two", "hatohama_islands"),
            ("three", "ushima"),
            ("four", "sekizen"),
        ]
    ]
    registry = data.registry_record(
        areas, [dict(id=k) for k in ["one", "two", "three", "four"]]
    )
    profiles = registry["rule_profiles"]
    assert profiles["mainland"]["categories"]["burnable"]["cutoff"] == "06:30"
    assert (
        profiles["mainland"]["categories"]["resources"]["cutoff_status"] == "unverified"
    )
    assert (
        profiles["hatohama_islands"]["categories"]["burnable"]["cutoff_status"]
        == "unverified"
    )
    assert (
        "出航時刻"
        in profiles["hatohama_islands"]["categories"]["burnable"]["time_note"]
    )
    assert profiles["ushima"]["categories"]["burnable"]["cutoff"] == "08:30"
    assert profiles["sekizen"]["categories"]["resources"]["cutoff"] == "08:30"
    assert (
        profiles["hatohama_islands"]["items_path"] == profiles["mainland"]["items_path"]
    )
    assert profiles["sekizen"]["items_path"] != profiles["mainland"]["items_path"]
