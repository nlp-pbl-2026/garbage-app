"""データベースモデル"""

from datetime import datetime

from sqlalchemy import String, DateTime, JSON, Integer, Float, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class User(Base):
    """ユーザーテーブル"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)  # male, female, other
    district_id: Mapped[str | None] = mapped_column(String(20), nullable=True)  # e.g. "38201-10"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # ユーザー設定（地域設定等をJSONで保存）
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class MunicipalityConfig(Base):
    """自治体粗大ごみ設定"""
    __tablename__ = "municipality_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    municipality_id: Mapped[str] = mapped_column(String(5), unique=True, index=True, nullable=False)
    municipality_name: Mapped[str] = mapped_column(String(100), nullable=False)
    collection_frequency: Mapped[str] = mapped_column(String(200), nullable=False)
    reception_hours: Mapped[str] = mapped_column(String(200), nullable=False)
    collection_rules: Mapped[str] = mapped_column(String(500), nullable=False)
    fee_structure_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "size_based" | "weight_based" | "fixed"
    application_method: Mapped[str] = mapped_column(String(20), nullable=False)  # "web_form" | "phone" | "both"
    web_form_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    steps: Mapped[list] = mapped_column(JSON, nullable=False)  # 申し込み手順 (JSON array)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BulkyWasteItem(Base):
    """粗大ごみ品目"""
    __tablename__ = "bulky_waste_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    municipality_id: Mapped[str] = mapped_column(
        String(5), ForeignKey("municipality_configs.municipality_id"), nullable=False, index=True
    )
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    item_name_kana: Mapped[str] = mapped_column(String(100), nullable=False)  # 品目名かな（ソート用）
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    fee_amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 手数料(円) 0~99999
    size_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    size_threshold_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    weight_threshold_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 備考（最大200文字）
    garbage_item_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # GarbageItemとのマッピング用品目名


class GarbageItemTranslation(Base):
    """ゴミ品目翻訳テーブル"""
    __tablename__ = "garbage_item_translations"
    __table_args__ = (
        UniqueConstraint("garbage_item_id", "language_code", name="uq_garbage_item_language"),
        CheckConstraint("language_code IN ('ja','en','pt','zh','vi')", name="ck_garbage_item_language_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    garbage_item_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    language_code: Mapped[str] = mapped_column(String(5), nullable=False)
    item_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    disposal_method: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caution: Mapped[str | None] = mapped_column(String(500), nullable=True)
    keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)  # カンマ区切り


class BulkyWasteItemTranslation(Base):
    """粗大ごみ品目翻訳テーブル"""
    __tablename__ = "bulky_waste_item_translations"
    __table_args__ = (
        UniqueConstraint("bulky_waste_item_id", "language_code", name="uq_bulky_waste_item_language"),
        CheckConstraint("language_code IN ('ja','en','pt','zh','vi')", name="ck_bulky_waste_item_language_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bulky_waste_item_id: Mapped[int] = mapped_column(ForeignKey("bulky_waste_items.id"), nullable=False)
    language_code: Mapped[str] = mapped_column(String(5), nullable=False)
    item_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class MunicipalityRomanization(Base):
    """自治体名ローマ字対応テーブル"""
    __tablename__ = "municipality_romanizations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    municipality_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    romanized_name: Mapped[str] = mapped_column(String(100), nullable=False)
