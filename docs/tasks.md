# Tasks

## Next

1. **Reference fixtures.** Add hand-calculated cases with gaps, splits, and dividends, and a deliberately simple reference simulator to reconcile ledgers against.
2. **Read-only market view.** Replace the per-bar history copy with a bounded view so throughput stays flat as runs grow. Accept it only if ledgers still match the reference simulator.
3. **Dividend-aware returns.** Load adjusted closes or dividends and use them for both strategy and benchmark returns.
4. **Multi-asset in the API and dashboard.** First define shared-cash allocation, union calendars, and stale-price valuation, since the Python engine currently intersects calendars and fills in ticker order.
5. **Hosted demo.** Deploy the dashboard and API with a pre-seeded data cache and the offline AI provider, so no key or network access is needed.

## Decided

- The dashboard stays single-asset until item 4 lands.
- CI builds and audits the frontend on every push.
- Core tests use synthetic data. Examples and the CLI use yfinance with the local cache.
- Demo screenshots and the header GIF are committed. Regenerate them with `scripts/capture_demo_media.py`.
