"use client";
import { useEffect, useRef, useState } from "react";
import { money } from "@/lib/paper";
type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
export type PlacementPlan = { id: string; inputs: { lots: number; entry: string; stop_loss: string; target: string }; preview: { quantity: number; account_revision: number; expires_at: string; cash_required: string | null; planned_stop_loss: string | null; checks: { code: string; status: string }[] } };
type Receipt = { order_id: string; status: string; quantity: number; filled_quantity: number; manual_intent_id: string; instrument_id?: string };
type Status = { account_id: string; revision: number; ready: boolean; reason: string | null; worker_mode: string | null; session: { id: string; instrument_id: string; entry_source: string; status: string; max_quantity: number; expires_at: string } | null; order: Receipt | null };
type Command = { plan: string; request_id: string; expected_account_revision: number };
const messages: Record<string,string> = {
  MANUAL_ENTRY_CUTOFF: "New entries have closed for this session. You can still save a plan for later.",
  MANUAL_MARKET_CLOSED: "The market is closed or its session is unverified. Save a plan and return during market hours.",
  VALIDATION_WORKER_REQUIRED: "Manual paper trading is not prepared. Open Account, then Paper controls to prepare the trading monitor.",
  MANUAL_SESSION_REQUIRED: "Start a five-minute manual session when you are ready. It permits one entry of one lot for this contract.",
  ENTRY_SOURCE_MISMATCH: "Another entry mode owns the active session. Stop it in Account before starting a manual session.",
  MANUAL_ENTRY_USED: "This session has used its one entry. Track orders and positions in Orders.",
  MANUAL_WAITING: "Waiting for the trading monitor to finish session checks. Preview again once it is ready.",
  VALIDATION_SCOPE_EXCEEDED: "A session is active for another contract. Finish or stop that session first.",
  VALIDATION_STOPPING: "Session stopping. Existing exposure is still being managed.",
};
export default function ManualPlacement({ instrument, request, plan, visible, onLock, onSessionChange, onOrderRecorded }: { instrument: { id: string; underlying: string; strike: string; option_type: string; lot_size: number }; request: Request; plan: PlacementPlan | null; visible: boolean; onLock: (locked: boolean) => void; onSessionChange: () => void; onOrderRecorded: () => void }) {
  const [status,setStatus] = useState<Status | null>(null);
  const [refresh,setRefresh] = useState(0);
  const [error,setError] = useState<string | null>(null);
  const [busy,setBusy] = useState(false);
  const [review,setReview] = useState(false);
  const [receipt,setReceipt] = useState<Receipt | null>(null);
  const [pending,setPending] = useState<Command | null>(null);
  const command = useRef<Command | null>(null);
  const storageKey = useRef<string | null>(null);
  const restored = useRef<string | null>(null);
  const startCommand = useRef<{ request_id: string; expected_revision: number } | null>(null);
  const receiptSession = useRef<string | null>(null);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const statusRequest = useRef(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current=true; return () => { mounted.current=false; }; },[]);
  useEffect(() => { setReview(false); },[plan?.id]);
  useEffect(() => { if (review) reviewHeading.current?.focus(); },[review]);
  useEffect(() => {
    if (!visible) { setStatus(null); return; }
    let active = true;
    const abort = new AbortController();
    let running = false;
    async function load() {
      if (running) return;
      running=true;
      const sequence=++statusRequest.current;
      try {
        const next=await request(`/api/paper/manual/status?${new URLSearchParams({instrument_id:instrument.id})}`,"GET",abort.signal) as Status;
        if (active && sequence===statusRequest.current) setStatus(next);
      } catch { if (active && sequence===statusRequest.current) setStatus(null); }
      finally { running=false; }
    }
    void load();
    const timer=setInterval(() => void load(),4000);
    return () => { active=false; abort.abort(); clearInterval(timer); };
  },[request,instrument.id,visible,refresh]);
  function clearPending() {
    try { if (storageKey.current) sessionStorage.removeItem(storageKey.current); } catch { /* In-memory recovery remains available. */ }
    command.current=null; setPending(null); onLock(false);
  }
  function accepted(value: Receipt) {
    clearPending(); receiptSession.current=status?.session?.id ?? null; setReceipt(value); setReview(false); setError(null); onOrderRecorded();
    setRefresh(value=>value+1);
  }
  useEffect(() => {
    if (!status?.account_id) return;
    const key=`swan:pending-manual:${status.account_id}:${instrument.id}`;
    if (restored.current===key) return;
    restored.current=key; storageKey.current=key;
    try {
      const stored=JSON.parse(sessionStorage.getItem(key) ?? "null") as Command | null;
      const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      if (stored && uuid.test(stored.plan) && uuid.test(stored.request_id) && Number.isSafeInteger(stored.expected_account_revision) && stored.expected_account_revision>=0) {
        command.current=stored; setPending(stored); onLock(true);
      }
    } catch { /* Storage is optional; the server still enforces one entry. */ }
  },[status?.account_id,instrument.id,onLock]);
  useEffect(() => {
    if (status?.order && command.current?.request_id===status.order.manual_intent_id) accepted(status.order);
    if (status?.session?.id===startCommand.current?.request_id) startCommand.current=null;
    if (status?.session && receiptSession.current && status.session.id!==receiptSession.current) { setReceipt(null); receiptSession.current=null; }
  // The command is reconciled only against the authenticated server response.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[status]);
  const human=status?.session?.entry_source==="HUMAN";
  const serverOrder=status?.order?.instrument_id===instrument.id ? status.order : null;
  const currentOrder=serverOrder && (!receipt || serverOrder.manual_intent_id===receipt.manual_intent_id) ? serverOrder : receipt;
  const fresh=!!plan && Date.now()<Date.parse(plan.preview.expires_at);
  const ready=!!status?.ready && !!status.session && Date.now()<Date.parse(status.session.expires_at);
  const checked=!!plan && plan.preview.cash_required!=null && plan.preview.planned_stop_loss!=null && plan.preview.checks.length>0 && plan.preview.checks.every(c=>["MANUAL_SUBMISSION","ENTRY_MODE"].includes(c.code) || c.status==="passed");
  const canReview=ready && fresh && checked && !!plan && plan.preview.account_revision===status?.revision && plan.preview.quantity<=(status?.session?.max_quantity ?? 0) && !currentOrder;
  async function start() {
    if (!status || busy || command.current) return;
    const value=startCommand.current ?? {request_id:crypto.randomUUID(),expected_revision:status.revision};
    startCommand.current=value; setBusy(true); setError(null);
    try {
      await request("/api/validation/start","POST",AbortSignal.timeout(15000),{...value,instrument_id:instrument.id,entry_source:"HUMAN",duration_seconds:300});
      if (!mounted.current) return;
      startCommand.current=null; setReceipt(null); receiptSession.current=null; onSessionChange(); setRefresh(v=>v+1);
    } catch (cause) { if (mounted.current) { setError(cause instanceof Error ? cause.message : "Session could not be started."); if (typeof (cause as {status?:number})?.status==="number") startCommand.current=null; } }
    finally { if (mounted.current) setBusy(false); }
  }
  async function stop() {
    if (!human || !status?.session || busy) return;
    setBusy(true); setError(null);
    try { await request(`/api/validation/${status.session.id}/stop`,"POST",AbortSignal.timeout(15000)); if (mounted.current) { setReview(false); onSessionChange(); setRefresh(v=>v+1); } }
    catch(cause) { if (mounted.current) setError(cause instanceof Error ? cause.message : "Session stop could not be confirmed."); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function place() {
    if (busy || (!command.current && (!canReview || !review || !plan))) return;
    if (!command.current && (Date.now()>=Date.parse(plan!.preview.expires_at) || !status?.session || Date.now()>=Date.parse(status.session.expires_at))) {
      setReview(false); setError("Preview or session expired. Calculate a fresh preview before placing."); onSessionChange(); setRefresh(v=>v+1); return;
    }
    const value=command.current ?? {plan:plan!.id,request_id:crypto.randomUUID(),expected_account_revision:plan!.preview.account_revision};
    command.current=value; setPending(value); onLock(true); setBusy(true); setError(null);
    try { if (storageKey.current) sessionStorage.setItem(storageKey.current,JSON.stringify(value)); } catch { /* Keep the same command in memory when storage is unavailable. */ }
    try {
      const response=await request(`/api/paper/plans/${encodeURIComponent(value.plan)}/submit`,"POST",AbortSignal.timeout(15000),{request_id:value.request_id,expected_account_revision:value.expected_account_revision}) as Receipt;
      if (mounted.current) accepted(response);
    } catch (cause) {
      if (!mounted.current || !command.current) return;
      const code=(cause as {status?:number})?.status;
      const reason=(cause as {code?:string})?.code;
      if ((code===409 && !!reason && reason!=="MANUAL_REQUEST_CONFLICT") || (code===404 && reason==="PAPER_PLAN_NOT_FOUND")) {
        clearPending(); setReview(false); onSessionChange();
        setError(cause instanceof Error ? cause.message : "Order checks changed. Preview again.");
      } else setError("The order response is unconfirmed. Retry the same request to check its result; do not create another order.");
      setRefresh(v=>v+1);
    } finally { if (mounted.current) setBusy(false); }
  }
  return <section className="manual-placement" aria-label="Manual paper trading">
    <h4>Manual paper trading</h4>
    <p className="catalog-status" role="status">{status ? ready ? `Session ready · one entry, up to ${status.session!.max_quantity} units · ends ${new Date(status.session!.expires_at).toLocaleTimeString("en-IN",{timeZone:"Asia/Kolkata",hour:"2-digit",minute:"2-digit"})} IST` : messages[status.reason ?? ""] ?? "Manual session checks are not met. Review Account, then Paper controls before trying again." : "Checking session availability. Placement stays disabled until checks are current."}</p>
    {error && <p className="notice error" role="alert">{error}</p>}
    {currentOrder && <div className="manual-order-receipt" role="status"><strong>Paper order recorded</strong><p>{currentOrder.quantity} units · Last confirmed: {currentOrder.status.toLowerCase().replaceAll("_"," ")} · {currentOrder.filled_quantity} filled</p><small>Order {currentOrder.order_id}</small><p>Track current fills and protection in Orders. Acceptance does not guarantee a fill.</p></div>}
    {!status?.session && <button className="secondary" disabled={busy || !!pending || !status || status.reason!=="MANUAL_SESSION_REQUIRED"} onClick={()=>void start()}>{busy ? "Starting..." : startCommand.current ? "Retry session request" : "Start manual session"}</button>}
    {human && <button className="secondary" disabled={busy || status?.session?.status==="STOPPING"} onClick={()=>void stop()}>{busy ? "Working..." : "Stop manual session"}</button>}
    {plan && !currentOrder && !pending && <><button className="preview-action" disabled={busy || !canReview} onClick={()=>setReview(true)}>Review paper order</button>{!canReview && ready && <p className="catalog-status">Preview and save one lot with current costs and all planning checks met before reviewing.</p>}</>}
    {review && plan && !pending && !currentOrder && <div className="manual-order-review" aria-label="Review paper order"><h4 tabIndex={-1} ref={reviewHeading}>Review your paper order</h4><p>{instrument.underlying} {instrument.strike} {instrument.option_type==="CALL" ? "CE" : "PE"} · Buy limit</p><dl className="instrument-values"><div><dt>Quantity</dt><dd>{plan.inputs.lots} lot · {plan.preview.quantity} units</dd></div><div><dt>Limit</dt><dd>{money(plan.inputs.entry)}</dd></div><div><dt>Stop</dt><dd>{money(plan.inputs.stop_loss)}</dd></div><div><dt>Target</dt><dd>{money(plan.inputs.target)}</dd></div><div><dt>Cash including allowance</dt><dd>{plan.preview.cash_required==null ? "Unavailable" : money(plan.preview.cash_required)}</dd></div><div><dt>Planned loss including costs</dt><dd>{plan.preview.planned_stop_loss==null ? "Unavailable" : money(plan.preview.planned_stop_loss)}</dd></div></dl><p className="catalog-status">Simulated funds only. The server checks prices, fees and risk again. Stops and targets do not guarantee an exit price.</p><div className="actions"><button disabled={busy || !canReview} onClick={()=>void place()}>Place paper order</button><button className="secondary" disabled={busy} onClick={()=>setReview(false)}>Back</button></div>{!fresh && <p role="status">Preview expired. Calculate and save a fresh preview.</p>}</div>}
    {pending && !currentOrder && <button disabled={busy} onClick={()=>void place()}>{busy ? "Confirming order..." : "Retry same order request"}</button>}
  </section>;
}
