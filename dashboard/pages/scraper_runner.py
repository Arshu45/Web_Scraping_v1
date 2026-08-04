"""
Scraper Runner Page
===================
Run individual brand targets or the full pipeline from the Streamlit UI.
Supports post-run retry of failed brands (same logic as master_pipeline.py).
"""

import glob
import json
import os
import queue
import sys
import threading
import time
import logging
import datetime

import streamlit as st

# ── Path setup ──────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from utils.styles import apply_css, page_header

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Scraper Runner · Market Intelligence",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_css()

# ── Extra CSS for this page ──────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Log console ──────────────────────────────────────────────── */
.log-console {
    background: #0F1117;
    border: 1px solid #2A2A3A;
    border-radius: 10px;
    padding: 16px 18px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 0.78rem;
    line-height: 1.7;
    color: #C8C8D8;
    max-height: 420px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
}
.log-info    { color: #7EC8E3; }
.log-warning { color: #F0C040; }
.log-error   { color: #F07070; }
.log-success { color: #5DE8A0; }

/* ── Status badges ────────────────────────────────────────────── */
.run-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 20px;
    margin-bottom: 1rem;
}
.run-badge-idle    { background: #F0F0F8; color: #8080A0; border: 1px solid #E0E0EE; }
.run-badge-running { background: rgba(91,80,232,0.10); color: #4840C0; border: 1px solid rgba(91,80,232,0.25); }
.run-badge-done    { background: rgba(31,175,138,0.10); color: #157A5A; border: 1px solid rgba(31,175,138,0.25); }
.run-badge-error   { background: rgba(208,74,106,0.10); color: #A0304A; border: 1px solid rgba(208,74,106,0.25); }

/* ── Result table ─────────────────────────────────────────────── */
.result-table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
.result-table th {
    font-size: 0.70rem; font-weight: 600; color: #A0A0B0;
    text-transform: uppercase; letter-spacing: 0.08em;
    padding: 8px 12px; border-bottom: 1px solid #E5E5EE; text-align: left;
}
.result-table td { font-size: 0.84rem; color: #505060; padding: 9px 12px; border-bottom: 1px solid #F2F2F6; }
.result-table tr:hover td { background: #F6F6FA; }
.r-ok   { color: #157A5A; font-weight: 600; }
.r-err  { color: #A0304A; font-weight: 600; }
.r-zero { color: #9A7020; font-weight: 600; }

/* ── Retry panel ──────────────────────────────────────────────── */
.retry-header {
    font-size: 0.85rem; font-weight: 600; color: #4840C0;
    margin: 1.5rem 0 0.5rem 0;
    display: flex; align-items: center; gap: 8px;
}

/* ── Config selector tweaks ───────────────────────────────────── */
.stMultiSelect [data-baseweb="tag"] { background-color: #EEF0F8 !important; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ──────────────────────────────────────────────────────────────────
CONFIG_DIR = os.path.join(ROOT, "config", "targets")

@st.cache_data(ttl=60)
def load_all_configs() -> dict[str, dict]:
    """Return {brand_name: config_dict} for all enabled JSON targets."""
    configs = {}
    for f in sorted(glob.glob(os.path.join(CONFIG_DIR, "*.json"))):
        try:
            with open(f, "r") as fh:
                cfg = json.load(fh)
            configs[cfg["brand"]] = cfg
        except Exception:
            pass
    return configs

def _status_badge(state: str) -> str:
    icons = {"idle": "○", "running": "◎", "done": "✓", "error": "✗"}
    classes = {"idle": "idle", "running": "running", "done": "done", "error": "error"}
    label = {"idle": "Idle", "running": "Running…", "done": "Completed", "error": "Error"}
    return (
        f'<div class="run-badge run-badge-{classes[state]}">'
        f'{icons[state]} {label[state]}</div>'
    )

def _result_row(r: dict) -> str:
    brand = r.get("brand", "—")
    if "error" in r:
        status = '<span class="r-err">✗ Error</span>'
        detail = str(r["error"])[:60]
    elif r.get("offers_extracted", 0) == 0:
        status = '<span class="r-zero">⚠ 0 offers</span>'
        detail = "No promos extracted"
    else:
        status = '<span class="r-ok">✓ OK</span>'
        detail = (
            f"extracted={r.get('offers_extracted',0)}  "
            f"stored={r.get('offers_stored',0)}  "
            f"cost=${r.get('estimated_cost_usd',0):.5f}"
        )
    return f"<tr><td>{brand}</td><td>{status}</td><td>{detail}</td></tr>"

def _render_results_table(results: list[dict], title: str = "Results"):
    rows = "".join(_result_row(r) for r in results)
    st.markdown(f"""
    <div class="section-label">{title}</div>
    <table class="result-table">
      <thead><tr><th>Brand</th><th>Status</th><th>Detail</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """, unsafe_allow_html=True)


# ── Queue-based log handler so scraper logs surface in the UI ────────────────
class QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record):
        self.q.put(self.format(record))


# ── Core runner (runs in a background thread) ────────────────────────────────
def _run_scraper(
    targets: list[dict],
    log_q: queue.Queue,
    result_store: dict,
    retry_errored: bool,
    max_retries: int,
    retry_delay_sec: int,
):
    """Runs scraping sequentially, posts log lines and results into shared state."""
    from scripts.run_hybrid_promo_scraper import scrape_single_target

    # Attach a queue handler to the root logger so all scraper logs flow through
    handler = QueueHandler(log_q)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    def run_batch(batch: list[dict]) -> list[dict]:
        results = []
        for t in batch:
            log_q.put(f"{'─'*55}")
            log_q.put(f"▶ Starting: {t['brand']}")
            try:
                r = scrape_single_target(t)
            except Exception as exc:
                r = {"brand": t["brand"], "error": str(exc)}
            results.append(r)
        return results

    # ── Main run ──
    log_q.put(f"🚀 Starting scrape for {len(targets)} brand(s)…")
    main_results = run_batch(targets)
    result_store["main"] = main_results

    # ── Retry pass ──
    if retry_errored:
        failed_brands = {r["brand"] for r in main_results if "error" in r}
        brand_map = {t["brand"]: t for t in targets}

        for attempt in range(1, max_retries + 1):
            if not failed_brands:
                log_q.put(f"✅ No failed brands — skipping retry {attempt}.")
                break

            log_q.put(
                f"\n⏳ Retry {attempt}/{max_retries} — waiting {retry_delay_sec}s "
                f"(~{retry_delay_sec//60} min) for: {', '.join(sorted(failed_brands))}"
            )
            time.sleep(retry_delay_sec)

            retry_targets = [brand_map[b] for b in sorted(failed_brands) if b in brand_map]
            log_q.put(f"🔁 Retrying {len(retry_targets)} brand(s) — attempt {attempt}/{max_retries}")
            retry_results = run_batch(retry_targets)

            result_store.setdefault("retries", []).append({
                "attempt": attempt,
                "results": retry_results,
            })

            failed_brands = {r["brand"] for r in retry_results if "error" in r}

        if failed_brands:
            log_q.put(f"\n⚠️  Still failing after {max_retries} retry attempt(s): {', '.join(sorted(failed_brands))}")

    root_logger.removeHandler(handler)
    log_q.put("__DONE__")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
page_header("Scraper Runner", "Trigger individual brand scrapes or a full pipeline run from the UI.")

all_configs = load_all_configs()
all_brands  = list(all_configs.keys())

# ── Sidebar — run options ────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="padding: 0.5rem 0 1rem 0;">
    <div style="font-size: 0.7rem; font-weight: 600; color: #A0A0B0; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.5rem;">Platform</div>
    <div style="font-size: 1rem; font-weight: 600; color: #1A1A2E;">Market Intelligence</div>
</div>
<hr style="border-color: #E0E0EA; margin: 0 0 1.5rem 0;">
""", unsafe_allow_html=True)

st.sidebar.markdown('<div class="section-label">Run Options</div>', unsafe_allow_html=True)

run_mode = st.sidebar.radio(
    "Mode",
    ["Selected brands", "Full pipeline (all enabled)"],
    index=0,
)

selected_brands: list[str] = []
if run_mode == "Selected brands":
    selected_brands = st.sidebar.multiselect(
        "Choose brands to scrape",
        options=all_brands,
        default=[],
        placeholder="Pick one or more…",
    )
else:
    selected_brands = all_brands  # all enabled configs

st.sidebar.markdown('<div class="section-label">Retry Settings</div>', unsafe_allow_html=True)

retry_errored   = st.sidebar.toggle("Auto-retry failed brands", value=True)
max_retries     = st.sidebar.slider("Max retry attempts", 1, 3, 2, disabled=not retry_errored)
retry_delay_min = st.sidebar.slider("Delay between retries (min)", 1, 15, 5, disabled=not retry_errored)
retry_delay_sec = retry_delay_min * 60

# ── Session state bootstrap ──────────────────────────────────────────────────
for key, default in [
    ("runner_state",   "idle"),     # idle | running | done | error
    ("log_lines",      []),
    ("result_store",   {}),
    ("log_q",          None),
    ("runner_thread",  None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Status badge + controls ──────────────────────────────────────────────────
col_badge, col_btn = st.columns([4, 1], vertical_alignment="center")

with col_badge:
    st.markdown(_status_badge(st.session_state.runner_state), unsafe_allow_html=True)

with col_btn:
    targets_to_run = [all_configs[b] for b in selected_brands if b in all_configs]
    can_run = bool(targets_to_run) and st.session_state.runner_state != "running"

    if st.button(
        "▶ Run Scraper",
        disabled=not can_run,
        type="primary",
        use_container_width=True,
        key="btn_run",
    ):
        # Reset state
        st.session_state.log_lines    = []
        st.session_state.result_store = {}
        st.session_state.runner_state = "running"
        log_q = queue.Queue()
        st.session_state.log_q = log_q

        t = threading.Thread(
            target=_run_scraper,
            args=(targets_to_run, log_q, st.session_state.result_store,
                  retry_errored, max_retries, retry_delay_sec),
            daemon=True,
        )
        t.start()
        st.session_state.runner_thread = t
        st.rerun()

# ── Drain log queue if a run is active ──────────────────────────────────────
if st.session_state.runner_state == "running" and st.session_state.log_q:
    log_q: queue.Queue = st.session_state.log_q
    done = False
    new_lines = []

    # Drain everything currently in the queue
    while True:
        try:
            line = log_q.get_nowait()
        except queue.Empty:
            break
        if line == "__DONE__":
            done = True
            break
        new_lines.append(line)

    st.session_state.log_lines.extend(new_lines)

    if done:
        st.session_state.runner_state = (
            "error"
            if any("error" in r for r in st.session_state.result_store.get("main", []))
            else "done"
        )

    # Auto-refresh while still running
    if not done:
        time.sleep(1.5)
        st.rerun()

# ── Log console ──────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Live Log</div>', unsafe_allow_html=True)

if st.session_state.log_lines:
    lines_html = ""
    for line in st.session_state.log_lines:
        if "[ERROR]" in line or "[CRITICAL]" in line:
            css = "log-error"
        elif "[WARNING]" in line:
            css = "log-warning"
        elif "✅" in line or "RECOVERED" in line or "✓" in line:
            css = "log-success"
        else:
            css = "log-info"
        import html as _html
        lines_html += f'<span class="{css}">{_html.escape(line)}</span>\n'

    st.markdown(f'<div class="log-console">{lines_html}</div>', unsafe_allow_html=True)
else:
    st.markdown(
        '<div class="log-console" style="color:#505070;">No log output yet. '
        'Select brands and press ▶ Run Scraper to begin.</div>',
        unsafe_allow_html=True,
    )

# ── Results ──────────────────────────────────────────────────────────────────
result_store: dict = st.session_state.result_store

if result_store.get("main"):
    st.markdown("<hr>", unsafe_allow_html=True)
    _render_results_table(result_store["main"], "Main Run — Results")

    # ── KPI strip ──
    main_results = result_store["main"]
    total        = len(main_results)
    succeeded    = sum(1 for r in main_results if "error" not in r and r.get("offers_extracted", 0) > 0)
    failed_count = sum(1 for r in main_results if "error" in r)
    total_offers = sum(r.get("offers_extracted", 0) for r in main_results)
    total_cost   = sum(r.get("estimated_cost_usd", 0.0) for r in main_results)

    st.markdown('<div class="section-label">Run Summary</div>', unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    def _kpi(col, label, value, sub=""):
        col.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {"<div class='kpi-sub'>"+sub+"</div>" if sub else ""}
        </div>""", unsafe_allow_html=True)

    _kpi(k1, "Brands Run",       total)
    _kpi(k2, "Succeeded",        succeeded,    f"{succeeded}/{total}")
    _kpi(k3, "Errored",          failed_count, "will be retried" if retry_errored and failed_count else "")
    _kpi(k4, "Total Offers",     total_offers, "extracted")
    _kpi(k5, "Est. Cost",        f"${total_cost:.4f}", "USD")

    # ── Retry attempt results ──
    for retry_pass in result_store.get("retries", []):
        attempt = retry_pass["attempt"]
        _render_results_table(
            retry_pass["results"],
            f"🔁 Retry Attempt {attempt}/{max_retries}",
        )

# ── Idle state hint ──────────────────────────────────────────────────────────
if st.session_state.runner_state == "idle":
    st.markdown("""
    <div style="margin-top: 2rem; padding: 2rem; background: #F8F8FC;
         border: 1px dashed #D8D8E8; border-radius: 12px; text-align: center;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">⚙️</div>
        <div style="font-size: 0.95rem; font-weight: 600; color: #505070; margin-bottom: 0.4rem;">
            No run in progress
        </div>
        <div style="font-size: 0.82rem; color: #A0A0B8;">
            Select brands from the sidebar and press <strong>▶ Run Scraper</strong> to begin.
        </div>
    </div>
    """, unsafe_allow_html=True)
