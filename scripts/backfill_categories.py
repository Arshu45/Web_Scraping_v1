"""
Backfill script to apply the master category mapping to existing product snapshots.
"""

import sys
import os

# Ensure the root of the project is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import ProductSnapshot
from enrichment.gliner_extractor import enrich_product_categories
from sqlalchemy import text

def backfill():
    session = get_session()
    try:
        # Reset all master categories to None to force re-enrichment
        print("Resetting existing master categories...")
        session.execute(text("UPDATE product_snapshots SET master_category = NULL"))
        session.commit()
        print("Reset complete.")
        
        # Run the new AI enricher
        enrich_product_categories()
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error during backfill: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    backfill()
