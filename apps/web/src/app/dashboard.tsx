"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { User } from "firebase/auth";
import type { Readiness } from "@/lib/readiness";
import SystemSetup from "./system-setup";
import ValidationPanel from "./validation";
import PaperControls from "./paper-controls";
import ExecutionHistory, { ActiveOrders, FundsPanel, Positions } from "./execution";
import type { ExecutionData, Position } from "@/lib/paper";
import { money, time } from "@/lib/paper";

type Runtime = { status: string; problem: string | null; heartbeat: string | null; resume_requested: boolean; active_envelope: unknown };
type Workspace = ExecutionData & {
  as_of: string; mode: string;
  readiness?: Readiness;
  account: { cash: string; enabled: boolean; daily_blocked: boolean; revision: number; config: Record<string, unknown> };
  runtime: Runtime | null; positions: Position[]; journal: Position[];
  ledger: { id: string; timestamp: string; category: string; amount: string }[];
  evaluations: { id: string; slot_at: string; status: string; evidence_ids: string[] }[];
  events: { id: string; timestamp: string; kind: string; details: unknown }[];
};
type ChainRow = { instrument: { id: string; underlying: string; expiry: string; strike: string; option_type: string; lot_size: number }; quote: { timestamp: string; bid: string | null; ask: string | null; oi: number | null; volume: number | null; iv: string | null } };
type Chain = { rows: ChainRow[]; next_offset: number | null; as_of: string };
const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const errors: Record<string, string> = {
  AUTH_NOT_CONFIGURED: "Backend Firebase verification needs its server configuration.",
  ACCOUNT_NOT_AUTHORIZED: "Your Firebase identity has not been linked to an authorized paper account.",
  PAPER_ACCOUNT_NOT_CONFIGURED: "Your paper account and risk policy need to be configured.",
  AUTH_VERIFICATION_UNAVAILABLE: "Identity verification is temporarily unavailable.",
  SESSION_INVALID: "Your session has expired or was revoked. Sign in again.",
  DATABASE_UNAVAILABLE: "The account database is unavailable.",
  WORKER_NOT_READY_OR_DAILY_BLOCKED: "Resume is unavailable: the worker is offline or the daily loss limit is active.",
  PAUSE_AND_CLOSE_POSITIONS_BEFORE_SETTINGS: "Pause new entries and close all positions before changing risk limits.",
  SETTINGS_CHANGED_REFRESH_REQUIRED: "The account changed. Refresh before saving your risk limits.",
  INVALID_RISK_LIMITS: "Trade risk must not exceed the daily loss limit. Check the values and try again.",
  USE_EXPLICIT_PAPER_ARMING: "Use Paper controls to review qualification and explicitly arm paper entries.",
  PAPER_QUALIFICATION_REQUIRED: "Current qualification is missing, expired or invalidated. Review the evidence checklist in Paper controls.",
  PAPER_ARM_PREFLIGHT_INCOMPLETE: "Complete setup and refresh connection tests before arming paper entries.",
  QUALIFICATION_EVIDENCE_INCOMPLETE: "The required actual-market evidence is incomplete. Review the qualification checklist.",
  QUALIFICATION_CONFIGURATION_INCOMPLETE: "Resolve execution configuration evidence before reviewing qualification.",
  WORKER_PREPARATION_REQUIRES_FLAT_PAUSED_ACCOUNT: "Pause entries, stop validation or disarm, then resolve all orders and positions before changing worker mode.",
  WORKER_PREPARATION_FAILED: "The worker could not be prepared. Inspect private local logs and refresh its status.",
  LOCAL_SINGLE_OWNER_REQUIRED: "Local worker control requires the enrolled single-owner account.",
  AUTONOMOUS_WORKER_REQUIRED: "Prepare an autonomous worker first. Preparing it does not arm entries.",
  PAPER_ENGINE_NOT_READY: "Paper validation has not been completed. Review the specific requirements in System setup.",
  VALIDATION_WORKER_REQUIRED: "Start the validation worker before requesting a bounded session.",
  VALIDATION_PREFLIGHT_INCOMPLETE: "Complete configuration and refresh the connection tests in System setup.",
  VALIDATION_FRESH_CONTRACT_REQUIRED: "Select a contract with a current stored quote from Option chain.",
  VALIDATION_FRESH_DEPTH_REQUIRED: "The selected contract needs fresh, verified market depth.",
  VALIDATION_OPEN_CURRENT_SESSION_REQUIRED: "Validation requires an open, verified market session and a current account baseline.",
  VALIDATION_ALREADY_ACTIVE_OR_ARMED: "Stop the existing session and resolve exposure before starting another.",
  VALIDATION_REQUIRES_FLAT_RECONCILED_ACCOUNT: "Resolve pending orders and positions and reconcile the account first.",
  VALIDATION_INELIGIBLE_CONTRACT: "Select a current eligible contract whose actual lot fits the approved quantity limit.",
  VALIDATION_WINDOW_TOO_SHORT: "Refresh connection tests and broker login; at least one minute must remain before the entry cutoff.",
  WORKER_OBSERVATION_ONLY: "The managed worker observes only. Entries remain disabled pending paper validation.",
  PAUSE_AND_RESOLVE_ORDERS_POSITIONS_BEFORE_SETTINGS: "Pause entries and resolve every pending order and position before changing settings.",
  INVALID_SETUP_CONFIGURATION: "The imported configuration is invalid. Check its schema, source evidence and required values.",
  COMPLETE_RISK_POLICY_REQUIRED: "Every risk-policy field must be supplied and reviewed.",
  CONFIGURATION_WRITE_UNAVAILABLE: "Configuration could not be saved. Check the local file permissions.",
  CONNECTION_CHECK_UNAVAILABLE: "Another connection check is running, or the account is unavailable. Retry shortly.",
  CAPITAL_CHANGE_REQUIRES_LEDGER_OPERATION: "Capital cannot be changed through risk settings. An audited funding operation is required.",
};

