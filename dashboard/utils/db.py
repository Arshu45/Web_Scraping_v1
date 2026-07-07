"""
Gold Layer — Database Query Functions
All SQL is encapsulated here. Streamlit pages call these and get clean DataFrames.
"""
import os
import sys
import streamlit as st
import pandas as pd
from sqlalchemy import text

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database.connection import get_session

EXCLUDED = ("'Other'", "'Multi-Category'")
EXCL_SQL = ", ".join(EXCLUDED)

# ─────────────────────────────────────────────
# OVERVIEW
# ─────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_kpis():
    """Top-line KPI numbers for the overview page."""
    session = get_session()
    r = session.execute(text(f"""
        SELECT
            (SELECT COUNT(*) FROM base_store_products) as our_products,
            (SELECT ROUND(AVG(discount_percentage)::numeric, 2) FROM base_store_products) as our_avg_disc,
            (SELECT COUNT(*) FROM product_snapshots) as comp_products,
            (SELECT ROUND(AVG(discount_percentage)::numeric, 2)
             FROM product_snapshots ps
             JOIN competitors c ON ps.competitor_id = c.id
             WHERE c.name = 'Forever New' AND ps.discount_percentage IS NOT NULL) as fn_avg_disc,
            (SELECT ROUND(AVG(discount_percentage)::numeric, 2)
             FROM product_snapshots ps
             JOIN competitors c ON ps.competitor_id = c.id
             WHERE c.name = 'Vero Moda' AND ps.discount_percentage IS NOT NULL) as vm_avg_disc,
            (SELECT COUNT(*) FROM promotions) as total_promos
    """)).fetchone()
    session.close()
    return {
        "our_products": r[0], "our_avg_disc": float(r[1] or 0),
        "comp_products": r[2], "fn_avg_disc": float(r[3] or 0),
        "vm_avg_disc": float(r[4] or 0), "total_promos": r[5],
    }


@st.cache_data(ttl=300)
def get_brand_discount_overview():
    """Average discount per brand — Our Store + both competitors."""
    session = get_session()
    df = pd.read_sql(text(f"""
        SELECT 'Our Store' as brand,
               master_category,
               ROUND(AVG(discount_percentage)::numeric, 2) as avg_discount,
               COUNT(*) as products
        FROM base_store_products
        WHERE master_category NOT IN ({EXCL_SQL})
          AND discount_percentage IS NOT NULL
        GROUP BY master_category
        UNION ALL
        SELECT c.name as brand,
               ps.master_category,
               ROUND(AVG(ps.discount_percentage)::numeric, 2) as avg_discount,
               COUNT(*) as products
        FROM product_snapshots ps
        JOIN competitors c ON ps.competitor_id = c.id
        WHERE ps.master_category NOT IN ({EXCL_SQL})
          AND ps.discount_percentage IS NOT NULL
        GROUP BY c.name, ps.master_category
        ORDER BY master_category, brand
    """), session.bind)
    session.close()
    return df


