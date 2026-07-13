"""
Gold Layer — Database Query Functions
Simplified to only fetch extracted promotions.
"""
import os
import sys
import streamlit as st
import pandas as pd
from sqlalchemy import text

# Make project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database.connection import get_session

@st.cache_data(ttl=60)
def get_promotions() -> pd.DataFrame:
    """Fetch all promotions joined with competitor name."""
    session = get_session()
    try:
        query = """
            SELECT 
                p.id,
                p.brand,
                p.offer_title,
                p.category,
                p.source_name,
                p.source_url,
                p.extraction_confidence,
                p.scraped_at,
                p.created_at
            FROM promotions p
            ORDER BY p.scraped_at DESC
        """
        df = pd.read_sql(text(query), session.bind)
        # Ensure scraped_at is datetime
        if not df.empty:
            df["scraped_at"] = pd.to_datetime(df["scraped_at"])
            df["scraped_date"] = df["scraped_at"].dt.date
        else:
            df["scraped_date"] = pd.Series(dtype="object")
        return df
    finally:
        session.close()
