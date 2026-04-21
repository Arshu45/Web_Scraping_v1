import json
import os
import re
from datetime import datetime
import scrapy
from promo_scraper.items import OfferItem

class CouponduniaSpider(scrapy.Spider):
    name = "coupondunia"
    
    def start_requests(self):
        # Locate and load the targets JSON
        config_path = os.path.join('config', 'targets.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        for source in config.get('sources', []):
            if source.get('enabled') and source.get('name') == self.name:
                for brand in source.get('brands', []):
                    if brand.get('enabled'):
                        yield scrapy.Request(
                            url=brand['url'],
                            callback=self.parse,
                            cb_kwargs={'brand': brand['name']}
                        )

    def parse(self, response, brand):
        # The offer terms are grouped inside <ol> tags
        ol_tags = response.css('ol')
        
        for ol in ol_tags:
            li_texts = []
            
            for li in ol.css('li'):
                # Extract text using native Scrapy selectors, stripping whitespace
                text = ' '.join(li.css('::text').getall()).strip()
                if text:
                    # Remove "1. " style prefixes
                    text = re.sub(r'^\d+\.\s*', '', text)
                    li_texts.append(text)
            
            # Skip if no items found
            if not li_texts:
                continue
                
            # First <li> is the title
            title = li_texts[0]
            # Join all <li> strings with " | "
            raw_text = ' | '.join(li_texts)
            
            item = OfferItem()
            item['source'] = self.name
            item['brand'] = brand
            item['title'] = title
            item['raw_text'] = raw_text
            item['scraped_at'] = datetime.utcnow().isoformat()
            
            yield item
