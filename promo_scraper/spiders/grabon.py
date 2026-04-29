import re
from datetime import datetime
import scrapy
from promo_scraper.items import OfferItem
from promo_scraper.spiders.base import BasePromoSpider


class GrabonSpider(BasePromoSpider):
    name = "grabon"

    def parse(self, response, brand, source_url):
        # GrabOn wraps individual offers in elements with class 'gc-box'
        for box in response.css('.gc-box'):
            title = box.css('p.title::text').get()
            if not title:
                title = box.css('div.h3::text').get() or box.css('.gcpn-title::text').get()
            if not title:
                continue

            title = title.strip()

            li_texts = []
            for li in box.css('div[data-type="desc-div"] ul li'):
                text = ' '.join(li.css('::text').getall()).strip()
                text = re.sub(r'\s+', ' ', text)
                if text:
                    li_texts.append(text)

            raw_text = ' | '.join(li_texts) if li_texts else title

            item = OfferItem()
            item['source']      = self.name
            item['brand']       = brand
            item['source_url']  = source_url
            item['title']       = title
            item['raw_text']    = raw_text
            item['scraped_at']  = datetime.utcnow().isoformat()

            yield item
