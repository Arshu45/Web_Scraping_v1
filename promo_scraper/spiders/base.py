import scrapy
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from database.connection import get_session
from database.models import ScrapingSource, Competitor


class BasePromoSpider(scrapy.Spider):
    """
    Base class for all promo spiders.

    Instead of reading config/targets.json, this spider queries the
    `scraping_sources` table in PostgreSQL to determine which URLs to crawl.

    To add a new spider:
        1. Create a new file in spiders/ (e.g., amazon.py)
        2. Inherit from BasePromoSpider
        3. Set name = "amazon"
        4. Implement parse()
    """

    def start_requests(self):
        session = get_session()
        try:
            # Query only enabled sources that match this spider's name
            sources = (
                session.query(ScrapingSource, Competitor)
                .join(Competitor, ScrapingSource.competitor_id == Competitor.id)
                .filter(
                    ScrapingSource.spider_name == self.name,
                    ScrapingSource.enabled == True,
                    Competitor.enabled == True,
                )
                .all()
            )

            if not sources:
                self.logger.warning(
                    f"No enabled sources found for spider '{self.name}'. "
                    f"Check the scraping_sources table."
                )

            for source, competitor in sources:
                self.logger.info(
                    f"Queuing: {competitor.name} → {source.source_url}"
                )
                yield scrapy.Request(
                    url=source.source_url,
                    callback=self.parse,
                    cb_kwargs={
                        'brand': competitor.name,
                        'source_url': source.source_url,
                    }
                )
        finally:
            session.close()
