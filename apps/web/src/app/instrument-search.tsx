"use client";

import { useEffect, useState } from "react";
import type { ChartContract } from "./candles";
import Icon from "./icons";

type Contract = ChartContract & { tick_size: string };
export type SelectedContract = { instrument: ChartContract; quote: { timestamp: string } | null };
type Results = { rows: Contract[]; expiries: string[]; next_offset: number | null; catalog_at: string | null; stale: boolean };
type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;

export default function InstrumentSearch({ request, underlying, onMarket, onOpen }: { request: Request; underlying: string; onMarket: (value: string) => void; onOpen: (result: SelectedContract) => void }) {
  const [query, setQuery] = useState("");
  const [expiry, setExpiry] = useState("");
  const [side, setSide] = useState("");
  const [offset, setOffset] = useState(0);
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setResults(null); setError(null);
    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ underlying, q: query, offset: String(offset) });
        if (expiry) params.set("expiry", expiry);
        if (side) params.set("option_type", side);
        const result = await request(`/api/market/instruments?${params}`, "GET", controller.signal) as Results;
        if (active) setResults(result);
      } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : "Contracts could not be loaded."); }
    }, 250);
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [request, underlying, query, expiry, side, offset, refresh]);

  async function refreshCatalog() {
    if (busy) return;
    setBusy("refresh"); setError(null);
    try { await request("/api/market/instruments/refresh", "POST"); setOffset(0); setRefresh(value => value + 1); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Contracts could not be refreshed."); }
    finally { setBusy(null); }
  }

  async function open(item: Contract) {
    if (busy) return;
    setBusy(item.id); setError(null);
    try {
      const result = await request("/api/market/instruments/selected", "POST", undefined, { instrument_id: item.id }) as SelectedContract;
      onOpen(result);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "This contract could not be opened."); }
    finally { setBusy(null); }
  }

  return <section className="panel instrument-search" aria-label="Contract search">
    <div className="panelhead"><div><h2>Find a contract</h2><p>NIFTY &amp; SENSEX options</p></div><button className="secondary" disabled={busy != null} onClick={refreshCatalog}><Icon name="refresh" />{busy === "refresh" ? "Loading…" : "Refresh contracts"}</button></div>
    <div className="contract-filters">
      <label className="contract-query">Search<input type="search" value={query} maxLength={60} placeholder="Strike, index or CE / PE" autoComplete="off" onChange={event => { setQuery(event.target.value); setOffset(0); }} /></label>
      <label>Market<select value={underlying} onChange={event => { onMarket(event.target.value); setExpiry(""); setOffset(0); }}><option>NIFTY</option><option>SENSEX</option></select></label>
      <label>Option type<select value={side} onChange={event => { setSide(event.target.value); setOffset(0); }}><option value="">Calls &amp; puts</option><option value="CALL">Calls · CE</option><option value="PUT">Puts · PE</option></select></label>
      <label className="contract-expiry">Expiry<select value={expiry} onChange={event => { setExpiry(event.target.value); setOffset(0); }}><option value="">All listed expiries</option>{(results?.expiries ?? (expiry ? [expiry] : [])).map(value => <option key={value}>{value}</option>)}</select></label>
    </div>
    {error && <p className="notice error" role="alert">{error}<button className="secondary" onClick={() => setRefresh(value => value + 1)}>Retry search</button></p>}
    {results?.catalog_at && <p className="catalog-status">Contracts updated {new Date(results.catalog_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} IST{results.stale ? ". Refresh contracts before opening a result." : ". Prices load separately in the chart."}</p>}
    {results == null && !error ? <p className="empty-state" role="status">Searching contracts…</p> : results?.catalog_at == null && !error ? <div className="market-empty"><Icon name="markets" /><strong>No contract list saved yet</strong><p>Use Refresh contracts to load listed options. This does not retrieve prices.</p></div> : results && !results.rows.length ? <div className="market-empty"><strong>No matching contracts</strong><p>Try another strike, expiry or option type.</p></div> : <div className="contract-results">{results?.rows.map(item => <button className="contract-result" key={item.id} disabled={busy != null || results.stale} onClick={() => open(item)} aria-label={`Open chart for ${item.underlying} ${item.strike} ${item.option_type === "CALL" ? "CE" : "PE"} ${item.expiry}`}><span><strong>{item.underlying} {item.strike} <span className="option-side">{item.option_type === "CALL" ? "CE" : "PE"}</span></strong><small>{item.expiry} expiry · Lot {item.lot_size} · Tick ₹{item.tick_size}</small></span><span className="result-action">{busy === item.id ? "Opening…" : "Chart"}<Icon name="arrow" /></span></button>)}</div>}
    {results && (offset > 0 || results.next_offset != null) && <div className="actions"><button className="secondary" disabled={offset === 0 || busy != null} onClick={() => setOffset(value => Math.max(0, value - 30))}>Previous</button><span className="catalog-status">{offset + 1}–{offset + results.rows.length}</span><button className="secondary" disabled={results.next_offset == null || busy != null} onClick={() => setOffset(results.next_offset ?? 0)}>Next</button></div>}
  </section>;
}
