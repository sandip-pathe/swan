"use client";

import { useState } from "react";

export type AdvisoryIdea = {
  id: string; kind: "idea"; revision: number; horizon: string; direction: string; state: string;
  title: string; summary: string; limitation: string; as_of: string; expires_at: string; published_at: string;
  trigger: string; invalidation: string; target_level: string; reasons: string[]; evidence_ids: string[];
  contract: { id: string; strike: string; option_type: string; expiry: string; lot_size: number } | null;
  economics: { premium_required: string; entry_ask: string; exit_bid: string; spread: string;
    estimated_net_loss: string; estimated_net_gain: string; loss_reference: string;
    estimated_round_trip_cost: string; quote_at: string; premium_invalidation: string;
    premium_target_scenario: string; assumptions: string } | null;
  research: { status: string; at: string; result: { thesis: string; counterargument: string;
    next_observation: string; abstain: boolean } | null } | null;
};
type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
const stamp = (value: string) => new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST";
const money = (value: string) => "INR " + Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const reasons: Record<string, string> = {
  SET_POSITION_BUDGET: "Set your position budget to check affordability.",
  ONE_LOT_EXCEEDS_POSITION_BUDGET: "One lot exceeds your position budget.",
  DOWNSIDE_EXCEEDS_FIVE_PERCENT_REFERENCE: "Estimated downside exceeds your 5% position reference.",
  PREMIUM_NOISE_WINDOW_WARMING_UP: "Waiting for enough observed premium behaviour.",
  DEPTH_QUANTITY_UNITS_UNVERIFIED: "Depth quantity units still need source verification.",
  ENTRY_CONDITION_NOT_CONFIRMED: "The entry condition has not been confirmed.",
  REQUIRED_BAR_WINDOW_INCOMPLETE: "A required candle window is incomplete.",
  RESEARCH_PENDING: "Research has not finished.",
};

export default function IdeaCard({ idea, clock, starred, onStar, onDiscuss, request, onUpdated }: {
  idea: AdvisoryIdea; clock: number; starred: boolean; onStar: () => void; onDiscuss: () => void;
  request: Request; onUpdated: () => void;
}) {
  const [reporting, setReporting] = useState(false);
  const [premium, setPremium] = useState("");
  const [quantity, setQuantity] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const expired = clock >= Date.parse(idea.expires_at);
  const pricesOld = !idea.economics || clock - Date.parse(idea.economics.quote_at) > 5000;
  const state = expired ? "expired" : idea.state === "eligible" && pricesOld ? "suspended" : idea.state;
  const research = idea.research?.result;
  async function record() {
    if (!idea.contract || !premium || !quantity) return;
    setBusy(true); setMessage("");
    try {
      await request(`/api/bot/ideas/${idea.id}/entry`, "POST", undefined, {
        expected_revision: idea.revision, premium, quantity: Number(quantity), entered_at: new Date().toISOString(),
      });
      setMessage("Your reported entry was saved and starred. No order was placed or broker fill verified.");
      setReporting(false); onUpdated();
    } catch { setMessage("Entry was not saved. Refresh the idea and check whole-lot quantity before retrying."); }
    finally { setBusy(false); }
  }
  return <article className={`bot-insight idea-card idea-${state}`}>
    <div className="bot-row"><p className="eyebrow">{idea.horizon} / {idea.direction} / EXPERIMENTAL</p>
      <span className="idea-state">{state === "eligible" ? "Conditions met" : state.replaceAll("_", " ")}</span></div>
    <h3>{idea.title}</h3>
    <p>{research && !research.abstain ? research.thesis : idea.summary}</p>
    <dl className="idea-conditions"><div><dt>Entry condition</dt><dd>{idea.trigger}</dd></div>
      <div><dt>What invalidates it</dt><dd>{idea.invalidation}</dd></div>
      <div><dt>Underlying target scenario</dt><dd>{idea.target_level} <small>not an option-price prediction</small></dd></div></dl>
    {idea.contract && <p><strong>{idea.contract.strike} {idea.contract.option_type}</strong> / expiry {idea.contract.expiry} / {idea.contract.lot_size} units per lot</p>}
    {idea.economics && <><dl className="idea-economics">
      <div><dt>One-lot premium</dt><dd>{money(idea.economics.premium_required)}</dd></div>
      <div><dt>Estimated downside scenario</dt><dd>{money(idea.economics.estimated_net_loss)}</dd></div>
      <div><dt>Estimated upside scenario</dt><dd>{money(idea.economics.estimated_net_gain)}</dd></div>
      <div><dt>Your 5% reference</dt><dd>{money(idea.economics.loss_reference)}</dd></div></dl>
      <p className="note">Ask / bid {idea.economics.entry_ask} / {idea.economics.exit_bid}; {stamp(idea.economics.quote_at)}. {pricesOld ? "Historical pricing; refresh before a decision." : "Source pricing received recently."}</p></>}
    {!!idea.reasons.length && <p className="idea-waiting">{reasons[idea.reasons[0]] ?? idea.reasons[0].replaceAll("_", " ").toLowerCase()}</p>}
    {research && <details><summary>Counterargument and next observation</summary><p>{research.counterargument}</p><p>{research.next_observation}</p></details>}
    <details><summary>Risk &amp; evidence</summary>{idea.reasons.length > 1 && <ul className="idea-reasons">{idea.reasons.slice(1).map(reason => <li key={reason}>{reasons[reason] ?? reason.replaceAll("_", " ").toLowerCase()}</li>)}</ul>}<p>Revision {idea.revision}; published {stamp(idea.published_at)}. Expires {stamp(idea.expires_at)}.</p>
      <p>{idea.evidence_ids.length} retained evidence references. {idea.limitation}</p>
      {idea.economics && <p>{idea.economics.assumptions} Estimated round-trip costs/slippage: {money(idea.economics.estimated_round_trip_cost)}. Premium invalidation/target scenarios: {idea.economics.premium_invalidation} / {idea.economics.premium_target_scenario}.</p>}
      <p>Scenario results are hypothetical. This assistant does not execute exits or guarantee the loss reference.</p></details>
    <div className="idea-actions"><button onClick={onDiscuss}>Discuss this idea</button>
      <button className="text-button" aria-pressed={starred} onClick={onStar}>{starred ? "Saved" : "Save"}</button>
      {idea.contract && <button className="text-button" onClick={() => setReporting(value => !value)}>Record an entry I placed</button>}</div>
    {reporting && <form className="idea-report" onSubmit={event => { event.preventDefault(); void record(); }}>
      <p>This records your statement only. It does not send an order.</p>
      <label>Premium paid per unit<input required inputMode="decimal" type="number" step="0.01" min="0.01" value={premium} onChange={event => setPremium(event.target.value)} /></label>
      <label>Quantity in units<input required type="number" min={idea.contract?.lot_size ?? 1} step={idea.contract?.lot_size ?? 1} value={quantity} onChange={event => setQuantity(event.target.value)} /></label>
      <button disabled={busy}>{busy ? "Saving..." : "Save my reported entry"}</button></form>}
    {message && <p role="status">{message}</p>}
  </article>;
}
