"use client";

import { useEffect, useState } from "react";
import { time } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";
import AgentEvidence from "./agent-evidence";

type Run = { available: boolean; slot_at?: string; title?: string; summary?: string; truncated?: boolean; rows?: { id: string; timestamp: string; stage: string; summary: string; rationale: string | null }[] };
const names: Record<string, string> = { analysis: "Analysis", proposal: "Proposal", review: "Review", unknown: "Recorded stage" };
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
      {!data.rows?.length && <p>No linked model outputs were recorded.</p>}
      <ol className="agent-activity-list">{data.rows?.map(row => <li className="execution-card" key={row.id}><p className="activity-stage">{names[row.stage] ?? "Recorded stage"}</p><h4>{row.summary}</h4><p className="muted">{time(row.timestamp)} IST</p>{row.rationale && <p className="recorded-rationale">{row.rationale}</p>}<AgentEvidence eventId={row.id} /></li>)}</ol>
      {data.truncated && <p className="notice">Showing the first 20 recorded outputs. This history is incomplete.</p>}
      <p className="muted">Missing stages may have stopped before an output was saved. Risk checks, permission and fills are separate.</p>
    </>}
  </>}</details>;
}
