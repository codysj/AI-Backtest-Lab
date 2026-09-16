"""Backtest engine composition layer."""

from backtester.engine.backtest import BacktestEngine, BacktestResult
from backtester.engine.config import BacktestConfig, ExecutionPolicy, MultiAssetBacktestConfig, PositionSizeMethod
from backtester.engine.multi_asset import MultiAssetBacktestEngine, MultiAssetBacktestResult

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "ExecutionPolicy",
    "MultiAssetBacktestConfig",
    "MultiAssetBacktestEngine",
    "MultiAssetBacktestResult",
    "PositionSizeMethod",
]
