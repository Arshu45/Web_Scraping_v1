# Promo Scraper

A scalable, multi-source promotional offer intelligence pipeline built with **Scrapy**, **PostgreSQL**, **GLiNER**, and **Prefect**.

The system operates in two main modes:
1. **Aggregator Scraping**: Scrapes promotional offers from aggregator sites (CouponDunia, GrabOn), stores them, and extracts key details (discount percentages, coupon codes, min purchase amounts) using AI-powered Named Entity Recognition (GLiNER).
2. **Direct Catalog Crawling**: Self-discovers and scrapes product catalogs directly from retail sites (like Forever New), extracting structured, SKU-level pricing data (MRP vs. Sale price, discounts) without needing NLP enrichment.

---

## Architecture

```
                    config/targets.json (seed only)
                                ↓
                          PostgreSQL DB
                 (competitors & scraping_sources)
                                │
          ┌─────────────────────┴─────────────────────┐
          ▼                                           ▼
Aggregator Spiders (BasePromoSpider)       Direct Catalog Crawlers
(e.g., coupondunia, grabon)                (e.g., forevernew_products)
Reads URLs from DB                         Self-discovering from site nav
          │                                           │
          ▼                                           ▼
   PostgresPipeline                        ProductSnapshotPipeline
   upserts OfferItems                      upserts ProductSnapshotItems
   (SHA-256 dedup)                         (URL dedup)
          │                                           │
          ▼                                           │
  GLiNER Enrichment                                   │
  (Extracts discounts, codes)                         │
          │                                           │
          └─────────────────────┬─────────────────────┘
                                ▼
                   Prefect Flow Orchestration
           (master_pipeline.py runs all in parallel)
```

### Database Schema (4 Tables)

| Table | Purpose |
|---|---|
| `competitors` | Brands being tracked (Myntra, Ajio, Forever New, etc.) |
| `scraping_sources` | Aggregator config / Entry points for crawlers |
| `promotions` | All scraped aggregator offers with structured fields |
| `product_snapshots`| SKU-level pricing data extracted from direct catalogs |
| `scraping_runs` | Audit log for every Prefect pipeline run |

*Note: Product categories are no longer stored in a database table. They are configured via `PROMOTION_CATEGORIES` in `enrichment/gliner_extractor.py` for dynamic mapping.*

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraping / Crawling | Scrapy |
| Database | PostgreSQL + SQLAlchemy |
| Migrations | Alembic |
| NLP Enrichment | GLiNER (zero-shot NER) |
| Orchestration | Prefect |
| Config | python-dotenv |

---

## Setup

### 1. Clone & Create Virtual Environment
```bash
git clone <your-repo-url>
cd Scrapy
python -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

> **Note:** GLiNER will download a ~1.5GB model on first run. This is cached locally.

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env and set your DATABASE_URL:
# DATABASE_URL=postgresql://user:password@localhost:5432/your_db
```

### 4. Run Database Migrations
```bash
alembic upgrade head
```
This creates all necessary tables in your PostgreSQL database.

### 5. Seed the Database
```bash
python scripts/seed_db.py
```
This migrates `config/targets.json` into the `competitors` and `scraping_sources` tables. 

> **Need a fresh start?** Run `python scripts/reset_db.py` to wipe all data (but keep the schema), then run `seed_db.py` again.

---

## Running the Pipeline

### Option A — Full Master Pipeline (Recommended)
Runs all enabled spiders (aggregators + catalogs) in parallel, stores results, and enriches aggregator data with GLiNER:
```bash
python flows/master_pipeline.py
```

### Option B — Run Individual Spiders (Scrapy CLI)
Runs just the scraping step, skipping Prefect orchestration and GLiNER enrichment:
```bash
scrapy crawl coupondunia
scrapy crawl grabon
scrapy crawl forevernew_products
```

---

## Project Structure

```
├── alembic/               # DB migration scripts
├── config/
│   └── targets.json       # Initial seed config (now managed via DB)
├── database/
│   ├── models.py          # SQLAlchemy ORM models
│   └── connection.py      # PostgreSQL engine & session factory
├── enrichment/
│   └── gliner_extractor.py  # GLiNER NER enrichment module
├── flows/
│   └── master_pipeline.py # Prefect master orchestration flow
├── promo_scraper/
│   ├── items.py           # OfferItem & ProductSnapshotItem schemas
│   ├── pipelines.py       # PostgresPipeline & ProductSnapshotPipeline
│   ├── settings.py        # Scrapy settings
│   └── spiders/
│       ├── base.py        # BasePromoSpider (reads targets from DB)
│       ├── coupondunia.py
│       ├── grabon.py
│       └── forevernew_products.py # Direct catalog crawler
├── scripts/
│   ├── seed_db.py         # DB seeding script
│   └── reset_db.py        # DB wipe script
├── .env.example           # Template for credentials
└── requirements.txt
```
