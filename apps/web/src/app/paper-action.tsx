"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

type Action = { kind: "cancel" | "exit"; id: string; label: string; quantity: number; requestId?: string };
type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
const Context = createContext<{ select: (action: Action) => void; locked: boolean; review?: ReactNode }>({ select: () => {}, locked: true });
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function PaperActionProvider({ ownerKey, request, onRefresh, children }: { ownerKey: string; request: Request; onRefresh: () => void; children: ReactNode }) {
  const [action, setAction] = useState<Action | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const command = useRef<Action | null>(null);
  const panel = useRef<HTMLElement>(null);
  const storageKey = `swan:paper-control:${ownerKey}`;
  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      if (saved && ["cancel", "exit"].includes(saved.kind) && uuid.test(saved.id) && uuid.test(saved.requestId) && typeof saved.label === "string" && saved.label.length <= 200 && Number.isSafeInteger(saved.quantity) && saved.quantity > 0) {
        command.current = saved; setAction(saved); setMessage("A previous request needs confirmation. Retry to check its result safely.");
      }
    } catch { /* Storage can be unavailable; the current command stays in memory. */ }
  }, [storageKey]);
  useEffect(() => { if (action) { panel.current?.focus(); panel.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); } }, [action]);
  async function confirm() {
    if (!action || busy) return;
    const pending = command.current ?? { ...action, requestId: crypto.randomUUID() };
    command.current = pending;
    try { sessionStorage.setItem(storageKey, JSON.stringify(pending)); } catch { /* Keep the in-memory identity. */ }
    setBusy(true); setAction(pending); setMessage("");
    try {
      const result = await request(`/api/paper/${pending.kind === "cancel" ? "orders" : "positions"}/${pending.id}/${pending.kind}`, "POST", AbortSignal.timeout(15000), { request_id: pending.requestId }) as { status: string; remaining_quantity?: number };
      setMessage(pending.kind === "cancel" ? result.status === "CANCELLED" ? "Unfilled entry units cancelled. Any completed fills remain in your positions." : `Order is ${result.status.toLowerCase().replaceAll("_", " ")}. Completed fills remain in your positions.` : result.status === "CLOSED" ? "Position is closed." : `Exit request recorded. ${result.remaining_quantity ?? "Remaining"} units still open. New entries are paused. Execution waits for monitoring and fresh market depth.`);
      command.current = null; setAction(null);
      try { sessionStorage.removeItem(storageKey); } catch { /* Receipt remains visible. */ }
      onRefresh();
    } catch (error) {
      const status = (error as { status?: number }).status;
      const code = (error as { code?: string }).code;
      if ((status === 404 || status === 409) && code !== "PAPER_ACTION_REQUEST_CONFLICT") {
        command.current = null; setAction(null);
        try { sessionStorage.removeItem(storageKey); } catch { /* No pending command. */ }
        setMessage("Request could not be completed. Refresh your account to check the current order or position."); onRefresh();
      } else setMessage("The result is unconfirmed. Retry this same request to check safely. If signed out, sign in again first.");
    } finally { setBusy(false); }
  }
  const review = (action || message) && <section ref={panel} tabIndex={-1} className="panel paper-action-review" aria-label="Order action review">
      {action && <><h2>{action.kind === "cancel" ? "Cancel remaining entry?" : "Exit this position?"}</h2><p><strong>{action.label}</strong> · {action.quantity} units shown</p><p>{action.kind === "cancel" ? "Only unfilled entry units are cancelled. Completed fills remain in your positions." : "Request an exit for the units still held and pause new entries. The request stays pending while monitoring or fresh market depth is unavailable."}</p><div className="actions"><button disabled={busy} onClick={confirm}>{busy ? "Checking request…" : command.current ? "Retry same request" : action.kind === "cancel" ? "Confirm cancellation" : "Request position exit"}</button>{!command.current && <button className="secondary" onClick={() => setAction(null)}>Back</button>}</div></>}
      {message && <p role="status">{message}</p>}
      {!action && <button className="secondary" onClick={() => setMessage("")}>Dismiss</button>}
    </section>;
  return <Context.Provider value={{ select: next => { if (!command.current && !busy) { setAction(next); setMessage(""); } }, locked: busy || !!command.current, review }}>{children}</Context.Provider>;
}

export function PaperActionButton({ kind, id, label, quantity, pending = false }: Action & { pending?: boolean }) {
  const control = useContext(Context);
  return <button className="secondary paper-action-button" disabled={control.locked || pending} onClick={() => control.select({ kind, id, label, quantity })}>{pending ? "Exit pending" : kind === "cancel" ? "Cancel remaining entry" : "Exit position"}</button>;
}

export function PaperActionStatus() { return useContext(Context).review; }
