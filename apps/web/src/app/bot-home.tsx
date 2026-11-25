"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { User } from "firebase/auth";
import Chat from "./chat";
import Brand from "./brand";
import IdeaCard, { type AdvisoryIdea } from "./idea-card";
import { clearArchive, readArchive, writeArchive } from "@/lib/bot-archive";

type Quote = { underlying: string; status: string; age_seconds: number | null;
  quote: { last_price: string; timestamp: string; source: string } | null };
type Analysis = { status: string; underlying?: string; missing_minutes?: string[]; reason?: string; as_of?: string; last_close?: string;
  sma20?: string; range_high?: string; range_low?: string; range_state?: string; trend?: string };
type Insight = { id: string; as_of: string; published_at?: string; title: string; summary: string; limitation: string;
  kind?: string;
  facts: Analysis & { evidence: string[]; source: string; rule: string } };
type Snapshot = { as_of: string; quotes: Quote[]; analysis: Analysis; analyses?: Record<string, Analysis>; insights: Insight[];
  evaluation?: { sample_count: number; closed_count: number; priced_count: number; unpriced_count: number; net_estimate_total: string; limitation: string };
  current_ideas?: AdvisoryIdea[]; preferences?: { position_budget: string };
  news?: { sources: { source?: string; status: string }[]; items: { id: string; title: string; source: string; published_at: string; url: string }[] };
  weekly?: { status: string; reason?: string; last_close?: string; as_of?: string };
  reported_entries?: { idea_id: string; premium: string; quantity: number }[];
  worker: { status: string; detail?: string; heartbeat_current: boolean; problems?: string[] };
  calendar: { state: string; last_covered_day?: string } };
type Evidence = { source: string; response_sha256: string; received_at: string;
  bars: { opens_at: string; close: string; evidence_id: string }[] };
