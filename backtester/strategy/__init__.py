"""Strategy abstractions and built-in strategy implementations."""

from backtester.strategy.base import MultiAssetStrategy, Signal, Strategy
from backtester.strategy.mean_reversion import MeanReversionStrategy
from backtester.strategy.momentum import MomentumStrategy
from backtester.strategy.multi_asset import SingleStrategyMultiAssetWrapper
from backtester.strategy.oscillators import DonchianBreakoutStrategy, MacdCrossoverStrategy, RsiReversionStrategy
from backtester.strategy.registry import STRATEGIES, ParameterSpec, StrategySpec
from backtester.strategy.rule_schema import (
    ConditionOperator,
    ConditionSpec,
    IndicatorName,
    IndicatorSpec,
    RuleBasedStrategySpec,
    RuleSetSpec,
)
from backtester.strategy.rules import RuleBasedStrategy

__all__ = [
    "STRATEGIES",
    "DonchianBreakoutStrategy",
    "MacdCrossoverStrategy",
    "ParameterSpec",
    "RsiReversionStrategy",
    "StrategySpec",
    "ConditionOperator",
    "ConditionSpec",
    "IndicatorName",
    "IndicatorSpec",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "MultiAssetStrategy",
    "RuleBasedStrategy",
    "RuleBasedStrategySpec",
    "RuleSetSpec",
    "Signal",
    "SingleStrategyMultiAssetWrapper",
    "Strategy",
]

