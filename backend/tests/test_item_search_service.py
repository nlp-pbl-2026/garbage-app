from app.services.item_search_service import ItemSearchService


def test_bento_lid_search_includes_structured_bento_container_record():
    matches = ItemSearchService().search(
        "松山市清水地区 お弁当の透明なプラスチック製フタ ごみ分別"
    )

    matching_items = {match.item: match for match in matches}
    assert "弁当・惣菜の容器（プラスチック製）" in matching_items
    assert matching_items["弁当・惣菜の容器（プラスチック製）"].category == "プラ"


def test_transparent_bento_lid_prioritizes_disposable_container_records():
    matches = ItemSearchService().search("お弁当の透明なフタ")

    assert [match.category for match in matches[:2]] == ["プラ", "プラ"]
    assert all("弁当箱" not in match.item for match in matches)


def test_material_mentioned_only_in_note_does_not_dominate_item_name_match():
    matches = ItemSearchService().search("弁当 プラスチック製 ふた")
    names = [match.item for match in matches]

    assert "弁当・惣菜の容器（プラスチック製）" in names
    assert "粉ミルクの缶" not in names


def test_packaged_lambda_path_is_detected(monkeypatch, tmp_path):
    packaged_csv = tmp_path / "data/regions/matsuyama/common/knowledge/items.csv"
    packaged_csv.parent.mkdir(parents=True)
    packaged_csv.write_text(
        "search_text,item_id,item,note,category,category_display\n"
        "テスト容器,item_1,テスト容器,,プラ,プラスチック製容器包装\n",
        encoding="utf-8",
    )
    fake_module = tmp_path / "app/services/item_search_service.py"
    monkeypatch.setattr(
        "app.services.item_search_service.__file__", str(fake_module)
    )

    service = ItemSearchService()

    assert service.search("テスト容器")[0].item_id == "item_1"
