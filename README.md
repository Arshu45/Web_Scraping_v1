# Promo Scraper

A highly scalable, multi-source web scraping pipeline built with [Scrapy](https://scrapy.org/). This project extracts promotional offers and discounts from various sources, currently supporting **CouponDunia** and **GrabOn**.

## 🏗️ Architecture Features

- **Generic Data Model**: All scraped items conform to the standard `OfferItem` schema (`source`, `brand`, `title`, `raw_text`, `scraped_at`).
- **Configuration-Driven**: Spiders do not contain hardcoded URLs. They read targets dynamically from `config/targets.json`.
- **Automated Routing**: The custom `BrandJSONPipeline` intercepts items from any spider and seamlessly routes them into distinct JSON files formatted as `{source}_{brand}_offers.json`. This prevents data collisions between different scraping sources.
- **Polite & Responsible**: Configured with Scrapy AutoThrottle and a realistic User-Agent to respect target servers.

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python 3.10+ installed. Set up your virtual environment and install Scrapy:

```bash
python -m venv .venv
source .venv/bin/activate
pip install scrapy
```

### 2. Configuration (`config/targets.json`)
Manage your scraping targets via the hierarchical JSON configuration file. You can enable or disable entire sources or specific brands by toggling the `"enabled"` boolean flag.

```json
{
  "sources": [
    {
      "name": "coupondunia",
      "enabled": true,
      "brands": [
        {
          "name": "Myntra",
          "url": "https://www.coupondunia.in/myntra",
          "enabled": true
        }
      ]
    }
  ]
}
```

### 3. Running Spiders
Run the spiders from the terminal using the `scrapy crawl` command:

```bash
# Run the CouponDunia spider
scrapy crawl coupondunia

# Run the GrabOn spider
scrapy crawl grabon
```

### 4. Output
Scraped data will be saved in the `data/` directory (created automatically). The output files will be named based on the source and brand, for example:
- `data/coupondunia_myntra_offers.json`
- `data/grabon_ajio_offers.json`

## 🛠️ Adding New Spiders
This architecture is built to scale. To add a new spider (e.g., for Amazon):
1. Add the new source block to `config/targets.json`.
2. Create a new spider file in `promo_scraper/spiders/`.
3. Read the targets in `start_requests()`.
4. In your `parse()` method, yield an `OfferItem`. 

The central pipeline will automatically handle the rest, from file creation to JSON formatting!
