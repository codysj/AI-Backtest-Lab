# Tasks

## Now

- Execution-timing credibility pass completed:
  - Single-asset and multi-asset engines separate close-time decisions, submitted orders, fills, and order lifecycle events.
  - Default execution is the next available open; same-close execution is an explicit opt-in policy.
  - Final-bar submissions expire instead of receiving an impossible fill.
  - Strategy decision inputs are copied histories bounded at the current bar, with future-mutation regression coverage.
  - API responses expose audit ledgers and the frontend request contract/configuration UI exposes execution timing.

- Research Copilot hardening pass completed:
  - Approval now revalidates the browser-returned compiled payload against the existing API request schema immediately before execution.
  - Malformed or tampered approval payloads return sanitized field-level errors, clear the compiled payload from the returned state, and do not echo raw browser-supplied values.
  - Already-executed states are blocked from a second approval run and report blocked status instead of completed status.
  - Tests now cover no-execution-before-approval, mismatched approval, one approved service call, malformed approval sanitization, already-executed approval blocking, deterministic grid-search analysis, deterministic walk-forward analysis, and Research Copilot API endpoint behavior.
  - The Research Copilot load/approval UI disables actions unless a ready compiled payload with no validation errors is present.

- Backtest Lab Research Copilot UI added:
  - New Research Copilot mode calls `POST /api/ai/research-plan` and displays graph steps, status, target mode, draft details, compiled payload JSON, warnings, unsupported items, and validation errors.
  - Approval remains explicit through a button that sends the prior state plus matching `approved_action` to `POST /api/ai/research-approve`.
  - Approved results display workflow summary, deterministic backend analysis, and recommended next step.
  - Compiled payloads can be loaded into existing Single Run, Grid Search, or Walk-Forward forms for review without auto-running.
  - No frontend API-key handling, generated Python execution, auth, database persistence, server-side sessions, broker integration, live trading, or TypeScript reimplementation of backtesting/research metrics was added.

- Research Copilot FastAPI endpoints added:
  - `POST /api/ai/research-plan` drafts and compiles through the existing graph, returns sanitized request/response state, and stops before any workflow execution.
  - `POST /api/ai/research-approve` resumes prior response state and runs at most one existing workflow only when `approved_action` matches the compiled target mode.
  - Mismatched approval, unsupported targets, missing payloads, validation errors, and already-executed states do not run workflows.
  - No frontend UI, auth, database persistence, server-side sessions, generated Python execution, broker integration, or live trading was added.

- Backend-only LangGraph Research Copilot skeleton added:
  - `backtester/agents/` typed state, graph nodes, LangGraph wiring, safe workflow wrappers, and deterministic result analysis.
  - Graph flow drafts and compiles through existing AI Builder services, records warnings/errors/audit steps, and stops at an approval gate by default.
  - Resumed states can run exactly one existing workflow only when `approved_action` matches the compiled target mode.
  - Initially added without frontend UI, generated strategy execution, shell/filesystem tool, database persistence, broker integration, or live trading.

- AI Strategy Builder backend skeleton added:
  - `backtester/ai/` schemas, prompt template, provider abstraction/factory, deterministic fake provider, optional OpenAI-compatible provider, validator, and compilers.
  - OpenRouter is available as a first-class backend provider with default model `tencent/hy3-preview:free`, server-side bearer auth, chat-completions requests, and optional app attribution headers.
  - Optional LangChain structured-output provider path added with `BACKTESTER_AI_PROVIDER=langchain_openai_compatible`, using backend-only env vars and the existing `StrategyDraft` validation/normalization boundary.
  - `POST /api/ai/strategy-draft` returns inert, validated draft JSON. Fake remains the default provider; real providers are server-side opt-in through env vars.
  - `POST /api/ai/compile` compiles reviewed drafts into existing Backtest, Grid Search, and Walk-Forward request payloads.
  - Backtest Lab AI Builder UI now drafts from prompts, previews assumptions/warnings/unsupported items, compiles drafts, and loads compiled configs into existing workflow forms.
  - Constrained rule-based strategy DSL added for AI Builder single-run handoff: close, SMA, prior rolling high/low, Bollinger bands, and simple comparison/cross operators.
  - No generated Python execution, persistence, broker integration, live trading, frontend API-key handling, or committed secrets.

