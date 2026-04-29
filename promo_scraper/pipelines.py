import hashlib
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.connection import get_session
from database.models import Competitor, Promotion, ProductSnapshot


def make_offer_hash(source: str, brand: str, title: str) -> str:
    """Generate a stable SHA-256 fingerprint for deduplication."""
    raw = f"{source}|{brand}|{title}".lower().strip()
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class PostgresPipeline:
    """
    Receives OfferItems from any spider and
    upserts them into the PostgreSQL `promotions` table using offer_hash
    for deduplication. Tracks insert/update counts for the audit log.
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
            return item  # Let ProductSnapshotPipeline handle it

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
                offer_title   = title,
                raw_text      = item.get('raw_text'),
                source_name   = source_name,
                source_url    = item.get('source_url'),
                offer_hash    = offer_hash,
                scraped_at    = datetime.utcnow(),
                created_at    = datetime.utcnow(),
                # Allow spiders to directly populate fields if they know them!
                discount_min  = item.get('discount_min'),
                discount_max  = item.get('discount_max'),
                category      = item.get('category'),
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
        # Make stats accessible to Prefect flow via spider object
        spider.pipeline_stats = {
            'items_scraped':  self.items_scraped,
            'items_inserted': self.items_inserted,
            'items_updated':  self.items_updated,
        }


class ProductSnapshotPipeline:
    """
    Receives ProductSnapshotItems and upserts them into `product_snapshots`
    using `product_url` as the unique key (Option B: latest-state only).
    - New product  → INSERT with first_seen_at = now
    - Seen before  → UPDATE prices + last_seen_at (first_seen_at preserved)
    """

    def open_spider(self, spider):
        self.session = get_session()
        self.inserted = 0
        self.updated  = 0
        spider.logger.info('ProductSnapshotPipeline: DB session opened.')

    def process_item(self, item, spider):
        from promo_scraper.items import ProductSnapshotItem
        if not isinstance(item, ProductSnapshotItem):
            return item  # Pass non-matching items through unchanged

        brand_name = item.get('competitor_name', 'unknown')
        competitor = self.session.query(Competitor).filter_by(name=brand_name).first()
        if not competitor:
            # Auto-create direct-brand competitors (e.g. Forever New)
            # They don't come from targets.json / scraping_sources, so we create on first use.
            competitor = Competitor(name=brand_name, enabled=True)
            self.session.add(competitor)
            self.session.flush()  # Get the ID before using it
            spider.logger.info(f"Auto-created competitor '{brand_name}' in DB.")

        now = datetime.utcnow()
        product_url = item.get('product_url')

        existing = self.session.query(ProductSnapshot).filter_by(product_url=product_url).first()

        if existing:
            # Update pricing and timestamp; preserve first_seen_at
            existing.product_name        = item.get('product_name')
            existing.original_price      = item.get('original_price')
            existing.sale_price          = item.get('sale_price')
            existing.discount_percentage = item.get('discount_percentage')
            existing.last_seen_at        = now
            self.updated += 1
        else:
            snapshot = ProductSnapshot(
                competitor_id       = competitor.id,
                product_name        = item.get('product_name'),
                product_url         = product_url,
                category_path       = item.get('category_path'),
                category_label      = item.get('category_label'),
                original_price      = item.get('original_price'),
                sale_price          = item.get('sale_price'),
                discount_percentage = item.get('discount_percentage'),
                first_seen_at       = now,
                last_seen_at        = now,
            )
            self.session.add(snapshot)
            self.inserted += 1

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            spider.logger.error(f"DB commit failed for '{product_url}': {e}")

        return item

    def close_spider(self, spider):
        self.session.close()
        spider.logger.info(
            f'ProductSnapshotPipeline closed. '
            f'Inserted={self.inserted}, Updated={self.updated}'
        )
