"use client";

import { useEffect, useRef, useState } from "react";
import { time } from "@/lib/paper";
import Icon from "./icons";
import Brand from "./brand";
import { usePwa } from "./pwa";

type Request = (
  path: string,
  method?: string,
  signal?: AbortSignal,
  body?: unknown,
) => Promise<unknown>;
type Message = {
  id: number;
  question: string;
  answer: string;
  source: string;
  asOf: string;
};
type Reply = { answer: string; as_of: string; sources: { source: string }[] };
type Context = { id: string; label: string } | null;
const prompts = [
  {
    title: "What changed?",
    detail: "Understand the saved observations",
    question: "Explain the latest market observations and their limitations.",
    icon: "activity" as const,
  },
  {
    title: "Understand the range",
    detail: "Put the opening range in context",
    question: "What does the opening range tell us, and what can it not tell us?",
    icon: "book" as const,
  },
  {
    title: "See the evidence",
    detail: "Open your market insights",
    question: "",
    icon: "markets" as const,
  },
];

export default function Chat({
  request,
  ownerKey,
  sessionId,
  active = true,
  onTitle,
  context = null,
  onClearContext,
  onMarket,
}: {
  request: Request;
  ownerKey: string;
  sessionId: string;
  active?: boolean;
  onTitle: (text: string) => void;
  context?: Context;
  onClearContext?: () => void;
  onMarket?: () => void;
}) {
  const { offline } = usePwa();
  const historyKey = `swan.chat.history.v2.${ownerKey}.${sessionId}`;
  const draftKey = `swan.chat.draft.v1.${ownerKey}.${sessionId}`;
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [ready, setReady] = useState(false);
  const [pending, setPending] = useState("");
  const [failed, setFailed] = useState("");
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const asking = useRef(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const scrollRegion = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const lastScroll = useRef<number | null>(null);
  const [unread, setUnread] = useState(false);
  const scrollKey = `swan.chat.scroll.v1.${ownerKey}.${sessionId}`;
  useEffect(() => {
    try { const saved = sessionStorage.getItem(scrollKey); lastScroll.current = saved === null ? null : Number(saved); atBottom.current = saved === null; } catch { /* Scroll memory is optional. */ }
  }, [scrollKey]);
  useEffect(() => {
    if (!ready || !active) return;
    const frame = requestAnimationFrame(() => {
      const node = scrollRegion.current; if (!node) return;
      node.scrollTop = lastScroll.current ?? node.scrollHeight;
      atBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 64;
    });
    return () => cancelAnimationFrame(frame);
  }, [active, ready]);
  useEffect(() => {
    if (!active) { if (messages.length) setUnread(true); return; }
    if (atBottom.current) {
      const frame = requestAnimationFrame(() => { if (scrollRegion.current && atBottom.current) scrollRegion.current.scrollTop = scrollRegion.current.scrollHeight; });
      return () => cancelAnimationFrame(frame);
    }
    if (messages.length) setUnread(true);
  }, [messages.length, pending, failed, active]);
  useEffect(() => {
    if (!active || !input.current) return;
    input.current.style.height = "auto";
    input.current.style.height = `${Math.min(input.current.scrollHeight, 144)}px`;
  }, [question, active, context]);
  function rememberScroll() {
    const node = scrollRegion.current; if (!node) return;
    lastScroll.current = node.scrollTop;
    atBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 64;
    if (atBottom.current) setUnread(false);
    try { sessionStorage.setItem(scrollKey, String(node.scrollTop)); } catch { /* In-memory position remains. */ }
  }

  useEffect(() => {
    try {
      const saved: unknown = JSON.parse(
        localStorage.getItem(historyKey) ?? "[]",
      );
      if (Array.isArray(saved))
        setMessages(
          saved
            .filter(
              (item) =>
                item &&
                typeof item.id === "number" &&
                typeof item.question === "string" &&
                typeof item.answer === "string" &&
                typeof item.source === "string" &&
                typeof item.asOf === "string",
            )
            .slice(-50),
        );
      setQuestion(localStorage.getItem(draftKey) ?? "");
    } catch {
      /* Storage is optional. */
    }
    setReady(true);
    return () => {
      generation.current++;
      controller.current?.abort();
    };
  }, [historyKey, draftKey]);
  useEffect(() => {
    if (!ready) return;
    const save = () => {
      try {
        localStorage.setItem(historyKey, JSON.stringify(messages.slice(-50)));
        localStorage.setItem(draftKey, question || pending || failed);
      } catch { /* The conversation remains usable. */ }
    };
    const timer = setTimeout(save, 200);
    window.addEventListener("pagehide", save);
    return () => { clearTimeout(timer); window.removeEventListener("pagehide", save); };
  }, [messages, question, pending, failed, ready, historyKey, draftKey]);
  async function ask(text: string) {
    if (asking.current || !text.trim()) return;
    const value = text.trim();
    atBottom.current = true; setUnread(false);
    onTitle(value);
    asking.current = true;
    setPending(value);
    setFailed("");
    setError("");
    setQuestion("");
    const ticket = ++generation.current;
    controller.current = new AbortController();
    try {
      const history = messages.slice(-3).flatMap((message) => [
        { role: "user", content: message.question.slice(0, 4000) },
        { role: "assistant", content: message.answer.slice(0, 4000) },
      ]);
      const contextual = context
        ? `${value}\nSelected instrument: ${context.label} (id: ${context.id}).`
        : value;
      const reply = (await request(
        "/api/chat/messages",
        "POST",
        AbortSignal.any([
          controller.current.signal,
          AbortSignal.timeout(60000),
        ]),
        { question: contextual.slice(0, 2000), history },
      )) as Reply;
      if (generation.current !== ticket) return;
      setMessages((current) =>
        [
          ...current,
          {
            id: Date.now(),
            question: value,
            answer: reply.answer,
            source: reply.sources.map((row) => row.source).join("; "),
            asOf: reply.as_of,
          },
        ].slice(-50),
      );
    } catch (failure) {
      if (generation.current === ticket) {
        setFailed(value);
        setQuestion((current) => current || value);
        setError(failure instanceof Error && /^(This frontend|Research is busy|Sign in again|This account)/.test(failure.message) ? failure.message :
          "This answer couldn’t complete. Your question is preserved. You can retry or use the rest of SWAN.",
        );
      }
    } finally {
      if (generation.current === ticket) {
        asking.current = false;
        setPending("");
      }
    }
  }
  return (
    <section className="live-chat" aria-label="SWAN chat">
      <div ref={scrollRegion} className="chat-scroll-region" onScroll={rememberScroll}>
      {!messages.length && !pending && !failed ? (
        <div className="chat-welcome">
          <div className="intro-logo">
            <Brand markOnly />
          </div>
          <p className="eyebrow">A LITTLE CLARITY GOES A LONG WAY</p>
          <h1>
            Your market.
            <br />
            Your questions.
          </h1>
          <p>
            A place to understand the market, examine the evidence,
            <br className="desktop-break" /> and get a little better every day.
          </p>
          <div className="chat-suggestions">
            {prompts.map((prompt) => (
              <button
                key={prompt.title}
                className="chat-suggestion"
                onClick={() =>
                  prompt.question ? void ask(prompt.question) : onMarket?.()
                }
              >
                <Icon name={prompt.icon} />
                <strong>{prompt.title}</strong>
                <span>{prompt.detail}</span>
                <span className="suggestion-arrow" aria-hidden="true">
                  ↗
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div
          className="chat-transcript"
          aria-live="polite"
          aria-relevant="additions"
        >
          {messages.map((message) => (
            <article className="chat-turn" key={message.id}>
              <p className="chat-user">{message.question}</p>
              <div className="chat-answer">
                <div className="assistant-name">
                  <Brand markOnly />
                  SWAN
                </div>
                <p>{message.answer}</p>
                <details className="chat-sources">
                  <summary>Sources · {time(message.asOf)} IST</summary>
                  <p>{message.source || "No source records returned."}</p>
                  <p>
                    Answer retrieved at the time above. Market observations may
                    be older; check the times in the answer.
                  </p>
                </details>
                <button className="text-button" onClick={onMarket}>
                  View insights <Icon name="arrow" />
                </button>
              </div>
            </article>
          ))}
          {pending && (
            <article className="chat-turn">
              <p className="chat-user">{pending}</p>
              <div className="chat-wait" role="status">
                <span className="wait-dot" />
                Waiting for SWAN’s response…
                <span>You can read Insights while the answer is prepared.</span>
              </div>
            </article>
          )}
          {failed && <p className="chat-user">{failed}</p>}
        </div>
      )}
      {error && (
        <div className="chat-error" role="alert">
          <p>{error}</p>
          {failed && (
            <button
              className="text-button"
              disabled={!!pending}
              onClick={() => void ask(failed)}
            >
              Retry answer
            </button>
          )}
        </div>
      )}
      </div>
      <div className="live-composer-wrap">
        {unread && <button className="text-button latest-response" onClick={() => { if (scrollRegion.current) scrollRegion.current.scrollTop = scrollRegion.current.scrollHeight; atBottom.current = true; setUnread(false); }}>Jump to latest <Icon name="arrowUp" /></button>}
        <form
          className="live-composer"
          onSubmit={(event) => {
            event.preventDefault();
            void ask(question);
          }}
          aria-busy={!!pending}
        >
          {context && (
            <div className="chat-attachment">
              <Icon name="markets" />
              <span>{context.label}</span>
              <button
                type="button"
                aria-label="Remove instrument context"
                onClick={onClearContext}
              >
                ×
              </button>
            </div>
          )}
          <label className="sr-only" htmlFor={`swan-question-${sessionId}`}>
            Message SWAN
          </label>
          <textarea
            ref={input}
            id={`swan-question-${sessionId}`}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                if (!pending) void ask(question);
              }
            }}
            enterKeyHint="send"
            autoCapitalize="sentences"
            spellCheck
            maxLength={1800}
            rows={2}
            placeholder="Ask about the market, an observation, or an idea…"
          />
          <div className="composer-actions">
            <span>
              Ask. Explore.
              Understand.
            </span>
            <button
              className="chat-send"
              disabled={offline || !!pending || !question.trim()}
              type="submit"
              aria-label="Send message"
            >
              <Icon name="arrowUp" />
            </button>
          </div>
        </form>

      </div>
    </section>
  );
}
