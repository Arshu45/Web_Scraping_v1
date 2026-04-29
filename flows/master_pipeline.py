"""
Master Prefect Flow: Runs ALL enabled spiders in parallel.

This is the primary entry point for the full scraping operation.

Usage:
    python flows/master_pipeline.py

What it does:
    1. Queries the DB for all distinct, enabled spider names
    2. Runs each spider in a SEPARATE subprocess in parallel
       (avoids Twisted reactor conflicts)
    3. Tracks success/failure per spider with a checklist
    4. Runs one GLiNER enrichment pass after all spiders complete
    5. Logs a final summary report to the console
"""

import sys
import os
import subprocess
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from prefect import flow, task, get_run_logger
from prefect.context import get_run_context

from database.connection import get_session
from database.models import ScrapingRun, ScrapingSource
from enrichment.enricher import enrich_promotions


# ─────────────────────────────────────────────
# Task 1: Discover all active spider names from DB
# ─────────────────────────────────────────────
@task(name="Discover Active Spiders")
def get_active_spiders() -> list[str]:
    logger = get_run_logger()
    session = get_session()
    try:
        rows = (
            session.query(ScrapingSource.spider_name)
            .filter(ScrapingSource.enabled == True)
            .distinct()
            .all()
        )
        spider_names = [r.spider_name for r in rows]
        logger.info(f"Found {len(spider_names)} active spider(s): {spider_names}")
        return spider_names
    finally:
        session.close()


# ─────────────────────────────────────────────
# Task 2: Run a single spider in a subprocess
# ─────────────────────────────────────────────
@task(name="Run Spider Subprocess", retries=1, retry_delay_seconds=30)
def run_spider_subprocess(spider_name: str) -> dict:
    """
    Runs a Scrapy spider in a dedicated subprocess.
    Using subprocess avoids the Twisted reactor conflict when
    running multiple spiders within the same Python process.
    """
    logger = get_run_logger()
    logger.info(f"[{spider_name}] Starting spider subprocess...")

    started_at = datetime.now(timezone.utc)
    session = get_session()

    # Log this spider run to the DB
    try:
        try:
            prefect_run_id = str(get_run_context().flow_run.id)
        except Exception:
            prefect_run_id = None

        run = ScrapingRun(
            spider_name    = spider_name,
            prefect_run_id = prefect_run_id,
            started_at     = started_at,
            status         = 'running',
        )
        session.add(run)
        session.commit()
        run_id = run.id
    finally:
        session.close()

    # Run the spider as a subprocess
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        [sys.executable, '-m', 'scrapy', 'crawl', spider_name],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    finished_at = datetime.now(timezone.utc)
    success = result.returncode == 0

    import re
    scraped = 0
    inserted = 0
    updated = 0

    # Try PostgresPipeline stats first (aggregator spiders)
    stats_match = re.search(r"PostgresPipeline closed\. Scraped=(\d+), Inserted=(\d+), Updated=(\d+)", result.stderr)
    if stats_match:
        scraped  = int(stats_match.group(1))
        inserted = int(stats_match.group(2))
        updated  = int(stats_match.group(3))

    # For direct-catalog spiders (forevernew_products), use ProductSnapshotPipeline stats
    snap_match = re.search(r"ProductSnapshotPipeline closed\. Inserted=(\d+), Updated=(\d+)", result.stderr)
    if snap_match:
        snap_ins = int(snap_match.group(1))
        snap_upd = int(snap_match.group(2))
        # Use snapshot stats if they have actual data (postgres stats will show 0 for these)
        if snap_ins + snap_upd > 0:
            inserted = snap_ins
            updated  = snap_upd
            scraped  = snap_ins + snap_upd

    # Update the DB run record
    session = get_session()
    try:
        run = session.get(ScrapingRun, run_id)
        if run:
            run.finished_at = finished_at
            run.status      = 'success' if success else 'failed'
            run.items_scraped = scraped
            run.items_inserted = inserted
            run.items_updated = updated
            session.commit()
    finally:
        session.close()

    if success:
        logger.info(f"[{spider_name}] ✅ Completed successfully.")
    else:
        logger.error(
            f"[{spider_name}] ❌ Failed (exit code {result.returncode}).\n"
            f"STDERR: {result.stderr[-500:] if result.stderr else 'none'}"
        )

    return {
        'spider': spider_name,
        'run_id': run_id,
        'success': success,
        'returncode': result.returncode,
        'items_scraped': scraped,
        'items_inserted': inserted,
        'items_updated': updated,
        'started_at': started_at.isoformat(),
        'finished_at': finished_at.isoformat(),
    }

