import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # adds /dashboard
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) # adds /Scrapy (root)

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
import langchain

# Optional: Enable terminal logging of exactly what langchain is doing
langchain.verbose = True

from llm.factory import get_langchain_llm
from utils.styles import apply_css, BRAND_COLORS

st.set_page_config(
    page_title="AI Analyst | Market Intelligence",
    page_icon="💬",
    layout="wide"
)
apply_css()

# ── Page Header ───────────────────────────────────────────────────────
st.markdown("<h1 style='color:#fff; font-weight:800;'>💬 AI Market Analyst</h1>", unsafe_allow_html=True)
st.markdown("""
<p style='color:#888; max-width: 700px;'>
Ask any business question in plain English. The AI will generate the right SQL query,
run it against our live data, and give you a clear, actionable answer.
</p>
""", unsafe_allow_html=True)
st.markdown("---")

# ── Suggested questions ───────────────────────────────────────────────
st.markdown("<div class='section-header'>💡 Try asking...</div>", unsafe_allow_html=True)
suggestions = [
    "What discounts are going on for products below ₹1000? What are we doing vs competitors?",
    "Which category has the biggest discount gap between our store and Vero Moda?",
    "How many Forever New products are on sale with more than 50% discount?",
    "What is the average sale price of Tops across all brands?",
    "Which brand has the most products in the Dresses & Jumpsuits category?",
    "Compare our average MRP vs Forever New's average MRP across all categories.",
]
cols = st.columns(3)
for i, q in enumerate(suggestions):
    with cols[i % 3]:
        if st.button(q, key=f"sug_{i}", use_container_width=False):
            st.session_state["prefill_question"] = q

st.markdown("<br>", unsafe_allow_html=True)

# ── Agent setup (cached) ──────────────────────────────────────────────
@st.cache_resource
def load_agent():
    db_url = os.getenv("DATABASE_URL")
    groq_key = os.getenv("GROQ_API_KEY")

    if not groq_key:
        return None, "❌ GROQ_API_KEY not found in .env"

    # Connect LangChain to our PostgreSQL Silver Layer tables
    db = SQLDatabase.from_uri(
        db_url,
        include_tables=["base_store_products", "product_snapshots", "competitors", "promotions"],
        sample_rows_in_table_info=3,
    )

    # ── LLM via factory ────────
    # Reads LLM_PROVIDER (e.g. 'litellm' or 'groq') and builds the right LangChain wrapper
    llm = get_langchain_llm()

    # System prompt with full schema context
    prefix = """You are an expert market intelligence analyst for a fashion retail company.
You have access to a PostgreSQL database with the following tables:

1. **base_store_products** — Our own store's product catalog.
   - product_id, product_name, brand, gender, category_label, master_category, original_price (MRP), sale_price, discount_percentage, last_synced_at
   - Contains 11,247 products from 35 brands (H&M, Mango, Nike, Zudio, etc.)
   - average discount is ~12-13% (our typical promotional depth)

2. **product_snapshots** — Scraped competitor product data.
   - product_name, product_url, sku, category_label, master_category, original_price, sale_price, discount_percentage, is_on_sale, first_seen_at, last_seen_at, competitor_id
   - Always JOIN with the **competitors** table on competitor_id to get the brand name

3. **competitors** — Maps competitor_id to brand name.
   - id, name (values: 'Forever New', 'Vero Moda')

4. **promotions** — Scraped coupon/promo offers from GrabOn and CouponDunia.
   - offer_title, category, discount_min, discount_max, flat_value, min_purchase, coupon_code, user_type, valid_until, source_name, scraped_at, competitor_id
   - JOIN with competitors on competitor_id for brand name

**master_category values (shared taxonomy across all tables):**
Tops, Bottoms, Dresses & Jumpsuits, Outerwear, Activewear, Intimates & Sleepwear, Co-Ords, Ethnic Wear, Footwear, Bags & Wallets, Jewellery, Accessories, Beauty & Personal Care, Kids, Collections & Edits, General Apparel

**Important rules:**
- When comparing "our store vs competitors", query base_store_products for "Our Store" and product_snapshots (joined with competitors) for "Forever New" / "Vero Moda"
- For price filters like "below ₹1000", filter on original_price
- Use master_category for category comparisons (not category_label)
- Always provide business-actionable insights, not just raw numbers
- Format numbers nicely: use ₹ for prices, % for discounts, commas for counts

Answer in a clear, structured way with key findings highlighted."""

    agent = create_sql_agent(
        llm=llm,
        db=db,
        agent_type="openai-tools",
        verbose=True,  # Changed to True so terminal shows logs
        prefix=prefix,
        max_iterations=10,
        handle_parsing_errors=True,
    )
    return agent, None