# ─────────────────────────────────────────────
# GAP ANALYSIS
# ─────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_gap_analysis():
    """Category-level discount gap: Our Store vs combined competitors."""
    session = get_session()
    df = pd.read_sql(text(f"""
        WITH ours AS (
            SELECT master_category,
                   ROUND(AVG(discount_percentage)::numeric, 2) as our_discount,
                   ROUND(AVG(original_price)::numeric, 0) as our_avg_mrp,
                   COUNT(*) as our_products,
                   ROUND(100.0 * COUNT(CASE WHEN discount_percentage > 0 THEN 1 END) / COUNT(*)::numeric, 1) as our_pct_on_sale
            FROM base_store_products
            WHERE master_category NOT IN ({EXCL_SQL})
              AND discount_percentage IS NOT NULL
            GROUP BY master_category
        ),
        fn AS (
            SELECT ps.master_category,
                   ROUND(AVG(ps.discount_percentage)::numeric, 2) as fn_discount,
                   ROUND(AVG(ps.original_price)::numeric, 0) as fn_avg_mrp,
                   ROUND(100.0 * COUNT(CASE WHEN ps.is_on_sale THEN 1 END) / COUNT(*)::numeric, 1) as fn_pct_on_sale
            FROM product_snapshots ps
            JOIN competitors c ON ps.competitor_id = c.id
            WHERE c.name = 'Forever New'
              AND ps.master_category NOT IN ({EXCL_SQL})
              AND ps.discount_percentage IS NOT NULL
            GROUP BY ps.master_category
        ),
        vm AS (
            SELECT ps.master_category,
                   ROUND(AVG(ps.discount_percentage)::numeric, 2) as vm_discount,
                   ROUND(AVG(ps.original_price)::numeric, 0) as vm_avg_mrp,
                   ROUND(100.0 * COUNT(CASE WHEN ps.is_on_sale THEN 1 END) / COUNT(*)::numeric, 1) as vm_pct_on_sale
            FROM product_snapshots ps
            JOIN competitors c ON ps.competitor_id = c.id
            WHERE c.name = 'Vero Moda'
              AND ps.master_category NOT IN ({EXCL_SQL})
              AND ps.discount_percentage IS NOT NULL
            GROUP BY ps.master_category
        )
        SELECT
            o.master_category as category,
            o.our_discount,    o.our_avg_mrp,    o.our_products,    o.our_pct_on_sale,
            COALESCE(f.fn_discount, 0) as fn_discount,
            COALESCE(f.fn_avg_mrp, 0) as fn_avg_mrp,
            COALESCE(f.fn_pct_on_sale, 0) as fn_pct_on_sale,
            COALESCE(v.vm_discount, 0) as vm_discount,
            COALESCE(v.vm_avg_mrp, 0) as vm_avg_mrp,
            COALESCE(v.vm_pct_on_sale, 0) as vm_pct_on_sale,
            ROUND(GREATEST(
                COALESCE(f.fn_discount, 0),
                COALESCE(v.vm_discount, 0)
            ) - o.our_discount, 2) as max_gap
        FROM ours o
        LEFT JOIN fn f ON o.master_category = f.master_category
        LEFT JOIN vm v ON o.master_category = v.master_category
        ORDER BY max_gap DESC
    """), session.bind)
    session.close()
    return df


@st.cache_data(ttl=300)
def get_gap_analysis_by_price_band(min_price: float, max_price: float):
    """
    Category-level gap analysis filtered to a specific price band.
    Ensures we compare like-for-like (e.g. mid-range accessories vs mid-range accessories).
    max_price of 0 means no upper cap.
    """
    session = get_session()
    price_filter_our  = "AND original_price >= :min_p" + (" AND original_price < :max_p" if max_price else "")
    price_filter_comp = "AND ps.original_price >= :min_p" + (" AND ps.original_price < :max_p" if max_price else "")
    params = {"min_p": min_price}
    if max_price:
        params["max_p"] = max_price

    df = pd.read_sql(text(f"""
        WITH ours AS (
            SELECT master_category,
                   ROUND(AVG(discount_percentage)::numeric, 2) as our_discount,
                   ROUND(AVG(original_price)::numeric, 0) as our_avg_mrp,
                   COUNT(*) as our_products,
                   ROUND(100.0 * COUNT(CASE WHEN discount_percentage > 0 THEN 1 END) / COUNT(*)::numeric, 1) as our_pct_on_sale
            FROM base_store_products
            WHERE master_category NOT IN ({EXCL_SQL})
              AND discount_percentage IS NOT NULL
              {price_filter_our}
            GROUP BY master_category
        ),
        fn AS (
            SELECT ps.master_category,
                   ROUND(AVG(ps.discount_percentage)::numeric, 2) as fn_discount,
                   ROUND(AVG(ps.original_price)::numeric, 0) as fn_avg_mrp,
                   ROUND(100.0 * COUNT(CASE WHEN ps.is_on_sale THEN 1 END) / COUNT(*)::numeric, 1) as fn_pct_on_sale
            FROM product_snapshots ps
            JOIN competitors c ON ps.competitor_id = c.id
            WHERE c.name = 'Forever New'
              AND ps.master_category NOT IN ({EXCL_SQL})
              AND ps.discount_percentage IS NOT NULL
              {price_filter_comp}
            GROUP BY ps.master_category
        ),
        vm AS (
            SELECT ps.master_category,
                   ROUND(AVG(ps.discount_percentage)::numeric, 2) as vm_discount,
                   ROUND(AVG(ps.original_price)::numeric, 0) as vm_avg_mrp,
                   ROUND(100.0 * COUNT(CASE WHEN ps.is_on_sale THEN 1 END) / COUNT(*)::numeric, 1) as vm_pct_on_sale
            FROM product_snapshots ps
            JOIN competitors c ON ps.competitor_id = c.id
            WHERE c.name = 'Vero Moda'
              AND ps.master_category NOT IN ({EXCL_SQL})
              AND ps.discount_percentage IS NOT NULL
              {price_filter_comp}
            GROUP BY ps.master_category
        )
        SELECT
            o.master_category as category,
            o.our_discount,    o.our_avg_mrp,    o.our_products,    o.our_pct_on_sale,
            COALESCE(f.fn_discount, 0) as fn_discount,
            COALESCE(f.fn_avg_mrp, 0) as fn_avg_mrp,
            COALESCE(f.fn_pct_on_sale, 0) as fn_pct_on_sale,
            COALESCE(v.vm_discount, 0) as vm_discount,
            COALESCE(v.vm_avg_mrp, 0) as vm_avg_mrp,
            COALESCE(v.vm_pct_on_sale, 0) as vm_pct_on_sale,
            ROUND(GREATEST(
                COALESCE(f.fn_discount, 0),
                COALESCE(v.vm_discount, 0)
            ) - o.our_discount, 2) as max_gap
        FROM ours o
        LEFT JOIN fn f ON o.master_category = f.master_category
        LEFT JOIN vm v ON o.master_category = v.master_category
        ORDER BY max_gap DESC
    """), session.bind, params=params)
    session.close()
    return df


