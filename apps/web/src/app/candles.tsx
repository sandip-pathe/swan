"use client";

import { useOverlayBack } from "@/lib/overlay-back";

import { useEffect, useMemo, useRef, useState } from "react";
import type { IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";
import { money } from "@/lib/paper";
import { resample, type Candles, type Timeframe } from "@/lib/chart-data";
import Icon from "./icons";
import { CHART_PREFERENCES_KEY, DEFAULT_CHART_PREFERENCES, parseChartPreferences } from "@/lib/chart-preferences";
import InstrumentDetails from "./instrument-details";
import InstrumentDepth from "./instrument-depth";
import OrderPreview from "./order-preview";
import UnderlyingContext from "./underlying-context";
import type { MarketQuote, QuoteStatistics, ReferenceContext } from "@/lib/market";

type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
export type ChartContract = { id: string; underlying: string; strike: string; option_type: string; expiry: string; lot_size: number; exchange?: string; tick_size?: string };
const istDate = (date: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
const stamp = (value: string) => new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value));
const timestamp = (value: string) => Math.floor(Date.parse(value) / 1000) as UTCTimestamp;

function PriceChart({ viewKey, data, minutes }: { viewKey: string; data: Candles; minutes: Timeframe }) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const savedRange = useRef<{ from: number; to: number } | null>(null);
  const prices = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumes = useRef<ISeriesApi<"Histogram"> | null>(null);
  const fitted = useRef(false);
  const [ready, setReady] = useState(false);
  const [failure, setFailure] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    let cleanupAppearance = () => {};
    void import("lightweight-charts").then(({ createChart, CandlestickSeries, HistogramSeries, ColorType }) => {
      if (!active || !host.current) return;
      const instance = createChart(host.current, {
        autoSize: true,
        layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#56647b", fontFamily: "Inter, system-ui, sans-serif", fontSize: 12, attributionLogo: true },
        grid: { vertLines: { visible: false }, horzLines: { color: "#edf0f5" } },
        rightPriceScale: { borderVisible: false, scaleMargins: { top: .12, bottom: .25 } },
        timeScale: { timeVisible: true, secondsVisible: false, borderColor: "#e5eaf2", rightOffset: 3, minBarSpacing: 3, tickMarkFormatter: (time: number) => stamp(new Date(time * 1000).toISOString()) },
        localization: { locale: "en-IN", timeFormatter: (time: number) => `${stamp(new Date(time * 1000).toISOString())} IST` },
        handleScroll: { vertTouchDrag: false, horzTouchDrag: true, pressedMouseMove: true, mouseWheel: false },
        handleScale: { pinch: true, mouseWheel: true, axisPressedMouseMove: true },
      });
      const applyAppearance = () => {
        const style = getComputedStyle(document.documentElement);
        instance.applyOptions({ layout: { background: { type: ColorType.Solid, color: style.getPropertyValue("--bg").trim() || "#ffffff" }, textColor: style.getPropertyValue("--muted").trim() || "#626268" }, grid: { horzLines: { color: style.getPropertyValue("--border").trim() || "#e5e5e7" } } });
      };
      applyAppearance();
      const appearanceObserver = new MutationObserver(applyAppearance);
      appearanceObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
      const appearanceMedia = window.matchMedia("(prefers-color-scheme: dark)");
      appearanceMedia.addEventListener("change", applyAppearance);
      cleanupAppearance = () => { appearanceObserver.disconnect(); appearanceMedia.removeEventListener("change", applyAppearance); };
      chart.current = instance;
      try { const saved = JSON.parse(sessionStorage.getItem(`swan.chart.viewport.v1.${viewKey}`) ?? "null"); if (Number.isFinite(saved?.from) && Number.isFinite(saved?.to) && saved.to > saved.from) savedRange.current = saved; } catch { /* Optional view memory. */ }
      instance.timeScale().subscribeVisibleLogicalRangeChange(range => { if (!range || !fitted.current) return; try { sessionStorage.setItem(`swan.chart.viewport.v1.${viewKey}`, JSON.stringify(range)); } catch { /* Chart remains usable. */ } });
      prices.current = instance.addSeries(CandlestickSeries, { upColor: "#087f62", downColor: "#cf3d4f", wickUpColor: "#087f62", wickDownColor: "#cf3d4f", borderVisible: false, priceFormat: { type: "price", precision: 2, minMove: .01 } });
      volumes.current = instance.addSeries(HistogramSeries, { priceScaleId: "volume", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
      volumes.current.priceScale().applyOptions({ scaleMargins: { top: .83, bottom: 0 }, visible: false });
      instance.subscribeCrosshairMove(event => setSelected(typeof event.time === "number" ? event.time : null));
      setReady(true);
    }).catch(() => { if (active) setFailure(true); });
    return () => { active = false; cleanupAppearance(); chart.current?.remove(); chart.current = null; };
  }, []);

  useEffect(() => {
    if (!ready || !prices.current || !volumes.current) return;
    const byTime = new Map(data.bars.map(bar => [timestamp(bar.opens_at), bar]));
    const times = [...new Set([...byTime.keys(), ...data.gaps.map(timestamp)])].sort((a, b) => a - b);
    prices.current.setData(times.map(time => {
      const bar = byTime.get(time);
      return bar ? { time, open: Number(bar.open), high: Number(bar.high), low: Number(bar.low), close: Number(bar.close) } : { time };
    }));
    volumes.current.setData(times.map(time => {
      const bar = byTime.get(time);
      return bar?.volume != null ? { time, value: bar.volume, color: Number(bar.close) >= Number(bar.open) ? "#087f6245" : "#cf3d4f45" } : { time };
    }));
    if (!fitted.current && data.bars.length) { if (savedRange.current) chart.current?.timeScale().setVisibleLogicalRange(savedRange.current); else chart.current?.timeScale().fitContent(); fitted.current = true; }
  }, [data, ready]);

  const bar = selected == null ? data.bars.at(-1) : data.bars.find(row => timestamp(row.opens_at) === selected);
  return <>
    <div className="candle-readout" aria-label="Selected candle details"><span>{bar ? `${stamp(bar.opens_at)} IST` : "Select a candle"}</span><dl>{([ ["Open", "open"], ["High", "high"], ["Low", "low"], ["Close", "close"] ] as const).map(([label, key]) => <div key={key}><dt>{label}</dt><dd>{bar ? Number(bar[key]).toFixed(2) : "?"}</dd></div>)}</dl></div>
    <div className="candle-canvas" ref={host} role="img" aria-label={`${minutes}-minute candlestick price chart. Drag to inspect prices; pinch or scroll to zoom.`} />
    {failure && <p role="alert" className="error">The chart could not load.</p>}
  </>;
}

