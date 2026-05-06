# Retail Market Intelligence Platform — Architecture & Implementation
---

## 1. Executive Summary

The Retail Market Intelligence Platform is a production-grade, end-to-end competitive intelligence system for a fashion retail business. It continuously scrapes pricing and promotional data from competitors, enriches it using AI-driven category classification, stores it in a well-governed three-layer database architecture, and surfaces real-time insights through an interactive Streamlit dashboard with a natural-language AI Analyst.

The system tracks two direct competitors (**Forever New**, **Vero Moda**) and aggregator promotional sites (**GrabOn**, **CouponDunia**), comparing them against an internal store catalog synced from an existing MySQL database.

**Key business value delivered:**
- Real-time visibility into competitor discount strategies by category and price range
- Price-band-aware gap analysis (eliminates the Simpson's Paradox problem of mixing discount averages across wildly different price points)
- A conversational AI analyst that can answer any competitive question in plain English and generate its own SQL

---

## 2. System Architecture — Medallion Layers

The platform is organized as a **Medallion Architecture** with three layers, each with a well-defined responsibility:

```
BRONZE  →  Raw ingestion from all sources
SILVER  →  Clean, conformed, enriched, deduplicated data in PostgreSQL
GOLD    →  Dashboard views and AI-driven analysis
```

### 2.1 Architecture Flow Diagram

```mermaid
graph TD
    subgraph BRONZE["Bronze Layer — Raw Ingestion"]
        A1[GrabOn Spider]
        A2[CouponDunia Spider]
        A3[Forever New Catalog Spider]
        A4[Vero Moda Catalog Spider]
        A5[MySQL Internal Store Sync]
    end

    subgraph SILVER["Silver Layer — PostgreSQL: promo_db_v3"]
        B1[(promotions)]
        B2[(product_snapshots)]
        B3[(base_store_products)]
        B4[(competitors)]
        B5[(scraping_sources)]
        ENR[GLiNER / LLM Enrichment<br/>Category Classification]
    end

    subgraph GOLD["Gold Layer — Analytics & AI"]
        C1[Streamlit Dashboard]
        C2[AI Analyst — LangChain NL-to-SQL]
    end

    subgraph ORCH["Prefect Orchestration"]
        P[master_pipeline.py<br/>Parallel subprocess execution]
    end

    A1 -->|hash dedup + upsert| B1
    A2 -->|hash dedup + upsert| B1
    A3 -->|hash dedup + upsert| B2
    A4 -->|hash dedup + upsert| B2
    A5 -->|sync + discount calc| B3
    B1 --> ENR
    B2 --> ENR
    ENR -->|category field written back| B1
    ENR -->|master_category field written back| B2
    P -->|orchestrates| A1
    P -->|orchestrates| A2
    P -->|orchestrates| A3
    P -->|orchestrates| A4
    B1 --> C1
    B2 --> C1
    B3 --> C1
    B4 --> C1
    B1 --> C2
    B2 --> C2
    B3 --> C2
```

---

## 3. Bronze Layer — Data Ingestion

### 3.1 Data Sources

| Source | Spider | Type | Data Captured |
|---|---|---|---|
| GrabOn | `grabon` | Aggregator | Coupon offers, discount %, coupon codes, min purchase |
| CouponDunia | `coupondunia` | Aggregator | Coupon offers, promo text, user type |
| Forever New | `forevernew_products` | Direct Catalog | Product name, MRP, sale price, discount %, category, URL, SKU |
| Vero Moda | `veromoda_products` | Direct Catalog | Product name, MRP, sale price, discount %, category, URL, SKU |
| Internal MySQL | `scripts/sync_own_store.py` | Internal Sync | Product catalog from `fashion_retail` MySQL DB |

### 3.2 Scrapy Pipeline — Deduplication

All Scrapy spiders pass items through `PostgresPipeline`, which implements **SHA-256 fingerprint deduplication**:

```
offer_hash = SHA256(source_name + competitor.name + offer_title)
```

On duplicate: SQL `ON CONFLICT DO UPDATE` (upsert) — no duplicates, always latest data.

### 3.3 Prefect Orchestration

The Prefect master pipeline (`flows/master_pipeline.py`) solves a fundamental Scrapy constraint: Scrapy's Twisted reactor cannot run multiple spiders in the same Python process. The solution is subprocess isolation:

```mermaid
flowchart LR
    A[Prefect Flow Start] --> B[Query DB for active sources]
    B --> C[Parallel subprocess pool]
    C --> D1[subprocess: scrapy crawl grabon]
    C --> D2[subprocess: scrapy crawl coupondunia]
    C --> D3[subprocess: scrapy crawl forevernew_products]
    C --> D4[subprocess: scrapy crawl veromoda_products]
    D1 & D2 & D3 & D4 --> E[Parse stderr for stats]
    E --> F[Log to scraping_runs table]
    F --> G[Trigger GLiNER Enrichment]
```

Each spider runs as a true parallel OS process. `stderr` output is parsed via regex to extract `Scraped / Inserted / Updated` counts which are logged for audit.

---

## 4. Silver Layer — Database Schema

All data is stored in PostgreSQL (`promo_db_v3`), managed via SQLAlchemy ORM and Alembic migrations.

### 4.1 Entity-Relationship Diagram

```mermaid
erDiagram
    COMPETITORS ||--o{ PROMOTIONS : "has"
    COMPETITORS ||--o{ PRODUCT_SNAPSHOTS : "has"

    COMPETITORS {
        serial id PK
        varchar name
        boolean enabled
        timestamp added_at
        timestamp modified_at
    }

    PROMOTIONS {
        serial id PK
        int competitor_id FK
        text offer_title
        text raw_text
        varchar category
        varchar promo_type
        float discount_min
        float discount_max
        float flat_value
        float min_purchase
        varchar coupon_code
        varchar user_type
        date valid_until
        varchar source_name
        varchar offer_hash UK
        timestamp scraped_at
        timestamp created_at
    }

    PRODUCT_SNAPSHOTS {
        serial id PK
        int competitor_id FK
        varchar product_name
        text product_url UK
        varchar sku
        varchar category_label
        varchar master_category
        float original_price
        float sale_price
        float discount_percentage
        boolean is_on_sale
        timestamp first_seen_at
        timestamp last_seen_at
    }

    BASE_STORE_PRODUCTS {
        serial id PK
        varchar product_id UK
        varchar product_name
        varchar brand
        varchar gender
        varchar category_label
        varchar master_category
        float original_price
        float sale_price
        float discount_percentage
        timestamp last_synced_at
    }
```

### 4.2 Table Reference

| Table | Row Count (approx) | Purpose |
|---|---|---|
| `competitors` | ~5 | Brand registry for all tracked sources |
| `promotions` | ~500+ | Structured coupon/promo data from aggregators |
| `product_snapshots` | ~5,000+ | SKU-level pricing from competitor direct sites |
| `base_store_products` | ~11,247 | Internal store catalog synced from MySQL |

### 4.3 Shared Category Taxonomy

Both `product_snapshots.master_category` and `base_store_products.master_category` use a **shared taxonomy** to enable apples-to-apples comparisons:

> Tops · Bottoms · Dresses & Jumpsuits · Outerwear · Activewear · Intimates & Sleepwear · Co-Ords · Ethnic Wear · Footwear · Bags & Wallets · Jewellery · Accessories · Beauty & Personal Care · Kids · Collections & Edits · General Apparel

---

## 5. AI Enrichment — Category Classification

### 5.1 GLiNER (Primary)

**GLiNER** is a zero-shot Named Entity Recognition (NER) model that runs **locally** — no API costs, no data leaving the network.

It processes raw product titles and promo text to extract product-type entities (e.g., `"lipstick"`, `"shirt"`, `"sneakers"`), which are then matched against a `CATEGORY_KEYWORDS` dictionary in `enrichment/gliner_extractor.py`.

### 5.2 LLM Fallback (Secondary)

When GLiNER confidence is low, an LLM fallback (`enrichment/llm_extractor.py`) is triggered via Groq API. **Prompt batching** groups 15 items per API call to stay within TPM rate limits:

```
Single-item approach: N API calls × high token overhead
Batch approach:       N/15 API calls × ~90% token reduction
```

### 5.3 Score-Based Category Assignment

```mermaid
flowchart TD
    A[Product Title / Promo Text] --> B[GLiNER / LLM Extracts Entities]
    B --> C[Match entities against CATEGORY_KEYWORDS dict]
    C --> D{Hits found?}
    D -->|No| E[master_category = Other]
    D -->|Yes| F{Dominance check}
    F -->|1 clear winner| G[Assign that category]
    F -->|≥3 categories match OR scores too close| H[Assign Multi-Category]
```

**Why Multi-Category exists:** Sitewide offers like *"shoes, shirts, bedsheets, earrings — all on sale"* should not be classified as "Tops" just because "shirts" appears first. The dominance check prevents this.

---

## 6. Gold Layer — Dashboard

The dashboard is built with **Streamlit** and runs at `http://localhost:8502`.

### 6.1 Active Pages

#### Overview (`1_🏠_Overview.py`)

The landing analytics page. Replaces a naive "average discount by category" chart with a **price-band-aware gap analysis** — the key insight being that comparing discount percentages across wildly different price points is statistically meaningless (a 10% average discount on accessories is meaningless if our accessories average ₹150 while competitors' average ₹2,500).

**Components:**
- Top-line KPI cards (product counts, avg discounts per brand)
- **Price-band filter** (`All / Budget / Mid-Range / Premium / Luxury`) — filters the entire gap table to compare only products in the same price window
- Enriched gap table — shows discount %, avg MRP, and % of products on sale per brand per category
- Product volume heatmap by brand & category

#### Competitor Battle (`2_⚔️_Competitor_Battle.py`)

Category-level head-to-head comparison with drill-down capability.

**Components:**
- Gap table: Our Store vs Forever New vs Vero Moda by category
- Gap visualisation bar chart
- **Category Deep Dive** — select any category to see MRP box-plot distribution across all three brands + individual metrics with delta indicators

#### Price Positioning (`4_💰_Price_Positioning.py`)

Shows how each brand's catalog is distributed across price bands.

**Components:**
- **Toggle view** (Donut / Bar) — both views show the same data, user picks preferred representation
- Shared legend strip
- Key observation callout cards

#### AI Analyst (`6_💬_AI_Analyst.py`)

A conversational interface where users type a business question in plain English and receive a data-backed answer — the AI generates SQL, runs it against the live database, and interprets the results.

**Example questions the AI handles:**
- *"Which category has the biggest discount gap between our store and Vero Moda?"*
- *"How many Forever New products are on sale with more than 50% off?"*
- *"What is the average sale price of Tops across all brands?"*

### 6.2 Disabled Pages

| Page | Reason |
|---|---|
| Category Analysis (`3_📊_Category_Analysis.py`) | Functionality merged into Overview and Competitor Battle |
| Promotions Intel (`5_🎯_Promotions_Intel.py`) | Deprioritised for current sprint |

Disabled pages are stored in `dashboard/pages_disabled/` and can be re-enabled by moving back to `dashboard/pages/`.

---

## 7. AI Analyst — LLM Architecture

### 7.1 LangChain NL-to-SQL Agent

The AI Analyst uses a **LangChain SQL Agent** (`create_sql_agent`) backed by a live PostgreSQL connection. The agent:

1. Receives a natural language question
2. Inspects the live database schema via LangChain's `SQLDatabase` tool
3. Autonomously generates and executes SQL queries (up to 10 iterations)
4. Synthesises a business-actionable answer from the query results

A rich system prompt (`prefix`) is injected to give the LLM full context on table structures, the shared category taxonomy, and query conventions (e.g., "always JOIN product_snapshots with competitors to get brand names").

**Observability:** `StreamlitCallbackHandler` renders the agent's internal thought process (tool calls, SQL generated, raw results) as expandable blocks in the UI — users can see exactly what SQL was run.

### 7.2 LLM Factory Pattern

The `llm/` module implements a factory pattern to support multiple providers without changing application code:

```mermaid
flowchart LR
    ENV[".env: LLM_PROVIDER=groq\nLLM_FALLBACK=litellm"] --> F[llm/factory.py\nget_langchain_llm()]
    F -->|provider=groq| G[llm/groq_client.py\nChatGroq wrapper]
    F -->|provider=litellm| L[llm/litellm_client.py\nChatOpenAI → LiteLLM proxy]
    G --> AGENT[LangChain SQL Agent]
    L --> AGENT
```

### 7.3 Automatic Rate-Limit Fallback

Groq enforces daily Token Per Day (TPD) limits. The AI Analyst handles this transparently:

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent (Primary LLM)
    participant F as Agent (Fallback LLM)
    participant DB as PostgreSQL

    U->>A: Ask question
    A->>DB: Generate + run SQL
    DB-->>A: Results
    A-->>U: Answer ✓

    Note over A: Rate limit hit (HTTP 429)
    U->>A: Ask question
    A->>DB: Generate + run SQL
    DB-->>A: 429 Error
    A->>A: Detect 429 in exception
    A->>F: Rebuild agent with LLM_FALLBACK provider
    F->>DB: Retry same question
    DB-->>F: Results
    F-->>U: Answer (labelled "answered by fallback")
```

### 7.4 Supported LLM Providers

| Provider | Config | Model |
|---|---|---|
| Groq | `LLM_PROVIDER=groq` | `llama-3.3-70b-versatile` |
| LiteLLM Proxy | `LLM_PROVIDER=litellm` | `claude-haiku-4.5` (or any model the proxy supports) |

---

## 8. Environment Configuration

```env
# PostgreSQL (Silver Layer)
DATABASE_URL=postgresql://user:password@localhost:5432/promo_db_v3

# MySQL (Internal Store, Bronze Layer)
MYSQL_HOST=your_host
MYSQL_PORT=3306
MYSQL_USER=readonly_user
MYSQL_PASSWORD=your_password
MYSQL_DB=fashion_retail

# LLM Provider (AI Analyst)
LLM_PROVIDER=groq                     # or: litellm
LLM_FALLBACK=litellm                  # used automatically on 429
LLM_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0
LLM_MAX_TOKENS=5000
GROQ_API_KEY=your_groq_api_key

# LiteLLM Proxy (optional)
LITELLM_API_KEY=your_key
LITELLM_API_BASE=https://your-proxy/v1

# Enrichment
ENRICHMENT_PROVIDER=gliner            # or: groq
```

---

## 9. Operational Runbook

### Full Pipeline Execution

```bash
# 1. Activate environment
source .venv/bin/activate

# 2. (Optional) start Prefect UI to monitor execution
prefect server start   # → http://localhost:4200

# 3. Run the full pipeline (scrape → enrich → ready for dashboard)
python flows/master_pipeline.py

# 4. Sync internal store data (run separately or as a cron)
python scripts/sync_own_store.py

# 5. Launch dashboard
streamlit run dashboard/app.py   # → http://localhost:8502
```

### Individual Spider Runs (Testing / Debugging)

```bash
scrapy crawl forevernew_products
scrapy crawl veromoda_products
scrapy crawl grabon
scrapy crawl coupondunia
```

### Data Maintenance

| Task | Command |
|---|---|
| Wipe & recreate all tables | `python scripts/reset_db.py` |
| Re-seed competitor config | `python scripts/seed_db.py` |
| Re-run AI enrichment only | `python scripts/backfill_categories.py` |
| Sync internal store | `python scripts/sync_own_store.py` |

---

## 10. Tech Stack Summary

| Component | Technology | Version / Notes |
|---|---|---|
| Web Scraping | Scrapy | Spider subprocess isolation for parallelism |
| Orchestration | Prefect | Flow + task model, subprocess-based parallelism |
| Silver DB | PostgreSQL | Managed via SQLAlchemy ORM + Alembic migrations |
| Bronze DB | MySQL | Read-only internal store connector |
| AI Enrichment | GLiNER | Zero-shot NER, runs locally |
| AI Enrichment | Groq / LLM | Cloud fallback with prompt batching |
| NL-to-SQL | LangChain | `create_sql_agent` + `SQLDatabase` |
| LLM Providers | Groq, LiteLLM | Factory pattern with automatic 429 fallback |
| Dashboard | Streamlit | `streamlit run dashboard/app.py` |
| Charts | Plotly | Bar, heatmap, box plot, donut |
| Design System | Custom CSS | Light theme, Inter font, minimal component library |

---

## 11. Key Design Decisions & Rationale

| Decision | Why |
|---|---|
| Subprocess isolation for Scrapy | Twisted reactor limitation — cannot run multiple spiders in one process |
| SHA-256 offer hashing | Idempotent upserts prevent duplicates across repeated runs |
| Shared `master_category` taxonomy | Enables apples-to-apples SQL joins between internal and competitor tables |
| Price-band filter on discount gap | Raw average discounts across all price ranges are statistically misleading |
| LLM factory + fallback | Groq has strict daily token limits; LiteLLM proxy provides a seamless failover |
| `.disabled` file extension for pages | Streamlit only loads `.py` files — cleanest way to hide pages without deleting code |
| GLiNER as primary enricher | No API cost, no data leaves the network, good accuracy for fashion taxonomy |
