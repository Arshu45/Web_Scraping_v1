# Scraper Agent — Task Breakdown for Claude Code Sessions

Each task below is scoped to run in its own Claude Code session. Every task ends with Claude Code producing a `HANDOFF.md` that the next session's opening prompt should include, so context carries forward without re-pasting the whole plan each time.

**How to start each session:** paste the task's prompt block, attach the actual current repo (or relevant files), and attach the previous task's `HANDOFF.md` (from Task 2 onward).

> **Updated [v3]:** Aligned to implementation plan v3 — corrected table names, LLM provider, file paths, extraction strategy values. Repair agent (old Task 8) deferred. Calibration script deferred from old Task 9.

---

## Task 0 — Repo Orientation (read-only, no code changes)

**Why this exists:** before any task touches code, Claude Code should understand what it's plugging into, so later tasks don't guess at your real schema/interfaces.

**Prompt to give Claude Code:**
```
Read through this repo (particularly promo_scraper/hybrid_promo_extractor.py,
database/models.py, database/connection.py, dashboard/app.py, dashboard/utils/,
llm/factory.py, scripts/run_hybrid_promo_scraper.py, flows/master_pipeline.py,
and config/targets/*.json).

Do not write any code. Produce HANDOFF.md summarizing:
- The current `competitors` table schema (exact columns from database/models.py)
- The current `promotions` table schema (exact columns)
- The exact config JSON shape HybridPromoExtractor expects (examine __init__ in
  hybrid_promo_extractor.py — document required vs optional fields and valid
  `extraction_strategy` values: "text", "screenshot", "image", "hybrid")
- How dashboard/app.py currently structures its Streamlit content (tabs? pages?
  single-page? sidebar filters?)
- How database/connection.py exposes a DB session/connection (SessionLocal,
  get_session(), init_db())
- How llm/factory.py works — what providers are supported (groq, litellm),
  what get_llm_client(), get_llm_client_with_fallback(), and get_langchain_llm()
  return, and how the FallbackLLMClient handles 429s
- The existing Alembic migration setup (alembic/ directory, alembic.ini)
- Whether any auth/session pattern exists in the app (if none exists, say so
  explicitly)
- How master_pipeline.py loads targets (load_targets() in
  scripts/run_hybrid_promo_scraper.py — filesystem glob)
- Anything in the repo that contradicts assumptions in the attached
  implementation plan v3 (flag it, don't silently resolve it)
```

**Deliverable:** `HANDOFF.md` — ground truth about the real codebase. Every later task attaches this alongside the plan.

---

## Task 1 — Foundation: Module Structure, Models, Orchestrator Skeleton
*(Plan §4, §5, §6, §10 — Phase 1)*

**Scope:** create the `agent/` package, all Pydantic state models, and an orchestrator skeleton with stub nodes (no real logic yet — just wiring that compiles and routes correctly).

**Prompt to give Claude Code:**
```
Attach: implementation plan v3 (§4-6, §10), Task 0's HANDOFF.md

Build:
- agent/__init__.py, agent/models.py (SiteAnalysis, GeneratedArtifacts,
  ValidationReport, AgentState — exact fields per §6, using
  `extraction_strategy` not `extraction_type`, with `scraper_code: str | None`)
- agent/orchestrator.py with the LangGraph StateGraph wired per §10, using
  stub node functions that just log and pass state through unchanged
  (NO repair node — deferred per v3)
- agent/prompts.py with the actual prompt constants from §7 and §8
  (EXPLORATION_VISUAL_PROMPT, DOM_ANALYSIS_PROMPT, CONFIG_GENERATION_PROMPT,
  CUSTOM_SCRAPER_PROMPT, TEST_ASSERTION_PROMPT)

Do NOT implement exploration/generation/validation logic yet — stub only.
Write a small test that builds the graph and runs it through with a fake URL,
confirming the routing logic (route_after_validation) behaves correctly for
scores >=90, 70-89, <70, and when sandbox_violations is non-empty.

End by producing HANDOFF.md: what was built, exact file paths, how to run the
test, and what stub functions the next task needs to fill in.
```

**Deliverable:** working skeleton + `HANDOFF.md`.

---

## Task 2 — Exploration Agent + Anti-Bot Detection
*(Plan §7, §7a — Phase 2)*

