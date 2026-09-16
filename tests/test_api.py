from __future__ import annotations

from fastapi.testclient import TestClient

from backtester.api.main import app
from backtester.api.main import get_cors_origins
from backtester.api.main import _selected_ai_model
from backtester.api.main import _selected_ai_provider
from backtester.api.schemas import (
    BacktestResponse,
    BacktestSeries,
    BacktestSummary,
    GridSearchResponse,
    GridSearchRow,
    HeatmapPoint,
    RobustnessAnalysis,
    SeriesPoint,
    WalkForwardResponse,
    WalkForwardSummary,
)


client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_origins_default_to_local_frontend_ports(monkeypatch) -> None:
    monkeypatch.delenv("BACKTESTER_CORS_ORIGINS", raising=False)

    assert get_cors_origins() == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_cors_origins_can_be_configured_from_comma_separated_value() -> None:
    origins = get_cors_origins("http://localhost:3001, https://example.test, ")

    assert origins == ["http://localhost:3001", "https://example.test"]


def test_ai_startup_log_settings_default_to_fake(monkeypatch) -> None:
    monkeypatch.delenv("BACKTESTER_AI_PROVIDER", raising=False)
    monkeypatch.delenv("BACKTESTER_AI_MODEL", raising=False)

    provider = _selected_ai_provider()

    assert provider == "fake"
    assert _selected_ai_model(provider) == "default"


def test_ai_startup_log_settings_report_openrouter_default_model(monkeypatch) -> None:
    monkeypatch.setenv("BACKTESTER_AI_PROVIDER", "openrouter")
    monkeypatch.delenv("BACKTESTER_AI_MODEL", raising=False)

    provider = _selected_ai_provider()

    assert provider == "openrouter"
    assert _selected_ai_model(provider) == "tencent/hy3-preview:free"


