import scrapy

class OfferItem(scrapy.Item):
    source = scrapy.Field()      # e.g., "coupondunia", "amazon_direct"
    brand = scrapy.Field()       # e.g., "Myntra", "Nike"
    title = scrapy.Field()       # First list item or main title
    raw_text = scrapy.Field()    # Full terms joined by " | "
    scraped_at = scrapy.Field()  # ISO timestamp
