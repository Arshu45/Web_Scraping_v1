"""
GLiNER Enrichment Module

Reads promotions from the DB that have no structured fields yet
(offer_hash exists but discount_min, coupon_code, etc. are all NULL)
and extracts structured entities using GLiNER.

Run this as a standalone step after scraping, or call enrich_promotions()
from the Prefect flow.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.connection import get_session
from database.models import Promotion

# Lazy-load GLiNER to avoid slow startup when not needed
_model = None

def get_model():
    global _model
    if _model is None:
        from gliner import GLiNER
        print("Loading GLiNER model (first run may take a moment)...")
        _model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
    return _model


# The entity labels we ask GLiNER to find in each offer's raw_text
ENTITY_LABELS = [
    "discount percentage",
    "flat discount amount",
    "minimum purchase amount",
    "coupon code",
    "user type",
    "valid until date",
    "promo type",
]


def parse_entities(entities: list) -> dict:
    """Convert GLiNER entity list into a structured dict for DB storage."""
    result = {
        'discount_min': None,
        'discount_max': None,
        'flat_value': None,
        'min_purchase': None,
        'coupon_code': None,
        'user_type': 'all',
        'valid_until': None,
        'promo_type': None,
    }

    for ent in entities:
        label = ent['label']
        text  = ent['text'].strip()

        if label == "discount percentage":
            # Handle ranges like "40-70%" or single "20%"
            import re
            nums = re.findall(r'\d+\.?\d*', text)
            if len(nums) >= 2:
                result['discount_min'] = float(nums[0])
                result['discount_max'] = float(nums[1])
            elif len(nums) == 1:
                result['discount_max'] = float(nums[0])

        elif label == "flat discount amount":
            import re
            nums = re.findall(r'\d+\.?\d*', text)
            if nums:
                result['flat_value'] = float(nums[0])

        elif label == "minimum purchase amount":
            import re
            nums = re.findall(r'\d+\.?\d*', text)
            if nums:
                result['min_purchase'] = float(nums[0])

        elif label == "coupon code":
            result['coupon_code'] = text.upper()

        elif label == "user type":
            t = text.lower()
            if 'new' in t:
                result['user_type'] = 'new'
            elif 'exist' in t:
                result['user_type'] = 'existing'

        elif label == "promo type":
            result['promo_type'] = text

        elif label == "valid until date":
            result['valid_until'] = text  # Store as string; convert to Date in pipeline if needed

    return result


def enrich_promotions(batch_size: int = 50) -> dict:
    """
    Main enrichment function. Finds unenriched promotions in the DB
    and populates their structured fields using GLiNER.

    Returns a summary dict with counts.
    """
    model = get_model()
    session = get_session()
    enriched = 0
    errors = 0

    try:
        # Find promotions that haven't been enriched yet
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

        print(f"Found {len(unenriched)} unenriched promotions to process.")

        for promo in unenriched:
            try:
                entities = model.predict_entities(promo.raw_text, ENTITY_LABELS)
                structured = parse_entities(entities)

                coupon_code = structured['coupon_code']
                if coupon_code and isinstance(coupon_code, str):
                    coupon_code = coupon_code[:50]

                promo_type = structured['promo_type']
                if promo_type and isinstance(promo_type, str):
                    promo_type = promo_type[:30]

                promo.discount_min = structured['discount_min']
                promo.discount_max = structured['discount_max']
                promo.flat_value   = structured['flat_value']
                promo.min_purchase = structured['min_purchase']
                promo.coupon_code  = coupon_code
                promo.user_type    = structured['user_type']
                promo.promo_type   = promo_type

                session.commit()
                enriched += 1

            except Exception as e:
                session.rollback()
                print(f"Error enriching promotion {promo.id}: {e}")
                errors += 1

    finally:
        session.close()

    summary = {'enriched': enriched, 'errors': errors}
    print(f"Enrichment complete: {enriched} enriched, {errors} errors.")
    return summary


if __name__ == "__main__":
    enrich_promotions(batch_size=100)
