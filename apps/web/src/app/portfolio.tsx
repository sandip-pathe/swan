"use client";

import { useEffect, useRef, useState } from "react";
import { money, time } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";
import { readSnapshot, saveSnapshot } from "@/lib/display-snapshot";
import DashboardSkeleton from "./dashboard-skeleton";

type Exposure = { instrument_id: string; open_quantity: number; entry_cost_basis: string; planned_stop_risk: string; pending_quantity: number; pending_limit_notional: string | null; pending_order_count: number; pending_limit_orders: number; pending_reserved_risk: string };
type Portfolio = { as_of: string; status: string; reconciled: boolean; open_positions: number; valid_until: string | null; oldest_quote_at: string | null; cash_balance: string | null; available_cash: string | null; equity: string | null; open_position_value: string | null; realized_pnl: string | null; unrealized_pnl: string | null; total_pnl: string | null; session_pnl: string | null; session_date: string | null; fees: string | null; fee_basis?: string; trade_statistics: { closed_positions: number; win_rate: string | null; average_win: string | null; average_loss: string | null; expectancy: string | null; profit_factor: string | null; realized_drawdown: string | null; average_holding_seconds: number | null }; risk_headroom: { loss_limit: string; loss_used: string; allocated_risk: string; remaining: string; blocked: boolean } | null; exposure?: Exposure[] | null };

