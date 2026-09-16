# Backtest Lab Frontend

Backtest Lab is the Next.js dashboard for the Backtester project. It is a local research UI for running single-asset backtests, grid searches, walk-forward validation, natural-language AI Builder handoffs, and Research Copilot approval workflows through the FastAPI API.

The frontend does not implement backtesting, grid-search, walk-forward, metrics, portfolio, or benchmark logic. It calls the Python API and renders the returned response.

## Setup

Install dependencies:

```bash
npm install
```

Backtest Lab currently uses Next.js 15. Use a Node.js version compatible with Next's engine range: `^18.18.0`, `^19.8.0`, or `>=20.0.0`.

Run the development server:

```bash
npm run dev
```

Build for production:

```bash
npm run lint
npm run typecheck
npm run build
```

`npm run lint` uses ESLint with the Next.js core web vitals and TypeScript rules. `npm run typecheck` runs `next typegen && tsc --noEmit` so route/layout types exist before TypeScript validation. `npm run build` skips Next's internal lint hook because linting is run explicitly as a separate command.

## Dependency Security

The project pins a stable Next.js 15 release and uses an npm override for Next's nested PostCSS dependency. CI blocks on high/critical vulnerabilities in shipped dependencies with `npm audit --omit=dev --audit-level=high`; a full local `npm audit` can still be used to review development-tool findings. Do not use `npm audit fix --force` unless a reviewed upgrade leaves no safe non-force path.

## API Configuration

By default, the frontend calls:

```text
http://localhost:8000
```

Override this with `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Only public browser settings belong in `frontend/.env.local`. AI provider keys such as `BACKTESTER_AI_API_KEY` are backend/server variables and must not be exposed through `NEXT_PUBLIC_*`.

Start the API from the repo root:

```bash
python -m uvicorn backtester.api.main:app --reload
```

The API currently allows browser requests from `http://localhost:3000` and `http://127.0.0.1:3000`.

To use another local frontend port, set `BACKTESTER_CORS_ORIGINS` before starting the backend:

```bash
BACKTESTER_CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

## UI Structure

- `app/page.tsx`
  - Owns dashboard state, API health/strategy loading, mode switching, request validation, and API submissions.
- `app/globals.css`
  - Dark dashboard color variables and shared font stacks.
- `components/AppShell.tsx`
  - Full-screen shell with sidebar, top bar, main workspace, and config panel slot.
- `components/Sidebar.tsx`
  - Product identity, navigation, and built-from-scratch badge.
- `components/TopBar.tsx`
  - Current run context, API status, reset/default controls, docs/GitHub links.
- `components/BacktestForm.tsx`
  - Controlled single-asset backtest form with inline validation display.
- `components/RiskExitFields.tsx`
  - Optional stop-loss, take-profit, and trailing-stop inputs shared by all workflow forms.
- `components/ResearchForms.tsx`
  - Controlled grid-search and walk-forward forms with range inputs, optimization metrics, and fold windows.
- `components/ai-builder/`
  - Natural-language AI Builder prompt panel, prompt templates, generated strategy preview, assumptions/warnings/unsupported states, compile handoff, and reproducibility JSON.
- `components/research-copilot/`
  - Research Copilot prompt panel, graph step timeline, compiled payload preview, explicit approval card, deterministic analysis summary, workflow result summary, and safe form handoff.
- `components/ResultsDashboard.tsx`
  - Run hero, status, KPI cards, charts, and result tabs.
- `components/ResearchResults.tsx`
  - Grid-search leaderboard, robustness warnings, heatmap, failed combinations, selected-config handoff, and walk-forward fold table.
- `components/EquityChart.tsx`
  - Recharts equity curve with optional benchmark series.
- `components/DrawdownChart.tsx`
  - Recharts drawdown chart with percent axis.
- `components/ResultsTabs.tsx`
  - Summary, Trades, Metrics, Risk, and Parameters tabs with export actions.
- `components/TradeTable.tsx`
  - Executed trades table.
- `components/EmptyState.tsx`, `ErrorState.tsx`, `LoadingSkeleton.tsx`
  - Non-happy-path states.
- `components/formatters.ts`
  - Shared formatting helpers.
- `lib/api.ts`
  - API client for `GET /health`, `GET /api/strategies`, `POST /api/backtest`, `POST /api/grid-search`, `POST /api/walk-forward`, `POST /api/ai/strategy-draft`, `POST /api/ai/compile`, `POST /api/ai/research-plan`, and `POST /api/ai/research-approve`.
- `lib/types.ts`
  - TypeScript request/response shapes matching the FastAPI schema.
- `lib/exports.ts`
  - Frontend CSV/JSON downloads from returned API data.
- `lib/defaults.ts`
  - Default AAPL Momentum SMA request and fallback metadata used until `GET /api/strategies` responds.
- `lib/rules.ts`
  - Human-readable labels for rule DSL conditions.
- `lib/validation.ts`
  - Client-side validation for form UX.

## API Assumptions

Backtest Lab assumes these API endpoints exist:

- `GET /health`
- `GET /api/strategies`
- `POST /api/backtest`
- `POST /api/grid-search`
- `POST /api/walk-forward`
- `POST /api/ai/strategy-draft`
- `POST /api/ai/compile`
- `POST /api/ai/research-plan`
- `POST /api/ai/research-approve`

All current browser workflows are single-asset. `POST /api/backtest` returns submitted config, summary metrics, equity/benchmark/drawdown/price series, trades, and richer risk analytics. `POST /api/grid-search` returns ranked research rows, failed combinations, heatmap data, and robustness warnings. `POST /api/walk-forward` returns folds, selected parameters, train/test metrics, degradation ratios, and aggregate validation warnings.
The AI Builder endpoints return inert draft and compiled request JSON only. The frontend reviews and loads compiled payloads into existing forms; it does not execute them automatically. Rule-based generated strategies arrive as a backend-validated `rule_spec`; the browser displays the rules but does not implement or edit the strategy logic.
Research Copilot uses request/response state passing. The plan call never executes a workflow; approval requires a user click and sends the prior state plus one matching action. The browser displays backend-provided analysis and can load compiled payloads into existing forms without auto-running them.
AI provider selection and API keys are handled only by the FastAPI backend. The browser never sends or receives provider credentials.

## Screenshots And GIF

README media in `docs/demos/` is generated from the running app. Start the API, run `npm run build && npm run start`, then run `python scripts/capture_demo_media.py` from the repo root.
