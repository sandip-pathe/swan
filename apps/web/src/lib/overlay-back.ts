"use client";
import { useEffect, useRef } from "react";

// An open mobile surface occupies one browser-history step. Native Back dismisses
// it before navigating away. No request or trading action is replayed.
export function useOverlayBack(open: boolean, dismiss: () => void) {
  const dismissRef = useRef(dismiss);
  dismissRef.current = dismiss;
  useEffect(() => {
    if (!open) return;
    const id = crypto.randomUUID();
    const previous = history.state;
    history.pushState({ ...previous, swanOverlay: id }, "", location.href);
    let popped = false;
    const back = () => {
      if (history.state?.swanOverlay !== id) {
        popped = true;
        dismissRef.current();
      }
    };
    window.addEventListener("popstate", back);
    return () => {
      window.removeEventListener("popstate", back);
      if (!popped && history.state?.swanOverlay === id) history.back();
    };
  }, [open]);
}
