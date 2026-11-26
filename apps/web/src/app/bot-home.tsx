"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, Bookmark, Clock3, LogOut, PanelLeft, Plus, RefreshCw, Settings2, X } from "lucide-react";
import type { User } from "firebase/auth";
import Chat from "./chat";
import Brand from "./brand";
import IdeaCard, { type AdvisoryIdea } from "./idea-card";
import { clearArchive, readArchive, writeArchive } from "@/lib/bot-archive";
import { useChatSessions } from "./chat-sessions";

type Quote = { underlying: string; status: string; age_seconds: number | null;
  quote: { last_price: string; timestamp: string; source: string } | null };
type Analysis = { status: string; underlying?: string; missing_minutes?: string[]; reason?: string; as_of?: string; last_close?: string;
  sma20?: string; range_high?: string; range_low?: string; range_state?: string; trend?: string };
type Insight = { id: string; as_of: string; published_at?: string; title: string; summary: string; limitation: string;
  kind?: string;
  facts: Analysis & { evidence: string[]; source: string; rule: string; news?: { title: string; url: string; published_at: string }[] } };
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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [feed, setFeed] = useState<"latest" | "saved">("latest");
  const [pushEnabled, setPushEnabled] = useState(false);
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
  const chats = useChatSessions(ownerKey);
  const [chatListOpen, setChatListOpen] = useState(false);
  const [chatSidebarClosed, setChatSidebarClosed] = useState(false);
  const chatListTrigger = useRef<HTMLButtonElement>(null);
  const chatListClose = useRef<HTMLButtonElement>(null);
  const chatListElement = useRef<HTMLElement>(null);
  useEffect(() => {
    const narrow = window.matchMedia("(max-width:760px)");
    const resetDrawer = () => { if (!narrow.matches) setChatListOpen(false); };
    narrow.addEventListener("change", resetDrawer);
    return () => narrow.removeEventListener("change", resetDrawer);
  }, []);
  useEffect(() => {
    if (!chatListOpen) return;
    const frame = requestAnimationFrame(() => chatListClose.current?.focus());
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setChatListOpen(false); chatListTrigger.current?.focus(); }
      if (event.key !== "Tab") return;
      const buttons = [...(chatListElement.current?.querySelectorAll<HTMLButtonElement>("button:not([disabled])") ?? [])];
      if (!buttons.length) return;
      if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[buttons.length - 1].focus(); }
      else if (!event.shiftKey && document.activeElement === buttons[buttons.length - 1]) { event.preventDefault(); buttons[0].focus(); }
    };
    window.addEventListener("keydown", close);
    return () => { cancelAnimationFrame(frame); window.removeEventListener("keydown", close); };
  }, [chatListOpen]);
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
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    let alive = true;
    void navigator.serviceWorker.getRegistration().then(registration => registration?.pushManager?.getSubscription())
      .then(subscription => { if (alive) setPushEnabled(Boolean(subscription)); }).catch(() => {});
    return () => { alive = false; };
  }, []);
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
  function go(value: "chat" | "insights") { setChatListOpen(false); location.hash = value; setScreen(value); }
  async function saveBudget() {
    try { await request("/api/bot/preferences", "POST", undefined, { position_budget: budget || data?.preferences?.position_budget || "0" });
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
        setPushEnabled(false); setPushMessage("Notifications disabled on all your devices."); return;
      }
      if (await Notification.requestPermission() !== "granted") { setPushMessage("Notifications were not allowed. Insights still update while the app is open."); return; }
      const result = await request("/api/bot/push-key") as { public_key: string };
      const raw = atob(result.public_key.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - result.public_key.length % 4) % 4));
      const key = Uint8Array.from(raw, char => char.charCodeAt(0));
      const subscription = await registration.pushManager.getSubscription() ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
      await request("/api/bot/push", "POST", undefined, subscription.toJSON());
      setPushEnabled(true); setPushMessage("Update notifications enabled. Open the app to confirm current conditions; delivery can be delayed by your device.");
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
  const ideas = data?.current_ideas ?? [];
  const visibleIdeas = feed === "saved" ? ideas.filter(idea => starred.includes(idea.id)) : ideas;
  const archived = (data?.insights ?? []).filter(item => !ideas.some(idea => idea.id === item.id) && (feed !== "saved" || starred.includes(item.id)));
  const closed = data?.calendar.state === "closed";
  const sessionLabel = closed ? "Market closed" : data?.calendar.state === "open" ? "Market open" : "Market status unavailable";
  const discuss = (idea: { id: string; title: string }) => { chats.create(); setSelectedIdea({ id: `idea:${idea.id}`, label: idea.title }); go("chat"); };
  const marketValues = ["SENSEX", "NIFTY"].flatMap(name => {
    const row = data?.quotes.find(quote => quote.underlying === name);
    const analysis = data?.analyses?.[name] ?? (name === "SENSEX" ? data?.analysis : undefined);
    const value = row?.quote?.last_price ?? analysis?.last_close;
    const at = row?.quote?.timestamp ?? analysis?.as_of;
    const current = row?.status === "current" && at && clock - Date.parse(at) <= 90000;
    return value ? [{ name, value, at, current }] : [];
  });
  return <div className="swan-app bot-app">
    <header className="bot-header"><Brand /><nav aria-label="Primary navigation">
      <button className="text-button" aria-current={screen === "chat" ? "page" : undefined} onClick={() => go("chat")}>Chat</button>
      <button className="text-button" aria-current={screen === "insights" ? "page" : undefined} onClick={() => go("insights")}>Insights</button>
    </nav><button className="text-button bot-signout" aria-label="Sign out" title="Sign out" onClick={() => void leave()}><LogOut size={19} aria-hidden="true" /></button></header>
    <div className={`bot-chat ${chatSidebarClosed ? "is-sidebar-closed" : ""}`} hidden={screen !== "chat"}>
      {chatListOpen && <button type="button" className="chat-list-backdrop" aria-label="Close conversations" onClick={() => { setChatListOpen(false); requestAnimationFrame(() => chatListTrigger.current?.focus()); }} />}
      <aside ref={chatListElement} id="bot-conversations" className={`bot-conversations ${chatListOpen ? "is-open" : ""}`} aria-label="Conversations" role={chatListOpen ? "dialog" : undefined} aria-modal={chatListOpen ? true : undefined}>
        <div className="chat-list-top"><strong>Chats</strong><button ref={chatListClose} className="chat-list-close" type="button" aria-label="Close conversations" onClick={() => { setChatListOpen(false); if (!window.matchMedia("(max-width:760px)").matches) setChatSidebarClosed(true); requestAnimationFrame(() => chatListTrigger.current?.focus()); }}><X size={19} aria-hidden="true" /></button></div>
        <button className="chat-list-new" type="button" onClick={() => { chats.create(); setSelectedIdea(null); setChatListOpen(false); }}><Plus size={18} aria-hidden="true" />New conversation</button>
        <nav className="chat-list-threads" aria-label="Saved conversations">{[...chats.sessions].sort((a, b) => b.updated - a.updated).map(session => <button key={session.id} type="button" title={session.title} aria-current={chats.activeId === session.id ? "page" : undefined} onClick={() => { chats.select(session.id); setSelectedIdea(null); setChatListOpen(false); }}><span>{session.title}</span></button>)}</nav>
      </aside>
      <div className="bot-chat-main">
        <div className="chat-side-controls"><button ref={chatListTrigger} type="button" aria-label="Open conversations" aria-controls="bot-conversations" aria-expanded={chatListOpen} onClick={() => { if (window.matchMedia("(max-width:760px)").matches) setChatListOpen(true); else { setChatListOpen(false); setChatSidebarClosed(false); } }}><PanelLeft size={20} aria-hidden="true" /></button><button type="button" aria-label="New conversation" onClick={() => { chats.create(); setSelectedIdea(null); }}><Plus size={20} aria-hidden="true" /></button></div>
        {chats.ready && chats.activeId && <Chat key={chats.activeId} request={request} ownerKey={ownerKey} sessionId={chats.activeId} active={screen === "chat"}
          context={selectedIdea} onClearContext={() => setSelectedIdea(null)}
          onTitle={text => chats.title(chats.activeId, text)} onMarket={() => go("insights")} />}
      </div>
    </div>
    {screen === "insights" && <main className="bot-insights">
      <div className="insights-titlebar"><div><p className="insights-date">{new Date(clock).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", weekday: "long", day: "numeric", month: "long" })}</p><h1>Insights</h1></div>
        <div className="insights-tools"><button className="insight-icon-button secondary" aria-label="Refresh insights" title="Refresh" onClick={() => refreshCurrent.current()} disabled={loading}><RefreshCw size={18} aria-hidden="true" className={loading ? "is-refreshing" : undefined} /></button>
        <button className="insight-icon-button secondary" aria-label={settingsOpen ? "Close insight settings" : "Insight settings"} aria-expanded={settingsOpen} aria-controls="insight-settings" onClick={() => setSettingsOpen(value => !value)}>{settingsOpen ? <X size={19} aria-hidden="true" /> : <Settings2 size={19} aria-hidden="true" />}</button></div></div>
      {error && <p role="alert" className="insight-message error">{error}</p>}
      {archiveError && <p role="alert" className="insight-message error">{archiveError}</p>}
      {settingsOpen && <section id="insight-settings" className="insight-settings" aria-label="Insight settings">
        <h2>Preferences</h2><form className="insight-budget-form" onSubmit={event => { event.preventDefault(); void saveBudget(); }}>
          <label htmlFor="position-budget">Position budget <span>Maximum premium per trade</span></label><div><span className="budget-currency">INR</span><input id="position-budget" type="number" min="0" max="10000000" step="0.01" inputMode="decimal" value={budget} placeholder={data?.preferences?.position_budget === "0" ? "Not set" : data?.preferences?.position_budget} onChange={event => setBudget(event.target.value)} /><button>Save</button></div>
          <p className="note">Risk reference: 5% of the position premium. You place every trade.</p>{budgetMessage && <p role="status" className="note">{budgetMessage}</p>}</form>
        <div className="insight-notifications"><div><strong>Notifications</strong><p>Get an update when an idea changes.</p></div><button className="insight-secondary secondary" onClick={() => void notifications(!pushEnabled)}>{pushEnabled ? "Turn off all devices" : "Enable"}</button></div>
        {pushMessage && <p role="status" className="note">{pushMessage}</p>}
        <details className="insight-details"><summary>Storage &amp; data status</summary><p>Insights are saved on this device. Starred items also stay on the server. Signing out clears this device's archive.</p><p>Unstarred server history: seven days or 1,000 items. Starred: up to 200.</p><p>Collection: {words(data?.worker.status)}. Last sync: {stamp(data?.as_of)}.</p>{data?.news?.sources.map((source, index) => <p key={source.source ?? index}>{source.source}: {words(source.status)}</p>)}</details>
      </section>}
      {data && <div className="market-strip" aria-label="Market summary"><span className="market-session"><span className={closed ? "session-dot" : "session-dot session-open"} />{sessionLabel}</span>
        {marketValues.map(row => <div className="market-value" key={row.name} title={stamp(row.at)}><span>{row.name}</span><strong>{Number(row.value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}</strong><small>{row.current ? "Live" : row.at ? new Date(row.at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) + " IST" : "Historical"}</small></div>)}</div>}
      <div className="insight-feedbar"><div className="insight-filters" aria-label="Insight filter"><button className="secondary" aria-pressed={feed === "latest"} onClick={() => setFeed("latest")}>Latest</button><button className="secondary" aria-pressed={feed === "saved"} onClick={() => setFeed("saved")}><Bookmark size={15} aria-hidden="true" />Saved{starred.length > 0 && <span>{starred.length}</span>}</button></div><span className="insight-sync">{loading ? "Updating" : data ? "Saved on this device" : "Connecting"}</span></div>
      {!data && <div className="insight-empty" role="status"><div className="insight-empty-icon"><Clock3 size={25} aria-hidden="true" /></div><h2>{loading || !ready ? "Getting your insights" : "Waiting for a connection"}</h2><p>{loading || !ready ? "Your saved research will appear here." : "Previously downloaded insights appear here when available."}</p></div>}
      {data && <>
        {!!visibleIdeas.length && <section aria-label="Current ideas" className="insight-ideas">{visibleIdeas.map(idea => <IdeaCard key={idea.id} idea={idea} clock={clock} starred={starred.includes(idea.id)} onStar={() => void toggleStar(idea.id)} onDiscuss={() => discuss(idea)} request={request} onUpdated={() => refreshCurrent.current()} />)}</section>}
        {!visibleIdeas.length && (feed === "latest" || !archived.length) && <section className="insight-empty insight-empty-compact" aria-label="No current ideas"><div className="insight-empty-icon">{feed === "saved" ? <Bookmark size={25} aria-hidden="true" /> : <Clock3 size={25} aria-hidden="true" />}</div>
          <div><h2>{feed === "saved" ? "No saved insights yet" : closed ? "No new trade ideas" : data.worker.heartbeat_current ? "Watching for a clear setup" : "Waiting for market data"}</h2><p>{feed === "saved" ? "Save an insight to come back to it." : closed ? "Market closed. Your latest research is below." : "Ideas appear when current data supports them."}</p></div></section>}
        {feed === "latest" && !!data.news?.items.length && <section className="insight-brief" aria-labelledby="market-brief"><div className="insight-section-heading"><h2 id="market-brief">Market brief</h2><span>From your sources</span></div>{data.news.items.slice(0, 5).map(item => <a className="brief-story" key={item.id} href={item.url} target="_blank" rel="noreferrer"><div><p>{item.title}</p><span>{item.source} <span aria-hidden="true">/</span> {new Date(item.published_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} IST</span></div><ArrowUpRight size={17} aria-hidden="true" /></a>)}</section>}
        {feed === "latest" && data.weekly?.last_close && <details className="insight-weekly"><summary><div><span>Weekly view</span><small>{data.weekly.status === "partial" ? "Partial history" : "Daily structure"}</small></div><ArrowRight size={17} aria-hidden="true" /></summary><p>Last available daily close: {Number(data.weekly.last_close).toLocaleString("en-IN", { maximumFractionDigits: 2 })} at {stamp(data.weekly.as_of)}.</p><p>{data.weekly.reason}</p><button className="text-button" onClick={() => go("chat")}>Discuss in chat</button></details>}
        {!!archived.length && <section className="insight-archive" aria-label={feed === "saved" ? "Saved insights" : "Earlier insights"}><h2>{feed === "saved" ? "Saved research" : "Earlier insights"}</h2>{archived.slice(0, visibleCount).map(insight => insight.kind === "idea" ? <IdeaCard key={insight.id} idea={insight as unknown as AdvisoryIdea} clock={clock} starred={starred.includes(insight.id)} onStar={() => void toggleStar(insight.id)} onDiscuss={() => discuss(insight)} request={request} onUpdated={() => refreshCurrent.current()} /> : <article className="bot-insight" key={insight.id}><div className="bot-row"><small>{stamp(insight.as_of)}</small><button className="insight-icon-button secondary" aria-label={starred.includes(insight.id) ? "Unsave insight" : "Save insight"} aria-pressed={starred.includes(insight.id)} disabled={!!starBusy} onClick={() => void toggleStar(insight.id)}><Bookmark size={17} fill={starred.includes(insight.id) ? "currentColor" : "none"} aria-hidden="true" /></button></div><h3>{insight.title}</h3><p>{insight.summary}</p><details className="insight-details"><summary>Evidence</summary><p>{insight.limitation}</p><p>{insight.facts.source}</p>{insight.kind === "brief" ? insight.facts.news?.map(row => <p key={row.url}><a href={row.url} target="_blank" rel="noreferrer">{row.title}</a></p>) : !evidence[insight.id] ? <button className="text-button" disabled={!!evidenceBusy} onClick={() => void loadEvidence(insight.id)}>View source candles</button> : <div><p>{evidence[insight.id].bars.length} candles, received {stamp(evidence[insight.id].received_at)}</p><ol>{evidence[insight.id].bars.slice(-20).map(bar => <li key={bar.evidence_id}>{stamp(bar.opens_at)}: {bar.close}</li>)}</ol></div>}</details></article>)}{archived.length > visibleCount && <button className="insight-secondary secondary" onClick={() => setVisibleCount(value => value + 100)}>Load earlier insights</button>}</section>}
        {!!data.reported_entries?.length && <details className="insight-details"><summary>Your reported entries ({data.reported_entries.length})</summary>{data.reported_entries.map(entry => <p key={entry.idea_id}>{entry.quantity} units at INR {entry.premium}. User-reported, not broker-verified.</p>)}</details>}
      </>}
    </main>}
  </div>;
}