def test_ai_startup_log_settings_preserve_configured_model(monkeypatch) -> None:
    monkeypatch.setenv("BACKTESTER_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("BACKTESTER_AI_MODEL", "custom-model")

    assert _selected_ai_model(_selected_ai_provider()) == "custom-model"


def test_strategies_returns_supported_strategies() -> None:
    response = client.get("/api/strategies")

    assert response.status_code == 200
    strategy_ids = {strategy["id"] for strategy in response.json()["strategies"]}
    assert strategy_ids == {
        "momentum",
        "mean_reversion",
        "rsi_reversion",
        "donchian_breakout",
        "macd_crossover",
        "rule_based",
    }


def test_backtest_uses_service_layer(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_run_backtest_from_request(request):  # type: ignore[no-untyped-def]
        return BacktestResponse(
            config={"ticker": request.ticker},
            summary=BacktestSummary(
                strategy_name="Momentum(10/50)",
                ticker=request.ticker,
                initial_value=100_000.0,
                final_value=101_000.0,
                total_return=0.01,
                annualized_return=0.1,
                sharpe_ratio=1.0,
                sortino_ratio=1.2,
                max_drawdown=-0.05,
                win_rate=0.5,
                profit_factor=1.3,
                total_trades=2,
            ),
            series=BacktestSeries(
                equity=[SeriesPoint(date="2020-01-01", value=100_000.0)],
                benchmark=[],
                drawdown=[SeriesPoint(date="2020-01-01", value=0.0)],
                price=[],
            ),
            trades=[],
        )

    monkeypatch.setattr("backtester.api.main.run_backtest_from_request", fake_run_backtest_from_request)

    response = client.post(
        "/api/backtest",
        json={
            "ticker": "aapl",
            "start_date": "2020-01-01",
            "end_date": "2021-01-01",
            "strategy": "momentum",
            "parameters": {"fast_window": 10, "slow_window": 50},
        },
    )

    assert response.status_code == 200
    assert response.json()["summary"]["ticker"] == "AAPL"


def test_invalid_strategy_returns_validation_error() -> None:
    response = client.post(
        "/api/backtest",
        json={
            "ticker": "AAPL",
            "start_date": "2020-01-01",
            "end_date": "2021-01-01",
            "strategy": "bad",
        },
    )

    assert response.status_code == 422


def test_grid_search_endpoint_uses_service_layer(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_run_grid_search_from_request(request):  # type: ignore[no-untyped-def]
        return GridSearchResponse(
            config={"ticker": request.ticker},
            strategy_id=request.strategy,
            strategy_name="Momentum SMA Crossover",
            optimization_metric=request.optimization_metric,
            total_combinations=0,
            results=[],
            failed_combinations=[],
            best_parameters=None,
            best_row=None,
            heatmap=[],
            analysis=RobustnessAnalysis(
                robustness_score=0,
                warnings=[],
                notes=[],
                nearby_parameter_stability=None,
                trade_count_flags=[],
                drawdown_flags=[],
                overfit_risk_flags=[],
            ),
        )

    monkeypatch.setattr("backtester.api.main.run_grid_search_from_request", fake_run_grid_search_from_request)

    response = client.post(
        "/api/grid-search",
        json={
            "ticker": "aapl",
            "start_date": "2020-01-01",
            "end_date": "2021-01-01",
            "strategy": "momentum",
            "parameter_grid": {"fast_window": [5], "slow_window": [20]},
            "optimization_metric": "sharpe_ratio",
        },
    )

    assert response.status_code == 200
    assert response.json()["config"]["ticker"] == "AAPL"


def test_walk_forward_endpoint_uses_service_layer(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_run_walk_forward_from_request(request):  # type: ignore[no-untyped-def]
        return WalkForwardResponse(
            config={"ticker": request.ticker},
            strategy_id=request.strategy,
            strategy_name="Momentum SMA Crossover",
            optimization_metric=request.optimization_metric,
            folds=[],
            summary=WalkForwardSummary(
                average_train_metric=None,
                average_test_metric=None,
                average_degradation=None,
                number_of_folds=0,
                parameter_stability=None,
                warnings=[],
            ),
        )

    monkeypatch.setattr("backtester.api.main.run_walk_forward_from_request", fake_run_walk_forward_from_request)

    response = client.post(
        "/api/walk-forward",
        json={
            "ticker": "aapl",
            "start_date": "2020-01-01",
            "end_date": "2021-01-01",
            "strategy": "momentum",
            "parameter_grid": {"fast_window": [5], "slow_window": [20]},
            "optimization_metric": "sharpe_ratio",
            "train_window_bars": 40,
            "test_window_bars": 10,
            "step_bars": 10,
        },
    )

    assert response.status_code == 200
    assert response.json()["config"]["ticker"] == "AAPL"


def test_research_plan_requires_approval_and_does_not_execute(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fail_grid_search(request):  # type: ignore[no-untyped-def]
        del request
        raise AssertionError("research-plan must not execute workflows")

    monkeypatch.setattr("backtester.agents.tools.run_grid_search_from_request", fail_grid_search)

    response = client.post(
        "/api/ai/research-plan",
        json={"user_goal": "Optimize AAPL from 2018 to 2024 using a 20/100 SMA crossover"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "awaiting_approval"
    assert payload["approval_required"] is True
    assert payload["target_mode"] == "grid_search"
    assert payload["workflow_result"] is None
    assert "run_workflow" not in payload["steps"]


def test_research_approval_executes_one_mocked_workflow(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[str] = []

    def fake_grid_search(request):  # type: ignore[no-untyped-def]
        calls.append("grid")
        return GridSearchResponse(
            config={"ticker": request.ticker},
            strategy_id=request.strategy,
            strategy_name="Momentum SMA Crossover",
            optimization_metric=request.optimization_metric,
            total_combinations=1,
            results=[
                GridSearchRow(
                    rank=1,
                    parameters={"fast_window": 20, "slow_window": 100},
                    final_value=101000.0,
                    total_return=0.01,
                    annualized_return=0.02,
                    sharpe_ratio=0.8,
                    sortino_ratio=0.9,
                    max_drawdown=-0.05,
                    information_ratio=None,
                    benchmark_total_return=None,
                    excess_total_return=None,
                    profit_factor=1.2,
                    win_rate=0.5,
                    total_trades=4,
                )
            ],
            failed_combinations=[],
            best_parameters={"fast_window": 20, "slow_window": 100},
            best_row=None,
            heatmap=[
                HeatmapPoint(
                    x_param="fast_window",
                    y_param="slow_window",
                    x=20,
                    y=100,
                    value=0.8,
                    parameters={"fast_window": 20, "slow_window": 100},
                )
            ],
            analysis=RobustnessAnalysis(
                robustness_score=90,
                warnings=[],
                notes=["Heuristics are a research aid, not a guarantee of future performance."],
                nearby_parameter_stability=None,
                trade_count_flags=[],
                drawdown_flags=[],
                overfit_risk_flags=[],
            ),
        )

    monkeypatch.setattr("backtester.agents.tools.run_grid_search_from_request", fake_grid_search)
    plan = client.post(
        "/api/ai/research-plan",
        json={"user_goal": "Optimize AAPL from 2018 to 2024 using a 20/100 SMA crossover"},
    ).json()

    response = client.post(
        "/api/ai/research-approve",
        json={"state": plan, "approved_action": "run_grid_search"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert calls == ["grid"]
    assert payload["status"] == "completed"
    assert payload["approval_required"] is False
    assert payload["workflow_result"]["summary"]["total_combinations"] == 1


def test_research_approval_refuses_already_executed_state(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[str] = []

    def fake_grid_search(request):  # type: ignore[no-untyped-def]
        calls.append("grid")
        return GridSearchResponse(
            config={"ticker": request.ticker},
            strategy_id=request.strategy,
            strategy_name="Momentum SMA Crossover",
            optimization_metric=request.optimization_metric,
            total_combinations=1,
            results=[],
            failed_combinations=[],
            best_parameters=None,
            best_row=None,
            heatmap=[],
            analysis=RobustnessAnalysis(
                robustness_score=90,
                warnings=[],
                notes=[],
                nearby_parameter_stability=None,
                trade_count_flags=[],
                drawdown_flags=[],
                overfit_risk_flags=[],
            ),
        )

    monkeypatch.setattr("backtester.agents.tools.run_grid_search_from_request", fake_grid_search)
    plan = client.post(
        "/api/ai/research-plan",
        json={"user_goal": "Optimize AAPL from 2018 to 2024 using a 20/100 SMA crossover"},
    ).json()
    completed = client.post(
        "/api/ai/research-approve",
        json={"state": plan, "approved_action": "run_grid_search"},
    ).json()

    response = client.post(
        "/api/ai/research-approve",
        json={"state": completed, "approved_action": "run_grid_search"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert calls == ["grid"]
    assert payload["status"] == "blocked"
    assert any("already contains a workflow result" in error for error in payload["validation_errors"])


def test_research_approval_refuses_mismatched_action(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[str] = []

    def fake_backtest(request):  # type: ignore[no-untyped-def]
        del request
        calls.append("backtest")
        raise AssertionError("mismatched approval must not execute")

    monkeypatch.setattr("backtester.agents.tools.run_backtest_from_request", fake_backtest)
    plan = client.post(
        "/api/ai/research-plan",
        json={"user_goal": "Optimize AAPL from 2018 to 2024 using a 20/100 SMA crossover"},
    ).json()

    response = client.post(
        "/api/ai/research-approve",
        json={"state": plan, "approved_action": "run_backtest"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert calls == []
    assert payload["status"] == "blocked"
    assert payload["approval_required"] is True
    assert any("approved_action must be run_grid_search" in error for error in payload["validation_errors"])


def test_research_approval_sanitizes_malformed_compiled_payload() -> None:
    secret = "sk-approval-secret"
    plan = client.post(
        "/api/ai/research-plan",
        json={"user_goal": "Optimize AAPL from 2018 to 2024 using a 20/100 SMA crossover"},
    ).json()
    plan["compile_payload"] = {"ticker": "AAPL", "secret_payload": secret}

    response = client.post(
        "/api/ai/research-approve",
        json={"state": plan, "approved_action": "run_grid_search"},
    )

    assert response.status_code == 200
    assert secret not in response.text
    payload = response.json()
    assert payload["status"] == "blocked"
    assert any("Compiled payload did not match the grid-search request schema" in error for error in payload["validation_errors"])


def test_research_plan_sanitizes_validation_errors(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    secret = "sk-secret-should-not-leak"

    class MalformedProvider:
        def draft_strategy(self, request):  # type: ignore[no-untyped-def]
            del request
            return {
                "status": "ready",
                "strategy_kind": "momentum",
                "parameters": {"fast_window": "bad"},
                "secret_payload": secret,
            }

    monkeypatch.setattr("backtester.ai.providers.get_strategy_draft_provider", lambda: MalformedProvider())

    response = client.post(
        "/api/ai/research-plan",
        json={
            "user_goal": "Run AAPL with momentum",
            "context": {"api_key": secret},
        },
    )

    assert response.status_code == 200
    serialized = response.text
    assert secret not in serialized
    assert response.json()["status"] == "blocked"
    assert response.json()["validation_errors"]


def test_research_plan_uses_fake_provider_without_network() -> None:
    response = client.post(
        "/api/ai/research-plan",
        json={"user_goal": "Run AAPL from 2018 to 2024 using a 20/100 SMA crossover"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft"]["strategy_kind"] == "momentum"
    assert payload["compile_payload"]["ticker"] == "AAPL"
