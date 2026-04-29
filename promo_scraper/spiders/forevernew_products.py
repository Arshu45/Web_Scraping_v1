"""
ForeverNewProductsSpider — Full catalog crawler for forevernew.co.in

Strategy:
  1. Start at the homepage and discover all main nav category links.
  2. For each category, follow subcategory links then paginate all product pages.
  3. Extract EVERY product — both on-sale and full-price.
  4. Set is_on_sale=True only when a strikethrough (old-price) is present.
  5. Yield ProductSnapshotItem — no NLP needed, all data is in the HTML.
"""
import re
from urllib.parse import urlparse, urljoin
import scrapy
from promo_scraper.items import ProductSnapshotItem

# Base URL and brand
BASE_URL   = 'https://www.forevernew.co.in'
BRAND_NAME = 'Forever New'

# URL fragments that indicate filter/facet pages — skip these
SKIP_PATTERNS = [
    'size=', 'primary_colors=', 'discount_new=', 'price_filter=',
    'shop_by_fit=', 'shop_by_pattern=', 'cate_occasion=',
    'javascript', 'login', 'account', 'checkout', 'cart', 'wishlist',
    'search', 'customer', 'contact', '#',
]

# Top-level nav path segments we care about (clothing, bags, etc.)
CATALOG_PATHS = [
    '/clothing',
    '/bags-accessories',
    '/jewellery',
    '/accessories',
    '/sale',
]


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


def _extract_sku(url: str) -> str | None:
    """Extract SKU from product URL: '...cp-30128201.html' → 'cp-30128201'"""
    match = re.search(r'(cp-\d+)', url)
    return match.group(1) if match else None


def _category_from_url(url: str) -> tuple[str, str]:
    """
    Derive category_path and human-readable label from a URL.
    '/clothing/dresses.html' → ('clothing/dresses', 'Dresses')
    """
    path = urlparse(url).path.strip('/').replace('.html', '')
    label = path.split('/')[-1].replace('-', ' ').title()
    return path, label


def _is_catalog_url(url: str) -> bool:
    """True if the URL is a real category page we should crawl."""
    if any(pat in url for pat in SKIP_PATTERNS):
        return False
    if not url.endswith('.html'):
        return False
    path = urlparse(url).path
    return any(path.startswith(cat) for cat in CATALOG_PATHS)


class ForeverNewProductsSpider(scrapy.Spider):
    name = 'forevernew_products'
    allowed_domains = ['forevernew.co.in']
    start_urls = [BASE_URL]

    def parse(self, response):
        """Step 1: Discover all category URLs from the homepage nav."""
        seen = set()
        all_links = response.css('a::attr(href)').getall()

        for href in all_links:
            url = urljoin(BASE_URL, href).split('?')[0]  # Strip query params

            if url in seen:
                continue
            if not _is_catalog_url(url):
                continue

            seen.add(url)
            cat_path, cat_label = _category_from_url(url)
            self.logger.info(f'[Category discovered] {cat_label} → {url}')
            yield response.follow(
                url,
                callback=self.parse_category,
                cb_kwargs={'cat_path': cat_path, 'cat_label': cat_label},
            )

    def parse_category(self, response, cat_path, cat_label):
        """Step 2: Extract all products on a category page + follow pagination."""
        cards = response.css('li.item.product.product-item')
        self.logger.info(f'[{cat_label}] {response.url} → {len(cards)} products')

        for card in cards:
            name = card.css('strong.product-item-name a::text').get('').strip()
            url  = card.css('a.product-item-link::attr(href)').get()

            if not name or not url:
                continue

            # Old/MRP price exists only on discounted products
            orig_str = card.css('span.old-price .price::text').get()
            # sale_price is the CSS key Magento uses for both discounted and regular prices
            curr_str = (
                card.css('span.special-price .price::text').get()
                or card.css('.price-box .price::text').get()
            )

            current_price = _parse_price(curr_str)
            if not current_price:
                continue  # No price at all — skip

            original_price      = _parse_price(orig_str)
            is_on_sale          = original_price is not None
            discount_percentage = _parse_discount(card.css('div.price-off::text').get()) if is_on_sale else None

            item = ProductSnapshotItem()
            item['competitor_name']     = BRAND_NAME
            item['product_name']        = name
            item['product_url']         = url
            item['sku']                 = _extract_sku(url)
            item['category_path']       = cat_path
            item['category_label']      = cat_label
            item['original_price']      = original_price     # MRP — None for full-price items
            item['sale_price']          = current_price      # What you actually pay
            item['discount_percentage'] = discount_percentage
            item['is_on_sale']          = is_on_sale

            yield item

        # Step 3: Pagination
        next_page = response.css('a.action.next::attr(href)').get()
        if next_page:
            yield response.follow(
                next_page,
                callback=self.parse_category,
                cb_kwargs={'cat_path': cat_path, 'cat_label': cat_label},
            )
