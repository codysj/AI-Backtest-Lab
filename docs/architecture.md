# Architecture

## High-Level Architecture

Backtester has three visible layers:

- Core Python backtesting package in `backtester/`.
- FastAPI API wrapper in `backtester/api/`.
- Next.js dashboard in `frontend/`, branded in the UI as Backtest Lab.

The core package is intentionally modular. Data loading, strategies, portfolio state, metrics, research utilities, and visualization are independently testable. Engines and API services compose those modules. The frontend is an API client: it renders forms, validation, charts, and tables, but it does not reimplement backtesting logic.

## Main Directories

- `backtester/data/`
  - Fetches OHLCV data with yfinance, cleans it, validates schema, and caches Parquet files under `~/.backtester/cache/`.
- `backtester/ai/`
  - Defines the safe natural-language strategy draft contract, prompt template, provider abstraction and factory, deterministic fake provider, optional OpenAI-compatible provider, optional LangChain OpenAI-compatible adapter, limited provider-output normalization, validation helpers, and compilers into existing API request schemas. Drafts and compiled payloads are inert data and are not executed.
- `backtester/agents/`
  - Defines a backend Research Copilot graph. It moves from natural-language goal interpretation to inert AI draft, validation, compile, approval gate, optional approved workflow execution, deterministic result analysis, and next-step recommendation through typed state transitions.
- `backtester/strategy/`
  - Defines `Strategy`, `MultiAssetStrategy`, `Signal`, causal indicators, built-in SMA crossover, Bollinger mean reversion, RSI reversion, Donchian breakout, and MACD crossover strategies, the strategy registry, constrained rule DSL schemas, `RuleBasedStrategy`, and a wrapper for applying one single-asset strategy across multiple assets.
- `backtester/portfolio/`
  - Defines `Order`, `Trade`, `Position`, and `Portfolio`. Tracks cash, positions, trade history, and equity curve.
- `backtester/engine/`
  - Contains single-asset and multi-asset engines, immutable configs, result dataclasses, shared position sizing, and close-time protective exits.
- `backtester/metrics/`
  - Computes returns, drawdowns, Sharpe/Sortino, alpha/beta, information ratio, profit factor, benchmark equity, and trade-level summaries.
- `backtester/research/`
  - Runs parameter grid searches and returns sorted `pandas.DataFrame` results, including failed-combination rows for research diagnostics.
- `backtester/viz/`
  - Matplotlib chart helpers for equity, drawdown, trades, and strategy comparison.
- `backtester/api/`
  - FastAPI routes, Pydantic schemas, and service conversion between engine objects and JSON responses.
- `frontend/app/`
  - Next.js App Router entrypoint, layout, global dark dashboard styles, and page-level state orchestration.
- `frontend/components/`
  - Backtest Lab UI components: app shell, sidebar, top bar, form, metric cards, charts, states, AI Builder, Research Copilot, result tabs, and trade table.
- `frontend/lib/`
  - Frontend API client, TypeScript API types, defaults, and form validation helpers.
- `examples/`
  - Demo scripts and chart generation scripts.
- `benchmarks/`
  - Synthetic benchmark and cProfile scripts.
- `tests/`
  - Unit and smoke tests using deterministic synthetic data where possible.

## Key Components

