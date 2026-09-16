# Current State

Last documentation pass: 2026-05-08.

## Implemented Functionality

- Data loading with yfinance and Parquet cache under `~/.backtester/cache/`.
- Clean OHLCV validation with schema `open`, `high`, `low`, `close`, `volume`.
- Single-asset backtest engine.
- Multi-asset backtest engine with intersection-based date alignment.
- Explicit execution timing for both engines:
  - close-derived decisions and submitted orders are distinct from fills
  - `CLOSE_SIGNAL_NEXT_OPEN` is the default policy
  - `SAME_CLOSE` remains an explicit comparison-only opt-in
  - final-bar orders expire when no later execution bar exists
  - result ledgers link decisions, orders, fills, and status events
  - strategy decision calls receive history bounded at the current bar
- Strategy interfaces:
  - `Strategy`
  - `MultiAssetStrategy`
  - `SingleStrategyMultiAssetWrapper`
- Built-in strategies:
  - Momentum SMA crossover
  - Mean reversion with Bollinger-style bands
- Constrained rule-based strategy DSL:
  - `RuleBasedStrategySpec` with strict Pydantic indicator and condition schemas.
  - `RuleBasedStrategy` implementing close, SMA, prior rolling high/low, and Bollinger upper/lower indicators.
  - Operators: `>`, `<`, `>=`, `<=`, `crosses_above`, and `crosses_below`.
  - Entry rules use ALL logic; exit rules use ANY logic.
- Portfolio simulation:
  - Cash
  - Positions
  - Orders/trades
  - Commission
  - Slippage
  - Equity curve
- Position sizing:
  - Fixed quantity
  - Fixed dollar
  - All-in
  - Percent equity
  - Simplified volatility targeting
- Metrics:
  - Total and annualized return
  - Sharpe/Sortino
  - Max drawdown
  - Alpha/beta
  - Excess returns
  - Information ratio
  - Benchmark equity
  - Win rate and profit factor
  - Trade summaries
- Grid search for single-asset strategies, including API/service conversion, failed-combination preservation, heatmap-ready response data, and robustness warnings.
- Walk-forward validation for single-asset strategies through FastAPI and Backtest Lab.
- Richer risk analytics:
  - rolling Sharpe
  - rolling volatility
  - rolling drawdown
  - drawdown duration
  - best/worst day
  - monthly returns
  - VaR/CVaR
- Matplotlib chart helpers.
- CLI:
  - `run`
  - `grid-search`
- FastAPI API:
  - `GET /health`
  - `GET /api/strategies`
  - `POST /api/ai/strategy-draft`
  - `POST /api/ai/compile`
  - `POST /api/ai/research-plan`
  - `POST /api/ai/research-approve`
  - `POST /api/backtest`
  - `POST /api/grid-search`
  - `POST /api/walk-forward`
  - Configurable CORS origins through `BACKTESTER_CORS_ORIGINS`
