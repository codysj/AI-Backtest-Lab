# One Registry Defines Built-In Strategies

Date: 2026-09-16

## Status

Accepted

## Context

Strategy ids, parameter names, defaults, and research grids were repeated in the API schemas, API services, CLI, AI validator, AI compiler, frontend defaults, and frontend validation. Adding one strategy meant touching about eight files and keeping them in sync by hand.

## Decision

`backtester/strategy/registry.py` maps each strategy id to its display metadata, typed parameters, default research grid, and factory. `StrategySpec.build()` coerces parameters, rejects unknown names, and lets the strategy constructor enforce its own invariants.

API validation, `GET /api/strategies`, CLI choices and flags, grid-search factories, and AI draft compilation all read from the registry. The dashboard renders forms and default grids from the API metadata.

The API keeps `StrategyId` as a `Literal` so OpenAPI shows a closed set. A test asserts that the literal matches the registry.

## Consequences

- Adding a strategy means one class plus one registry entry, then one literal line that a test forces.
- Parameter validation messages come from strategy constructors, so every interface reports the same error.
- The rule-based strategy stays outside the registry because it is configured by a validated spec, not numeric parameters.
