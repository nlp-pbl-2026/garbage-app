"""データベース接続・セッション管理"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """DBセッションの依存性注入用ジェネレータ"""
    async with async_session() as session:
        yield session


async def init_db():
    """データベーステーブルを初期化する"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
