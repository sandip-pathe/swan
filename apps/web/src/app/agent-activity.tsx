"use client";

import { useEffect, useRef, useState } from "react";
import { money, time, words } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";
import OrderHistory from "./order-history";

type Activity = { id: string; timestamp: string; stage: string; state: string; title: string; summary: string; rationale: string | null; evidence_count: number | null; concerns: string[]; instrument: { underlying: string; strike: string; option_type: string; expiry: string } | null; risk: { quantity: number; cash_budget: string; risk_budget: string; expires_at: string } | null; order: { id: string; status: string; quantity: number; filled_quantity: number } | null };
type Page = { as_of: string; mode: string; rows: Activity[]; next_before: string | null };
const stageNames: Record<string, string> = { output: "Model output", analysis: "Market analysis", proposal: "Model proposal", review: "Independent review", evaluation: "Evaluation outcome", risk: "Risk checks" };
const stateNames: Record<string, string> = { wait: "Wait", blocked: "Blocked", failed: "Failed", ready: "Checks passed", proposed: "Proposed", reviewed: "Reviewed", analysis: "Analysis", pending: "Pending", unspecified: "Unspecified outcome", unavailable: "Unavailable" };

export default function AgentActivity() {
  const request = usePaperRequest();
  const [category, setCategory] = useState("all");
  const [data, setData] = useState<Page | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const active = useRef<AbortController | null>(null);
  const generation = useRef(0);
  async function load(before?: string) {
    if (!request) return;
    active.current?.abort(); const controller = new AbortController(); active.current = controller;
    const current = ++generation.current; setBusy(true); setError(false);
    if (!before) setData(null);
    try {
      const result = await request(`/api/paper/agent-activity?${new URLSearchParams({ category, ...(before ? { before } : {}) })}`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)])) as Page;
      if (generation.current === current) setData(previous => before && previous ? { ...result, rows: [...previous.rows, ...result.rows.filter(row => !previous.rows.some(old => old.id === row.id))] } : result);
    } catch { if (generation.current === current) setError(true); }
    finally { if (generation.current === current) setBusy(false); }
  }
  useEffect(() => { load(); return () => { generation.current++; active.current?.abort(); }; }, [request, category, refresh]); // Selection changes replace the complete page.
  return <section className="panel agent-activity" aria-label="Agent activity">
    <div className="panelhead"><div><h2>Agent activity</h2><p>Recorded analysis, proposals, review and risk checks.</p></div><button className="text-button" disabled={busy} onClick={() => setRefresh(value => value + 1)}>Refresh activity</button></div>
    <label>Activity type<select value={category} onChange={event => setCategory(event.target.value)}><option value="all">All stages</option><option value="agents">Models and evaluations</option><option value="risk">Risk checks</option></select></label>
    {data?.mode === "OBSERVATION" && <p className="notice">Observation mode: automated analysis is idle. Records below are history.</p>}
    <p className="muted">A proposal or review is not an executed trade. Risk permission, order acceptance and actual fills are separate stages.</p>
    {busy && <p role="status">Loading recorded activity…</p>}
    {error && <p className="notice error" role="alert">Activity could not be loaded. <button className="secondary" disabled={busy} onClick={() => load(data?.next_before ?? undefined)}>Retry activity</button></p>}
    {data && <>
      <p className="muted">Newest first · Snapshot {time(data.as_of)} IST</p>
      {!data.rows.length ? <p className="empty-state">No recorded activity in this view. Analysis appears after a permitted agent session runs; refreshing this page does not start one.</p> : <ol className="agent-activity-list">{data.rows.map(row => <li key={row.id} className="execution-card">
        <div className="execution-card-head"><div><p className="activity-stage">{stageNames[row.stage] ?? "Recorded stage"}</p><h3>{row.title}</h3></div><span className={`status-pill activity-state ${["wait", "blocked", "failed", "ready"].includes(row.state) ? row.state : ""}`}>{stateNames[row.state] ?? "Recorded"}</span></div>
        <time dateTime={row.timestamp}>{time(row.timestamp)} IST</time>
        {row.instrument && <p><strong>{row.instrument.underlying} {row.instrument.strike} {row.instrument.option_type}</strong> · {row.instrument.expiry}</p>}
        <p>{row.summary}</p>
        {(row.rationale || row.concerns.length > 0 || row.risk || row.evidence_count != null) && <details><summary>Recorded explanation</summary>{row.rationale && <p className="recorded-rationale">{row.rationale}</p>}{row.concerns.length > 0 && <><h4>Recorded concerns</h4><ul>{row.concerns.map((text, index) => <li key={index}>{text}</li>)}</ul></>}{row.evidence_count != null && <p className="muted">{row.evidence_count} cited market observations. A citation count alone does not establish acceptance or freshness.</p>}{row.risk && <><dl className="execution-values"><div><dt>Approved quantity</dt><dd>{row.risk.quantity} units</dd></div><div><dt>Cash allowance</dt><dd>{money(row.risk.cash_budget)}</dd></div><div><dt>Risk allowance</dt><dd>{money(row.risk.risk_budget)}</dd></div></dl><p className="muted">Recorded approval valid until {time(row.risk.expires_at)} IST. This historical result grants no current permission.</p></>}</details>}
        {row.stage === "risk" && <>{row.order ? <><p>Linked order · {words(row.order.status)} · {row.order.filled_quantity} / {row.order.quantity} units filled</p><OrderHistory orderId={row.order.id} /></> : <p className="muted">No linked paper order was found for this decision.</p>}</>}
      </li>)}</ol>}
      {data.next_before && <button className="secondary" disabled={busy} onClick={() => load(data.next_before!)}>Load older activity</button>}
    </>}
  </section>;
}
