"""Run database migration to create new tables."""
import asyncio
import sys
sys.path.insert(0, r"c:\dev\garbage-app\backend")

from app.database import init_db


async def main():
    await init_db()
    print("Database migration completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
