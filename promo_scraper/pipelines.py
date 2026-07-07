import hashlib
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.connection import get_session
from database.models import Competitor, Promotion


def make_offer_hash(source: str, brand: str, title: str) -> str:
    """Generate a stable SHA-256 fingerprint for deduplication."""
    raw = f"{source}|{brand}|{title}".lower().strip()
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class PostgresPipeline:
    """
    Receives OfferItems from any spider and
    upserts them into the PostgreSQL `promotions` table using offer_hash
    for deduplication.
    """

    def open_spider(self, spider):
        self.session = get_session()
        self.items_scraped = 0
        self.items_inserted = 0
        self.items_updated = 0
        spider.logger.info("PostgresPipeline: DB session opened.")

    def process_item(self, item, spider):
        from promo_scraper.items import OfferItem
        if not isinstance(item, OfferItem):
            return item

        self.items_scraped += 1

        brand_name  = item.get('brand', 'unknown')
        source_name = item.get('source', 'unknown')
        title       = item.get('title', '')

        # 1. Look up competitor_id from DB
        competitor = self.session.query(Competitor).filter_by(name=brand_name).first()
        if not competitor:
            spider.logger.warning(f"Competitor '{brand_name}' not found in DB. Skipping item.")
            return item

        # 2. Generate deduplication hash
        offer_hash = make_offer_hash(source_name, brand_name, title)

        # 3. Upsert: check if offer already exists
        existing = self.session.query(Promotion).filter_by(offer_hash=offer_hash).first()

        if existing:
            # Update only the scraped_at timestamp — don't duplicate
            existing.scraped_at = datetime.utcnow()
            self.items_updated += 1
        else:
            # Insert new promotion
            promotion = Promotion(
                competitor_id = competitor.id,
                brand         = brand_name,
                offer_title   = title,
                raw_text      = item.get('raw_text'),
                source_name   = source_name,
                source_url    = item.get('source_url'),
                offer_hash    = offer_hash,
                scraped_at    = datetime.utcnow(),
                created_at    = datetime.utcnow(),
            )
            self.session.add(promotion)
            self.items_inserted += 1

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            spider.logger.error(f"DB commit failed for item '{title[:50]}': {e}")

        return item

    def close_spider(self, spider):
        self.session.close()
        spider.logger.info(
            f"PostgresPipeline closed. "
            f"Scraped={self.items_scraped}, "
            f"Inserted={self.items_inserted}, "
            f"Updated={self.items_updated}"
        )
        spider.pipeline_stats = {
            'items_scraped':  self.items_scraped,
            'items_inserted': self.items_inserted,
            'items_updated':  self.items_updated,
        }
