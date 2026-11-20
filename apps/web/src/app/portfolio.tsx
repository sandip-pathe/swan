"use client";

import { useEffect, useRef, useState } from "react";
import { money, time } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";

type Portfolio = { as_of: string; status: string; reconciled: boolean; open_positions: number; valid_until: string | null; oldest_quote_at: string | null; cash_balance: string | null; available_cash: string | null; equity: string | null; open_position_value: string | null; realized_pnl: string | null; unrealized_pnl: string | null; total_pnl: string | null; session_pnl: string | null; session_date: string | null; fees: string | null };

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
  const message = error ? "Portfolio could not be updated. Retry when your connection is available." : !data ? "Loading your portfolio…" : !snapshotFresh ? "Account snapshot is stale. Refresh to check current holdings." : !data.reconciled ? "Account records need reconciliation. Values are unavailable until this is resolved." : valued ? data.status === "FLAT" ? "No open positions. Portfolio value equals recorded cash." : "Estimated from bid depth after exit fees. This is an estimate, not a guaranteed sale value." : data.status === "STALE" || (data.status === "FRESH" && !quoteFresh) ? "Market prices are stale. Open-position value and estimated P&L are unavailable." : "Fresh executable depth or reviewed valuation settings are unavailable. Recorded results remain separate.";
  return <section className="panel portfolio-panel" aria-label="Portfolio value and P&L">
    <div className="panelhead"><h2>Portfolio</h2><button className="text-button" disabled={busy} onClick={() => setRefresh(value => value + 1)}>{busy && !data ? "Loading…" : "Refresh portfolio"}</button></div>
    <p className="portfolio-caption">Estimated portfolio value</p><strong className="portfolio-equity">{money(valued ? data?.equity : null)}</strong>
    <p className="muted" role={error ? "alert" : "status"}>{message}</p>
    <dl className="portfolio-values">
      <div><dt>Realized P&amp;L · all time</dt><dd>{money(recorded ? data?.realized_pnl : null)}</dd></div>
      <div><dt>Estimated open P&amp;L</dt><dd>{money(valued ? data?.unrealized_pnl : null)}</dd></div>
      <div><dt>Total P&amp;L · all time</dt><dd>{money(valued ? data?.total_pnl : null)}</dd></div>
      <div><dt>Session P&amp;L</dt><dd>{money(valued ? data?.session_pnl : null)}</dd></div>
    </dl>
    <details><summary>How these values are calculated</summary><p>Portfolio value is recorded cash plus the estimated sale value of all open positions after exit fees. Reserved and restricted cash remain part of the balance, but are not available to trade.</p><p>Realized P&amp;L uses completed sales and allocated entry costs. Open P&amp;L includes remaining entry costs and estimated exit fees. Total P&amp;L compares portfolio value with recorded capital. Session P&amp;L requires a current session baseline.</p><dl className="execution-values"><div><dt>Cash balance</dt><dd>{money(recorded ? data?.cash_balance : null)}</dd></div><div><dt>Available to trade</dt><dd>{money(recorded ? data?.available_cash : null)}</dd></div><div><dt>Estimated open value</dt><dd>{money(valued ? data?.open_position_value : null)}</dd></div><div><dt>Recorded fees · all time</dt><dd>{money(recorded ? data?.fees : null)}</dd></div></dl>{data && <p className="muted">Account snapshot {time(data.as_of)} IST{data.oldest_quote_at ? ` · Oldest valuation quote ${time(data.oldest_quote_at)} IST` : ""}{data.session_date ? ` · Session ${data.session_date}` : " · Current session baseline unavailable"}</p>}</details>
  </section>;
}
