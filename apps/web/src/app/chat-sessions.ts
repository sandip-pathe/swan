"use client";

import { useEffect, useState } from "react";

type Session = { id: string; title: string; updated: number };
export function useChatSessions(owner: string) {
  const storageKey = `swan.chat.sessions.v1.${owner}`;
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let rows: Session[] = [];
    let selected = "";
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) ?? "null");
      if (Array.isArray(saved?.sessions)) rows = saved.sessions.filter((item: Session) => item && typeof item.id === "string" && /^[a-zA-Z0-9-]+$/.test(item.id) && typeof item.title === "string" && typeof item.updated === "number");
      selected = saved?.activeId;
      if (!rows.length) {
        const existingMain = localStorage.getItem(`swan.chat.history.v2.${owner}.main`);
        const existingMainDraft = localStorage.getItem(`swan.chat.draft.v1.${owner}.main`);
        const id = existingMain || existingMainDraft ? "main" : crypto.randomUUID();
        const history = localStorage.getItem(`swan.chat.history.v2.${owner}`);
        const draft = localStorage.getItem(`swan.chat.draft.v1.${owner}`);
        let title = "New conversation";
        if (existingMain || history) {
          try {
            const messages = JSON.parse(existingMain || history || "[]");
            if (Array.isArray(messages) && typeof messages[0]?.question === "string") title = messages[0].question.slice(0, 64);
          } catch { /* Keep the existing thread even if its saved preview is unreadable. */ }
          if (!existingMain && history) localStorage.setItem(`swan.chat.history.v2.${owner}.${id}`, history);
        }
        if (!existingMain && draft) localStorage.setItem(`swan.chat.draft.v1.${owner}.${id}`, draft);
        rows = [{ id, title, updated: Date.now() }];
      }
    } catch { /* Conversations also work without device storage. */ }
    if (!rows.length) rows = [{ id: crypto.randomUUID(), title: "New conversation", updated: Date.now() }];
    setSessions(rows);
    setActiveId(rows.some(row => row.id === selected) ? selected : rows[0].id);
    setReady(true);
  }, [storageKey, owner]);
  useEffect(() => {
    if (!ready) return;
    try { localStorage.setItem(storageKey, JSON.stringify({ sessions, activeId })); } catch { /* In-memory sessions stay usable. */ }
  }, [sessions, activeId, ready, storageKey]);
  function create() {
    const id = crypto.randomUUID();
    setSessions(current => [{ id, title: "New conversation", updated: Date.now() }, ...current]);
    setActiveId(id);
  }
  function title(id: string, text: string) {
    setSessions(current => current.map(row => row.id === id ? { ...row, title: row.title === "New conversation" ? text.replace(/\s+/g, " ").slice(0, 64) : row.title, updated: Date.now() } : row));
  }
  return { sessions, activeId, select: setActiveId, create, title, ready };
}
