"""
Seed Script: Migrates config/targets.json → PostgreSQL DB

Run this ONCE after setting up the database:
    python scripts/seed_db.py

This populates the `competitors` and `scraping_sources` tables
from the existing targets.json, making the DB the new source of truth.
"""

import json
import os
import sys

# Make sure project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session, init_db
from database.models import Competitor, ScrapingSource, Category

# Master category seed data
MASTER_CATEGORIES = [
    "Apparel", "Footwear", "Beauty & Personal Care",
    "Accessories", "Jewellery", "Home & Decor",
    "Kids", "Sports & Fitness", "Electronics",
]


def seed_categories(session):
    print("→ Seeding master categories...")
    for cat_name in MASTER_CATEGORIES:
        exists = session.query(Category).filter_by(name=cat_name).first()
        if not exists:
            session.add(Category(name=cat_name))
    session.commit()
    print(f"  ✓ {len(MASTER_CATEGORIES)} categories seeded.")


def seed_from_targets(session):
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'targets.json')

    with open(config_path, 'r') as f:
        config = json.load(f)

    inserted_competitors = 0
    inserted_sources = 0

    for source in config.get('sources', []):
        spider_name = source['name']

        for brand in source.get('brands', []):
            brand_name = brand['name']

            # Upsert competitor
            competitor = session.query(Competitor).filter_by(name=brand_name).first()
            if not competitor:
                competitor = Competitor(
                    name=brand_name,
                    category="Fashion",
                    enabled=True,
                )
                session.add(competitor)
                session.flush()  # Get the ID before adding sources
                inserted_competitors += 1
                print(f"  ✓ Added competitor: {brand_name}")
            
            # Upsert scraping source
            src = session.query(ScrapingSource).filter_by(source_url=brand['url']).first()
            if not src:
                src = ScrapingSource(
                    competitor_id=competitor.id,
                    source_name=spider_name,
                    source_url=brand['url'],
                    spider_name=spider_name,
                    enabled=brand.get('enabled', True),
                )
                session.add(src)
                inserted_sources += 1
                print(f"  ✓ Added source: {spider_name} → {brand['url']}")

    session.commit()
    print(f"\n✅ Seed complete: {inserted_competitors} competitors, {inserted_sources} sources added.")


if __name__ == "__main__":
    print("🌱 Initializing database tables...")
    init_db()

    session = get_session()
    try:
        seed_categories(session)
        print("\n→ Seeding competitors and scraping sources from targets.json...")
        seed_from_targets(session)
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()
