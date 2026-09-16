# Technical Roadmap: From Backtest Demo to Reproducible Research System

## Purpose

This roadmap turns the current application into a defensible research system and a stronger portfolio project. The goal is not to add the most features. It is to make a smaller set of claims that can be demonstrated with fixtures, replayed artifacts, API workflows, and measured engineering results.

The six proposed workstreams are intentionally ordered. Execution timing is first because every later result depends on it. Reproducibility and data semantics follow because they define what a saved result means. Experiment tracking, portfolio research, and optimization should build on those stable contracts rather than preserve today's assumptions by accident.

## Current Baseline and Important Gaps

The existing repository is a useful foundation:

- The Python engine, portfolio, strategy, metrics, research, API, and frontend layers are separated.
- Single-asset research is available end to end; multi-asset execution exists in Python.
- Grid search preserves failed combinations, and walk-forward evaluation reports out-of-sample folds.
- Synthetic tests and benchmark scripts already support offline validation.

However, the current engine creates a signal from bar `t`, creates an order immediately, and fills it at the same bar's close. Strategies receive the complete DataFrame and are trusted to respect `current_index`. Multi-asset data is reduced to the intersection of all calendars and orders compete for cash in ticker order. yfinance is loaded with `auto_adjust=False`, but adjusted close, dividends, and splits are discarded. Research endpoints execute synchronously and results are not persisted. These are the principal limits on the credibility of reported results.

## Product Principle: Every Result Must Be Explainable and Replayable

A completed research result should answer these questions without reading implementation code:

1. What information was available when each decision was made?
2. When was the order submitted, and at what price and time was it filled or rejected?
3. Which exact input data, strategy implementation, configuration, and random seed produced it?
4. Which other configurations were tried before this result was selected?
5. How were missing observations, corporate actions, cash, and portfolio constraints handled?
6. Can a clean worker reproduce the result, and can a simple reference implementation reconcile its trades?

The API and UI should expose these answers as first-class metadata rather than burying them in documentation.

## Delivery Order

| Phase | Outcome | Why it comes here | Suggested size |
| --- | --- | --- | --- |
| 0 | Golden fixtures and invariant harness | Creates an oracle before semantics change | 2–3 days |
| 1 | Explicit signal, order, and fill timing | Removes the largest source of optimistic bias | 1–2 weeks |
| 2 | Reproducible persisted research jobs | Makes results durable, replayable, and operable | 2–3 weeks |
| 3 | Corporate-action-aware data and accounting | Makes input prices and economic returns defensible | 1–2 weeks |
| 4 | Experiment registry and selection-bias controls | Makes repeated search visible and interpretable | 2 weeks |
| 5 | Multi-asset API and portfolio workspace | Builds a useful workflow on stable accounting | 2–3 weeks |
| 6 | Reconciled performance optimization | Produces an attributable SWE performance result | 1–2 weeks |

Time ranges are implementation estimates, not commitments. Each phase should be mergeable and demonstrable independently.

## Phase 0 — Establish Reference Cases Before Refactoring

### Scope

- Add tiny, human-auditable OHLCV fixtures with deliberately different opens and closes, gaps, missing sessions, a split, and a cash dividend.
- Add a deliberately slow reference simulator used only by tests and benchmarks. It should favor clarity: bounded DataFrame slices, explicit next-bar fills, no precomputation tricks, and a ledger of cash mutations.
- Define comparison tolerances for prices, cash, returns, and risk metrics. Money should reconcile to the cent under the chosen rounding policy; ratios may use documented floating-point tolerances.
- Snapshot expected signals, submitted orders, fills, positions, cash, equity, and rejection reasons—not only final return.

### Exit evidence

- At least three hand-calculated single-asset cases and two multi-asset accounting cases.
- A machine-readable `reference_cases` artifact that can be run in CI.
- An invariant suite covering no negative cash, no unowned share sales, cash-plus-holdings equality, deterministic event ordering, and stable reruns.

