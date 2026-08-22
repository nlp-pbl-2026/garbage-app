"""Database migration script to add translation tables.

Creates the following tables:
- garbage_item_translations: Translations for garbage item fields (item_name, disposal_method, caution, keywords)
- bulky_waste_item_translations: Translations for bulky waste item fields (item_name, notes)
- municipality_romanizations: Romanized names for municipality names

Each translation table has:
- UNIQUE constraint on (item_id, language_code) to prevent duplicate translations
- CHECK constraint on language_code to only allow supported values (ja, en, pt, zh, vi)
"""
import asyncio
import sys
sys.path.insert(0, r"c:\dev\garbage-app\backend")

from sqlalchemy import text
from app.database import engine


async def main():
    async with engine.begin() as conn:
        # Create garbage_item_translations table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS garbage_item_translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                garbage_item_id TEXT NOT NULL,
                language_code TEXT NOT NULL CHECK(language_code IN ('ja','en','pt','zh','vi')),
                item_name TEXT,
                disposal_method TEXT,
                caution TEXT,
                keywords TEXT,
                UNIQUE(garbage_item_id, language_code)
            )
        """))

        # Create index on garbage_item_id for faster lookups
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_garbage_item_translations_garbage_item_id
            ON garbage_item_translations(garbage_item_id)
        """))

        # Create bulky_waste_item_translations table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bulky_waste_item_translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bulky_waste_item_id INTEGER NOT NULL REFERENCES bulky_waste_items(id),
                language_code TEXT NOT NULL CHECK(language_code IN ('ja','en','pt','zh','vi')),
                item_name TEXT,
                notes TEXT,
                UNIQUE(bulky_waste_item_id, language_code)
            )
        """))

        # Create municipality_romanizations table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS municipality_romanizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                municipality_name TEXT NOT NULL UNIQUE,
                romanized_name TEXT NOT NULL
            )
        """))

    print("Translation tables migration completed successfully.")
    print("Created tables:")
    print("  - garbage_item_translations")
    print("  - bulky_waste_item_translations")
    print("  - municipality_romanizations")


if __name__ == "__main__":
    asyncio.run(main())
