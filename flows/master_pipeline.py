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

    # Update the DB run record
    session = get_session()
    try:
        run = session.get(ScrapingRun, run_id)
        if run:
            run.finished_at = finished_at
            run.status      = 'success' if success else 'failed'
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
        'started_at': started_at.isoformat(),
        'finished_at': finished_at.isoformat(),
    }


# ─────────────────────────────────────────────
# Task 3: GLiNER / enrichment pass
# ─────────────────────────────────────────────
@task(name="Enrich All Data with GLiNER")
def enrich_all(batch_size: int = 200) -> dict:
    logger = get_run_logger()
    logger.info("Starting GLiNER enrichment pass on all new promotions...")
    summary = enrich_promotions(batch_size=batch_size)
    logger.info(f"Enrichment complete: {summary}")
    return summary


# ─────────────────────────────────────────────
# Task 4: Print the final checklist / report
# ─────────────────────────────────────────────
@task(name="Generate Summary Report")
def generate_report(spider_results: list[dict], enrichment_summary: dict):
    logger = get_run_logger()

    passed = [r for r in spider_results if r.get('success')]
    failed = [r for r in spider_results if not r.get('success')]

    report_lines = [
        "",
        "╔══════════════════════════════════════════════╗",
        "║         PROMO SCRAPER - RUN SUMMARY          ║",
        "╠══════════════════════════════════════════════╣",
        f"║  Total Spiders  : {len(spider_results):<27}║",
        f"║  ✅ Passed       : {len(passed):<27}║",
        f"║  ❌ Failed       : {len(failed):<27}║",
        f"║  💡 Enriched    : {enrichment_summary.get('enriched', 0):<27}║",
        "╠══════════════════════════════════════════════╣",
        "║  SPIDER CHECKLIST                            ║",
        "╠══════════════════════════════════════════════╣",
    ]

    for r in spider_results:
        icon   = "✅" if r.get('success') else "❌"
        name   = r.get('spider', 'unknown')
        run_id = r.get('run_id', '?')
        report_lines.append(f"║  {icon} {name:<20} (run #{run_id}){' ' * (8 - len(str(run_id)))}║")

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
def master_pipeline(enrich_batch_size: int = 200):
    """
    Discovers all enabled spiders from the DB and runs them ALL
    in parallel subprocesses. After all complete, runs GLiNER
    enrichment and prints a full checklist report.
    """
    logger = get_run_logger()
    logger.info("🚀 Master pipeline starting...")

    # Step 1: Discover all active spiders from DB
    spider_names = get_active_spiders()

    if not spider_names:
        logger.warning("No active spiders found. Exiting.")
        return

    # Step 2: Run all spiders in parallel using Prefect's .map()
    # Each spider gets its own subprocess — no reactor conflicts
    spider_results = run_spider_subprocess.map(spider_names)

    # Step 3: GLiNER enrichment after all spiders are done
    enrichment_summary = enrich_all(enrich_batch_size, wait_for=spider_results)

    # Step 4: Print checklist report
    generate_report(spider_results, enrichment_summary)


if __name__ == "__main__":
    master_pipeline()
