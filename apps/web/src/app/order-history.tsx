"use client";

import { useEffect, useId, useRef, useState } from "react";
import { money, time, words } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";

type Related = { id: string; side: string; status: string; quantity: number; filled_quantity: number; order_type: string; reason: string; limit_price: string | null; trigger_price: string | null };
type Event = { id: string; kind: string; timestamp: string; fill_recorded: boolean; detail: { quantity?: number; price?: string; fees?: string; fee_breakdown?: Record<string, string>; limit_price?: string | null; trigger_price?: string | null; before?: Record<string, string | null>; after?: Record<string, string | null> } };
type History = { as_of: string; order: Related & { source: string; legacy: boolean }; instrument: { underlying: string; strike: string; option_type: string; expiry: string; exchange: string } | null; fills: { quantity: number; average_price: string | null; premium: string; fees: string; cash_movement: string }; position: { id: string; remaining_quantity: number; closed: boolean; stop_loss: string; target: string; pending_exit: string | null; realized_pnl: string | null } | null; related_orders: Related[]; related_truncated: boolean; related_next_before: string | null; events: Event[]; next_before: string | null };
const titles: Record<string, string> = { ACCEPTED: "Order accepted", AMENDED: "Order changed", FILL: "Trade filled", CANCEL_REQUESTED: "Cancellation requested", CANCELLED: "Cancellation acknowledged", EXPIRED: "Order expired", TRIGGERED: "Stop triggered", PRICE_PROTECTION_SET: "Execution price bound set", REJECTED: "Order rejected" };

function EventDetail({ event }: { event: Event }) {
  const detail = event.detail;
  if (event.kind === "FILL") return event.fill_recorded ? <><p>{detail.quantity} units at {money(detail.price)}</p><p>Fees {money(detail.fees)}</p><details><summary>Fee breakdown</summary><dl className="execution-values">{Object.entries(detail.fee_breakdown ?? {}).map(([key, value]) => <div key={key}><dt>{words(key)}</dt><dd>{money(value)}</dd></div>)}</dl></details></> : <p>Linked fill details unavailable. Refresh to check the recorded trade.</p>;
  if (event.kind === "AMENDED") return <dl className="execution-values">{(["entry", "stop_loss", "target", "reserved_cash", "reserved_risk"] as const).map(key => <div key={key}><dt>{words(key)}</dt><dd>{money(detail.before?.[key])} {"\u2192"} {money(detail.after?.[key])}</dd></div>)}</dl>;
  if (event.kind === "ACCEPTED") return <p>{detail.quantity ?? "Unknown"} units{detail.limit_price ? ` Ã‚Â· Limit ${money(detail.limit_price)}` : ""}{detail.trigger_price ? ` Ã‚Â· Trigger ${money(detail.trigger_price)}` : ""}. Acceptance is not a fill.</p>;
  if (event.kind === "CANCEL_REQUESTED") return <p>Unfilled units await cancellation acknowledgement.</p>;
  if (event.kind === "CANCELLED") return <p>Cancellation was processed. Any completed fills remain recorded above.</p>;
  return detail.trigger_price || detail.limit_price ? <p>{detail.trigger_price ? `Trigger ${money(detail.trigger_price)}` : `Price bound ${money(detail.limit_price)}`}</p> : null;
}