- `DataLoader.fetch(ticker, start, end)` returns a cleaned OHLCV `DataFrame` with lowercase columns and `DatetimeIndex` named `date`.
- `BacktestEngine.run()` runs one ticker with a `Strategy`.
- `MultiAssetBacktestEngine.run()` runs multiple tickers with a `MultiAssetStrategy`.
- `STRATEGIES` in `backtester/strategy/registry.py` maps strategy ids to metadata, typed parameters, default research grids, and factories. `StrategySpec.build()` is the single construction path for the API, CLI, research, and AI compiler.
- `backtester/strategy/indicators.py` holds causal SMA, EMA, Wilder RSI, MACD, and prior high/low helpers shared by strategies and the rule DSL.
- `risk_exit_reason()` in `backtester/engine/risk.py` decides stop-loss, take-profit, and trailing-stop exits from completed closes for both engines.
- `RuleBasedStrategy` evaluates Pydantic-validated rule specs over precomputed indicators without executing generated code.
- `Portfolio.execute_order()` applies slippage/commission and mutates cash/positions on accepted trades.
- `generate_report()` computes primary performance metrics and optional benchmark comparison keys.
- Additional metrics helpers compute rolling Sharpe, rolling volatility, rolling drawdown, drawdown duration, best/worst day, monthly returns, VaR, and CVaR from first principles.
- `buy_and_hold_equity()` creates a benchmark equity curve for comparison.
- `run_grid_search()` expands a parameter grid, runs backtests, and records errors per combination.
- FastAPI `POST /api/backtest` wraps a single-asset backtest for Backtest Lab.
- FastAPI `POST /api/grid-search` wraps single-asset parameter sweeps, heatmap data, and deterministic robustness analysis.
- FastAPI `POST /api/walk-forward` wraps rolling train/test validation using grid-search-selected parameters per fold.
- FastAPI `POST /api/ai/strategy-draft` wraps the AI Strategy Builder provider factory and returns validated structured drafts. The fake provider is the default; real providers are server-side opt-in.
- FastAPI `POST /api/ai/compile` compiles validated drafts into existing API-compatible request payloads without running them.
- FastAPI `POST /api/ai/research-plan` exposes the Research Copilot draft-and-compile path and stops before workflow execution.
- FastAPI `POST /api/ai/research-approve` resumes a prior response state and executes at most one existing workflow when approval matches the compiled target mode.
- `backtester/agents/research_graph.py` wires the research workflow with LangGraph when the backend dependency is installed. Importing the package does not require LangGraph; direct graph construction without it raises a sanitized dependency error, while the high-level runner can still use the same local state transitions for deterministic tests.
- `backtester/agents/nodes.py` reuses the existing AI provider, draft validator, compiler, and API service wrappers. It never runs a compiled payload until an explicit matching `approved_action` is present.
- `backtester/agents/tools.py` revalidates approved payload JSON with the existing API request schemas, runs only the matching service method, and reports malformed payload errors without including raw payload values.
- Frontend `frontend/lib/api.ts` isolates API calls from UI components.
- Frontend `frontend/lib/validation.ts` performs inline form validation before POST requests.

## Data Flow

### Single-Asset Python Backtest

1. `DataLoader` fetches and validates OHLCV data.
2. `BacktestEngine` initializes `Portfolio` and reads the open/close execution arrays.
3. For each bar, the engine gives the strategy a copied history ending at that bar for feature precomputation and `generate_signal`; future rows are structurally unavailable.
4. The engine records a `Decision` at the close and converts actionable signals into linked submitted `Order`s. If an open position breaches a configured stop-loss, take-profit, or trailing stop at the close, the decision becomes a SELL and records the exit reason.
5. Under the default `CLOSE_SIGNAL_NEXT_OPEN` policy, an order fills at the next available bar's open. The explicit `SAME_CLOSE` policy exists for assumption comparisons and is not the default.
6. The engine records immutable order status events and linked `Fill`s; an order submitted on the final bar expires rather than filling without a later bar. A buy that a price gap makes unaffordable is clipped to available cash, and the fill event records the reduction.
   When `evaluation_start` is set, earlier bars only warm up indicators: they produce no orders and no equity points.
7. `Portfolio` applies accepted fills and records post-fill equity valued at the current close.
8. Engine returns `BacktestResult`, including decisions, orders, fills, status events, and the compatibility trade ledger.
9. Metrics, charts, CLI, API, or frontend consume the result.

### Browser To API To Engine

