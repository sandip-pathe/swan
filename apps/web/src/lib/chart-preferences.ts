import type { Timeframe } from "./chart-data";

export const CHART_PREFERENCES_KEY = "swan.chart.preferences.v1";
export type ChartPreferences = { minutes: Timeframe };
export const DEFAULT_CHART_PREFERENCES: ChartPreferences = { minutes: 1 };

/** Untrusted device storage contains presentation choices only. */
export function parseChartPreferences(raw: string | null): ChartPreferences {
  let value: Partial<ChartPreferences> = {};
  try {
    const parsed: unknown = JSON.parse(raw ?? "null");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) value = parsed;
  } catch { /* A damaged preference must not prevent the chart from opening. */ }
  return { minutes: value.minutes === 5 || value.minutes === 15 ? value.minutes : 1 };
}