- AI Strategy Builder backend foundation:
  - `backtester/ai/` package with strict Pydantic draft schemas.
  - Prompt template that requires JSON-only output, forbids executable code, forbids extra fields, and documents the exact rule-based DSL shape expected from real providers.
  - `LLMProvider` protocol, provider factory, deterministic `FakeStrategyDraftProvider`, optional OpenAI-compatible provider implementation, first-class OpenRouter selection through `BACKTESTER_AI_PROVIDER=openrouter`, and optional LangChain OpenAI-compatible selection through `BACKTESTER_AI_PROVIDER=langchain_openai_compatible`.
  - OpenRouter defaults to `https://openrouter.ai/api/v1`, `POST /chat/completions`, and model `tencent/hy3-preview:free`, with optional backend attribution headers from `BACKTESTER_AI_APP_NAME` and `BACKTESTER_AI_APP_URL`. `BACKTESTER_AI_USE_RESPONSE_FORMAT=false` can disable the OpenAI-style `response_format` request field while keeping JSON parsing and strict draft validation.
  - LangChain provider support is optional through `langchain-openai`, available via `python -m pip install ".[ai-langchain]"` or `python -m pip install -r requirements-ai-langchain.txt`. It uses `ChatOpenAI.with_structured_output(StrategyDraft)` and reuses backend-only AI model, API key, base URL, and timeout env vars. Missing LangChain imports fail as sanitized backend configuration errors only when the LangChain provider is selected.
  - Backend-only AI environment variables for `BACKTESTER_AI_ENABLED`, provider, model, API key, base URL, timeout, app name, and app URL. No API key is exposed to the frontend.
  - Repo-root `.env.example` is committed as a placeholder-only OpenRouter template. FastAPI auto-loads a private repo-root `.env` on startup through `python-dotenv` without overriding already-set system environment variables. Local `.env` and `.env.*` files are gitignored, while `.env.example` remains tracked.
  - A limited provider-output normalization layer repairs only deterministic schema-adjacent mistakes before Pydantic validation: simple `benchmark` boolean strings, clearly structured `equity_sizing` objects, and clean `rule_spec.conditions` references that can be converted into the internal `rule_spec.rules` DSL.
  - Ambiguous sizing, malformed rule specs, unsupported indicators/operators, arbitrary formulas, raw code, and extra provider fields remain rejected. Validation errors include sanitized provider/model context and failing fields without exposing API keys or raw payloads.
  - Semantic draft validator for dates, supported strategies, windows, unsupported concepts, and raw-code field rejection.
  - Compilers that map validated drafts into existing `BacktestRequest`, `GridSearchRequest`, and `WalkForwardRequest` payloads, including rule-based single-run payloads with `rule_spec`.
  - API endpoints return draft/compile status, warnings, unsupported items, and validation errors without executing workflows. Fake remains the default provider, including tests.
- Backend/API Research Copilot:
  - `backtester/agents/` package with typed `ResearchGraphState`, audit events, approval actions, workflow summaries, LangGraph wiring, small graph nodes, and safe workflow wrappers.
  - Explicit graph steps: `interpret_research_goal`, `draft_strategy`, `validate_draft`, `compile_request`, `await_user_approval`, optional `run_workflow`, `analyze_results`, and `recommend_next_step`.
  - The initial path drafts and compiles through existing safe AI services, then stops with `approval_required=true` before any backtest, grid-search, or walk-forward service call.
  - A resumed state must provide a matching `approved_action` (`run_backtest`, `run_grid_search`, or `run_walk_forward`) before one existing workflow can run. Mismatched approval records a validation error and does not run.
  - `POST /api/ai/research-plan` exposes the draft-and-compile path and returns sanitized graph state without execution.
  - `POST /api/ai/research-approve` accepts prior response state plus one explicit approval, refuses mismatched or already-executed states, and runs at most one existing workflow through the service wrappers.
  - Approval payloads are revalidated against the existing API request schemas immediately before execution. Malformed or tampered payloads return sanitized field-level errors, clear the compiled payload from the response, and do not echo raw browser-supplied values.
  - Deterministic result analysis surfaces heuristic notes for benchmark underperformance where available, high drawdown, sparse trades, failed grid combinations, and walk-forward degradation.
  - No frontend UI, generated code execution, shell/filesystem tools, broker integration, auth, database persistence, server-side sessions, or live trading was added.