This harness prevents the later timing and data refactors from turning into unreviewable output changes.

## Phase 1 — Make Information Timing and Execution Explicit

### Contract design

Replace the implicit `Signal -> same-bar close Trade` path with explicit events:

- `Decision`: strategy output with `decision_time`, `information_cutoff`, ticker, desired action or target, and strategy reason.
- `Order`: immutable submission record with a unique id, decision id, `submitted_at`, order type, time-in-force, requested quantity, and status.
- `Fill`: immutable execution record with order id, `filled_at`, reference price field, actual price, quantity, commission, and slippage.
- `OrderEvent` or status history: submitted, accepted, partially filled if supported later, filled, cancelled, expired, or rejected with a structured reason.

Keep the first implementation intentionally narrow: market orders, whole shares, next-available-open execution, and no partial fills. Rich order types can wait until a use case requires them.

### Default timing semantics

Use an explicit default named something like `close_signal_next_open`:

1. Strategy observes data through bar `t` close.
2. It emits a decision whose information cutoff is `t` close.
3. The engine submits the derived order after that cutoff.
4. The order fills at the next available bar's open, with configured slippage and commission.
5. Sizing must use information available at submission. If quantity depends on execution price, document whether it uses the known reference price conservatively or is calculated at fill time.
6. Equity at each timestamp must state whether it is pre-fill or post-fill and which valuation price is used.

Do not silently fill an order when there is no later bar. Mark it expired at end of simulation. Do not call this event-driven if signals, submissions, and fills are still collapsed into one loop operation.

An optional `same_close` policy may exist only as an explicitly selected comparison mode with a warning explaining its same-bar assumption. The API response, exports, UI result header, and job provenance must carry the execution policy.

### Enforce bounded history structurally

Documentation alone is insufficient. Introduce a read-only `MarketView`/`StrategyContext` that exposes:

- current timestamp and positional index;
- current and prior bars only;
- trailing windows that cannot cross the information cutoff;
- precomputed causal features keyed to the cutoff;
- portfolio state as of the decision time.

Strategies should no longer receive the full DataFrame in the public decision method. During migration, provide an adapter for built-ins and deprecate the old interface rather than breaking every public strategy immediately. Precomputation may still operate on complete arrays for speed, but decision code must receive a view that cannot index future observations. Any feature implementation must prove causality independently.

### Tests that matter

- **Future mutation property:** mutate, append, or delete all bars after cutoff `t`; decisions and orders through `t` must remain byte-for-byte equivalent.
- **Gap case:** a close signal before a large overnight gap fills at the next open, not the signal close.
- **Last-bar case:** a final-bar decision creates an expired order and no trade.
- **Warm-up case:** indicator history is bounded and insufficient history results in `HOLD` without peeking.
- **Audit case:** every fill links to one submitted order and every order links to one decision.
- **Multi-calendar case:** “next available” is defined per asset/calendar, not by array position alone.
- **Reference comparison:** show at least one scenario where same-close and next-open returns materially differ, and explain why.

### Portfolio/resume value

Publish an execution-semantics diagram, one annotated ledger, and a before/after reference case in the README. This demonstrates market-microstructure awareness, API design, invariants, and avoidance of look-ahead bias—not merely another indicator.

## Phase 2 — Build Durable, Reproducible Research Jobs

### Architecture

Add a small job subsystem behind the existing synchronous service functions:

- FastAPI is the control plane: create, inspect, list, cancel, and replay jobs.
- A worker claims queued jobs, writes heartbeats and progress, and invokes the existing engine/research services.
- SQLite is a credible local/demo default. Use explicit transactions, schema migrations, uniqueness constraints, and a lease/heartbeat claim protocol. Keep repository interfaces narrow enough to adopt PostgreSQL later without pretending both are already supported.
- Store large result payloads and canonical input snapshots as content-addressed artifacts on disk; store their hashes and locations transactionally in the database. Do not put an unbounded equity curve in a queue row.