1. Backtest Lab loads health status from `GET /health`.
2. Backtest Lab loads strategy metadata from `GET /api/strategies`; local fallback metadata keeps the form renderable if the API is offline.
3. User edits the single-asset config in the right-side form.
4. Frontend validates the request shape and strategy parameters inline.
5. Browser submits `BacktestRequest` to `POST /api/backtest`.
6. `backtester/api/services.py` builds `BacktestConfig` and the selected strategy.
7. Existing Python engine and metrics run server-side.
8. API returns:
   - Submitted config
   - Summary metrics
   - Equity series
   - Optional benchmark series
   - Drawdown series
   - Price series
   - Executed trades
   - Decisions, submitted orders, fills, and order status events
9. Frontend renders KPI cards, Recharts equity/drawdown charts, result tabs, trades, metrics, and parameters.

### Natural-Language Strategy Draft And Compile Flow

1. A client submits a prompt to `POST /api/ai/strategy-draft`.
2. The API calls `get_strategy_draft_provider()`, which selects the deterministic fake provider by default or an opt-in server-side OpenAI-compatible provider from backend environment variables.
3. The provider returns a constrained draft describing a single-run, grid-search, walk-forward, or unspecified target. Real-provider responses are parsed as JSON and checked for raw code-looking output.
4. A limited normalization step repairs only deterministic schema-adjacent mistakes before validation: simple boolean strings for `benchmark`, clear `equity_sizing` objects into `position_size_method`/`position_size_value`, and clean `rule_spec.conditions` references into the existing `rule_spec.rules` DSL.
5. `StrategyDraft` Pydantic validation remains the strict boundary. Unexpected fields, ambiguous sizing, malformed rule specs, unsupported indicators/operators, and extra provider output are rejected with sanitized validation errors.
6. `backtester/ai/validator.py` checks semantic safety: ticker readiness, ISO dates, date order, supported strategy kind, positive windows, momentum window ordering, mean-reversion bands, unsupported concepts, and raw-code fields.
7. The API returns structured JSON containing the draft, status, warnings, unsupported items, and validation errors.
8. A reviewed draft can be submitted to `POST /api/ai/compile`.
9. `backtester/ai/compiler.py` maps the draft into an existing `BacktestRequest`, `GridSearchRequest`, or `WalkForwardRequest` payload.
10. Rule-based drafts compile to a single-run `BacktestRequest` with a strict `rule_spec`; built-in momentum and mean-reversion drafts can also compile to research workflows.
11. Missing research grids, date ranges, optimization metrics, and walk-forward windows use deterministic defaults with warnings.
12. The compiled payload is not executed. Clients must submit it to the existing workflow endpoints if they choose to run it.

### Rule-Based Strategy DSL Flow

1. Natural-language rule prompts are converted into `RuleBasedStrategySpec`, not Python code.
2. The spec contains only enum-backed indicators and operators:
   - indicators: `close`, `sma`, `ema`, `rsi`, `rolling_high`, `rolling_low`, `bollinger_upper`, `bollinger_lower`, and constant `value`
   - operators: `>`, `<`, `>=`, `<=`, `crosses_above`, `crosses_below`
3. API schemas validate the nested `rule_spec` with `extra="forbid"` before strategy construction. AI provider normalization may translate one narrow indicator/conditions shape into this DSL, but only when every condition validates and no unused or unsupported indicators remain.
4. `backtester/api/services.py` builds `RuleBasedStrategy` server-side from the structured spec.
5. `RuleBasedStrategy.precompute(data)` calculates indicator arrays from Pandas/NumPy only.
6. `generate_signal(data, current_index)` reads only current and previous indicator values. Entry conditions use ALL logic; exit conditions use ANY logic.
7. The engine remains strategy-agnostic and continues to receive only `Signal.BUY`, `Signal.SELL`, or `Signal.HOLD`.

### Browser AI Builder Flow