export default function PortfolioPanel({ revision, ownerKey }: { revision: number; ownerKey: string }) {
  const request = usePaperRequest();
  const [data, setData] = useState<Portfolio | null>(() => readSnapshot<Portfolio>(ownerKey, "portfolio"));
  const [confirmed, setConfirmed] = useState(false);
  const [manual, setManual] = useState(false);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(Date.now);
  const sequence = useRef(0);
  const previousRevision = useRef(revision);
  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    const current = ++sequence.current;
    let pending = false, failures = 0;
    let polling: ReturnType<typeof setTimeout>;
    async function load() {
      clearTimeout(polling);
      if (pending || document.hidden || !navigator.onLine) { if (!controller.signal.aborted) polling = setTimeout(load, 10000); return; }
      pending = true; setBusy(true);
      try {
        const result = await request!("/api/paper/portfolio", "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(12000)])) as Portfolio;
        if (current === sequence.current && !controller.signal.aborted) { setData(result); setConfirmed(true); setError(false); setNow(Date.now()); saveSnapshot(ownerKey, "portfolio", result); failures = 0; }
      } catch { if (current === sequence.current && !controller.signal.aborted) { setError(true); failures++; } }
      finally { pending = false; if (current === sequence.current && !controller.signal.aborted) { setBusy(false); setManual(false); polling = setTimeout(load, failures ? Math.min(60000, 10000 * 2 ** failures) : 10000); } }
    }
    load();
    document.addEventListener("visibilitychange", load);
    return () => { controller.abort(); clearTimeout(polling); document.removeEventListener("visibilitychange", load); };
  }, [request, refresh, ownerKey]);
  useEffect(() => {
    if (previousRevision.current === revision) return;
    previousRevision.current = revision;
    // An initial workspace reply must not cancel the parallel portfolio read.
    if (!busy) setRefresh(value => value + 1);
  }, [revision, busy]);
  useEffect(() => {
    if (!data) return;
    const deadline = Math.min(Date.parse(data.as_of) + 15000, data.status === "FRESH" && data.valid_until ? Date.parse(data.valid_until) : Infinity);
    const timer = setTimeout(() => setNow(Date.now()), Math.max(0, deadline - Date.now()) + 1);
    return () => clearTimeout(timer);
  }, [data]);
  const snapshotFresh = confirmed && !!data && Number.isFinite(Date.parse(data.as_of)) && now - Date.parse(data.as_of) >= 0 && now - Date.parse(data.as_of) < 15000;
  const quoteFresh = !!data && (data.status === "FLAT" || (data.status === "FRESH" && !!data.valid_until && now < Date.parse(data.valid_until)));
  const valued = snapshotFresh && quoteFresh && data?.reconciled && !error;
  const recorded = snapshotFresh && data?.reconciled && !error;
  const stats = recorded ? data?.trade_statistics : null;
  const risk = valued ? data?.risk_headroom : null;
  const exposure = recorded ? data?.exposure : null;
  const cash = data?.reconciled && data?.cash_balance != null ? Number(data.cash_balance) : NaN;
  const available = data?.reconciled && data?.available_cash != null ? Number(data.available_cash) : NaN;
  const cashSplit = Number.isFinite(cash) && cash > 0 && Number.isFinite(available) && available >= 0 && available <= cash;
  const availablePercent = cashSplit ? available / cash * 100 : 0;
  const message = error ? "Portfolio could not be updated. Retry when your connection is available." : !data ? "Loading your portfolio…" : !snapshotFresh ? "Account snapshot is stale. Refresh to check current holdings." : !data.reconciled ? "Your account totals need checking. Balances will return when they match." : valued ? data.status === "FLAT" ? "No trades are open. Your account value is all cash." : "Estimated from bid depth after exit fees. This is an estimate, not a guaranteed sale value." : data.status === "STALE" || (data.status === "FRESH" && !quoteFresh) ? "Market prices are stale. Open-position value and estimated P&L are unavailable." : "We need reliable prices to estimate your open trades. Closed-trade results stay separate.";
  if (!data && !error) return <DashboardSkeleton />;
  const historical = !!data && (!recorded || !valued);
  const displayed = data?.reconciled && (valued || historical);
  return <section className="panel portfolio-panel" aria-label="Portfolio value and P&L">
    <div className="panelhead"><div><h2>Your money</h2><p className="muted">{data ? `${historical ? "Last saved" : "Updated"} ${time(data.as_of)} IST` : "Account values load from your paper ledger."}</p></div><button className="text-button" disabled={busy && manual} onClick={() => { setManual(true); setRefresh(value => value + 1); }}>{busy && !data ? "Loading…" : busy ? "Updating…" : "Refresh balance"}</button></div>
    {historical && <p className="saved-data-strip" role="status">Saved values from {time(data?.as_of)} IST. {error ? "Could not update. We will retry in the background." : "Checking for newer data."} These are not current buying power.</p>}
    <dl className="portfolio-hero"><div><dt>Practice account value</dt><dd className={!data && !error ? "value-loading" : undefined}>{!data && !error ? "Loading..." : money(displayed ? data?.equity : null)}</dd><small>Cash + estimated value of open trades</small></div><div><dt>Today’s profit / loss</dt><dd className={!data && !error ? "value-loading" : undefined}>{!data && !error ? "Loading..." : displayed && data?.session_pnl == null ? "\u2014" : money(displayed ? data?.session_pnl : null)}</dd><small>{displayed && data?.session_pnl == null ? "Today’s starting balance is missing" : "Includes estimated trading costs"}</small></div><div><dt>Trades still open</dt><dd className={!data && !error ? "value-loading" : undefined}>{!data && !error ? "Loading..." : data?.reconciled ? `${data?.open_positions ?? 0} positions` : "Unavailable"}</dd><small>{recorded && data?.open_positions === 0 ? "No trades running right now" : "See your open trades below"}</small></div></dl>
    {cashSplit && <div className="money-map"><div className="money-map-label"><strong>{historical ? "Cash available when saved" : "Cash you can use"}</strong><strong>{money(data?.available_cash)}</strong></div><div className="money-track" role="img" aria-label={`${Math.round(availablePercent)}% of cash is available; ${money(String(cash - available))} is held or reserved.`}><span style={{width: `${availablePercent}%`}} /></div><div className="money-map-label muted"><span>{Math.round(availablePercent)}% available</span><span>{money(String(cash - available))} held / reserved</span></div><details><summary>Why is some cash held?</summary><p>Pending orders can reserve cash. Some sale proceeds also stay locked until their release is verified. This bar shows cash only.</p></details></div>}
    <details className="simple-money-details"><summary>Closed trades & trading costs</summary><dl className="dashboard-facts"><div><dt>Profit / loss from closed trades</dt><dd>{money(recorded ? data?.realized_pnl : null)}</dd></div><div><dt>Trading costs so far</dt><dd>{money(recorded ? data?.fees : null)}</dd></div></dl><p>Closed-trade profit / loss includes recorded costs. Open trades can still change in value.</p></details>
    {!historical && <p className="muted" role="status">{message}</p>}
    <details className="portfolio-details"><summary>Go deeper: results, risk & costs</summary>
    <p className="muted" role={error ? "alert" : "status"}>{message}</p>
    {data && ["estimated", "mixed", "legacy"].includes(data.fee_basis ?? "") && <p className="muted">Paper P&amp;L includes modeled fees. These charges have not been reconciled to a broker contract note.</p>}
    <details><summary>Account performance breakdown</summary>
    <dl className="portfolio-values">
      <div><dt>Realized P&amp;L · all time</dt><dd>{money(recorded ? data?.realized_pnl : null)}</dd></div>
      <div><dt>Estimated open P&amp;L</dt><dd>{money(valued ? data?.unrealized_pnl : null)}</dd></div>
      <div><dt>Total P&amp;L · all time</dt><dd>{money(valued ? data?.total_pnl : null)}</dd></div>
      <div><dt>Session P&amp;L</dt><dd>{money(displayed ? data?.session_pnl : null)}</dd></div>
    </dl>
    </details>
    <details><summary>Closed-trade statistics · {stats?.closed_positions ?? "Unavailable"}</summary><p className="muted">Closed positions only. P&amp;L fields use recorded net realized results. Drawdown is the peak-to-trough path of those realized results; it excludes open positions, funding and marked equity. No performance guarantee is implied.</p><dl className="execution-values"><div><dt>Win rate</dt><dd>{stats?.win_rate == null ? "Unavailable" : `${(Number(stats.win_rate) * 100).toFixed(1)}%`}</dd></div><div><dt>Average win</dt><dd>{money(stats?.average_win)}</dd></div><div><dt>Average loss</dt><dd>{money(stats?.average_loss)}</dd></div><div><dt>Expectancy / closed position</dt><dd>{money(stats?.expectancy)}</dd></div><div><dt>Profit factor</dt><dd>{stats?.profit_factor == null ? "Unavailable" : Number(stats.profit_factor).toFixed(2)}</dd></div><div><dt>Realized drawdown</dt><dd>{money(stats?.realized_drawdown)}</dd></div><div><dt>Average holding time</dt><dd>{stats?.average_holding_seconds == null ? "Unavailable" : `${Math.round(stats.average_holding_seconds / 60)} min`}</dd></div></dl></details>
    <details><summary>Daily risk headroom</summary>{risk ? <><dl className="execution-values"><div><dt>Loss limit</dt><dd>{money(risk.loss_limit)}</dd></div><div><dt>Loss used</dt><dd>{money(risk.loss_used)}</dd></div><div><dt>Risk allocated to open positions and entries</dt><dd>{money(risk.allocated_risk)}</dd></div><div><dt>Remaining headroom</dt><dd>{money(risk.remaining)}</dd></div></dl><p className="muted">Based on the current session opening equity, fresh portfolio valuation, recorded risk reservations and the saved daily limit. {risk.blocked ? "The daily trading block is active; headroom does not grant entry permission." : "Headroom is informational; normal entry gates still apply."}</p></> : <p>Unavailable until the session baseline, account reconciliation and fresh portfolio valuation are available.</p>}</details>
    <details><summary>Exposure by contract</summary>{data && !("exposure" in data) ? <p>Restart the local API to load this breakdown.</p> : exposure ? exposure.length ? <><p className="muted">Open exposure uses remaining units at average entry cost. Stop risk and pending-order risk are saved estimates; they are not current market value or a guaranteed maximum loss.</p><div className="position-list">{exposure.map(item => <article className="execution-card" key={item.instrument_id}><strong className="contract-label">{item.instrument_id}</strong><dl className="execution-values"><div><dt>Open units</dt><dd>{item.open_quantity.toLocaleString("en-IN")}</dd></div><div><dt>Entry cost basis</dt><dd>{money(item.entry_cost_basis)}</dd></div><div><dt>Planned stop risk</dt><dd>{money(item.planned_stop_risk)}</dd></div><div><dt>Pending entry units</dt><dd>{item.pending_quantity.toLocaleString("en-IN")}</dd></div><div><dt>Pending limit value</dt><dd>{item.pending_quantity === 0 ? "—" : item.pending_limit_notional == null ? "Partial / unavailable" : money(item.pending_limit_notional)}</dd></div><div><dt>Pending reserved risk</dt><dd>{money(item.pending_reserved_risk)}</dd></div></dl></article>)}</div></> : <p>No open positions or pending entry orders.</p> : <p>Unavailable until account records reconcile.</p>}</details>
    <details><summary>How these values are calculated</summary><p>Portfolio value is recorded cash plus the estimated sale value of all open positions after exit fees. Reserved and restricted cash remain part of the balance, but are not available to trade.</p><p>Realized P&amp;L uses completed sales and allocated entry costs. Open P&amp;L includes remaining entry costs and estimated exit fees. Total P&amp;L compares portfolio value with recorded capital. Session P&amp;L requires a current session baseline.</p><dl className="execution-values"><div><dt>Cash balance</dt><dd>{money(recorded ? data?.cash_balance : null)}</dd></div><div><dt>Available to trade</dt><dd>{money(recorded ? data?.available_cash : null)}</dd></div><div><dt>Estimated open value</dt><dd>{money(valued ? data?.open_position_value : null)}</dd></div><div><dt>Recorded fees · all time</dt><dd>{money(recorded ? data?.fees : null)}</dd></div></dl>{data && <p className="muted">Account snapshot {time(data.as_of)} IST{data.oldest_quote_at ? ` · Oldest valuation quote ${time(data.oldest_quote_at)} IST` : ""}{data.session_date ? ` · Session ${data.session_date}` : " · Current session baseline unavailable"}</p>}</details>
    </details>
  </section>;
}
