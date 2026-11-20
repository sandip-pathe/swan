"use client";

import type { ChartContract } from "./candles";
import type { MarketQuote, ReferenceContext } from "@/lib/market";
import Icon from "./icons";
import UnderlyingContext from "./underlying-context";

export type ChainRow = { instrument: ChartContract; quote: MarketQuote };
export type Chain = { reference?: ReferenceContext; rows: ChainRow[]; next_offset: number | null; as_of: string; expiry?: string | null; expiries?: string[]; page_size?: number; truncated?: boolean };
type Props = { sort: "latest" | "strike"; onSort: (value: "latest" | "strike") => void; chain: Chain | null; error: string | null; underlying: string; expiry: string; busy: boolean; stale: boolean; offset: number; now: number; maxAge: number; onMarket: (value: string) => void; onExpiry: (value: string) => void; onRefresh: () => void; onPage: (value: number) => void; onOpen: (item: ChartContract) => void };

function Side({ rows, name, now, maxAge, onOpen }: { rows: ChainRow[]; name: "CE" | "PE"; now: number; maxAge: number; onOpen: Props["onOpen"] }) {
  if (rows.length !== 1) return <div className="chain-side chain-unavailable">{rows.length ? "Multiple listings" : "No saved quote"}</div>;
  const { instrument, quote } = rows[0];
  const recent = now - Date.parse(quote.timestamp) >= 0 && now - Date.parse(quote.timestamp) <= maxAge * 1000;
  const value = (input?: string | null) => input == null ? "—" : Number(input).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return <button className="chain-side" onClick={() => onOpen(instrument)} aria-label={`Open chart for ${instrument.underlying} ${instrument.strike} ${name}`}>
    <strong>{value(quote.last_price)}</strong><span className="chain-bid-ask"><span><small>Bid</small>{value(quote.bid)}</span><span><small>Ask</small>{value(quote.ask)}</span></span><span className="chain-extra">OI {quote.oi?.toLocaleString("en-IN") ?? "—"}</span><span className="chain-extra">Vol {quote.volume?.toLocaleString("en-IN") ?? "—"}</span><small className="chain-time">{recent ? "Recent" : "Last quote"} · {new Date(quote.timestamp).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</small>
  </button>;
}

export default function OptionChain(props: Props) {
  const { chain, underlying, now, maxAge, onOpen } = props;
  const groups = new Map<string, { strike: string; expiry: string; calls: ChainRow[]; puts: ChainRow[] }>();
  for (const row of chain?.rows ?? []) {
    const { instrument } = row;
    const key = `${instrument.expiry}:${Number(instrument.strike)}`;
    if (!groups.has(key)) groups.set(key, { strike: instrument.strike, expiry: instrument.expiry, calls: [], puts: [] });
    groups.get(key)![instrument.option_type === "CALL" ? "calls" : "puts"].push(row);
  }
  const newest = (group: { calls: ChainRow[]; puts: ChainRow[] }) => Math.max(0, ...[...group.calls, ...group.puts].map(row => Date.parse(row.quote.timestamp) || 0));
  const sorted = [...groups.values()].sort((a, b) => a.expiry.localeCompare(b.expiry) || (props.sort === "latest" ? newest(b) - newest(a) : 0) || Number(a.strike) - Number(b.strike));
  return <section className="panel paired-chain" aria-label="Option chain">
    <div className="panelhead"><div><h2>Option chain</h2><p>Calls &amp; puts · prices in INR</p></div><button className="secondary" disabled={props.busy || props.stale} onClick={props.onRefresh}><Icon name="refresh" />{props.busy ? "Refreshing..." : "Refresh prices"}</button></div>
    <div className="chain-filters"><label>Market<select value={underlying} onChange={event => props.onMarket(event.target.value)}><option>NIFTY</option><option>SENSEX</option></select></label><label>Expiry<select value={props.expiry || chain?.expiry || ""} onChange={event => props.onExpiry(event.target.value)}><option value="">Nearest saved expiry</option>{(chain?.expiries ?? []).map(value => <option key={value}>{value}</option>)}</select></label></div>
    <UnderlyingContext underlying={underlying} reference={chain?.reference} maxAge={maxAge} error={!!props.error} />
    <label className="chain-sort">Order<select aria-label="Option chain order" value={props.sort} onChange={event => props.onSort(event.target.value as "latest" | "strike")}><option value="latest">Latest quotes first</option><option value="strike">Strike: low to high</option></select></label>
    <p className="catalog-status">Saved quotes only · exchange times in IST. Tap a call or put for its chart and details.</p>
    {props.error ? <p className="notice error" role="alert">{props.error}</p> : chain == null ? <p role="status" className="empty-state">Loading option chain…</p> : !sorted.length ? <p className="empty-state">No saved quotes for this selection. Use Refresh prices for the nearest listed expiry, or find another contract in Search.</p> : <>
      <div className="paired-chain-head"><span>CALLS · CE</span><span>STRIKE</span><span>PUTS · PE</span></div>
      {sorted.map(group => <div className="paired-strike" key={`${group.expiry}:${group.strike}`}><Side rows={group.calls} name="CE" now={now} maxAge={maxAge} onOpen={onOpen} /><div className="strike-label"><strong>{Number(group.strike).toLocaleString("en-IN")}</strong>{chain.reference?.atm_strike != null && Number(chain.reference.atm_strike) === Number(group.strike) && <small className="atm-marker">ATM at saved price</small>}{!chain.expiry && <small>{group.expiry}</small>}</div><Side rows={group.puts} name="PE" now={now} maxAge={maxAge} onOpen={onOpen} /></div>)}
      {chain.truncated && <p className="catalog-status">Some duplicate listing observations exceed this view’s limit. Uncertain sides are unavailable.</p>}
    </>}
    <div className="actions"><button className="secondary" disabled={props.offset === 0} onClick={() => props.onPage(Math.max(0, props.offset - (chain?.page_size ?? 50)))}>Previous</button><button className="secondary" disabled={chain?.next_offset == null} onClick={() => props.onPage(chain?.next_offset ?? 0)}>Next</button></div>
  </section>;
}
