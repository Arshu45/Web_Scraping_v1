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


@st.cache_resource(ttl=60)
def get_promotions() -> pd.DataFrame:
    """Fetch all promotions joined with competitor name and assigned team IDs."""
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
                p.created_at,
                COALESCE(STRING_AGG(pta.team_id, ','), '') AS team_ids_str
            FROM promotions p
            LEFT JOIN promotion_team_assignments pta ON p.id = pta.promotion_id
            GROUP BY p.id
            ORDER BY p.scraped_at DESC
        """
        df = pd.read_sql(text(query), session.bind)
        if not df.empty:
            df["scraped_at"] = pd.to_datetime(df["scraped_at"])
            df["scraped_date"] = df["scraped_at"].dt.date
            df["team_ids_str"] = df["team_ids_str"].fillna("")
        else:
            df["scraped_date"] = pd.Series(dtype="object")
            df["team_ids_str"] = pd.Series(dtype="str")
        return df
    finally:
        session.close()
