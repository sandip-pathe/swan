"use client";

import { useEffect, useState } from "react";
import type { MarketQuote, QuoteStatistics, ReferenceContext } from "@/lib/market";
import type { ChartContract } from "./candles";
import Icon from "./icons";
import type { WatchState } from "./watchlist";

type Contract = ChartContract & { tick_size: string };
export type SelectedContract = { reference?: ReferenceContext; instrument: ChartContract; quote: MarketQuote | null; statistics?: QuoteStatistics };
type Results = { rows: Contract[]; expiries: string[]; next_offset: number | null; catalog_at: string | null; stale: boolean };
type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;

export default function InstrumentSearch({ ownerKey, request, underlying, onMarket, onOpen, watchlist }: { ownerKey: string; watchlist: WatchState; request: Request; underlying: string; onMarket: (value: string) => void; onOpen: (result: SelectedContract) => void }) {
  const filterKey = `swan.market.filters.v1.${ownerKey}.${underlying}`;
  const [savedFilters] = useState<Record<string, unknown>>(() => { try { const value = JSON.parse(sessionStorage.getItem(filterKey) ?? "{}"); return value && typeof value === "object" && !Array.isArray(value) ? value : {}; } catch { return {}; } });
  const [query, setQuery] = useState(typeof savedFilters.query === "string" ? savedFilters.query.slice(0, 60) : "");
  const [expiry, setExpiry] = useState(typeof savedFilters.expiry === "string" && /^\d{4}-\d{2}-\d{2}$/.test(savedFilters.expiry) ? savedFilters.expiry : "");
  const [side, setSide] = useState(savedFilters.side === "CALL" || savedFilters.side === "PUT" ? savedFilters.side : "");
  const [offset, setOffset] = useState(0);
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => { try { sessionStorage.setItem(filterKey, JSON.stringify({ query, expiry, side })); } catch { /* Search remains usable. */ } }, [filterKey, query, expiry, side]);


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

  const activeFilters = Number(Boolean(side)) + Number(Boolean(expiry));
  return <section className="panel instrument-search" aria-label="Contract search">
    <div className="panelhead"><div><h2>Find an option</h2><p>Pick a market, then find a strike you want to explore.</p></div><button className="secondary" disabled={busy != null} onClick={refreshCatalog}><Icon name="refresh" />{busy === "refresh" ? "Updating…" : "Update contract list"}</button></div>
    <div className="contract-filters">
      <label className="contract-query">Search<input type="search" value={query} maxLength={60} placeholder="Try a strike, NIFTY or CE / PE" autoComplete="off" onChange={event => { setQuery(event.target.value); setOffset(0); }} /></label>
      <label>Market<select value={underlying} onChange={event => { onMarket(event.target.value); setExpiry(""); setOffset(0); }}><option>NIFTY</option><option>SENSEX</option></select></label>
    </div>
    <details className="trade-filters" open={activeFilters > 0}><summary>Filters{activeFilters ? ` · ${activeFilters} selected` : ""}</summary><div className="contract-filters"><label>Call or put<select value={side} onChange={event => { setSide(event.target.value); setOffset(0); }}><option value="">Calls and puts</option><option value="CALL">Call · CE</option><option value="PUT">Put · PE</option></select></label><label className="contract-expiry">Expiry<select value={expiry} onChange={event => { setExpiry(event.target.value); setOffset(0); }}><option value="">Any listed expiry</option>{(results?.expiries ?? (expiry ? [expiry] : [])).map(value => <option key={value}>{value}</option>)}</select></label>{activeFilters > 0 && <button type="button" className="text-button" onClick={() => { setSide(""); setExpiry(""); setOffset(0); }}>Clear filters</button>}</div></details>
    {error && <p className="notice error" role="alert">{error}<button className="secondary" onClick={() => setRefresh(value => value + 1)}>Retry search</button></p>}
    {results?.catalog_at && <p className="catalog-status">Contract list checked {new Date(results.catalog_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} IST{results.stale ? " | Update it before opening a contract." : " | Prices appear after you open a chart."}</p>}
    {results == null && !error ? <p className="empty-state" role="status">Finding options...</p> : results?.catalog_at == null && !error ? <div className="market-empty"><Icon name="markets" /><strong>Options list needs an update</strong><p>Update the list to see contracts. Prices are loaded separately.</p></div> : results && !results.rows.length ? <div className="market-empty"><strong>No options found</strong><p>Try another strike or clear a filter.</p></div> : <div className="contract-results">{results?.rows.map(item => {
      const saved = watchlist.data?.rows.some(row => row.instrument.id === item.id) ?? false;
      const strike = Number(item.strike).toLocaleString("en-IN", { maximumFractionDigits: 2 });
      const name = `${item.underlying} ${strike} ${item.option_type === "CALL" ? "CE" : "PE"}`;
      return <article className="contract-result" key={item.id}><button className="contract-result-open" disabled={busy != null || results.stale} onClick={() => open(item)} aria-label={`Open chart for ${name} ${item.expiry}`}><span><strong>{name}</strong><small>{item.expiry} | {item.option_type === "CALL" ? "Call" : "Put"}</small></span><span className="result-action">{busy === item.id ? "Opening..." : "View chart"}<Icon name="arrow" /></span></button><button className="secondary watch-star" disabled={watchlist.data == null || !!watchlist.error || watchlist.busy != null || busy != null || results.stale && !saved} aria-pressed={saved} aria-label={`${saved ? "Remove" : "Save"} ${name} ${saved ? "from" : "to"} watchlist`} onClick={() => void watchlist.change(item.id, !saved)}><Icon name="star" /></button></article>;
    })}</div>}
    {watchlist.error && <p className="notice error" role="alert">{watchlist.error}<button className="secondary" onClick={() => void watchlist.retry()}>Retry watchlist</button></p>}
    {results && (offset > 0 || results.next_offset != null) && <div className="actions"><button className="secondary" disabled={offset === 0 || busy != null} onClick={() => setOffset(value => Math.max(0, value - 30))}>Previous</button><span className="catalog-status">{offset + 1}–{offset + results.rows.length}</span><button className="secondary" disabled={results.next_offset == null || busy != null} onClick={() => setOffset(results.next_offset ?? 0)}>Next</button></div>}
  </section>;
}
