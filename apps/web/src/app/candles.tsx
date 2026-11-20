"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { IChartApi, ISeriesApi, SeriesDefinition, UTCTimestamp } from "lightweight-charts";
import { money } from "@/lib/paper";
import { contiguous, ema20, resample, type Candles, type Point, type Timeframe } from "@/lib/chart-data";
import Icon from "./icons";

type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
export type ChartContract = { id: string; underlying: string; strike: string; option_type: string; expiry: string; lot_size: number };
const istDate = (date: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
const stamp = (value: string) => new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value));
const timestamp = (value: string) => Math.floor(Date.parse(value) / 1000) as UTCTimestamp;

function PriceChart({ data, minutes, mode, showEma, onToggleEma }: { data: Candles; minutes: Timeframe; mode: "candles" | "line"; showEma: boolean; onToggleEma: () => void }) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const prices = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumes = useRef<ISeriesApi<"Histogram"> | null>(null);
  const lineDefinition = useRef<SeriesDefinition<"Line"> | null>(null);
  const lines = useRef<ISeriesApi<"Line">[]>([]);
  const averages = useRef<ISeriesApi<"Line">[]>([]);
  const ema = useMemo(() => ema20(data, minutes), [data, minutes]);
  const fitted = useRef(false);
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    void import("lightweight-charts").then(({ createChart, CandlestickSeries, HistogramSeries, LineSeries, ColorType }) => {
      if (!active || !host.current) return;
      const instance = createChart(host.current, {
        autoSize: true,
        layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#56647b", fontFamily: "IBM Plex Sans, sans-serif", fontSize: 12, attributionLogo: true },
        grid: { vertLines: { visible: false }, horzLines: { color: "#edf0f5" } },
        rightPriceScale: { borderVisible: false, scaleMargins: { top: .12, bottom: .25 } },
        timeScale: { timeVisible: true, secondsVisible: false, borderColor: "#e5eaf2", rightOffset: 3, minBarSpacing: 3, tickMarkFormatter: (time: number) => stamp(new Date(time * 1000).toISOString()) },
        localization: { locale: "en-IN", timeFormatter: (time: number) => `${stamp(new Date(time * 1000).toISOString())} IST` },
        handleScroll: { vertTouchDrag: false, horzTouchDrag: true, pressedMouseMove: true, mouseWheel: false },
        handleScale: { pinch: true, mouseWheel: true, axisPressedMouseMove: true },
      });
      chart.current = instance;
      lineDefinition.current = LineSeries;
      prices.current = instance.addSeries(CandlestickSeries, { upColor: "#087f62", downColor: "#cf3d4f", wickUpColor: "#087f62", wickDownColor: "#cf3d4f", borderVisible: false, priceFormat: { type: "price", precision: 2, minMove: .01 } });
      volumes.current = instance.addSeries(HistogramSeries, { priceScaleId: "volume", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
      volumes.current.priceScale().applyOptions({ scaleMargins: { top: .83, bottom: 0 }, visible: false });
      instance.subscribeCrosshairMove(event => {
        setSelected(typeof event.time === "number" ? event.time : null);
      });
      setReady(true);
    }).catch(() => { if (active) setFailure(true); });
    return () => { active = false; chart.current?.remove(); chart.current = null; };
  }, []);

  useEffect(() => {
    if (!ready || !prices.current || !volumes.current) return;
    const byTime = new Map(data.bars.map(bar => [timestamp(bar.opens_at), bar]));
    const times = [...new Set([...byTime.keys(), ...data.gaps.map(timestamp)])].sort((a, b) => a - b);
    prices.current.applyOptions({ visible: mode === "candles" });
    prices.current.setData(times.map(time => {
      const bar = byTime.get(time);
      return bar ? { time, open: Number(bar.open), high: Number(bar.high), low: Number(bar.low), close: Number(bar.close) } : { time };
    }));
    volumes.current.setData(times.map(time => {
      const bar = byTime.get(time);
      return bar?.volume != null ? { time, value: bar.volume, color: Number(bar.close) >= Number(bar.open) ? "#087f6245" : "#cf3d4f45" } : { time };
    }));
    function syncLines(series: ISeriesApi<"Line">[], runs: Point[][], color: string, visible: boolean, dashed = false) {
      const instance = chart.current, definition = lineDefinition.current;
      if (!instance || !definition) return;
      while (series.length > runs.length) instance.removeSeries(series.pop()!);
      runs.forEach((run, index) => {
        if (!series[index]) series.push(instance.addSeries(definition, { color, lineWidth: 2, lineStyle: dashed ? 2 : 0, priceLineVisible: false, lastValueVisible: false, pointMarkersVisible: true, pointMarkersRadius: 2 }));
        series[index].applyOptions({ visible });
        series[index].setData(run.map(point => ({ ...point, time: point.time as UTCTimestamp })));
      });
    }
    syncLines(lines.current, contiguous(data.bars.map(bar => ({ time: timestamp(bar.opens_at), value: Number(bar.close) })), minutes), "#2455e6", mode === "line");
    syncLines(averages.current, showEma ? contiguous(ema, minutes) : [], "#9a5b09", showEma, true);
    if (!fitted.current && data.bars.length) { chart.current?.timeScale().fitContent(); fitted.current = true; }
  }, [data, ready, mode, showEma, ema, minutes]);

  const bar = selected == null ? data.bars.at(-1) : data.bars.find(row => timestamp(row.opens_at) === selected);
  const average = bar ? ema.find(point => point.time === timestamp(bar.opens_at))?.value : undefined;
  const zoom = (factor: number) => {
    const scale = chart.current?.timeScale();
    const range = scale?.getVisibleLogicalRange();
    if (scale && range) { const middle = (range.from + range.to) / 2; const half = (range.to - range.from) * factor / 2; scale.setVisibleLogicalRange({ from: middle - half, to: middle + half }); }
  };
  return <>
    <div className="candle-readout" aria-label="Selected candle details"><span>{bar ? `${stamp(bar.opens_at)} IST` : "Select a candle"}</span><dl>{([ ["O", "open"], ["H", "high"], ["L", "low"], ["C", "close"] ] as const).map(([label, key]) => <div key={key}><dt>{label}</dt><dd>{bar ? Number(bar[key]).toFixed(2) : "—"}</dd></div>)}</dl><small>Vol {bar?.volume?.toLocaleString("en-IN") ?? "unavailable"}{showEma ? ` · EMA 20 ${average == null ? "unavailable — needs 20 completed candles after each gap" : average.toFixed(2)}` : ""}</small></div>
    <div className="candle-canvas" ref={host} role="img" aria-label={`${minutes}-minute ${mode === "candles" ? "candlestick" : "line"} price chart. Equivalent values are available in Candle data below.`} />
    {failure && <p role="alert" className="error">The chart could not load. Candle values are available below.</p>}
    <div className="chart-tools"><button className="secondary ema-toggle" aria-pressed={showEma} onClick={onToggleEma}>EMA 20</button><div><button className="secondary" aria-label="Zoom out chart" onClick={() => zoom(1.4)} disabled={!ready}>−</button><button className="secondary" aria-label="Zoom in chart" onClick={() => zoom(.7)} disabled={!ready}>+</button><button className="secondary" onClick={() => chart.current?.timeScale().fitContent()} disabled={!ready}>Fit</button></div></div>
  </>;
}