**Prompt to give Claude Code:**
```
Attach: implementation plan v3 (§7, §7a), Task 1's HANDOFF.md

Implement agent/exploration_agent.py:
- Playwright site visit, screenshot capture, DOM extraction, scroll-and-recapture
  (per the §7 workflow diagram)
- The ANTI_BOT_CHECKS dict and score_anti_bot_risk() function exactly as in §7a
- Gemini Vision call using the EXPLORATION_VISUAL_PROMPT from agent/prompts.py
  (the exact prompt text is in §7 of the plan)
- LLM call (via llm/factory.py's get_llm_client_with_fallback() or
  get_langchain_llm()) to classify extraction_strategy and identify CSS selectors,
  using DOM_ANALYSIS_PROMPT from agent/prompts.py
- Wire this into the "exploration" node in agent/orchestrator.py, replacing the stub

Important: use the existing llm/factory.py for LLM calls, NOT a direct
Anthropic/Claude client. The repo uses LiteLLM/Groq with fallback.

Test against 3 real URLs I'll provide, and confirm anti_bot_signals dict is
populated with which specific checks fired for each site.

End with HANDOFF.md: what was tested, any sites where anti-bot detection
behaved unexpectedly, and what SiteAnalysis looks like on real output.
```

**Note:** have 3 real competitor URLs ready before starting this session — one you expect to be clean, one you suspect has bot protection, one with image-heavy promos.

---

## Task 3 — Generation Agent
*(Plan §8 — Phase 3)*

**Prompt to give Claude Code:**
```
Attach: implementation plan v3 (§8), Task 0's HANDOFF.md (for exact config
JSON shape HybridPromoExtractor expects), Task 2's HANDOFF.md

Implement agent/generation_agent.py:
- Takes a SiteAnalysis, calls LLM via llm/factory.py with
  CONFIG_GENERATION_PROMPT to produce the config JSON in the EXACT shape
  HybridPromoExtractor consumes (per Task 0's findings — do not invent a
  different shape)
- The config MUST include: brand, source_url, extraction_strategy (one of
  "text", "screenshot", "image", "hybrid"), text_selectors, screenshot_selectors,
  and the image filter thresholds
- Optional custom scraper code generation path (per §8 workflow)
- Test assertion generation
- Wire into the "generation" node

Test using the real SiteAnalysis outputs saved from Task 2's session.

End with HANDOFF.md: sample generated config for each of the 3 test sites,
and whether any generated config would actually be accepted by
HybridPromoExtractor's current interface (check against Task 0 findings).
```

---

## Task 4 — Sandbox Infrastructure
*(Plan §9a, §9a-1 — Phase 4, sandbox half)*

**This is the highest-stakes new infrastructure piece — keep it isolated from validation logic so it's easy to review on its own.**

**Prompt to give Claude Code:**
```
Attach: implementation plan v3 (§9a, §9a-1)

Build, but do NOT yet wire into the agent pipeline:
- docker/Dockerfile.sandbox — minimal Python image with dependencies a generated
  scraper needs (playwright, requests/bs4, the promo_scraper module — whatever
  HybridPromoExtractor-compatible scrapers use). Include sandbox_entrypoint.py
  in the image per §9a-1.
- docker/setup_egress_network.sh — creates the "scraper-egress-only" Docker
  network that restricts outbound traffic to a single allowlisted host,
  parameterized per target domain
- agent/sandbox_runner.py per the code in §9a, with detect_violations()
  implemented to check for: OOM kill, non-zero exit from a disallowed network
  attempt, disallowed filesystem write attempt
- agent/sandbox_entrypoint.py per §9a-1 — handles both the custom scraper
  code path AND the standard HybridPromoExtractor path (when scraper_code is
  None, run HybridPromoExtractor with the config directly)
- A standalone test script that runs deliberately misbehaving test scrapers
  (one that tries to write to /etc, one that tries to reach a non-allowlisted
  host, one that leaks memory) and confirms each is caught and reported in
  violations

Do not integrate this into validation_agent.py yet — that's the next task.

End with HANDOFF.md: exact commands to build the image, how the egress-only
network is created/torn down, confirmed test results for each misbehaving
scraper, and any environment prerequisites (Docker daemon access, permissions).
```

**Note:** this task needs an actual Docker daemon available — flag that constraint if your environment isn't containerized locally.

---

## Task 5 — Validation Agent + Scoring + Outcome Logging
*(Plan §9, §9b, §9c — Phase 4, validation half)*

**Prompt to give Claude Code:**
```
Attach: implementation plan v3 (§9, §9b, §9c), Task 4's HANDOFF.md

Implement agent/validation_agent.py:
- Uses sandbox_runner.py from Task 4 (do not reimplement sandboxing here)
- Pydantic schema validation of extracted offers
- Confidence scoring exactly per §9b, with score_breakdown populated
  (each contributing term, not just the final number)
- sandbox_violations forcing score=0/reject regardless of offer count
- Zero offers -> score starts at 10 (not 20)
- Wire into the "validation" node

Add the agent_run_outcomes table (exact SQL in §9c) as an Alembic migration
using the existing alembic/ setup. Also add the corresponding SQLAlchemy
model to database/models.py. Log every validation run to this table.

Test end-to-end using Task 3's generated configs run through the real sandbox.

End with HANDOFF.md: real confidence scores + breakdowns for the 3 test sites,
confirmation the outcomes table is being written to, and the migration file path.
```

---