type Delta = Snapshot & { cursor: number; has_more: boolean; saved: Insight[]; saved_ids: string[]; saved_version: string; server_reset: boolean };
const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const stamp = (value?: string) => value ? new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", dateStyle: "medium", timeStyle: "medium" }) + " IST" : "Not received";
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
  const [starred, setStarred] = useState<string[]>([]);
  const [starBusy, setStarBusy] = useState("");
  const [archiveError, setArchiveError] = useState("");
  const [ready, setReady] = useState(false);
  const [visibleCount, setVisibleCount] = useState(100);
  const [selectedIdea, setSelectedIdea] = useState<{ id: string; label: string } | null>(null);
  const [budget, setBudget] = useState("");
  const [budgetMessage, setBudgetMessage] = useState("");
  const [pushMessage, setPushMessage] = useState("");
  const refreshCurrent = useRef<() => void>(() => {});
  const archive = useRef({ cursor: 0, insights: [] as Insight[], savedVersion: "" });
  const active = useRef(true);
  const ownerKey = `bot.${user.uid}`;
  useEffect(() => {
    let alive = true;
    void readArchive<Snapshot, Insight>(ownerKey).then(saved => {
      if (!alive) return;
      archive.current = { cursor: saved.metadata?.cursor ?? 0, insights: saved.insights, savedVersion: "" };
      if (saved.metadata) { setData({ ...saved.metadata.snapshot, insights: saved.insights }); setStarred(saved.metadata.starred); }
    }).catch(() => { if (alive) setArchiveError("Device storage is unavailable. Insights received now may not survive closing the app."); })
      .finally(() => { if (alive) setReady(true); });
    return () => { alive = false; };
  }, [ownerKey]);
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 1000); return () => clearInterval(timer); }, []);
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
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string } | null;
      const detail = typeof payload?.detail === "string" ? payload.detail : "";
      if (detail === "ACCOUNT_NOT_AUTHORIZED") throw new Error("Your sign-in succeeded, but this backend has not linked your account. This is an app configuration issue.");
      if (/^(BROKER_|DAILY_BROKER_|ANGELONE_)/.test(detail)) throw new Error("Market data is waiting for the broker session. Your app sign-in and saved records are separate.");
      if (detail === "PROVIDER_RATE_LIMITED") throw new Error("Market data is temporarily rate limited. Saved records remain available.");
      if (response.status === 401) throw new Error("Sign in again to continue.");
      if (response.status === 403) throw new Error("The server refused this request. Reconnect and retry; this response does not identify a broker-login problem.");
      if (response.status === 429) throw new Error("Research is busy. Try again shortly.");
      throw new Error("Unable to reach SWAN. Your question is preserved.");
    }
    return response.json();
  }, [user]);
  useEffect(() => {
    const restore = () => setScreen(location.hash === "#insights" || (!navigator.onLine && !location.hash) ? "insights" : "chat");
    restore(); window.addEventListener("hashchange", restore);
    return () => window.removeEventListener("hashchange", restore);
  }, []);
  useEffect(() => {
    if (!ready) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    let running = false;
    async function load() {
      if (!alive || running) return;
      running = true;
      if (!document.hidden && navigator.onLine) {
        setLoading(true);
        try {
          const result = await request(`/api/bot/insights?after=${archive.current.cursor}&saved_version=${archive.current.savedVersion}`, "GET", controller.signal) as Delta;
          if (!Array.isArray(result.quotes) || !Array.isArray(result.insights) || !result.worker || !result.analysis) throw new Error("Market response is unavailable.");
          if (!Number.isSafeInteger(result.cursor) || !Array.isArray(result.saved) || !Array.isArray(result.saved_ids)) throw new Error("Insight sync is unavailable. Update the bot backend before syncing.");
          if (alive && active.current) {
            const updates = [...result.insights, ...result.saved];
            const merged = new Map(archive.current.insights.map(item => [item.id, item]));
            for (const item of updates) merged.set(item.id, item);
            const insights = [...merged.values()].sort((a, b) => b.as_of.localeCompare(a.as_of));
            const stars = result.saved_ids;
            // Advance the durable cursor only in the same transaction as its new records.
            try {
              await writeArchive(ownerKey, updates, { cursor: result.cursor, snapshot: { ...result, insights: [], saved: [] } as Snapshot, starred: stars });
              setArchiveError("");
            } catch { setArchiveError("Device storage failed. Keep this app open or retry to preserve received insights."); }
            archive.current = { cursor: result.cursor, insights, savedVersion: result.saved_version };
            setData({ ...result, insights }); setStarred(stars); setError("");
            if (result.has_more) { running = false; void load(); return; }
          }
        } catch (problem) { if (alive) setError(problem instanceof Error ? problem.message : "Unable to refresh."); }
        finally { if (alive) setLoading(false); }
      }
      running = false;
      if (alive) timer = setTimeout(load, 15000);
    }
    const wake = () => { clearTimeout(timer); void load(); };
    refreshCurrent.current = wake;
    window.addEventListener("online", wake); document.addEventListener("visibilitychange", wake);
    void load();
    return () => { alive = false; controller.abort(); clearTimeout(timer); window.removeEventListener("online", wake); document.removeEventListener("visibilitychange", wake); };
  }, [ready, request, refresh, ownerKey]);
  useEffect(() => {
    if (!ready) return;
    const controller = new AbortController();
    let retry: ReturnType<typeof setTimeout>;
    async function listen() {
      if (controller.signal.aborted) return;
      try {
        if (!navigator.onLine || document.hidden) throw new Error("paused");
        const token = await user.getIdToken();
        const response = await fetch(base + "/api/bot/events", { cache: "no-store",
          headers: { Authorization: `Bearer ${token}` },
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(65000)]) });
        if (!response.ok || !response.body) throw new Error("stream unavailable");
        const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
        while (!controller.signal.aborted) {
          const chunk = await reader.read(); if (chunk.done) break;
          buffer += decoder.decode(chunk.value, { stream: true });
          if (buffer.length > 65536) throw new Error("stream invalid");
          let boundary: number;
          while ((boundary = buffer.indexOf("\n\n")) >= 0) {
            const event = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
            if (event.startsWith("event: update")) refreshCurrent.current();
          }
        }
      } catch { /* Visible 15-second delta polling remains the fallback. */ }
      if (!controller.signal.aborted) retry = setTimeout(listen, 3000);
    }
    void listen();
    return () => { controller.abort(); clearTimeout(retry); };
  }, [ready, user]);
  async function leave() {
    active.current = false;
    try { const registration = await navigator.serviceWorker?.getRegistration();
      await (await registration?.pushManager.getSubscription())?.unsubscribe();
    } catch { /* Server sends no private details to a lock screen. */ }
    // Bot conversations use their own owner namespace; legacy project caches remain separate.
    try { for (const key of Object.keys(localStorage)) if (key.includes(ownerKey)) localStorage.removeItem(key); } catch { /* Sign-out still works when storage is unavailable. */ }
    try { await clearArchive(ownerKey); } catch { /* Records stay scoped to this signed-in account. */ }
    setData(null); onSignOut();
  }
  function go(value: "chat" | "insights") { location.hash = value; setScreen(value); }
  async function saveBudget() {
    try { await request("/api/bot/preferences", "POST", undefined, { position_budget: budget || "0" });
      setBudgetMessage("Position budget saved. This does not authorize any order."); refreshCurrent.current();
    } catch { setBudgetMessage("Budget was not saved. Reconnect and enter a valid amount."); }
  }
  async function notifications(enable: boolean) {
    try {
      if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) throw new Error("unsupported");
      const registration = await navigator.serviceWorker.ready;
      if (!enable) {
        await request("/api/bot/push/disable", "POST", undefined, {});
        await (await registration.pushManager.getSubscription())?.unsubscribe();
        setPushMessage("Notifications disabled on all your devices."); return;
      }
      if (await Notification.requestPermission() !== "granted") { setPushMessage("Notifications were not allowed. Insights still update while the app is open."); return; }
      const result = await request("/api/bot/push-key") as { public_key: string };
      const raw = atob(result.public_key.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - result.public_key.length % 4) % 4));
      const key = Uint8Array.from(raw, char => char.charCodeAt(0));
      const subscription = await registration.pushManager.getSubscription() ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
      await request("/api/bot/push", "POST", undefined, subscription.toJSON());
      setPushMessage("Update notifications enabled. Open the app to confirm current conditions; delivery can be delayed by your device.");
    } catch { setPushMessage("Notifications could not be updated. Use a supported installed PWA and reconnect."); }
  }
  async function toggleStar(id: string) {
    setStarBusy(id);
    try {
      await request(`/api/bot/insights/${id}/star`, "POST", undefined, { starred: !starred.includes(id) });
      setRefresh(value => value + 1);
    } catch { setError("Unable to change saved status. Reconnect and retry; older unstarred server records may have expired."); }
    finally { setStarBusy(""); }
  }
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
        context={selectedIdea} onClearContext={() => setSelectedIdea(null)}
        onTitle={() => {}} onMarket={() => go("insights")} />
    </div>
    {screen === "insights" && <main className="bot-insights">
      <div className="bot-heading"><div><p className="eyebrow">OBSERVE. QUESTION. UNDERSTAND.</p><h1>Market insights</h1><p>What changed, the evidence behind it, and what remains uncertain.</p></div>
        <button onClick={() => setRefresh(value => value + 1)} disabled={loading}>{loading ? "Refreshing…" : "Refresh saved insights"}</button></div>
      {error && <p role="alert" className="error">{error}{data ? " Previously received observations remain below." : ""}</p>}
      {archiveError && <p role="alert" className="error">{archiveError}</p>}
      <div className="idea-actions"><button onClick={() => void notifications(true)}>Enable update notifications</button><button onClick={() => void notifications(false)}>Disable all notifications</button></div>
      {pushMessage && <p role="status">{pushMessage}</p>}
      <p className="note">Received insights stay on this device until you sign out or clear site data. Star important ones for server retention (up to 200). Unstarred server records expire after seven days or 1,000 records. Catch-up beyond that window is not guaranteed.</p>
      {!data && loading && <p role="status">Loading your saved market observations…</p>}
      {data && <>
        <form className="bot-budget" onSubmit={event => { event.preventDefault(); void saveBudget(); }}>
          <label>Maximum premium allocation per position (INR)<input type="number" min="0" max="10000000" step="0.01" inputMode="decimal" value={budget} placeholder={data.preferences?.position_budget === "0" ? "Not set" : data.preferences?.position_budget} onChange={event => setBudget(event.target.value)} /></label>
          <button>Save position budget</button><p className="note">Used for one-lot affordability; your loss reference remains 5% of the position premium. No account balance is assumed.</p>
          {budgetMessage && <p role="status">{budgetMessage}</p>}</form>
        <aside className="bot-status"><strong>Collection: {words(data.worker.status)}</strong><span>{data.worker.heartbeat_current && clock - Date.parse(data.as_of) <= 180000 ? "Worker heartbeat received" : "Worker heartbeat unavailable or old"} · Last received market calendar: {data.calendar.state}</span>
          {data.worker.detail && <p>{data.worker.detail}</p>}<p>Server snapshot generated {stamp(data.as_of)}. Source times are shown separately. Refresh reads saved records.</p>
          {data.worker.problems?.length ? <p>Some source reads failed. Retained values may be historical.</p> : null}</aside>
        <section className="bot-quotes" aria-label="Index observations">{data.quotes.map(row => <article key={row.underlying}><div className="bot-row"><h2>{row.underlying}</h2><span>{words(row.status === "current" && row.quote && clock - Date.parse(row.quote.timestamp) > 90000 ? "historical" : row.status)}</span></div>
          <p className="bot-price">{row.quote ? Number(row.quote.last_price).toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "Unavailable"}</p><p>Observed {stamp(row.quote?.timestamp)}</p></article>)}</section>
        <section aria-labelledby="active-ideas"><h2 id="active-ideas">Decision ideas</h2>
          <p className="note">Experimental conditional research. Watch means wait; conditions met still requires your decision and fresh pricing.</p>
          {!data.current_ideas?.length && <p>No supported trade idea yet. The system will not force a call or put when required evidence is missing.</p>}
          {data.current_ideas?.map(idea => <IdeaCard key={idea.id} idea={idea} clock={clock} starred={starred.includes(idea.id)}
            onStar={() => void toggleStar(idea.id)} onDiscuss={() => { setSelectedIdea({ id: `idea:${idea.id}`, label: `${idea.title} / revision ${idea.revision}` }); go("chat"); }}
            request={request} onUpdated={() => refreshCurrent.current()} />)}</section>
        {!!data.reported_entries?.length && <aside className="bot-status"><strong>Your reported entries</strong>{data.reported_entries.map(entry => <p key={entry.idea_id}>{entry.quantity} units at INR {entry.premium} per unit. User-reported; not broker-verified or automatically protected.</p>)}</aside>}
        <section className="bot-analysis"><h2>Weekly research</h2><p>{words(data.weekly?.status)}</p><p>{data.weekly?.reason ?? "Waiting for verified daily history."}</p>{data.weekly?.last_close && <p>Verified daily close {data.weekly.last_close} at {stamp(data.weekly.as_of)}</p>}</section>
        <section className="bot-analysis"><h2>Source events</h2>{data.news?.sources.map((source, index) => <p key={source.source ?? index}>{source.source ?? "Official feed"}: {source.status}</p>)}
          {!data.news?.items.length && <p>No usable source excerpts received. This does not establish that there is no news.</p>}
          {data.news?.items.slice(0, 5).map(item => <p key={item.id}><a href={item.url} target="_blank" rel="noreferrer">{item.title}</a><br /><small>{item.source} / published {stamp(item.published_at)}</small></p>)}</section>
        {Object.entries(data.analyses ?? { SENSEX: data.analysis }).map(([name, analysis]) => <section className="bot-analysis" key={name}><h2>{name} candle context <small>{words(analysis.status === "current" && analysis.as_of && clock - Date.parse(analysis.as_of) > 180000 ? "historical" : analysis.status)}</small></h2>
          {analysis.last_close && <p>Last received completed close: {analysis.last_close} at {stamp(analysis.as_of)}</p>}
          {analysis.reason && <p>{analysis.reason}</p>}
          {analysis.trend ? <dl><div><dt>Trend</dt><dd>{words(analysis.trend)}</dd></div><div><dt>Opening range</dt><dd>{words(analysis.range_state)}</dd></div></dl> : !analysis.reason && <p>Waiting for validated completed candles.</p>}
          {!!analysis.missing_minutes?.length && <p className="note">{analysis.missing_minutes.length} missing completed minutes. Scans withheld while coverage is incomplete.</p>}
          <p className="note">Completed-bar context. Independent windows can remain useful when another window has gaps.</p></section>)}
        {data.evaluation && <section><h2>Prospective record</h2><p>{data.evaluation.sample_count} hypothetical ideas ? {data.evaluation.closed_count} closed ? {data.evaluation.unpriced_count} without a verified exit price.</p><p>Net estimate across {data.evaluation.priced_count} priced outcomes: INR {data.evaluation.net_estimate_total}. No trading edge established.</p><p className="note">{data.evaluation.limitation}</p></section>}
        <section aria-labelledby="changes"><h2 id="changes">Recorded changes</h2>{!data.insights.length && <p>No validated changes have been recorded yet. This does not establish that the market is quiet.</p>}
          {data.insights.filter(insight => !data.current_ideas?.some(idea => idea.id === insight.id)).slice(0, visibleCount).map(insight => insight.kind === "idea" ? <IdeaCard key={`archive-${insight.id}`} idea={insight as unknown as AdvisoryIdea} clock={clock}
            starred={starred.includes(insight.id)} onStar={() => void toggleStar(insight.id)} request={request}
            onDiscuss={() => { setSelectedIdea({ id: `idea:${insight.id}`, label: insight.title }); go("chat"); }} onUpdated={() => refreshCurrent.current()} /> : <article className="bot-insight" key={insight.id}><p className="eyebrow">{stamp(insight.as_of)} · SAVED OBSERVATION</p><h3>{insight.title}</h3><p>{insight.summary}</p><p className="note">{insight.limitation}</p>
            <button className="text-button" aria-pressed={starred.includes(insight.id)} disabled={!!starBusy} onClick={() => void toggleStar(insight.id)}>{starred.includes(insight.id) ? "Unstar" : "Star for retention"}</button>
            {insight.published_at && <p className="note">Published {stamp(insight.published_at)}</p>}
            <details><summary>Evidence and calculation</summary><p>Close: {insight.facts.last_close} · SMA: {insight.facts.sma20 ?? "Unavailable"}</p><p>Range: {insight.facts.range_low}–{insight.facts.range_high}</p><p>{insight.facts.source} · {insight.facts.rule}</p><p>{insight.facts.evidence.length} source candle references retained.</p>
              {!evidence[insight.id] ? <button className="text-button" disabled={!!evidenceBusy} onClick={() => void loadEvidence(insight.id)}>{evidenceBusy === insight.id ? "Loading source…" : "Inspect source candles"}</button> : <div><p>Source received {stamp(evidence[insight.id].received_at)} · {evidence[insight.id].bars.length} validated bars</p><p>Response fingerprint: {evidence[insight.id].response_sha256}</p><ol>{evidence[insight.id].bars.slice(-20).map(bar => <li key={bar.evidence_id}>{stamp(bar.opens_at)} · close {bar.close}</li>)}</ol></div>}
            </details></article>)}{data.insights.length > visibleCount && <button onClick={() => setVisibleCount(value => value + 100)}>Show older device insights</button>}</section>
      </>}
    </main>}
  </div>;
}
