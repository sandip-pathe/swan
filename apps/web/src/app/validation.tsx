"use client";

import { useEffect, useState, type FormEvent } from "react";
import type { ApiRequest, Readiness } from "@/lib/readiness";
import { time, words } from "@/lib/paper";

type Validation = { id: string; instrument_id: string; status: string; max_quantity: number; expires_at: string; stop_reason: string | null; outcome: { result: string; entry_attempts: number; fees: string; reconciled: boolean; orders: unknown[]; fills: unknown[] } | null };
type Status = { revision: number; worker_mode: string | null; sessions: Validation[] };

export default function ValidationPanel({ request, report }: { request: ApiRequest; report?: Readiness }) {
  const [data, setData] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const value = await request("/api/validation", "GET", controller.signal) as Status;
        if (!controller.signal.aborted) { setData(value); setStale(false); }
      } catch { if (!controller.signal.aborted) { setStale(true); setError("Validation status is unavailable. Refresh before starting a session."); } }
      finally { if (!controller.signal.aborted) timer = setTimeout(load, 5000); }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [request, refresh]);

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data || busy || stale) return;
    const form = new FormData(event.currentTarget);
    setBusy(true); setError(null);
    try {
        await request("/api/validation/start", "POST", undefined, { request_id: crypto.randomUUID(), expected_revision: data.revision, instrument_id: String(form.get("instrument")), duration_seconds: Number(form.get("duration")) * 60 });
      setRefresh(value => value + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Session could not start."); }
    finally { setBusy(false); }
  }
  async function stop(id: string) {
    setBusy(true); setError(null);
    try { await request(`/api/validation/${id}/stop`, "POST"); setRefresh(value => value + 1); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Stop could not be requested."); }
    finally { setBusy(false); }
  }
  const live = data?.sessions.find(row => row.status !== "STOPPED");
  const ready = report?.configuration_complete && report.connections_verified && report.worker_online;
  return <>
    <section className="panel"><h2>Paper order access</h2><p>Turn on paper buying for a short window to place up to one order for one option. Risk, price and available-cash checks still apply. The window may end without an order.</p>
      <p>When the window ends or you turn it off, new orders stop. Any open trade is still monitored and managed.</p>
      {error && <p role="alert" className="error">{error}</p>}
      {data?.worker_mode !== "VALIDATION" && <p className="muted">Paper order checks need to be prepared in Trading permissions while your account is paused and has no open trades. This leaves buying turned off until you start the window here.</p>}
      {!ready && <p className="muted">Finish the setup steps and refresh the connection checks before starting. SWAN also checks the option and market hours.</p>}
      {!live && <form onSubmit={start}><fieldset disabled={busy || stale || !ready || data?.worker_mode !== "VALIDATION"}><label>Option ID from Trade<input name="instrument" required maxLength={100} autoComplete="off" /></label><label>Window length in minutes<input name="duration" type="number" min={1} max={15} defaultValue={5} required /></label><p className="muted">A paper strategy can place one order during this window.</p><button type="submit">Turn on paper buying</button></fieldset></form>}
      {live && <><h3>{words(live.status)}</h3><p>Option: {live.instrument_id} · Up to {live.max_quantity} units · Ends {time(live.expires_at)}</p><p>{live.stop_reason && words(live.stop_reason)}</p><button className="secondary" disabled={busy || live.status === "STOPPING"} onClick={() => stop(live.id)}>{live.status === "STOPPING" ? "Turning off…" : "Turn off paper buying"}</button></>}
    </section>
    <section className="panel"><h2>Validation records</h2><p>Recorded sessions do not automatically qualify autonomous trading.</p>{!data?.sessions.length ? <p>No controlled sessions recorded.</p> : data.sessions.map(row => <details key={row.id}><summary>{row.instrument_id} · {words(row.status)} · {time(row.expires_at)}</summary><p>Reference: {row.id}</p>{row.outcome ? <><p>{words(row.outcome.result)} · {row.outcome.entry_attempts} entry attempts · Reconciled: {row.outcome.reconciled ? "Yes" : "No"}</p><pre>{JSON.stringify(row.outcome, null, 2)}</pre></> : <p>Awaiting a flat, reconciled account before producing the final record.</p>}</details>)}</section>
  </>;
}
