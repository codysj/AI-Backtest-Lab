# AI Strategies Compile To A Constrained Rule DSL

Date: 2026-05-07

## Status

Accepted

## Context

Natural-language strategy prompts can describe ideas beyond the two built-in strategies. Letting a model generate Python would be flexible, but it would create unacceptable safety, reproducibility, and maintenance risks: arbitrary code execution, filesystem access, dynamic imports, look-ahead bugs, and behavior that bypasses the existing API and validator contracts.

Backtester already has a safe `Strategy` interface and a FastAPI/Pydantic boundary. The AI Builder should extend that path without creating a second execution model.

## Decision

Natural-language strategies compile into a constrained, Pydantic-validated rule DSL. The DSL supports only enum-backed indicators and operators, and `RuleBasedStrategy` evaluates those specs through the existing bar-by-bar `Strategy` interface.

The v1 DSL supports close, SMA, prior rolling high/low, and Bollinger upper/lower indicators. Entry rules use ALL logic and exit rules use ANY logic. The engine remains strategy-agnostic, and no generated Python code, dynamic imports, subprocess calls, or file-based strategies are allowed.

## Consequences

- AI Builder can express more natural strategy ideas while preserving deterministic validation and review.
- Model output remains untrusted data and must pass schema validation plus semantic validation before compilation.
- Look-ahead prevention remains inside strategy implementation: `RuleBasedStrategy` uses only current and prior indicator values at `current_index`.
- The first version was intentionally limited. EMA, RSI, and constant operands were added on 2026-09-16 using the shared causal indicator module. Arbitrary formulas, multi-asset rules, nested boolean logic, and rule-grid optimization still require design and tests.