export default function ContractChart({ instrument, quoteDate, request, onBack, marketLabel, backLabel = "Option chain", quote = null, statistics, quoteError, reference, quoteMaxAge = 10, quoteBusy = false, onRefreshQuote }: { instrument: ChartContract; quoteDate?: string; request: Request; onBack: () => void; marketLabel: string; backLabel?: string; quote?: MarketQuote | null; statistics?: QuoteStatistics; quoteError?: string | null; reference?: ReferenceContext; quoteMaxAge?: number; quoteBusy?: boolean; onRefreshQuote?: () => void }) {
  const today = istDate(new Date());
  const maximum = instrument.expiry < today ? instrument.expiry : today;
  const initial = quoteDate ? istDate(new Date(quoteDate)) : maximum;
  const [date, setDate] = useState(initial > maximum ? maximum : initial);
  const [surface, setSurface] = useState("chart");
  const [buyOpen, setBuyOpen] = useState(false);
  const buyDialog = useRef<HTMLDialogElement>(null);
  const buyTitle = useRef<HTMLHeadingElement>(null);
  const orderTrigger = useRef<HTMLButtonElement>(null);
  function closeBuy() { buyDialog.current?.close(); setBuyOpen(false); }
  useOverlayBack(buyOpen, closeBuy);
  useEffect(() => {
    const dialog = buyDialog.current;
    if (!dialog) return;
    if (buyOpen && !dialog.open) {
      dialog.showModal();
      requestAnimationFrame(() => buyTitle.current?.focus());
    } else if (!buyOpen && dialog.open) dialog.close();
  }, [buyOpen]);

  const [preferences, setPreferences] = useState(DEFAULT_CHART_PREFERENCES);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);
  const { minutes } = preferences;
  useEffect(() => {
    try { setPreferences(parseChartPreferences(localStorage.getItem(CHART_PREFERENCES_KEY))); } catch { /* Storage may be disabled. */ }
    setPreferencesLoaded(true);
  }, []);
  useEffect(() => {
    if (!preferencesLoaded) return;
    try { localStorage.setItem(CHART_PREFERENCES_KEY, JSON.stringify(preferences)); } catch { /* Charts still work without device storage. */ }
  }, [preferences, preferencesLoaded]);
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
  const headerPrice = quote?.last_price ?? latest?.close;
  const headerCaption = quote?.last_price != null
    ? `Observed ${new Date(quote.timestamp).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} IST`
    : latest ? `${stamp(latest.opens_at)} IST · candle close` : "No saved price";
  return <section className="panel contract-chart" aria-label="Contract chart">
    <div className="contract-workspace"><div className="contract-analysis">
    <button className="text-button chart-back" onClick={onBack}><span aria-hidden="true">←</span>{backLabel}</button>
    <div className="contract-chart-heading"><div><h2>{instrument.underlying} {Number(instrument.strike).toLocaleString("en-IN", { maximumFractionDigits: 2 })} {instrument.option_type === "CALL" ? "Call · CE" : "Put · PE"}</h2><p>{instrument.expiry} · 1 lot = {instrument.lot_size} units</p></div><div className="chart-heading-actions"><div className="chart-last"><strong>{headerPrice == null ? "—" : money(headerPrice)}</strong><span>{headerCaption}</span></div><button ref={orderTrigger} className="chart-buy-button" aria-haspopup="dialog" aria-controls="buy-dialog" onClick={() => setBuyOpen(true)}>Buy</button></div></div>
    <UnderlyingContext underlying={instrument.underlying} reference={reference} maxAge={quoteMaxAge} error={!!quoteError} />
    {quoteError && <p className="notice error" role="alert">{quoteError} Saved quotes may be out of date.</p>}
    {onRefreshQuote && <button className="secondary quote-refresh" disabled={quoteBusy} onClick={onRefreshQuote}><Icon name="refresh" />{quoteBusy ? "Updating price…" : "Update price"}</button>}
    <div className="instrument-tabs" role="group" aria-label="Instrument details"><button className="secondary" aria-pressed={surface === "chart"} onClick={() => setSurface("chart")}>Chart</button><button className="secondary" aria-pressed={surface === "depth"} onClick={() => setSurface("depth")}>Buyers &amp; sellers</button><button className="secondary" aria-pressed={surface === "details"} onClick={() => setSurface("details")}>Details</button></div>
    {surface === "depth" && <InstrumentDepth quote={quote} statistics={statistics} error={quoteError} maxAge={quoteMaxAge} />}
    {surface === "details" && <InstrumentDetails instrument={instrument} quote={quote} statistics={statistics} maxAge={quoteMaxAge} error={quoteError} />}
    <div hidden={surface !== "chart"}>
    <div className="chart-toolbar" aria-label="Chart controls">
      <div className="chart-timeframes" role="group" aria-label="Chart timeframe">{([1, 5, 15] as Timeframe[]).map(value => <button key={value} className="secondary" aria-pressed={minutes === value} onClick={() => setPreferences(current => ({ ...current, minutes: value }))}>{value}m</button>)}</div>
      <label className="chart-date"><span className="sr-only">Chart session</span><input aria-label="Chart session" type="date" value={date} max={maximum} disabled={busy} onChange={event => { if (event.target.value) { setDate(event.target.value); setData(null); setUpdated(null); setMessage(null); } }} /></label>
      <button className="secondary chart-history-refresh" disabled={busy || !canRefresh} onClick={refreshHistory}><Icon name="refresh" />{busy ? "Loading…" : "Update candles"}</button>
    </div>
    <p className="chart-status">{marketLabel}</p>
    {!validRange || session && Date.parse(session.opens_at) > Date.parse(end) ? <p className="chart-empty">This date hasn’t started yet.</p> : view == null ? <p className="chart-empty" role="status">Loading chart…</p> : !view.bars.length ? <div className="chart-empty"><strong>No candles saved for this date.</strong><p>Tap Update candles to check for available history.</p></div> : <PriceChart viewKey={`${instrument.id}:${date}:${minutes}`} key={`${instrument.id}:${date}:${minutes}`} data={view} minutes={minutes} />}
    {error && <p className="notice error" role="alert">{error}</p>}{message && <p role="status" className="chart-feedback">{message}</p>}
    </div></div></div>
    <dialog id="buy-dialog" ref={buyDialog} className="buy-dialog" aria-labelledby="buy-dialog-title" onClose={() => { setBuyOpen(false); requestAnimationFrame(() => orderTrigger.current?.focus()); }}>
      <div className="buy-dialog-header"><div><p className="eyebrow">PAPER ORDER</p><h2 id="buy-dialog-title" ref={buyTitle} tabIndex={-1}>Buy {instrument.underlying} {Number(instrument.strike).toLocaleString("en-IN", { maximumFractionDigits: 2 })} {instrument.option_type === "CALL" ? "CE" : "PE"}</h2></div><button className="secondary buy-dialog-close" aria-label="Close buy window" onClick={closeBuy}>×</button></div>
      <OrderPreview visible={buyOpen} instrument={instrument} quote={quote} request={request} />
    </dialog>
  </section>;
}
