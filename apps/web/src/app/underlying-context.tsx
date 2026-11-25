"use client";

import type { ReferenceContext } from "@/lib/market";
const points = (value: string) => Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function UnderlyingContext({ underlying, reference, maxAge = 10, error = false }: { underlying: string; reference?: ReferenceContext; maxAge?: number; error?: boolean }) {
  const quote = reference?.quote?.underlying === underlying ? reference.quote : null;
  const age = quote ? Date.now() - Date.parse(quote.timestamp) : Infinity;
  const recent = !error && age >= 0 && age <= maxAge * 1000;
  return <div className="underlying-context" aria-label={`${underlying} underlying context`}>
    <div className="underlying-price"><span>{underlying}</span><strong>{quote ? points(quote.last_price) : "Index price not available"}</strong>{quote && reference?.change != null && reference.change_pct != null && <span className={Number(reference.change) >= 0 ? "positive" : "negative"}>{Number(reference.change) > 0 ? "+" : ""}{points(reference.change)} ({Number(reference.change_pct) > 0 ? "+" : ""}{Number(reference.change_pct).toFixed(2)}%) <small>vs previous close</small></span>}</div>
    <p>{quote ? `${recent ? "Recent price" : "Saved price"} · ${new Date(quote.timestamp).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" })} IST` : "This index price has not been saved yet."}</p>
    {quote && reference?.atm_strike != null ? <p className="underlying-atm"><strong>{recent ? "Nearest strike" : "Nearest strike at saved price"} {Number(reference.atm_strike).toLocaleString("en-IN")}</strong><span>The listed strike closest to this index price.</span></p> : quote && <p>Nearest strike unavailable.{reference?.atm_status === "catalog_refresh_required" ? " Update the options list in Find." : reference?.atm_status === "reference_from_another_session" ? " The index price is from another session." : " No matching strike for this expiry."}</p>}
  </div>;
}
