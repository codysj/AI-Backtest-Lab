"""Command-line interface for Backtester."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from backtester.data.loader import DataLoader
from backtester.engine import BacktestConfig, BacktestEngine, PositionSizeMethod
from backtester.metrics import buy_and_hold_equity, generate_report, print_report
from backtester.research import run_grid_search
from backtester.strategy import STRATEGIES
from backtester.viz import plot_drawdown, plot_equity_curve, plot_trades


def parse_assignment(value: str) -> tuple[str, list[float]]:
    """Parse ``name=1`` or ``name=1,2,3`` into a name and numeric values."""
    name, separator, raw_values = value.partition("=")
    if not separator or not name.strip():
        msg = f"Expected NAME=VALUE, got {value!r}."
        raise argparse.ArgumentTypeError(msg)
    try:
        values = [float(item) for item in raw_values.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Non-numeric value in {value!r}.") from exc
    if not values:
        raise argparse.ArgumentTypeError(f"No values given in {value!r}.")
    return name.strip(), values


def _add_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--strategy", choices=sorted(STRATEGIES), default="momentum")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--commission-rate", type=float, default=0.001)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument(
        "--position-size-method",
        choices=[method.name for method in PositionSizeMethod],
        default=PositionSizeMethod.PERCENT_EQUITY.name,
    )
    parser.add_argument("--position-size-value", type=float, default=0.95)
    parser.add_argument("--stop-loss", type=float, help="Exit when close falls this fraction below entry.")
    parser.add_argument("--take-profit", type=float, help="Exit when close rises this fraction above entry.")
    parser.add_argument("--trailing-stop", type=float, help="Exit when close falls this fraction below its peak.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backtester", description="Run Backtester workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one backtest.")
    _add_config_arguments(run_parser)
    run_parser.add_argument(
        "--param",
        type=parse_assignment,
        action="append",
        default=[],
        help="Strategy parameter as NAME=VALUE. Omitted parameters use registry defaults.",
    )
    run_parser.add_argument("--benchmark", action="store_true")
    run_parser.add_argument("--save-charts", action="store_true")
    run_parser.add_argument("--output-dir", default="outputs")

    grid_parser = subparsers.add_parser("grid-search", help="Run a parameter grid search.")
    _add_config_arguments(grid_parser)
    grid_parser.add_argument(
        "--grid",
        type=parse_assignment,
        action="append",
        default=[],
        help="Parameter range as NAME=V1,V2,... Omitted parameters use the registry default grid.",
    )
    grid_parser.add_argument("--sort-by", default="sharpe_ratio")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            _run_backtest(args)
        else:
            _run_grid_search(args)
    except Exception as exc:  # noqa: BLE001 - CLI should show readable errors.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _config(args: argparse.Namespace) -> BacktestConfig:
    return BacktestConfig(
        ticker=args.ticker,
        start_date=args.start,
        end_date=args.end,
        initial_cash=args.initial_cash,
        commission_rate=args.commission_rate,
        slippage_bps=args.slippage_bps,
        position_size_method=PositionSizeMethod[args.position_size_method],
        position_size_value=args.position_size_value,
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        trailing_stop_pct=args.trailing_stop,
    )


def _run_backtest(args: argparse.Namespace) -> None:
    loader = DataLoader()
    config = _config(args)
    parameters = {name: values[-1] for name, values in args.param}
    strategy = STRATEGIES[args.strategy].build(parameters)
    result = BacktestEngine(loader=loader, strategy=strategy, config=config).run()
    benchmark_equity = None
    price_data = None
    if args.benchmark or args.save_charts:
        price_data = loader.fetch(config.ticker, config.start_date, config.end_date)
    if args.benchmark and price_data is not None:
        benchmark_equity = buy_and_hold_equity(price_data, config.initial_cash)

    print_report(generate_report(result, benchmark_equity=benchmark_equity))
    if args.save_charts and price_data is not None:
        output_dir = Path(args.output_dir)
        plot_equity_curve(result, benchmark_equity=benchmark_equity, save_path=str(output_dir / "equity_curve.png"))
        plot_drawdown(result.equity_curve, save_path=str(output_dir / "drawdown.png"))
        plot_trades(price_data, result.trades, save_path=str(output_dir / "trades.png"))
        print(f"charts saved to {output_dir}")


def _run_grid_search(args: argparse.Namespace) -> None:
    spec = STRATEGIES[args.strategy]
    grid: dict[str, list[int | float]] = {**spec.default_grid(), **dict(args.grid)}
    results = run_grid_search(
        loader=DataLoader(),
        strategy_factory=lambda **parameters: spec.build(parameters),
        param_grid=grid,
        config=_config(args),
        sort_by=args.sort_by,
    )
    print(results.to_string(index=False))


if __name__ == "__main__":
    raise SystemExit(main())
