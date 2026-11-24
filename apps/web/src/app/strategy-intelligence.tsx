"use client";

import { useEffect, useState } from "react";
import { time, words } from "@/lib/paper";

type Assessment = {
  snapshot_id: string; strategy_id: string; version: string; session_key: string;
  as_of: string; status: string; reason_codes: string[]; evidence_ids: string[];
  range_high: string | null; range_low: string | null; target: string | null;
};
type Plan = {
  plan_id: string; strategy_id: string; version: string; session_key: string;
  as_of: string; outcome: string; reason_codes: string[]; evidence_ids: string[];
  direction: string | null; execution_eligible: false; mandate_state: string;
};
type Candidate = {
  candidate_id: string; strategy_id: string; version: string; created_at?: string;
  hypothesis: string; scope: string; assumptions: string[]; evaluation_method: string;
  evidence_ids: string[]; status: "INACTIVE_RESEARCH";
};
type PaperCandidate = {
  candidate_id: string; candidate_version: string; status: string;
  source_plan: { plan_id: string; strategy_id: string; version: string; outcome: string };
  blocker_codes: string[]; review_assignment_id: string; reviewed_at: string;
};
type CandidatePreflight = { candidate_id: string; status: string; can_submit: boolean; blocker_codes: string[] };
type Assignment = {
  assignment_id: string; state: string; created_at: string; deadline: string;
  snapshot_id: string | null; outcome: Record<string, unknown>;
  artifacts: { kind: string; approved?: boolean; disposition?: string; rationale?: string;
    scope?: string; hypothesis?: string; evaluation_method?: string; tool_statuses?: Record<string, string> }[];
};
type OperationSnapshot = {
  as_of: string; readiness?: { title: string; detail: string; market_state: string;
    worker_online: boolean; connections_verified: boolean; checks: { code: string; status: string; title: string }[] };
  account?: { enabled: boolean; daily_blocked: boolean };
  runtime?: { status: string; problem: string | null; heartbeat: string | null; resume_requested: boolean } | null;
  active_orders?: { id: string; status: string; side: string; instrument_id: string; filled_quantity: number; quantity: number }[];
  order_summary?: { active_count: number; active_truncated: boolean };
  fills?: { id: string; side: string; instrument_id: string; quantity: number; price: string; timestamp: string | null }[];
  positions?: { id: string; pending_exit: string | null; closed_at: string | null }[];
};
type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
type Props = { request: Request; onNavigate?: (page: string) => void };

