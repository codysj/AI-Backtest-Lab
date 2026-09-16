"""Grid-search utilities for strategy parameter research."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product

import pandas as pd

from backtester.data.loader import DataLoader
from backtester.engine import BacktestConfig, BacktestEngine
from backtester.metrics import buy_and_hold_equity, generate_report
from backtester.strategy import Strategy


@dataclass(frozen=True)
class GridSearchResult:
    """A single parameter-combination result row."""

    params: dict[str, object]
    final_value: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    error: str


def run_grid_search(
    loader: DataLoader,
    strategy_factory: Callable[..., Strategy],
    param_grid: Mapping[str, Sequence[object]],
    config: BacktestConfig,
    risk_free_rate: float = 0.0,
    sort_by: str = "sharpe_ratio",
    ascending: bool = False,
    benchmark: bool = False,
) -> pd.DataFrame:
    """Run all parameter combinations and return a sorted result DataFrame."""
    rows: list[dict[str, object]] = []
    for params in _expand_grid(param_grid):
        row: dict[str, object] = dict(params)
        try:
            strategy = strategy_factory(**params)
            result = BacktestEngine(loader=loader, strategy=strategy, config=config).run()
            price_data = loader.fetch(config.ticker, config.evaluation_start or config.start_date, config.end_date)
            benchmark_equity = buy_and_hold_equity(price_data, config.initial_cash) if benchmark else None
            report = generate_report(result, risk_free_rate=risk_free_rate, benchmark_equity=benchmark_equity)
            row.update(
                {
                    "final_value": result.final_value,
                    "total_return": report["total_return"],
                    "annualized_return": report["annualized_return"],
                    "sharpe_ratio": report["sharpe_ratio"],
                    "sortino_ratio": report["sortino_ratio"],
                    "max_drawdown": report["max_drawdown"],
                    "benchmark_total_return": report.get("benchmark_total_return"),
                    "excess_total_return": report.get("excess_total_return"),
                    "information_ratio": report.get("information_ratio"),
                    "profit_factor": report["profit_factor"],
                    "win_rate": report["win_rate"],
                    "total_trades": len(result.trades),
                    "error": "",
                }
            )
        except Exception as exc:  # noqa: BLE001 - grid search records bad combinations.
            row.update(
                {
                    "final_value": float("nan"),
                    "total_return": float("nan"),
                    "annualized_return": float("nan"),
                    "sharpe_ratio": float("nan"),
                    "sortino_ratio": float("nan"),
                    "max_drawdown": float("nan"),
                    "benchmark_total_return": float("nan"),
                    "excess_total_return": float("nan"),
                    "information_ratio": float("nan"),
                    "profit_factor": float("nan"),
                    "win_rate": float("nan"),
                    "total_trades": 0,
                    "error": str(exc),
                }
            )
        rows.append(row)

    result_frame = pd.DataFrame(rows)
    if sort_by in result_frame.columns:
        result_frame = result_frame.sort_values(sort_by, ascending=ascending, na_position="last")
    return result_frame.reset_index(drop=True)


def _expand_grid(param_grid: Mapping[str, Sequence[object]]) -> list[dict[str, object]]:
    keys = list(param_grid)
    values = [param_grid[key] for key in keys]
    return [dict(zip(keys, combination, strict=True)) for combination in product(*values)]
