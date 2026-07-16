# Autonomous Scraping Agent

An autonomous agent system designed to dynamically explore competitor websites, analyze layouts, evaluate anti-bot protections, identify visual promotional areas, determine optimal CSS extraction strategies, and register scraping configurations.

The system is built on **LangGraph** to orchestrate step-by-step agent executions, using **Playwright** for browser automation, **LiteLLM** for Claude model access, and direct **Gemini** API fallbacks.

---

## Agentic Architecture

The autonomous pipeline is represented as a state graph coordinated by a LangGraph orchestrator:

```text
       [START]
          │
          ▼
   ┌─────────────┐
   │ Exploration │  ◄── visits site, scores anti-bot, analyzes layout & DOM
   └─────────────┘
          │
          ▼
   ┌─────────────┐
   │ Generation  │  ◄── generates CSS configuration for scraping target
   └─────────────┘
          │
          ▼
   ┌─────────────┐
   │ Validation  │  ◄── tests generated configuration & checks sandbox
   └─────────────┘
          │
      Conditional
      Routing (based on validation score & sandbox violations)
      ┌───┼───┐
      │   │   │
      │   │   ▼
      │   │ [END] (Score < 70 or Sandbox Violation -> Rejected)
      │   │
      │   ▼
      │ [END] (Score 70 - 89 -> Pending Human Review)
      │
      ▼
   ┌──────────────┐
   │ Registration │ ◄── registers verified config (Score >= 90)
   └──────────────┘
          │
          ▼
        [END]
```

### Agent Nodes & Responsibilities

1. **Exploration Agent** (`agent/exploration_agent.py`):
   - Opens target site headlessly with stealth flags, custom headers, and webdriver detection blocks.
   - Evaluates page height, triggers dynamic scroll actions to bypass lazy loading, and resets scroll.
   - Computes an **anti-bot risk score** based on DOM presence of security elements (CAPTCHA, Cloudflare, etc.) and response headers.
   - Cleans non-semantic HTML tags (e.g. `<script>`, `<style>`, `<head>`, `<svg>`) to generate a truncated DOM.
   - Uses multimodal models (LiteLLM Claude falling back to direct Gemini) to identify visual promotional areas from pre/post-scroll screenshots.
   - Evaluates cleaned DOM structure alongside the visual analysis to recommend the extraction strategy and suggest selectors.
2. **Generation Agent** (`agent/orchestrator.py` - stub):
   - Generates target configurations matching the exploration recommendations.
3. **Validation Agent** (`agent/orchestrator.py` - stub):
   - Evaluates scraping coverage, compares output schema, and verifies security sandboxing.
4. **Registration Agent** (`agent/orchestrator.py` - stub):
   - Stores and activates approved configurations for production scraping.

---

## Setup & Initialization

### 1. Requirements
- Python 3.10+
- Google Gemini API Key
- LiteLLM Gateway / Corporate API Access (optional; falls back to direct Gemini API)

### 2. Installation
Clone the repository, initialize your virtual environment, and install dependencies:

```bash
# Create and activate virtual environment
python -m venv env
source env/bin/activate

# Install required packages
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

### 3. Environment Configuration
Create a `.env` file in the project root:

```env
# LiteLLM Configuration (Primary)
LITELLM_API_KEY=your_litellm_api_key
LITELLM_API_BASE=https://your-litellm-gateway.example/v1
LLM_MODEL=openai/claude-haiku-4.5
VISION_LLM_MODEL=openai/claude-haiku-4.5

# Direct Gemini Fallback Configuration
GEMINI_API_KEY=your_gemini_api_key
```

---

## Executing the System

### Running Unit Tests (Routing & Graph Mocked Runs)
Execute the orchestrator unit tests to verify the routing flows based on validation scores and sandbox checks:
```bash
PYTHONPATH=. ../env/bin/python3 agent/test_orchestrator.py
```

### Running the Exploration Agent (Live Dynamic Analysis)
To test the site exploration agent directly on a live retail page:
Create or run a script calling `explore_site(url, brand)`. 

Example test invocation:
```bash
PYTHONPATH=. ../env/bin/python3 -c "
from agent.exploration_agent import explore_site
res = explore_site('https://www.oxfordshop.com.au/', 'Oxford Shop')
print('Strategy:', res.extraction_strategy)
print('Anti-bot risk:', res.anti_bot_risk)
"
```

The system will print token usage logs and USD costing breakdowns for both steps:
- **Visual Call**:
  `LiteLLM Vision SUCCESS: model=openai/claude-haiku-4.5 | prompt_tokens=3436 | completion_tokens=544 | total_tokens=3980 | cost=$0.006156`
- **DOM Reasoning Call**:
  `LiteLLM Reasoning SUCCESS: model=openai/claude-haiku-4.5 | prompt_tokens=19975 | completion_tokens=522 | total_tokens=20497 | cost=$0.022585`
