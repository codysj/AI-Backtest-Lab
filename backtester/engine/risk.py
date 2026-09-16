"""Close-time protective exits shared by the single- and multi-asset engines."""

from __future__ import annotations

from backtester.engine.config import BacktestConfig, MultiAssetBacktestConfig


def risk_exit_reason(
    config: BacktestConfig | MultiAssetBacktestConfig,
    *,
    entry_price: float,
    peak_close: float,
    close: float,
) -> str | None:
    """Return why an open position must be exited at this close, if at all.

    Exits are evaluated on completed closes only, so they submit a SELL that
    follows the configured execution policy like any other decision. Intrabar
    stop fills are deliberately not modeled: daily bars cannot say whether the
    low or the high printed first.
    """
    if config.stop_loss_pct is not None and close <= entry_price * (1 - config.stop_loss_pct):
        return "STOP_LOSS"
    if config.take_profit_pct is not None and close >= entry_price * (1 + config.take_profit_pct):
        return "TAKE_PROFIT"
    if config.trailing_stop_pct is not None and close <= peak_close * (1 - config.trailing_stop_pct):
        return "TRAILING_STOP"
    return None