export default function ContractChart({ instrument, quoteDate, request, onBack, marketLabel, backLabel = "Option chain" }: { instrument: ChartContract; quoteDate?: string; request: Request; onBack: () => void; marketLabel: string; backLabel?: string }) {
  const today = istDate(new Date());
  const maximum = instrument.expiry < today ? instrument.expiry : today;
  const initial = quoteDate ? istDate(new Date(quoteDate)) : maximum;
  const [date, setDate] = useState(initial > maximum ? maximum : initial);
  const [minutes, setMinutes] = useState<Timeframe>(1);
  const [mode, setMode] = useState<"candles" | "line">("candles");
  const [showEma, setShowEma] = useState(false);
  const [data, setData] = useState<Candles | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [updated, setUpdated] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const start = `${date}T00:00:00+05:30`;
  const dayEnd = Date.parse(`${date}T23:59:00+05:30`);
  const end = new Date(Math.min(dayEnd, Math.floor(Date.now() / 60000) * 60000)).toISOString();
  const validRange = Date.parse(start) < Date.parse(end);
  const session = data?.sessions?.find(session => session.verified);
  const historyEnd = session ? new Date(Math.min(Date.parse(session.closes_at), Date.parse(end))).toISOString() : null;
  const canRefresh = session != null && historyEnd != null && Date.parse(session.opens_at) < Date.parse(historyEnd);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        if (!navigator.onLine) throw new Error("You’re offline. These prices may be out of date.");
        if (!document.hidden && validRange) {
          const result = await request(`/api/market/candles?${new URLSearchParams({ instrument_id: instrument.id, start, end })}`, "GET", controller.signal) as Candles;
          if (active) { setData(result); setError(null); setUpdated(new Date().toISOString()); }
        }
      } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : "Candles are unavailable."); }
      finally { if (active) timer = setTimeout(load, 5000); }
    }
    void load();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [request, instrument.id, start, end, validRange, refresh]);

  async function refreshHistory() {
    if (busy || !canRefresh || !session || !historyEnd) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      await request("/api/market/history/refresh", "POST", undefined, { instrument_id: instrument.id, interval: "ONE_MINUTE", start: session.opens_at, end: historyEnd });
      setRefresh(value => value + 1); setMessage("Latest available candles retrieved.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "History is unavailable. Try again shortly."); }
    finally { setBusy(false); }
  }
  const view = useMemo(() => data ? resample(data, minutes) : null, [data, minutes]);
  const latest = view?.bars.at(-1);
  return <section className="panel contract-chart" aria-label="Contract chart">
    <button className="text-button chart-back" onClick={onBack}><span aria-hidden="true">←</span>{backLabel}</button>
    <div className="contract-chart-heading"><div><h2>{instrument.underlying} {instrument.strike} {instrument.option_type === "CALL" ? "CE" : "PE"}</h2><p>{instrument.expiry} expiry · Lot {instrument.lot_size}</p></div><div className="chart-last"><strong>{latest ? money(latest.close) : "—"}</strong><span>{latest ? `${stamp(latest.opens_at)} IST · candle close` : "No candle price"}</span></div></div>
    <div className="chart-controls"><label><span className="sr-only">Session</span><input aria-label="Chart session" type="date" value={date} max={maximum} disabled={busy} onChange={event => { if (event.target.value) { setDate(event.target.value); setData(null); setUpdated(null); setMessage(null); } }} /></label><button className="secondary" disabled={busy || !canRefresh} onClick={refreshHistory}><Icon name="refresh" />{busy ? "Loading…" : "Get candles"}</button></div>
    <div className="chart-options"><div className="timeframes" role="group" aria-label="Chart timeframe">{([1, 5, 15] as Timeframe[]).map(value => <button key={value} className="secondary" aria-pressed={minutes === value} onClick={() => setMinutes(value)}>{value}m</button>)}</div><label className="chart-view"><span className="sr-only">Chart style</span><select aria-label="Chart style" value={mode} onChange={event => setMode(event.target.value as "candles" | "line")}><option value="candles">Candles</option><option value="line">Line</option></select></label></div>
    <p className="chart-status">{marketLabel} · {date}{updated ? ` · Checked ${stamp(updated)} IST` : ""}</p>
    {error && <p className="notice error" role="alert">{error}</p>}{message && <p role="status" className="chart-feedback">{message}</p>}
    {!validRange || session && Date.parse(session.opens_at) > Date.parse(end) ? <p className="chart-empty">This session has not started.</p> : view == null ? <p className="chart-empty" role="status">Loading candles…</p> : !view.bars.length ? <div className="chart-empty"><Icon name="markets" /><strong>{!session ? "Trading hours unavailable" : data?.bars.length ? "Not enough data for this timeframe" : "No candles saved for this session"}</strong><p>{!session ? "Choose another session. Trading hours must be verified before retrieving history." : data?.bars.length ? "Try 1m or Get candles to fill missing history. Larger candles need a verified session and every elapsed minute." : "Tap Get candles to load the broker’s available price history."}</p></div> : <PriceChart key={`${instrument.id}:${date}:${minutes}`} data={view} minutes={minutes} mode={mode} showEma={showEma} onToggleEma={() => setShowEma(value => !value)} />}
    {view && <p className="chart-coverage">{view.gaps.length ? `${view.gaps.length} ${minutes === 1 ? "minutes" : "intervals"} have missing candles. Gaps are left blank. ` : ""}{view.bars.some(bar => bar.source === "observed_ltp_snapshots" || bar.source === "derived_mixed") ? "Stream candles use observed prices; volume is unavailable until history arrives. " : ""}{view.bars.some(bar => bar.state === "provisional") ? "The current candle can change. " : ""}{view.unknown_session_dates.length ? "Trading hours could not be verified for this date. " : ""}{view.truncated ? "Some saved records are outside this view’s limit. " : ""}</p>}
    {minutes > 1 && <p className="chart-method">{minutes}m candles combine saved 1m candles, aligned to verified trading hours. Missing minutes leave a gap.</p>}
    {showEma && <details className="chart-explainer"><summary>About EMA 20</summary><p className="chart-method">The dashed amber line averages completed candle closes. It needs 20 consecutive candles and restarts each session or after a gap. Forming candles are excluded. Calculation: start with a 20-candle average, then give each new close a weight of 2/21.</p></details>}
    {!!view?.bars.length && <details className="candle-data"><summary>Candle data · latest 20 candles</summary>{view.bars.slice(-20).reverse().map(bar => <article key={bar.opens_at}><strong>{stamp(bar.opens_at)} IST</strong><span>{bar.state === "provisional" ? "Forming" : "Elapsed"} · {bar.source === "observed_ltp_snapshots" ? "Observed prices" : bar.source === "derived_mixed" ? "Combined observed prices" : bar.source === "derived_broker_history" ? "Combined broker history" : "Broker history"}</span><dl>{([ ["Open", bar.open], ["High", bar.high], ["Low", bar.low], ["Close", bar.close], ["Volume", bar.volume?.toLocaleString("en-IN") ?? "Unavailable"] ]).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></article>)}</details>}
    <p className="chart-attribution">Charts by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView Lightweight Charts™</a> · Copyright © 2025 TradingView, Inc.</p>
  </section>;
}
