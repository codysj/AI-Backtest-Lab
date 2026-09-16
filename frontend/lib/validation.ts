import type { BacktestRequest, GridSearchRequest, RiskExitSettings, StrategyMetadata, WalkForwardRequest } from "./types";

export type FormErrors = Partial<Record<string, string>>;

function validateSizingAndExits(
  request: RiskExitSettings & { position_size_method: string; position_size_value: number },
  errors: FormErrors
) {
  const fractional = request.position_size_method === "PERCENT_EQUITY" || request.position_size_method === "VOLATILITY_TARGET";
  if (fractional && request.position_size_value > 1) {
    errors.position_size_value = "Use a fraction between 0 and 1 for this sizing method.";
  }
  (["stop_loss_pct", "take_profit_pct", "trailing_stop_pct"] as const).forEach((key) => {
    const value = request[key];
    if (value != null && (!Number.isFinite(value) || value <= 0 || value >= 1)) {
      errors[key] = "Enter a percent between 0 and 100.";
    }
  });
}

export function validateBacktestRequest(request: BacktestRequest, strategy?: StrategyMetadata): FormErrors {
  const errors: FormErrors = {};

  if (!request.ticker.trim()) {
    errors.ticker = "Ticker is required.";
  }

  if (!request.start_date) {
    errors.start_date = "Start date is required.";
  }

  if (!request.end_date) {
    errors.end_date = "End date is required.";
  }

  if (request.start_date && request.end_date && request.start_date >= request.end_date) {
    errors.date_range = "Start date must be before end date.";
  }

  if (!Number.isFinite(request.initial_cash) || request.initial_cash <= 0) {
    errors.initial_cash = "Initial cash must be positive.";
  }

  if (!Number.isFinite(request.position_size_value) || request.position_size_value <= 0) {
    errors.position_size_value = "Size value must be positive.";
  }

  if (!Number.isFinite(request.commission_rate) || request.commission_rate < 0) {
    errors.commission_rate = "Commission must be zero or greater.";
  }

  if (!Number.isFinite(request.slippage_bps) || request.slippage_bps < 0) {
    errors.slippage_bps = "Slippage must be zero or greater.";
  }

  strategy?.parameters.forEach((parameter) => {
    const value = request.parameters[parameter.name];
    if (!Number.isFinite(value) || value <= 0) {
      errors[`parameters.${parameter.name}`] = `${parameter.label} must be positive.`;
    }
  });

  if (request.strategy === "momentum") {
    const fast = request.parameters.fast_window;
    const slow = request.parameters.slow_window;
    if (Number.isFinite(fast) && Number.isFinite(slow) && fast >= slow) {
      errors["parameters.fast_window"] = "Fast window must be less than slow window.";
      errors["parameters.slow_window"] = "Slow window must be greater than fast window.";
    }
  }
  validateSizingAndExits(request, errors);
  if (request.strategy === "rule_based" && !request.rule_spec) {
    errors.rule_spec = "Rule-based strategies require a generated rule spec.";
  }

  return errors;
}

export function hasErrors(errors: FormErrors): boolean {
  return Object.keys(errors).length > 0;
}

export function validateGridSearchRequest(request: GridSearchRequest): FormErrors {
  const errors = validateResearchBase(request);
  if (!Number.isFinite(request.max_results) || request.max_results < 1) {
    errors.max_results = "Top results must be at least 1.";
  }
  return errors;
}

export function validateWalkForwardRequest(request: WalkForwardRequest): FormErrors {
  const errors = validateResearchBase(request);
  if (!Number.isFinite(request.train_window_bars) || request.train_window_bars < 20) {
    errors.train_window_bars = "Train window must be at least 20 bars.";
  }
  if (!Number.isFinite(request.test_window_bars) || request.test_window_bars < 5) {
    errors.test_window_bars = "Test window must be at least 5 bars.";
  }
  if (request.train_window_bars <= request.test_window_bars) {
    errors.train_window_bars = "Train window must be greater than test window.";
  }
  if (!Number.isFinite(request.step_bars) || request.step_bars < 1) {
    errors.step_bars = "Step must be at least 1 bar.";
  }
  return errors;
}

export function validateResearchGoal(goal: string): FormErrors {
  const errors: FormErrors = {};
  const normalized = goal.trim();
  if (!normalized) {
    errors.user_goal = "Research goal is required.";
  }
  if (normalized.length > 2000) {
    errors.user_goal = "Research goal must be 2000 characters or fewer.";
  }
  return errors;
}

function validateResearchBase(request: GridSearchRequest | WalkForwardRequest): FormErrors {
  const errors: FormErrors = {};
  if (!request.ticker.trim()) {
    errors.ticker = "Ticker is required.";
  }
  if (request.start_date >= request.end_date) {
    errors.date_range = "Start date must be before end date.";
  }
  Object.entries(request.parameter_grid).forEach(([name, values]) => {
    if (values.length === 0 || values.some((value) => !Number.isFinite(value) || value <= 0)) {
      errors[`parameter_grid.${name}`] = "Enter one or more positive values.";
    }
  });
  if (request.strategy === "momentum") {
    const fastValues = request.parameter_grid.fast_window ?? [];
    const slowValues = request.parameter_grid.slow_window ?? [];
    if (fastValues.length === 0) errors["parameter_grid.fast_window"] = "Fast windows are required.";
    if (slowValues.length === 0) errors["parameter_grid.slow_window"] = "Slow windows are required.";
    if (fastValues.length > 0 && slowValues.length > 0 && Math.min(...fastValues) >= Math.max(...slowValues)) {
      errors["parameter_grid.fast_window"] = "At least one fast window must be less than a slow window.";
    }
  }
  validateSizingAndExits(request, errors);
  return errors;
}
