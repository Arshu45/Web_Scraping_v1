# Promotional Intelligence Platform: Architecture & Implementation Plan

## 1. Executive Summary

The Promotional Intelligence Platform is a production-grade, AI-powered web scraping and data enrichment pipeline. It extracts promotional offers from various aggregator sites, deduplicates them, and uses advanced NLP (Natural Language Processing) and LLMs (Large Language Models) to extract structured, queryable data from raw marketing text. The entire process is orchestrated via Prefect to ensure scalability, parallelism, and robust audit trails.

---

## 2. System Architecture

The platform follows a modular ETL (Extract, Transform, Load) architecture with four distinct layers:

1.  **Orchestration Layer (Prefect):** Manages the execution flow, handles parallel spider runs, and triggers the enrichment pipeline.
2.  **Scraping Layer (Scrapy):** Discovers and extracts raw promotion texts from aggregator sites (e.g., CouponDunia, GrabOn).
3.  **Database Layer (PostgreSQL):** Centralized storage for configurations, deduplicated raw data, structured insights, and audit logs.
4.  **Enrichment Layer (GLiNER / Groq LLM):** Pluggable NLP module that processes raw text to extract actionable fields and classify product categories.

### High-Level Architecture Flow

```mermaid
graph TD
    subgraph Orchestration [Prefect Master Pipeline]
        A[Start Flow] --> B[Discover Active Sources from DB]
        B --> C{Parallel Execution}
    end

    subgraph Scraping [Scrapy Subprocesses]
        C -->|Spider 1| D1[GrabOn Spider]
        C -->|Spider 2| D2[CouponDunia Spider]
        D1 -->|Hash Deduplication| DB[(PostgreSQL)]
        D2 -->|Hash Deduplication| DB
    end

    subgraph Enrichment [NLP / LLM Processing]
        DB -->|Fetch Unenriched Data| E[Enrichment Dispatcher]
        E -->|GLiNER Local Model| F1[Extract Entities]
        E -->|Groq LLM API| F2[Batch LLM Extraction]
        F1 --> G[Score-Based Category Classification]
        F2 --> G
        G -->|Update Structured Fields| DB
    end

    C -->|Wait for Spiders| E
    E --> H[Generate Summary Report]
```

---

## 3. Database Schema

The platform relies on a relational schema managed via SQLAlchemy and Alembic. Recent refactoring simplified the schema by removing the dedicated `Category` table in favor of a dynamic, config-driven approach.

### Entity-Relationship Diagram

```mermaid
erDiagram
    COMPETITOR ||--o{ SCRAPING_SOURCE : has
    COMPETITOR ||--o{ PROMOTION : has
    
    COMPETITOR {
        int id PK
        string name
        boolean enabled
        datetime added_at
    }
    
    SCRAPING_SOURCE {
        int id PK
        int competitor_id FK
        string source_name
        string source_url
        string spider_name
        boolean enabled
    }
    
    PROMOTION {
        int id PK
        int competitor_id FK
        text offer_title
        text raw_text
        string category
        string promo_type
        float discount_min
        float discount_max
        float flat_value
        float min_purchase
        string coupon_code
        string user_type
        string offer_hash UK
    }
    
    SCRAPING_RUN {
        int id PK
        string spider_name
        string status
        int items_scraped
        int items_inserted
    }
```

---

## 4. Key Implementation Details & Enhancements

### 4.1 Orchestration and Parallelism
-   **Subprocess Execution:** Scrapy's Twisted reactor prevents multiple spiders from running in the same Python process. The Prefect master pipeline solves this by launching each spider in an isolated subprocess (`subprocess.run`), enabling true parallel execution.
-   **Audit Logging:** `stderr` output from the Scrapy subprocesses is parsed via regex to extract accurate pipeline statistics (Scraped, Inserted, Updated), which are logged to the `scraping_runs` table.

### 4.2 Data Deduplication
-   **SHA-256 Fingerprinting:** To prevent duplicate records across multiple aggregator sites, the `PostgresPipeline` generates a unique `offer_hash` based on: `source_name + competitor.name + offer_title`. Conflicts trigger SQL `ON CONFLICT DO UPDATE` (upserts) rather than duplicate inserts.

### 4.3 Pluggable AI Enrichment
The system supports two interchangeable enrichment backends controlled via the `ENRICHMENT_PROVIDER` environment variable:
1.  **GLiNER (Local NLP):** A fast, local NER (Named Entity Recognition) model capable of zero-shot extraction. Excellent for privacy and avoiding API costs.
2.  **Groq LLM (Cloud API):** Uses `llama-3.1-8b-instant` for complex parsing. 
    -   *Enhancement:* Implemented **Prompt Batching**. To avoid strict Tokens Per Minute (TPM) rate limits (e.g., 6000 TPM), the Groq extractor batches 15 promotions into a single API request. This reduces token overhead by 90% and prevents infinite hanging.

### 4.4 Smart Category Classification
Instead of a rigid database table, categories are dynamically matched using a score-based classification algorithm.

```mermaid
flowchart TD
    A[Raw Promotion Text] --> B{GLiNER/LLM Extracts Product Entities}
    B -->|e.g., 'lipstick, foundation'| C[Keyword Matcher]
    B -->|None| D[Fallback: Scan Raw Text]
    D --> C
    
    C --> E[Calculate Hits per Category]
    E --> F{Are there hits?}
    
    F -->|No| G[Category = None]
    F -->|Yes| H{Check Dominance}
    
    H -->|1 Category clear winner| I[Assign Top Category]
    H -->|≥3 Categories match OR similar scores| J[Assign 'Multi-Category']
```
-   **Handling Sitewide Offers:** Broad offers (e.g., *"shoes, shirts, bedsheets, earrings"*) are correctly identified as generic sales and assigned `"Multi-Category"` instead of failing or defaulting to the first keyword matched.

---

## 5. Deployment and Operations

### Environment Configuration (`.env`)
```env
DATABASE_URL=postgresql://user:password@localhost/dbname
ENRICHMENT_PROVIDER=groq  # Options: 'gliner' or 'groq'
GROQ_API_KEY=your_api_key
GROQ_MODEL=llama-3.1-8b-instant
```

### Operational Commands
-   **Reset Environment:** `python scripts/reset_db.py` (Clears data, keeps schema)
-   **Seed Database:** `python scripts/seed_db.py` (Loads initial competitors and sources)
-   **Run Pipeline:** `python flows/master_pipeline.py` (Executes full ETL flow)
-   **Monitor UI:** `prefect server start` (View DAG execution and logs in browser)
