"use client";

const templates = [
  "20/100 SMA crossover on AAPL",
  "Buy AAPL when close crosses above the 50 day SMA and sell when close crosses below it",
  "Mean reversion on MSFT",
  "Optimize SMA windows",
  "Walk-forward validate momentum",
  "Grid search an RSI strategy on NVDA from 2019 to 2023"
];

type PromptTemplatesProps = {
  onSelect: (template: string) => void;
};

export function PromptTemplates({ onSelect }: PromptTemplatesProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {templates.map((template) => (
        <button
          key={template}
          type="button"
          onClick={() => onSelect(template)}
          className="rounded-lg border border-lab-border bg-lab-card px-3 py-2 text-xs text-lab-secondary transition hover:border-lab-blue hover:text-lab-text"
        >
          {template}
        </button>
      ))}
    </div>
  );
}
