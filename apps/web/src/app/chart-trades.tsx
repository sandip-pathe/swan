"use client";

import { useEffect, useState } from "react";
import type { Candles, Timeframe } from "@/lib/chart-data";
import { tradeMarkers, type ChartTrades } from "@/lib/chart-trades";
import { money, time, words } from "@/lib/paper";
import OrderHistory from "./order-history";

type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
export function useChartTrades(instrument: string, day: string, request: Request, enabled: boolean) {
  const [data, setData] = useState<ChartTrades | null>(null);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController(); let active = true, busy = false;
    async function load() {
      if (busy || document.hidden) return;
      busy = true;
      try {
        const result = await request(`/api/paper/chart-trades?${new URLSearchParams({ instrument_id: instrument, day })}`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(12000)])) as ChartTrades;
        if (active) { setData(result); setError(false); setNow(Date.now()); }
      } catch { if (active) setError(true); }
      finally { busy = false; }
    }
    load(); const polling = setInterval(load, 5000);
    document.addEventListener("visibilitychange", load);
    return () => { active = false; controller.abort(); clearInterval(polling); document.removeEventListener("visibilitychange", load); };
  }, [instrument, day, request, enabled, refresh]);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const matching = data?.instrument_id === instrument && data.day === day ? data : null;
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  const fresh = enabled && !error && matching != null && now - Date.parse(matching.as_of) >= 0 && now - Date.parse(matching.as_of) < 15000;
  return { data: matching, fresh, levelsCurrent: fresh && matching?.current_day && today === day, error, refresh: () => setRefresh(value => value + 1) };
}

export function ChartTradeControls({ state, candles, minutes, shown, onToggle, selected, onSelect }: { state: ReturnType<typeof useChartTrades>; candles: Candles | null; minutes: Timeframe; shown: boolean; onToggle: () => void; selected: string; onSelect: (id: string) => void }) {
  const { data } = state;
  const plotted = data && candles ? tradeMarkers(candles, minutes, data.fills).length : 0;
  const position = data?.positions.find(item => item.id === selected) ?? data?.positions[0];
  const exits = data?.exit_orders.filter(item => item.position_id === position?.id) ?? [];
  return <div className="chart-trade-controls" aria-label="Your chart trades">
    <div className="chart-trade-actions"><button className="secondary" aria-pressed={shown} onClick={onToggle}>{shown ? "Hide my trades" : "Show my trades"}</button><button className="text-button" onClick={state.refresh}>Refresh trade overlays</button></div>
    {state.error ? <p role="alert">Trade overlays could not be updated. Current position lines are hidden.</p> : !data ? <p role="status">Loading your recorded trades…</p> : !state.fresh ? <p role="status">Trade snapshot is stale. Current position lines are hidden.</p> : null}
    {shown && data && <>
      <p className="chart-method">B ↑ buy fill · S ↓ sell fill. Markers use actual fill prices. Lines show current entry, stop and target settings, not guaranteed exits.</p>
      {!data.current_day && <p className="chart-method">Historical date: recorded fills only. Current position levels are hidden.</p>}
      {data.current_day && !data.positions.length && <p className="chart-method">No open position levels for this contract.</p>}
      {state.levelsCurrent && data.positions.length > 1 && <label>Position levels<select value={position?.id} onChange={event => onSelect(event.target.value)}>{data.positions.map((item, index) => <option key={item.id} value={item.id}>Position {index + 1} · {item.remaining_quantity} units open</option>)}</select></label>}
      {state.levelsCurrent && position && <div className="chart-position-levels"><strong>{position.remaining_quantity} units open{position.pending_exit ? ` · Exit pending: ${words(position.pending_exit)}` : ""}</strong><dl className="execution-values"><div><dt>Average entry</dt><dd>{money(position.average_price)}</dd></div><div><dt>Stop</dt><dd>{money(position.stop_loss)}</dd></div><div><dt>Target</dt><dd>{money(position.target)}</dd></div></dl><p className="chart-method">{exits.length ? `${exits.length} pending exit order${exits.length === 1 ? "" : "s"} recorded. Execution still requires monitoring and fresh depth.` : "No pending exit order is recorded in this snapshot."} Levels may be outside the visible price range.</p><OrderHistory orderId={position.entry_order_id} label="Position order history" /></div>}
      {data.fills_truncated && <p role="status">Showing the latest 200 fills for this date.</p>}
      {(data.positions_truncated || data.exits_truncated) && <p role="status">Some position or exit orders are outside this view's limit. This view cannot confirm full exit coverage.</p>}
      {!data.fills.length ? <p className="chart-method">No recorded fills for this contract and date.</p> : <details><summary>Recorded fills · {data.fills.length}</summary><p>{plotted} fills align with displayed candles. {data.fills.length - plotted} have no matching displayed candle and are listed here only.</p>{data.fills.map(fill => <article className="chart-fill-row" key={fill.id}><strong>{words(fill.side)} · {fill.quantity} units · {money(fill.price)}</strong><span>{time(fill.timestamp)} IST</span><OrderHistory orderId={fill.order_id} /></article>)}</details>}
      <p className="chart-method">Account snapshot {time(data.as_of)} IST. Trade annotations never change candle data.</p>
    </>}
  </div>;
}
