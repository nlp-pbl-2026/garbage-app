"""API-free synthetic tests; official-data audits are a separate command."""

from pathlib import Path
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import saijo_data as data
from saijo_pdf import visible, compact, color_code


@pytest.mark.parametrize(
    "note,primary,expected",
    [
        ("金属製はもえないごみへ", "burnable", ["non_burnable"]),
        ("プラスチック製はもえるごみへ", "non_burnable", ["burnable"]),
        ("汚れの取れないものはもえるごみへ", "pet_bottles", ["burnable"]),
        ("割れたものはもえないごみへ", "bottles", ["non_burnable"]),
        ("キャップとラベルは外し、もえるごみへ", "pet_bottles", []),
        ("金属は取り外しもえないごみへ", "burnable", []),
        ("ケースはもえるごみへ", "non_burnable", []),
        ("指定袋に入れて口を縛れないものは粗大ごみへ", "non_burnable", ["bulky"]),
    ],
)
def test_whole_item_conditions_do_not_apply_accessory_categories(
    note, primary, expected
):
    assert data.classification_options(note, primary) == expected


def test_hidden_white_and_stroke_duplicate_glyphs_are_excluded():
    class Page:
        def get_texttrace(self):
            def span(c, kind=0, color=(0, 0, 0), opacity=1):
                return dict(
                    type=kind,
                    color=color,
                    opacity=opacity,
                    chars=[(ord(c), 0, (0, 0), (0, 0, 10, 10))],
                )

            return [
                span("２"),
                span("２"),
                span("２", kind=1),
                span("0", color=(1, 1, 1)),
                span("９", kind=3),
                span("３", opacity=0),
            ]

    assert compact("".join(c for c, _ in visible(Page()))) == "2"


def test_color_classification_keeps_same_day_streams_separate():
    assert [
        color_code(c)
        for c in [
            (0.2, 0.8, 0.2),
            (1, 0.4, 0),
            (0.816, 0.808, 0.808),
            (0.608, 0.757, 0.898),
        ]
    ] == ["burnable", "non_burnable", "paper", "resources"]
    assert color_code((0.75, 0.75, 0.75)) is None


def test_volatile_navigation_is_excluded_but_rule_changes_are_not():
    marker = "<!-- main_bodyここから -->"
    end = "<!-- main_bodyここまで -->"
    spec = dict(canonicalization="main_body_utf8")
    a = (marker + "<p>朝8時</p>" + end + "navigation A").encode()
    b = (marker + "<p>朝8時</p>" + end + "navigation B").encode()
    c = (marker + "<p>朝9時</p>" + end).encode()
    assert data.normalize_source(a, spec) == data.normalize_source(b, spec)
    assert data.normalize_source(a, spec) != data.normalize_source(c, spec)


def test_changed_official_source_does_not_overwrite_existing_file(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(data, "DATA", tmp_path)
    (tmp_path / "source").mkdir()
    target = tmp_path / "source/a.pdf"
    target.write_bytes(b"original")
    (tmp_path / "sources.json").write_text(
        json.dumps(
            dict(
                sources=[
                    dict(
                        file="a.pdf",
                        url="https://www.city.saijo.ehime.jp/a.pdf",
                        sha256="incorrect",
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
    assert target.read_bytes() == b"original"


def test_failed_verification_prevents_catalog_activation(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "ROOT", tmp_path)
    target = tmp_path / "data/regions/catalog.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"municipalities":[{"id":"38201"}]}')
    before = target.read_bytes()

    def fail():
        raise ValueError("missing dedicated index")

    monkeypatch.setattr(data, "verify", fail)
    with pytest.raises(ValueError, match="dedicated index"):
        data.activate()
    assert target.read_bytes() == before