1. User switches Backtest Lab into AI Builder mode.
2. Frontend collects a natural-language prompt and submits it to `POST /api/ai/strategy-draft`.
3. The browser renders the returned draft as an auditable strategy card: target mode, ticker/date range, strategy kind, parameters, sizing, costs, benchmark, assumptions, warnings, unsupported items, validation errors, and readiness status.
4. User can inspect secondary reproducibility JSON for the original prompt, validated draft, and latest compiled payload.
5. When the user chooses to load the draft, frontend calls `POST /api/ai/compile`.
6. The compile response payload is copied into the existing Single Run, Grid Search, or Walk-Forward form based on `target_mode`.
7. The workflow form is shown for review. Backtest Lab does not execute the loaded request until the user runs the existing workflow.

### Browser Research Copilot Flow

1. User switches Backtest Lab into Research Copilot mode.
2. Frontend collects a natural-language research goal and submits it to `POST /api/ai/research-plan`.
3. The browser renders the returned graph state: status, target mode, step timeline, audit log, draft summary, compiled payload preview, warnings, unsupported items, validation errors, and recommendation.
4. The plan response stops before execution. Backtest Lab does not call `research-approve` automatically.
5. When a ready compiled payload is present, the user may load it into the existing Single Run, Grid Search, or Walk-Forward form for manual review. Loading does not run the workflow.
6. If the user clicks the explicit approval button, frontend sends the previous response state plus the matching `approved_action` to `POST /api/ai/research-approve`.
7. The backend runs at most one existing workflow and returns an updated state containing workflow result summary, deterministic analysis, and recommended next step.
8. Frontend displays that analysis as server-provided research commentary. It does not compute backtest metrics, grid-search rankings, walk-forward folds, or portfolio accounting in TypeScript.

### Backend Research Copilot Graph Flow

1. A backend caller, or `POST /api/ai/research-plan`, creates a `ResearchGraphState` with a `user_goal`.
2. The graph records `interpret_research_goal`, then calls the existing AI draft provider path to create an inert `StrategyDraft`.
3. The draft passes through `backtester/ai/validator.py`, preserving warnings, unsupported concepts, and validation errors in state.
4. The compiler maps ready drafts into one existing API request payload: single run, grid search, or walk-forward.
5. The graph stops at `await_user_approval` with `approval_required=true` when a compiled payload is ready and no explicit approval is present. The plan endpoint returns sanitized state and never runs `backtest`, `grid-search`, or `walk-forward`.
6. `POST /api/ai/research-approve` accepts the prior response state plus `approved_action`, then sets exactly one matching action: `run_backtest`, `run_grid_search`, or `run_walk_forward`.
7. Mismatched approval is recorded as a validation error and no workflow is run.
8. Approved execution uses thin wrappers around existing API service functions only, refuses already-executed response states, revalidates the browser-returned compiled payload against the target request schema, and does not create server-side sessions.
9. Malformed or tampered approval payloads return sanitized field-level validation messages and clear the compiled payload from the response so raw browser-supplied values are not echoed back.
10. There are no filesystem, shell, generated-code, broker, live-trading, auth, database, or persistence tools.
11. Result analysis is deterministic and heuristic. It summarizes high drawdown, sparse trades, failed grid combinations, benchmark underperformance where available, and walk-forward degradation. It is transparent research commentary, not prediction.

### Browser Grid Search Flow

1. User switches Backtest Lab into Grid Search mode.
2. Frontend validates ticker/date range, base portfolio settings, optimization metric, and strategy parameter ranges for UX.
3. Browser submits `GridSearchRequest` to `POST /api/grid-search`.
4. `backtester/api/services.py` builds a base `BacktestConfig`, strategy factory, and parameter grid.
5. `backtester/research/run_grid_search()` expands combinations and runs the Python engine for each one.
6. The service converts the result frame into ranked JSON rows, failed-combination rows, best parameters, heatmap points when two numeric parameters vary, and deterministic robustness warnings.
7. Frontend renders the leaderboard, heatmap, robustness panel, failed combinations, exports, and a "Run selected config" action.