Avoid adding Redis/Celery solely for résumé keywords. A well-tested database-backed queue with leases, recovery, and idempotency is easier to run and more educational. Document that the first target is a single-host research service, not a distributed trading platform.

### Job model and API

Suggested states: `queued`, `running`, `cancel_requested`, `cancelled`, `succeeded`, and `failed`. State transitions must be validated and timestamped.

Suggested endpoints:

- `POST /api/research-jobs` with an `Idempotency-Key`.
- `GET /api/research-jobs/{job_id}` and paginated `GET /api/research-jobs`.
- `POST /api/research-jobs/{job_id}/cancel`.
- `POST /api/research-jobs/{job_id}/replay`.
- Optional Server-Sent Events for progress after polling works correctly.

Canonicalize requests before hashing. A uniqueness constraint on `(owner_scope, idempotency_key)` should return the original job for a duplicate submission, even if the first request timed out. Separately compute a `run_fingerprint` for equivalent research inputs; allow users to reuse a prior result or deliberately schedule another attempt.

Cancellation should be cooperative at safe checkpoints (between parameter combinations/folds and periodically during long simulations). Report completed and total work units. A cancellation request is not the same thing as confirmed cancellation.

### Provenance manifest

Every attempt should persist:

- canonical configuration and schema version;
- job, attempt, and parent/replay identifiers;
- raw-data artifact SHA-256 plus normalized-data fingerprint;
- data source, requested/actual range, symbols, adjustment policy, timezone/calendar, and retrieval timestamp;
- strategy id, semantic version, parameter values, and a source identifier such as Git commit plus dirty-tree flag;
- engine/package version and execution-policy version;
- random seeds and random number generator name, even when currently unused;
- Python/dependency/platform metadata;
- start/end timestamps, worker id, warnings, errors, and result artifact hashes.

Do not rely only on a Git SHA: built-in strategy behavior needs an explicit version that changes when its semantics change. Replays should consume the persisted normalized input artifact by default, not refetch mutable vendor history.

### Recovery and operability tests

- Kill a worker after it claims work; after the lease expires, a replacement resumes from the last durable checkpoint.
- Kill it while writing an artifact; the database must not point to a partial file.
- Submit the same idempotency key concurrently; exactly one logical job is created.
- Cancel queued and running sweeps and prove no later combinations start.
- Replay on a clean process and compare manifest, event ledger, result hashes, and metrics.
- Run a fixed workload with one and multiple workers; publish throughput, queue latency, and peak memory.

For sweep resumption, persist each trial as an independently committed unit. Never infer completion merely from a progress counter.

### UI slice

Add a Research Jobs view with status, progress, cancellation, retry/replay, provenance, warnings, and downloadable manifest/results. This is more valuable than a cosmetic dashboard refresh because it exposes real backend behavior.

## Phase 3 — Handle Corporate Actions and Historical Data Correctly

### Data contract first

Replace the ambiguous five-column frame with a versioned market-data bundle that retains:

- raw OHLCV;
- split ratio and cash dividend events;
- optional vendor-adjusted fields for reconciliation, not as an unexplained replacement;
- symbol, currency, exchange calendar/timezone, source, retrieval time, and adjustment mode;
- field-level availability/effective timestamps where the source supports them.

Supported modes should be explicit, for example:

- `raw_with_actions`: engine applies splits and dividends to holdings/cash;
- `split_adjusted_with_cash_dividends`: prices/volumes are consistently split-adjusted while dividends enter cash;
- `total_return_adjusted_analysis_only`: acceptable for comparison series, not mixed with separate dividend cash flows.

Reject incompatible combinations that would double-count an action. Cache keys and fingerprints must include the mode, schema version, source identity, and action data.

### Accounting policy

