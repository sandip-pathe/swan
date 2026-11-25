"use client";
import { useCallback, useLayoutEffect, useRef } from "react";

// Temporary UI position only; never account data, authority or commands.
export function useScreenMemory(
  owner: string,
  screen: string,
  contentReady: boolean,
) {
  const key = `swan.navigation.v1.${owner}`;
  const offsets = useRef<Record<string, number>>({});
  const current = useRef(screen);
  useLayoutEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(key) ?? "{}");
      for (const [name, y] of Object.entries(saved))
        if (typeof y === "number" && Number.isFinite(y) && y >= 0)
          offsets.current[name] = y;
    } catch {
      /* In-memory navigation still works. */
    }
    const previous = history.scrollRestoration;
    history.scrollRestoration = "manual";
    return () => {
      history.scrollRestoration = previous;
    };
  }, [key]);
  const remember = useCallback(() => {
    offsets.current[current.current] = window.scrollY;
    try {
      sessionStorage.setItem(key, JSON.stringify(offsets.current));
    } catch {
      /* Optional. */
    }
  }, [key]);
  useLayoutEffect(() => {
    current.current = screen;
    const frame = requestAnimationFrame(() =>
      window.scrollTo({
        top: offsets.current[screen] ?? 0,
        behavior: "instant",
      }),
    );
    return () => cancelAnimationFrame(frame);
  }, [screen, contentReady]);
  return remember;
}
