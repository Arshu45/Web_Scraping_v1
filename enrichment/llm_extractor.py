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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from groq import Groq

from database.connection import get_session
from database.models import Promotion

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# System prompt — instructs the LLM to return strict JSON
SYSTEM_PROMPT = """You are a retail promotion data extraction assistant.
Extract structured information from the given promotional offer text and return ONLY a valid JSON object.
If a field is not found in the text, use null.

Return this exact JSON structure with no extra text:
{
  "discount_min": <float or null>,
  "discount_max": <float or null>,
  "flat_value": <float or null>,
  "min_purchase": <float or null>,
  "coupon_code": <string or null>,
  "user_type": <"new" | "existing" | "all">,
  "promo_type": <"Percentage Off" | "Flat Discount" | "Cashback" | "Free Shipping" | "BOGO" | null>,
  "valid_until": <"YYYY-MM-DD" or null>
}

Rules:
- discount_min and discount_max: extract percentage numbers (e.g. "40-70% off" → min=40, max=70; "up to 90% off" → min=null, max=90)
- flat_value: extract flat currency amounts (e.g. "₹300 off" → 300.0)
- min_purchase: extract minimum order value (e.g. "on orders above ₹1499" → 1499.0)
- coupon_code: extract any uppercase promo/coupon code mentioned (e.g. "SAVE20")
- user_type: "new" if offer is for new users, "existing" if for existing users, "all" otherwise
- valid_until: extract expiry date if mentioned, in YYYY-MM-DD format
- Return ONLY raw JSON — no markdown, no explanation, no code fences
"""


def _call_groq(raw_text: str) -> dict:
    """Call Groq API and parse the JSON response."""
    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Extract from this promotion:\n\n{raw_text}"},
        ],
        temperature=0.0,   # Deterministic output for extraction tasks
        max_tokens=300,
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
    Main enrichment function — same interface as gliner_extractor.enrich_promotions().
    Finds unenriched promotions and populates structured fields using Groq LLM.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in .env")

    session = get_session()
    enriched = 0
    errors   = 0

    try:
        unenriched = (
            session.query(Promotion)
            .filter(
                Promotion.raw_text.isnot(None),
                Promotion.promo_type.is_(None),
                Promotion.discount_max.is_(None),
                Promotion.flat_value.is_(None),
            )
            .limit(batch_size)
            .all()
        )

        print(f"[Groq] Found {len(unenriched)} unenriched promotions.")

        for promo in unenriched:
            try:
                structured = _call_groq(promo.raw_text)

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

                session.commit()
                enriched += 1

            except Exception as e:
                session.rollback()
                print(f"[Groq] Error on promotion {promo.id}: {e}")
                errors += 1

    finally:
        session.close()

    summary = {'enriched': enriched, 'errors': errors}
    print(f"[Groq] Enrichment complete: {enriched} enriched, {errors} errors.")
    return summary


if __name__ == "__main__":
    enrich_promotions(batch_size=10)