### Browser Walk-Forward Flow

1. User switches Backtest Lab into Walk-Forward mode.
2. Frontend validates base config, parameter grid, optimization metric, and train/test/step bar windows.
3. Browser submits `WalkForwardRequest` to `POST /api/walk-forward`.
4. The API fetches the full single-asset price window once and slices train/test folds server-side.
5. Each train fold runs grid search; the best train parameters are then evaluated on the following out-of-sample test fold. The test run starts at the train window so indicators are warm, but `evaluation_start` confines trading and scoring to the test window.
6. The service returns selected parameters, train/test metrics, degradation ratios, fold warnings, aggregate averages, parameter stability, and overall warnings.
7. Frontend renders a table-first validation view. It does not optimize, rank, or compute metrics in TypeScript.

### Multi-Asset Python Flow

1. Engine fetches each ticker independently.
2. DataFrames align on the intersection of dates available for all tickers.
3. Strategy returns ticker-to-signal mappings.
4. Orders execute in config ticker order.
5. Equity is recorded once per shared timestamp using all current prices.

Multi-asset support exists in Python. It is not currently exposed by FastAPI, CLI, or Backtest Lab.

## API Contract

FastAPI app: `backtester/api/main.py`

- `GET /health`
  - Response: `{ "status": "ok" }`.
- `GET /api/strategies`
  - Returns supported strategy ids, descriptions, and parameter metadata.
- `POST /api/backtest`
  - Request schema:
    - `ticker`
    - `start_date`
    - `end_date`
    - `strategy`
    - `initial_cash`
    - `commission_rate`
    - `slippage_bps`
    - `execution_policy` (`CLOSE_SIGNAL_NEXT_OPEN` by default, or explicit `SAME_CLOSE`)
    - `position_size_method`
    - `position_size_value`
    - optional `stop_loss_pct`, `take_profit_pct`, `trailing_stop_pct` as fractions between 0 and 1
    - `benchmark`
    - `parameters`
    - optional `rule_spec` for `strategy="rule_based"`
  - Response schema:
    - `config`
    - `summary`
    - `series.equity`
    - `series.benchmark`
    - `series.drawdown`
    - `series.price`
    - `trades`
    - `decisions`
    - `orders`
    - `fills`
    - `order_events`
    - `risk`
- `POST /api/grid-search`
  - Request schema:
    - base single-asset config fields
    - `strategy`
    - `parameter_grid`
    - `optimization_metric`
    - `max_results`
  - Response schema:
    - `config`
    - `strategy_id`
    - `strategy_name`
    - `optimization_metric`
    - `total_combinations`
    - `results`
    - `failed_combinations`
    - `best_parameters`
    - `best_row`
    - `heatmap`
    - `analysis`
- `POST /api/walk-forward`
  - Request schema:
    - base single-asset config fields
    - `strategy`
    - `parameter_grid`
    - `optimization_metric`
    - `train_window_bars`
    - `test_window_bars`
    - `step_bars`
  - Response schema:
    - `config`
    - `folds`
    - `summary`
- `POST /api/ai/strategy-draft`
  - Request schema:
    - `prompt`
    - optional `provider`, `model`, and `current_config` placeholders for future compatibility
  - Response schema:
    - `draft`
    - `status`
    - `warnings`
    - `unsupported`
    - `validation_errors`
- `POST /api/ai/compile`
  - Request schema:
    - `draft`, or a bare StrategyDraft-shaped body
  - Response schema:
    - `target_mode`
    - `status`
    - `payload`
    - `assumptions`
    - `warnings`
    - `unsupported`
    - `validation_errors`
