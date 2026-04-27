"""
Reset Script: Clears all data tables and re-seeds from targets.json.

This does NOT drop the schema (tables stay). It only deletes all rows
so you can run a fresh scrape from scratch.

Usage:
    python scripts/reset_db.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import Promotion, ScrapingRun, ScrapingSource, Competitor


def reset_all_tables(session):
    print("🗑️  Clearing all tables...")

    # Order matters — delete child tables before parents (foreign key constraints)
    counts = {
        'promotions':       session.query(Promotion).delete(),
        'scraping_runs':    session.query(ScrapingRun).delete(),
        'scraping_sources': session.query(ScrapingSource).delete(),
        'competitors':      session.query(Competitor).delete(),
    }
    session.commit()

    for table, count in counts.items():
        print(f"   ✓ {table}: {count} rows deleted")


if __name__ == "__main__":
    confirm = input(
        "\n⚠️  This will DELETE ALL rows from promotions, competitors, "
        "scraping_sources, and scraping_runs.\n"
        "   Type 'yes' to continue: "
    ).strip().lower()

    if confirm != 'yes':
        print("Aborted. No changes made.")
        sys.exit(0)

    session = get_session()
    try:
        reset_all_tables(session)
        print("\n✅ All tables cleared.")
        print("\n👉 Next steps:")
        print("   1. python scripts/seed_db.py       ← re-seed targets")
        print("   2. python flows/master_pipeline.py  ← run all spiders")
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()
