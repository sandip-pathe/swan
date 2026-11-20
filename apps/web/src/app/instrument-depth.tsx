"use client";

import type { MarketQuote, QuoteStatistics } from "@/lib/market";
import { money } from "@/lib/paper";

const observed = (value: string) => new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });

export default function InstrumentDepth({ quote, statistics, error, maxAge = 10 }: { quote: MarketQuote | null; statistics?: QuoteStatistics; error?: string | null; maxAge?: number }) {
  const retained = quote?.depth_kind === "best_five";
  const bids = retained ? (quote.bid_depth ?? []).slice(0, 5) : [];
  const asks = retained ? (quote.ask_depth ?? []).slice(0, 5) : [];
  const hasDepth = bids.length > 0 || asks.length > 0;
  const verified = !!quote?.quantity_unit_source?.trim() && (quote.quantity_unit === "units" || quote.quantity_unit === "lots");
  const unit = verified ? quote?.quantity_unit === "lots" ? "Lots" : "Units" : "Qty";
  const age = quote ? Date.now() - Date.parse(quote.timestamp) : Infinity;
  const recent = !error && age >= 0 && age <= maxAge * 1000;
  const crossed = quote?.bid != null && quote.ask != null && Number(quote.bid) > Number(quote.ask);
  const price = (value?: string | null) => value == null ? "Unavailable" : money(value);
  return <div className="instrument-depth" aria-label="Market depth">
    <div className="depth-heading"><h3>Market depth</h3><span>{hasDepth ? "Up to 5 levels" : "Best bid / ask"}</span></div>
    <p className="instrument-observed">{quote ? `${recent ? "Recent quote" : "Last saved quote"} · ${observed(quote.timestamp)} IST` : "No quote saved for this contract."}</p>
    {!recent && quote && <p className="depth-notice">These are saved prices. They may no longer be available in the market.</p>}
    {crossed && <p className="depth-notice" role="status">Bid exceeds ask. This quote does not show a usable market spread.</p>}
    {quote && (hasDepth || quote.bid != null || quote.ask != null) ? <>
      <table className="depth-book"><caption className="sr-only">Saved bid and ask prices. {verified ? `Quantities in ${unit.toLowerCase()}.` : "Quantities unavailable because units are unverified."}</caption><thead><tr><th scope="col">{unit}</th><th scope="col">Bid</th><th scope="col">Ask</th><th scope="col">{unit}</th></tr></thead><tbody>{Array.from({ length: hasDepth ? Math.max(bids.length, asks.length) : 1 }, (_, index) => <tr key={index}><td>{verified && bids[index] ? bids[index].quantity.toLocaleString("en-IN") : "—"}</td><td className="depth-bid">{price(hasDepth ? bids[index]?.price : quote.bid)}</td><td className="depth-ask">{price(hasDepth ? asks[index]?.price : quote.ask)}</td><td>{verified && asks[index] ? asks[index].quantity.toLocaleString("en-IN") : "—"}</td></tr>)}</tbody></table>
      <dl className="depth-spread"><dt>Spread</dt><dd>{price(crossed ? null : statistics?.spread)}</dd></dl>
      {!hasDepth && <p className="catalog-status">Only the best bid and ask were saved. Additional levels are unavailable.</p>}
    </> : <p className="empty-state">No depth prices saved yet. Refresh price to retrieve the broker's available quote.</p>}
    {!verified && <p className="depth-notice">Quantities are hidden until their units are verified. Prices are shown where available.</p>}
    <details><summary>About market depth</summary><p className="catalog-status">This view shows saved broker observations, not the complete exchange order book. Missing levels remain unavailable. Quantities are shown only when the quote includes verified units; lots and units are never converted here.</p>{quote?.received_at && <p className="catalog-status">Received {observed(quote.received_at)} IST. Source: {quote.source?.startsWith("angelone") ? "Angel One" : "saved market observation"}.</p>}</details>
  </div>;
}