- `POST /api/ai/research-plan`
  - Request schema:
    - `user_goal`
    - optional `current_config`
    - optional `context`
  - Response schema:
    - `session_id`
    - `user_goal`
    - `status`
    - `current_step`
    - `target_mode`
    - `steps`
    - `draft`
    - `compile_response`
    - `compile_payload`
    - `approval_required`
    - `approved_action`
    - `workflow_result`
    - `analysis`
    - `recommendation`
    - `warnings`
    - `unsupported`
    - `validation_errors`
    - `audit_log`
- `POST /api/ai/research-approve`
  - Request schema:
    - `state`: prior `ResearchGraphResponse`
    - `approved_action`: `run_backtest`, `run_grid_search`, or `run_walk_forward`
  - Response schema:
    - same sanitized `ResearchGraphResponse` shape as `research-plan`

The API normalizes ticker case and validates strategy parameters with Pydantic.

## Frontend Architecture

Backtest Lab uses Next.js App Router with client-side state in `frontend/app/page.tsx`.

Main component groups:

- `AppShell`, `Sidebar`, `TopBar`
  - Full-screen application frame and run context.
- `BacktestForm`, `GridSearchForm`, `WalkForwardForm`
  - Controlled right-side configuration panels for single-run and research workflows.
- `ai-builder/*`
  - Natural-language prompt panel, prompt templates, generated strategy preview, assumptions/warnings display, compile handoff, and reproducibility JSON.
- `research-copilot/*`
  - Natural-language research goal panel, graph step timeline, payload preview, explicit approval card, workflow summary, deterministic analysis, warnings/errors display, and safe load-into-form handoff.
- `ResultsDashboard`
  - Run hero, KPI cards, chart stack, and tab orchestration.
- `GridSearchResults`, `WalkForwardResults`
  - Research result views for leaderboard, heatmap, robustness warnings, fold tables, and export actions.
- `EquityChart`, `DrawdownChart`
  - Recharts charts with dark financial styling and custom tooltips.
- `ResultsTabs`, `TradeTable`
  - Summary, trades, metrics, richer risk analytics, exports, and parameters views.
- `EmptyState`, `LoadingSkeleton`, `ErrorState`
  - Non-happy-path dashboard states.
- `formatters`
  - Shared currency, percent, number, decimal, and date formatting.

The design system lives mostly in Tailwind classes plus `frontend/app/globals.css` CSS variables. Numeric values use a mono font stack through `font-mono-finance`.

## External Services And APIs

- yfinance is used for historical market data.
- FastAPI serves the local API.
- The Next.js frontend calls `NEXT_PUBLIC_API_URL`, defaulting to `http://localhost:8000`.
- No database, auth provider, broker API, payment system, paid data feed, or live trading integration is present.
- The AI Strategy Builder uses a deterministic fake provider by default. Optional real provider support uses server-side OpenAI-compatible chat completion calls or a LangChain structured-output adapter only when `BACKTESTER_AI_PROVIDER` and server-side credentials are configured.
- OpenRouter is supported as a first-class backend AI provider with `BACKTESTER_AI_PROVIDER=openrouter`. It calls `POST https://openrouter.ai/api/v1/chat/completions` by default, uses bearer auth from `BACKTESTER_AI_API_KEY`, defaults to `tencent/hy3-preview:free`, and can send backend-only attribution headers from `BACKTESTER_AI_APP_NAME` and `BACKTESTER_AI_APP_URL`.
- LangChain is supported as an optional backend provider with `BACKTESTER_AI_PROVIDER=langchain_openai_compatible`. It reuses `BACKTESTER_AI_MODEL`, `BACKTESTER_AI_API_KEY`, `BACKTESTER_AI_BASE_URL`, and `BACKTESTER_AI_TIMEOUT_SECONDS`, requires the optional `langchain-openai` dependency, invokes `ChatOpenAI.with_structured_output(StrategyDraft)`, and still returns through the existing normalization and validation boundary.

## Configuration And Environment

