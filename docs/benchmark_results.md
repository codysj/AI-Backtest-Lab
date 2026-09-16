# Benchmark Results

The benchmark runs offline on synthetic OHLCV data with `MomentumStrategy(10/50)`, zero costs, and $10,000 fixed-dollar sizing.

```bash
python benchmarks/benchmark_backtest.py --bars 2500
python benchmarks/profile_backtest.py
```

## Current engine

Measured 2026-09-16 on Windows 11, Python 3.12.10, AMD64 with 20 logical cores.

| Bars | Seconds | Bars per second |
| --- | --- | --- |
| 1,000 | 0.137 | 7,297 |
| 2,500 | 0.358 | 6,992 |
| 5,000 | 0.899 | 5,561 |

A 2,500-bar run covers about ten years of daily data. At under half a second per run, a 27-combination grid search over that period finishes in about ten seconds.

## Why throughput falls as runs get longer

Each bar, the engine copies history up to the current bar and hands the strategy that copy. This makes look-ahead structurally impossible, as described in the [execution-timing decision](decisions/2026-09-16-close-signal-next-open-execution.md). The copy grows with the bar index, so total work grows faster than linearly.

An earlier version passed the full DataFrame with an index and reached about 130,000 bars per second. It relied on strategies not reading future rows. That number is not comparable, because the fast version could not guarantee what the current one does.

## Next step

A read-only market view with a bounded length would drop the per-bar copy while keeping the guarantee. Any optimization should be accepted only if every registered strategy still produces identical decision, order, and fill ledgers.
