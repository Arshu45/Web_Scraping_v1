"""
Dashboard theme — color palette and chart config.
"""

# Brand colors — consistent across all pages
BRAND_COLORS = {
    "Our Store":   "#6C63FF",   # Vibrant purple
    "Forever New": "#FF6584",   # Rose pink
    "Vero Moda":   "#43D9AD",   # Teal green
}

BRAND_LIST = ["Our Store", "Forever New", "Vero Moda"]

# Plotly layout defaults for dark mode
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#E0E0E0"),
    margin=dict(l=20, r=20, t=40, b=20),
)

def apply_css():
    import streamlit as st
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Dark background */
    .stApp { background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%); }
    .block-container { padding-top: 1.5rem; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #16213e 0%, #0f3460 100%);
        border-right: 1px solid rgba(255,255,255,0.08);
    }
    section[data-testid="stSidebar"] * { color: #E0E0E0 !important; }

    /* KPI cards */
    .kpi-card {
        background: linear-gradient(135deg, rgba(108,99,255,0.15), rgba(67,217,173,0.1));
        border: 1px solid rgba(108,99,255,0.3);
        border-radius: 16px;
        padding: 20px 24px;
        text-align: center;
        backdrop-filter: blur(10px);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 32px rgba(108,99,255,0.25);
    }
    .kpi-label { font-size: 0.8rem; font-weight: 500; color: #888; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 6px; }
    .kpi-value { font-size: 2.2rem; font-weight: 700; color: #fff; line-height: 1.1; }
    .kpi-sub   { font-size: 0.8rem; color: #aaa; margin-top: 4px; }

    /* Gap signal badges */
    .badge-red    { background: rgba(255,99,99,0.2); color: #ff6363; border: 1px solid rgba(255,99,99,0.4); border-radius: 8px; padding: 2px 10px; font-weight: 600; font-size: 0.82rem; }
    .badge-yellow { background: rgba(255,200,80,0.2); color: #ffc850; border: 1px solid rgba(255,200,80,0.4); border-radius: 8px; padding: 2px 10px; font-weight: 600; font-size: 0.82rem; }
    .badge-green  { background: rgba(67,217,173,0.2); color: #43d9ad; border: 1px solid rgba(67,217,173,0.4); border-radius: 8px; padding: 2px 10px; font-weight: 600; font-size: 0.82rem; }

    /* Section headers */
    .section-header {
        font-size: 1.1rem; font-weight: 600; color: #c0c0d8;
        border-left: 3px solid #6C63FF; padding-left: 10px;
        margin: 1.5rem 0 0.8rem 0;
    }

    /* Tables */
    .stDataFrame { border-radius: 12px; overflow: hidden; }
    .stDataFrame thead th { background: #1a1a2e !important; color: #6C63FF !important; }

    /* Hide streamlit branding */
    #MainMenu, footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = "") -> str:
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {"<div class='kpi-sub'>"+sub+"</div>" if sub else ""}
    </div>"""


def gap_badge(gap: float) -> str:
    if gap > 30:
        return '<span class="badge-red">🔴 Critical Gap</span>'
    elif gap > 15:
        return '<span class="badge-yellow">🟡 Monitor</span>'
    else:
        return '<span class="badge-green">🟢 Competitive</span>'
