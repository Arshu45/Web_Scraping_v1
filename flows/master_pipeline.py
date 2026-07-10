"""
Master Prefect Flow: Runs ALL configured brand targets in parallel.

This is the primary entry point for the concurrent hybrid scraping operation.

Usage:
    python flows/master_pipeline.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from prefect import flow, task, get_run_logger

# ─────────────────────────────────────────────
# Task: Scrape a SINGLE brand target (runs concurrently via .map)
# ─────────────────────────────────────────────
@task(name="Scrape Brand Target", retries=1, retry_delay_seconds=15)
def scrape_brand_target(target: dict) -> dict:
    """
    Runs the hybrid extractor for ONE brand.
    Prefect will run all mapped instances concurrently.
    Each task owns its own DB session — safe for parallel execution.
    """
    logger = get_run_logger()
    logger.info("[%s] Starting extraction...", target.get('brand', '?'))
    from scripts.run_hybrid_promo_scraper import scrape_single_target
    try:
        return scrape_single_target(target)
    except Exception as e:
        logger.error("[%s] Task failed: %s", target.get('brand', '?'), e)
        return {"brand": target.get("brand", "unknown"), "error": str(e)}


# ─────────────────────────────────────────────
# Task: Print the final checklist / report
# ─────────────────────────────────────────────
@task(name="Generate Summary Report")
def generate_report(hybrid_results: list[dict]):
    logger = get_run_logger()

    report_lines = [
        "",
        "╔══════════════════════════════════════════════╗",
        "║         PROMO SCRAPER - RUN SUMMARY          ║",
        "╠══════════════════════════════════════════════╣",
        "║  HYBRID PROMO SCRAPER RESULTS                ║",
        "╠══════════════════════════════════════════════╣",
    ]

    for h in hybrid_results:
        brand = h.get("brand", "Unknown")
        if "error" in h:
            report_lines.append(f"║  ❌ {brand:<14} | ERROR: {h['error'][:23]:<24} ║")
        else:
            offers = h.get("offers_extracted", 0)
            stored = h.get("offers_stored", 0)
            cost = h.get("estimated_cost_usd", 0.0)
            report_lines.append(f"║  ✓ {brand:<14} | Offers: {offers:<3} | Stored: {stored:<3} | Cost: ${cost:.6f} ║")

    report_lines.append("╚══════════════════════════════════════════════╝")
    report = "\n".join(report_lines)

    logger.info(report)


# ─────────────────────────────────────────────
# THE MASTER FLOW
# ─────────────────────────────────────────────
# Each brand target spins up its own Playwright Chromium instance. Submitting
# all targets at once (unbounded .map()) launches that many browsers
# simultaneously, which can exhaust system memory. Cap how many run at a time.
MAX_CONCURRENT_BROWSERS = 3


@flow(name="Master Promo Scraper Pipeline", log_prints=True)
def master_pipeline():
    """
    1. Loads all brand targets from config/targets/*.json.
    2. Runs the hybrid promo scraper for all configured brands, batching
       concurrent extraction so at most MAX_CONCURRENT_BROWSERS browsers
       are open at once.
    3. Prints a full checklist summary report.
    """
    logger = get_run_logger()
    logger.info("🚀 Master pipeline starting...")

    from scripts.run_hybrid_promo_scraper import load_targets
    targets = load_targets()
    logger.info(
        "Running %d brand targets, %d at a time...",
        len(targets), MAX_CONCURRENT_BROWSERS,
    )

    hybrid_results = []
    for i in range(0, len(targets), MAX_CONCURRENT_BROWSERS):
        batch = targets[i:i + MAX_CONCURRENT_BROWSERS]
        batch_futures = scrape_brand_target.map(batch)
        hybrid_results.extend(f.result() for f in batch_futures)

    generate_report(hybrid_results)


if __name__ == "__main__":
    master_pipeline()
