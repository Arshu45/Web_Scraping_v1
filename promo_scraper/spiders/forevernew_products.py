"""
ForeverNewProductsSpider — Self-discovering product-level catalog crawler.

Strategy:
  1. Start at /sale.html to auto-discover all sale category URLs.
  2. Filter out facet/filter URLs (size=, color=, etc.).
  3. For each clean category URL, paginate and extract every product card.
  4. Yield a ProductSnapshotItem per product — no NLP, pure HTML extraction.
"""
import re
import scrapy
from urllib.parse import urlparse, urljoin
from promo_scraper.items import ProductSnapshotItem

# Patterns in URL query/path that indicate a facet/filter page, not a real category
SKIP_PATTERNS = [
    'size=', 'primary_colors=', 'discount_new=', 'price_filter=',
    'shop_by_fit=', 'shop_by_pattern=', 'cate_occasion=',
]

BASE_URL = 'https://www.forevernew.co.in'
BRAND_NAME = 'Forever New'


def _parse_price(price_str: str) -> float | None:
    """Convert '₹9,800.00' → 9800.0"""
    if not price_str:
        return None
    cleaned = re.sub(r'[^\d.]', '', price_str.replace(',', ''))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_discount(discount_str: str) -> float | None:
    """Convert '30% OFF' → 30.0"""
    if not discount_str:
        return None
    nums = re.findall(r'\d+\.?\d*', discount_str)
    return float(nums[0]) if nums else None


def _category_from_url(url: str) -> tuple[str, str]:
    """
    Derive a category path and human-readable label from a URL.
    e.g., 'https://www.forevernew.co.in/sale/clothing/jackets-blazers.html'
          → ('sale/clothing/jackets-blazers', 'Jackets Blazers')
    """
    path = urlparse(url).path.strip('/')
    path = path.replace('.html', '')
    label = path.split('/')[-1].replace('-', ' ').title()
    return path, label


class ForeverNewProductsSpider(scrapy.Spider):
    name = 'forevernew'
    allowed_domains = ['forevernew.co.in']
    start_urls = [f'{BASE_URL}/sale.html']

    def parse(self, response):
        """Step 1: Discover all clean sale category URLs from /sale.html."""
        seen = set()
        raw_links = response.css('a[href*="/sale/"]::attr(href)').getall()

        for href in raw_links:
            # Make absolute
            url = urljoin(BASE_URL, href)

            # Skip if it's a facet/filter URL
            if any(pat in url for pat in SKIP_PATTERNS):
                continue

            # Only proper category .html pages
            if not url.endswith('.html'):
                continue

            # Skip the /sale.html index itself
            if url.rstrip('/') == f'{BASE_URL}/sale.html'.rstrip('/'):
                continue

            if url not in seen:
                seen.add(url)
                cat_path, cat_label = _category_from_url(url)
                self.logger.info(f'[Category discovered] {cat_label} → {url}')
                yield response.follow(
                    url,
                    callback=self.parse_category,
                    cb_kwargs={'cat_path': cat_path, 'cat_label': cat_label},
                )

    def parse_category(self, response, cat_path, cat_label):
        """Step 2: Extract every product card on this page."""
        cards = response.css('li.item.product.product-item')
        self.logger.info(f'[{cat_label}] Page {response.url} → {len(cards)} products')

        for card in cards:
            name = card.css('strong.product-item-name a::text').get('').strip()
            url  = card.css('a.product-item-link::attr(href)').get()
            orig = _parse_price(card.css('span.old-price .price::text').get())
            sale = _parse_price(card.css('span.special-price .price::text').get())
            disc = _parse_discount(card.css('div.price-off::text').get())

            # Skip cards with no pricing data
            if not name or not url or not sale:
                continue

            # If there is no old-price label, the item is full-price — skip
            if not orig:
                continue

            item = ProductSnapshotItem()
            item['competitor_name']     = BRAND_NAME
            item['product_name']        = name
            item['product_url']         = url
            item['category_path']       = cat_path
            item['category_label']      = cat_label
            item['original_price']      = orig
            item['sale_price']          = sale
            item['discount_percentage'] = disc

            yield item

        # Step 3: Pagination — follow the "Next" button if it exists
        next_page = response.css('a.action.next::attr(href)').get()
        if next_page:
            yield response.follow(
                next_page,
                callback=self.parse_category,
                cb_kwargs={'cat_path': cat_path, 'cat_label': cat_label},
            )