The latest research-workstation batch added:
  - `POST /api/grid-search` with leaderboard rows, failed-combination preservation, heatmap data, and robustness warnings.
  - `POST /api/walk-forward` with train/test folds, selected parameters, degradation ratios, aggregate warnings, and parameter stability.
  - Backtest Lab mode switcher for Single Run, Grid Search, and Walk-Forward workflows.
  - Richer server-side risk analytics and frontend exports.

## Next

- Execute the staged credibility roadmap in `docs/technical-roadmap.md`, beginning with golden accounting fixtures and explicit close-signal/next-open execution semantics before persistence, portfolio UI, or performance work.
- Replace bounded DataFrame copies with a dedicated read-only market-view abstraction while preserving the new causal boundary, then add future-bar mutation tests for every built-in strategy.
- Add a durable, idempotent research-job service with persisted attempts/trials, cancellation, progress, lease-based recovery, immutable input artifacts, and replayable provenance manifests.
- Define and test raw/adjusted price, split, dividend, missing-bar, and stale-valuation policies before expanding data-dependent workflows.
- Build an experiment registry with preserved failed trials, locked final holdouts, and documented selection-bias diagnostics before presenting optimized results as evidence.
- Refactor multi-asset processing around simultaneous intents, portfolio allocation constraints, union-calendar tradability, and explicit stale valuation before exposing it through API and UI.
- Compare the stable optimized engine against a simple reference simulator on identical event ledgers, then publish hardware, workload, memory, dispersion, correctness hashes, and attributable speedup.
- Manually test Research Copilot with the API and frontend running together, then capture updated portfolio screenshots if desired.
- Decide whether Research Copilot sessions need persistence only if a future durable audit or saved-run feature is explicitly requested.
- Expose multi-asset backtesting through FastAPI only after its timing, calendar, allocation, and accounting contracts satisfy the roadmap acceptance cases.
- Expand the rule DSL only when there is a tested strategy intent contract for more indicators, OR composition, and research optimization.
- Add multi-asset controls/results to Backtest Lab only after the API contract exists.
- Add CLI support for multi-asset backtests.
- Add a small screenshot or short GIF asset for the remodeled Backtest Lab if a committed portfolio asset is desired.
- Add richer walk-forward charts once the table-first validation workflow has settled.
- Add backend export endpoints only if frontend-side CSV/JSON export becomes insufficient.
- Add a local Python interpreter/venv setup note or script for Windows workspaces where `python` is not on PATH.
- Measure a reference-engine baseline and update `docs/benchmark_results.md` only after execution semantics stabilize; reconcile events, fills, cash, positions, and equity before publishing speedup.
- Revisit AI Builder provider quality if OpenRouter free-model rate limits or availability become noisy during demos.
- Improve AI Builder DSL prompting with more few-shot examples for rule-based drafts.
- Add model-specific tests or notes for LangChain-backed providers if a demo model requires provider-specific structured-output tuning.
- Add model-specific tuning notes for OpenRouter free models and any paid models used in demos.

## Later

- Add richer chart interactions or a more finance-specific charting library if Recharts becomes limiting.
- Add more strategy examples.
- Add benchmark history from a pre-optimization baseline commit.
- Add a public deployment guide if the project moves beyond local demo use.

## Questions / Needs Owner Input

- Should Backtest Lab stay single-asset for portfolio demo clarity, or should multi-asset be prioritized next?
- Should CI run Node installation/build on every push?
- Should examples default entirely to synthetic data to avoid network surprises?
- Should generated docs PNGs and Backtest Lab screenshots be tracked in Git?