- Backtest Lab frontend:
  - Next.js 15 App Router, TypeScript, Tailwind CSS, Recharts.
  - Full-screen dark finance dashboard shell.
  - Sidebar, top run-context header, and sticky right configuration panel.
  - Mode switcher for Single Run, Grid Search, Walk-Forward, AI Builder, and Research Copilot workflows.
  - Single-asset backtest form with inline validation.
  - Grid-search form with strategy parameter ranges, optimization metric, benchmark toggle, and top-N control.
  - Grid-search leaderboard, best-row summary, robustness warnings, failed-combination display, two-parameter heatmap, CSV/config export, and selected-row handoff into a single run.
  - Walk-forward form with train/test/step windows and strategy parameter grids.
  - Walk-forward fold table, train/test metric comparison, degradation ratios, aggregate warnings, and parameter stability.
  - AI Builder UI with natural-language prompt templates, draft generation through `POST /api/ai/strategy-draft`, readable strategy preview, assumptions/warnings/unsupported states, compile handoff through `POST /api/ai/compile`, and secondary reproducibility JSON.
  - Research Copilot UI with natural-language research goals, plan calls through `POST /api/ai/research-plan`, graph step timeline, status and target-mode display, draft and compiled payload preview, warnings/unsupported/validation errors, explicit approval through `POST /api/ai/research-approve`, workflow result summary, deterministic analysis, recommendation, and safe compiled-payload handoff into existing forms.
  - API health indicator and strategy metadata loading.
  - Empty, loading, and error states.
  - KPI cards.
  - Equity chart with optional buy-and-hold benchmark.
  - Drawdown chart.
  - Summary, Trades, Metrics, and Parameters tabs.
  - Risk tab and frontend exports for trades CSV, metrics JSON, config JSON, and grid-search CSV.
  - Reproducibility view for submitted config and strategy parameters.
- Examples, benchmark scripts, tests, mypy config, Python CI, and frontend CI checks.
- Local Python development should use a repo-root `.venv`. The `.venv/`, `venv/`, and `env/` directories are gitignored and should never be committed. Validation commands should be run from the activated environment.

## Known Incomplete Areas

- Backtest Lab research workflows remain single-asset only.
- Research Copilot is available in Backtest Lab and has no server-side session persistence; the browser passes sanitized response state back to `/api/ai/research-approve`. The backend treats returned state as untrusted and revalidates the compiled payload before execution.
- AI Strategy Builder can optionally call OpenRouter, another real OpenAI-compatible provider, or the optional LangChain OpenAI-compatible adapter when backend env vars and dependencies are configured. It does not execute compiled payloads, execute generated code, or expose API keys to the frontend. Rule-based support is single-run only in v1, and rule-based drafts must conform to the internal `rule_spec.rules` DSL. OpenRouter free models may be rate-limited, temporarily unavailable, lower quality than paid models, or prone to imperfect JSON/schema output; only limited deterministic normalization is applied before strict validation rejects the rest.
- CLI does not expose multi-asset workflows.
- Walk-forward is table-first; richer charts can be added later.
- No live deployment config.
- No auth, database, broker integration, paid data feed, or live trading.
- Benchmark docs include measured optimized synthetic numbers, but baseline speedup is not measured.
- No committed Backtest Lab screenshot or GIF asset; dashboard screenshots are regenerated on demand unless a future portfolio asset is intentionally committed.
- Frontend package uses an npm override for Next's nested PostCSS dependency until a stable Next release no longer needs it.

## Known Bugs Or TODOs

- `docs/benchmark_results.md` still has TODOs for pre-optimization baseline measurement and speedup comparison.
- No committed Backtest Lab screenshot/GIF asset yet; screenshot regeneration workflow is documented.

## Recent Assumptions From Repo State

- Python and frontend commands are both CI gates.
- Frontend is intended as a local portfolio/demo surface, not a deployed product yet.
- Frontend business logic should remain an API client and should not reimplement backtesting logic.
- Backtest Lab should use a Node.js runtime compatible with Next's engine range: `^18.18.0`, `^19.8.0`, or `>=20.0.0`.
- Core tests should remain deterministic and avoid live yfinance/network calls unless explicitly testing mocked loader behavior.
- yfinance-backed CLI/API/browser runs may require network or existing cache.
- Generated Python bytecode, pytest/mypy caches, local virtual environments, frontend build output, and `node_modules` should remain untracked.
- In Windows workspaces where `python` is unavailable on PATH, install Python 3.11+ and create/activate `.venv` with `py -m venv .venv`; after activation, rerun validation through `python -m pytest` and `python -m mypy backtester`.

