import type { AverageKind, Timeframe } from "./chart-data";

export const CHART_PREFERENCES_KEY = "swan.chart.preferences.v1";
export const AVERAGE_PERIODS = [9, 20, 50, 100, 200] as const;
export type ChartPreferences = { minutes: Timeframe; mode: "candles" | "line"; showAverage: boolean; averageKind: AverageKind; averagePeriod: number };
export const DEFAULT_CHART_PREFERENCES: ChartPreferences = { minutes: 1, mode: "candles", showAverage: false, averageKind: "EMA", averagePeriod: 20 };

/** Untrusted device storage contains presentation choices only. */
export function parseChartPreferences(raw: string | null): ChartPreferences {
  let value: Partial<ChartPreferences> = {};
  try {
    const parsed: unknown = JSON.parse(raw ?? "null");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) value = parsed;
  } catch { /* A damaged preference must not prevent the chart from opening. */ }
  return {
    minutes: value.minutes === 5 || value.minutes === 15 ? value.minutes : 1,
    mode: value.mode === "line" ? "line" : "candles",
    showAverage: value.showAverage === true,
    averageKind: value.averageKind === "SMA" ? "SMA" : "EMA",
    averagePeriod: AVERAGE_PERIODS.some(period => period === value.averagePeriod) ? value.averagePeriod! : 20,
  };
}
