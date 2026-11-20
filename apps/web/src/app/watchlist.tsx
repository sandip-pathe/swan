"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SelectedContract } from "./instrument-search";
import Icon from "./icons";
import { money } from "@/lib/paper";

type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
export type WatchRow = SelectedContract & { saved_at: string; status: "listed" | "expired" | "not_listed"; quote: (NonNullable<SelectedContract["quote"]> & { last_price?: string | null }) | null };
type Data = { rows: WatchRow[]; limit: number; as_of: string };

export function useWatchlist(request: Request, enabled: boolean, visible: boolean) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const generation = useRef(0);
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; generation.current++; }; }, []);

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!mounted.current) return;
    const ticket = ++generation.current;
    try {
      const result = await request("/api/watchlist", "GET", signal) as Data;
      if (mounted.current && ticket === generation.current) { setData(result); setError(null); }
    } catch (cause) { if (mounted.current && ticket === generation.current && !signal?.aborted) setError(cause instanceof Error ? cause.message : "Watchlist unavailable."); }
  }, [request]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      if (!pending.current && !document.hidden) await load(controller.signal);
      if (active && visible) timer = setTimeout(poll, 5000);
    }
    void poll();
    return () => { active = false; controller.abort(); clearTimeout(timer); generation.current++; };
  }, [enabled, visible, load]);

  async function change(instrumentId: string, save: boolean) {
    if (pending.current || !data || error) return;
    pending.current = true; generation.current++;
    setBusy(instrumentId); setFeedback(null);
    try {
      await request(`/api/watchlist/${save ? "save" : "remove"}`, "POST", undefined, { instrument_id: instrumentId });
      if (mounted.current) { setFeedback(save ? "Saved to watchlist." : "Removed from watchlist."); await load(); }
    } catch (cause) { if (mounted.current) setError(cause instanceof Error ? cause.message : "Watchlist could not be changed."); }
    finally { pending.current = false; if (mounted.current) setBusy(null); }
  }
  return { data, error, busy, feedback, change, retry: load };
}

export type WatchState = ReturnType<typeof useWatchlist>;

export default function Watchlist({ state, onOpen, onSearch, now, quoteAge }: { state: WatchState; onOpen: (row: WatchRow) => void; onSearch: () => void; now: number; quoteAge: number }) {
  const { data, error, busy, change } = state;
  return <section className="panel saved-watchlist" aria-label="Saved watchlist">
    <div className="panelhead"><div><h2>Watchlist</h2><p>{data ? `${data.rows.length} of ${data.limit} contracts` : "Your saved contracts"}</p></div><button className="secondary" onClick={onSearch}><Icon name="markets" />Find contracts</button></div>
    {error && <p className="notice error" role="alert">{error}<button className="secondary" onClick={() => void state.retry()}>Retry</button></p>}
    {!data && !error ? <p role="status" className="empty-state">Loading watchlist…</p> : data?.rows.length === 0 ? <div className="market-empty"><Icon name="star" /><strong>Keep your contracts close</strong><p>Tap the star beside a Search result to save it here.</p></div> : <div>{data?.rows.map(row => {
      const item = row.instrument;
      const name = `${item.underlying} ${item.strike} ${item.option_type === "CALL" ? "CE" : "PE"}`;
      const age = row.quote ? now - Date.parse(row.quote.timestamp) : Infinity;
      const recent = !error && age >= 0 && age <= quoteAge * 1000;
      return <article className="saved-contract" key={item.id}>
        <button className="saved-contract-open" onClick={() => onOpen(row)} aria-label={`Open chart for ${name} ${item.expiry}`}><strong>{name}</strong><small>{item.expiry} expiry · Lot {item.lot_size}</small><span className="saved-price">{row.quote?.last_price != null ? money(row.quote.last_price) : "Price unavailable"}</span><small>{row.quote ? `${recent ? "Recent quote" : "Last quote"} · ${new Date(row.quote.timestamp).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" })} IST` : "No saved quote yet"}</small>{row.status !== "listed" && <span className="saved-contract-status">{row.status === "expired" ? "Expired · saved history" : "Not in the latest contract list"}</span>}</button>
        <button className="secondary watch-star" disabled={busy != null || !!error} onClick={() => void change(item.id, false)} aria-label={`Remove ${name} from watchlist`}><Icon name="remove" /></button>
      </article>;
    })}</div>}
    {!!data?.rows.length && <p className="catalog-status">Prices show saved observations and their exchange time. A saved contract may not have a current quote.</p>}
  </section>;
}
