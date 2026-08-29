"""粗大ごみ関連ルーター"""

from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import BulkyWasteItem, BulkyWasteItemTranslation, MunicipalityConfig
from ..schemas import (
    BulkyWasteItemListResponse,
    BulkyWasteItemResponse,
    MunicipalityConfigResponse,
    ApplicationStep,
)

router = APIRouter(prefix="/api/bulky-waste", tags=["bulky-waste"])


# 言語別エラーメッセージ
ERROR_MESSAGES = {
    "municipality_not_found": {
        "ja": "指定された自治体が見つかりません",
        "en": "The specified municipality was not found",
        "pt": "O município especificado não foi encontrado",
        "zh": "未找到指定的市区町村",
        "vi": "Không tìm thấy thành phố được chỉ định",
    },
    "item_not_found": {
        "ja": "指定された品目が見つかりません",
        "en": "The specified item was not found",
        "pt": "O item especificado não foi encontrado",
        "zh": "未找到指定的物品",
        "vi": "Không tìm thấy vật phẩm được chỉ định",
    },
}


def get_error_message(error_key: str, language: str) -> str:
    """言語に応じたエラーメッセージを返す。対応言語がない場合は日本語にフォールバック。"""
    messages = ERROR_MESSAGES.get(error_key, {})
    return messages.get(language, messages.get("ja", "エラーが発生しました"))


class SortBy(str, Enum):
    name = "name"
    fee = "fee"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


async def get_localized_item(
    item: BulkyWasteItem, language: str, db: AsyncSession
) -> BulkyWasteItemResponse:
    """品目のローカライズされたレスポンスを生成する。

    翻訳が存在すれば翻訳テキストを使用し、存在しなければ日本語ベースフィールドにフォールバックする。
    日本語(ja)の場合は翻訳テーブルの検索をスキップする。
    """
    item_name = item.item_name
    notes = item.notes

    if language != "ja":
        result = await db.execute(
            select(BulkyWasteItemTranslation).where(
                BulkyWasteItemTranslation.bulky_waste_item_id == item.id,
                BulkyWasteItemTranslation.language_code == language,
            )
        )
        translation = result.scalar_one_or_none()

        if translation:
            # 翻訳フィールドが存在する場合のみ上書き（Noneの場合は日本語フォールバック）
            if translation.item_name:
                item_name = translation.item_name
            if translation.notes:
                notes = translation.notes

    return BulkyWasteItemResponse(
        id=item.id,
        item_name=item_name,
        category=item.category,
        fee_amount=item.fee_amount,
        size_category=item.size_category,
        size_threshold_cm=item.size_threshold_cm,
        weight_category=item.weight_category,
        weight_threshold_kg=item.weight_threshold_kg,
        notes=notes,
    )


@router.get("/config/{municipality_id}", response_model=MunicipalityConfigResponse)
async def get_municipality_config(
    municipality_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MunicipalityConfigResponse:
    """自治体粗大ごみ設定を取得する"""
    language = getattr(request.state, "language", "ja")

    result = await db.execute(
        select(MunicipalityConfig).where(
            MunicipalityConfig.municipality_id == municipality_id
        )
    )
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=get_error_message("municipality_not_found", language),
        )

    # steps JSON を ApplicationStep リストに変換
    steps = [ApplicationStep(**step) for step in (config.steps or [])]

    return MunicipalityConfigResponse(
        municipality_id=config.municipality_id,
        municipality_name=config.municipality_name,
        collection_frequency=config.collection_frequency,
        reception_hours=config.reception_hours,
        collection_rules=config.collection_rules,
        fee_structure_type=config.fee_structure_type,
        application_method=config.application_method,
        web_form_url=config.web_form_url,
        phone_number=config.phone_number,
        steps=steps,
    )


@router.get("/items/{municipality_id}", response_model=BulkyWasteItemListResponse)
async def get_bulky_waste_items(
    municipality_id: str,
    request: Request,
    search: str | None = Query(default=None, description="品目名またはカテゴリの部分一致検索"),
    sort_by: SortBy = Query(default=SortBy.name, description="ソート基準: name または fee"),
    sort_order: SortOrder = Query(default=SortOrder.asc, description="ソート順序: asc または desc"),
    db: AsyncSession = Depends(get_db),
) -> BulkyWasteItemListResponse:
    """自治体の粗大ごみ品目一覧を取得する（最大500件）"""
    language = getattr(request.state, "language", "ja")

    # 自治体存在チェック
    config_result = await db.execute(
        select(MunicipalityConfig).where(
            MunicipalityConfig.municipality_id == municipality_id
        )
    )
    config = config_result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=get_error_message("municipality_not_found", language),
        )

    # クエリ構築
    query = select(BulkyWasteItem).where(
        BulkyWasteItem.municipality_id == municipality_id
    )

    # 検索フィルタ
    if search:
        query = query.where(
            BulkyWasteItem.item_name.contains(search)
            | BulkyWasteItem.category.contains(search)
        )

    # ソート
    if sort_by == SortBy.name:
        order_column = BulkyWasteItem.item_name_kana
    else:
        order_column = BulkyWasteItem.fee_amount

    if sort_order == SortOrder.desc:
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    # 最大500件制限
    query = query.limit(500)

    result = await db.execute(query)
    items = result.scalars().all()

    # 各品目をローカライズ
    item_responses = []
    for item in items:
        localized = await get_localized_item(item, language, db)
        item_responses.append(localized)

    return BulkyWasteItemListResponse(
        items=item_responses,
        total_count=len(item_responses),
        municipality_name=config.municipality_name,
    )


@router.get("/items/{municipality_id}/{item_id}", response_model=BulkyWasteItemResponse)
async def get_bulky_waste_item_detail(
    municipality_id: str,
    item_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> BulkyWasteItemResponse:
    """粗大ごみ品目詳細を取得する"""
    language = getattr(request.state, "language", "ja")

    # 自治体存在チェック
    config_result = await db.execute(
        select(MunicipalityConfig).where(
            MunicipalityConfig.municipality_id == municipality_id
        )
    )
    config = config_result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=get_error_message("municipality_not_found", language),
        )

    # 品目取得
    result = await db.execute(
        select(BulkyWasteItem).where(
            BulkyWasteItem.id == item_id,
            BulkyWasteItem.municipality_id == municipality_id,
        )
    )
    item = result.scalar_one_or_none()

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=get_error_message("item_not_found", language),
        )

    return await get_localized_item(item, language, db)
