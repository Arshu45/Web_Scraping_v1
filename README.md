# Retail Market Intelligence Platform

A production-grade, end-to-end retail competitive intelligence system built on a **Medallion Architecture** (Bronze → Silver → Gold). The platform scrapes competitor pricing and promotional data, enriches it with AI-driven category classification, and surfaces actionable insights through a real-time Streamlit dashboard with an LLM-powered natural language analyst.

---

## Architecture & Data Flow

```text
╔══════════════════════════════════════════════ ════════════════════╗
║                        BRONZE LAYER                               ║
║                    (Raw Ingestion Sources)                        ║
╠══════════════════╦═══════════════════════╦════════════════════════╣
║  Aggregator      ║  Direct Catalog       ║  Internal Store        ║
║  Scraping        ║  Crawling             ║  Sync                  ║
║                  ║                       ║                        ║
║  GrabOn          ║  Forever New          ║ MySQL (fashion_retail) ║
║  CouponDunia     ║  Vero Moda            ║  ↓ orders + products   ║
║  (Scrapy)        ║  (Scrapy)             ║  (scripts/sync_own_    ║
║                  ║                       ║   store.py)            ║
╚══════════════════╩═══════════════════════╩════════════════════════╝
                              ↓
╔══════════════════════════════════════════════════════════════════╗
║                        SILVER LAYER                              ║
║               (PostgreSQL: promo_db_v3)                          ║
║                                                                  ║
║   promotions  ·  product_snapshots  ·  base_store_products       ║
║                          ↓                                       ║
║          GLiNER AI Enrichment (zero-shot NER)                    ║
║    Maps raw labels → Shared Taxonomy (Tops, Bottoms, etc.)       ║
╚══════════════════════════════════════════════════════════════════╝
                              ↓
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║              Streamlit Dashboard + AI Analyst                    ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `competitors` | Brands being tracked (Forever New, Vero Moda, …) |
| `scraping_sources` | Aggregator configs and spider entry points |
| `promotions` | Structured coupon/offer data from GrabOn & CouponDunia |
| `product_snapshots` | SKU-level pricing scraped from competitor websites |
| `base_store_products` | Internal store catalog synced from MySQL |

> Categories are not stored in a table. They are dynamically assigned via `CATEGORY_KEYWORDS` in `enrichment/gliner_extractor.py` using GLiNER zero-shot NER with priority-based tie-breaking.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraping / Crawling | Scrapy |
| Silver DB | PostgreSQL + SQLAlchemy + Alembic |
| Bronze DB | MySQL + PyMySQL |
| AI Enrichment | GLiNER (zero-shot NER) |
| AI Analyst | LangChain · LiteLLM · Groq (`llama-3.3-70b`) |
| Orchestration | Prefect |
| Dashboard | Streamlit |
| Charts | Plotly |

---

## Dashboard Pages

The dashboard runs at `http://localhost:8502` via `streamlit run dashboard/app.py`.

| Page | Description | Status |
|---|---|---|
| **Overview** | Top-line KPIs · Price-band-aware discount gap table · Volume heatmap | ✅ Active |
| **Competitor Battle** | Category-level gap analysis · Box plot price distribution | ✅ Active |
| **Price Positioning** | Price-band donut/bar toggle · Budget vs Premium breakdown | ✅ Active |
| **AI Analyst** | Natural language → SQL → Insight (LangChain + LLM) | ✅ Active |
| Category Analysis | Discount depth & scatter by category | 🔒 Disabled |
| Promotions Intel | Coupon & promo offer explorer | 🔒 Disabled |

---

## LLM Factory (`llm/`)

The AI Analyst uses a factory pattern to support multiple LLM providers with automatic failover:

```
llm/
├── factory.py        # Reads LLM_PROVIDER from .env, returns LangChain LLM wrapper
├── groq_client.py    # ChatGroq wrapper (llama-3.3-70b-versatile)
├── litellm_client.py # ChatOpenAI wrapper pointed at LiteLLM proxy
└── base.py           # Shared interface
```

- **Primary**: Set `LLM_PROVIDER=groq` or `LLM_PROVIDER=litellm`
- **Fallback**: Set `LLM_FALLBACK=litellm` — on a `429` rate-limit error the agent automatically rebuilds with the fallback provider and retries the query transparently

---

## Project Structure