## Task 6 — Auth Hooks + Data-Driven Registration
*(Plan §11a, §12a — Phase 5, auth/registration half)*

**Prompt to give Claude Code:**
```
Attach: implementation plan v3 (§11a, §12a), Task 0's HANDOFF.md

Implement:
- auth/approval_rbac.py per §11a — lightweight single role (AGENT_USER),
  with hooks for future OPERATOR/APPROVER split. The app currently has NO
  auth (per Task 0 findings), so this is greenfield — use a simple
  get_current_user() that reads AGENT_USER_ID from env.
- agent_audit_log table (exact SQL in §11a) via Alembic migration +
  SQLAlchemy model in database/models.py
- prefect_target_registry table (exact SQL in §12a) via Alembic migration +
  SQLAlchemy model in database/models.py
- New columns on competitors table (extraction_strategy, agent_generated,
  agent_confidence, agent_notes, source_url) via Alembic migration
- Update load_targets() in scripts/run_hybrid_promo_scraper.py to read from
  prefect_target_registry first with filesystem fallback (per §12a code sample).
  flows/master_pipeline.py should NOT need changes — it already calls
  load_targets().
- agent/orchestrator.py "registration" node: writes config file, updates/inserts
  competitors row, inserts prefect_target_registry row, inserts audit log row —
  ALL in a single DB transaction. Rollback everything if any step fails.

End with HANDOFF.md: confirmation the registry-read replaces the old glob-only
behavior while maintaining backward compat, the migration file paths, and how
the auth hooks work.
```

---

## Task 7 — Streamlit Approval UI + Edit-Then-Revalidate
*(Plan §11, §11b — Phase 5, UI half)*

**Prompt to give Claude Code:**
```
Attach: implementation plan v3 (§11, §11b), Task 6's HANDOFF.md

Implement the Agent tab in dashboard/app.py (or a new module imported into it,
matching this repo's existing Streamlit structure per Task 0 findings — the
app is a single-page layout with sidebar filters, not tabbed):
- URL/brand/requirements input form
- Three-column results display (site analysis incl. anti-bot signals, generated
  config, validation report incl. score_breakdown and sandbox_violations)
- Approve button (logs to audit log via Task 6's auth hooks)
- Edit Config button that re-enters the graph at "validation" (not registration)
  per the §11b code sample — confirm this actually re-runs scoring, don't just
  save the edit
- Reject button that logs a reason to audit log
- All actions logged to agent_audit_log (Task 6)

Test the full loop manually: generate → review → edit → confirm re-validation
actually happens → approve → confirm registration fires (Task 6's logic).

End with HANDOFF.md: screenshots or a description of the working UI, confirmed
edit-then-revalidate behavior, and any TODOs left.
```

---

## Task 8 — Health Check + Live Testing + Docs
*(Plan §19a detection only, §20 success criteria — Phase 6 + 7)*

**Prompt to give Claude Code:**
```
Attach: implementation plan v3 (§19a, §20 success criteria), Task 5's HANDOFF.md,
Task 6's HANDOFF.md

Implement:
- scripts/run_health_check.py per §19a — reads active targets from
  prefect_target_registry (Task 6), checks last 3 runs' offer counts,
  logs to agent_run_outcomes (Task 5's table). Detection + alerting ONLY —
  no automated repair (deferred to fast-follow, leave a TODO comment).
- Run the full pipeline end-to-end on 5 real target sites (I'll provide URLs)
- Confirm success criteria from §20 phase by phase — write a checklist of
  which pass and which don't
- Update README.md with: how to run the agent CLI (§17), how to run health
  checks, how to interpret a ValidationReport, and how the audit log works

End with HANDOFF.md: final checklist against §20's success criteria, any
criteria not met and why, health check test results, and a short "known gaps"
list for fast-follow items (repair agent, calibration script, RBAC role split).
```

---

## Quick Reference — Task Dependency Order

```
Task 0 (orientation, no deps)
  └─> Task 1 (skeleton)
        ├─> Task 2 (exploration) ──┐
        └─> Task 4 (sandbox)  ─────┤  ← can run in parallel
                                    │
        Task 3 (generation, needs Task 2 output) ──┤
                                                    │
        Task 5 (validation, needs Task 3 + Task 4) ┘
              └─> Task 6 (auth + registration)
                    └─> Task 7 (UI)
                          └─> Task 8 (health check + live testing + docs)
```

Tasks 2 and 4 can run in parallel sessions if you want to move faster, since neither depends on the other. Everything from Task 5 onward is strictly sequential.

> **[v3] Changes from v2 breakdown:**
> - Old Task 8 (Repair Agent) deferred entirely — no longer in the task list.
> - Old Task 9 (Calibration Script + Live Testing + Docs) merged into new Task 8, minus the calibration script (deferred).
> - Total: 9 tasks → 9 tasks (0-8), but scope is tighter — 4 weeks instead of 5.