- On a split effective date, adjust share quantity and cost basis inversely to price so economic value is preserved before market movement. Define treatment of fractional shares; cash-in-lieu is preferable to silent rounding.
- On a dividend, credit eligible shares on the configured pay-date convention. Record an explicit cash-ledger event and state the simplifying assumption if the data source provides only ex-date information.
- Define benchmark treatment consistently with the strategy portfolio (price return versus total return).
- Do not forward-fill tradable OHLC bars across missing sessions. Distinguish “market closed,” “asset has no print,” and “missing vendor data.” A stale price may be used for valuation only under a declared policy and must not be executable.
- Record data as-of/retrieval metadata. True point-in-time fundamental data is out of scope until a source supplies revision history; say so plainly.

### Independent reference cases

- A 2-for-1 split leaves pre/post-action economic value unchanged before other movement.
- A reverse split exercises the fractional-share policy correctly.
- A cash dividend increases cash and total-return equity but not price-return equity.
- Split plus dividend is not double counted under any allowed adjustment mode.
- A hand-built ledger reconciles quantity, cost basis, cash, and total value at every event.
- Where licensing permits, compare a small result against a second source or published issuer action record and save the reconciliation—not mutable network output—as evidence.

### UI and docs

Display data source, adjustment mode, action counts, stale/missing observations, currency, and data fingerprint beside each result. Add a “Data & assumptions” export so reviewers can audit a result without opening code.

## Phase 4 — Account for Repeated Experimentation and False Discoveries

### Experiment hierarchy

Build on the job store with `Study -> Trial -> Evaluation` records:

- A study freezes its universe, data snapshot, objective, parameter search space, costs, split policy, and evaluation protocol before trials begin.
- Every attempted parameter set is registered before execution and retained whether it succeeds, fails, is cancelled, or performs poorly.
- Canonical parameter hashes prevent accidental duplicate trials while preserving deliberate reruns as new attempts.
- The trial counter used by selection-bias diagnostics includes unsuccessful and manually initiated variants when they belong to the same research question.

### Untouched final evaluation

Define chronological partitions explicitly:

1. development/training data for fitting or search;
2. validation/walk-forward data for selection and stability checks;
3. a locked final holdout used once for the nominated strategy.

The service should deny holdout access until a candidate is frozen. Unlocking creates an immutable event. Subsequent selection after viewing the holdout must create a new study whose former holdout is now considered observed; it must not keep the “untouched” badge.

### Diagnostics and honest reporting

- Report the number of attempted, completed, failed, and inspected trials.
- Show the distribution of outcomes, parameter stability, in-sample/out-of-sample degradation, turnover/cost sensitivity, and benchmark comparison—not only the winner.
- Add Deflated Sharpe Ratio only with its assumptions documented: non-normal return moments, sample length, number/correlation of trials, and expected maximum Sharpe estimate. Validate it against examples from Bailey and López de Prado, *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality* (Journal of Portfolio Management, 2014; DOI `10.3905/jpm.2014.40.5.094`).
- Prefer “insufficient evidence” over a green badge when sample size or trial history makes the statistic unreliable.
- Consider Probability of Backtest Overfitting or combinatorially symmetric cross-validation only after the registry and partition discipline are correct. A sophisticated statistic cannot repair missing experiment history.

### Demonstration

Ship one narrative case study: an attractive grid-search winner, its full trial distribution, walk-forward degradation, Deflated Sharpe interpretation, and locked-holdout result. Preserve the losing trials in the downloadable study bundle. This is stronger résumé evidence than presenting an isolated high Sharpe ratio.

## Phase 5 — Expose Multi-Asset Research with Portfolio Constraints

### Correct core semantics before UI

Replace intersection-only alignment and ticker-order cash allocation with an explicit portfolio clock and two-phase processing:

1. Build the decision snapshot for all assets at timestamp `t`.
2. Collect all intents without mutating cash.
3. Convert intents to target holdings/orders through a portfolio allocator.
4. Apply portfolio constraints consistently.
5. Execute eligible orders according to each asset's next tradable bar and the execution policy.
6. Value holdings under the documented stale-price policy.

This removes arbitrary dependence on ticker ordering. Preserve deterministic tie-breaking, but make it an implementation detail after allocation rather than a source of portfolio weights.

