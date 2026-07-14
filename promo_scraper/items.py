import scrapy


class OfferItem(scrapy.Item):
    # Provenance
    source      = scrapy.Field()   # Spider name
    brand       = scrapy.Field()   # Competitor name
    source_url  = scrapy.Field()   # Exact page scraped

    # Content
    title       = scrapy.Field()   # Short title / headline
    category    = scrapy.Field()   # Business category for weekly reporting

    # Metadata
    scraped_at  = scrapy.Field()   # ISO timestamp
