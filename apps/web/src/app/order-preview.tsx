"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ChartContract } from "./candles";
import type { MarketQuote } from "@/lib/market";
import { money } from "@/lib/paper";

type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
type Preview = { as_of: string; expires_at: string; quantity: number; premium: string; gross_stop_loss: string; gross_target_gain: string; entry_fee_allowance: string | null; stop_exit_fee_allowance: string | null; cash_required: string | null; available_cash: string | null; planned_stop_loss: string | null; remaining_risk_budget: string | null; checks: { code: string; label: string; status: "passed" | "blocked" }[] };

export default function OrderPreview({ instrument, quote, request }: { instrument: ChartContract; quote: MarketQuote | null; request: Request }) {
  const [lots, setLots] = useState("1");
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");
  const [target, setTarget] = useState("");
  const [result, setResult] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    setExpired(false);
    if (!result) return;
    const timer = setTimeout(() => setExpired(true), Math.max(0, Date.parse(result.expires_at)-Date.now()));
    return () => clearTimeout(timer);
  }, [result]);
  const change = (setter: (value: string) => void, value: string) => { setter(value); setResult(null); setError(null); };
  async function preview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!(Number(stop)>0 && Number(stop)<Number(entry) && Number(entry)<Number(target))) { setError("Set the stop below your limit price and the target above it."); return; }
    controller.current?.abort(); controller.current = new AbortController();
    setBusy(true); setError(null); setResult(null);
    try {
      const response = await request("/api/paper/orders/preview", "POST", controller.current.signal, { instrument_id: instrument.id, lots: Number(lots), entry, stop_loss: stop, target }) as Preview;
      setResult(response);
    } catch (cause) { if (!controller.current?.signal.aborted) setError(cause instanceof Error ? cause.message : "Preview unavailable."); }
    finally { setBusy(false); }
  }
  const amount = (value: string | null) => value == null ? "Unavailable" : money(value);
  return <div className="order-preview" aria-label="Paper order preview">
    <div className="depth-heading"><h3>Plan a paper order</h3><span>Buy {instrument.option_type === "CALL" ? "CE" : "PE"} · Limit</span></div>
    <p className="catalog-status">Intraday long option. Preview calculates costs and checks only; it does not place an order.</p>
    <form onSubmit={preview}>
      <fieldset disabled={busy}><legend className="sr-only">Order inputs</legend>
        <label className="order-lots">Lots<input aria-label="Number of lots" type="number" min="1" max="1000" step="1" required value={lots} onChange={event => change(setLots,event.target.value)} /><small>{Number.isInteger(Number(lots)) && Number(lots)>0 ? `${Number(lots)*instrument.lot_size} units · ${instrument.lot_size} per lot` : `Lot size ${instrument.lot_size}`}</small></label>
        <div className="order-price-fields">{[["Limit price",entry,setEntry],["Stop price",stop,setStop],["Target price",target,setTarget]].map(([label,value,setter]) => <label key={String(label)}>{String(label)}<input aria-label={String(label)} type="number" inputMode="decimal" step={instrument.tick_size ?? "0.01"} min={instrument.tick_size ?? "0.01"} required value={String(value)} onChange={event => change(setter as (value: string) => void,event.target.value)} /></label>)}</div>
        {quote?.ask != null && <button className="secondary use-ask" type="button" onClick={() => change(setEntry,quote.ask!)}>Use saved ask {money(quote.ask)}</button>}
        <button className="preview-action" type="submit">{busy ? "Calculating…" : "Preview costs & risk"}</button>
      </fieldset>
    </form>
    {error && <p className="notice error" role="alert">{error}</p>}
    {result && <div className="order-preview-result" aria-label="Order estimate">
      <p role="status">{expired ? "This preview has expired. Calculate again for current checks." : `Estimate for ${result.quantity} units · ${new Date(result.as_of).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", second: "2-digit" })} IST`}</p>
      <dl className="instrument-values">{[["Premium at limit",result.premium],["Entry fee allowance",result.entry_fee_allowance],["Cash required",result.cash_required],["Available cash",result.available_cash],["Gross stop loss",result.gross_stop_loss],["Gross target gain",result.gross_target_gain],["Stop exit fee allowance",result.stop_exit_fee_allowance],["Planned stop loss incl. costs",result.planned_stop_loss],["Remaining risk budget",result.remaining_risk_budget]].map(([label,value]) => <div key={label!}><dt>{label}</dt><dd>{amount(value)}</dd></div>)}</dl>
      <p className="catalog-status">Fee allowances use reviewed schedules. Planned stop loss includes modeled slippage and costs when available; a stop is not a guaranteed fill price.</p>
      <h4>Planning checks</h4><ul className="order-checks">{result.checks.filter(check => check.code !== "MANUAL_SUBMISSION").map(check => <li key={check.code}><span>{check.label}</span><strong>{check.status === "passed" ? "Met" : "Not met"}</strong></li>)}</ul>
      <p className="depth-notice">No order placed. This preview does not reserve funds or enable trading.</p>
    </div>}
  </div>;
}