export default function OrderHistory({ orderId, label = "Order timeline" }: { orderId: string; label?: string }) {
  const request = usePaperRequest();
  const panelId = useId();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(orderId);
  const [data, setData] = useState<History | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [relatedError, setRelatedError] = useState(false);
  const active = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => () => { generation.current++; active.current?.abort(); }, []);
  async function load(id: string, before?: string) {
    if (!request) return;
    active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    const current = ++generation.current;
    setBusy(true); setError(""); setRelatedError(false);
    if (!before) setData(null);
    try {
      const result = await request(`/api/paper/orders/${id}/history${before ? `?before=${encodeURIComponent(before)}` : ""}`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)])) as History;
      if (generation.current !== current) return;
      setData(previous => before && previous ? { ...result, events: [...previous.events, ...result.events.filter(event => !previous.events.some(old => old.id === event.id))], related_orders: [...previous.related_orders, ...result.related_orders.filter(row => !previous.related_orders.some(old => old.id === row.id))], related_next_before: previous.related_next_before, related_truncated: previous.related_truncated } : result);
    } catch {
      if (generation.current === current) setError("Order history could not be loaded. Check your connection and try again.");
    } finally { if (generation.current === current) setBusy(false); }
  }
  async function loadRelated(before?: string) {
    if (!request || !before) return;
    active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    const current = ++generation.current;
    setBusy(true); setRelatedError(false);
    try {
      const result = await request(`/api/paper/orders/${selected}/history?${new URLSearchParams({ related_before: before })}`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)])) as History;
      if (generation.current === current) setData(previous => previous ? { ...result, events: previous.events, related_orders: [...previous.related_orders, ...result.related_orders.filter(row => !previous.related_orders.some(old => old.id === row.id))] } : previous);
    } catch {
      if (generation.current === current) setRelatedError(true);
    } finally { if (generation.current === current) setBusy(false); }
  }
  function select(id: string) { setSelected(id); load(id); heading.current?.focus(); }
  function toggle() {
    if (open) { generation.current++; active.current?.abort(); setBusy(false); setOpen(false); }
    else { setOpen(true); setSelected(orderId); load(orderId); }
  }
  return <div className="order-history"><button className="secondary" aria-expanded={open} aria-controls={panelId} onClick={toggle}>{open ? "Close timeline" : label}</button>
    {open && <section id={panelId} aria-label="Order timeline" aria-busy={busy} className="order-timeline-panel">
      <div className="panelhead"><h3 ref={heading} tabIndex={-1}>Order timeline</h3><button className="text-button" disabled={busy} onClick={() => load(selected)}>Refresh timeline</button></div>
      {selected !== orderId && <button className="secondary" disabled={busy} onClick={() => select(orderId)}>Back to original order</button>}
      {busy && <p role="status">Loading order historyÃ¢â‚¬Â¦</p>}
      {error && <p role="alert">{error} <button className="secondary" onClick={() => load(selected, data?.next_before ?? undefined)}>Retry history</button></p>}
      {data && <>
        {data.instrument && <p><strong>{data.instrument.underlying} {data.instrument.strike} {data.instrument.option_type}</strong><br /><span className="muted">{data.instrument.expiry} Ã‚Â· {data.instrument.exchange}</span></p>}
        <p><span className="status-pill">{words(data.order.side)} Ã‚Â· {words(data.order.status)}</span> Ã‚Â· {data.order.source === "HUMAN" ? "Manual entry" : data.order.source === "AI" ? "Automated entry" : "Source unavailable"}</p>
        <dl className="execution-values"><div><dt>Recorded fills</dt><dd>{data.fills.quantity} / {data.order.quantity} units</dd></div><div><dt>Average fill price</dt><dd>{money(data.fills.average_price)}</dd></div><div><dt>Total fees</dt><dd>{money(data.fills.fees)}</dd></div><div><dt>Net cash movement</dt><dd>{money(data.fills.cash_movement)}</dd></div></dl>
        <p className="muted">Cash movement includes these fills and fees. Sale proceeds may remain restricted.</p>
        {data.position && <div className="timeline-position"><h4>{data.position.closed ? "Closed position" : "Linked position"}</h4><p>{data.position.remaining_quantity} units open{data.position.pending_exit ? ` Ã‚Â· Exit pending: ${words(data.position.pending_exit)}` : ""}</p><dl className="execution-values"><div><dt>Stop</dt><dd>{money(data.position.stop_loss)}</dd></div><div><dt>Target</dt><dd>{money(data.position.target)}</dd></div><div><dt>Realized P&amp;L</dt><dd>{money(data.position.realized_pnl)}</dd></div></dl></div>}
        {!!data.related_orders.length && <div className="timeline-related"><h4>Entry and exit orders</h4><p className="muted">An exit order can be pending, replaced or cancelled. Its presence does not guarantee a fill.</p>{data.related_orders.map(order => <button className="secondary" key={order.id} disabled={busy} onClick={() => select(order.id)}>{words(order.side)} Ã‚Â· {words(order.reason)} Ã‚Â· {words(order.status)}<small>{order.filled_quantity} / {order.quantity} units filled</small></button>)}{relatedError && <p role="alert">More related orders could not be loaded. Current orders are still shown.</p>}{data.related_next_before && <button className="secondary" disabled={busy} onClick={() => loadRelated(data.related_next_before!)}>{busy ? "Loading related orders..." : relatedError ? "Retry related orders" : "Load more related orders"}</button>}{data.related_truncated && !data.related_next_before && <p>Some related orders are unavailable.</p>}</div>}
        <h4>Activity Ã‚Â· newest first</h4><p className="muted">Snapshot {time(data.as_of)} IST. Refresh for new activity.</p>
        {!data.events.length ? <p>No recorded lifecycle events{data.order.legacy ? " for this earlier order" : ""}.</p> : <ol className="order-event-list">{data.events.map(event => <li key={event.id}><strong>{titles[event.kind] ?? "Order activity recorded"}</strong><time dateTime={event.timestamp}>{time(event.timestamp)} IST</time><EventDetail event={event} /></li>)}</ol>}
        {data.next_before && <button className="secondary" disabled={busy} onClick={() => load(selected, data.next_before!)}>Load older activity</button>}
      </>}
    </section>}
  </div>;
}
