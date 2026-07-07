# Retail Competitive Intelligence Scraper

A production-grade, concurrent hybrid competitive intelligence system. The platform scrapes promotional offers directly from competitor websites (such as Forever New, David Jones, and The Iconic) in parallel, handles deduplication, and stores them in PostgreSQL.

---

## System Architecture

```text
╔══════════════════════════════════════════════════════════════════╗
║                        BRONZE LAYER                              ║
║                (Dynamic Browser Scraping)                        ║
║                                                                  ║
║   Parallel Playwright Headless Scraping via Target configs       ║
║   (e.g., config/targets/forever_new.json, david_jones.json)       ║
║   Downloads promotional banners & extracts text elements        ║
╚══════════════════════════════════════════════════════════════════╝
                              ↓
╔══════════════════════════════════════════════════════════════════╗
║                        SILVER LAYER                              ║
║                  (PostgreSQL Database)                           ║
║                                                                  ║
║   Deduplication using SHA-256 (source + competitor + title)      ║
║   Stores raw promotions, brand name, source URL, and confidence   ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Database Schema

The PostgreSQL database is streamlined to store only the essential promotional data:

### `competitors` Table
* `id` (Primary Key)
* `name` (Unique brand/competitor name, e.g. "David Jones")
* `enabled` (Boolean)
* `added_at` (Timestamp)
* `modified_at` (Timestamp)

### `promotions` Table
* `id` (Primary Key)
* `competitor_id` (Foreign Key to competitors)
* `brand` (Denormalized string name of the competitor site)
* `offer_title` (Raw promotional headline/offer title)
* `raw_text` (Full raw text extracted from elements or banners)
* `source_name` (Name of the scraper/strategy, e.g. "text_scraper")
* `source_url` (Exact page URL where the promo was scraped)
* `extraction_confidence` (Confidence level "high" | "medium" | "low")
* `offer_hash` (Unique SHA-256 fingerprint used for deduplication)
* `scraped_at` (Timestamp of last scraping run)
* `created_at` (Timestamp of insertion)

---

## Tech Stack

| Component | Technology |
|---|---|
| Browser Automation | Playwright (Python) |
| Database | PostgreSQL + SQLAlchemy |
| Orchestration | Prefect |

---

## Project Structure

```
.
├── config/
│   └── targets/
│       ├── david_jones.json            # Target config for David Jones
│       ├── forever_new.json            # Target config for Forever New
│       └── the_iconic.json             # Target config for The Iconic
├── database/
│   ├── connection.py                   # SQLAlchemy connection session factory
│   └── models.py                       # Simplified SQLAlchemy Models
├── flows/
│   └── master_pipeline.py              # Prefect flow orchestrating parallel runs
├── promo_scraper/
│   ├── hybrid_promo_extractor.py       # Core browser/text extraction logic
│   ├── items.py                        # Scrapy legacy items configuration
│   └── pipelines.py                    # Scrapy legacy pipelines configuration
├── scripts/
│   ├── init_db.py                      # Initialize database tables
│   ├── reset_db.py                     # Clears database tables
│   └── run_hybrid_promo_scraper.py     # Hybrid scraper runner script
├── alembic/                            # DB migrations (optional)
└── .env                                # Database and API key configuration
```

---

## Quickstart

### 1. Install dependencies
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

### 2. Configure environment
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/promo_db_v3
GEMINI_API_KEY=your_gemini_vision_api_key
```

### 3. Initialize the database
```bash
python scripts/init_db.py
```

### 4. Run the Pipeline
To run all target scrapers in parallel via Prefect:
```bash
python flows/master_pipeline.py
```

To run a single target directly or test sequentially:
```bash
python scripts/run_hybrid_promo_scraper.py
```

### 5. Launch the Dashboard
To start the Streamlit web dashboard to filter and view promotions:
```bash
streamlit run dashboard/app.py
```

