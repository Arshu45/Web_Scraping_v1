# Promo Scraper

A scalable, multi-source promotional offer intelligence pipeline built with **Scrapy**, **PostgreSQL**, **GLiNER**, and **Prefect**.

The system scrapes promotional offers and discounts from aggregator sites (CouponDunia, GrabOn), stores them in a structured PostgreSQL database, and automatically extracts key details like discount percentages, coupon codes, and minimum purchase amounts using AI-powered Named Entity Recognition (GLiNER).

---

## Architecture

```
config/targets.json (seed only)
        ↓
  PostgreSQL DB  ←──────────────────────────────────────┐
  (scraping_sources table)                              │
        ↓                                               │
  Scrapy Spider (BasePromoSpider)                       │
  reads targets from DB, not hardcoded URLs             │
        ↓                                               │
  PostgresPipeline                                      │
  upserts OfferItems with SHA-256 deduplication ────────┘
        ↓
  GLiNER Enrichment
  extracts: discount %, flat value, coupon code, min purchase
        ↓
  Prefect Flow Orchestration
  schedules, retries, and logs every run
```

### Database Schema (5 Tables)

| Table | Purpose |
|---|---|
| `competitors` | Brands being tracked (Myntra, Ajio, etc.) |
| `scraping_sources` | Aggregator URLs per brand — the dynamic config |
| `categories` | Master category lookup (Apparel, Footwear, etc.) |
| `promotions` | All scraped offers with structured fields |
| `scraping_runs` | Audit log for every Prefect pipeline run |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraping | Scrapy |
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

> **Note:** GLiNER will download a ~1.5GB model on first run. This is cached locally after the first download.

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
This creates all 5 tables in your PostgreSQL database.

### 5. Seed the Database
```bash
python scripts/seed_db.py
```
This migrates `config/targets.json` into the `competitors`, `scraping_sources`, and `categories` tables. Run this once on setup.

---

## Running the Pipeline

### Option A — Full Prefect Pipeline (Recommended)
Runs the spider, stores results in PostgreSQL, then enriches with GLiNER:
```bash
python flows/scraping_pipeline.py coupondunia
python flows/scraping_pipeline.py grabon
```

### Option B — Spider Only (Scrapy CLI)
Runs just the scraping step, skipping GLiNER enrichment:
```bash
scrapy crawl coupondunia
scrapy crawl grabon
```

### Option C — GLiNER Enrichment Only
Enriches any previously scraped but unenriched promotions:
```bash
python enrichment/gliner_extractor.py
```

---

## Adding a New Spider

1. Add the new source to `config/targets.json` and re-run `scripts/seed_db.py`, **or** insert directly into the `scraping_sources` table.
2. Create a new spider file in `promo_scraper/spiders/` that inherits from `BasePromoSpider`.
3. Set `name = "your_spider_name"` and implement the `parse()` method.

The central `PostgresPipeline` and Prefect flow will handle the rest automatically.

---

## Project Structure

```
├── alembic/               # DB migration scripts
├── config/
│   └── targets.json       # Initial seed config (now managed via DB)
├── database/
│   ├── models.py          # SQLAlchemy ORM models (5 tables)
│   └── connection.py      # PostgreSQL engine & session factory
├── enrichment/
│   └── gliner_extractor.py  # GLiNER NER enrichment module
├── flows/
│   └── scraping_pipeline.py # Prefect 4-task orchestration flow
├── promo_scraper/
│   ├── items.py           # OfferItem schema
│   ├── pipelines.py       # PostgresPipeline (upsert with deduplication)
│   ├── settings.py        # Scrapy settings
│   └── spiders/
│       ├── base.py        # BasePromoSpider (reads targets from DB)
│       ├── coupondunia.py
│       └── grabon.py
├── scripts/
│   └── seed_db.py         # One-time DB seeding script
├── .env.example           # Template for credentials
└── requirements.txt
```