export default function Dashboard({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const [tab, setTab] = useState("Overview");
  const [data, setData] = useState<Workspace | null>(null);
  const [chain, setChain] = useState<Chain | null>(null);
  const [underlying, setUnderlying] = useState("NIFTY");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [chainError, setChainError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [feedback, setFeedback] = useState<string | null>(null);

  const request = useCallback(async (path: string, method = "GET", signal?: AbortSignal, body?: unknown) => {
    const token = await user.getIdToken();
    const response = await fetch(base + path, { method, signal, cache: "no-store", headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
    const result = await response.json();
    if (!response.ok) {
      const message = typeof result.detail === "string" ? errors[result.detail] : null;
      throw new Error(message ?? (response.status === 422 ? "Some configuration fields are invalid or missing. Review the required fields and permitted ranges." : "Unable to complete the request. Check the connection and settings."));
    }
    return result;
  }, [user]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const workspace: Workspace = await request("/api/workspace", "GET", controller.signal);
        if (active) { setData(workspace); setError(null); setNow(Date.now()); }
        if (tab === "Option chain") {
          try {
            const options: Chain = await request(`/api/chain?underlying=${underlying}&offset=${offset}`, "GET", controller.signal);
            if (active) { setChain(options); setChainError(null); }
          } catch { if (active) { setChainError("Option observations could not be loaded. Account data is still available."); setChain(null); } }
        }
      } catch (cause) {
        if (active) { setError(cause instanceof Error ? cause.message : "Connection unavailable."); setChain(null); }
      } finally {
        if (active) timer = setTimeout(load, 5000);
      }
    }
    void load();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [request, tab, underlying, offset, refresh]);

  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);

  async function control(action: "pause" | "resume") {
    if (busy) return;
    setBusy(true); setActionError(null); setFeedback(null);
    try { await request(`/api/control/${action}`, "POST"); setFeedback(action === "pause" ? "New entries are paused." : "Resume requested. Entries wait for worker preflight and strategy approval."); setRefresh(value => value + 1); }
    catch (cause) { setActionError(cause instanceof Error ? cause.message : "Action unavailable."); }
    finally { setBusy(false); }
  }

  async function saveRisk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data || busy) return;
    const values = new FormData(event.currentTarget);
    setBusy(true); setActionError(null); setFeedback(null);
    try {
      const policy = { ...data.account.config };
      for (const key of ["max_positions", "quote_max_age_seconds", "entry_cutoff_minutes", "flatten_minutes", "max_fill_quantity", "min_volume", "min_oi", "max_spread_bps"]) policy[key] = key === "max_spread_bps" ? String(values.get(key)) : Number(values.get(key));
      policy.max_trade_risk_pct = String(Number(values.get("trade")) / 100);
      policy.max_daily_loss_pct = String(Number(values.get("daily")) / 100);
      policy.max_holding_seconds = Number(values.get("holding"));
      await request("/api/settings/risk-policy", "POST", undefined, {
        expected_revision: data.account.revision, policy, reviewed: values.get("reviewed") === "on",
      });
      setRefresh(value => value + 1);
      setFeedback("The complete risk policy is saved and reviewed. Entries remain paused.");
    } catch (cause) { setActionError(cause instanceof Error ? cause.message : "Unable to save risk policy."); }
    finally { setBusy(false); }
  }

  async function downloadJournal() {
    if (busy) return;
    setBusy(true); setActionError(null); setFeedback(null);
    try {
      const token = await user.getIdToken();
      const response = await fetch(base + "/api/reports/journal.csv", { cache: "no-store", headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("Journal export unavailable. Check your session and backend connection.");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = url; link.download = "swan-paper-journal.csv";
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) { setActionError(cause instanceof Error ? cause.message : "Export unavailable."); }
    finally { setBusy(false); }
  }

  const heartbeat = data?.runtime?.heartbeat;
  const workerOnline = heartbeat != null && now - Date.parse(heartbeat) >= 0 && now - Date.parse(heartbeat) <= 10000;
  const stale = data != null && (error !== null || now - Date.parse(data.as_of) > 15000);
  const ready = data?.readiness;

  return <main className="workspace">
    <header className="topbar"><div><p className="eyebrow">SWAN TRADE <span className="badge">PAPER ACCOUNT</span></p><h1>Trading workspace</h1><p className="subtitle">Your capital, positions and system health in one place.</p></div><div className="identity"><span>{user.email ?? user.displayName ?? "Signed in"}</span><button className="secondary" onClick={onSignOut}>Sign out</button></div></header>
    <nav className="tabs" aria-label="Workspace pages">{["Overview", "Execution", "Paper controls", "Paper validation", "Option chain", "Journal", "Activity", "Risk settings", "System setup"].map(name => <button key={name} aria-current={tab === name ? "page" : undefined} onClick={() => { setTab(name); setChain(null); setFeedback(null); }}>{name}</button>)}</nav>
    {error && <div className="notice error" role="alert">{error}<button className="secondary" onClick={() => setRefresh(value => value + 1)}>Retry</button></div>}
    {actionError && <p className="notice error" role="alert">{actionError}</p>}
    {feedback && <p className="notice" role="status">{feedback}</p>}
    {!data ? <section className="panel"><h2>{error ? "Workspace unavailable" : "Loading your workspace…"}</h2><p>Account balances and market observations appear after the authorized backend connects.</p></section> : <>
      <div className="statusline"><span className={`dot ${workerOnline ? "online" : ""}`} /><span>{workerOnline ? "Worker connected" : "Worker disconnected"}</span><span className="status-pill">{data.account.enabled && workerOnline ? "Entries enabled" : "Entries paused"}</span><span className="updated">Account synced {time(data.as_of)} IST</span><button className="text-button" onClick={() => setRefresh(value => value + 1)}>Refresh</button></div>
      {stale && <p className="notice error" role="status">Workspace data is stale. Controls are unavailable until it refreshes.</p>}
      {tab !== "System setup" && <aside className={`readiness-banner ${ready?.configuration_complete ? "waiting" : ""}`}><div><span className="eyebrow">{ready?.configuration_complete ? "SETUP STATUS" : "ACTION REQUIRED"}</span><h2>{ready?.title ?? "Readiness checks unavailable"}</h2><p>{!workerOnline && data.positions.length > 0 ? "Open positions have no connected worker monitoring. " : ""}{ready?.detail ?? "Refresh to load the server readiness report."}</p></div><button className="secondary" onClick={() => setTab("System setup")}>Review system setup <span aria-hidden="true">&rarr;</span></button></aside>}
      {tab === "Overview" && <>
        <div className="metrics"><article><p>Available paper cash</p><strong>{money(data.funds?.available_cash)}</strong><span>After reservations and restrictions</span></article><article><p>Open positions</p><strong>{data.positions.length}</strong><span>{data.order_summary ? `${data.order_summary.active_count} pending orders` : "Pending order count unavailable"}</span></article><article><p>New entries</p><strong>{data.account.enabled && workerOnline ? "Enabled" : "Paused"}</strong><span>{workerOnline ? "Worker connected" : "Worker connection required"}</span></article><article><p>Daily loss limit</p><strong>{Number(data.account.config.max_daily_loss_pct) * 100}%</strong><span>{data.account.daily_blocked ? "Limit reached · entries blocked" : "Configured in your risk policy"}</span></article></div>
        <FundsPanel funds={data.funds} />
        <ActiveOrders data={data} />
        <section className="panel"><div className="panelhead"><div><h2>Trading controls</h2><p>{workerOnline ? "Pause stops new entries while the worker continues to manage exits." : "Entries are unavailable while the worker is disconnected. Exit monitoring also requires the worker."}</p></div><div className="actions"><button className="secondary" disabled={busy || stale || (!data.account.enabled && !data.runtime?.resume_requested)} onClick={() => control("pause")}>Pause entries</button><button className="secondary" onClick={() => setTab("Paper controls")}>Review paper controls</button></div></div><p className="muted" id="resume-reason">Preparing a worker leaves entries paused. Review qualification and explicitly arm entries in Paper controls, or start a bounded session in Paper validation.</p></section>
        <div className="overview-grid">
        <section className="panel"><h2>Open positions</h2><Positions rows={data.positions} data={data} workerOnline={workerOnline} stale={stale} empty="No open paper positions." /></section>
        <section className="panel"><h2>Recent evaluations</h2>{data.evaluations.length ? <div className="tablewrap"><table><thead><tr><th>Time (IST)</th><th>Outcome</th><th>Evidence items</th></tr></thead><tbody>{data.evaluations.map(item => <tr key={item.id}><td>{time(item.slot_at)}</td><td>{item.status.replaceAll("_", " ")}</td><td>{item.evidence_ids.length}</td></tr>)}</tbody></table></div> : <p>No recorded evaluations.</p>}</section>
        </div>
      </>}
      {tab === "Execution" && <><FundsPanel funds={data.funds} /><ActiveOrders data={data} /><section className="panel"><h2>Open positions</h2><Positions rows={data.positions} data={data} workerOnline={workerOnline} stale={stale} empty="No open paper positions." /></section><ExecutionHistory data={data} /></>}
      {tab === "Paper controls" && <PaperControls request={request} report={ready} />}
      {tab === "Paper validation" && <ValidationPanel request={request} report={ready} />}
      {tab === "System setup" && (ready ? <SystemSetup report={ready} request={request} onRefresh={() => setRefresh(value => value + 1)} /> : <section className="panel"><h2>Readiness checks unavailable</h2><p>Refresh to retrieve the backend setup report.</p></section>)}
      {tab === "Option chain" && <section className="panel"><div className="panelhead"><div><h2>Observed option chain</h2><p>Latest stored observations. Missing fields remain unavailable.</p></div><label className="inline-label">Underlying<select value={underlying} onChange={event => { setUnderlying(event.target.value); setOffset(0); setChain(null); }}><option>NIFTY</option><option>SENSEX</option></select></label></div>{chainError ? <p className="error" role="alert">{chainError}</p> : chain == null ? <p>Loading observations…</p> : !chain.rows.length ? <p>No stored observations for {underlying}. Connect the market worker to populate this view.</p> : <div className="tablewrap"><table><thead><tr>{["Contract ID", "Expiry", "Strike", "Type", "Lot", "Bid", "Ask", "OI", "Volume", "IV %", "Observed (IST)", "Freshness"].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{chain.rows.map(({ instrument: item, quote }) => <tr key={item.id}><td><code>{item.id}</code></td><td>{item.expiry}</td><td>{item.strike}</td><td>{item.option_type}</td><td>{item.lot_size}</td><td>{quote.bid ?? "—"}</td><td>{quote.ask ?? "—"}</td><td>{quote.oi ?? "—"}</td><td>{quote.volume ?? "—"}</td><td>{quote.iv ?? "—"}</td><td>{time(quote.timestamp)}</td><td>{now - Date.parse(quote.timestamp) >= 0 && now - Date.parse(quote.timestamp) <= Number(data.account.config.quote_max_age_seconds) * 1000 ? "Fresh" : "Stale"}</td></tr>)}</tbody></table></div>}<div className="actions"><button className="secondary" disabled={offset === 0} onClick={() => { setOffset(Math.max(0, offset - 100)); setChain(null); }}>Previous</button><button className="secondary" disabled={chain?.next_offset == null} onClick={() => { setOffset(chain?.next_offset ?? 0); setChain(null); }}>Next</button></div></section>}
      {tab === "Journal" && <><section className="panel"><div className="panelhead"><h2>Closed positions</h2><button className="secondary" disabled={busy} onClick={downloadJournal}>Export CSV</button></div><p>Most recent 50 records. Realized P&amp;L includes recorded execution costs. CSV exports up to 10,000 closed positions.</p><Positions rows={data.journal} data={data} empty="No closed paper positions." /></section><section className="panel"><h2>Cash ledger</h2>{!data.ledger.length ? <p>No ledger entries recorded.</p> : <div className="tablewrap"><table><thead><tr><th>Time (IST)</th><th>Category</th><th>Amount</th></tr></thead><tbody>{data.ledger.map(item => <tr key={item.id}><td>{time(item.timestamp)}</td><td>{item.category}</td><td>{money(item.amount)}</td></tr>)}</tbody></table></div>}</section></>}
      {tab === "Activity" && <section className="panel"><h2>Account activity</h2><p>Most recent 50 persisted events.</p>{!data.events.length ? <p>No activity recorded.</p> : data.events.map(event => <details key={event.id}><summary>{time(event.timestamp)} · {event.kind.replaceAll("_", " ")}</summary><pre>{JSON.stringify(event.details, null, 2)}</pre></details>)}</section>}
      {tab === "Risk settings" && <section className="panel"><h2>Review your complete risk policy</h2><p>Pause entries and resolve pending orders and positions before saving. Capital is preserved in the ledger; changing it requires a separate funding operation.</p><form onSubmit={saveRisk} key={data.account.revision}><fieldset disabled={busy || stale || data.account.enabled || data.positions.length > 0 || (data.order_summary?.active_count ?? 1) > 0 || data.runtime?.resume_requested}><p>Configured paper capital: <strong>{money(String(data.account.config.capital))}</strong></p><div className="riskform">
        <label>Trade risk (% of capital)<input name="trade" type="number" required min="0.01" max="100" step="0.01" defaultValue={Number(data.account.config.max_trade_risk_pct) * 100} /></label>
        <label>Daily loss limit (% of capital)<input name="daily" type="number" required min="0.01" max="100" step="0.01" defaultValue={Number(data.account.config.max_daily_loss_pct) * 100} /></label>
        <label>Maximum holding (seconds)<input name="holding" type="number" required min="1" max="300" step="1" defaultValue={Number(data.account.config.max_holding_seconds)} /></label>
        {([ ["Maximum open positions", "max_positions", 1, undefined], ["Quote maximum age (seconds)", "quote_max_age_seconds", 1, 10], ["Stop new entries before close (minutes)", "entry_cutoff_minutes", 1, undefined], ["Request flatten before close (minutes)", "flatten_minutes", 1, undefined], ["Maximum fill quantity (units)", "max_fill_quantity", 1, undefined], ["Minimum observed volume", "min_volume", 0, undefined], ["Minimum open interest", "min_oi", 0, undefined], ["Maximum spread (basis points)", "max_spread_bps", 0.01, 10000] ] as const).map(([label, key, min, max]) => <label key={key}>{label}<input name={key} type="number" required min={min} max={max} step={key === "max_spread_bps" ? "0.01" : "1"} defaultValue={Number(data.account.config[key])} /></label>)}
        </div><p className="muted">Maximum quantity must accommodate an actual whole option lot. Entry cutoff must be earlier than flatten time. Execution policy and reviewed fees are configured separately.</p><label className="checkbox-label"><input name="reviewed" type="checkbox" required />I reviewed all limits, including quantity, liquidity and session cutoffs.</label><button type="submit">Save and review policy</button></fieldset></form><details><summary>Current complete policy</summary><pre>{JSON.stringify(data.account.config, null, 2)}</pre></details></section>}
    </>}
    <footer>Paper execution only · NIFTY &amp; SENSEX · All times Asia/Kolkata</footer>
  </main>;
}

