"use client";

import { useEffect, useRef, useState } from "react";
import { money, time } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";
import OrderHistory from "./order-history";

type Report = { day: string; as_of: string; day_ended: boolean; status: string; fill_count: number; buy_units: number; sell_units: number; open_units_at_cutoff: number | null; cash_opening: string | null; cash_at_cutoff: string | null; cash_movement: string | null; fees: string | null; realized_pnl: string | null; activity_complete: boolean; activity: Record<string, number> | null; fills_truncated: boolean; next_fills_before?: string | null; fills: { id: string; order_id: string; side: string; quantity: number; price: string; fees: string; timestamp: string; instrument: { underlying: string; strike: string; option_type: string; expiry: string } | null }[] };
function todayIST() { return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date()); }
const stages: Record<string, string> = { proposals_wait: "Wait proposals", reviews_rejected: "Declined reviews", evaluations_failed: "Failed evaluations", strategies_accepted: "Accepted strategies", unclassified: "Other recorded outcomes" };

export default function DailyReport() {
  const request = usePaperRequest();
  const [day, setDay] = useState(todayIST);
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<Report | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pageBusy, setPageBusy] = useState(false);
  const [pageError, setPageError] = useState(false);
  const generation = useRef(0);
  const pageController = useRef<AbortController | null>(null);
  useEffect(() => {
    if (!request || !day) return;
    const controller = new AbortController(); let current = true;
    const requestGeneration = ++generation.current;
    pageController.current?.abort(); setPageBusy(false); setPageError(false);
    setData(null); setError(false); setBusy(true);
    request(`/api/paper/daily-report?${new URLSearchParams({ day })}`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]))
      .then(result => {
        if (!Array.isArray((result as Partial<Report>).fills) || typeof (result as Partial<Report>).day !== "string") throw new Error("Report response is incomplete.");
        if (current) setData(result as Report);
      })
      .catch(() => { if (current) setError(true); })
      .finally(() => { if (current) setBusy(false); });
    return () => { current = false; generation.current++; controller.abort(); pageController.current?.abort(); };
  }, [request, day, refresh]);
  async function loadOlderFills() {
    if (!request || !data?.next_fills_before || pageBusy) return;
    const current = generation.current;
    const controller = new AbortController(); pageController.current = controller;
    setPageBusy(true); setPageError(false);
    try {
      const result = await request(`/api/paper/daily-report?${new URLSearchParams({ day: data.day, fills_before: data.next_fills_before })}`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)])) as Report;
      if (current === generation.current) setData(previous => previous ? { ...previous, fills: [...previous.fills, ...result.fills.filter(fill => !previous.fills.some(old => old.id === fill.id))], next_fills_before: result.next_fills_before, fills_truncated: result.fills_truncated } : previous);
    } catch { if (current === generation.current) setPageError(true); }
    finally { if (current === generation.current) setPageBusy(false); }
  }
  return <section className="panel daily-report" aria-label="Daily results">
    <div className="panelhead"><div><p className="eyebrow">YOUR RESULTS</p><h2>How did today go?</h2><p>Closed trades and costs. Open trades are not included in this total.</p></div><button className="text-button" disabled={busy || !day} onClick={() => setRefresh(value => value + 1)}>{busy ? "Updating…" : "Update"}</button></div>
    <label className="report-day">Choose a day<input type="date" value={day} max={todayIST()} onChange={event => setDay(event.target.value)} /></label>
    {busy && <div role="status" aria-label="Loading daily results" className="history-skeleton"><i /><i /><i /></div>}
    {error && <p className="report-error" role="alert">Your results aren’t available right now. <button className="text-button" onClick={() => setRefresh(value => value + 1)}>Try again</button></p>}
    {data && <>
      <p className="muted report-asof">{data.day_ended ? "Full day" : "So far today"} · Updated {time(data.as_of)} IST</p>
      {data.status !== "RECONCILED" && <p className="notice error" role="alert">Accounting records need attention. Financial totals are unavailable; listed fills include dated records only.</p>}
      <dl className="execution-values report-metrics"><div><dt>Profit / loss from closed trades</dt><dd>{money(data.realized_pnl)}</dd></div><div><dt>Trading costs</dt><dd>{money(data.fees)}</dd></div><div><dt>Fills</dt><dd>{data.fill_count}</dd></div><div><dt>Still open at day end</dt><dd>{data.open_units_at_cutoff == null ? "Unavailable" : `${data.open_units_at_cutoff} units`}</dd></div></dl>
      <details className="report-details"><summary>More about today</summary><p className="muted">Profit/loss includes recorded entry costs and exit fees. Cash movement also includes funding and purchases, so it is not the same as profit. Open trades are not counted.</p><dl className="execution-values"><div><dt>Cash added or used</dt><dd>{money(data.cash_movement)}</dd></div><div><dt>Bought / sold</dt><dd>{data.buy_units} / {data.sell_units} units</dd></div><div><dt>Cash at start</dt><dd>{money(data.cash_opening)}</dd></div><div><dt>Cash at end</dt><dd>{money(data.cash_at_cutoff)}</dd></div></dl><p className="muted">Saved decision counts describe recorded stages, not unique trades.</p><dl className="execution-values">{Object.entries(stages).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{data.activity?.[key] ?? "Unavailable"}</dd></div>)}</dl></details>
      <h3>Trades today</h3>
      {!data.fills.length ? <p className="empty-state">No trades filled on this day.</p> : <ol className="agent-activity-list">{data.fills.map(fill => <li className="execution-card" key={fill.id}><h4>{fill.side === "BUY" ? "Bought" : "Sold"} {fill.quantity} units</h4><p>{fill.instrument ? `${fill.instrument.underlying} ${fill.instrument.strike} ${fill.instrument.option_type} / ${fill.instrument.expiry}` : "Contract details unavailable"}</p><p>{money(fill.price)} each · Costs {money(fill.fees)}</p><p className="muted">{time(fill.timestamp)} IST</p><OrderHistory orderId={fill.order_id} /></li>)}</ol>}
      {pageError && <p role="alert">Older fills could not be loaded. Current fills are still shown.</p>}
      {data.next_fills_before && <button className="secondary" disabled={pageBusy} onClick={loadOlderFills}>{pageBusy ? "Loading older fills..." : pageError ? "Retry older fills" : "Load older fills"}</button>}
      {data.fills_truncated && !data.next_fills_before && <p className="notice">Additional fills are unavailable in this view.</p>}
    </>}
  </section>;
}
