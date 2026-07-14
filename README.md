# Retail Competitive Intelligence Scraper

A production-grade, concurrent hybrid competitive intelligence system. The platform scrapes promotional offers directly from competitor websites, extracts text and visual banner offers, assigns reporting categories with an LLM, deduplicates by source page, and stores clean promotion rows in PostgreSQL for dashboard review.

---

## System Architecture

```text
BRONZE LAYER
Dynamic browser scraping

- Parallel Playwright headless scraping via config/targets/*.json
- Text extraction from configured CSS selectors
- Screenshot/image extraction for banner-like promotional elements
- Vision LLM extraction for image-based offers

        ↓

SILVER LAYER
PostgreSQL storage

- LLM category assignment from env-driven category taxonomy
- URL-aware deduplication using source + brand + source_url + offer_title
- Stores offer title, category, brand, source URL, confidence, and timestamps

        ↓

GOLD LAYER
Dashboard and weekly matrix

- Streamlit dashboard filters by brand, category, source, and date
- Weekly competitor matrix groups offers by category, brand, and day of week
```

---

## Final Approach

The scraper uses a hybrid extraction strategy:

* **Text extraction** collects visible promotional text from configured CSS selectors.
* **Screenshot/image extraction** captures banner-like page elements and sends them to the configured vision LLM.
* **LLM category classification** runs once per brand scrape as a batched text call. It assigns each extracted offer to one category from the environment-driven taxonomy.
* **URL-aware deduplication** keeps identical promo text separate when it appears on different pages, such as `/men/` and `/kids/`.

Categories are not hardcoded in Python. Configure them in `.env`:

```env
PROMO_CATEGORIES="Home, Entertainment, Womens, Beauty, Kids, Toys, Menswear, Footwear, Other"
```

If `PROMO_CATEGORIES` is not set, the extractor falls back to:

```env
STANDARD_BASKETS="Womens, Beauty, Kids & Toys, Home, Menswear, Toys, Entertainment, Other"
```

The dashboard produces:

* a categorized promotion table
* category filters
* a weekly competitor matrix grouped by category

---

## Database Schema

The PostgreSQL database is streamlined to store only the essential promotional data.

### `competitors` Table

* `id` - primary key
* `name` - unique brand/competitor name
* `enabled` - boolean flag
* `added_at` - timestamp
* `modified_at` - timestamp

### `promotions` Table

* `id` - primary key
* `competitor_id` - foreign key to competitors
* `brand` - denormalized brand/competitor name
* `offer_title` - promotional headline/offer title
* `category` - LLM-assigned reporting category
* `source_name` - extraction source, e.g. `text_scraper` or `image_promo`
* `source_url` - exact page URL where the promo was scraped
* `extraction_confidence` - `high`, `medium`, or `low`
* `offer_hash` - SHA-256 fingerprint from source + brand + source URL + title
* `scraped_at` - timestamp of the latest scrape
* `created_at` - timestamp of insertion

`raw_text` has been removed from the active model and pipeline because it duplicated `offer_title`.

---

## Tech Stack

| Component | Technology |
|---|---|
| Browser Automation | Playwright Python |
| Vision/Text LLM | LiteLLM gateway or Gemini client |
| Database | PostgreSQL + SQLAlchemy |
| Orchestration | Prefect |
| Dashboard | Streamlit |

---

## Project Structure

```text
.
├── config/
│   └── targets/                       # Per-brand scrape configuration
├── database/
│   ├── connection.py                   # SQLAlchemy engine/session setup
│   └── models.py                       # SQLAlchemy models
├── flows/
│   └── master_pipeline.py              # Prefect flow for parallel scraping
├── promo_scraper/
│   ├── hybrid_promo_extractor.py       # Core extraction, LLM, dedupe, cost estimate
│   ├── items.py                        # Legacy Scrapy item definition
│   └── pipelines.py                    # Legacy Scrapy DB pipeline
├── scripts/
│   ├── init_db.py                      # Create/update DB schema
│   ├── reset_db.py                     # Clear DB tables
│   └── run_hybrid_promo_scraper.py     # Direct scraper runner
├── dashboard/
│   ├── app.py                          # Streamlit dashboard
│   └── utils/db.py                     # Dashboard DB query helpers
├── alembic/                            # Optional migrations
└── .env                                # Local configuration and credentials
```

---

## Quickstart

### 1. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

### 2. Configure Environment

Create a `.env` file in the root directory.

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/promo_db_v3

# LiteLLM / corporate gateway path
LLM_PROVIDER=litellm
LITELLM_API_KEY=your_litellm_key
LITELLM_API_BASE=https://your-litellm-gateway.example/v1
VISION_LLM_MODEL=claude-haiku-4.5

# Direct Gemini fallback/path
GEMINI_API_KEY=your_gemini_api_key

# Category taxonomy used by the LLM classifier and vision prompt
PROMO_CATEGORIES="Home, Entertainment, Womens, Beauty, Kids, Toys, Menswear, Footwear, Other"

MAX_CONCURRENT_BROWSERS=3
VISION_API_MIN_DELAY=1.0
```

### 3. Initialize or Update the Database

```bash
python scripts/init_db.py
```

`init_db.py` creates tables if needed, ensures `category` exists, and drops the old `raw_text` column if it is still present.

### 4. Run the Scraper

Run all enabled targets through Prefect:

```bash
python flows/master_pipeline.py
```

Run one target directly for testing:

```bash
python scripts/run_hybrid_promo_scraper.py --target config/targets/the_iconic.json
```

### 5. Launch the Dashboard

```bash
streamlit run dashboard/app.py
```

---

## Target Configuration

Each target file in `config/targets/` controls where and how a brand is scraped.

```json
{
  "brand": "The Iconic",
  "source_url": [
    "https://www.theiconic.com.au/men/",
    "https://www.theiconic.com.au/kids/"
  ],
  "spider": "image_promo",
  "extraction_strategy": "hybrid",
  "text_selectors": [".discover-more-content b"],
  "screenshot_selectors": ["[class*='Banner']"],
  "enabled": true
}
```

`source_url` may be a single string or a list. The extractor keeps duplicate promo text separate across different source URLs.

---

## Deduplication

Promotions are deduplicated using:

```text
source_name + brand + source_url + offer_title
```

This keeps the same offer text separate across different category pages when needed.

---

## LLM Cost Estimation

The scraper reports an estimated LLM input cost in each run summary.

For Claude Haiku 4.5, the estimate uses:

```text
USD 1.00 per 1M input tokens
image_tokens ~= (width * height / 800) + 170
text_tokens ~= characters / 4
```

Image cost is estimated after resizing, so it reflects the actual image sent to the model. The batched category classifier is counted separately as a text-only LLM call.

---

## Dashboard Output

The dashboard shows:

* KPI summary cards
* promotions by brand
* extraction timeline
* weekly competitor matrix grouped by category
* extracted promotions table with brand, category, source, offer title, source URL, confidence, and timestamp
