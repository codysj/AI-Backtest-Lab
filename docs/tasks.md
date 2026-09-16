# Tasks

## Next

Full designs, acceptance criteria, and open decisions are in the [technical roadmap](technical-roadmap.md).

1. **Hosted live demo.** Per-ticker data cache, offline mode, Docker API deploy, Vercel frontend, request limits.
2. **Verified engine speedup.** Reference fixtures and simulator, read-only market view, incremental indicators, identical ledgers.
3. **Overfitting statistics.** Bootstrap Sharpe intervals, deflated Sharpe ratio, probability of backtest overfitting, locked holdout.
4. **Multi-asset portfolio research.** Allocators, rebalancing, union calendars, portfolio API and dashboard mode.
5. **Persisted research jobs.** SQLite-backed async runs with progress, idempotency, recovery, and replay.
6. **Polish bundle.** Playwright tests in CI, trade markers with exit reasons, dividend-aware returns.

## Decided

- The dashboard stays single-asset until item 4 lands.
- CI builds and audits the frontend on every push.
- Core tests use synthetic data. Examples and the CLI use yfinance with the local cache.
- Demo screenshots and the header GIF are committed. Regenerate them with `scripts/capture_demo_media.py`.
