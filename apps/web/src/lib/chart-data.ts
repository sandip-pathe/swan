/** Analysis only. Never used for order prices, fills or entry permission. */
export type Bar = { opens_at: string; open: string; high: string; low: string; close: string; volume: number | null; state: string; source: string };
export type ChartSession = { opens_at: string; closes_at: string; verified: boolean };
export type Candles = { bars: Bar[]; gaps: string[]; truncated: boolean; unknown_session_dates: string[]; sessions: ChartSession[]; start: string; end: string; as_of: string };
export type Timeframe = 1 | 5 | 15;
export type Point = { time: number; value: number };
const MINUTE = 60_000;

/** Larger bars require every elapsed constituent minute; never bridge a missing minute. */
export function resample(data: Candles, minutes: Timeframe): Candles {
  if (minutes === 1) return data;
  const byTime = new Map(data.bars.map(bar => [Date.parse(bar.opens_at), bar]));
  const bars: Bar[] = [], gaps: string[] = [];
  const left = Date.parse(data.start), right = Date.parse(data.end), now = Date.parse(data.as_of);
  for (const session of data.sessions ?? []) {
    if (!session.verified) continue;
    const opening = Date.parse(session.opens_at), closing = Date.parse(session.closes_at);
    for (let start = opening; start < closing && start <= right && start <= now; start += minutes * MINUTE) {
      if (start < left) continue;
      const end = Math.min(start + minutes * MINUTE, closing);
      const parts: Bar[] = [];
      let missing = false;
      for (let t = start; t < end && t <= now; t += MINUTE) {
        const part = byTime.get(t);
        if (t > right || !part) missing = true;
        else parts.push(part);
      }
      if (missing || !parts.length) { gaps.push(new Date(start).toISOString()); continue; }
      bars.push({
        opens_at: new Date(start).toISOString(), open: parts[0].open,
        high: String(Math.max(...parts.map(bar => Number(bar.high)))),
        low: String(Math.min(...parts.map(bar => Number(bar.low)))),
        close: parts.at(-1)!.close,
        volume: parts.every(bar => bar.volume != null) ? parts.reduce((sum, bar) => sum + bar.volume!, 0) : null,
        state: end > now || parts.some(bar => bar.state === "provisional") ? "provisional" : "elapsed",
        source: parts.some(bar => bar.source === "observed_ltp_snapshots" || bar.source === "derived_mixed") ? "derived_mixed" : "derived_broker_history",
      });
    }
  }
  return { ...data, bars, gaps };
}

/** Split plotted lines so the library cannot visually connect missing intervals. */
export function contiguous(points: Point[], minutes: Timeframe): Point[][] {
  const result: Point[][] = [];
  for (const point of points) {
    const previous = result.at(-1)?.at(-1);
    if (!previous || point.time - previous.time !== minutes * 60) result.push([]);
    result.at(-1)!.push(point);
  }
  return result;
}

export type AverageKind = "EMA" | "SMA";

/** Completed closes only; seed/reset independently for each session and contiguous run. */
export function movingAverage(data: Candles, minutes: Timeframe, kind: AverageKind, period: number): Point[] {
  if (!Number.isInteger(period) || period < 2 || period > 200 || !["EMA", "SMA"].includes(kind)) throw new RangeError("Invalid moving average");
  const output: Point[] = [];
  for (const session of data.sessions ?? []) {
    if (!session.verified) continue;
    const open = Date.parse(session.opens_at), close = Date.parse(session.closes_at);
    const points = data.bars.filter(bar => bar.state !== "provisional" && Date.parse(bar.opens_at) >= open && Date.parse(bar.opens_at) < close)
      .map(bar => ({ time: Date.parse(bar.opens_at) / 1000, value: Number(bar.close) }));
    for (const run of contiguous(points, minutes)) {
      if (run.length < period) continue;
      let value = run.slice(0, period).reduce((sum, point) => sum + point.value, 0) / period;
      output.push({ time: run[period - 1].time, value });
      for (let index = period; index < run.length; index++) {
        const point = run[index];
        value = kind === "EMA" ? value + (2 / (period + 1)) * (point.value - value)
          : value + (point.value - run[index - period].value) / period;
        output.push({ time: point.time, value });
      }
    }
  }
  return output;
}

/** Backward-compatible default study. */
export function ema20(data: Candles, minutes: Timeframe): Point[] {
  return movingAverage(data, minutes, "EMA", 20);
}

/** Wilder RSI(14): 14 changes need 15 completed closes; reset across sessions/gaps. */
export function rsi14(data: Candles, minutes: Timeframe): Point[] {
  const output: Point[] = [];
  for (const session of data.sessions ?? []) {
    if (!session.verified) continue;
    const open = Date.parse(session.opens_at), close = Date.parse(session.closes_at);
    const points = data.bars.filter(bar => bar.state !== "provisional" && Date.parse(bar.opens_at) >= open && Date.parse(bar.opens_at) < close)
      .map(bar => ({ time: Date.parse(bar.opens_at) / 1000, value: Number(bar.close) }));
    for (const run of contiguous(points, minutes)) {
      if (run.length < 15) continue;
      let gain = 0, loss = 0;
      for (let i = 1; i <= 14; i++) {
        const change = run[i].value - run[i - 1].value;
        gain += Math.max(change, 0) / 14;
        loss += Math.max(-change, 0) / 14;
      }
      const value = () => gain === 0 && loss === 0 ? 50 : loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
      output.push({ time: run[14].time, value: value() });
      for (let i = 15; i < run.length; i++) {
        const change = run[i].value - run[i - 1].value;
        gain = (gain * 13 + Math.max(change, 0)) / 14;
        loss = (loss * 13 + Math.max(-change, 0)) / 14;
        output.push({ time: run[i].time, value: value() });
      }
    }
  }
  return output;
}

/** Session HLC3 VWAP. A missing bar or unknown volume invalidates the remaining session. */
export function sessionVwap(data: Candles, minutes: Timeframe): Point[] {
  const out: Point[] = [];
  const byTime = new Map(data.bars.map(bar => [Date.parse(bar.opens_at), bar]));
  for (const session of data.sessions ?? []) {
    if (!session.verified) continue;
    let total = 0, volume = 0;
    for (let t = Date.parse(session.opens_at); t + minutes * MINUTE <= Math.min(Date.parse(data.as_of), Date.parse(session.closes_at)); t += minutes * MINUTE) {
      const bar = byTime.get(t);
      if (!bar || bar.state === "provisional" || bar.volume == null) break;
      total += (Number(bar.high) + Number(bar.low) + Number(bar.close)) / 3 * bar.volume;
      volume += bar.volume;
      if (volume > 0) out.push({ time: t / 1000, value: total / volume });
    }
  }
  return out;
}

/** SMA-seeded DEMA. Matches the backend's 2*period-1 completed-bar warm-up. */
export function doubleEma(data: Candles, minutes: Timeframe, period = 9): Point[] {
  const first = movingAverage(data, minutes, "EMA", period), out: Point[] = [];
  for (const run of contiguous(first, minutes)) {
    if (run.length < period) continue;
    let second = run.slice(0, period).reduce((sum, point) => sum + point.value, 0) / period;
    out.push({ time: run[period - 1].time, value: 2 * run[period - 1].value - second });
    for (let i = period; i < run.length; i++) {
      second += 2 / (period + 1) * (run[i].value - second);
      out.push({ time: run[i].time, value: 2 * run[i].value - second });
    }
  }
  return out;
}
