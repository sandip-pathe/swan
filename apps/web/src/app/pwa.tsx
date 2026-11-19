"use client";

import { useEffect, useState } from "react";
import Icon from "./icons";

type InstallPrompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
export default function Pwa() {
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [offline, setOffline] = useState(false);
  const [ios, setIos] = useState(false);
  const [help, setHelp] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    const install = (event: Event) => { event.preventDefault(); setPrompt(event as InstallPrompt); };
    const installed = () => { setPrompt(null); setIos(false); };
    update();
    setIos(/iPad|iPhone|iPod/.test(navigator.userAgent) && !window.matchMedia("(display-mode: standalone)").matches && !(navigator as Navigator & { standalone?: boolean }).standalone);
    window.addEventListener("online", update); window.addEventListener("offline", update);
    window.addEventListener("beforeinstallprompt", install); window.addEventListener("appinstalled", installed);
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => setFailed(true));
    return () => { window.removeEventListener("online", update); window.removeEventListener("offline", update); window.removeEventListener("beforeinstallprompt", install); window.removeEventListener("appinstalled", installed); };
  }, []);
  async function install() {
    if (!prompt) { setHelp(value => !value); return; }
    try { await prompt.prompt(); await prompt.userChoice; setPrompt(null); }
    catch { setHelp(true); }
  }
  return <>
    {offline && <div className="offline-notice" role="alert">You are offline. Prices and balances cannot refresh. Trading controls need a connection.</div>}
    {(prompt || ios) && <div className="install-app"><button className="text-button" onClick={install}><Icon name="download" /> Add SWAN to your home screen</button>{help && <p>In Safari, tap Share, then Add to Home Screen.</p>}</div>}
    {failed && <p className="pwa-fallback" role="status">App installation support is unavailable. You can continue in your browser.</p>}
  </>;
}
