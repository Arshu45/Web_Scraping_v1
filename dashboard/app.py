import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.styles import apply_css

st.set_page_config(
    page_title="Market Intelligence Hub",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_css()

st.sidebar.markdown("""
<div style="text-align:center; padding: 1rem 0 1.5rem 0;">
    <div style="font-size: 2.2rem;">📊</div>
    <div style="font-size: 1.1rem; font-weight: 700; color: #6C63FF; letter-spacing: 0.04em;">
        Market Intelligence
    </div>
    <div style="font-size: 0.75rem; color: #666; margin-top: 4px;">
        Gold Layer Dashboard
    </div>
    <hr style="border-color: rgba(255,255,255,0.08); margin-top: 1rem;">
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
**Navigate using the pages above** ↑

---
**Data Sources**
- 🏪 Our Store — 11,247 products  
- 🛍️ Forever New — scraped  
- 🛍️ Vero Moda — scraped  
- 🎯 Promotions — GrabOn / CouponDunia  

---
""")

# ── Landing content ──
st.markdown("""
<div style="text-align:center; padding: 3rem 0 1rem 0;">
    <div style="font-size: 3.5rem;">📊</div>
    <h1 style="font-size: 2.5rem; font-weight: 800; color: #fff; margin-bottom: 0.5rem;">
        Market Intelligence Hub
    </h1>
    <p style="color: #888; font-size: 1.1rem; max-width: 600px; margin: 0 auto;">
        Competitive pricing intelligence across <strong style="color:#6C63FF;">Our Store</strong>,
        <strong style="color:#FF6584;">Forever New</strong>, and
        <strong style="color:#43D9AD;">Vero Moda</strong>.
        Built on a live Gold Layer data pipeline.
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(108,99,255,0.15), rgba(108,99,255,0.05));
                border: 1px solid rgba(108,99,255,0.3); border-radius: 16px; padding: 24px; text-align: center;">
        <div style="font-size: 2.5rem;">🏠</div>
        <div style="font-weight: 700; color: #fff; font-size: 1.1rem; margin-top: 8px;">Overview</div>
        <div style="color: #888; font-size: 0.85rem; margin-top: 6px;">KPIs, overall discount gap, data freshness</div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(255,101,132,0.15), rgba(255,101,132,0.05));
                border: 1px solid rgba(255,101,132,0.3); border-radius: 16px; padding: 24px; text-align: center;">
        <div style="font-size: 2.5rem;">⚔️</div>
        <div style="font-weight: 700; color: #fff; font-size: 1.1rem; margin-top: 8px;">Competitor Battle</div>
        <div style="color: #888; font-size: 0.85rem; margin-top: 6px;">Category-by-category head-to-head analysis</div>
    </div>""", unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(67,217,173,0.15), rgba(67,217,173,0.05));
                border: 1px solid rgba(67,217,173,0.3); border-radius: 16px; padding: 24px; text-align: center;">
        <div style="font-size: 2.5rem;">🎯</div>
        <div style="font-weight: 700; color: #fff; font-size: 1.1rem; margin-top: 8px;">Promotions Intel</div>
        <div style="color: #888; font-size: 0.85rem; margin-top: 6px;">Live coupons, promo types, discount ranges</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
col4, col5 = st.columns(2)
with col4:
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(255,200,80,0.15), rgba(255,200,80,0.05));
                border: 1px solid rgba(255,200,80,0.3); border-radius: 16px; padding: 24px; text-align: center;">
        <div style="font-size: 2.5rem;">📊</div>
        <div style="font-weight: 700; color: #fff; font-size: 1.1rem; margin-top: 8px;">Category Analysis</div>
        <div style="color: #888; font-size: 0.85rem; margin-top: 6px;">Drill into any fashion category across all brands</div>
    </div>""", unsafe_allow_html=True)

with col5:
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(150,100,255,0.15), rgba(150,100,255,0.05));
                border: 1px solid rgba(150,100,255,0.3); border-radius: 16px; padding: 24px; text-align: center;">
        <div style="font-size: 2.5rem;">💰</div>
        <div style="font-weight: 700; color: #fff; font-size: 1.1rem; margin-top: 8px;">Price Positioning</div>
        <div style="color: #888; font-size: 0.85rem; margin-top: 6px;">Budget vs mid vs premium — where do we sit?</div>
    </div>""", unsafe_allow_html=True)
