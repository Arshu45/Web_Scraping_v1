import re
from datetime import datetime
import scrapy
from promo_scraper.items import OfferItem
from promo_scraper.spiders.base import BasePromoSpider


class CouponduniaSpider(BasePromoSpider):
    name = "coupondunia"

    def parse(self, response, brand, source_url):
        # Offer terms are grouped inside <ol> tags on CouponDunia
        for ol in response.css('ol'):
            li_texts = []

            for li in ol.css('li'):
                text = ' '.join(li.css('::text').getall()).strip()
                if text:
                    text = re.sub(r'^\d+\.\s*', '', text)  # Remove "1. " prefixes
                    li_texts.append(text)

            if not li_texts:
                continue

            item = OfferItem()
            item['source']      = self.name
            item['brand']       = brand
            item['source_url']  = source_url
            item['title']       = li_texts[0]
            item['raw_text']    = ' | '.join(li_texts)
            item['scraped_at']  = datetime.utcnow().isoformat()

            yield item
