"""
Dashboard design system — minimal, clean, light theme.
"""

# ── Brand palette ───────────────────────────────────────────────────────
BRAND_COLORS = {
    "Our Store":   "#5B50E8",   # Indigo
    "Forever New": "#D04A6A",   # Rose
    "Vero Moda":   "#1FAF8A",   # Teal
}

BRAND_LIST = ["Our Store", "Forever New", "Vero Moda"]

# ── Shared chart constants ──────────────────────────────────────────────
GRID_COLOR = "#EBEBF2"

# ── Plotly light defaults ───────────────────────────────────────────────
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="'Inter', sans-serif", color="#707080", size=12),
    margin=dict(l=16, r=16, t=36, b=16),
)


def apply_css():
    import streamlit as st
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, sans-serif;
        -webkit-font-smoothing: antialiased;
    }

    /* ── Base ─────────────────────────────────────────────────────── */
    .stApp { background-color: #FAFAFA; }
    .block-container { padding-top: 3.5rem !important; padding-bottom: 3rem; max-width: 1280px; }

    /* ── Sidebar ─────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background-color: #F4F4F8;
        border-right: 1px solid #E0E0EA;
    }
    section[data-testid="stSidebar"] * { color: #505060 !important; }

    /* ── Dividers ────────────────────────────────────────────────── */
    hr { border-color: #E5E5EE !important; margin: 1.5rem 0 !important; }

    /* ── Page title ──────────────────────────────────────────────── */
    .page-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1A1A2E;
        letter-spacing: -0.02em;
        margin-bottom: 0.15rem;
    }
    .page-subtitle {
        font-size: 0.85rem;
        color: #909098;
        margin-bottom: 0;
    }

    /* ── Section label ───────────────────────────────────────────── */
    .section-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #A0A0B0;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin: 2rem 0 1rem 0;
    }

    /* ── KPI cards ───────────────────────────────────────────────── */
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E5E5EE;
        border-radius: 10px;
        padding: 18px 20px;
    }
    .kpi-label {
        font-size: 0.72rem;
        font-weight: 500;
        color: #A0A0B0;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 8px;
    }
    .kpi-value {
        font-size: 1.9rem;
        font-weight: 600;
        color: #1A1A2E;
        letter-spacing: -0.03em;
        line-height: 1;
    }
    .kpi-sub {
        font-size: 0.75rem;
        color: #C0C0CC;
        margin-top: 6px;
    }

    /* ── Gap badges ─────────────────────────────────────────────── */
    .badge-red    { color: #C0354A; background: rgba(208,74,106,0.08); border: 1px solid rgba(208,74,106,0.25); border-radius: 5px; padding: 2px 8px; font-size: 0.78rem; font-weight: 500; }
    .badge-yellow { color: #9A7020; background: rgba(180,130,40,0.08);  border: 1px solid rgba(180,130,40,0.25);  border-radius: 5px; padding: 2px 8px; font-size: 0.78rem; font-weight: 500; }
    .badge-green  { color: #1A8A68; background: rgba(31,175,138,0.08);  border: 1px solid rgba(31,175,138,0.25);  border-radius: 5px; padding: 2px 8px; font-size: 0.78rem; font-weight: 500; }

    /* ── Tables ──────────────────────────────────────────────────── */
    table { width: 100%; border-collapse: collapse; }
    thead tr { border-bottom: 1px solid #E5E5EE; }
    thead th { font-size: 0.72rem; font-weight: 600; color: #A0A0B0; text-transform: uppercase; letter-spacing: 0.08em; padding: 8px 12px; text-align: left; background: transparent; }
    tbody tr { border-bottom: 1px solid #F2F2F6; }
    tbody tr:hover { background: #F6F6FA; }
    tbody td { font-size: 0.85rem; color: #505060; padding: 9px 12px; }

    .weekly-matrix {
        width: 100%;
        table-layout: fixed;
        border: 1px solid #E0E0EA;
        border-radius: 8px;
        overflow: hidden;
        background: #FFFFFF;
        margin-bottom: 1.5rem;
    }
    .weekly-matrix th,
    .weekly-matrix td {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        word-break: normal;
        vertical-align: top;
        line-height: 1.45;
        border-bottom: 1px solid #E5E5EE;
        border-right: 1px solid #E5E5EE;
    }
    .weekly-matrix th {
        background: #F7F7FA;
        color: #707080;
        font-size: 0.78rem;
        text-transform: none;
        letter-spacing: 0;
    }
    .weekly-matrix td {
        min-height: 72px;
        padding: 12px 10px;
        color: #1A1A2E;
    }
    .weekly-matrix .brand-cell {
        width: 150px;
        font-weight: 600;
        white-space: normal;
    }
    .weekly-matrix .promo-cell {
        min-width: 140px;
    }

    /* ── Streamlit widget tweaks ──────────────────────────────────── */
    .stSelectbox > div > div, .stMultiSelect > div > div {
        background: #FFFFFF !important;
        border-color: #E5E5EE !important;
        color: #1A1A2E !important;
        border-radius: 8px !important;
    }

    .stMultiSelect [data-baseweb="tag"] {
        background-color: #EEF0F8 !important;
        border: 1px solid #D9DDEA !important;
        border-radius: 6px !important;
        color: #303247 !important;
        box-shadow: none !important;
    }
    .stMultiSelect [data-baseweb="tag"] span {
        color: #303247 !important;
        font-weight: 500 !important;
    }
    .stMultiSelect [data-baseweb="tag"] svg {
        fill: #6F7285 !important;
    }
    .stMultiSelect [data-baseweb="tag"]:hover {
        background-color: #E5E8F3 !important;
        border-color: #C9CEDF !important;
    }

    /* ── Chat ────────────────────────────────────────────────────── */
    .stChatMessage { background: #FFFFFF !important; border: 1px solid #E5E5EE !important; border-radius: 10px !important; margin-bottom: 0.5rem; }
    .stChatInputContainer { border-top: 1px solid #E5E5EE !important; background: #FAFAFA !important; }

    /* ── Hide branding ───────────────────────────────────────────── */
    #MainMenu, footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = ""):
    import streamlit as st
    st.markdown(f"<div class='page-title'>{title}</div>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<div class='page-subtitle'>{subtitle}</div>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)


def section_label(text: str):
    import streamlit as st
    st.markdown(f"<div class='section-label'>{text}</div>", unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = "") -> str:
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {"<div class='kpi-sub'>"+sub+"</div>" if sub else ""}
    </div>"""


def gap_badge(gap: float) -> str:
    if gap > 30:
        return '<span class="badge-red">Critical Gap</span>'
    elif gap > 15:
        return '<span class="badge-yellow">Monitor</span>'
    else:
        return '<span class="badge-green">Competitive</span>'
