"use client";

import { useEffect, useState } from "react";
import { time } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";

type Usage = { day_ended: boolean; policy_source: string; day: string; as_of: string; resets_at: string; policy: { model: string | null; daily_allowance: number } | null; reservation_count: number; reserved_allowance: number | null; remaining_allowance: number | null; reported_tokens: number; reported_calls: number; unknown_calls: number; models: { model: string; reservations: number }[] };
const count = (value: number | null | undefined) => value == null ? "Unavailable" : value.toLocaleString("en-IN");

function todayIST() { return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date()); }

export default function AgentUsage() {
  const request = usePaperRequest();
  const [day, setDay] = useState(todayIST);
  const [data, setData] = useState<Usage | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (!request || !day) { setData(null); setBusy(false); setError(false); return; }
    const controller = new AbortController(); let current = true;
    setData(null); setError(false); setBusy(true);
    request(`/api/paper/agent-usage?${new URLSearchParams({ day })}`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]))
      .then(result => { if (current) setData(result as Usage); })
      .catch(() => { if (current) setError(true); })
      .finally(() => { if (current) setBusy(false); });
    return () => { current = false; controller.abort(); };
  }, [request, refresh, day]);
  return <section className="panel" aria-label="Analysis allowance">
    <div className="panelhead"><div><h2>Analysis allowance</h2><p>Daily model allowance and recorded usage.</p></div><button className="secondary" disabled={busy || !day} onClick={() => setRefresh(value => value + 1)}>Refresh allowance</button></div>
    <label>Usage date (IST)<input type="date" value={day} max={todayIST()} onChange={event => setDay(event.target.value)} /></label>
    {!day && <p>Choose a date to view usage.</p>}
    {busy && <p role="status">Loading allowance...</p>}
    {error && <p className="notice error" role="alert">Allowance could not be loaded. <button className="secondary" onClick={() => setRefresh(value => value + 1)}>Retry allowance</button></p>}
    {data && <>
      <p className="muted">{data.day} IST / Snapshot {time(data.as_of)} IST</p>
      {!data.policy && <p className={`notice ${data.day_ended ? "" : "error"}`}>{data.day_ended ? data.policy_source === "changed" ? "Recorded allowance changed during this day. Remaining allowance is unavailable." : "The historical allowance was not fully recorded. Remaining allowance is unavailable." : "Current model settings are unavailable. Remaining allowance cannot be calculated."}</p>}
      {data.reserved_allowance == null && <p className="notice error">Some reservation records are invalid. Reserved and remaining totals are unavailable.</p>}
      <dl className="execution-values"><div><dt>{data.day_ended ? "Recorded request allowance" : "Daily allowance"}</dt><dd>{count(data.policy?.daily_allowance)}</dd></div><div><dt>Reserved allowance</dt><dd>{count(data.reserved_allowance)}</dd></div><div><dt>{data.day_ended ? "Unused recorded allowance" : "Remaining allowance"}</dt><dd>{count(data.remaining_allowance)}</dd></div><div><dt>Requests reserved</dt><dd>{count(data.reservation_count)}</dd></div></dl>
      <p className="muted">Allowance uses a conservative reservation for each request, not measured tokens. Reservations remain counted after failed calls. The daily boundary is midnight IST; refreshing does not start analysis.</p>
      {data.day_ended && <p className="muted">Historical allowance uses limits saved with requests, not the day's final settings. Usage follows the request date, including responses saved later.</p>}
      {!data.reservation_count && <p className="empty-state">No model requests reserved for this day.</p>}
      <details><summary>Reported usage and models</summary>
        <dl className="execution-values"><div><dt>Reported tokens</dt><dd>{count(data.reported_tokens)}</dd></div><div><dt>Requests with usage</dt><dd>{count(data.reported_calls)}</dd></div><div><dt>Usage unavailable</dt><dd>{count(data.unknown_calls)}</dd></div></dl>
        <p>Reported tokens cover only linked, valid completed responses with recorded usage. Missing usage is unknown, including failed or in-flight requests. This is not a billing total.</p>
        {!data.day_ended && <p>Configured model: <strong className="recorded-rationale">{data.policy?.model ?? "Unavailable"}</strong></p>}
        <p className="muted">{!data.day_ended && "Current settings may differ from a running worker. "}Models below come from each reservation; a model name does not identify an immutable version.</p>
        {data.models.map(row => <p className="recorded-rationale" key={row.model}>{row.model}: {count(row.reservations)} reserved requests</p>)}
        <p className="muted">Monetary cost is unavailable. New evaluation histories include recorded model and rule details.</p>
      </details>
    </>}
  </section>;
}