## Recommended Next Tasks

- Decide whether to expose multi-asset runs through FastAPI, CLI, and Backtest Lab.
- Exercise the Backtest Lab Research Copilot workflow manually against a running FastAPI backend before capturing screenshots.
- Keep Research Copilot approval state request/response-only unless a future durable audit or saved-run feature is explicitly requested.
- Decide later whether Research Copilot needs persistence; current API intentionally uses request/response state passing only.
- Add richer walk-forward visuals if the table-first workflow needs more portfolio polish.
- Add a small screenshot workflow and committed dashboard screenshot once the UI stabilizes.
- Measure a pre-optimization baseline for `docs/benchmark_results.md`.
- Keep the frontend dependency audit clean during future upgrades.
- Expand the rule DSL only after there are clear tests and UI/API contracts for additional indicators, OR composition, and optimization.

## Commands Verified During This Documentation Pass

```bash
python -m pytest
python -m mypy backtester
cd frontend && npm install
cd frontend && npm audit
cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm run build
```

Recent documented results:

- `python -m pytest`: not run successfully during the 2026-05-08 hardening pass. PowerShell returned `python : The term 'python' is not recognized as the name of a cmdlet, function, script file, or operable program.`
- `.\.venv\Scripts\python.exe -m pytest`: success after Research Copilot hardening. 207 passed with existing LangGraph/Python deprecation warnings.
- `python -m mypy backtester`: not run successfully during the 2026-05-08 hardening pass for the same missing `python` PATH issue.
- `.\.venv\Scripts\python.exe -m mypy backtester`: success after Research Copilot hardening. No issues found in 45 source files.
- `cmd /c npm install` from `frontend/`: success. Packages were already up to date.
- `cmd /c npm audit` from `frontend/`: initial sandboxed run failed because the npm audit endpoint returned an error; rerun outside the sandbox succeeded with `found 0 vulnerabilities`.
- `cmd /c npm run lint` from `frontend/`: success.
- `cmd /c npm run typecheck` from `frontend/`: success. `next typegen` generated route types and `tsc --noEmit` passed, including the Research Copilot API types.
- `cmd /c npm run build` from `frontend/`: success. Next.js 15.5.15 production build compiled successfully and generated 4 static pages.
- `.\.venv\Scripts\python.exe -m pip install "langgraph>=0.2,<1"`: success. Installed the newly declared backend Research Copilot graph dependency into the local venv for validation.
- `.\.venv\Scripts\python.exe -m pytest`: success after adding the backend Research Copilot skeleton. 197 passed with LangGraph deprecation warnings from the installed dependency.
- `.\.venv\Scripts\python.exe -m mypy backtester`: success after adding the backend Research Copilot skeleton. No issues found in 43 source files.
- `.\.venv\Scripts\python.exe -m pytest tests\test_api.py tests\test_research_graph.py tests\test_ai_builder.py`: success after exposing Research Copilot API endpoints. 88 passed with existing LangGraph/Python deprecation warnings.
- `python -m pytest`: not run successfully in the local Windows shell. PowerShell returned `python : The term 'python' is not recognized as the name of a cmdlet, function, script file, or operable program.`
- `.\.venv\Scripts\python.exe -m pytest`: success after exposing Research Copilot API endpoints. 202 passed with existing LangGraph/Python deprecation warnings.
- `python -m mypy backtester`: not run successfully in the local Windows shell for the same missing `python` PATH issue.
- `.\.venv\Scripts\python.exe -m mypy backtester`: success after exposing Research Copilot API endpoints. No issues found in 45 source files.
- `cmd /c npm run lint` from `frontend/`: success after adding the Research Copilot UI.
- `cmd /c npm run typecheck` from `frontend/`: success after adding the Research Copilot UI. `next typegen` generated route types and `tsc --noEmit` passed.
- `cmd /c npm run build` from `frontend/`: success after adding the Research Copilot UI. Next.js 15.5.15 production build compiled successfully and generated 4 static pages.
- `python -m pytest`: not run successfully in the local Windows shell after the Research Copilot UI docs update. PowerShell returned `python : The term 'python' is not recognized as the name of a cmdlet, function, script file, or operable program.`
- `.\.venv\Scripts\python.exe -m pytest`: success after the Research Copilot UI docs update. 202 passed with existing LangGraph/Python deprecation warnings.
- `python -m mypy backtester`: not run successfully in the local Windows shell for the same missing `python` PATH issue.
- `.\.venv\Scripts\python.exe -m mypy backtester`: success after the Research Copilot UI docs update. No issues found in 45 source files.
- `python -m pytest`: not run successfully. PowerShell returned `python : The term 'python' is not recognized as the name of a cmdlet, function, script file, or operable program.`
- `python -m mypy backtester`: not run successfully. PowerShell returned `python : The term 'python' is not recognized as the name of a cmdlet, function, script file, or operable program.`
- `cmd /c npm run lint` from `frontend/`: success after adding the AI Builder UI.
- `cmd /c npm run typecheck` from `frontend/`: success after adding the AI Builder UI. `next typegen` generated route types and `tsc --noEmit` passed.
- `cmd /c npm run build` from `frontend/`: success after clearing a stale generated `.next` directory. Next.js 15.5.15 production build compiled successfully and generated 4 static pages.
- `python -m pytest --cov=backtester`: not run successfully for the same reason; no Python launcher or local `venv` was available in this workspace.
- `cmd /c npm run lint` from `frontend/`: success.
- `cmd /c npm run typecheck` from `frontend/`: success. `next typegen` generated route types and `tsc --noEmit` passed.
- `cmd /c npm run build` from `frontend/`: success. Next.js 15.5.15 production build compiled successfully and generated 4 static pages.
- `cmd /c npm audit` from `frontend/`: success after rerunning outside the sandbox to allow registry access. `found 0 vulnerabilities`.
- `cmd /c npm install next@15.5.15 postcss@^8.5.10` from `frontend/`: success. Upgraded Next and PostCSS without `npm audit fix --force`.
- `cmd /c npm install` from `frontend/`: success. Refreshed install state after adding the scoped PostCSS override.
- `cmd /c npm update postcss` from `frontend/`: success. Applied the override so Next's nested PostCSS resolved to 8.5.10.
- `cmd /c npm install --save-dev eslint eslint-config-next @eslint/eslintrc` from `frontend/`: success. Added frontend lint tooling; `npm audit` reported 0 vulnerabilities.
- `cmd /c npm install --save-dev eslint@^8.57.1` from `frontend/`: success. Pinned ESLint to a version compatible with `eslint-config-next`.
- `cmd /c npm install --save-dev eslint-config-next@15.5.15` from `frontend/`: success. Aligned the lint config package with Next.js 15.5.15.
- `cmd /c npm ci` from `frontend/`: not run successfully in the local Windows workspace. npm returned `EPERM: operation not permitted, unlink ...next-swc.win32-x64-msvc.node`; this appears to be a local native-binary file lock/permission issue, not a lockfile consistency issue.
- `cmd /c npm install` from `frontend/`: success after rerunning outside the sandbox to recover from the local npm cache/node_modules EPERM error.
- `cmd /c npm audit` from `frontend/`: success. `found 0 vulnerabilities`.
- `cmd /c npm run lint` from `frontend/`: success.
- `cmd /c npm run typecheck` from `frontend/`: success. `next typegen` generated route types and `tsc --noEmit` passed.
- `cmd /c npm run build` from `frontend/`: success. Next.js 15.5.15 production build compiled successfully, skipped internal linting because lint is run separately, checked validity of types, generated 4 static pages, and reported `/` at 117 kB with 219 kB first-load JS.

If these docs are read later, rerun the commands before relying on the status.
