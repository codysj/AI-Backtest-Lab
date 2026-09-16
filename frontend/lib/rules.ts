import type { ConditionSpec, IndicatorSpec } from "./types";

export function indicatorLabel(indicator: IndicatorSpec): string {
  if (indicator.name === "close") return "close";
  if (indicator.name === "value") return String(indicator.value);
  const suffix = indicator.num_std ? `, ${indicator.num_std} std` : "";
  return `${indicator.name.replaceAll("_", " ")}(${indicator.window}${suffix})`;
}

export function conditionLabel(condition: ConditionSpec): string {
  return `${indicatorLabel(condition.left)} ${condition.operator} ${indicatorLabel(condition.right)}`;
}
