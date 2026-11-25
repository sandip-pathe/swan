"use client";

import { useCallback, useEffect, useState } from "react";
import type { User } from "firebase/auth";
import Chat from "./chat";
import Brand from "./brand";

type Quote = { underlying: string; status: string; age_seconds: number | null;
  quote: { last_price: string; timestamp: string; source: string } | null };
type Analysis = { status: string; reason?: string; as_of?: string; last_close?: string;
  sma20?: string; range_high?: string; range_low?: string; range_state?: string; trend?: string };
type Insight = { id: string; as_of: string; title: string; summary: string; limitation: string;
  facts: Analysis & { evidence: string[]; source: string; rule: string } };
type Snapshot = { as_of: string; quotes: Quote[]; analysis: Analysis; insights: Insight[];
  worker: { status: string; detail?: string; heartbeat_current: boolean; problems?: string[] };
  calendar: { state: string; last_covered_day?: string } };
type Evidence = { source: string; response_sha256: string; received_at: string;
  bars: { opens_at: string; close: string; evidence_id: string }[] };
const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const stamp = (value?: string) => value ? new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "short" }) + " IST" : "Not received";
const words = (value?: string) => (value ?? "unavailable").replaceAll("_", " ");

export default function BotHome({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const [screen, setScreen] = useState<"chat" | "insights">("chat");
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [clock, setClock] = useState(Date.now());
  const [evidence, setEvidence] = useState<Record<string, Evidence>>({});
  const [evidenceBusy, setEvidenceBusy] = useState("");
  const ownerKey = `bot.${user.uid}`;
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 15000); return () => clearInterval(timer); }, []);
  const request = useCallback(async (path: string, method = "GET", signal?: AbortSignal, body?: unknown) => {
    if (!navigator.onLine) throw new Error("Reconnect to continue.");
    if (method === "POST") {
      const health = await fetch(base + "/health", { cache: "no-store", signal: AbortSignal.timeout(10000) });
      const identity = await health.json();
      if (!health.ok || identity.service !== "swan-bot") throw new Error("This frontend is waiting for the bot API cutover. Your question is preserved.");
    }
    const token = await user.getIdToken();
    const response = await fetch(base + path, { method, cache: "no-store",
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(35000)]) : AbortSignal.timeout(35000),
      headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}) });
    if (!response.ok) throw new Error(response.status === 401 ? "Sign in again to continue." : response.status === 403 ? "This account is not authorized." : response.status === 429 ? "Research is busy. Try again shortly." : "Unable to reach SWAN. Your question is preserved.");
    return response.json();
  }, [user]);
  useEffect(() => {
    const restore = () => setScreen(location.hash === "#insights" ? "insights" : "chat");
    restore(); window.addEventListener("hashchange", restore);
    return () => window.removeEventListener("hashchange", restore);
  }, []);
  useEffect(() => {
    if (screen !== "insights") return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function load() {
      if (!alive) return;
      if (!document.hidden && navigator.onLine) {
        setLoading(true);
        try {
          const result = await request("/api/bot/insights", "GET", controller.signal) as Snapshot;
          if (!Array.isArray(result.quotes) || !Array.isArray(result.insights) || !result.worker || !result.analysis) throw new Error("Market response is unavailable.");
          if (alive) { setData(result); setError(""); }
        } catch (problem) { if (alive) setError(problem instanceof Error ? problem.message : "Unable to refresh."); }
        finally { if (alive) setLoading(false); }
      }
      if (alive) timer = setTimeout(load, 60000);
    }
    void load();
    return () => { alive = false; controller.abort(); clearTimeout(timer); };
  }, [screen, request, refresh]);
  async function leave() {
    // Bot conversations use their own owner namespace; legacy project caches remain separate.
    try { for (const key of Object.keys(localStorage)) if (key.includes(ownerKey)) localStorage.removeItem(key); } catch { /* Sign-out still works when storage is unavailable. */ }
    setData(null); onSignOut();
  }
  function go(value: "chat" | "insights") { location.hash = value; setScreen(value); }
  async function loadEvidence(id: string) {
    setEvidenceBusy(id);
    try { const result = await request(`/api/bot/insights/${id}/evidence`) as Evidence;
      if (!Array.isArray(result.bars)) throw new Error("Source record is unavailable.");
      setEvidence(current => ({ ...current, [id]: result }));
    } catch { setError("Unable to load this source record. The insight remains visible."); }
    finally { setEvidenceBusy(""); }
  }
  return <div className="swan-app bot-app">
    <header className="bot-header"><Brand /><nav aria-label="Primary navigation">
      <button className="text-button" aria-current={screen === "chat" ? "page" : undefined} onClick={() => go("chat")}>Chat</button>
      <button className="text-button" aria-current={screen === "insights" ? "page" : undefined} onClick={() => go("insights")}>Insights</button>
    </nav><button className="text-button bot-signout" onClick={() => void leave()}>Sign out</button></header>
    <div className="bot-chat" hidden={screen !== "chat"}>
      <Chat request={request} ownerKey={ownerKey} sessionId="main" active={screen === "chat"}
        onTitle={() => {}} onMarket={() => go("insights")} />
    </div>
    {screen === "insights" && <main className="bot-insights">
      <div className="bot-heading"><div><p className="eyebrow">OBSERVE. QUESTION. UNDERSTAND.</p><h1>Market insights</h1><p>What changed, the evidence behind it, and what remains uncertain.</p></div>
        <button onClick={() => setRefresh(value => value + 1)} disabled={loading}>{loading ? "Refreshing…" : "Refresh saved insights"}</button></div>
      {error && <p role="alert" className="error">{error}{data ? " Previously received observations remain below." : ""}</p>}
      {!data && loading && <p role="status">Loading your saved market observations…</p>}
      {data && <>
        <aside className="bot-status"><strong>Collection: {words(data.worker.status)}</strong><span>{data.worker.heartbeat_current ? "Worker heartbeat received" : "Worker heartbeat unavailable or old"} · Market calendar: {data.calendar.state}</span>
          {data.worker.detail && <p>{data.worker.detail}</p>}<p>Saved response received {stamp(data.as_of)}. Source times are shown separately. Refresh reads saved records.</p>
          {data.worker.problems?.length ? <p>Some source reads failed. Retained values may be historical.</p> : null}</aside>
        <section className="bot-quotes" aria-label="Index observations">{data.quotes.map(row => <article key={row.underlying}><div className="bot-row"><h2>{row.underlying}</h2><span>{words(row.status === "current" && row.quote && clock - Date.parse(row.quote.timestamp) > 90000 ? "historical" : row.status)}</span></div>
          <p className="bot-price">{row.quote ? Number(row.quote.last_price).toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "Unavailable"}</p><p>Observed {stamp(row.quote?.timestamp)}</p></article>)}</section>
        <section className="bot-analysis"><h2>NIFTY candle context <small>{words(data.analysis.status === "current" && data.analysis.as_of && clock - Date.parse(data.analysis.as_of) > 180000 ? "historical" : data.analysis.status)}</small></h2>
          {data.analysis.last_close ? <><p>Last completed close: {data.analysis.last_close} · {stamp(data.analysis.as_of)}</p><dl><div><dt>Trend</dt><dd>{words(data.analysis.trend)}</dd></div><div><dt>Opening range</dt><dd>{words(data.analysis.range_state)}</dd></div></dl></> : <p>{data.analysis.reason ?? "Waiting for validated completed candles."}</p>}
          <p className="note">SENSEX candle scans, options and live news are not available in this first slice.</p></section>
        <section aria-labelledby="changes"><h2 id="changes">Recorded changes</h2>{!data.insights.length && <p>No validated changes have been recorded yet. This does not establish that the market is quiet.</p>}
          {data.insights.map(insight => <article className="bot-insight" key={insight.id}><p className="eyebrow">{stamp(insight.as_of)} · SAVED OBSERVATION</p><h3>{insight.title}</h3><p>{insight.summary}</p><p className="note">{insight.limitation}</p>
            <details><summary>Evidence and calculation</summary><p>Close: {insight.facts.last_close} · SMA: {insight.facts.sma20 ?? "Unavailable"}</p><p>Range: {insight.facts.range_low}–{insight.facts.range_high}</p><p>{insight.facts.source} · {insight.facts.rule}</p><p>{insight.facts.evidence.length} source candle references retained.</p>
              {!evidence[insight.id] ? <button className="text-button" disabled={!!evidenceBusy} onClick={() => void loadEvidence(insight.id)}>{evidenceBusy === insight.id ? "Loading source…" : "Inspect source candles"}</button> : <div><p>Source received {stamp(evidence[insight.id].received_at)} · {evidence[insight.id].bars.length} validated bars</p><p>Response fingerprint: {evidence[insight.id].response_sha256}</p><ol>{evidence[insight.id].bars.slice(-20).map(bar => <li key={bar.evidence_id}>{stamp(bar.opens_at)} · close {bar.close}</li>)}</ol></div>}
            </details></article>)}</section>
      </>}
    </main>}
  </div>;
}