function todayIST() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export default function StrategyIntelligence({ request, onNavigate }: Props) {
  const [session, setSession] = useState(todayIST);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [paperCandidates, setPaperCandidates] = useState<PaperCandidate[]>([]);
  const [preflights, setPreflights] = useState<CandidatePreflight[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [operation, setOperation] = useState<OperationSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [asOf, setAsOf] = useState(() => new Date().toISOString());
  const preflightById = new Map(preflights.map(item => [item.candidate_id, item]));
  const openPositions = operation?.positions?.filter(item => !item.closed_at) ?? [];

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const query = new URLSearchParams({ session_key: session, as_of: asOf, limit: "100" });
    const candidateQuery = new URLSearchParams({ as_of: asOf, limit: "50" });
    setBusy(true);
    setError(false);
    setAssessments([]);
    setPlans([]);
    setCandidates([]);
    setPreflights([]);
    setAssignments([]);
    setOperation(null);
    Promise.all([
      request(`/api/strategies/assessments?${query}`, "GET", controller.signal),
      request(`/api/strategies/plans?${query}`, "GET", controller.signal),
      request(`/api/strategies/research-candidates?${candidateQuery}`, "GET", controller.signal),
      request(`/api/strategies/paper-plan-candidates?${candidateQuery}`, "GET", controller.signal),
      request(`/api/strategies/paper-plan-candidates/preflight?${candidateQuery}`, "GET", controller.signal),
      request(`/api/strategies/assignments?${query}`, "GET", controller.signal),
      request("/api/workspace", "GET", controller.signal),
    ]).then(([a, p, c, pc, pf, assignmentsValue, workspace]) => {
      if (!active) return;
      setAssessments(list(a) as Assessment[]);
      setPlans(list(p) as Plan[]);
      setCandidates(list(c) as Candidate[]);
      setPaperCandidates(list(pc) as PaperCandidate[]);
      setPreflights(list(pf) as CandidatePreflight[]);
      setAssignments(list(assignmentsValue) as Assignment[]);
      setOperation(workspace as OperationSnapshot);
    }).catch(() => {
      if (active) setError(true);
    }).finally(() => {
      if (active) setBusy(false);
    });
    return () => { active = false; controller.abort(); };
  }, [request, session, asOf]);

  return <section className="panel strategy-intelligence" aria-label="Strategy intelligence">
    <div className="panelhead"><div><p className="eyebrow">PAPER LIFECYCLE</p><h2>Strategy intelligence</h2><p>Assessments, agent outcomes, admission blockers, and current paper operation state.</p></div><button className="secondary" disabled={busy} onClick={() => setAsOf(new Date().toISOString())}>Refresh records</button></div>
    <div className="button-row"><button className="secondary" onClick={() => onNavigate?.("Paper controls")}>Review paper controls</button><button className="secondary" onClick={() => onNavigate?.("Execution")}>Open execution</button></div>
    <label>Trading session<input type="date" value={session} onChange={event => setSession(event.target.value)} /></label>
    <p className="notice">Strategy candidates remain blocked until reviewed controls and protection are complete. This view does not authorize entries or change account risk settings.</p>
    {busy && <p role="status">Loading strategy records…</p>}
    {error && <p className="notice error" role="alert">Strategy records could not be loaded. Refresh the page or check the API migration status.</p>}
    {!busy && !error && <>
      <section aria-labelledby="strategy-operation-heading">
        <h3 id="strategy-operation-heading">Current paper operation</h3>
        {!operation ? <p className="empty-state">Paper operation state is unavailable.</p> : <>
          <p className="muted">Workspace snapshot {time(operation.as_of)} IST. Refresh to request a newer database snapshot.</p>
          <dl className="execution-values">
            <div><dt>Market session</dt><dd>{words(operation.readiness?.market_state ?? "unknown")}</dd></div>
            <div><dt>Worker</dt><dd>{operation.readiness?.worker_online ? words(operation.runtime?.status ?? "online") : "offline or unverified"}</dd></div>
            <div><dt>Last heartbeat</dt><dd>{time(operation.runtime?.heartbeat)}</dd></div>
            <div><dt>Account entries</dt><dd>{operation.account?.daily_blocked ? "blocked for today" : operation.account?.enabled ? "enabled by existing controls" : "paused"}</dd></div>
            <div><dt>Active orders</dt><dd>{operation.order_summary?.active_count ?? "Unavailable"}{operation.order_summary?.active_truncated ? " · list truncated" : ""}</dd></div>
            <div><dt>Open positions</dt><dd>{openPositions.length}</dd></div>
          </dl>
          {operation.runtime?.problem && <p className="notice error">Worker recovery/status: {words(operation.runtime.problem)}. Inspect the execution and paper control panels.</p>}
          {!!openPositions.length && <p className={openPositions.some(item => item.pending_exit) ? "notice error" : "notice"}>
            {openPositions.some(item => item.pending_exit) ? "An exit is pending or unresolved. Review Orders before further action." : "Open exposure is present. Exit monitoring and order coverage are shown in Execution."}
          </p>}
          {!!operation.readiness?.checks.length && <details><summary>Data and readiness checks</summary><ul>{operation.readiness.checks.map(check => <li key={check.code}>{words(check.status)} · {check.title}</li>)}</ul></details>}
          {!!operation.active_orders?.length && <details><summary>Working paper orders</summary><ul>{operation.active_orders.slice(0, 10).map(order => <li key={order.id}>{words(order.side)} · {words(order.status)} · {order.filled_quantity}/{order.quantity} filled · {order.instrument_id}</li>)}</ul></details>}
          {!!operation.fills?.length && <details><summary>Recent paper fills</summary><ul>{operation.fills.slice(0, 10).map(fill => <li key={fill.id}>{words(fill.side)} · {fill.quantity} · {fill.instrument_id} · {fill.price} · {fill.timestamp ? `${time(fill.timestamp)} IST` : "time unavailable"}</li>)}</ul></details>}
        </>}
      </section>
      <section aria-labelledby="strategy-assessments-heading">
        <h3 id="strategy-assessments-heading">Assessments · {session}</h3>
        {!assessments.length ? <p className="empty-state">No deterministic assessments are recorded for this session.</p> : assessments.map(item => <article className="execution-card" key={item.snapshot_id + item.strategy_id + item.as_of}>
          <div className="execution-card-head"><div><h4>{item.strategy_id} · {item.version}</h4><p>{words(item.status)}</p></div><time dateTime={item.as_of}>{time(item.as_of)} IST</time></div>
          {item.reason_codes.length > 0 && <p>Recorded reasons: {item.reason_codes.map(words).join(", ")}</p>}
          {(item.range_high || item.range_low || item.target) && <dl className="execution-values">{item.range_high && <div><dt>Opening range high</dt><dd>{item.range_high}</dd></div>}{item.range_low && <div><dt>Opening range low</dt><dd>{item.range_low}</dd></div>}{item.target && <div><dt>Underlying target</dt><dd>{item.target}</dd></div>}</dl>}
          <details><summary>Evidence and provenance</summary><p>Snapshot: <code>{item.snapshot_id}</code></p><p>{item.evidence_ids.length} cited bar records: {item.evidence_ids.map(id => <code key={id}>{id} </code>)}</p></details>
        </article>)}
      </section>
      <section aria-labelledby="strategy-agent-assignments-heading">
        <h3 id="strategy-agent-assignments-heading">Watcher and agent outcomes</h3>
        {!assignments.length ? <p className="empty-state">No watcher assignments are recorded for this session.</p> : assignments.map(item => {
          const result = item.outcome.result ?? item.outcome.reason ?? item.outcome.classification ?? item.state;
          return <article className="execution-card" key={item.assignment_id}>
            <div className="execution-card-head"><div><h4>{words(item.state)}</h4><p>Created {time(item.created_at)} IST · deadline {time(item.deadline)} IST</p></div><span className="status-pill">{words(String(result))}</span></div>
            {item.snapshot_id && <p>Source snapshot: <code>{item.snapshot_id}</code></p>}
            {!!item.artifacts.length && <details><summary>Saved workflow artifacts ({item.artifacts.length})</summary>{item.artifacts.map((artifact, index) => <div key={`${artifact.kind}-${index}`}><h4>{words(artifact.kind)}</h4>{artifact.disposition && <p>Analyst disposition: {words(artifact.disposition)}</p>}{artifact.approved != null && <p>Reviewer: {artifact.approved ? "approved" : "rejected"}</p>}{artifact.rationale && <p>{artifact.rationale}</p>}{artifact.hypothesis && <p>{artifact.hypothesis}</p>}{artifact.scope && <p>Scope: {artifact.scope}</p>}{artifact.evaluation_method && <p>Evaluation: {artifact.evaluation_method}</p>}{artifact.tool_statuses && <p>Tools: {Object.entries(artifact.tool_statuses).map(([name, state]) => `${words(name)} ${words(state)}`).join(" · ")}</p>}</div>)}</details>}
          </article>;
        })}
      </section>
      <section aria-labelledby="strategy-plans-heading">
        <h3 id="strategy-plans-heading">Plan drafts</h3>
        {!plans.length ? <p className="empty-state">No plan drafts are recorded for this session.</p> : plans.map(item => <article className="execution-card" key={item.plan_id}>
          <div className="execution-card-head"><div><h4>{item.strategy_id} · {item.version}</h4><p>{words(item.outcome)}{item.direction ? ` · ${words(item.direction)}` : ""}</p></div><span className="status-pill">Pending review</span></div>
          <p>Execution eligible: no. Mandate: {words(item.mandate_state)}.</p>
          {item.reason_codes.length > 0 && <p>Recorded reasons: {item.reason_codes.map(words).join(", ")}</p>}
          <details><summary>Linked evidence</summary><p>Plan: <code>{item.plan_id}</code></p><p>Evidence: {item.evidence_ids.map(id => <code key={id}>{id} </code>)}</p></details>
        </article>)}
      </section>
      <section aria-labelledby="strategy-paper-candidates-heading">
        <h3 id="strategy-paper-candidates-heading">Paper-plan candidates</h3>
        {!paperCandidates.length ? <p className="empty-state">No reviewed paper-plan candidates are recorded as of this view.</p> : paperCandidates.map(item => {
          const preflight = preflightById.get(item.candidate_id);
          return <article className="execution-card" key={item.candidate_id}>
            <div className="execution-card-head"><div><h4>{item.source_plan.strategy_id} · {item.source_plan.version}</h4><p>{words(item.source_plan.outcome)} · mandate {item.candidate_version}</p></div><span className="status-pill">Blocked</span></div>
            <p>Execution eligible: no. Reviewed {time(item.reviewed_at)} IST.</p>
            {!preflight ? <p>Current admission checks are unavailable.</p> : <><p>Current preflight: {words(preflight.status)}. Order submitted: no.</p>{!!preflight.blocker_codes.length && <ul>{preflight.blocker_codes.map(code => <li key={code}>{words(code)}</li>)}</ul>}</>}
            <details><summary>Candidate provenance</summary><p>Candidate: <code>{item.candidate_id}</code></p><p>Source plan: <code>{item.source_plan.plan_id}</code></p><p>Review assignment: <code>{item.review_assignment_id}</code></p></details>
          </article>;
        })}
      </section>
      <section aria-labelledby="strategy-candidates-heading">
        <h3 id="strategy-candidates-heading">Inactive research candidates</h3>
        {!candidates.length ? <p className="empty-state">No research candidates are recorded as of this view.</p> : candidates.map(item => <article className="execution-card" key={item.candidate_id}>
          <div className="execution-card-head"><div><h4>{item.strategy_id} · {item.version}</h4><p>{item.scope}</p></div><span className="status-pill">Inactive research</span></div>
          <p>{item.hypothesis}</p><p><strong>Evaluation method:</strong> {item.evaluation_method}</p>
          {item.assumptions.length > 0 && <p><strong>Assumptions:</strong> {item.assumptions.join("; ")}</p>}
          <details><summary>Evidence</summary><p>{item.evidence_ids.map(id => <code key={id}>{id} </code>)}</p></details>
        </article>)}
      </section>
    </>}
  </section>;
}
