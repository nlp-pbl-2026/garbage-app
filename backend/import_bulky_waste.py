"""S3/ローカルのCSVから粗大ごみ品目データをDBにインポートするスクリプト。

あいまい検索(RAG)で使用している items.csv と同じデータソースから、
category == "粗大" のレコードを抽出し、bulky_waste_items テーブルに投入する。
MunicipalityConfig が未登録の場合は松山市のデフォルト設定も作成する。

使い方:
    python import_bulky_waste.py
    python import_bulky_waste.py --csv path/to/items.csv
    python import_bulky_waste.py --s3-bucket my-bucket --s3-key path/to/items.csv
"""

import asyncio
import argparse
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, async_session, init_db
from app.models import BulkyWasteItem, MunicipalityConfig


# 松山市のデフォルト municipality_id
MATSUYAMA_MUNICIPALITY_ID = "38201"

# デフォルトのCSVパス（あいまい検索と同じファイル）
DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "regions" / "matsuyama" / "common" / "knowledge" / "items.csv"


def parse_args():
    parser = argparse.ArgumentParser(description="粗大ごみ品目データをCSVからDBにインポート")
    parser.add_argument("--csv", type=str, default=None, help="ローカルCSVファイルのパス")
    parser.add_argument("--s3-bucket", type=str, default=None, help="S3バケット名")
    parser.add_argument("--s3-key", type=str, default=None, help="S3オブジェクトキー")
    parser.add_argument("--municipality-id", type=str, default=MATSUYAMA_MUNICIPALITY_ID, help="自治体ID（デフォルト: 38201 松山市）")
    parser.add_argument("--clear", action="store_true", help="インポート前に既存データを削除")
    return parser.parse_args()


def download_from_s3(bucket: str, key: str) -> Path:
    """S3からCSVファイルをダウンロードして一時ファイルのパスを返す。"""
    import boto3
    s3 = boto3.client("s3")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    s3.download_file(bucket, key, tmp.name)
    print(f"S3からダウンロード完了: s3://{bucket}/{key} → {tmp.name}")
    return Path(tmp.name)


def load_bulky_items_from_csv(csv_path: Path) -> list[dict]:
    """CSVファイルから category == "粗大" のレコードを読み込む。"""
    items = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("category") == "粗大":
                items.append({
                    "item_name": row.get("item", "").strip(),
                    "item_name_kana": row.get("reading", "").strip() or "",
                    "notes": row.get("note", "").strip() or None,
                    "item_id": row.get("item_id", "").strip(),
                })
    return items


async def ensure_municipality_config(session: AsyncSession, municipality_id: str):
    """MunicipalityConfigが存在しなければ松山市のデフォルト設定を作成する。"""
    result = await session.execute(
        select(MunicipalityConfig).where(
            MunicipalityConfig.municipality_id == municipality_id
        )
    )
    config = result.scalar_one_or_none()

    if config is not None:
        print(f"MunicipalityConfig 既存: {config.municipality_name} ({municipality_id})")
        return

    new_config = MunicipalityConfig(
        municipality_id=municipality_id,
        municipality_name="松山市",
        collection_frequency="年6回（申込区分ごとに受付期間が異なります）",
        reception_hours="粗大ごみ収集申込みガイドで受付期間を確認",
        collection_rules="ハガキまたはインターネットで事前に申し込み、収集日当日の午前8時までに粗大ごみシールを貼って指定場所へ排出。収集は無料。",
        fee_structure_type="fixed",
        application_method="web_form",
        web_form_url="https://www.city.matsuyama.ehime.jp/kurashi/gomi/dashikata/sodaigomi.html",
        phone_number="089-921-5516",
        steps=[
            {"step_number": 1, "title": "申込区分の確認", "description": "住所がA〜Dのどの申込区分に該当するか、公式の申込みガイドで確認します。", "notes": None},
            {"step_number": 2, "title": "申込期間の確認", "description": "申込区分ごとに定められた受付期間を確認します。", "notes": None},
            {"step_number": 3, "title": "申し込み", "description": "専用ハガキまたはインターネットで申し込みます。", "notes": "インターネット申込みには、えひめ電子申請システムへの登録が必要です。"},
            {"step_number": 4, "title": "収集日の連絡", "description": "収集日の約1週間前に、粗大ごみシール付きの通知ハガキが届きます。", "notes": None},
            {"step_number": 5, "title": "排出", "description": "収集日当日の午前8時までに、シールを貼って申込時の指定場所へ出します。", "notes": None},
        ],
    )
    session.add(new_config)
    await session.flush()
    print(f"MunicipalityConfig 作成完了: 松山市 ({municipality_id})")


async def import_items(
    session: AsyncSession,
    items: list[dict],
    municipality_id: str,
    clear: bool = False,
):
    """粗大ごみ品目をDBにインポートする。"""
    if clear:
        await session.execute(
            delete(BulkyWasteItem).where(
                BulkyWasteItem.municipality_id == municipality_id
            )
        )
        print(f"既存の粗大ごみ品目を削除しました（municipality_id={municipality_id}）")

    # 既存品目名を取得して重複チェック用に使う
    existing_result = await session.execute(
        select(BulkyWasteItem.item_name).where(
            BulkyWasteItem.municipality_id == municipality_id
        )
    )
    existing_names = {row[0] for row in existing_result.all()}

    inserted_count = 0
    skipped_count = 0

    for item_data in items:
        item_name = item_data["item_name"]
        if not item_name:
            continue

        if item_name in existing_names:
            skipped_count += 1
            continue

        new_item = BulkyWasteItem(
            municipality_id=municipality_id,
            item_name=item_name,
            item_name_kana=item_data["item_name_kana"],
            category="粗大ごみ",
            fee_amount=0,  # 松山市の戸別収集は無料
            size_category=None,
            size_threshold_cm=None,
            weight_category=None,
            weight_threshold_kg=None,
            notes=item_data["notes"],
            garbage_item_name=item_name,  # あいまい検索との連携用
        )
        session.add(new_item)
        existing_names.add(item_name)
        inserted_count += 1

    await session.flush()
    print(f"インポート完了: {inserted_count}件追加, {skipped_count}件スキップ（既存）")


async def main():
    args = parse_args()

    # CSVファイルの決定
    if args.s3_bucket and args.s3_key:
        csv_path = download_from_s3(args.s3_bucket, args.s3_key)
    elif args.csv:
        csv_path = Path(args.csv)
    else:
        csv_path = DEFAULT_CSV_PATH

    if not csv_path.exists():
        print(f"エラー: CSVファイルが見つかりません: {csv_path}")
        sys.exit(1)

    print(f"CSVファイル: {csv_path}")

    # CSV読み込み
    items = load_bulky_items_from_csv(csv_path)
    print(f"粗大ごみ品目数: {len(items)}件")

    if not items:
        print("インポートする品目がありません。")
        return

    # DB初期化（テーブルがなければ作成）
    await init_db()

    # インポート実行
    async with async_session() as session:
        async with session.begin():
            await ensure_municipality_config(session, args.municipality_id)
            await import_items(session, items, args.municipality_id, clear=args.clear)

    print("完了!")


if __name__ == "__main__":
    asyncio.run(main())
