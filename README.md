# Promo Scraper & Market Intelligence Pipeline

A scalable, multi-source promotional offer intelligence pipeline built with **Scrapy**, **PostgreSQL**, **MySQL**, **GLiNER**, and **Prefect**.

The system operates across three distinct data pipelines, bringing all data into a conformed "Silver Layer" for easy apples-to-apples comparisons:
1. **Aggregator Scraping**: Scrapes promotional offers from aggregator sites (CouponDunia, GrabOn), extracts key details (discount percentages, coupon codes, min purchase amounts) using AI-powered Named Entity Recognition (GLiNER).
2. **Direct Catalog Crawling**: Self-discovers and scrapes product catalogs directly from retail sites (like Forever New, Vero Moda), extracting structured, SKU-level pricing data.
3. **Internal Store Sync**: Extracts your internal product catalog from MySQL (`fashion_retail`), calculates true historical discount averages from order history, and seamlessly aligns it with competitor data.

---

## Architecture & Data Flow (Medallion Architecture)

```text
                     [BRONZE LAYER]

  config/targets.json                      Internal MySQL DB
           ↓                               (fashion_retail)
     PostgreSQL DB                                 │
(competitors / sources)                            │
           │                                       │
  ┌────────┴────────┐                              │
  ▼                 ▼                              │
Aggregators      Direct Catalogs                   │
(Scrapy)         (Scrapy)                          │
  │                 │                              │
  ▼                 ▼                              ▼
─────────────────────────────────────────────────────────────────
                     [SILVER LAYER]
             (PostgreSQL: promo_db_v3)

promotions   product_snapshots           base_store_products
  │                 │                              │
  └─────────────────┼──────────────────────────────┘
                    ▼
          GLiNER AI ENRICHMENT
  (Maps raw labels → Granular Taxonomy:
   Tops, Bottoms, Activewear, Footwear, etc.)
─────────────────────────────────────────────────────────────────
                     [GOLD LAYER]
     (SQL Views / Dashboards - Ready for Analysis)
```

### Database Schema (5 Main Tables)

| Table | Purpose |
|---|---|
| `competitors` | Brands being tracked (Our Store, Forever New, Vero Moda, etc.) |
| `scraping_sources` | Aggregator config / Entry points for crawlers |
| `promotions` | All scraped aggregator offers with structured fields |
| `product_snapshots`| SKU-level pricing data extracted from direct competitor catalogs |
| `base_store_products`| SKU-level internal data from MySQL synced into Postgres |

*Note: Product categories are no longer stored in a database table. They are dynamically mapped via `CATEGORY_KEYWORDS` in `enrichment/gliner_extractor.py` using AI and smart tie-breaking priority logic.*

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraping / Crawling | Scrapy |
| Databases | PostgreSQL (Silver), MySQL (Bronze) + SQLAlchemy / PyMySQL |
| Migrations | Alembic |
| NLP Enrichment | GLiNER (zero-shot NER) |
| Orchestration | Prefect |

---

## 🛠️ Command Cheat Sheet

### 1. Database Setup & Reset
Configure your PostgreSQL database from scratch.
*   **Wipe & Recreate Tables:** 
    ```bash
    python scripts/reset_db.py
    ```
    *(Warning: Deletes all scraped data and recreates empty tables)*
*   **Seed Target URLs:** 
    ```bash
    python scripts/seed_db.py
    ```

### 2. The Master Pipeline (Daily Run)
Runs all spiders concurrently and finishes by running the AI GLiNER model to categorize new data.
*   **Start the UI Dashboard:**
    ```bash
    prefect server start
    ```
*   **Execute the Full Pipeline:**
    ```bash
    python flows/master_pipeline.py
    ```

### 3. Internal Data Sync (Silver Layer)
Refresh your PostgreSQL database with the latest internal data from your MySQL store.
*   **Sync Internal Store:**
    ```bash
    python scripts/sync_own_store.py
    ```
    *(Fetches MySQL data, calculates real discounts, applies AI categorization, and saves to `base_store_products`)*

### 4. Standalone Spider Execution (For Testing)
Run a specific crawler bypassing the Prefect orchestrator.
*   **Run Forever New or Vero Moda:**
    ```bash
    scrapy crawl forevernew_products
    scrapy crawl veromoda_products
    ```
*   **Run Coupon Aggregators:**
    ```bash
    scrapy crawl grabon
    scrapy crawl coupondunia
    ```

### 5. Manual AI Backfill (Debugging)
If you update `CATEGORY_KEYWORDS` in `gliner_extractor.py` and want to re-run the AI without scraping the websites again.
*   **Re-categorize Scraped Products:**
    ```bash
    python scripts/backfill_categories.py
    ```

---

## Environment Variables (`.env`)

Ensure your `.env` contains the following:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/promo_db_v3
ENRICHMENT_PROVIDER=gliner

# MySQL Database (Internal Store Data)
MYSQL_HOST=172.27.133.173
MYSQL_PORT=3306
MYSQL_USER=readonly_user
MYSQL_PASSWORD=cybage@123
MYSQL_DB=fashion_retail
```
