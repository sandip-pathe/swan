"use client";

import type { ChartContract } from "./candles";
import type { MarketQuote, QuoteStatistics } from "@/lib/market";
import { money } from "@/lib/paper";

const observed = (value: string) => new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
const price = (value?: string | null) => value == null ? "Unavailable" : money(value);

export default function InstrumentDetails({ instrument, quote, statistics, error, maxAge = 10 }: { instrument: ChartContract; quote: MarketQuote | null; statistics?: QuoteStatistics; error?: string | null; maxAge?: number }) {
  const stats = statistics;
  const age = quote ? Date.now() - Date.parse(quote.timestamp) : Infinity;
  const recent = !error && age >= 0 && age <= maxAge * 1000;
  const prices = [["Last traded", price(quote?.last_price)], ["Previous close", price(quote?.previous_close)], ["Open", price(quote?.session_open)], ["High", price(quote?.session_high)], ["Low", price(quote?.session_low)], ["Bid", price(quote?.bid)], ["Ask", price(quote?.ask)], ["Spread", price(stats?.spread)], ["Spread (bps)", stats?.spread_bps == null ? "Unavailable" : Number(stats.spread_bps).toFixed(2)], ["Volume", quote?.volume?.toLocaleString("en-IN") ?? "Unavailable"], ["Open interest", quote?.oi?.toLocaleString("en-IN") ?? "Unavailable"], ["IV", quote?.iv != null && quote.iv_unit === "percent" ? `${Number(quote.iv).toFixed(2)}%` : "Unavailable"]];
  return <div className="instrument-detail" aria-label="Instrument details">
    <p className="instrument-observed">{quote ? `${recent ? "Recent quote" : "Last saved quote"} · ${observed(quote.timestamp)} IST` : "No quote saved for this contract. Candle history loads separately."}</p>
    {stats?.change != null && stats.change_pct != null && <p className={`instrument-change ${Number(stats.change) >= 0 ? "positive" : "negative"}`}>{Number(stats.change) > 0 ? "+" : ""}{money(stats.change)} ({Number(stats.change_pct) > 0 ? "+" : ""}{Number(stats.change_pct).toFixed(2)}%) <span>vs previous close</span></p>}
    <dl className="instrument-values">{prices.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <h3>Contract</h3><dl className="instrument-values">{[["Exchange", instrument.exchange ?? "Unavailable"], ["Expiry", instrument.expiry], ["Lot size", String(instrument.lot_size)], ["Tick size", price(instrument.tick_size)]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    {quote?.metrics_timestamp && <p className="catalog-status">IV observed {observed(quote.metrics_timestamp)} IST. IV may have a different observation time from prices.</p>}
    <details><summary>About these values</summary><p className="catalog-status">Prices and session OHLC are saved broker observations. A closed market or old quote does not represent a current executable price. Change compares the last traded price with the broker’s previous close. Spread is ask minus bid; basis points divide that spread by the bid/ask midpoint and multiply by 10,000. Missing or crossed prices leave spread unavailable. Depth quantities remain unavailable until their units are verified.</p>{quote?.received_at && <p className="catalog-status">Received {observed(quote.received_at)} IST. {quote.source?.startsWith("angelone") ? "Source: Angel One." : "Source: saved market observation."}</p>}</details>
  </div>;
}
