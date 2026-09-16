from __future__ import annotations

import pytest

from backtester.cli import build_parser, parse_assignment


def test_parse_assignment() -> None:
    assert parse_assignment("entry_window=20, 55") == ("entry_window", [20.0, 55.0])


def test_run_parser_accepts_required_arguments() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--ticker",
            "AAPL",
            "--start",
            "2020-01-01",
            "--end",
            "2021-01-01",
            "--strategy",
            "momentum",
        ]
    )

    assert args.command == "run"
    assert args.strategy == "momentum"


def test_invalid_strategy_exits_cleanly() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "run",
                "--ticker",
                "AAPL",
                "--start",
                "2020-01-01",
                "--end",
                "2021-01-01",
                "--strategy",
                "bad",
            ]
        )