# ─────────────────────────────────────────────
# Task 4: GLiNER / enrichment pass
# ─────────────────────────────────────────────
@task(name="Enrich Data")
def enrich_all(batch_size: int = 200) -> dict:
    logger = get_run_logger()
    logger.info("Starting enrichment pass on all new promotions...")
    summary = enrich_promotions(batch_size=batch_size)
    logger.info(f"Enrichment complete: {summary}")
    return summary


# ─────────────────────────────────────────────
# Task: Print the final checklist / report
# ─────────────────────────────────────────────
@task(name="Generate Summary Report")
def generate_report(spider_results: list[dict], enrichment_summary: dict):
    logger = get_run_logger()

    passed = [r for r in spider_results if r.get('success')]
    failed = [r for r in spider_results if not r.get('success')]

    # Separate out the forevernew snapshot stats for the summary header
    fn_result = next((r for r in spider_results if r.get('spider') == 'forevernew_products'), {})
    fn_ins = fn_result.get('items_inserted', 0)
    fn_upd = fn_result.get('items_updated', 0)

    report_lines = [
        "",
        "╔══════════════════════════════════════════════╗",
        "║         PROMO SCRAPER - RUN SUMMARY          ║",
        "╠══════════════════════════════════════════════╣",
        f"║  Total Spiders  : {len(spider_results):<27}║",
        f"║  ✅ Passed       : {len(passed):<27}║",
        f"║  ❌ Failed       : {len(failed):<27}║",
        f"║  💡 Enriched    : {enrichment_summary.get('enriched', 0):<27}║",
        f"║  📸 Products (new): {fn_ins:<25}║",
        f"║  🔄 Products (upd): {fn_upd:<25}║",
        "╠══════════════════════════════════════════════╣",
        "║  SPIDER CHECKLIST                            ║",
        "╠══════════════════════════════════════════════╣",
    ]

    for r in spider_results:
        icon    = "✅" if r.get('success') else "❌"
        name    = r.get('spider', 'unknown')
        run_id  = str(r.get('run_id', '-'))
        scraped  = r.get('items_scraped', 0)
        inserted = r.get('items_inserted', 0)
        report_lines.append(f"║  {icon} {name:<14} (run #{run_id:<3}) | Scraped: {scraped:<4} | Inserted: {inserted:<4} ║")

    if failed:
        report_lines.append("╠══════════════════════════════════════════════╣")
        report_lines.append("║  FAILED SPIDERS — NEEDS ATTENTION            ║")
        report_lines.append("╠══════════════════════════════════════════════╣")
        for r in failed:
            report_lines.append(f"║  ⚠️  {r.get('spider'):<41}║")

    report_lines.append("╚══════════════════════════════════════════════╝")
    report = "\n".join(report_lines)

    logger.info(report)

    return {
        'total': len(spider_results),
        'passed': len(passed),
        'failed': len(failed),
    }


# ─────────────────────────────────────────────
# THE MASTER FLOW
# ─────────────────────────────────────────────
@flow(name="Master Promo Scraper Pipeline", log_prints=True)
def master_pipeline(enrich_batch_size: int = 50):
    """
    1. Discovers ALL enabled spiders from the DB (including forevernew_products) and runs them in parallel.
    2. Runs GLiNER enrichment on new aggregator promotions.
    3. Prints a full checklist summary report.
    """
    logger = get_run_logger()
    logger.info("🚀 Master pipeline starting...")

    # Step 1: Discover all active spiders from DB (grabon, coupondunia, forevernew_products, ...)
    spider_names = get_active_spiders()

    if not spider_names:
        logger.warning("No active spiders found in DB.")

    # Step 2: Run ALL spiders in parallel (aggregator + catalog crawlers)
    spider_futures = run_spider_subprocess.map(spider_names) if spider_names else []

    # Step 3: Wait for aggregator spiders, then run enrichment
    # Note: forevernew_products writes directly to product_snapshots — no enrichment needed
    enrichment_summary = enrich_all(enrich_batch_size, wait_for=spider_futures)

    # Step 4: Collect results and print report
    spider_results = [f.result() for f in spider_futures]
    generate_report(spider_results, enrichment_summary)


if __name__ == "__main__":
    master_pipeline()
