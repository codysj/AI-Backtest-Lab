# Close-Time Decisions Fill At The Next Open

Date: 2026-09-16

## Status

Accepted

## Context

The original engine turned a signal computed from bar `t`'s close into a fill at that same close. That is impossible in practice. By the time the close is known, the market is shut and nobody can still trade at that price. The error biases results optimistically, and it compounds in grid search, where the most look-ahead-sensitive parameters rank highest.

Strategies also received the full DataFrame plus a `current_index`. Nothing but convention stopped a strategy from reading bar `t + 1`.

## Decision

- A strategy decision at bar `t` sees only a copy of history ending at `t`. Later rows do not exist in the object it receives.
- An actionable decision creates an order at `t`. Under the default `CLOSE_SIGNAL_NEXT_OPEN` policy, the order fills at bar `t + 1`'s open, with slippage and commission applied.
- An order submitted on the final bar expires rather than filling.
- `SAME_CLOSE` remains available as an explicit opt-in for measuring how much the optimistic assumption flatters a strategy.
- Each run returns separate ledgers of decisions, orders, fills, and order events, linked by id.
- Protective exits follow the same path. A stop is evaluated on the completed close and submits a normal SELL order.
- Buys are sized at the decision close. If a gap at the open makes the order unaffordable, the fill is clipped to available cash and the event records why.

## Consequences

- Reported returns no longer include a fill that could not have happened. Every trade can be traced to the bar that produced it.
- Look-ahead is prevented structurally, not by convention. A test runs every registered strategy on truncated and full histories and requires identical decisions.
- Copying history each bar costs throughput and grows with run length. See [benchmark results](../benchmark_results.md). A read-only market view could remove the copy without weakening the guarantee.
- Stops cannot fill intrabar. Daily bars do not say whether the high or low printed first, so modeling an intrabar fill would be guesswork.
