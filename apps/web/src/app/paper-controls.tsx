"use client";

import { useEffect, useState } from "react";
import type { ApiRequest, Readiness } from "@/lib/readiness";
import { time, words } from "@/lib/paper";

type Status = {
  revision: number; can_prepare: boolean; history_truncated?: boolean;
  runtime: { mode: string; status: string; heartbeat: string | null } | null;
  assessment: { matrix_version: string; passed: boolean; checks: { code: string; passed: boolean; evidence: string[] }[]; sessions: { session_id: string }[] };
  qualification: { id: string; valid: boolean; valid_until: string; scope: { instruments: { instrument_id: string; exchange: string; max_quantity: number; strategy_version: string }[] } } | null;
  arm: { id: string; status: string; expires_at: string; stop_reason: string | null } | null;
};

export default function PaperControls({ request, report }: { request: ApiRequest; report?: Readiness }) {
  const [data, setData] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const result = await request("/api/paper/qualification", "GET", controller.signal) as Status;
        if (!controller.signal.aborted) { setData(result); setStale(false); }
      } catch { if (!controller.signal.aborted) { setStale(true); setError("Paper control status is unavailable. Refresh before preparing or arming."); } }
      finally { if (!controller.signal.aborted) timer = setTimeout(load, 5000); }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [request, refresh]);
  async function action(path: string, body?: unknown, message?: string) {
    if (busy) return;
    setBusy(true); setError(null); setFeedback(null);
    try { await request(path, "POST", undefined, body); setFeedback(message ?? "Request recorded. Refreshing current state."); setRefresh(value => value + 1); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Request could not be completed."); }
    finally { setBusy(false); }
  }
  const ready = report?.configuration_complete && report.connections_verified && report.worker_online && report.market_state === "open";
  const active = data?.arm?.status === "ACTIVE";
  return <>
    <section className="panel"><h2>Paper operation controls</h2><p>Preparing a worker, qualifying evidence and arming entries are separate actions. Restart, pause, expired permission or changed inputs disable new entries. Existing exposure continues through exit management.</p>
      {error && <p className="error" role="alert">{error}</p>}{feedback && <p role="status">{feedback}</p>}{busy && <p role="status">Preparing or checking paper operation; worker preparation can take up to 45 seconds.</p>}
      <p>Worker mode: <strong>{data?.runtime ? words(data.runtime.mode) : "Unavailable"}</strong> · {data?.runtime ? words(data.runtime.status) : "No worker status"}</p>
      <p className="muted">A mode change requires a flat, paused account with no active validation or arm. It briefly restarts the local worker. Web and API remain available.</p>
      <div className="actions">{[["OBSERVATION", "Prepare observer"], ["VALIDATION", "Prepare validation worker"], ["AUTONOMOUS", "Prepare autonomous worker"]].map(([mode, label]) => <button key={mode} className="secondary" disabled={busy || stale || !data?.can_prepare} onClick={() => action("/api/worker/prepare", { mode, expected_revision: data!.revision }, "Worker preparation requested. Confirm its mode and heartbeat; entries remain paused.")}>{label}</button>)}</div>
      <p className="muted">Observation collects data without agent generation or entries. Validation requires a separate bounded session. Autonomous mode remains idle until qualified paper entries are explicitly armed.</p>
    </section>
    <section className="panel"><h2>Qualification and arming</h2><p>A session record alone does not qualify the system. The server inspects original market observations, genuine strategy reviews, orders, fills, recovery and reconciliation evidence for both venues.</p>
      {data?.history_truncated && <p className="notice">This assessment includes the latest 100 validation sessions. Older evidence is not included; explicit session IDs can be submitted through the qualification API.</p>}
      <details open={!data?.qualification?.valid}><summary>Qualification checklist · {data?.assessment.matrix_version ?? "Unavailable"}</summary>{data?.assessment.checks.map(check => <p key={check.code}><strong>{check.passed ? "Passed" : "Evidence required"}</strong> · {words(check.code)}{check.passed ? ` · ${check.evidence.length} evidence references` : ""}</p>)}</details>
      <button className="secondary" disabled={busy || stale || !data?.can_prepare || !data?.assessment.passed} onClick={() => action("/api/paper/qualification/review", { request_id: crypto.randomUUID(), expected_revision: data!.revision, session_ids: data!.assessment.sessions.map(row => row.session_id) })}>Review qualification evidence</button>
      {data?.qualification && <><p>Qualification: <strong>{data.qualification.valid ? "Valid for reviewed scope" : "Expired or invalidated"}</strong> · Valid until {time(data.qualification.valid_until)}</p><details><summary>Reviewed instruments and strategy versions</summary>{data.qualification.scope.instruments.map((scope, index) => <p key={index} style={{ overflowWrap: "anywhere" }}>{scope.exchange} · {scope.instrument_id} · {scope.max_quantity} units maximum · {scope.strategy_version}</p>)}</details></>}
      {active ? <><p>Paper permission active until {time(data!.arm!.expires_at)}. A fresh approved strategy and deterministic risk checks are still required for each entry.</p><button className="secondary" disabled={busy} onClick={() => action("/api/paper/disarm", undefined, "New entries disarmed. Follow Execution until existing exposure is resolved.")}>Disarm paper entries</button></> : <><p className="muted">Arming requires valid qualification, an autonomous worker, fresh setup/connection checks and an open verified session. Permission expires at the earliest applicable evidence, broker or entry cutoff.</p><button disabled={busy || stale || !ready || !data?.can_prepare || !data?.qualification?.valid || data?.runtime?.mode !== "AUTONOMOUS"} onClick={() => action("/api/paper/arm", { request_id: crypto.randomUUID(), expected_revision: data!.revision, qualification_id: data!.qualification!.id }, "Paper arming requested for the reviewed scope. No broker orders are placed.")}>Arm qualified paper entries</button>{data?.arm?.stop_reason && <p>Last disarm: {words(data.arm.stop_reason)}</p>}</>}
      {data?.qualification?.valid && <p><button className="secondary" disabled={busy} onClick={() => action(`/api/paper/qualification/${data.qualification!.id}/revoke`, undefined, "All account qualifications revoked and entries disarmed. Existing exposure still needs exit management.")}>Revoke qualification and disarm</button></p>}
    </section>
  </>;
}