### First useful capability

- Long-only portfolios with target-weight or periodic rebalancing.
- Shared cash, commission, slippage, minimum cash reserve, maximum position weight, gross exposure cap, and optional turnover cap.
- Explicit trading calendar policy (`union` for the portfolio clock), per-asset tradability, last-known valuation age, and configurable stale-value limit.
- Portfolio and asset ledgers, allocation drift, turnover, concentration, and ex-post marginal/component risk contributions.

Do not claim full risk management from simplified volatility targeting. Label covariance estimator, lookback, annualization, and behavior with insufficient history. Reject cross-currency portfolios until FX conversion and currency cash ledgers exist, or constrain v1 to one currency.

### API/UI sequence

1. Add typed multi-asset schemas and `POST /api/portfolio-backtests` with deterministic service tests.
2. Return portfolio equity, cash, weights through time, per-asset prices/tradability, fills, rebalances, constraint violations, and risk contributions.
3. Add portfolio configuration to Backtest Lab only after the contract is stable.
4. Add a timeline/holdings view that makes unavailable prices, stale valuations, rejected orders, and allocation drift visible.
5. Add saved jobs/studies integration rather than a second ad hoc execution path.

### Acceptance cases

- Simultaneous targets are invariant to ticker request order.
- Shared cash and exposure constraints hold after every fill.
- Different holiday calendars do not create synthetic executable prices.
- Delisted/missing assets follow an explicit terminal policy and do not disappear from value silently.
- Portfolio replay reproduces orders, fills, cash, weights, and final equity exactly.
- API-to-browser end-to-end test renders the same provenance and accounting totals as Python.

## Phase 6 — Produce a Defensible Performance Improvement

### Benchmark contract

Do not optimize until the timing/event model is stable. Establish two implementations:

- `reference`: simple, readable, bounded-history simulator used as a correctness oracle;
- `optimized`: production engine with precomputation/vectorized data access and identical public semantics.

For each benchmark workload, compare decisions, order statuses, fills, cash ledger, positions, equity curve, and summary metrics before reporting speed. A speedup with different trades is not a speedup.

### Workloads

Use seeded synthetic data checked into or generated deterministically by the benchmark:

- single asset at 2.5K, 25K, and 250K bars;
- 10/50/250-asset portfolio workloads with staggered calendars;
- grid sweeps with enough trials to expose repeated data loading and indicator computation;
- action-heavy and sparse-calendar cases;
- cold process and warm-cache runs, reported separately.

### Measurement discipline

- Pin Python and dependency versions; record OS, CPU model/core count, RAM, Git commit, power mode, and worker count.
- Include warm-up, multiple samples, median plus dispersion, bars/sec or trials/sec, wall time, CPU time where practical, and peak RSS.
- Profile first. Attribute changes to measured hot paths such as duplicate loading, indicator recomputation, Python event overhead, or serialization.
- Compare one optimization at a time against a frozen baseline commit/tag.
- Keep network and frontend startup outside engine timing.
- Add a benchmark correctness gate to CI; keep long performance runs scheduled/manual to avoid noisy per-commit failures.

Likely candidates, subject to profiling, are loading each grid-search dataset once, sharing immutable data/features across trials, minimizing Python/Pandas work inside the bar loop, batching artifact serialization, and bounded parallel trial execution. Do not assume these are bottlenecks until profiles show them.

### Published evidence

Replace the current TODO baseline with a reproducible report containing commands, raw machine-readable samples, environment manifest, flame graph or profile table, memory, output reconciliation hashes, and limitations. A concise claim such as “2.8× median throughput on a 100-trial sweep with identical fill-ledger SHA-256” has substantially more value than “optimized backtester.”

## Cross-Cutting Engineering Work

### Versioning and migrations

- Version execution semantics, market-data schema, API schemas, result artifacts, and manifests independently.
- Add database migrations from the first persisted schema; never edit an already-released migration.
- Readers should either migrate old artifacts deterministically or reject them with a useful compatibility message.