# ── Chat state ─────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Render chat history ────────────────────────────────────────────────
chat_container = st.container()
with chat_container:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"],
                             avatar="🧑" if msg["role"] == "user" else "🤖"):
            st.markdown(msg["content"])

# ── Input box ─────────────────────────────────────────────────────────
prefill = st.session_state.pop("prefill_question", "")
question = st.chat_input(
    "Ask anything about your data...",
    key="chat_input",
) or prefill

if question:
    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(question)

    # Load agent
    with st.chat_message("assistant", avatar="🤖"):
        agent, error = load_agent()
        if error:
            st.error(error)
            st.session_state.messages.append({"role": "assistant", "content": error})
        else:
            # We remove the hardcoded st.spinner and instead use StreamlitCallbackHandler
            # which will show real-time UI expanders of what the agent is thinking/doing
            try:
                st_callback = StreamlitCallbackHandler(st.container(), expand_new_thoughts=True)
                result = agent.invoke(
                    {"input": question},
                    config={"callbacks": [st_callback]}
                )
                answer = result.get("output", str(result))
            except Exception as e:
                    error_str = str(e)
                    # ── 429 rate-limit: rebuild agent with fallback LLM ──────
                    if "429" in error_str or "rate_limit_exceeded" in error_str or "Rate limit" in error_str:
                        st.toast("⚡ Rate limit hit — switching to fallback model...", icon="⚠️")
                        try:
                            fallback_name = os.getenv("LLM_FALLBACK", "").strip()
                            if not fallback_name:
                                raise ValueError("No LLM_FALLBACK configured in .env")

                            # Build a new LLM wrapper for the fallback provider
                            fb_llm = get_langchain_llm(provider=fallback_name)
                            
                            db_url = os.getenv("DATABASE_URL")
                            fb_db  = SQLDatabase.from_uri(
                                db_url,
                                include_tables=["base_store_products", "product_snapshots", "competitors", "promotions"],
                                sample_rows_in_table_info=2,
                            )
                            fb_agent = create_sql_agent(
                                llm=fb_llm, db=fb_db,
                                agent_type="openai-tools",
                                verbose=True, max_iterations=8,
                                handle_parsing_errors=True,
                            )
                            st_callback = StreamlitCallbackHandler(st.container(), expand_new_thoughts=True)
                            result = fb_agent.invoke(
                                {"input": question},
                                config={"callbacks": [st_callback]}
                            )
                            answer = result.get("output", str(result))
                            answer = f"*(answered by fallback provider: {fallback_name})*\n\n{answer}"
                        except Exception as fb_e:
                            answer = f"⚠️ Both primary and fallback models failed.\n\nPrimary error: `{error_str[:200]}`\n\nFallback error: `{str(fb_e)[:200]}`"
                    else:
                        answer = f"⚠️ I ran into an issue: {error_str[:300]}\n\nTry rephrasing your question."

            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

# ── Clear chat button ─────────────────────────────────────────────────
if st.session_state.messages:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ Clear conversation", key="clear"):
        st.session_state.messages = []
        st.rerun()
