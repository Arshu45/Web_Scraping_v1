"""
hybrid_promo_extractor.py
=========================
Multi-strategy promotional offer extractor for retail websites.

Supports three extraction strategies (set per site in config):

  "text"       — Scrape promo text directly from HTML elements.
                 No Vision API needed. Works for sites with text-based banners.

  "screenshot" — Playwright screenshots banner *elements* from within the live
                 browser session, then sends screenshots to Gemini Vision.
                 Bypasses CDN 403s because no external image download is needed.

  "image"      — Original strategy: collect <img> src URLs, download via httpx,
                 send to Gemini Vision. Works when CDN allows external downloads.

  "hybrid"     — Runs "text" + "screenshot" together.

All strategies yield offer dicts that feed into the existing PostgresPipeline.
"""

import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from io import BytesIO
from typing import Any

import httpx
import google.genai as genai
from google.genai import types as genai_types
from PIL import Image
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_message,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

# Global rate limiting for Gemini Vision calls (max 15 RPM under free tier)
_gemini_lock = threading.Lock()
_last_gemini_time = 0.0
GEMINI_MIN_DELAY = 4.5  # Ensure at least 4.5s delay between requests



# ── Gemini Vision prompt ────────────────────────────────────────────────────
VISION_PROMPT = """You are a retail promotions analyst.
Examine the promotional banner image provided.
Extract every offer or discount visible in the image.

Return a JSON array only — no explanation, no markdown, no code fences.
Each element must have exactly these fields:
  - "promo_text"   : the full offer text as it appears in the image
  - "category"     : the product category (e.g. "Clothing", "Footwear", "Bedding")
  - "discount_min" : lower bound discount % as an integer, or null
  - "discount_max" : upper bound discount % as an integer, or null
  - "confidence"   : "high", "medium", or "low"

If the image contains no promotional text (lifestyle photo, brand logo, product photo), return: []
Do not infer or estimate discounts. Only extract text explicitly visible in the image."""

# ── Common browser setup ────────────────────────────────────────────────────
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


