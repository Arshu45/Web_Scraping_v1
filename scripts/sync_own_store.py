import sys
import os

# Ensure the root of the project is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import BaseStoreProduct
from database.mysql_connector import fetch_base_store_products
from enrichment.gliner_extractor import get_model, classify_category, classify_from_raw_text

def sync_base_store():
    print("Fetching internal products from MySQL...")
    mysql_products = fetch_base_store_products()
    total = len(mysql_products)
    print(f"Retrieved {total} products. Initializing GLiNER for categorization...")
    
    # Pre-compute unique categories to avoid running GLiNER 11,000 times
    unique_labels = {p['category_label'] for p in mysql_products if p.get('category_label')}
    label_to_master = {}
    
    if unique_labels:
        model = get_model()
        print(f"Found {len(unique_labels)} unique category labels. Running AI inference...")
        for label in unique_labels:
            entities = model.predict_entities(label, ["product category"])
            category_entity = entities[0]['text'] if entities else None
            
            master_cat = classify_category(category_entity)
            if not master_cat:
                master_cat = classify_from_raw_text(label)
            if not master_cat:
                master_cat = "Other"
                
            label_to_master[label] = master_cat
            
    print("Writing to PostgreSQL `base_store_products` table...")
    session = get_session()
    
    try:
        # For simplicity in syncing, we'll clear and re-insert or use merge.
        # Since this is a batch sync table, an efficient way is to delete all and bulk insert.
        session.query(BaseStoreProduct).delete()
        
        objects = []
        for p in mysql_products:
            mrp = float(p['original_price'] or 0)
            discount = round(float(p['discount_percentage'] or 0), 2)
            sale_price = round(mrp * (1 - (discount / 100)), 2)
            
            cat_label = p.get('category_label')
            
            objects.append(BaseStoreProduct(
                product_id=p['product_id'],
                product_name=p['product_name'],
                brand=p['brand'],
                gender=p['gender'],
                category_label=cat_label,
                master_category=label_to_master.get(cat_label, "Other"),
                original_price=mrp,
                sale_price=sale_price,
                discount_percentage=discount
            ))
            
            # Batch insert every 2000
            if len(objects) >= 2000:
                session.bulk_save_objects(objects)
                objects = []
                
        if objects:
            session.bulk_save_objects(objects)
            
        session.commit()
        print(f"✅ Successfully synced {total} products to PostgreSQL.")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error during sync: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    sync_base_store()
