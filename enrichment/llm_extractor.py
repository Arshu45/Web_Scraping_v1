"""
LLM Enrichment Module (Groq)

Uses Groq's fast inference API to extract structured fields from
raw promotional text. Produces the exact same output dict as
gliner_extractor.py so the two are interchangeable.

Requires:
    GROQ_API_KEY in .env
    GROQ_MODEL   in .env (optional, defaults to llama-3.1-8b-instant)
"""

import os
import json
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from groq import Groq

from database.connection import get_session
from database.models import Promotion
from enrichment.gliner_extractor import PROMOTION_CATEGORIES

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# System prompt — instructs the LLM to return strict JSON array
_SYSTEM_PROMPT_BASE = """You are a retail promotion data extraction assistant.
I will provide a list of promotions, each with an 'id' and 'text'.
Extract structured information for EACH promotion and return ONLY a valid JSON ARRAY of objects.
If a field is not found in the text, use null.

Return this EXACT JSON array structure with no extra text:
[
  {
    "id": <the exact id provided>,
    "discount_min": <float or null>,
    "discount_max": <float or null>,
    "flat_value": <float or null>,
    "min_purchase": <float or null>,
    "coupon_code": <string or null>,
    "user_type": <"new" | "existing" | "all">,
    "promo_type": <"Percentage Off" | "Flat Discount" | "Cashback" | "Free Shipping" | "BOGO" | null>,
    "valid_until": <"YYYY-MM-DD" or null>,
    "category": <one of the allowed categories or null>
  }
]

Allowed categories (use EXACTLY one of these strings or null):
"""

SYSTEM_PROMPT = _SYSTEM_PROMPT_BASE + "\n".join(f"- {c}" for c in PROMOTION_CATEGORIES) + """

Rules:
- discount_min and discount_max: extract percentage numbers (e.g. "40-70% off" → min=40, max=70)
- flat_value: extract flat currency amounts (e.g. "₹300 off" → 300.0)
- min_purchase: extract minimum order value (e.g. "on orders above ₹1499" → 1499.0)
- coupon_code: extract any uppercase promo/coupon code mentioned (e.g. "SAVE20")
- user_type: "new" if offer is for new users, "existing" if for existing users, "all" otherwise
- category: classify the promotion into one of the allowed categories based on the products mentioned
- Return ONLY raw JSON array — no markdown, no explanation, no code fences.
"""


def _call_groq_batch(promotions: list) -> list:
    """Call Groq API with a batch of promotions to reduce token overhead."""
    # We re-enable retries here but handle sleeping manually if needed
    client = Groq(api_key=GROQ_API_KEY, max_retries=2)
    
    # Format user message
    user_content = "Promotions to extract:\n"
    for p in promotions:
        user_content += f"ID {p.id}:\n{p.raw_text}\n---\n"

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
        temperature=0.0,   
        max_tokens=2000,
    )

    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model wraps in ```json ... ```
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    return json.loads(content)


def enrich_promotions(batch_size: int = 50) -> dict:
    """
    Main enrichment function.
    Finds unenriched promotions and populates structured fields using Groq LLM.
    We fetch in batches, but process them in sub-batches of 10 to avoid Groq TPM limits.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in .env")

    session = get_session()
    enriched = 0
    errors   = 0

    try:
        seen_ids = set()
        while True:
            query = session.query(Promotion).filter(
                Promotion.raw_text.isnot(None),
                Promotion.promo_type.is_(None),
                Promotion.discount_max.is_(None),
                Promotion.flat_value.is_(None),
            )
            
            if seen_ids:
                query = query.filter(~Promotion.id.in_(seen_ids))
                
            unenriched = query.limit(batch_size).all()

            if not unenriched:
                break
            
            if enriched == 0 and errors == 0:
                print(f"[Groq] Found unenriched promotions. Extracting...")

            # Sub-batching: Process 15 items per LLM call to stay well under TPM limits
            sub_batch_size = 15
            for i in range(0, len(unenriched), sub_batch_size):
                sub_batch = unenriched[i:i + sub_batch_size]
                
                for p in sub_batch:
                    seen_ids.add(p.id)
                
                print(f"  [Groq] Processing batch of {len(sub_batch)} items... ", end="")
                sys.stdout.flush()
                
                try:
                    results = _call_groq_batch(sub_batch)
                    
                    # Map results back to promo objects by ID
                    results_map = {item['id']: item for item in results if 'id' in item}
                    
                    for promo in sub_batch:
                        structured = results_map.get(promo.id)
                        if not structured:
                            continue # Model missed this ID
                            
                        coupon_code = structured.get('coupon_code')
                        if coupon_code and isinstance(coupon_code, str):
                            coupon_code = coupon_code[:50]

                        promo_type = structured.get('promo_type')
                        if promo_type and isinstance(promo_type, str):
                            promo_type = promo_type[:30]

                        promo.discount_min = structured.get('discount_min')
                        promo.discount_max = structured.get('discount_max')
                        promo.flat_value   = structured.get('flat_value')
                        promo.min_purchase = structured.get('min_purchase')
                        promo.coupon_code  = coupon_code
                        promo.user_type    = structured.get('user_type', 'all')
                        promo.promo_type   = promo_type
                        promo.category     = structured.get('category')

                        enriched += 1

                    session.commit()
                    print("✅")
                    
                    # Prevent aggressive rate limits
                    time.sleep(1)

                except Exception as e:
                    session.rollback()
                    print(f"❌ Error: {e}")
                    errors += len(sub_batch)
                    time.sleep(3) # longer sleep on error

    finally:
        session.close()

    summary = {'enriched': enriched, 'errors': errors}
    print(f"[Groq] Enrichment complete: {enriched} enriched, {errors} errors.")
    return summary


if __name__ == "__main__":
    enrich_promotions(batch_size=50)
