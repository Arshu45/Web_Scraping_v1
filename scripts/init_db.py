"""
init_db.py
==========
Creates all database tables (competitors, promotions) if they do not exist.

Usage:
    python scripts/init_db.py
"""

import os
import sys
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import engine, init_db


def ensure_schema_columns():
    """Apply small schema updates for existing local databases."""
    statements = [
        "ALTER TABLE promotions ADD COLUMN IF NOT EXISTS category VARCHAR(100)",
        "ALTER TABLE promotions DROP COLUMN IF EXISTS raw_text",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def main():
    print("🚀 Initializing database...")

    # 1. Test database connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("   ✓ Connection to database successful.")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nPlease check your DATABASE_URL inside the .env file.")
        sys.exit(1)

    # 2. Recreate tables
    try:
        init_db()
        ensure_schema_columns()
        print("   ✓ All tables ('competitors', 'promotions') initialized successfully.")
        print("\n✅ Database is ready!")
        print("\n👉 Next steps:")
        print("   1. python flows/master_pipeline.py  ← run all scrapers")
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