# ─────────────────────────────────────────────
# CATEGORY ANALYSIS
# ─────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_category_price_distribution(category: str):
    """MRP distribution for a specific category across all 3 brands."""
    session = get_session()
    df_our = pd.read_sql(text("""
        SELECT original_price as price, :brand as brand
        FROM base_store_products
        WHERE master_category = :cat AND original_price IS NOT NULL
    """), session.bind, params={"cat": category, "brand": "Our Store"})

    df_comp = pd.read_sql(text("""
        SELECT ps.original_price as price, c.name as brand
        FROM product_snapshots ps
        JOIN competitors c ON ps.competitor_id = c.id
        WHERE ps.master_category = :cat AND ps.original_price IS NOT NULL
    """), session.bind, params={"cat": category})
    session.close()
    return pd.concat([df_our, df_comp], ignore_index=True)


@st.cache_data(ttl=300)
def get_volume_heatmap():
    """Product count per brand per category for a heatmap."""
    session = get_session()
    df = pd.read_sql(text(f"""
        SELECT 'Our Store' as brand, master_category as category, COUNT(*) as products
        FROM base_store_products
        WHERE master_category NOT IN ({EXCL_SQL})
        GROUP BY master_category
        UNION ALL
        SELECT c.name as brand, ps.master_category as category, COUNT(*) as products
        FROM product_snapshots ps
        JOIN competitors c ON ps.competitor_id = c.id
        WHERE ps.master_category NOT IN ({EXCL_SQL})
        GROUP BY c.name, ps.master_category
    """), session.bind)
    session.close()
    return df.pivot(index="brand", columns="category", values="products").fillna(0)


# ─────────────────────────────────────────────
# PRICE POSITIONING
# ─────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_price_band_data():
    """Products bucketed into price bands per brand."""
    session = get_session()
    df = pd.read_sql(text(f"""
        SELECT 'Our Store' as brand, original_price as mrp
        FROM base_store_products
        WHERE original_price IS NOT NULL
          AND master_category NOT IN ({EXCL_SQL})
        UNION ALL
        SELECT c.name as brand, ps.original_price as mrp
        FROM product_snapshots ps
        JOIN competitors c ON ps.competitor_id = c.id
        WHERE ps.original_price IS NOT NULL
          AND ps.master_category NOT IN ({EXCL_SQL})
    """), session.bind)
    session.close()

    def band(mrp):
        if mrp < 1500: return "Budget (<₹1.5K)"
        elif mrp < 5000: return "Mid-Range (₹1.5K–5K)"
        elif mrp < 10000: return "Premium (₹5K–10K)"
        else: return "Luxury (>₹10K)"

    df["price_band"] = df["mrp"].apply(band)
    band_order = ["Budget (<₹1.5K)", "Mid-Range (₹1.5K–5K)", "Premium (₹5K–10K)", "Luxury (>₹10K)"]
    return df.groupby(["brand", "price_band"]).size().reset_index(name="count"), band_order


# ─────────────────────────────────────────────
# PROMOTIONS INTEL
# ─────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_promotions():
    """All scraped promotions with competitor name."""
    session = get_session()
    df = pd.read_sql(text("""
        SELECT
            c.name as brand,
            p.offer_title,
            p.category,
            p.discount_min,
            p.discount_max,
            p.flat_value,
            p.min_purchase,
            p.coupon_code,
            p.user_type,
            p.valid_until,
            p.source_name,
            p.scraped_at::date as scraped_date
        FROM promotions p
        JOIN competitors c ON p.competitor_id = c.id
        ORDER BY p.scraped_at DESC
    """), session.bind)
    session.close()
    return df
