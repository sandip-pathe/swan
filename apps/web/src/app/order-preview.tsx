"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ChartContract } from "./candles";
import type { MarketQuote } from "@/lib/market";
import { money } from "@/lib/paper";
import ManualPlacement from "./manual-placement";

type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
type Preview = { available_depth_lots: number | null; available_depth_quantity: number | null; account_revision: number; as_of: string; expires_at: string; quantity: number; premium: string; gross_stop_loss: string; gross_target_gain: string; entry_fee_allowance: string | null; stop_exit_fee_allowance: string | null; cash_required: string | null; available_cash: string | null; planned_stop_loss: string | null; remaining_risk_budget: string | null; checks: { code: string; label: string; status: "passed" | "blocked" }[] };

type SavedPlan = { id: string; created_at: string; inputs: { instrument_id: string; lots: number; entry: string; stop_loss: string; target: string }; preview: Preview; status: string; order_id?: string | null };
type Plans = { rows: SavedPlan[]; next_offset: number | null };

export default function OrderPreview({ instrument, quote, request, visible }: { instrument: ChartContract; quote: MarketQuote | null; request: Request; visible: boolean }) {
  const [submissionLocked, setSubmissionLocked] = useState(false);
  const [placementPlan, setPlacementPlan] = useState<SavedPlan | null>(null);
  const [lots, setLots] = useState("1");
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");
  const [target, setTarget] = useState("");
  const [result, setResult] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const [saveKey, setSaveKey] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [plans, setPlans] = useState<Plans | null>(null);
  const [plansError, setPlansError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [plansRefresh, setPlansRefresh] = useState(0);
  const [planBusy, setPlanBusy] = useState(false);
  useEffect(() => {
    if (!visible) return;
    let active = true;
    const abort = new AbortController();
    setPlans(null);
    void request(`/api/paper/plans?${new URLSearchParams({ instrument_id: instrument.id, offset: String(offset) })}`, "GET", abort.signal).then(response => { if (active) { setPlans(response as Plans); setPlansError(null); } }).catch(cause => { if (active) setPlansError(cause instanceof Error ? cause.message : "Saved plans unavailable."); });
    return () => { active = false; abort.abort(); };
  }, [request, instrument.id, visible, offset, plansRefresh]);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    setExpired(false);
    if (!result) return;
    const timer = setTimeout(() => setExpired(true), Math.max(0, Date.parse(result.expires_at)-Date.now()));
    return () => clearTimeout(timer);
  }, [result]);
  const change = (setter: (value: string) => void, value: string) => { setter(value); setPlacementPlan(null); setResult(null); setError(null); setSaved(null); setSaveKey(null); setSaveMessage(null); };
  async function preview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || submissionLocked) return;
    if (!(Number(stop)>0 && Number(stop)<Number(entry) && Number(entry)<Number(target))) { setError("Set the stop below your limit price and the target above it."); return; }
    controller.current?.abort(); controller.current = new AbortController();
    setBusy(true); setPlacementPlan(null); setError(null); setResult(null); setSaved(null); setSaveMessage(null); setSaveKey(crypto.randomUUID());
    try {
      const response = await request("/api/paper/orders/preview", "POST", controller.current.signal, { instrument_id: instrument.id, lots: Number(lots), entry, stop_loss: stop, target }) as Preview;
      setResult(response);
    } catch (cause) { if (!controller.current?.signal.aborted) setError(cause instanceof Error ? cause.message : "Preview unavailable."); }
    finally { setBusy(false); }
  }
  async function savePlan() {
    if (busy || submissionLocked || !result || !saveKey || saved) return;
    if (Date.now() >= Date.parse(result.expires_at)) { setExpired(true); return; }
    setBusy(true); setError(null);
    controller.current?.abort(); controller.current = new AbortController();
    try {
      const plan = await request("/api/paper/plans", "POST", controller.current.signal, { instrument_id: instrument.id, lots: Number(lots), entry, stop_loss: stop, target, idempotency_key: saveKey, expected_account_revision: result.account_revision }) as SavedPlan;
      setPlacementPlan(plan); setSaved(plan.id); setResult(plan.preview); setSaveMessage("Paper plan saved to your account. No order placed."); setOffset(0); setPlansRefresh(value => value + 1);
    } catch (cause) { if (!controller.current?.signal.aborted) setError(cause instanceof Error ? cause.message : "Plan could not be saved. Retry without editing to avoid duplicate requests."); }
    finally { setBusy(false); }
  }
  async function archivePlan(plan: SavedPlan) {
    if (planBusy || busy || submissionLocked) return;
    setPlanBusy(true); setPlansError(null);
    try { await request(`/api/paper/plans/${encodeURIComponent(plan.id)}/archive`, "POST"); setOffset(0); setPlansRefresh(value => value + 1); }
    catch (cause) { setPlansError(cause instanceof Error ? cause.message : "Plan could not be archived."); }
    finally { setPlanBusy(false); }
  }
  function restorePlan(plan: SavedPlan) {
    if (submissionLocked) return;
    setPlacementPlan(null);
    setLots(String(plan.inputs.lots)); setEntry(plan.inputs.entry); setStop(plan.inputs.stop_loss); setTarget(plan.inputs.target);
    setResult(null); setSaved(null); setSaveKey(null); setError(null); setSaveMessage("Saved inputs loaded. Preview again for current costs and checks.");
  }
  const amount = (value: string | null) => value == null ? "Unavailable" : money(value);
  return <div className="order-preview" aria-label="Paper order preview">
    <div className="depth-heading"><h3>Manual paper order</h3><span>Buy {instrument.option_type === "CALL" ? "CE" : "PE"} · Limit</span></div>
    <p className="catalog-status">Intraday long option. Preview calculates costs and checks only; it does not place an order.</p>
    <form onSubmit={preview}>
      <fieldset disabled={busy || submissionLocked}><legend className="sr-only">Order inputs</legend>
        <label className="order-lots">Lots<input aria-label="Number of lots" type="number" min="1" max="1000" step="1" required value={lots} onChange={event => change(setLots,event.target.value)} /><small>{Number.isInteger(Number(lots)) && Number(lots)>0 ? `${Number(lots)*instrument.lot_size} units · ${instrument.lot_size} per lot` : `Lot size ${instrument.lot_size}`}</small></label>
        <div className="order-price-fields">{[["Limit price",entry,setEntry],["Stop price",stop,setStop],["Target price",target,setTarget]].map(([label,value,setter]) => <label key={String(label)}>{String(label)}<input aria-label={String(label)} type="number" inputMode="decimal" step={instrument.tick_size ?? "0.01"} min={instrument.tick_size ?? "0.01"} required value={String(value)} onChange={event => change(setter as (value: string) => void,event.target.value)} /></label>)}</div>
        {quote?.ask != null && <button className="secondary use-ask" type="button" onClick={() => change(setEntry,quote.ask!)}>Use saved ask {money(quote.ask)}</button>}
        <button className="preview-action" type="submit">{busy ? "Calculating…" : "Preview costs & risk"}</button>
      </fieldset>
    </form>
    {saveMessage && <p className="catalog-status" role="status">{saveMessage}</p>}
    {error && <p className="notice error" role="alert">{error}</p>}
    {result && <div className="order-preview-result" aria-label="Order estimate">
      <p role="status">{expired ? "This preview has expired. Calculate again for current checks." : `Estimate for ${result.quantity} units · ${new Date(result.as_of).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", second: "2-digit" })} IST`}</p>
      <dl className="instrument-values">{[["Premium at limit",result.premium],["Entry fee allowance",result.entry_fee_allowance],["Cash required",result.cash_required],["Available cash",result.available_cash],["Gross stop loss",result.gross_stop_loss],["Gross target gain",result.gross_target_gain],["Stop exit fee allowance",result.stop_exit_fee_allowance],["Planned stop loss incl. costs",result.planned_stop_loss],["Remaining risk budget",result.remaining_risk_budget]].map(([label,value]) => <div key={label!}><dt>{label}</dt><dd>{amount(value)}</dd></div>)}<div><dt>Usable depth at limit</dt><dd>{result.available_depth_lots == null ? "Unavailable" : `${result.available_depth_lots} ${result.available_depth_lots === 1 ? "lot" : "lots"}`}</dd></div></dl>
      <p className="catalog-status">Fee allowances use reviewed schedules. Planned stop loss includes modeled slippage and costs when available; a stop is not a guaranteed fill price.</p>
      <p className="catalog-status">{result.available_depth_lots == null ? "Usable depth could not be verified. Calculate a new preview after prices update." : result.available_depth_lots === 0 ? "No whole lots are currently usable at this limit under the fill policy. Review your limit or wait for depth to change." : "Usable depth accounts for participation limits and prior paper fills. It can change before an order fills."}</p>
      <h4>Planning checks</h4><ul className="order-checks">{result.checks.filter(check => check.code !== "MANUAL_SUBMISSION").map(check => <li key={check.code}><span>{check.label}</span><strong>{check.status === "passed" ? "Met" : "Not met"}</strong></li>)}</ul>
      <button className="secondary save-paper-plan" disabled={busy || submissionLocked || expired || !!saved} onClick={() => void savePlan()}>{saved ? "Plan saved" : busy ? "Saving..." : "Save paper plan"}</button>
      <p className="depth-notice">A preview does not place an order, reserve funds or enable trading.</p>
    </div>}
    <ManualPlacement instrument={instrument} request={request} visible={visible} plan={placementPlan} onLock={setSubmissionLocked} onOrderRecorded={()=>{setResult(null);setPlacementPlan(null);setSaved(null);setSaveKey(null);setSaveMessage(null);setPlansRefresh(value=>value+1);}} onSessionChange={()=>{setResult(null);setPlacementPlan(null);setSaved(null);setSaveKey(null);setSaveMessage(null);}} />
    <details className="saved-paper-plans"><summary>Saved paper plans</summary>
      {plansError && <p role="alert" className="notice error">{plansError}<button className="secondary" onClick={() => setPlansRefresh(value => value + 1)}>Retry</button></p>}
      {!plans && !plansError ? <p className="catalog-status">Loading saved plans...</p> : plans?.rows.length === 0 ? <p className="catalog-status">No saved plans for this contract.</p> : plans?.rows.map(plan => <article key={plan.id}><strong>{plan.inputs.lots} lots at {money(plan.inputs.entry)}</strong><p>Stop {money(plan.inputs.stop_loss)} · Target {money(plan.inputs.target)}</p><small>Saved {new Date(plan.created_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} IST · {plan.order_id ? "Order recorded - track in Orders" : "No order placed"}</small><div className="actions"><button className="secondary" disabled={busy || planBusy || submissionLocked} onClick={() => restorePlan(plan)}>Load inputs</button><button className="secondary" disabled={busy || planBusy || submissionLocked} onClick={() => void archivePlan(plan)}>Archive</button></div></article>)}
      {(offset>0 || plans?.next_offset != null) && <div className="actions"><button className="secondary" disabled={offset===0 || busy || planBusy} onClick={() => setOffset(Math.max(0,offset-25))}>Previous</button><button className="secondary" disabled={plans?.next_offset==null || busy || planBusy} onClick={() => setOffset(plans?.next_offset ?? 0)}>Next</button></div>}
    </details>
  </div>;
}
