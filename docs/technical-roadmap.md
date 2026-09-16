# Technical Roadmap

The goal is fewer, stronger claims. Each buildout below makes one class of result more trustworthy or more visible, and ships with evidence a reviewer can rerun.

## Principle

A result should answer these questions without anyone reading the code:

1. What data was available when each decision was made?
2. When did each order fill, at what price, and why?
3. Which data, strategy version, and configuration produced the result?
4. Which other configurations were tried before this one was chosen?

## Completed

| Work | Evidence |
| --- | --- |
| Close-time decisions, next-open fills, bounded history, linked ledgers | [ADR](decisions/2026-09-16-close-signal-next-open-execution.md) and causality tests for every registered strategy |
| Strategy registry, RSI/Donchian/MACD, protective exits | [ADR](decisions/2026-09-16-strategy-registry.md) and `tests/test_strategy_expansion.py` |
| Warm-started walk-forward test folds, gap-aware cash clipping | Ledger-equivalence and clipping tests |

## Recommended order

| # | Buildout | Effort | What it proves |
| --- | --- | --- | --- |
| 1 | [Hosted live demo](#1-hosted-live-demo) | 1–2 days | Reviewers can use the product without cloning it |
| 2 | [Verified engine speedup](#2-verified-engine-speedup) | 3–4 days | Performance work that is measured and reconciled against a reference |
| 3 | [Overfitting statistics](#3-overfitting-statistics) | 3–5 days | Quantitative rigor about selection bias |
| 4 | [Multi-asset portfolio research](#4-multi-asset-portfolio-research) | 1–2 weeks | Portfolio construction, not just single-ticker signals |
| 5 | [Persisted research jobs](#5-persisted-research-jobs) | ~1 week | Backend systems design: async work, durability, replay |
| 6 | [Polish bundle](#6-polish-bundle) | 2–4 days | End-to-end tests, trade-level explainability, total returns |

Items 1–3 are about two weeks together and each yields a concrete resume line. After that, pick by target role: item 4 for quant roles, item 5 for backend roles.

---

## 1. Hosted live demo

### Why
Reviewers rarely clone portfolio repos. A working link is worth more than any single feature, and today the project only runs locally.

### Current state
- No Dockerfile or deployment configuration exists.
- `DataLoader` caches one Parquet file per exact `(ticker, start, end)` triple. Changing either date misses the cache and calls yfinance, which is slow and rate-limited from cloud hosts.
- The AI layer already defaults to a deterministic offline provider.
- CORS origins are configurable through `BACKTESTER_CORS_ORIGINS`, and the frontend reads `NEXT_PUBLIC_API_URL`.

### Design
- **Data.** Change the cache to one file per ticker covering its full history, and slice by date in memory. Add a seed script that downloads about ten liquid tickers such as SPY, QQQ, AAPL, MSFT, and NVDA from 2005 onward. Bake the files into the API image.
- **Offline mode.** Add `BACKTESTER_OFFLINE=1`. When set, the loader never calls yfinance and returns a clear error listing the available tickers and date range. The dashboard ticker field becomes a select in this mode, fed by a new `GET /api/universe` endpoint.
- **API hosting.** Add a slim Python Dockerfile running uvicorn. Deploy it to Fly.io or Render with one always-on instance, so the first visitor doesn't wait on a cold start.
- **Frontend hosting.** Deploy `frontend/` to Vercel with `NEXT_PUBLIC_API_URL` pointed at the API.
- **Abuse limits.** Cap grid combinations and walk-forward folds per request, cap the date span, and add a small in-memory per-IP rate limit middleware. Force the offline AI provider and ignore provider environment variables in the demo.
- **Smoke check.** Add a post-deploy script that calls `/health` and runs one small backtest against the public URL.

### Acceptance
- The README links to the live dashboard, and every workflow works there with no API key.
- The demo makes no outbound market-data calls, verified by running the API with network egress blocked.
- Existing tests pass with the per-ticker cache, and new tests cover slicing and offline errors.

### Decisions needed
- Hosting providers and accounts, custom domain, and monthly budget.
- The demo ticker universe and date range.

---

## 2. Verified engine speedup

### Why
Throughput is about 7,000 bars per second and falls as runs lengthen, per [benchmark results](benchmark_results.md). A reconciled speedup turns that weakness into a strong, quantified result, and it unblocks larger grids and multi-asset universes.

### Current state
- Each bar, `BacktestEngine.run()` copies `data.iloc[: i + 1]` and calls `strategy.precompute()` on the copy. Indicator work is O(i) per bar, so a run is O(n²).
- Strategies expose `precompute(data)` and `generate_signal(data, current_index)`.
- There is no independent implementation to reconcile ledgers against.

### Design
- **Reference fixtures.** Add small hand-calculated cases under `tests/fixtures/`, each an OHLCV CSV plus an expected ledger JSON with decisions, orders, fills, cash, and equity. Cover an open that gaps away from the prior close, a missing session, final-bar expiry, a stop-loss exit, cash clipping, and commission and slippage arithmetic.
- **Reference simulator.** Add `tests/reference/simulator.py`, a deliberately slow engine that uses plain Python loops and recomputes each indicator from the bounded prefix. It exists only to reconcile against.
- **Read-only market view.** Replace the per-bar copy with a `MarketView` that wraps the full NumPy column arrays and exposes only rows up to the current bar. Slicing returns non-writable NumPy views, so creating the view is O(1).
- **Incremental indicators.** Give built-in indicators O(1) update state: running sums for SMA, recursive EMA and Wilder smoothing, and monotonic deques for rolling highs and lows. Strategies update on each bar instead of recomputing the whole prefix.
- **Compatibility.** Keep the current DataFrame path as an adapter for user-written strategies, clearly documented as slower.
- **Profiling.** Publish before and after cProfile output with the benchmark.

### Acceptance
- For every registered strategy and every fixture, the fast engine, the current engine, and the reference simulator produce identical decision, order, and fill ledgers, with cash equal to the cent.
- Throughput stays roughly flat from 1,000 to 20,000 bars.
- `benchmark_results.md` reports hardware, Python version, bar counts, median of repeated runs, and the speedup against the current engine.

### Decisions needed
- Whether user-defined strategies must migrate to the incremental API or keep the adapter indefinitely.

---

## 3. Overfitting statistics

### Why
The README says the research workflows punish overfitting. Today that means heuristics and walk-forward. Standard statistics for multiple testing would make the claim rigorous, and they are the part quant interviewers probe hardest.

### Current state
- Grid search keeps summary metrics per combination but discards each combination's daily returns.
- Robustness analysis is a deterministic heuristic score.
- Nothing reports how many configurations were tried, and there is no untouched holdout.

### Design
- **Keep trial returns.** Store each combination's daily return series in the grid-search result. A 250-combination grid over 2,500 bars is about 5 MB of floats.
- **Bootstrap confidence intervals.** Compute a stationary block bootstrap of the best configuration's Sharpe ratio with a fixed seed and about 1,000 resamples. Report the 5th and 95th percentiles.
- **Deflated Sharpe ratio.** Implement the Bailey and López de Prado adjustment using the number of trials, the variance of Sharpe across trials, and the skew and kurtosis of the chosen series. Use `statistics.NormalDist` from the standard library, so no SciPy dependency is added.
- **Probability of backtest overfitting.** Implement combinatorially symmetric cross-validation over the trial return matrix. Split time into an even number of blocks, rank configurations in-sample, and measure how often the in-sample winner falls below the out-of-sample median.
- **Locked holdout.** Add an optional holdout fraction to grid search. The search runs only on the in-sample period, and the winner is evaluated once on the holdout. Both results are reported side by side.
- **Dashboard.** Add an overfitting panel to grid-search results with the deflated Sharpe probability, its confidence interval, the overfitting probability, the trial count, and the holdout comparison. Each statistic gets a one-line plain-language explanation.

### Acceptance
- On a grid of pure-noise strategies, the overfitting probability is near 0.5 and the deflated Sharpe is not significant.
- On a synthetic series with a planted edge, the overfitting probability is low and the deflated Sharpe is significant.
- Unit tests cover the deflated Sharpe and bootstrap against hand-computed small cases, and fixed seeds make results deterministic.
- `docs/architecture.md` documents each statistic with its formula and references.

### Decisions needed
- The default holdout fraction and whether the holdout is on by default.

---

## 4. Multi-asset portfolio research

### Why
Real strategies allocate across instruments. Exposing portfolio construction changes the project from a single-ticker signal tester into a portfolio research tool.

### Current state
- `MultiAssetBacktestEngine` exists in Python but not in the API, CLI, or dashboard.
- It aligns tickers on the intersection of their calendars, which silently drops dates when one asset is missing a bar.
- Signals are processed in config ticker order, so earlier tickers consume cash first.
- There is no notion of target weights or rebalancing.

### Design
- **Allocators.** Add an allocator interface that returns target weights on each rebalance date. Ship equal weight, inverse volatility, and top-k momentum rotation, defined in a registry like strategies.
- **Rebalancing.** Support monthly and weekly schedules plus an optional drift threshold. Convert target weights into orders at the decision close. Submit sells before buys, fill at the next open, and reuse gap-aware cash clipping.
- **Calendar.** Use the union of asset calendars. Value a missing bar at the last close and mark it stale. An order for an asset with no bar waits for its next available open or expires.
- **Analytics.** Report weights over time, per-asset return contribution, turnover, total costs, and a correlation matrix. Buy-and-hold of an equal-weight basket is the default benchmark.
- **API and CLI.** Add `POST /api/portfolio-backtest` and a `portfolio` CLI command.
- **Dashboard.** Add a Portfolio mode with a ticker multi-select, allocator and schedule controls, a stacked weights chart, a contribution table, and a correlation heatmap.

### Acceptance
- A hand-calculated two-asset fixture matches expected weights, orders, fills, and cash to the cent.
- Tests confirm sells settle before buys, weights never exceed full investment, and a halted asset is valued stale rather than dropping the date.
- Portfolio runs also pass through the verified engine from item 2 once that lands.

### Decisions needed
- Whether union-calendar semantics replace the current intersection behavior or live in a new engine.
- The maximum universe size for the API and the hosted demo.

---

## 5. Persisted research jobs

### Why
Research endpoints block until they finish, and nothing is saved. A 250-combination grid takes about 90 seconds in one request. Durable jobs make runs replayable and comparable, and they feed the trial count that item 3 needs across sessions.

### Current state
- `POST /api/grid-search` and `POST /api/walk-forward` run synchronously inside the request.
- Results exist only in the browser tab that requested them.
- There is no record of code version or input data behind a result.

### Design
- **Storage.** Use SQLite through the standard-library `sqlite3` module. A `runs` table stores id, kind, status, progress, config JSON, config hash, data fingerprint, git commit, timestamps, and error. A `trials` table stores run id, parameters, metrics, and optionally returns.
- **Execution.** Run jobs in a `concurrent.futures.ProcessPoolExecutor` inside the API process. No Redis or Celery. Trials commit as they complete, so progress is real.
- **Fingerprints.** Hash the input price data with `pandas.util.hash_pandas_object`. Hash the normalized config JSON with SHA-256.
- **Idempotency.** Submitting an identical config against identical data returns the existing completed run.
- **Recovery.** On startup, runs left as running become interrupted. Resuming skips trials already stored.
- **Endpoints.** `POST /api/runs` returns 202 with an id. `GET /api/runs/{id}` returns status and progress, `GET /api/runs` lists history, and `POST /api/runs/{id}/cancel` cancels. Small requests may keep the synchronous endpoints.
- **Replay.** `POST /api/runs/{id}/replay` reruns with stored inputs and flags any metric difference.
- **Dashboard.** Add a run history panel, progress bars that poll status, and a side-by-side comparison of two runs.

### Acceptance
- Tests cover idempotent resubmission, cancellation, recovery after killing the worker mid-run, and replay producing identical metrics.
- Every stored result shows its data fingerprint, config hash, and commit.

### Decisions needed
- Whether the hosted demo persists runs or resets on each deploy.
- Retention limits for stored trial returns.

---

## 6. Polish bundle

Three smaller items that are cheap together and remove visible rough edges.

### End-to-end tests in CI
- **Current state.** `scripts/capture_demo_media.py` already drives every dashboard workflow, but only manually against live data.
- **Design.** Turn those flows into Playwright tests with assertions on visible results. Serve deterministic data by pointing the loader at small committed Parquet fixtures through a data-directory environment variable. Add a CI job that builds the frontend, starts both servers, installs Chromium, and runs the tests. Upload screenshots as artifacts on failure.
- **Acceptance.** Each workflow asserts a 200 response and its key result text. The job runs on every pull request without network access to market data.

### Trade markers and exit reasons
- **Current state.** The API returns a price series, but the dashboard has no price chart. Exit reasons exist on decisions, but trades carry no link to the order or decision behind them.
- **Design.** Join fills to orders to decisions in the API service, and add `order_id` and `reason` to each trade. Add a price chart with buy and sell markers. Add an exit-reason column to the trades table so stop-loss and trailing-stop exits are visible.
- **Acceptance.** A service test confirms a stop-loss trade carries its reason. The chart renders markers on the correct dates.

### Dividend-aware returns
- **Current state.** The loader requests unadjusted data and keeps only split-adjusted OHLCV, so dividends are ignored for both the strategy and the benchmark.
- **Design.** Load dividend events alongside prices. Keep signals on split-adjusted closes, and credit dividends as cash on the ex-date for shares held. Build the buy-and-hold benchmark the same way. Version the cache format so old files are rebuilt.
- **Acceptance.** A fixture with a dividend reconciles cash exactly. The README limitation about dividends is removed.

---

## Non-goals

- Live trading, broker integration, or order routing.
- Intraday data or intrabar fill modeling.
- Letting AI output execute as code.
