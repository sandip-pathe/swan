"use client";

import { useEffect, useRef, useState } from "react";
import { time } from "@/lib/paper";

type Request = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
type Message = { id: number; question: string; answer: string; source: string; asOf: string };
type Reply = { answer: string; as_of: string; sources: { source: string }[] };
const prompts = ["What is happening in NIFTY?", "Why are the agents waiting?", "What is my paper P&L and risk?", "Explain VWAP and DEMA and how agents use them"];
const HISTORY_KEY = "swan.chat.history.v1";

export default function Chat({ request }: { request: Request }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const stopId = useRef<string | null>(null);
  useEffect(() => {
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
      if (Array.isArray(saved)) setMessages(saved.filter(item => item && typeof item.question === "string" && typeof item.answer === "string" && typeof item.source === "string" && typeof item.asOf === "string").slice(-50));
    } catch { /* History may be unavailable. */ }
    setReady(true);
  }, []);
  useEffect(() => {
    if (ready) try { localStorage.setItem(HISTORY_KEY, JSON.stringify(messages.slice(-50))); } catch { /* Session still works without persistence. */ }
  }, [messages, ready]);

  async function ask(text: string) {
    if (busy || !text.trim()) return;
    setBusy(true); setError("");
    try {
      const history = messages.slice(-3).flatMap(message => [
        { role: "user", content: message.question.slice(0, 4000) },
        { role: "assistant", content: message.answer.slice(0, 4000) },
      ]);
      const reply = await request("/api/chat/messages", "POST", undefined, { question: text.trim(), history }) as Reply;
      setMessages(current => [...current, { id: Date.now(), question: text, answer: reply.answer, source: reply.sources.map(row => row.source).join("; "), asOf: reply.as_of }]);
      setQuestion("");
    } catch { setError("SWAN could not complete this answer. No trading action was taken. Try again after checking provider status."); }
    finally { setBusy(false); }
  }
  async function stopEntries() {
    if (busy) return;
    setBusy(true); setError(""); stopId.current ??= crypto.randomUUID();
    try {
      const result = await request("/api/chat/stop-trading-today", "POST", undefined, { request_id: stopId.current }) as { effect: string; as_of: string };
      setMessages(current => [...current, { id: Date.now(), question: "Stop new entries today", answer: result.effect, source: "/api/chat/stop-trading-today", asOf: result.as_of }]);
      stopId.current = null;
    } catch { setError("Could not confirm the session stop. Check paper status before retrying."); }
    finally { setBusy(false); }
  }
  return <section className="panel" aria-label="SWAN chat">
    <p className="eyebrow">MARKET ASSISTANT</p><h2>Ask SWAN</h2>
    <p>Talk to the agent about market observations, indicators, strategy decisions and your paper account. Answers use read-only tools and show their sources. Missing or stale data stays explicit.</p>
    <div className="button-row">{prompts.map(prompt => <button key={prompt} className="secondary" disabled={busy} onClick={() => void ask(prompt)}>{prompt}</button>)}</div>
    <ol aria-live="polite">{messages.map(message => <li key={message.id} className="execution-card"><p><strong>You:</strong> {message.question}</p><p style={{ whiteSpace: "pre-wrap" }}><strong>SWAN:</strong> {message.answer}</p><p className="muted">Sources: <code>{message.source}</code> / Read at {time(message.asOf)} IST</p></li>)}</ol>
    <form onSubmit={event => { event.preventDefault(); void ask(question); }}>
      <label htmlFor="swan-question">Your message</label>
      <textarea style={{ width: "100%", minHeight: 96, padding: 12, border: "1px solid #d9dfeb", borderRadius: 12, font: "inherit", color: "inherit", resize: "vertical" }} id="swan-question" value={question} onChange={event => setQuestion(event.target.value)} maxLength={2000} rows={3} placeholder="What is the market doing, and why are we waiting?" disabled={busy} />
      <button disabled={busy || !question.trim()} type="submit">{busy ? "Reading tools and thinking..." : "Send"}</button>
    </form>
    {error && <p className="notice error" role="alert">{error}</p>}
    <p className="muted">Chat does not place orders or change risk. Agent paper plans use their own supported levels; the manual order form is optional.</p>
    <div className="button-row"><button className="secondary" disabled={busy} onClick={() => void stopEntries()}>Stop new entries today</button>{!!messages.length && <button className="text-button" disabled={busy} onClick={() => setMessages([])}>Clear history</button>}</div>
  </section>;
}
