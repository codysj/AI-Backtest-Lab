# AGENTS.md

Durable instructions for Codex and other coding agents working in this repo.

## Project Snapshot

- Backtester is a Python 3.12+ event-driven strategy backtesting engine with a FastAPI wrapper and a Next.js dashboard called Backtest Lab.
- Core Python package is in `backtester/`; frontend source is isolated in `frontend/`.
- The engine supports single-asset and multi-asset backtests, pluggable strategies, protective exits, portfolio simulation, metrics, grid search, walk-forward validation, charts, CLI, and API responses.
- Built-in strategies are defined once in `backtester/strategy/registry.py`. API validation, strategy metadata, CLI flags, research grids, and AI compilation read from it.
- FastAPI exposes health, strategy metadata, backtest, grid-search, walk-forward, AI draft/compile, and Research Copilot plan/approve endpoints.
- Backtest Lab is a single-asset research dashboard. Multi-asset support remains Python-side.
- The project intentionally avoids backtesting-specific libraries such as backtrader, zipline, quantstats, and empyrical.
- Core tests should remain deterministic and should not depend on live yfinance/network calls.

## Commands

Python setup:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate
python -m pip install -r requirements.txt
```

Create `.venv` locally and activate it before running validation. Never commit `.venv/`, `venv/`, or generated environment files.

Python validation:

```powershell
python -m pytest
python -m mypy backtester
python -m pytest --cov=backtester
```

Important:
- Do not run bare `pytest` or `mypy` commands.
- Always invoke them through `python -m ...` because PATH is not reliable in this environment.

API:

```bash
python -m uvicorn backtester.api.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
npm run lint
npm run typecheck
npm run build
```

Backtest Lab uses Next.js 15. Use a Node.js version compatible with Next's engine range: `^18.18.0`, `^19.8.0`, or `>=20.0.0`.

CLI/examples:

```bash
python -m backtester.cli --help
python -m backtester.cli run --ticker AAPL --strategy momentum --start 2020-01-01 --end 2023-12-31 --param fast_window=20 --benchmark
python -m backtester.cli grid-search --ticker AAPL --start 2020-01-01 --end 2023-12-31 --strategy donchian_breakout --grid entry_window=20,55
python examples/run_demo.py
python examples/grid_search_demo.py
python examples/multi_asset_demo.py
```

## Architecture Boundaries

- Keep `data`, `strategy`, `portfolio`, `metrics`, and `viz` independently testable.
- `engine` composes data, strategy, portfolio, and config.
- `api` composes schemas, service conversion, engine execution, and JSON responses.
- `frontend` is an API client and presentation layer. It must not reimplement backtesting, portfolio accounting, benchmark math, or performance metrics in TypeScript.
- Preserve public APIs unless the user explicitly asks for a breaking change.
- Prefer small, well-scoped changes over broad rewrites.

## Backend And API Conventions

- Keep strict typing for public Python functions/classes; `mypy backtester` should pass.
- Pydantic schemas in `backtester/api/schemas.py` are the API contract for Backtest Lab.
- `backtester/api/services.py` should convert API requests into engine configs and convert engine results back to JSON-friendly responses.
- Do not add auth, database persistence, live trading, broker integration, or paid data feeds unless explicitly requested.
- If API tests need data, use FastAPI `TestClient` and monkeypatch service/loader behavior to avoid network calls.
- yfinance-backed flows may be used in demos and manual local runs, but deterministic tests should use synthetic data or mocked yfinance/data loader behavior.

## Frontend Conventions

- Current stack: Next.js App Router, TypeScript, Tailwind CSS, Recharts, lucide-react.
- Avoid heavy UI libraries or state managers unless there is a clear, user-requested reason.
- Keep API calls isolated in `frontend/lib/api.ts`.
- Keep API request/response shapes typed in `frontend/lib/types.ts`.
- Use shared formatting helpers for currency, percentages, numbers, decimals, and dates.
- Keep validation user-friendly and inline; do not rely on `alert()`.
- Default `NEXT_PUBLIC_API_URL` behavior should remain `http://localhost:8000` unless explicitly changed.
- Backtest Lab should remain desktop-first but usable on smaller screens without horizontal overflow.
- Numbers in metric cards, tables, percentages, dates, and chart tooltips should use the finance mono font stack.
- Do not add fake multi-page workflows or unsupported multi-asset UI. Disabled or coming-soon affordances are fine when honest.

## Testing Expectations

- Add or update tests for behavior changes.
- For Python changes, run:
  - `python -m pytest`
  - `python -m mypy backtester`
- For frontend changes, run:
  - `cd frontend && npm run lint`
  - `cd frontend && npm run typecheck`
  - `cd frontend && npm run build`
- If a command fails because dependencies, PATH, network, or local services are unavailable, document that clearly in the handoff.

## Where To Look

- `README.md` for user-facing overview and run commands.
- `docs/architecture.md` for module map, data flow, and integration notes.
- `docs/current-state.md` for a one-page summary of what is implemented and known gaps.
- `docs/tasks.md` for prioritized next work.
- `docs/technical-roadmap.md` for the phased plan.
- `docs/decisions/` for architecture decision records.
- `frontend/README.md` for Backtest Lab-specific setup and component map.
- `backtester/api/` for API contract and service conversion.
- `frontend/app/`, `frontend/components/`, and `frontend/lib/` for dashboard implementation.

## Common Pitfalls

- Strategy decision calls receive a DataFrame history bounded at `current_index`; preserve this causal boundary when optimizing or introducing a market-view abstraction.
- Close-derived signals execute at the next available open by default. Same-close execution must remain an explicit opt-in assumption.
- Multi-asset engine aligns tickers on the intersection of available dates and processes signals in config ticker order.
- The web dashboard and FastAPI workflows are single-asset; multi-asset remains Python-side.
- To add a built-in strategy, add the class, add a registry entry, and extend the `StrategyId` literals in `backtester/api/schemas.py` and `frontend/lib/types.ts`. A test fails if the Python literal drifts from the registry.
- Walk-forward test folds warm indicators with `BacktestConfig.evaluation_start`; keep scoring confined to the test window.
- The frontend must call the API and render returned data; do not duplicate metrics or engine behavior in TypeScript.
- yfinance calls may require network unless data is cached.
- API CORS defaults to localhost/127.0.0.1 port 3000. Other frontend origins can be configured with `BACKTESTER_CORS_ORIGINS`.
- Generated files such as `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `frontend/node_modules/`, and `frontend/.next/` should not be committed.

## Handoff

At the end of a session, report:

- Files changed.
- Commands run and results.
- Tests or builds not run, with reasons.
- API assumptions made.
- Any known limitations or follow-up tasks added to `docs/tasks.md`.
