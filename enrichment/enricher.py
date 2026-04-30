"""
Enrichment Dispatcher

Reads ENRICHMENT_PROVIDER from .env and routes to the correct engine:
    - "gliner" → enrichment/gliner_extractor.py  (local model, no API key needed)
    - "groq"   → enrichment/llm_extractor.py     (Groq API, fast, requires GROQ_API_KEY)

Usage in any Python file:
    from enrichment.enricher import enrich_promotions
    enrich_promotions(batch_size=100)

The Prefect flow (master_pipeline.py, scraping_pipeline.py) imports from here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

ENRICHMENT_PROVIDER = os.getenv("ENRICHMENT_PROVIDER", "gliner").lower().strip()

SUPPORTED_PROVIDERS = ("gliner", "groq")

if ENRICHMENT_PROVIDER not in SUPPORTED_PROVIDERS:
    raise ValueError(
        f"Invalid ENRICHMENT_PROVIDER='{ENRICHMENT_PROVIDER}'. "
        f"Choose from: {SUPPORTED_PROVIDERS}"
    )

# Route to the correct module
if ENRICHMENT_PROVIDER == "groq":
    from enrichment.llm_extractor import enrich_promotions
    enrich_product_categories = lambda: {'unique_labels_enriched': 0, 'total_products_updated': 0} # LLM mapping not supported yet
    print(f"[Enricher] Provider: Groq LLM (model: {os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')})")
else:
    from enrichment.gliner_extractor import enrich_promotions, enrich_product_categories
    print(f"[Enricher] Provider: GLiNER (local model)")

__all__ = ["enrich_promotions", "enrich_product_categories"]