```
.
├── dashboard/
│   ├── app.py                          # Landing page & sidebar
│   ├── pages/
│   │   ├── 1_🏠_Overview.py            # KPIs + price-band gap view
│   │   ├── 2_⚔️_Competitor_Battle.py   # Gap table + deep-dive
│   │   ├── 4_💰_Price_Positioning.py   # Donut/bar toggle
│   │   └── 6_💬_AI_Analyst.py          # NL-to-SQL AI chat
│   ├── pages_disabled/                 # Temporarily hidden pages
│   └── utils/
│       ├── db.py                       # All SQL queries (cached)
│       └── styles.py                   # Design system (light theme)
├── database/
│   ├── models.py                       # SQLAlchemy ORM models
│   ├── connection.py                   # DB session factory
│   └── mysql_connector.py              # Internal store MySQL connector
├── enrichment/
│   ├── gliner_extractor.py             # GLiNER NER-based category mapping
│   ├── llm_extractor.py                # LLM-based category fallback
│   └── enricher.py                     # Orchestrates enrichment pipeline
├── flows/
│   ├── master_pipeline.py              # Prefect master flow (all spiders + enrichment)
│   └── scraping_pipeline.py            # Prefect scraping sub-flow
├── llm/
│   ├── factory.py                      # LLM provider factory + fallback
│   ├── groq_client.py                  # Groq LLM client
│   └── litellm_client.py               # LiteLLM proxy client
├── promo_scraper/
│   ├── spiders/
│   │   ├── grabon.py                   # GrabOn aggregator spider
│   │   ├── coupondunia.py              # CouponDunia aggregator spider
│   │   ├── forevernew_products.py      # Forever New catalog spider
│   │   └── veromoda_products.py        # Vero Moda catalog spider
│   ├── pipelines.py                    # Scrapy item pipelines (dedup + save)
│   └── settings.py                     # Scrapy settings
├── scripts/
│   ├── reset_db.py                     # Wipe & recreate all tables
│   ├── seed_db.py                      # Seed competitor & source config
│   ├── sync_own_store.py               # Sync internal MySQL → PostgreSQL
│   └── backfill_categories.py          # Re-run AI enrichment without re-scraping
├── alembic/                            # DB migration history
├── .streamlit/config.toml              # Streamlit light theme config
└── .env                                # Secrets & provider config
```

---

## Quickstart

### 1. Install dependencies
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment
```env
# .env
DATABASE_URL=postgresql://user:password@localhost:5432/promo_db_v3

# Internal Store (MySQL)
MYSQL_HOST=your_mysql_host
MYSQL_PORT=3306
MYSQL_USER=readonly_user
MYSQL_PASSWORD=your_password
MYSQL_DB=fashion_retail

# LLM Provider (for AI Analyst)
LLM_PROVIDER=groq                        # or: litellm
LLM_FALLBACK=litellm                     # fallback on 429 rate-limit
LLM_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0
LLM_MAX_TOKENS=5000
GROQ_API_KEY=your_groq_key

# LiteLLM proxy (optional)
LITELLM_API_KEY=your_key
LITELLM_API_BASE=https://your-proxy/v1
```

### 3. Set up the database
```bash
python scripts/reset_db.py      # create tables
python scripts/seed_db.py       # seed competitor config
```

### 4. Run the full data pipeline
```bash
# Option A — Prefect (orchestrated, with monitoring)
prefect server start             # open http://localhost:4200
python flows/master_pipeline.py

# Option B — individual spiders (for testing)
scrapy crawl forevernew_products
scrapy crawl veromoda_products
scrapy crawl grabon
scrapy crawl coupondunia
```

### 5. Sync internal store data
```bash
python scripts/sync_own_store.py
```

### 6. Launch the dashboard
```bash
streamlit run dashboard/app.py
# → http://localhost:8502
```

---

## Useful Commands

| Task | Command |
|---|---|
| Re-run AI enrichment only (no re-scrape) | `python scripts/backfill_categories.py` |
| Reset all data | `python scripts/reset_db.py` |
| Re-seed competitor config | `python scripts/seed_db.py` |
| Run a single spider | `scrapy crawl <spider_name>` |
| Run full pipeline | `python flows/master_pipeline.py` |

---

## Branches

| Branch | Purpose |
|---|---|
| `main` | Stable baseline |
| `develop` | Integration branch |
| `final_output` | **Current production state** |
| `Medallion_Architecture` | Architecture-level work |
| `Database-CRUD-Setup` | DB schema setup work |
