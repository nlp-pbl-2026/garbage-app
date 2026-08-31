"""品目検索ルーター - あいまい検索（CSV）ベースの品目検索エンドポイントを提供する。"""

from fastapi import APIRouter, Query

from ..services.item_search_service import ItemSearchService

router = APIRouter(prefix="/api/items", tags=["items"])

# サービスのシングルトンインスタンス
_search_service = ItemSearchService()

# カテゴリコードからフロントエンド用カテゴリへのマッピング
_CATEGORY_MAP = {
    "可燃": "burnable",
    "プラ": "plastic",
    "金・ガ": "recyclable",
    "紙類": "recyclable",
    "埋立": "hazardous",
    "水銀": "hazardous",
    "粗大": "burnable",  # フロントエンドのenumに粗大がないためfallback
    "ペット": "petBottle",
    "禁止": "hazardous",
}


def _to_frontend_category(category_code: str) -> str:
    """CSVのカテゴリコードをフロントエンドのGarbageCategory文字列に変換する。"""
    return _CATEGORY_MAP.get(category_code, "burnable")


def _match_to_item_dict(match) -> dict:
    """ItemMatchをフロントエンドのGarbageItem JSON形式に変換する。"""
    primary_category = _to_frontend_category(match.category)
    return {
        "id": match.item_id,
        "name": match.item,
        "primaryCategory": primary_category,
        "secondaryCategories": [],
        "disposalMethod": match.note or match.category_display or "",
        "caution": match.note if match.note else None,
        "keywords": [],
    }


@router.get("/search")
async def search_items(
    keyword: str = Query(..., min_length=2, description="検索キーワード（2文字以上）"),
):
    """品目をキーワードで検索する。"""
    matches = _search_service.search(keyword, limit=50)
    items = [_match_to_item_dict(m) for m in matches]
    return {"items": items}


@router.get("/popular")
async def get_popular_items():
    """よく検索される品目を返す（デフォルト品目リスト）。"""
    # 代表的な品目を返す
    popular_keywords = ["ペットボトル", "新聞紙", "缶", "びん", "プラスチック"]
    items = []
    seen_ids = set()
    for kw in popular_keywords:
        matches = _search_service.search(kw, limit=1)
        for m in matches:
            if m.item_id not in seen_ids:
                items.append(_match_to_item_dict(m))
                seen_ids.add(m.item_id)
    return {"items": items}


@router.get("/{item_id}")
async def get_item_by_id(item_id: str):
    """品目IDから詳細を取得する。"""
    # 全品目から該当IDを検索
    for row in _search_service._items:
        if row.get("item_id") == item_id:
            primary_category = _to_frontend_category(row.get("category", ""))
            return {
                "id": row.get("item_id", ""),
                "name": row.get("item", ""),
                "primaryCategory": primary_category,
                "secondaryCategories": [],
                "disposalMethod": row.get("note", "") or row.get("category_display", ""),
                "caution": row.get("note") or None,
                "keywords": [],
            }
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="品目が見つかりません")
