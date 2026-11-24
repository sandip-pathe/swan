"use client";

import { useEffect, useRef, useState } from "react";
import { money, time } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";

type Exposure = { instrument_id: string; open_quantity: number; entry_cost_basis: string; planned_stop_risk: string; pending_quantity: number; pending_limit_notional: string | null; pending_order_count: number; pending_limit_orders: number; pending_reserved_risk: string };
type Portfolio = { as_of: string; status: string; reconciled: boolean; open_positions: number; valid_until: string | null; oldest_quote_at: string | null; cash_balance: string | null; available_cash: string | null; equity: string | null; open_position_value: string | null; realized_pnl: string | null; unrealized_pnl: string | null; total_pnl: string | null; session_pnl: string | null; session_date: string | null; fees: string | null; fee_basis?: string; trade_statistics: { closed_positions: number; win_rate: string | null; average_win: string | null; average_loss: string | null; expectancy: string | null; profit_factor: string | null; realized_drawdown: string | null; average_holding_seconds: number | null }; risk_headroom: { loss_limit: string; loss_used: string; allocated_risk: string; remaining: string; blocked: boolean } | null; exposure?: Exposure[] | null };

export default function PortfolioPanel({ revision }: { revision: number }) {
  const request = usePaperRequest();
  const [data, setData] = useState<Portfolio | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(Date.now);
  const sequence = useRef(0);
  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    const current = ++sequence.current;
    let pending = false;
    async function load() {
      if (pending || document.visibilityState === "hidden") return;
      pending = true; setBusy(true);
      try {
        const result = await request!("/api/paper/portfolio", "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(12000)])) as Portfolio;
        if (current === sequence.current && !controller.signal.aborted) { setData(result); setError(false); setNow(Date.now()); }
      } catch { if (current === sequence.current && !controller.signal.aborted) setError(true); }
      finally { pending = false; if (current === sequence.current && !controller.signal.aborted) setBusy(false); }
    }
    load();
    const polling = setInterval(load, 5000);
    document.addEventListener("visibilitychange", load);
    return () => { controller.abort(); clearInterval(polling); document.removeEventListener("visibilitychange", load); };
  }, [request, revision, refresh]);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const snapshotFresh = !!data && Number.isFinite(Date.parse(data.as_of)) && now - Date.parse(data.as_of) >= 0 && now - Date.parse(data.as_of) < 15000;
  const quoteFresh = !!data && (data.status === "FLAT" || (data.status === "FRESH" && !!data.valid_until && now < Date.parse(data.valid_until)));
  const valued = snapshotFresh && quoteFresh && data?.reconciled && !error;
  const recorded = snapshotFresh && data?.reconciled && !error;
  const stats = recorded ? data?.trade_statistics : null;
  const risk = valued ? data?.risk_headroom : null;
  const exposure = recorded ? data?.exposure : null;
  const message = error ? "Portfolio could not be updated. Retry when your connection is available." : !data ? "Loading your portfolio…" : !snapshotFresh ? "Account snapshot is stale. Refresh to check current holdings." : !data.reconciled ? "Account records need reconciliation. Values are unavailable until this is resolved." : valued ? data.status === "FLAT" ? "No open positions. Portfolio value equals recorded cash." : "Estimated from bid depth after exit fees. This is an estimate, not a guaranteed sale value." : data.status === "STALE" || (data.status === "FRESH" && !quoteFresh) ? "Market prices are stale. Open-position value and estimated P&L are unavailable." : "Fresh executable depth or reviewed valuation settings are unavailable. Recorded results remain separate.";
  return <section className="panel portfolio-panel" aria-label="Portfolio value and P&L">
    <div className="panelhead"><h2>Portfolio</h2><button className="text-button" disabled={busy} onClick={() => setRefresh(value => value + 1)}>{busy && !data ? "Loading…" : "Refresh portfolio"}</button></div>
    <p className="portfolio-caption">Estimated portfolio value</p><strong className="portfolio-equity">{money(valued ? data?.equity : null)}</strong>
    <p className="muted" role={error ? "alert" : "status"}>{message}</p>
    {data && ["estimated", "mixed", "legacy"].includes(data.fee_basis ?? "") && <p className="muted">Paper P&amp;L includes modeled fees. These charges have not been reconciled to a broker contract note.</p>}
    <dl className="portfolio-values">
      <div><dt>Realized P&amp;L · all time</dt><dd>{money(recorded ? data?.realized_pnl : null)}</dd></div>
      <div><dt>Estimated open P&amp;L</dt><dd>{money(valued ? data?.unrealized_pnl : null)}</dd></div>
      <div><dt>Total P&amp;L · all time</dt><dd>{money(valued ? data?.total_pnl : null)}</dd></div>
      <div><dt>Session P&amp;L</dt><dd>{money(valued ? data?.session_pnl : null)}</dd></div>
    </dl>
    <details><summary>Closed-trade statistics · {stats?.closed_positions ?? "Unavailable"}</summary><p className="muted">Closed positions only. P&amp;L fields use recorded net realized results. Drawdown is the peak-to-trough path of those realized results; it excludes open positions, funding and marked equity. No performance guarantee is implied.</p><dl className="execution-values"><div><dt>Win rate</dt><dd>{stats?.win_rate == null ? "Unavailable" : `${(Number(stats.win_rate) * 100).toFixed(1)}%`}</dd></div><div><dt>Average win</dt><dd>{money(stats?.average_win)}</dd></div><div><dt>Average loss</dt><dd>{money(stats?.average_loss)}</dd></div><div><dt>Expectancy / closed position</dt><dd>{money(stats?.expectancy)}</dd></div><div><dt>Profit factor</dt><dd>{stats?.profit_factor == null ? "Unavailable" : Number(stats.profit_factor).toFixed(2)}</dd></div><div><dt>Realized drawdown</dt><dd>{money(stats?.realized_drawdown)}</dd></div><div><dt>Average holding time</dt><dd>{stats?.average_holding_seconds == null ? "Unavailable" : `${Math.round(stats.average_holding_seconds / 60)} min`}</dd></div></dl></details>
    <details><summary>Daily risk headroom</summary>{risk ? <><dl className="execution-values"><div><dt>Loss limit</dt><dd>{money(risk.loss_limit)}</dd></div><div><dt>Loss used</dt><dd>{money(risk.loss_used)}</dd></div><div><dt>Risk allocated to open positions and entries</dt><dd>{money(risk.allocated_risk)}</dd></div><div><dt>Remaining headroom</dt><dd>{money(risk.remaining)}</dd></div></dl><p className="muted">Based on the current session opening equity, fresh portfolio valuation, recorded risk reservations and the saved daily limit. {risk.blocked ? "The daily trading block is active; headroom does not grant entry permission." : "Headroom is informational; normal entry gates still apply."}</p></> : <p>Unavailable until the session baseline, account reconciliation and fresh portfolio valuation are available.</p>}</details>
    <details><summary>Exposure by contract</summary>{data && !("exposure" in data) ? <p>Restart the local API to load this breakdown.</p> : exposure ? exposure.length ? <><p className="muted">Open exposure uses remaining units at average entry cost. Stop risk and pending-order risk are saved estimates; they are not current market value or a guaranteed maximum loss.</p><div className="position-list">{exposure.map(item => <article className="execution-card" key={item.instrument_id}><strong className="contract-label">{item.instrument_id}</strong><dl className="execution-values"><div><dt>Open units</dt><dd>{item.open_quantity.toLocaleString("en-IN")}</dd></div><div><dt>Entry cost basis</dt><dd>{money(item.entry_cost_basis)}</dd></div><div><dt>Planned stop risk</dt><dd>{money(item.planned_stop_risk)}</dd></div><div><dt>Pending entry units</dt><dd>{item.pending_quantity.toLocaleString("en-IN")}</dd></div><div><dt>Pending limit value</dt><dd>{item.pending_quantity === 0 ? "—" : item.pending_limit_notional == null ? "Partial / unavailable" : money(item.pending_limit_notional)}</dd></div><div><dt>Pending reserved risk</dt><dd>{money(item.pending_reserved_risk)}</dd></div></dl></article>)}</div></> : <p>No open positions or pending entry orders.</p> : <p>Unavailable until account records reconcile.</p>}</details>
    <details><summary>How these values are calculated</summary><p>Portfolio value is recorded cash plus the estimated sale value of all open positions after exit fees. Reserved and restricted cash remain part of the balance, but are not available to trade.</p><p>Realized P&amp;L uses completed sales and allocated entry costs. Open P&amp;L includes remaining entry costs and estimated exit fees. Total P&amp;L compares portfolio value with recorded capital. Session P&amp;L requires a current session baseline.</p><dl className="execution-values"><div><dt>Cash balance</dt><dd>{money(recorded ? data?.cash_balance : null)}</dd></div><div><dt>Available to trade</dt><dd>{money(recorded ? data?.available_cash : null)}</dd></div><div><dt>Estimated open value</dt><dd>{money(valued ? data?.open_position_value : null)}</dd></div><div><dt>Recorded fees · all time</dt><dd>{money(recorded ? data?.fees : null)}</dd></div></dl>{data && <p className="muted">Account snapshot {time(data.as_of)} IST{data.oldest_quote_at ? ` · Oldest valuation quote ${time(data.oldest_quote_at)} IST` : ""}{data.session_date ? ` · Session ${data.session_date}` : " · Current session baseline unavailable"}</p>}</details>
  </section>;
}
