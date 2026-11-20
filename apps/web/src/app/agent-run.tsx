"use client";

import { useEffect, useState } from "react";
import { money, time, words } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";
import AgentEvidence from "./agent-evidence";
import OrderHistory from "./order-history";

type Execution = { state: string; truncated: boolean; strategy?: { version: string; action: string; instrument: string | null; issued_at: string; expires_at: string; min_entry: string; max_entry: string; stop_loss: string; target: string }; decisions: { id: string; status: string; timestamp: string | null; summary: string; orders: { id: string; side: string; status: string; quantity: number; filled_quantity: number }[] }[] };
type Run = { execution?: Execution; available: boolean; slot_at?: string; title?: string; summary?: string; truncated?: boolean; checks_truncated?: boolean; checks?: { id: string; timestamp: string; stage: string; state: string; summary: string }[]; rows?: { id: string; timestamp: string; stage: string; summary: string; rationale: string | null }[] };
const names: Record<string, string> = { analysis: "Analysis", proposal: "Proposal", review: "Review", strategy: "Strategy", unknown: "Recorded stage" };
export default function AgentRun({ eventId }: { eventId: string }) {
  const request = usePaperRequest();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Run | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open || !request) return;
    let current = true; const controller = new AbortController(); setError(false); setData(null);
    request(`/api/paper/agent-activity/${eventId}/run`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]))
      .then(value => { if (current) setData(value as Run); })
      .catch(() => { if (current) setError(true); });
    return () => { current = false; controller.abort(); };
  }, [open, request, eventId, retry]);
  return <details onToggle={event => { if (event.target === event.currentTarget) setOpen(event.currentTarget.open); }}><summary>Evaluation history</summary>{open && <>
    {error ? <p role="alert">History could not be loaded. <button className="secondary" onClick={() => setRetry(value => value + 1)}>Retry history</button></p> : !data ? <p role="status">Loading history...</p> : !data.available ? <p>No reliable evaluation link was saved for this record.</p> : <>
      <h4>{data.title}</h4><p>{data.summary}</p><p className="muted">Evaluation slot: {time(data.slot_at!)} IST. Model outputs are shown in recorded order; they do not confirm a trade.</p>
      <h4>Strategy and orders</h4>
      {!data.execution || data.execution.state === "unavailable" ? <p>No reliable accepted-strategy link is available.</p> : data.execution.state === "none" ? <p>No accepted strategy was recorded for this outcome.</p> : <>
        {data.execution.strategy && <><p className="recorded-rationale"><strong>{data.execution.strategy.instrument ?? "Contract details unavailable"}</strong></p><p>{words(data.execution.strategy.action)} / {data.execution.strategy.version}</p><dl className="execution-values"><div><dt>Entry range</dt><dd>{money(data.execution.strategy.min_entry)} - {money(data.execution.strategy.max_entry)}</dd></div><div><dt>Stop / target</dt><dd>{money(data.execution.strategy.stop_loss)} / {money(data.execution.strategy.target)}</dd></div></dl><p className="muted">Recorded validity: {time(data.execution.strategy.issued_at)} to {time(data.execution.strategy.expires_at)} IST. This historical strategy grants no current permission.</p></>}
        {!data.execution.decisions.length && <p>No linked risk decision was found. Strategy acceptance alone does not place an order.</p>}
        {data.execution.decisions.map(decision => <div className="execution-card" key={decision.id}><h4>{decision.status === "APPROVED" ? "Risk checks approved entry" : decision.status === "REJECTED" ? "Risk checks rejected entry" : "Risk result unavailable"}</h4><p>{decision.summary}</p>{decision.timestamp && <p className="muted">{time(decision.timestamp)} IST</p>}{!decision.orders.length ? <p>No linked entry order was found.</p> : decision.orders.map(order => <div key={order.id}><p>{words(order.side)} / {words(order.status)} / {order.filled_quantity} of {order.quantity} units filled</p><OrderHistory orderId={order.id} /></div>)}</div>)}
        {data.execution.truncated && <p className="notice">Linked history exceeds the display limit. Some decisions or orders are not shown.</p>}
      </>}
      <h4>Stage checks</h4>
      <p className="muted">These validate model responses. Trading permission and execution are separate.</p>
      {!data.checks?.length ? <p>No stage-check results were saved for this evaluation.</p> : <ol className="agent-activity-list">{data.checks.map(check => <li className="execution-card" key={check.id}><div className="execution-card-head"><strong>{names[check.stage] ?? "Recorded stage"}</strong><span className={`status-pill activity-state ${check.state === "PASSED" ? "ready" : check.state === "FAILED" ? "failed" : ""}`}>{check.state === "PASSED" ? "Passed" : check.state === "FAILED" ? "Failed" : check.state === "INTERRUPTED" ? "Interrupted" : "Unavailable"}</span></div><p>{check.summary}</p><p className="muted">{time(check.timestamp)} IST</p></li>)}</ol>}
      {data.checks_truncated && <p className="notice">Showing the first 20 check results. This list is incomplete.</p>}
      <h4>Model outputs</h4>
      {!data.rows?.length && <p>No linked model outputs were recorded.</p>}
      <ol className="agent-activity-list">{data.rows?.map(row => <li className="execution-card" key={row.id}><p className="activity-stage">{names[row.stage] ?? "Recorded stage"}</p><h4>{row.summary}</h4><p className="muted">{time(row.timestamp)} IST</p>{row.rationale && <p className="recorded-rationale">{row.rationale}</p>}<AgentEvidence eventId={row.id} /></li>)}</ol>
      {data.truncated && <p className="notice">Showing the first 20 recorded outputs. This history is incomplete.</p>}
      <p className="muted">Missing stages may have stopped before an output was saved. Risk checks, permission and fills are separate.</p>
    </>}
  </>}</details>;
}
