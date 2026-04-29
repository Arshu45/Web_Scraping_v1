import scrapy


class OfferItem(scrapy.Item):
    # Provenance
    source      = scrapy.Field()   # Spider name: "coupondunia", "grabon"
    brand       = scrapy.Field()   # Competitor name: "Myntra", "Ajio"
    source_url  = scrapy.Field()   # Exact page scraped

    # Content
    title       = scrapy.Field()   # Short title / headline
    raw_text    = scrapy.Field()   # Full scraped text joined with " | "

    # Structured fields (populated by GLiNER enrichment pass)
    promo_type    = scrapy.Field() # "Percentage Off", "Flat Discount", "Cashback"
    discount_min  = scrapy.Field() # e.g., 40.0
    discount_max  = scrapy.Field() # e.g., 70.0
    flat_value    = scrapy.Field() # e.g., 300.0 (₹300 off)
    min_purchase  = scrapy.Field() # e.g., 1499.0
    coupon_code   = scrapy.Field() # e.g., "SAVE20"
    user_type     = scrapy.Field() # "new", "existing", "all"
    valid_until   = scrapy.Field() # Date string, e.g., "2024-12-31"
    category      = scrapy.Field() # "Apparel", "Accessories", etc.

    # Metadata
    scraped_at  = scrapy.Field()   # ISO timestamp


class ProductSnapshotItem(scrapy.Item):
    """
    Represents a single discounted product scraped directly from a brand's
    e-commerce catalog (e.g., forevernew.co.in/sale/).
    Stored in the `product_snapshots` table.
    """
    competitor_name     = scrapy.Field()   # e.g., "Forever New"
    product_name        = scrapy.Field()   # e.g., "Angie Petite Halter Linen Midi Dress"
    product_url         = scrapy.Field()   # Full absolute URL (deduplication key)

    # Category (auto-derived from the crawled URL, no manual config needed)
    category_path       = scrapy.Field()   # e.g., "sale/clothing/jackets-blazers"
    category_label      = scrapy.Field()   # e.g., "Jackets Blazers"

    # Exact pricing
    original_price      = scrapy.Field()   # e.g., 9800.0
    sale_price          = scrapy.Field()   # e.g., 6860.0
    discount_percentage = scrapy.Field()   # e.g., 30.0
