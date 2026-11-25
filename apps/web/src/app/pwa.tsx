"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";

type InstallPrompt = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: string }>;
};
type PwaState = {
  offline: boolean;
  installed: boolean;
  canInstall: boolean;
  ios: boolean;
  install: () => Promise<void>;
};
const Context = createContext<PwaState>({
  offline: false,
  installed: false,
  canInstall: false,
  ios: false,
  install: async () => {},
});
export const usePwa = () => useContext(Context);

export default function Pwa({ children }: { children: React.ReactNode }) {
  const prompt = useRef<InstallPrompt | null>(null);
  const [canInstall, setCanInstall] = useState(false);
  const [installed, setInstalled] = useState(false);
  const [ios, setIos] = useState(false);
  const [offline, setOffline] = useState(false);
  const [reconnected, setReconnected] = useState(false);
  const [help, setHelp] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let wasOffline = !navigator.onLine;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    const updateConnection = () => {
      const disconnected = !navigator.onLine;
      setOffline(disconnected);
      document.documentElement.dataset.offline = String(disconnected);
      if (wasOffline && !disconnected) {
        setReconnected(true);
        window.dispatchEvent(new Event("swan:refresh"));
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(() => setReconnected(false), 3500);
      }
      wasOffline = disconnected;
    };
    const installPrompt = (event: Event) => {
      event.preventDefault();
      prompt.current = event as InstallPrompt;
      setCanInstall(true);
    };
    const appInstalled = () => {
      prompt.current = null;
      setCanInstall(false);
      setInstalled(true);
    };
    const standalone = window.matchMedia("(display-mode: standalone)");
    const updateInstalled = () =>
      setInstalled(
        standalone.matches ||
          Boolean(
            (navigator as Navigator & { standalone?: boolean }).standalone,
          ),
      );
    updateInstalled();
    updateConnection();
    setIos(/iPad|iPhone|iPod/.test(navigator.userAgent));
    window.addEventListener("online", updateConnection);
    window.addEventListener("offline", updateConnection);
    window.addEventListener("beforeinstallprompt", installPrompt);
    window.addEventListener("appinstalled", appInstalled);
    standalone.addEventListener("change", updateInstalled);
    if ("serviceWorker" in navigator)
      navigator.serviceWorker.register("/sw.js").catch(() => setFailed(true));
    return () => {
      clearTimeout(reconnectTimer);
      window.removeEventListener("online", updateConnection);
      window.removeEventListener("offline", updateConnection);
      window.removeEventListener("beforeinstallprompt", installPrompt);
      window.removeEventListener("appinstalled", appInstalled);
      standalone.removeEventListener("change", updateInstalled);
      delete document.documentElement.dataset.offline;
    };
  }, []);
  useEffect(() => {
    const root = document.documentElement;
    const viewport = window.visualViewport;
    const baseline = { height: window.innerHeight, width: window.innerWidth };
    const update = () => {
      // Pinch zoom must remain accessible; it must not be mistaken for the keyboard.
      if (viewport && Math.abs(viewport.scale - 1) > 0.05) return;
      const editing = document.activeElement?.matches(
        'input,textarea,[contenteditable="true"]',
      );
      const height = viewport?.height ?? window.innerHeight;
      if (!editing || Math.abs(baseline.width - window.innerWidth) > 100) {
        baseline.height = window.innerHeight;
        baseline.width = window.innerWidth;
      }
      const keyboard = Boolean(editing && baseline.height - height > 100);
      root.style.setProperty(
        "--app-height",
        `${viewport?.height ?? window.innerHeight}px`,
      );
      root.dataset.keyboard = String(keyboard);
    };
    update();
    viewport?.addEventListener("resize", update);
    window.addEventListener("resize", update);
    document.addEventListener("focusin", update);
    document.addEventListener("focusout", update);
    const colors = () => {
      const color =
        getComputedStyle(root).getPropertyValue("--bg").trim() || "#ffffff";
      document
        .querySelector('meta[name="theme-color"]')
        ?.setAttribute("content", color);
    };
    colors();
    const observer = new MutationObserver(colors);
    observer.observe(root, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    const scheme = window.matchMedia("(prefers-color-scheme: dark)");
    scheme.addEventListener("change", colors);
    return () => {
      viewport?.removeEventListener("resize", update);
      window.removeEventListener("resize", update);
      document.removeEventListener("focusin", update);
      document.removeEventListener("focusout", update);
      observer.disconnect();
      scheme.removeEventListener("change", colors);
      root.style.removeProperty("--app-height");
      delete root.dataset.keyboard;
    };
  }, []);
  async function install() {
    if (!prompt.current) {
      setHelp(true);
      return;
    }
    try {
      await prompt.current.prompt();
      await prompt.current.userChoice;
      prompt.current = null;
      setCanInstall(false);
    } catch {
      setHelp(true);
    }
  }
  return (
    <Context.Provider value={{ offline, installed, canInstall, ios, install }}>
      {children}
      {offline && (
        <div className="connection-strip" role="status">
          Offline. Displayed records may be old. Reconnect to refresh or send
          requests.
        </div>
      )}
      {reconnected && !offline && (
        <div className="connection-strip" role="status">
          Connection restored. Saved market observations can be refreshed.
        </div>
      )}
      {help && (
        <div className="pwa-help" role="status">
          <span>
            {ios
              ? "In Safari, tap Share, then Add to Home Screen."
              : "Open your browser menu and choose Install app or Add to Home Screen, if available."}
          </span>
          <button
            className="text-button"
            aria-label="Dismiss install help"
            onClick={() => setHelp(false)}
          >
            &times;
          </button>
        </div>
      )}
      {failed && (
        <span className="sr-only" role="status">
          Offline launch support is unavailable in this browser.
        </span>
      )}
    </Context.Provider>
  );
}
