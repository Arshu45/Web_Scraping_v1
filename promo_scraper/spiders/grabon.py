import json
import os
import re
from datetime import datetime
import scrapy
from promo_scraper.items import OfferItem

class GrabonSpider(scrapy.Spider):
    name = "grabon"
    
    def start_requests(self):
        # Locate and load the targets JSON
        config_path = os.path.join('config', 'targets.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        for source in config.get('sources', []):
            if source.get('enabled') and source.get('name') == self.name:
                for brand in source.get('brands', []):
                    if brand.get('enabled'):
                        # Add a realistic User-Agent specifically for Grabon to avoid 403s if any
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.5',
                        }
                        yield scrapy.Request(
                            url=brand['url'],
                            callback=self.parse,
                            headers=headers,
                            cb_kwargs={'brand': brand['name']}
                        )

    def parse(self, response, brand):
        # GrabOn wraps individual offers in elements with class 'gc-box'
        offer_boxes = response.css('.gc-box')
        
        for box in offer_boxes:
            # Extract the title
            title = box.css('p.title::text').get()
            if not title:
                # Fallback to other title classes if p.title is missing
                title = box.css('div.h3::text').get() or box.css('.gcpn-title::text').get()
                if not title:
                    continue
                    
            title = title.strip()
            
            # Extract list items from the description div
            li_texts = []
            for li in box.css('div[data-type="desc-div"] ul li'):
                # Extract all text nodes within the <li> and join them
                text = ' '.join(li.css('::text').getall()).strip()
                # Clean up excessive whitespace
                text = re.sub(r'\s+', ' ', text)
                if text:
                    li_texts.append(text)
            
            # If no list items, fallback to the title as raw_text
            raw_text = ' | '.join(li_texts) if li_texts else title
            
            item = OfferItem()
            item['source'] = self.name
            item['brand'] = brand
            item['title'] = title
            item['raw_text'] = raw_text
            item['scraped_at'] = datetime.utcnow().isoformat()
            
            yield item