class HybridPromoExtractor:
    """
    Extracts promotional offers from a single retail site.

    Config keys:
        brand, source_url, extraction_strategy ("text"|"screenshot"|"image"|"hybrid")
        text_selectors      list[str]  — CSS selectors for text extraction
        screenshot_selectors list[str] — CSS selectors for element screenshots
        banner_selectors    list[str]  — CSS selectors for <img> src URLs (image strategy)
        min_image_width     int        — filter small images (default 400)
        min_image_height    int        — filter thin strips (default 150)
        min_aspect_ratio    float      — filter non-banner shapes (default 1.2)
        exclude_url_patterns list[str] — URL substrings to skip
        request_delay_seconds int      — delay between Gemini calls (default 4)
        scroll_depth        int        — scroll iterations to trigger lazy load (default 3)
    """

    COST_PER_IMAGE_USD = 0.000075   
    GEMINI_MODEL       = "gemini-2.5-flash"

    def __init__(self, target_config: dict):
        self.cfg        = target_config
        self.brand      = target_config["brand"]
        # Can be a single URL string or a list of URL strings
        raw_url = target_config["source_url"]
        if isinstance(raw_url, list):
            self.source_urls = raw_url
            self.source_url = raw_url[0] if raw_url else ""
        else:
            self.source_urls = [raw_url]
            self.source_url = raw_url
        self.strategy   = target_config.get("extraction_strategy", "image")

        # Image filter thresholds
        self.min_width  = target_config.get("min_image_width",  400)
        self.min_height = target_config.get("min_image_height", 150)
        self.min_aspect = target_config.get("min_aspect_ratio", 1.2)
        self.exclude_patterns = target_config.get("exclude_url_patterns", [
            "/logo", "/icon", "/avatar", "social", "payment", "brand-logo",
        ])
        self.delay       = target_config.get("request_delay_seconds", 4)
        self.scroll_depth = target_config.get("scroll_depth", 3)

        # Counters
        self._images_found     = 0
        self._images_processed = 0
        self._images_skipped   = 0
        self._offers_extracted = 0
        self._gemini_api_calls = 0

        # Select client type (litellm or direct gemini)
        self.use_litellm = bool(os.getenv("LITELLM_API_BASE"))
        if self.use_litellm:
            model_name = os.getenv("VISION_LLM_MODEL") or os.getenv("LLM_MODEL")
            if not model_name:
                raise EnvironmentError("VISION_LLM_MODEL or LLM_MODEL must be set in .env when using LiteLLM.")
            if "/" not in model_name:
                self.model = f"openai/{model_name}"
            else:
                self.model = model_name
        else:
            self.model = os.getenv("VISION_LLM_MODEL") or self.GEMINI_MODEL

        # Init API client (only needed for screenshot / image strategies)
        if self.strategy in ("screenshot", "image", "hybrid"):
            if self.use_litellm:
                import litellm
                litellm.suppress_debug_info = True
                self._client = litellm
            else:
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise EnvironmentError(
                        "GEMINI_API_KEY is not set. Add it to .env.\n"
                        "Free key: https://aistudio.google.com/app/apikey"
                    )
                self._client = genai.Client(api_key=api_key)
        else:
            self._client = None

        logger.info(
            "HybridPromoExtractor ready: brand='%s', strategy='%s', model=%s (via %s)",
            self.brand, self.strategy, self.model, "litellm" if self.use_litellm else "direct gemini",
        )

    # ═══════════════════════════════════════════════════════════════════════
    # Public entry point
    # ═══════════════════════════════════════════════════════════════════════

    def run(self) -> dict[str, Any]:
        """Run the extraction pipeline. Returns a summary dict."""
        all_offer_items: list[dict] = []

        for url in self.source_urls:
            self.source_url = url
            logger.info("Starting extraction → %s [strategy=%s]", self.source_url, self.strategy)

            offer_items: list[dict] = []

            if self.strategy in ("text", "screenshot", "hybrid"):
                offer_items = self._run_playwright_extraction()
            elif self.strategy == "image":
                offer_items = self._run_image()
            else:
                logger.error("Unknown strategy '%s' — skipping", self.strategy)
                continue

            all_offer_items.extend(offer_items)

        # Deduplicate extracted offers within this run to ensure clean reporting
        seen_keys = set()
        deduped_items = []
        for item in all_offer_items:
            title_clean = (item.get("title") or "").strip()
            item["title"] = title_clean
            key = (item.get("source"), item.get("brand"), title_clean.lower())
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_items.append(item)
        all_offer_items = deduped_items

        self._offers_extracted = len(all_offer_items)
        summary = {
            "brand":             self.brand,
            "strategy":          self.strategy,
            "images_found":      self._images_found,
            "images_processed":  self._images_processed,
            "images_skipped":    self._images_skipped,
            "offers_extracted":  self._offers_extracted,
            "offers_stored":     0,
            "gemini_api_calls":  self._gemini_api_calls,
            "estimated_cost_usd": round(self._gemini_api_calls * self.COST_PER_IMAGE_USD, 6),
            "offer_items":       all_offer_items,
        }
        logger.info(
            "Done: %d offers from %d images processed | cost=$%s",
            self._offers_extracted, self._images_processed, summary["estimated_cost_usd"],
        )
        return summary

    def _create_stealth_page(self, pw) -> tuple[Any, Any]:
        """Launch browser and context with stealth settings to bypass anti-bot screens."""
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080",
            ]
        )
        context = browser.new_context(
            user_agent=_UA,
            viewport={"width": 1920, "height": 1080},
            extra_http_headers={
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "accept-language": "en-US,en;q=0.9",
                "sec-ch-ua": '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }
        )
        page = context.new_page()
        page.add_init_script("delete navigator.__proto__.webdriver;")
        return browser, page

    def _run_playwright_extraction(self) -> list[dict]:
        """
        Unified Playwright extraction flow for text and screenshot/hybrid strategies.
        Uses stealth parameters to bypass Cloudflare/Akamai bot detection.
        """
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        offer_items: list[dict] = []
        seen_hashes: set[str] = set()

        with sync_playwright() as pw:
            browser, page = self._create_stealth_page(pw)
            try:
                page.goto(self.source_url, timeout=60_000, wait_until="domcontentloaded")
                self._wait_and_scroll(page)

                # 1. Text Extraction Strategy
                if self.strategy in ("text", "hybrid"):
                    text_selectors = self.cfg.get("text_selectors", [])
                    candidate_texts: list[str] = []
                    seen_norms: set[str] = set()

                    def _norm(s: str) -> str:
                        # Strip punctuation/separators so "Buy 2, Get 30% Off"
                        # and "Buy 2 Get 30% Off" (desktop vs. mobile-nav
                        # copies of the same link) dedupe as one offer.
                        return re.sub(r"[^\w\s%$]", "", s).lower().strip()

                    for selector in text_selectors:
                        try:
                            elements = page.query_selector_all(selector)
                        except Exception:
                            continue
                        for el in elements:
                            try:
                                # Skip elements hidden via responsive
                                # (mobile/desktop) breakpoint classes — Playwright's
                                # inner_text() doesn't apply normal line-break-to-space
                                # conversion on unlaid-out elements, so a hidden
                                # duplicate can come back malformed (e.g. "GET30%"
                                # instead of "GET 30%") and defeat dedup.
                                if not el.is_visible():
                                    continue
                                text = el.inner_text().strip()
                            except Exception:
                                continue

                            # Deduplicate & filter noise
                            text = re.sub(r"\s+", " ", text)
                            if not text or len(text) < 8:
                                continue
                            norm = _norm(text)
                            if not norm or norm in seen_norms:
                                continue

                            # Skip leaked <style>/CSS content some themes render as
                            # visible text (e.g. scoped block-width rules)
                            if re.search(r"[.#]?[\w-]+\s*\{[^{}]*:[^{}]*\}", text):
                                continue

                            seen_norms.add(norm)

                            # Only keep text that looks promotional (percentage off, free
                            # shipping, multibuy/price-threshold offers like "2 for $99",
                            # "Jackets from $99", or "2 from AU$599", etc.)
                            if not re.search(
                                r"\d+\s*%|off|sale|deal|save|discount|extra|free\s+(delivery|shipping|gift)"
                                r"|clearance|offer|\bfor\s+[A-Za-z]{0,3}\$\d|\bfrom\s+[A-Za-z]{0,3}\$\d",
                                text, re.I,
                            ):
                                continue

                            logger.info("  TEXT  %-60s [%s]", text[:60], selector)
                            candidate_texts.append(text)

                    # Overlapping/nested selectors (e.g. a broad container matched
                    # alongside its own child) can yield several near-duplicate
                    # strings that are prefixes/substrings of one another — keep
                    # only the longest version of each (compared on normalized form
                    # so punctuation differences don't defeat the check).
                    candidate_texts.sort(key=len, reverse=True)
                    kept_texts: list[str] = []
                    kept_norms: list[str] = []
                    for text in candidate_texts:
                        norm = _norm(text)
                        if any(norm in longer_norm for longer_norm in kept_norms):
                            continue
                        kept_texts.append(text)
                        kept_norms.append(norm)

                    for text in kept_texts:
                        offer_items.append(self._make_text_offer(text))

                # 2. Screenshot/Vision Strategy
                if self.strategy in ("screenshot", "hybrid"):
                    screenshot_selectors = self.cfg.get("screenshot_selectors", [])
                    if not screenshot_selectors:
                        # Generic default selectors to locate promos/banners
                        screenshot_selectors = [
                            "[class*='Hero']", "[class*='hero']",
                            "[class*='Banner']", "[class*='banner']",
                            "[class*='Editorial']", "[class*='editorial']",
                            "[class*='Promo']", "[class*='promo']",
                            "[class*='Campaign']", "[class*='campaign']",
                            ".discover-more", ".discover-more-content", ".dm-sale",
                            "img"
                        ]

                    for selector in screenshot_selectors:
                        try:
                            elements = page.query_selector_all(selector)
                        except Exception:
                            continue
                        logger.debug("Selector '%s' → %d elements", selector, len(elements))

                        for el in elements:
                            # Handle IMG tags (both visible and hidden)
                            is_img = False
                            img_src = ""
                            try:
                                if el.evaluate("el => el.tagName") == "IMG":
                                    is_img = True
                                    img_src = el.get_attribute("src") or el.get_attribute("data-src") or ""
                                    if img_src.startswith("//"):
                                        img_src = "https:" + img_src
                                    elif img_src.startswith("/"):
                                        from urllib.parse import urlparse
                                        parsed = urlparse(self.source_url)
                                        img_src = f"{parsed.scheme}://{parsed.netloc}{img_src}"
                            except Exception:
                                pass

                            if is_img and img_src:
                                if any(p in img_src.lower() for p in self.exclude_patterns):
                                    continue

                            # Visibility check
                            box = None
                            try:
                                box = el.bounding_box()
                            except Exception:
                                pass

                            ss_bytes = None
                            if is_img and img_src:
                                # For IMG tags, if visible we can screenshot; if hidden we fetch bytes directly
                                if box and box['width'] >= 100 and box['height'] >= 50:
                                    try:
                                        ss_bytes = el.screenshot()
                                    except Exception:
                                        pass
                                
                                # If screenshot failed or element is hidden, fetch via browser API to bypass CORS/403
                                if not ss_bytes:
                                    try:
                                        logger.info("Fetching hidden/uncaptured image bytes for: %s", img_src[:80])
                                        image_b64 = page.evaluate("""async (url) => {
                                            const response = await fetch(url);
                                            const blob = await response.blob();
                                            return new Promise((resolve, reject) => {
                                                const reader = new FileReader();
                                                reader.onloadend = () => resolve(reader.result.split(',')[1]);
                                                reader.onerror = reject;
                                                reader.readAsDataURL(blob);
                                            });
                                        }""", img_src)
                                        import base64
                                        ss_bytes = base64.b64decode(image_b64)
                                    except Exception as e:
                                        logger.debug("Failed to fetch image bytes via browser fetch: %s", e)
                                        continue
                            else:
                                # For non-img elements (containers, divs), they MUST be visible
                                if not box or box['width'] < 100 or box['height'] < 50:
                                    continue
                                try:
                                    ss_bytes = el.screenshot()
                                except Exception:
                                    continue

                            if not ss_bytes:
                                continue

                            # Deduplicate identical screenshots
                            ss_hash = hashlib.md5(ss_bytes).hexdigest()
                            if ss_hash in seen_hashes:
                                continue
                            seen_hashes.add(ss_hash)

                            # Check dimensions
                            try:
                                img = Image.open(BytesIO(ss_bytes))
                                if img.width < self.min_width or img.height < self.min_height:
                                    continue
                                if img.width > 0 and (img.width / max(img.height, 1)) < self.min_aspect:
                                    continue
                            except Exception:
                                continue

                            self._images_found += 1
                            label = f"screenshot:{selector}"

                            if self._gemini_api_calls > 0:
                                time.sleep(self.delay)

                            offers = self._vision_extract(ss_bytes, "image/png", label)
                            if offers:
                                items = self._build_offer_items(offers, label)
                                offer_items.extend(items)
                                self._images_processed += 1
                                logger.info("  SHOT  %d offers from selector '%s'", len(items), selector)
                            else:
                                self._images_skipped += 1

            except PWTimeout:
                logger.error("Playwright timed out loading %s", self.source_url)
            except Exception as e:
                logger.error("Playwright extraction error: %s", e)
            finally:
                browser.close()

        logger.info("Playwright strategy: %d images/elements processed → %d offers",
                    self._images_processed, len(offer_items))
        return offer_items


    # ═══════════════════════════════════════════════════════════════════════
    # Strategy 3: IMAGE — download <img> src URLs, send to Gemini Vision
    # ═══════════════════════════════════════════════════════════════════════

    def _run_image(self) -> list[dict]:
        """Original strategy: collect img src URLs → download → Gemini Vision."""
        image_urls = self._collect_image_urls()
        self._images_found = len(image_urls)
        logger.info("Image strategy: %d candidate URLs", self._images_found)

        offer_items: list[dict] = []

        for url in image_urls:
            if self._gemini_api_calls > 0:
                time.sleep(self.delay)

            img_bytes, mime = self._download_image(url)
            if img_bytes is None:
                self._images_skipped += 1
                continue

            offers = self._vision_extract(img_bytes, mime, url)
            if offers:
                offer_items.extend(self._build_offer_items(offers, url))
                self._images_processed += 1
                logger.info("  IMG  %d offers from %s", len(offers), url)
            else:
                self._images_skipped += 1

        return offer_items

    # ═══════════════════════════════════════════════════════════════════════
    # Shared Playwright helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _wait_and_scroll(self, page) -> None:
        """Wait for any banner selector to become visible, then scroll to trigger lazy loads."""
        from playwright.sync_api import TimeoutError as PWTimeout

        all_selectors = (
            self.cfg.get("screenshot_selectors", [])
            + self.cfg.get("text_selectors", [])
            + self.cfg.get("banner_selectors", [])
        )

        valid_selectors = [s for s in all_selectors if s.strip()]
        if valid_selectors:
            combined = ", ".join(valid_selectors)
            try:
                page.wait_for_selector(combined, state="visible", timeout=15_000)
                logger.info("One of the configured selectors became visible")
            except PWTimeout:
                logger.warning("None of the configured selectors became visible within 15s")
                page.wait_for_timeout(5_000)
        else:
            page.wait_for_timeout(5_000)

        for i in range(self.scroll_depth):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(2_000)

        # Scroll back to top to ensure screenshot visibility
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(1_000)

    def _collect_image_urls(self) -> list[str]:
        """Playwright: collect filtered <img> src URLs from the rendered DOM."""
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        from urllib.parse import urlparse

        urls: list[str] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_context(
                user_agent=_UA, viewport={"width": 1920, "height": 1080}
            ).new_page()
            try:
                page.goto(self.source_url, timeout=60_000, wait_until="domcontentloaded")
                self._wait_and_scroll(page)

                imgs = page.query_selector_all("img")
                logger.info("Total img tags: %d", len(imgs))

                parsed_base = urlparse(self.source_url)

                for img in imgs:
                    src = img.get_attribute("src") or img.get_attribute("data-src") or ""
                    if not src or src.startswith("data:"):
                        continue
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        src = f"{parsed_base.scheme}://{parsed_base.netloc}{src}"

                    if any(p in src.lower() for p in self.exclude_patterns):
                        continue

                    try:
                        w = img.evaluate("el => el.naturalWidth")
                        h = img.evaluate("el => el.naturalHeight")
                        if w and h:
                            if w < self.min_width or h < self.min_height:
                                continue
                            if (w / max(h, 1)) < self.min_aspect:
                                continue
                    except Exception:
                        pass

                    urls.append(src)

            except PWTimeout:
                logger.error("Playwright timed out on %s", self.source_url)
            except Exception as e:
                logger.error("collect_image_urls error: %s", e)
            finally:
                browser.close()

        seen: set[str] = set()
        return [u for u in urls if not (u in seen or seen.add(u))]  # type: ignore

    # ═══════════════════════════════════════════════════════════════════════
    # Gemini Vision call (shared by image + screenshot strategies)
    # ═══════════════════════════════════════════════════════════════════════

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=70),
        retry=retry_if_exception_message(match=".*429.*|.*quota.*|.*exhausted.*"),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call_gemini(self, img_bytes: bytes, mime: str) -> str:
        global _last_gemini_time
        
        with _gemini_lock:
            now = time.time()
            elapsed = now - _last_gemini_time
            if elapsed < GEMINI_MIN_DELAY:
                sleep_time = GEMINI_MIN_DELAY - elapsed
                logger.info(f"Rate limiting: sleeping {sleep_time:.2f}s before calling API...")
                time.sleep(sleep_time)
            
            if self.use_litellm:
                import base64
                base64_image = base64.b64encode(img_bytes).decode("utf-8")
                
                kwargs = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": VISION_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime};base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    "temperature": 0.0,
                }
                api_key = os.getenv("LITELLM_API_KEY")
                api_base = os.getenv("LITELLM_API_BASE")
                if api_key:
                    kwargs["api_key"] = api_key
                if api_base:
                    kwargs["api_base"] = api_base
                
                response = self._client.completion(**kwargs)
                reply = response.choices[0].message.content
            else:
                image_part = genai_types.Part.from_bytes(data=img_bytes, mime_type=mime)
                response = self._client.models.generate_content(
                    model=self.model, contents=[VISION_PROMPT, image_part]
                )
                reply = response.text
                
            _last_gemini_time = time.time()
            
        self._gemini_api_calls += 1
        return reply

    def _vision_extract(self, img_bytes: bytes, mime: str, label: str) -> list[dict]:
        """Resize image, call Gemini, parse JSON. Returns list of offer dicts."""
        try:
            img = Image.open(BytesIO(img_bytes))
            if img.width > 1600:
                ratio = 1600 / img.width
                img = img.resize((1600, int(img.height * ratio)), Image.LANCZOS)
            buf = BytesIO()
            fmt = "PNG" if mime == "image/png" else "JPEG"
            img.save(buf, format=fmt)
            raw = self._call_gemini(buf.getvalue(), f"image/{fmt.lower()}")
        except Exception as e:
            logger.error("Gemini call failed for %s: %s", label, e)
            return []

        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        try:
            offers = json.loads(raw)
            return offers if isinstance(offers, list) else []
        except json.JSONDecodeError:
            logger.warning("Malformed JSON from Gemini for %s — raw: %s", label, raw[:200])
            if raw and raw != "[]":
                return [{"promo_text": raw[:400], "category": None,
                         "discount_min": None, "discount_max": None, "confidence": "low"}]
            return []

    # ═══════════════════════════════════════════════════════════════════════
    # Image download (image strategy only)
    # ═══════════════════════════════════════════════════════════════════════

    def _download_image(self, url: str) -> tuple[bytes | None, str]:
        """Download image bytes. Returns (bytes, mime) or (None, '')."""
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                r = client.get(url, headers={"User-Agent": _UA, "Referer": self.source_url})
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if "image" not in ct:
                logger.warning("Non-image content-type '%s' for %s", ct, url)
                return None, ""
            if "svg" in ct:
                logger.debug("Skipping SVG: %s", url)
                return None, ""
            return r.content, ct.split(";")[0].strip()
        except Exception as e:
            logger.warning("Download failed %s: %s", url, e)
            return None, ""

    # ═══════════════════════════════════════════════════════════════════════
    # Item builders
    # ═══════════════════════════════════════════════════════════════════════

    def _make_text_offer(self, text: str) -> dict:
        """Build an offer dict from scraped text. discount_* parsed by regex."""
        numbers = re.findall(r"(\d+)\s*%", text)
        nums    = [int(n) for n in numbers if 1 <= int(n) <= 99]
        return {
            "source":       "text_scraper",
            "brand":        self.brand,
            "source_url":   self.source_url,
            "title":        text[:200],
            "raw_text":     text,
            "category":     None,
            "discount_min": min(nums) if len(nums) >= 2 else (nums[0] if nums else None),
            "discount_max": max(nums) if len(nums) >= 2 else None,
            "confidence":   "high",
            "scraped_at":   datetime.utcnow().isoformat(),
        }

    def _build_offer_items(self, offers: list[dict], source_url: str) -> list[dict]:
        """Convert Gemini JSON offers into offer dicts."""
        items = []
        for offer in offers:
            text = (offer.get("promo_text") or "").strip()
            if not text:
                continue

            # Reject low-signal labels vision sometimes returns for generic
            # category/nav tiles (e.g. bare "SALE") that carry no actual
            # offer detail (%, $, or a concrete benefit like free shipping)
            has_number = re.search(r"\d", text)
            has_benefit = re.search(r"free\s+(delivery|shipping|gift)|buy\s+\d|\bBOGO\b", text, re.I)
            if not has_number and not has_benefit:
                continue

            def _f(v):
                try: return float(v) if v is not None else None
                except (TypeError, ValueError): return None

            items.append({
                "source":       "image_promo",
                "brand":        self.brand,
                "source_url":   source_url,
                "title":        text,
                "raw_text":     text,
                "category":     offer.get("category"),
                "discount_min": _f(offer.get("discount_min")),
                "discount_max": _f(offer.get("discount_max")),
                "confidence":   offer.get("confidence", "medium"),
                "scraped_at":   datetime.utcnow().isoformat(),
            })
        return items
