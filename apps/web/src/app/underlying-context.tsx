"use client";

import type { ReferenceContext } from "@/lib/market";
const points = (value: string) => Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function UnderlyingContext({ underlying, reference, maxAge = 10, error = false }: { underlying: string; reference?: ReferenceContext; maxAge?: number; error?: boolean }) {
  const quote = reference?.quote?.underlying === underlying ? reference.quote : null;
  const age = quote ? Date.now() - Date.parse(quote.timestamp) : Infinity;
  const recent = !error && age >= 0 && age <= maxAge * 1000;
  return <div className="underlying-context" aria-label={`${underlying} underlying context`}>
    <div className="underlying-price"><span>{underlying} index</span><strong>{quote ? points(quote.last_price) : "Price unavailable"}</strong>{quote && reference?.change != null && reference.change_pct != null && <span className={Number(reference.change) >= 0 ? "positive" : "negative"}>{Number(reference.change) > 0 ? "+" : ""}{points(reference.change)} ({Number(reference.change_pct) > 0 ? "+" : ""}{Number(reference.change_pct).toFixed(2)}%) <small>points vs previous close</small></span>}</div>
    <p>{quote ? `${recent ? "Recent reference" : "Saved reference"} · ${new Date(quote.timestamp).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" })} IST` : "Refresh chain prices to retrieve the underlying reference."}</p>
    {quote && reference?.atm_strike != null ? <p className="underlying-atm"><strong>{recent ? "ATM" : "Nearest strike at saved price"} {Number(reference.atm_strike).toLocaleString("en-IN")}</strong><span>Nearest listed strike for this expiry. Equal distances use the lower strike.</span></p> : quote && <p>ATM unavailable.{reference?.atm_status === "catalog_refresh_required" ? " Refresh contracts in Search." : reference?.atm_status === "reference_from_another_session" ? " The index reference is from another session." : " No current listed strike for this expiry."}</p>}
  </div>;
}
