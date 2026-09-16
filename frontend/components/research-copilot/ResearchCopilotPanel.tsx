"use client";

import { Bot, Send, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { approveResearch, planResearch } from "../../lib/api";
import type { ApprovedAction, ResearchGraphResponse, StrategyCompileResponse } from "../../lib/types";
import { hasErrors, validateResearchGoal } from "../../lib/validation";
import { StrategyAssumptions } from "../ai-builder/StrategyAssumptions";
import { ResearchAnalysisSummary } from "./ResearchAnalysisSummary";
import { ResearchApprovalCard } from "./ResearchApprovalCard";
import { ResearchPayloadPreview } from "./ResearchPayloadPreview";
import { ResearchStepTimeline } from "./ResearchStepTimeline";
import { modeLabel, statusTone } from "./researchCopilotUtils";

type ResearchCopilotPanelProps = {
  onLoadCompiled: (response: StrategyCompileResponse) => void;
};

const exampleGoals = [
  "Optimize AAPL from 2018 to 2024 using a 20/100 SMA crossover",
  "Walk-forward AAPL from 2019 to 2024 using a 10/50 SMA crossover",
  "Walk-forward MSFT from 2018 to 2024 using a MACD crossover",
  "Run MSFT from 2020 to 2023 using mean reversion with a 20 day window and 2 standard deviations"
];

function uniqueMessages(...groups: string[][]): string[] {
  return Array.from(new Set(groups.flat().filter(Boolean)));
}

function responseForLoad(state: ResearchGraphResponse): StrategyCompileResponse | null {
  if (!state.compile_payload || state.target_mode === null) return null;
  if (state.compile_response) {
    return state.compile_response.status === "ready" && state.compile_response.payload ? state.compile_response : null;
  }
  if (state.status === "blocked" || state.target_mode === "unspecified" || state.validation_errors.length > 0) return null;
  return {
    target_mode: state.target_mode,
    status: "ready",
    payload: state.compile_payload,
    assumptions: state.draft?.assumptions ?? [],
    warnings: state.warnings,
    unsupported: state.unsupported,
    validation_errors: state.validation_errors
  };
}

export function ResearchCopilotPanel({ onLoadCompiled }: ResearchCopilotPanelProps) {
  const [goal, setGoal] = useState("");
  const [goalError, setGoalError] = useState<string | null>(null);
  const [researchState, setResearchState] = useState<ResearchGraphResponse | null>(null);
  const [isPlanning, setIsPlanning] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [loadMessage, setLoadMessage] = useState<string | null>(null);

  const mergedWarnings = useMemo(
    () => uniqueMessages(researchState?.draft?.warnings ?? [], researchState?.warnings ?? [], researchState?.compile_response?.warnings ?? []),
    [researchState]
  );
  const mergedUnsupported = useMemo(
    () => uniqueMessages(researchState?.draft?.unsupported ?? [], researchState?.unsupported ?? [], researchState?.compile_response?.unsupported ?? []),
    [researchState]
  );
  const mergedValidationErrors = useMemo(
    () => uniqueMessages(researchState?.validation_errors ?? [], researchState?.compile_response?.validation_errors ?? []),
    [researchState]
  );
  const loadableResponse = useMemo(() => (researchState ? responseForLoad(researchState) : null), [researchState]);

  async function submitPlan(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationErrors = validateResearchGoal(goal);
    setGoalError(validationErrors.user_goal ?? null);
    setApiError(null);
    setLoadMessage(null);

    if (hasErrors(validationErrors)) {
      return;
    }

    setIsPlanning(true);
    try {
      const response = await planResearch({ user_goal: goal.trim() });
      setResearchState(response);
    } catch (caught) {
      setApiError(caught instanceof Error ? caught.message : "Could not create a research plan.");
      setResearchState(null);
    } finally {
      setIsPlanning(false);
    }
  }

  async function approve(action: ApprovedAction) {
    if (!researchState) return;

    setIsApproving(true);
    setApiError(null);
    setLoadMessage(null);
    try {
      const response = await approveResearch({ state: researchState, approved_action: action });
      setResearchState(response);
    } catch (caught) {
      setApiError(caught instanceof Error ? caught.message : "Could not approve the research workflow.");
    } finally {
      setIsApproving(false);
    }
  }

  function loadCompiled(response: StrategyCompileResponse) {
    onLoadCompiled(response);
    setLoadMessage(`Loaded compiled ${modeLabel(response.target_mode)} payload into the existing workflow form. Review before running.`);
  }

  function loadCurrentPayload() {
    if (loadableResponse) loadCompiled(loadableResponse);
  }

  return (
    <div className="space-y-5">
      <section id="research-copilot" className="rounded-xl border border-lab-border bg-lab-surface p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-lab-border bg-lab-card text-lab-cyan">
            <Bot size={18} />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-lab-text">Research Copilot</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-lab-secondary">
              Plan, inspect, approve, and analyze one existing research workflow through the backend graph.
            </p>
          </div>
        </div>

        <form onSubmit={submitPlan} className="mt-5 space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-lab-text">Research goal</span>
            <textarea
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              rows={5}
              maxLength={2000}
              className="mt-2 w-full resize-y rounded-lg border border-lab-border bg-lab-bg px-3 py-3 text-sm leading-6 text-lab-text outline-none transition placeholder:text-lab-muted focus:border-lab-blue focus:ring-2 focus:ring-lab-blue/20"
              placeholder="Example: Optimize AAPL from 2018 to 2024 using a 20/100 SMA crossover"
            />
            <div className="mt-1 flex items-center justify-between gap-3 text-xs">
              <span className="text-lab-red">{goalError}</span>
              <span className="font-mono-finance text-lab-muted">{goal.length}/2000</span>
            </div>
          </label>

          <div className="flex flex-wrap gap-2">
            {exampleGoals.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => setGoal(example)}
                className="rounded-lg border border-lab-border bg-lab-card px-3 py-2 text-left text-xs text-lab-secondary transition hover:border-lab-blue hover:text-lab-text"
              >
                {example}
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={isPlanning}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-lab-blue px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-950/30 transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Send size={16} />
            {isPlanning ? "Planning..." : "Create research plan"}
          </button>
        </form>

        {apiError ? <p className="mt-4 rounded-lg border border-lab-red/40 bg-lab-red/10 px-3 py-2 text-sm text-red-100">{apiError}</p> : null}
      </section>

      <section className="rounded-xl border border-lab-border bg-lab-surface p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${statusTone(researchState?.status ?? "drafted")}`}>
              <ShieldCheck size={14} />
              {researchState?.status.replaceAll("_", " ") ?? "No plan"}
            </div>
            <p className="mt-2 text-sm leading-6 text-lab-secondary">
              Target: <span className="font-mono-finance text-lab-text">{modeLabel(researchState?.target_mode)}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={loadCurrentPayload}
            disabled={!loadableResponse}
            title={loadableResponse ? "Load the compiled request into its existing workflow form" : "A ready compiled payload with no validation errors is required first"}
            className="inline-flex items-center justify-center rounded-lg border border-lab-border bg-lab-card px-3 py-2 text-sm font-semibold text-lab-secondary transition hover:border-lab-blue hover:text-lab-text disabled:cursor-not-allowed disabled:opacity-50"
          >
            Load compiled payload
          </button>
        </div>
        {loadMessage ? <p className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">{loadMessage}</p> : null}
      </section>

      {isPlanning && !researchState ? (
        <section className="rounded-xl border border-lab-border bg-lab-surface p-6">
          <h2 className="text-base font-semibold text-lab-text">Planning Research</h2>
          <p className="mt-2 text-sm leading-6 text-lab-secondary">Calling the backend graph through draft, validation, compile, and approval gate.</p>
        </section>
      ) : null}

      <ResearchStepTimeline state={researchState} />

      {researchState ? (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-5">
            <ResearchPayloadPreview state={researchState} onLoadCompiled={loadCompiled} />
            <ResearchAnalysisSummary state={researchState} />
          </div>
          <div className="space-y-5">
            <ResearchApprovalCard state={researchState} isApproving={isApproving} onApprove={approve} />
            <StrategyAssumptions title="Warnings" items={mergedWarnings} tone="warning" />
            <StrategyAssumptions title="Unsupported" items={mergedUnsupported} tone="danger" />
            <StrategyAssumptions title="Validation Errors" items={mergedValidationErrors} tone="danger" />
          </div>
        </div>
      ) : (
        <section className="rounded-xl border border-lab-border bg-lab-surface p-6">
          <h2 className="text-base font-semibold text-lab-text">No Plan Yet</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-lab-secondary">
            Create a plan to inspect graph steps, inferred draft, compiled payload, warnings, and the explicit approval gate.
          </p>
        </section>
      )}
    </div>
  );
}
