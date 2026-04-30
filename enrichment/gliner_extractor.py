"""
GLiNER Enrichment Module

Reads promotions from the DB that have no structured fields yet
and extracts structured entities using GLiNER.

Category classification is done via keyword matching against the
PROMOTION_CATEGORIES list defined here. To add or remove categories,
just edit that list — no schema change needed.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.connection import get_session
from database.models import Promotion

# ─────────────────────────────────────────────
# CONFIGURABLE CATEGORIES
# Edit this list to add / remove categories.
# The keyword list is used to classify promotions by matching
# against the product category entity extracted by GLiNER.
# ─────────────────────────────────────────────
PROMOTION_CATEGORIES = [
    "Tops",
    "Bottoms",
    "Dresses & Jumpsuits",
    "Outerwear",
    "Activewear",
    "Intimates & Sleepwear",
    "Co-Ords",
    "Ethnic Wear",
    "Footwear",
    "Bags & Wallets",
    "Jewellery",
    "Accessories",
    "Beauty & Personal Care",
    "Kids",
    "Home & Decor",
    "Electronics",
    "Collections & Edits",
    "General Apparel",
]

# Keyword → Category mapping for smart matching
CATEGORY_KEYWORDS = {
    "Tops":                  ["shirt", "top", "topwear", "tshirt", "t-shirt", "tee", "blouse", "cami", "tank", "knit", "tunic"],
    "Bottoms":               ["jean", "pant", "trouser", "short", "skirt", "legging", "jegging", "bottom", "bottomwear", "bottom wear", "palazzo", "chino"],
    "Dresses & Jumpsuits":   ["dress", "dreses", "jumpsuit", "playsuit", "romper", "gown", "pinafore"],
    "Outerwear":             ["jacket", "coat", "blazer", "sweater", "cardigan", "outerwear", "shacket", "hoodie", "sweatshirt", "waistcoat"],
    "Activewear":            ["activewear", "athleisure", "sports", "gym", "yoga", "cycling", "sportswear", "trekking", "football"],
    "Intimates & Sleepwear": ["intimate", "lingerie", "bra", "brief", "underwear", "sleepwear", "night", "pyjama", "lounge", "robe", "wrap"],
    "Co-Ords":               ["co ord", "co-ord", "set", "suit"],
    "Ethnic Wear":           ["ethnic", "saree", "lehenga", "kurta", "kurti", "dupatta", "sherwani", "dhoti", "lungi", "salwar"],
    "Footwear":              ["footwear", "shoe", "sandal", "slipper", "sneaker", "boot", "heel", "loafer", "flip flop", "moccasin", "mojri", "kolhapuri", "flat"],
    "Bags & Wallets":        ["bag", "wallet", "purse", "handbag", "backpack", "clutch", "tote"],
    "Jewellery":             ["jewellery", "jewelry", "ring", "necklace", "earring", "bracelet", "pendant", "gold", "silver", "diamond", "bangle", "mangalsutra"],
    "Accessories":           ["accessory", "accessories", "belt", "sunglasses", "sunglass", "watch", "cap", "hat", "scarf", "scarves", "cape", "hair", "glove"],
    "Beauty & Personal Care":["beauty", "makeup", "lipstick", "mascara", "foundation", "skincare", "haircare", "cosmetic", "perfume", "grooming", "personal care", "serum", "moisturiser", "moisturizer", "kajal", "eyeliner", "shampoo", "conditioner", "fragrance"],
    "Kids":                  ["kids", "children", "baby", "toddler", "infant", "toy", "kidswear", "girl", "boy"],
    "Home & Decor":          ["home decor", "furniture", "kitchen", "bedding", "curtain", "cushion", "lamp", "bedsheet", "bed sheet", "pillow", "mattress", "sofa", "dining"],
    "Electronics":           ["electronics", "mobile", "phone", "laptop", "tablet", "earphone", "headphone", "gadget", "camera", "smartwatch", "speaker"],
    "Collections & Edits":   ["collection", "new arrival", "edit", "trend", "marquee", "devil", "signature", "essentials", "petite", "curve", "monochrome", "festive"],
    "General Apparel":       ["apparel", "clothing", "fashion", "workwear", "menswear", "womenswear", "office wear", "upcycled"],
}


def classify_category(text: str) -> str | None:
    """
    Score-based category classification.

    Counts the number of keyword hits per category and returns:
    - The top category if it has a clear majority (score >= 2x the runner-up)
    - "Multi-Category" if multiple categories match roughly equally
    - None if no keywords match at all

    Works for both a GLiNER entity string and a full raw_text fallback.
    """
    if not text:
        return None

    text_lower = text.lower()
    scores: dict[str, int] = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        hit_count = sum(1 for kw in keywords if kw in text_lower)
        if hit_count > 0:
            # Apply priority weighting to resolve ties intelligently
            priority_bonus = 0
            if category == "Kids":
                priority_bonus = 5
            elif category == "Ethnic Wear":
                priority_bonus = 4
            elif category == "Footwear":
                priority_bonus = 4
            elif category == "Intimates & Sleepwear":
                priority_bonus = 3
            elif category == "Activewear":
                priority_bonus = 3
            elif category == "Dresses & Jumpsuits":
                priority_bonus = 2
            elif category == "Outerwear":
                priority_bonus = 2
            elif category == "General Apparel" or category == "Collections & Edits":
                priority_bonus = -2 # Lower priority, only wins if nothing else matches

            scores[category] = hit_count + priority_bonus

    if not scores:
        return None

    # Sort categories by score descending
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_category, top_score = ranked[0]

    if len(ranked) == 1:
        # Only one category matched — clear winner
        return top_category

    second_score = ranked[1][1]

    # Dominant if top score is strictly greater than second score (tie-breaker)
    if top_score > second_score:
        return top_category

    # Two categories matched with exact same score — ambiguous
    return "Multi-Category"


def classify_from_raw_text(raw_text: str) -> str | None:
    """Convenience wrapper — classify directly from raw promotion text."""
    return classify_category(raw_text)


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
    "product category",
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
        'category_entity': None,  # Raw GLiNER extraction before mapping
    }

    for ent in entities:
        label = ent['label']
        text  = ent['text'].strip()

        if label == "discount percentage":
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
            result['valid_until'] = text

        elif label == "product category":
            result['category_entity'] = text

    return result


def enrich_promotions(batch_size: int = 50) -> dict:
    """
    Main enrichment function. Finds unenriched promotions in the DB
    and populates their structured fields using GLiNER.
    Category is classified from the GLiNER entity or via keyword fallback.
    """
    model = get_model()
    session = get_session()
    enriched = 0
    errors = 0

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
                print(f"Found unenriched promotions. Starting batches of {batch_size}...")

            batch_errors = 0
            for promo in unenriched:
                seen_ids.add(promo.id)
                try:
                    entities = model.predict_entities(promo.raw_text, ENTITY_LABELS)
                    structured = parse_entities(entities)

                    coupon_code = structured['coupon_code']
                    if coupon_code and isinstance(coupon_code, str):
                        coupon_code = coupon_code[:50]

                    promo_type = structured['promo_type']
                    if promo_type and isinstance(promo_type, str):
                        promo_type = promo_type[:30]

                    # Classify category: GLiNER entity → keyword map, fallback to raw text scan
                    category = classify_category(structured['category_entity'])
                    if not category:
                        category = classify_from_raw_text(promo.raw_text)

                    promo.discount_min = structured['discount_min']
                    promo.discount_max = structured['discount_max']
                    promo.flat_value   = structured['flat_value']
                    promo.min_purchase = structured['min_purchase']
                    promo.coupon_code  = coupon_code
                    promo.user_type    = structured['user_type']
                    promo.promo_type   = promo_type
                    promo.category     = category

                    session.commit()
                    enriched += 1

                except Exception as e:
                    session.rollback()
                    print(f"Error enriching promotion {promo.id}: {e}")
                    errors += 1
                    batch_errors += 1

            # Prevent infinite loop if a batch fails completely
            if batch_errors == len(unenriched):
                print("Halting enrichment: entire batch failed.")
                break

    finally:
        session.close()

    summary = {'enriched': enriched, 'errors': errors}
    print(f"Enrichment complete: {enriched} enriched, {errors} errors.")
    return summary

def enrich_product_categories() -> dict:
    """
    Highly optimized AI category enrichment for product snapshots.
    Extracts only distinct, unmapped category_labels, runs GLiNER on them,
    and bulk-updates the database.
    """
    from database.models import ProductSnapshot
    model = get_model()
    session = get_session()
    enriched_labels = 0
    updated_products = 0

    try:
        # Find unique category labels that haven't been mapped
        query = session.query(ProductSnapshot.category_label).filter(
            ProductSnapshot.category_label.isnot(None),
            ProductSnapshot.master_category.is_(None)
        ).distinct()
        
        unmapped_labels = [row[0] for row in query.all()]
        
        if unmapped_labels:
            print(f"Found {len(unmapped_labels)} unique unmapped category labels. Running GLiNER inference...")
            
            for label in unmapped_labels:
                # Ask GLiNER what category this label belongs to
                entities = model.predict_entities(label, ["product category"])
                
                category_entity = entities[0]['text'] if entities else None
                
                # Use our smart matching to map GLiNER's prediction (or the raw label) to PROMOTION_CATEGORIES
                master_cat = classify_category(category_entity)
                if not master_cat:
                    master_cat = classify_from_raw_text(label)
                    
                # Fallback
                if not master_cat:
                    master_cat = "Other"
                    
                # Bulk update all products sharing this label
                update_count = session.query(ProductSnapshot).filter(
                    ProductSnapshot.category_label == label,
                    ProductSnapshot.master_category.is_(None)
                ).update({"master_category": master_cat}, synchronize_session=False)
                
                session.commit()
                enriched_labels += 1
                updated_products += update_count
                
    except Exception as e:
        session.rollback()
        print(f"Error enriching product categories: {e}")
    finally:
        session.close()

    summary = {'unique_labels_enriched': enriched_labels, 'total_products_updated': updated_products}
    print(f"Product category enrichment complete: {enriched_labels} unique labels mapped, {updated_products} products updated.")
    return summary


if __name__ == "__main__":
    enrich_promotions(batch_size=100)
    enrich_product_categories()
