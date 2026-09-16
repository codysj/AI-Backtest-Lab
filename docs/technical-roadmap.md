# Technical Roadmap

The goal is fewer, stronger claims. Each phase makes one class of result more trustworthy and ships with evidence a reviewer can rerun.

## Principle

A result should answer these questions without anyone reading the code:

1. What data was available when each decision was made?
2. When did each order fill, at what price, and why?
3. Which data, strategy version, and configuration produced the result?
4. Which other configurations were tried before this one was chosen?

## Phases

| Phase | Outcome | Status |
| --- | --- | --- |
| 1. Execution timing | Close-time decisions, next-open fills, bounded history, linked ledgers | Done. See the [ADR](decisions/2026-09-16-close-signal-next-open-execution.md). |
| 2. Reference fixtures | Hand-calculated cases with gaps, splits, and dividends, plus a slow reference simulator for reconciling ledgers | Next |
| 3. Performance | Read-only market view. Publish speedup only when ledgers match the reference simulator exactly. | Planned |
| 4. Data semantics | Dividend-aware returns, split handling, and an explicit missing-bar policy | Planned |
| 5. Reproducible runs | Persisted jobs with data fingerprints, a config hash, and replay | Planned |
| 6. Selection-bias controls | Keep every trial, lock a final holdout, and report how many configurations were tried | Planned |
| 7. Multi-asset research | Shared-cash allocation and union calendars, then API and dashboard support | Planned |

## Non-goals

- Live trading, broker integration, or order routing.
- Intraday data or intrabar fill modeling.
- Letting AI output execute as code.
