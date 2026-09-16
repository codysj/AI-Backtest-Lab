# Current State

Updated 2026-09-16. For module-level detail, see [architecture.md](architecture.md).

## Implemented

- **Engine.** Single-asset and multi-asset event-driven engines with close-time decisions, next-open fills by default, and linked decision, order, fill, and order-event ledgers.
- **Strategies.** SMA crossover, Bollinger mean reversion, RSI reversion, Donchian breakout, and MACD crossover, defined in one registry.
- **Rule DSL.** Close, SMA, EMA, RSI, prior rolling high and low, Bollinger bands, and constants, with comparison and crossover operators.
- **Portfolio.** Commission, basis-point slippage, five sizing methods, and fills clipped to available cash after gaps.
- **Risk exits.** Stop-loss, take-profit, and trailing stop, evaluated at the close.
- **Metrics.** Returns, Sharpe, Sortino, alpha and beta, information ratio, drawdown and duration, VaR and CVaR, rolling metrics, and trade statistics.
- **Research.** Grid search with failed-combination capture, heatmaps, and robustness warnings. Walk-forward validation with warm-started test folds.
- **AI.** Natural-language drafts validated against strict schemas and compiled into API requests. A LangGraph Research Copilot with an approval gate and backend revalidation. The default provider is offline and deterministic.
- **Interfaces.** FastAPI, Next.js dashboard, CLI, and Python API.
- **Quality.** 234 pytest tests, strict mypy, frontend lint, typecheck, build, and a runtime dependency audit in CI.

## Known gaps

- Multi-asset runs are Python-only.
- Returns exclude dividends.
- Stops fill at the next open after a close breach, not intrabar.
- Per-bar history copies reduce throughput on long runs.
- No persistence, authentication, or deployment configuration.

The prioritized follow-ups are in [tasks.md](tasks.md).
