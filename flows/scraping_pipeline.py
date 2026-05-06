"""
Prefect Orchestration Flow: Promo Scraper Pipeline

Orchestrates the full pipeline as 4 chained tasks:
    1. log_run_start  → creates a scraping_run record
    2. run_spider     → executes the Scrapy spider via CrawlerProcess
    3. enrich_data    → runs GLiNER on new unenriched promotions
    4. log_run_end    → finalises the scraping_run with stats and status

Usage:
    # Run once manually:
    python flows/scraping_pipeline.py coupondunia

    # Or deploy via Prefect UI / schedule:
    prefect deploy flows/scraping_pipeline.py
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from prefect import flow, task, get_run_logger
from prefect.context import get_run_context

from database.connection import get_session
from database.models import ScrapingRun
from enrichment.enricher import enrich_promotions


# ─────────────────────────────────────────────
# Task 1: Log the start of this run
# ─────────────────────────────────────────────
@task(name="Log Run Start")
def log_run_start(spider_name: str) -> int:
    logger = get_run_logger()
    session = get_session()

    try:
        # Try to get the Prefect flow run ID for traceability
        try:
            prefect_run_id = str(get_run_context().flow_run.id)
        except Exception:
            prefect_run_id = None

        run = ScrapingRun(
            spider_name    = spider_name,
            prefect_run_id = prefect_run_id,
            started_at     = datetime.now(timezone.utc),
            status         = 'running',
        )
        session.add(run)
        session.commit()
        run_id = run.id
        logger.info(f"Scraping run #{run_id} started for spider '{spider_name}'.")
        return run_id
    finally:
        session.close()


# ─────────────────────────────────────────────
# Task 2: Execute the Scrapy spider
# ─────────────────────────────────────────────
@task(name="Run Spider", retries=2, retry_delay_seconds=30)
def run_spider(spider_name: str) -> dict:
    logger = get_run_logger()
    logger.info(f"Starting Scrapy spider: {spider_name}")

    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    from scrapy import signals

    stats_holder = {}

    settings = get_project_settings()
    process = CrawlerProcess(settings)
    crawler = process.create_crawler(spider_name)

    # Capture stats when spider closes
    def on_spider_closed(spider, reason):
        stats_holder.update(getattr(spider, 'pipeline_stats', {}))

    crawler.signals.connect(on_spider_closed, signal=signals.spider_closed)
    process.crawl(crawler)
    process.start()  # Blocks until spider finishes

    logger.info(f"Spider '{spider_name}' finished. Stats: {stats_holder}")
    return stats_holder


# ─────────────────────────────────────────────
# Task 3: GLiNER enrichment pass
# ─────────────────────────────────────────────
@task(name="Enrich Data with GLiNER")
def enrich_data(batch_size: int = 100) -> dict:
    logger = get_run_logger()
    logger.info("Starting GLiNER enrichment pass...")
    summary = enrich_promotions(batch_size=batch_size)
    logger.info(f"Enrichment done: {summary}")
    return summary


# ─────────────────────────────────────────────
# Task 4: Log the end of this run
# ─────────────────────────────────────────────
@task(name="Log Run End")
def log_run_end(run_id: int, spider_stats: dict, enrichment_summary: dict):
    logger = get_run_logger()
    session = get_session()
    try:
        run = session.get(ScrapingRun, run_id)
        if run:
            run.finished_at     = datetime.now(timezone.utc)
            run.status          = 'success'
            run.items_scraped   = spider_stats.get('items_scraped', 0)
            run.items_inserted  = spider_stats.get('items_inserted', 0)
            run.items_updated   = spider_stats.get('items_updated', 0)
            session.commit()
        logger.info(f"Scraping run #{run_id} marked as success. Stats: {spider_stats}")
    finally:
        session.close()


# ─────────────────────────────────────────────
# The Main Flow
# ─────────────────────────────────────────────
@flow(name="Promo Scraper Pipeline", log_prints=True)
def scraping_pipeline(spider_name: str, enrich_batch_size: int = 100):
    """
    Full pipeline: scrape → store in Postgres → enrich with GLiNER → log.
    """
    run_id             = log_run_start(spider_name)
    spider_stats       = run_spider(spider_name)
    enrichment_summary = enrich_data(enrich_batch_size)
    log_run_end(run_id, spider_stats, enrichment_summary)


if __name__ == "__main__":
    spider = sys.argv[1] if len(sys.argv) > 1 else "coupondunia"
    scraping_pipeline(spider_name=spider)
