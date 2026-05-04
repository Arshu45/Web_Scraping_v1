import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.styles import apply_css

st.set_page_config(
    page_title="Market Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_css()

st.sidebar.markdown("""
<div style="padding: 1.25rem 0 1.5rem 0;">
    <div style="font-size: 0.7rem; font-weight: 600; color: #A0A0B0; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.5rem;">Platform</div>
    <div style="font-size: 1rem; font-weight: 600; color: #1A1A2E; letter-spacing: -0.01em;">Market Intelligence</div>
</div>
<hr style="border-color: #E0E0EA; margin: 0 0 1rem 0;">
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style="font-size: 0.7rem; font-weight: 600; color: #A0A0B0; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.75rem;">Data Sources</div>
""", unsafe_allow_html=True)

for color, name, sub in [
    ("#5B50E8", "Our Store",   "11,247 products"),
    ("#D04A6A", "Forever New", "Scraped"),
    ("#1FAF8A", "Vero Moda",   "Scraped"),
]:
    st.sidebar.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
        <span style="color:{color};font-size:0.55rem;">●</span>
        <div>
            <div style="font-size:0.82rem;color:#505060;">{name}</div>
            <div style="font-size:0.7rem;color:#A0A0B0;">{sub}</div>
        </div>
    </div>""", unsafe_allow_html=True)

# ── Hero ────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding: 3rem 0 2rem 0;">
    <div style="font-size:0.7rem;font-weight:600;color:#A0A0B0;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:1rem;">Market Intelligence</div>
    <div style="font-size:2.8rem;font-weight:600;color:#1A1A2E;letter-spacing:-0.04em;line-height:1.15;margin-bottom:1rem;">
        Retail Competitive<br>Intelligence Dashboard
    </div>
    <div style="font-size:0.9rem;color:#909098;max-width:520px;line-height:1.7;">
        Real-time pricing and promotional intelligence across
        <span style="color:#5B50E8;">Our Store</span>,
        <span style="color:#D04A6A;">Forever New</span>, and
        <span style="color:#1FAF8A;">Vero Moda</span>.
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ── Navigation cards ────────────────────────────────────────────────
pages = [
    ("Overview",           "Executive KPIs, discount gaps, product volumes"),
    ("Competitor Battle",  "Category-by-category head-to-head gap analysis"),
    ("Category Analysis",  "Drill into discount depth and pricing per category"),
    ("Price Positioning",  "Budget vs mid-range vs premium — where do we sit?"),
    ("AI Analyst",         "Ask any business question in plain English"),
]

cols = st.columns(3)
for i, (name, desc) in enumerate(pages):
    with cols[i % 3]:
        st.markdown(f"""
        <div style="background:#FFFFFF;border:1px solid #E5E5EE;border-radius:10px;
                    padding:20px 22px;margin-bottom:12px;">
            <div style="font-size:0.85rem;font-weight:600;color:#1A1A2E;margin-bottom:6px;">{name}</div>
            <div style="font-size:0.78rem;color:#909098;line-height:1.5;">{desc}</div>
        </div>""", unsafe_allow_html=True)