### Determinism

- Canonicalize JSON key ordering, timestamps, enums, floating-point serialization, and symbol order before hashing.
- Inject clocks, id generators, and random generators in tests.
- Define which metadata is intentionally non-deterministic and exclude it from the core result hash.
- Never describe a rerun against freshly downloaded history as deterministic replay.

### Security and operational boundaries

- Treat job configurations, artifact paths, and imports as untrusted input. Never execute stored Python or accept arbitrary filesystem paths.
- Put caps on symbols, bars, grid combinations, artifact bytes, concurrent jobs, and runtime.
- Sanitize user-facing failures while preserving structured internal diagnostics.
- Keep live trading, broker integration, arbitrary generated code, and multi-tenant auth out of scope unless explicitly commissioned.

### CI layers

1. Fast unit/property tests for causal history, accounting, state transitions, hashes, and statistics.
2. Deterministic integration tests for API + worker + temporary database/artifact store.
3. Golden reference reconciliation tests.
4. Frontend lint/type/build and a small API-contract UI test.
5. Scheduled benchmark and replay-recovery jobs with retained artifacts.

## Portfolio Presentation and Resume Evidence

Create a single reproducible demonstration rather than six disconnected screenshots:

1. Submit a sweep and show idempotent duplicate handling.
2. Stream progress, kill the worker, and show lease-based recovery.
3. Inspect the winning result's data/strategy/execution manifest and fill ledger.
4. Show all attempted trials and the walk-forward/Deflated Sharpe interpretation.
5. Lock and run the holdout once.
6. Replay the job from its persisted input snapshot and compare hashes.
7. Run the same nominated strategy as a constrained multi-asset portfolio.
8. Show the reference-versus-optimized benchmark with identical outputs.

Recommended repository artifacts:

- one architecture decision record per consequential policy (timing, corporate actions, queue recovery, study/holdout rules, portfolio calendar);
- a versioned provenance-manifest example;
- hand-checked ledgers and golden fixtures;
- an operations/recovery demo script;
- a quantitative case-study notebook or static report generated from saved artifacts;
- machine-readable benchmark results plus a concise human report;
- a short architecture diagram and a 2–3 minute demo recording.

Resume bullets should state measured, reviewable outcomes. Examples once substantiated:

- “Designed a causal event model separating close-time decisions, order submission, and next-open fills; validated against mutation-based look-ahead tests and hand-reconciled ledgers.”
- “Built a SQLite-backed resumable research queue with idempotent submission, cooperative cancellation, lease recovery, and content-addressed experiment artifacts.”
- “Implemented corporate-action and portfolio accounting reference cases and deterministic replay using versioned SHA-256 provenance manifests.”
- “Measured an `N×` speedup over a reference simulator on a published workload while preserving signal, fill, cash, and equity reconciliation hashes.”

Do not use the numeric claims until the committed evidence supports them.

## Definition of Done for the Roadmap

The project has crossed from polished demo to defensible research system when:

- the default execution path cannot inspect future bars and does not fill close-derived decisions at that same close;
- all results expose execution, data, strategy, and environment provenance;
- jobs survive worker failure, support safe cancellation, and replay from immutable data;
- corporate actions reconcile through an explicit cash/position ledger;
- all trials, including failures, remain attached to a study with honest holdout history;
- portfolio results are invariant to ticker request order and disclose stale/unavailable data;
- a reference implementation agrees with the optimized engine on event and accounting outputs;
- the README demonstration can be reproduced offline from committed or generated deterministic fixtures.

## Deliberate Non-Goals

- Live trading, brokers, low-latency execution, order-book simulation, or claims of production trading readiness.
- Arbitrary Python generated by an LLM.
- A large distributed stack before single-host durability and recovery are proven.
- More indicators as a substitute for correctness, provenance, or research discipline.
- Point-in-time fundamentals without a data source that supplies revision history.
- Cross-currency portfolios before FX and currency-ledger semantics exist.
