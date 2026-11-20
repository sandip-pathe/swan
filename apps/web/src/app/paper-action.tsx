"use client";

import { money } from "@/lib/paper";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

type Action = { kind: "cancel" | "exit" | "amend"; id: string; label: string; quantity: number; requestId?: string; entry?: string; stop_loss?: string; target?: string; expected_account_revision?: number };
type AmendmentPreview = { account_revision: number; quantity: number; before: Record<string, string>; after: Record<string, string>; expires_at: string };
const validPrices = (action: Action) => [action.entry, action.stop_loss, action.target].every(value => typeof value === "string" && /^\d+(\.\d{1,4})?$/.test(value) && Number(value) > 0) && Number(action.stop_loss) < Number(action.entry) && Number(action.entry) < Number(action.target);
type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
const Context = createContext<{ select: (action: Action) => void; locked: boolean; review?: ReactNode; request?: Request }>({ select: () => {}, locked: true });
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function PaperActionProvider({ ownerKey, revision, request, onRefresh, children }: { ownerKey: string; revision?: number; request: Request; onRefresh: () => void; children: ReactNode }) {
  const [action, setAction] = useState<Action | null>(null);
  const [preview, setPreview] = useState<AmendmentPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const command = useRef<Action | null>(null);
  const panel = useRef<HTMLElement>(null);
  const storageKey = `swan:paper-control:${ownerKey}`;
  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      if (saved && ["cancel", "exit", "amend"].includes(saved.kind) && uuid.test(saved.id) && uuid.test(saved.requestId) && typeof saved.label === "string" && saved.label.length <= 200 && Number.isSafeInteger(saved.quantity) && saved.quantity > 0 && (saved.kind !== "amend" || (validPrices(saved) && Number.isSafeInteger(saved.expected_account_revision) && saved.expected_account_revision >= 0))) {
        command.current = saved; setAction(saved); setMessage("A previous request needs confirmation. Retry to check its result safely.");
      }
    } catch { /* Storage can be unavailable; the current command stays in memory. */ }
  }, [storageKey]);
  useEffect(() => { if (action) { panel.current?.focus(); panel.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); } }, [action?.id, action?.kind]);
  async function previewAmend() {
    if (!action || busy || !validPrices(action) || revision == null) return;
    setBusy(true); setMessage(""); setPreview(null);
    try {
      const result = await request(`/api/paper/orders/${action.id}/amend/preview`, "POST", AbortSignal.timeout(15000), { expected_account_revision: revision, entry: action.entry, stop_loss: action.stop_loss, target: action.target }) as AmendmentPreview;
      setPreview(result); setAction({ ...action, expected_account_revision: result.account_revision });
    } catch { setMessage("The change is unavailable at these prices or the order has changed. Refresh your account and review again. Your order was not amended."); }
    finally { setBusy(false); }
  }
  async function confirm() {
    if (!action || busy) return;
    if (action.kind === "amend" && !command.current && (!preview || Date.parse(preview.expires_at) <= Date.now())) { setPreview(null); setMessage("The estimate expired. Preview the change again."); return; }
    const pending = command.current ?? { ...action, requestId: crypto.randomUUID() };
    command.current = pending;
    try { sessionStorage.setItem(storageKey, JSON.stringify(pending)); } catch { /* Keep the in-memory identity. */ }
    setBusy(true); setAction(pending); setMessage("");
    try {
      const result = await request(`/api/paper/${pending.kind === "exit" ? "positions" : "orders"}/${pending.id}/${pending.kind}`, "POST", AbortSignal.timeout(15000), { request_id: pending.requestId, ...(pending.kind === "amend" ? { expected_account_revision: pending.expected_account_revision, entry: pending.entry, stop_loss: pending.stop_loss, target: pending.target } : {}) }) as { status: string; remaining_quantity?: number };
      setMessage(pending.kind === "amend" ? "Order amended. Revised entry, stop and target are recorded. Acceptance is not a fill." : pending.kind === "cancel" ? result.status === "CANCELLED" ? "Unfilled entry units cancelled. Any completed fills remain in your positions." : `Order is ${result.status.toLowerCase().replaceAll("_", " ")}. Completed fills remain in your positions.` : result.status === "CLOSED" ? "Position is closed." : `Exit request recorded. ${result.remaining_quantity ?? "Remaining"} units still open. New entries are paused. Execution waits for monitoring and fresh market depth.`);
      command.current = null; setAction(null);
      try { sessionStorage.removeItem(storageKey); } catch { /* Receipt remains visible. */ }
      onRefresh();
    } catch (error) {
      const status = (error as { status?: number }).status;
      const code = (error as { code?: string }).code;
      if ((status === 404 || status === 409) && code !== "PAPER_ACTION_REQUEST_CONFLICT" && code !== "MANUAL_REQUEST_CONFLICT") {
        command.current = null; setAction(null);
        try { sessionStorage.removeItem(storageKey); } catch { /* No pending command. */ }
        setMessage("Request could not be completed. Refresh your account to check the current order or position."); onRefresh();
      } else setMessage("The result is unconfirmed. Retry this same request to check safely. If signed out, sign in again first.");
    } finally { setBusy(false); }
  }
  const review = (action || message) && <section ref={panel} tabIndex={-1} className="panel paper-action-review" aria-label="Order action review">
      {action && <><h2>{action.kind === "amend" ? "Change pending entry" : action.kind === "cancel" ? "Cancel remaining entry?" : "Exit this position?"}</h2><p><strong>{action.label}</strong> · {action.quantity} units shown</p>
        {action.kind === "amend" ? <>
          <p>Only a wholly unfilled manual entry can change. Quantity stays unchanged and expiry cannot be extended. A fill or cancellation can prevent the change.</p>
          {!command.current && !preview && <form onSubmit={event => { event.preventDefault(); previewAmend(); }}><fieldset disabled={busy}><div className="amend-fields">{(["entry", "stop_loss", "target"] as const).map(field => <label key={field}>{field === "entry" ? "Entry limit" : field === "stop_loss" ? "Stop loss" : "Target"}<input required inputMode="decimal" type="text" value={action[field] ?? ""} onChange={event => { setAction({ ...action, [field]: event.target.value }); setPreview(null); setMessage(""); }} /></label>)}</div><button className="secondary" disabled={!validPrices(action) || revision == null} type="submit">{busy ? "Checking prices..." : "Preview change"}</button></fieldset></form>}
          {(preview || command.current) && <><h3>Review revised order</h3><dl className="execution-values">{(["entry", "stop_loss", "target"] as const).map(field => <div key={field}><dt>{field === "entry" ? "Entry limit" : field === "stop_loss" ? "Stop loss" : "Target"}</dt><dd>{preview ? `${money(preview.before[field])} \u2192 ` : ""}{money(action[field])}</dd></div>)}{preview && <><div><dt>Cash reserved</dt><dd>{money(preview.before.reserved_cash)} {"\u2192"} {money(preview.after.reserved_cash)}</dd></div><div><dt>Risk reserved</dt><dd>{money(preview.before.reserved_risk)} {"\u2192"} {money(preview.after.reserved_risk)}</dd></div></>}</dl><p className="muted">Confirmation repeats the current account and market checks.</p>{!command.current && <button className="secondary" onClick={() => setPreview(null)}>Edit prices</button>}</>}
        </> : <p>{action.kind === "cancel" ? "Only unfilled entry units are cancelled. Completed fills remain in your positions." : "Request an exit for the units still held and pause new entries. The request stays pending while monitoring or fresh market depth is unavailable."}</p>}
        <div className="actions">{(action.kind !== "amend" || preview || command.current) && <button disabled={busy} onClick={confirm}>{busy ? "Checking request..." : command.current ? "Retry same request" : action.kind === "amend" ? "Confirm order change" : action.kind === "cancel" ? "Confirm cancellation" : "Request position exit"}</button>}{!command.current && <button className="secondary" disabled={busy} onClick={() => { setAction(null); setPreview(null); }}>Back</button>}</div></>}

      {message && <p role="status">{message}</p>}
      {!action && <button className="secondary" onClick={() => setMessage("")}>Dismiss</button>}
    </section>;
  return <Context.Provider value={{ select: next => { if (!command.current && !busy) { setAction(next); setPreview(null); setMessage(""); } }, locked: busy || !!command.current, review, request }}>{children}</Context.Provider>;
}

export function PaperActionButton({ kind, id, label, quantity, entry, stop_loss, target, pending = false }: Action & { pending?: boolean }) {
  const control = useContext(Context);
  return <button className="secondary paper-action-button" disabled={control.locked || pending} onClick={() => control.select({ kind, id, label, quantity, entry, stop_loss, target })}>{pending ? "Exit pending" : kind === "amend" ? "Change order" : kind === "cancel" ? "Cancel remaining entry" : "Exit position"}</button>;
}

export function PaperActionStatus() { return useContext(Context).review; }

export function usePaperRequest() { return useContext(Context).request; }
