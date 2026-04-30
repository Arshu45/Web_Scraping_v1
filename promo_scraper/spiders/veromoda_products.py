"""
Vero Moda Products Crawler — Full catalog crawler for veromoda.in

Strategy:
  1. Start at the homepage and discover all category links matching `/collections/`.
  2. For each category, parse the `<product-card>` elements which hold structured data
     in their attributes (`data-price-cents`, `data-compare-at-cents`, `handle`).
  3. Extract both on-sale and full-price items seamlessly.
  4. Yield ProductSnapshotItem — no NLP needed.
"""
import re
from urllib.parse import urlparse, urljoin
import scrapy
from promo_scraper.items import ProductSnapshotItem

BASE_URL   = 'https://www.veromoda.in'
BRAND_NAME = 'Vero Moda'

class VeroModaProductsSpider(scrapy.Spider):
    name = 'veromoda_products'
    allowed_domains = ['veromoda.in']
    start_urls = [BASE_URL]

    def parse(self, response):
        """Step 1: Discover all category URLs from the homepage nav."""
        seen = set()
        
        # Discover all collection links
        nav_links = response.css('a[href*="/collections/"]::attr(href)').getall()

        for href in nav_links:
            url = urljoin(BASE_URL, href).split('?')[0]  # Strip query params

            if url in seen:
                continue

            seen.add(url)
            cat_path, cat_label = self._category_from_url(url)
            self.logger.info(f'[Category discovered] {cat_label} → {url}')
            
            yield response.follow(
                url,
                callback=self.parse_category,
                cb_kwargs={'cat_path': cat_path, 'cat_label': cat_label},
            )

    def parse_category(self, response, cat_path, cat_label):
        """Step 2: Extract all products on a category page + follow pagination."""
        cards = response.css('product-card')
        self.logger.info(f'[{cat_label}] {response.url} → {len(cards)} products')

        for card in cards:
            handle = card.attrib.get('handle')
            if not handle:
                continue

            name = card.css('a.product-title::text').get('').strip()
            href = card.css('a.product-title::attr(href)').get()
            url  = urljoin(BASE_URL, href) if href else f"{BASE_URL}/products/{handle}"

            price_c = card.attrib.get('data-price-cents', '')
            mrp_c   = card.attrib.get('data-compare-at-cents', '')
            
            # Prices are in cents
            current_price = int(price_c) / 100 if price_c and price_c.isdigit() else None
            
            if not current_price:
                continue # Skip if no price

            original_price = int(mrp_c) / 100 if mrp_c and mrp_c.isdigit() and mrp_c != '0' else None

            is_on_sale = False
            discount_percentage = None
            
            if original_price and original_price > current_price:
                is_on_sale = True
                disc_str = card.css('span.text-on-sale::text').get('').strip()
                if disc_str:
                    nums = re.findall(r'\d+\.?\d*', disc_str)
                    discount_percentage = float(nums[0]) if nums else None

            item = ProductSnapshotItem()
            item['competitor_name']     = BRAND_NAME
            item['product_name']        = name
            item['product_url']         = url
            item['sku']                 = handle
            item['category_path']       = cat_path
            item['category_label']      = cat_label
            item['original_price']      = original_price
            item['sale_price']          = current_price
            item['discount_percentage'] = discount_percentage
            item['is_on_sale']          = is_on_sale

            yield item

        # Step 3: Pagination
        next_page = response.css('a[rel="next"]::attr(href)').get()
        if next_page:
            yield response.follow(
                next_page,
                callback=self.parse_category,
                cb_kwargs={'cat_path': cat_path, 'cat_label': cat_label},
            )

    def _category_from_url(self, url: str) -> tuple[str, str]:
        """
        Derive category_path and human-readable label from a URL.
        '/collections/all-products-dresses' → ('collections/all-products-dresses', 'All Products Dresses')
        """
        path = urlparse(url).path.strip('/').replace('.html', '')
        label = path.split('/')[-1].replace('-', ' ').title()
        return path, label
