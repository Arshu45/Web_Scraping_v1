import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_mysql_connection():
    """Establish a connection to the MySQL fashion_retail database."""
    return pymysql.connect(
        host=os.getenv('MYSQL_HOST', '172.27.133.173'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER', 'readonly_user'),
        password=os.getenv('MYSQL_PASSWORD', 'cybage@123'),
        database=os.getenv('MYSQL_DB', 'fashion_retail'),
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor
    )

def fetch_base_store_products():
    """
    Fetches all products from the MySQL DB.
    Joins with the category table to get the category label.
    Left joins with an aggregation of the order_item table to compute the true historical average discount per product.
    """
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    p.product_id,
                    p.product_name,
                    p.brand,
                    p.gender,
                    p.mrp as original_price,
                    c.category_name as category_label,
                    IFNULL(d.avg_discount_pct, 0) as discount_percentage
                FROM product p
                JOIN category c ON p.primary_category_id = c.category_id
                LEFT JOIN (
                    SELECT product_id, AVG(discount_pct) as avg_discount_pct
                    FROM order_item
                    WHERE is_returned = 0 OR is_returned IS NULL
                    GROUP BY product_id
                ) d ON p.product_id = d.product_id
            """
            cur.execute(query)
            return cur.fetchall()
    finally:
        conn.close()