- Python dependencies are in `requirements.txt` and `pyproject.toml`; optional LangChain provider dependencies are in the `ai-langchain` extra and `requirements-ai-langchain.txt`.
- LangGraph powers the backend-only Research Copilot graph and is listed with backend Python dependencies. The graph module imports it lazily; missing installations do not affect the rest of the backend, and direct graph construction reports a sanitized dependency error.
- Tests are configured in `pyproject.toml` with `testpaths = ["tests"]`.
- Mypy is configured strict for Python 3.12 in `pyproject.toml`.
- Frontend dependencies and scripts are in `frontend/package.json`.
- Frontend optional env file: `frontend/.env.local`, based on `frontend/.env.example`.
- API CORS currently allows:
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
- Additional API CORS origins can be configured with comma-separated `BACKTESTER_CORS_ORIGINS`.
- AI Builder backend env vars:
  - `BACKTESTER_AI_ENABLED=true|false`
  - `BACKTESTER_AI_PROVIDER=fake|deepseek|openrouter|openai_compatible|langchain_openai_compatible`
  - `BACKTESTER_AI_MODEL`
  - `BACKTESTER_AI_API_KEY`
  - `BACKTESTER_AI_BASE_URL`
  - `BACKTESTER_AI_TIMEOUT_SECONDS`
  - `BACKTESTER_AI_APP_NAME`
  - `BACKTESTER_AI_APP_URL`
- OpenRouter defaults:
  - `BACKTESTER_AI_MODEL=tencent/hy3-preview:free`
  - `BACKTESTER_AI_BASE_URL=https://openrouter.ai/api/v1`
  - `BACKTESTER_AI_APP_NAME=Backtest Lab`
- AI provider keys are backend-only. The frontend receives draft statuses, warnings, unsupported items, and validation errors, never API keys.
- CI is `.github/workflows/ci.yml`; it installs Python requirements, runs `python -m pytest`, runs `python -m mypy backtester`, installs frontend dependencies with `npm ci`, audits shipped dependencies at high severity or above, runs `npm run lint`, runs `npm run typecheck`, and runs `npm run build`.

## Important Design Decisions

- No domain-specific backtesting or finance metrics libraries are used.
- Strategy precomputation and decision calls receive history bounded at `current_index`; future bars are structurally unavailable during a decision.
- Multi-asset backtests use inner-join date alignment for simplicity and predictable shared indexing.
- `Portfolio.execute_order()` returns `None` for rejected orders; rejection is normal simulation behavior. Engines clip gap-affected buys to available cash before calling it.
- Cash is rounded to cents after trades; production-grade accounting would likely use `Decimal`.
- Backtest Lab is deliberately a single-asset API client even though the Python engine supports multi-asset backtests.
- Frontend validation improves UX but does not replace API/Pydantic validation.
- Robustness scoring is transparent deterministic heuristics only. It flags sparse trades, severe drawdowns, failed combinations, benchmark underperformance, and concentrated parameter performance; it is not ML and not a guarantee of strategy quality.
- AI strategy drafts are never executable code. Real-provider output is treated as untrusted JSON, may pass through only limited deterministic normalization, and must pass Pydantic schema validation plus `validator.py`; unexpected fields, raw-code fields, unsupported indicators/operators, unsupported strategy kinds, broker execution, live trading, intraday minute bars, options flow, sentiment feeds, filesystem/code loading, and multi-asset portfolios are surfaced as unsupported or clarification-needed for the v1 builder. OpenRouter support does not change this flow: draft JSON is validated, compiled only into existing API request payloads, and never executed automatically.
- The Research Copilot graph preserves that same boundary. It can resume and run one existing workflow only after explicit matching approval. The API and frontend use request/response state passing only: no server-side session persistence, auth, database, broker integration, generated-code execution, or frontend API-key handling is added. Because the browser returns state to the approval endpoint, the backend treats the compiled payload as untrusted and validates it again before execution.
- Backtest Lab favors the existing stack: Next.js, TypeScript, Tailwind CSS, Recharts, and small local components instead of heavy UI libraries.
