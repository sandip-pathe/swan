"use client";

import { useEffect, useState } from "react";
import { money, time } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";

type Evidence = { available: boolean; missing: number | null; quotes: { id: string; instrument: string; timestamp: string; received_at: string; source: string; timestamp_basis: string; bid: string | null; ask: string | null; last_price: string | null }[]; headlines: { id: string; title: string; source: string; published_at: string; fetched_at: string; provider_delay_seconds: number }[] };
export default function AgentEvidence({ eventId }: { eventId: string }) {
  const request = usePaperRequest();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Evidence | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open || !request) return;
    let current = true; const controller = new AbortController(); setError(false); setData(null);
    request(`/api/paper/agent-activity/${eventId}/evidence`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]))
      .then(value => { if (current) setData(value as Evidence); })
      .catch(() => { if (current) setError(true); });
    return () => { current = false; controller.abort(); };
  }, [open, request, eventId, retry]);
  return <details onToggle={event => setOpen(event.currentTarget.open)}><summary>Evidence used</summary>{open && <>
    {error ? <p role="alert">Evidence could not be loaded. <button className="secondary" onClick={() => setRetry(value => value + 1)}>Retry evidence</button></p> : !data ? <p role="status">Loading evidence...</p> : !data.available ? <p>No reliable evidence link was saved for this record.</p> : <>
      <p className="muted">Historical observations cited by this output. A citation alone does not confirm that checks passed.</p>
      {!!data.missing && <p className="notice">{data.missing} cited {data.missing === 1 ? "observation is" : "observations are"} unavailable.</p>}
      {data.quotes.map(row => <div className="execution-card" key={row.id}><h4 className="recorded-rationale">{row.instrument}</h4><dl className="execution-values"><div><dt>Bid</dt><dd>{money(row.bid)}</dd></div><div><dt>Ask</dt><dd>{money(row.ask)}</dd></div><div><dt>Last price</dt><dd>{money(row.last_price)}</dd></div></dl><p>{row.source} / {time(row.timestamp)} IST</p><p className="muted">Received {time(row.received_at)} IST{row.timestamp_basis !== "exchange_feed" ? " / Exchange time unverified" : ""}</p></div>)}
      {data.headlines.map(row => <div className="execution-card" key={row.id}><h4 className="recorded-rationale">{row.title}</h4><p>{row.source}</p><p className="muted">Published {time(row.published_at)} IST / Retrieved {time(row.fetched_at)} IST</p><p className="muted">Provider delay: {row.provider_delay_seconds > 0 ? `${row.provider_delay_seconds / 3600} hours` : "No delay declared"}</p></div>)}
      {!data.quotes.length && !data.headlines.length && !data.missing && <p>No observations were cited.</p>}
    </>}
  </>}</details>;
}
