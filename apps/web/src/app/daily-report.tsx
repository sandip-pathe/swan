"use client";

import { useEffect, useState } from "react";
import { money, time } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";
import OrderHistory from "./order-history";

type Report = { day: string; as_of: string; day_ended: boolean; status: string; fill_count: number; buy_units: number; sell_units: number; open_units_at_cutoff: number | null; cash_opening: string | null; cash_at_cutoff: string | null; cash_movement: string | null; fees: string | null; realized_pnl: string | null; activity_complete: boolean; activity: Record<string, number> | null; fills_truncated: boolean; fills: { id: string; order_id: string; side: string; quantity: number; price: string; fees: string; timestamp: string; instrument: { underlying: string; strike: string; option_type: string; expiry: string } | null }[] };
function todayIST() { return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date()); }
const stages: Record<string, string> = { proposals_wait: "Wait proposals", reviews_rejected: "Declined reviews", evaluations_failed: "Failed evaluations", strategies_accepted: "Accepted strategies", unclassified: "Other recorded outcomes" };

export default function DailyReport() {
  const request = usePaperRequest();
  const [day, setDay] = useState(todayIST);
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<Report | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!request || !day) return;
    const controller = new AbortController(); let current = true;
    setData(null); setError(false); setBusy(true);
    request(`/api/paper/daily-report?${new URLSearchParams({ day })}`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]))
      .then(result => { if (current) setData(result as Report); })
      .catch(() => { if (current) setError(true); })
      .finally(() => { if (current) setBusy(false); });
    return () => { current = false; controller.abort(); };
  }, [request, day, refresh]);
  return <section className="panel daily-report" aria-label="Daily report">
    <div className="panelhead"><div><h2>Daily report</h2><p>Recorded paper trades and account movements.</p></div><button className="secondary" disabled={busy || !day} onClick={() => setRefresh(value => value + 1)}>Refresh report</button></div>
    <label>Report date (IST)<input type="date" value={day} max={todayIST()} onChange={event => setDay(event.target.value)} /></label>
    {busy && <p role="status">Loading daily report...</p>}
    {error && <p className="notice error" role="alert">The report could not be loaded. <button className="secondary" onClick={() => setRefresh(value => value + 1)}>Retry report</button></p>}
    {data && <>
      <p className="muted">{data.day_ended ? "Completed calendar day" : "Today so far"} - Snapshot {time(data.as_of)} IST</p>
      {data.status !== "RECONCILED" && <p className="notice error" role="alert">Accounting records need attention. Financial totals are unavailable; listed fills include dated records only.</p>}
      <dl className="execution-values"><div><dt>Net realized P&amp;L</dt><dd>{money(data.realized_pnl)}</dd></div><div><dt>Recorded fees</dt><dd>{money(data.fees)}</dd></div><div><dt>Cash movement</dt><dd>{money(data.cash_movement)}</dd></div><div><dt>Fills</dt><dd>{data.fill_count}</dd></div><div><dt>Bought / sold</dt><dd>{data.buy_units} / {data.sell_units} units</dd></div><div><dt>Open at cutoff</dt><dd>{data.open_units_at_cutoff == null ? "Unavailable" : `${data.open_units_at_cutoff} units`}</dd></div></dl>
      <p className="muted">Realized P&amp;L includes allocated entry costs and exit fees. Cash movement also includes funding and purchases; it is not profit. Open positions are not marked to market in this report.</p>
      <details><summary>Cash and recorded decisions</summary><dl className="execution-values"><div><dt>Opening cash</dt><dd>{money(data.cash_opening)}</dd></div><div><dt>Cash at cutoff</dt><dd>{money(data.cash_at_cutoff)}</dd></div></dl><p className="muted">Cash includes funds reserved for orders. Decision counts describe recorded stages, not unique trades or permission to trade.</p>{data.activity ? <dl className="execution-values">{Object.entries(stages).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{data.activity![key]}</dd></div>)}</dl> : <p>Decision totals unavailable: this day exceeds the reporting limit.</p>}</details>
      <h3>Filled trades</h3>
      {!data.fills.length ? <p className="empty-state">No dated fills recorded for this day.</p> : <ol className="agent-activity-list">{data.fills.map(fill => <li className="execution-card" key={fill.id}><h4>{fill.side === "BUY" ? "Bought" : "Sold"} {fill.quantity} units</h4><p>{fill.instrument ? `${fill.instrument.underlying} ${fill.instrument.strike} ${fill.instrument.option_type} / ${fill.instrument.expiry}` : "Contract details unavailable"}</p><p>{money(fill.price)} per unit / Fees {money(fill.fees)}</p><p className="muted">{time(fill.timestamp)} IST</p><OrderHistory orderId={fill.order_id} /></li>)}</ol>}
      {data.fills_truncated && <p className="muted">Showing the latest 20 fills. Totals include all dated fills for this day.</p>}
    </>}
  </section>;
}
