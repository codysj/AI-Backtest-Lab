"""Pydantic schemas for inert AI strategy drafts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backtester.api.schemas import OptimizationMetric
from backtester.engine import PositionSizeMethod
from backtester.strategy.rule_schema import RuleBasedStrategySpec


class TargetMode(str, Enum):
    """Supported downstream workflow targets."""

    SINGLE_RUN = "single_run"
    GRID_SEARCH = "grid_search"
    WALK_FORWARD = "walk_forward"
    UNSPECIFIED = "unspecified"


class StrategyKind(str, Enum):
    """Strategy kinds the draft contract can name."""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    RSI_REVERSION = "rsi_reversion"
    DONCHIAN_BREAKOUT = "donchian_breakout"
    MACD_CROSSOVER = "macd_crossover"
    RULE_BASED = "rule_based"
    UNSUPPORTED = "unsupported"


class StrategyDraftStatus(str, Enum):
    """Readiness status for a generated strategy draft."""

    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"


class StrategyDraftRequest(BaseModel):
    """Natural-language request for a structured strategy draft."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None
    current_config: dict[str, Any] | None = None

    @field_validator("prompt")
    @classmethod
    def strip_prompt(cls, value: str) -> str:
        """Normalize whitespace without changing user intent."""
        normalized = value.strip()
        if not normalized:
            msg = "prompt must not be empty."
            raise ValueError(msg)
        return normalized


class StrategyDraft(BaseModel):
    """Structured, non-executable strategy draft produced from natural language."""

    model_config = ConfigDict(extra="forbid")

    target_mode: TargetMode = TargetMode.UNSPECIFIED
    ticker: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    benchmark: bool = Field(default=True, strict=True)
    initial_cash: float | None = Field(default=100_000.0, gt=0)
    commission_rate: float | None = Field(default=0.001, ge=0)
    slippage_bps: float | None = Field(default=5.0, ge=0)
    position_size_method: PositionSizeMethod | None = PositionSizeMethod.PERCENT_EQUITY
    position_size_value: float | None = Field(default=0.95, gt=0)
    strategy_kind: StrategyKind = StrategyKind.UNSUPPORTED
    parameters: dict[str, int | float] = Field(default_factory=dict)
    rule_spec: RuleBasedStrategySpec | None = None
    parameter_grid: dict[str, list[int | float]] | None = None
    optimization_metric: OptimizationMetric | None = None
    train_window_bars: int | None = Field(default=None, gt=0)
    test_window_bars: int | None = Field(default=None, gt=0)
    step_bars: int | None = Field(default=None, gt=0)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: StrategyDraftStatus = StrategyDraftStatus.NEEDS_CLARIFICATION

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str | None) -> str | None:
        """Normalize tickers for consistency with the existing API."""
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None


class StrategyDraftValidation(BaseModel):
    """Validation details for a draft beyond basic Pydantic checks."""

    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


class StrategyDraftResponse(BaseModel):
    """API response for natural-language strategy draft generation."""

    draft: StrategyDraft | None
    status: StrategyDraftStatus
    warnings: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class StrategyCompileRequest(BaseModel):
    """Request to compile an inert draft into an existing API request payload."""

    model_config = ConfigDict(extra="forbid")

    draft: StrategyDraft

    @model_validator(mode="before")
    @classmethod
    def accept_draft_or_response_payload(cls, data: Any) -> Any:
        """Accept either {"draft": ...} or a bare StrategyDraft-shaped body."""
        if isinstance(data, StrategyDraft):
            return {"draft": data}
        if not isinstance(data, Mapping):
            return data
        if "draft" in data:
            return {"draft": data["draft"]}
        if "strategy_kind" in data or "target_mode" in data:
            return {"draft": data}
        return data


class StrategyCompileResponse(BaseModel):
    """Compiled request payload for one existing API workflow."""

    target_mode: TargetMode
    status: StrategyDraftStatus
    payload: dict[str, Any] | None = None
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
