"use client";

import { useEffect, useRef, useState } from "react";
import { money, time } from "@/lib/paper";
import { usePaperRequest } from "./paper-action";
import OrderHistory from "./order-history";

type JournalRow = { id: string; quantity: number; closed_quantity: number; average_price: string; opened_at: string; closed_at: string; realized_pnl: string | null; entry_order_id: string; instrument: { underlying?: string; strike?: string; option_type?: string; expiry?: string } | null };
type Page = { rows: JournalRow[]; next_before: string | null };

export default function ClosedJournal() {
  const request = usePaperRequest();
  const [page, setPage] = useState<Page | null>(null);
  const [busy, setBusy] = useState(false);
  const [pageBusy, setPageBusy] = useState(false);
  const [error, setError] = useState(false);
  const [pageError, setPageError] = useState(false);
  const generation = useRef(0);
  const olderController = useRef<AbortController | null>(null);
  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    const current = ++generation.current;
    olderController.current?.abort();
    setPage(null); setBusy(true); setError(false); setPageError(false); setPageBusy(false);
    request("/api/paper/journal", "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]))
      .then(result => { if (current === generation.current) setPage(result as Page); })
      .catch(() => { if (current === generation.current) setError(true); })
      .finally(() => { if (current === generation.current) setBusy(false); });
    return () => { generation.current++; controller.abort(); olderController.current?.abort(); };
  }, [request]);
  async function loadOlder() {
    if (!request || !page?.next_before || pageBusy) return;
    const current = generation.current;
    const controller = new AbortController(); olderController.current = controller;
    setPageBusy(true); setPageError(false);
    try {
      const result = await request(`/api/paper/journal?${new URLSearchParams({ before: page.next_before })}`, "GET", AbortSignal.any([controller.signal, AbortSignal.timeout(15000)])) as Page;
      if (current === generation.current) setPage(previous => previous ? { rows: [...previous.rows, ...result.rows.filter(row => !previous.rows.some(existing => existing.id === row.id))], next_before: result.next_before } : previous);
    } catch { if (current === generation.current) setPageError(true); }
    finally { if (current === generation.current) setPageBusy(false); }
  }
  return <section aria-label="Closed paper positions">
    {busy && <p role="status">Loading closed positions…</p>}
    {error && <p className="notice error" role="alert">Journal history could not be loaded. Refresh the page to retry.</p>}
    {!busy && page && !page.rows.length && <p className="empty-state">No closed paper positions.</p>}
    {page?.rows.length ? <div className="position-list">{page.rows.map(row => <article className="execution-card" key={row.id}>
      <div className="execution-card-head"><strong>{row.instrument ? `${row.instrument.underlying ?? "Contract"} ${row.instrument.strike ?? ""} ${row.instrument.option_type ?? ""} / ${row.instrument.expiry ?? ""}` : "Contract details unavailable"}</strong><span className="status-pill">Closed</span></div>
      <dl className="execution-values"><div><dt>Closed units</dt><dd>{row.closed_quantity} / {row.quantity}</dd></div><div><dt>Average entry</dt><dd>{money(row.average_price)}</dd></div><div><dt>Realized P&amp;L</dt><dd>{money(row.realized_pnl)}</dd></div></dl>
      <p className="muted">Opened {time(row.opened_at)} IST · Closed {time(row.closed_at)} IST</p>
      <OrderHistory orderId={row.entry_order_id} label="Entry and exit history" />
    </article>)}</div> : null}
    {pageError && <p role="alert">Older positions could not be loaded. Current rows are still shown.</p>}
    {page?.next_before && <button className="secondary" disabled={pageBusy} onClick={loadOlder}>{pageBusy ? "Loading older positions…" : pageError ? "Retry older positions" : "Load older positions"}</button>}
  </section>;
}
