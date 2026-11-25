"use client";
import { useEffect, useState } from "react";
import { usePwa } from "./pwa";
export default function DeviceSettings() {
  const pwa = usePwa();
  const [retained, setRetained] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [storageMessage, setStorageMessage] = useState("");
  useEffect(() => {
    navigator.storage
      ?.persisted?.()
      .then(setRetained)
      .catch(() => {});
  }, []);
  async function retain() {
    setBusy(true);
    try {
      const granted = await navigator.storage.persist();
      setRetained(granted);
      setStorageMessage(
        granted
          ? "Browser protection from automatic storage cleanup is enabled."
          : "Your browser did not grant persistent storage. Saved conversations still work on this device.",
      );
    } catch {
      setStorageMessage(
        "Your browser manages storage automatically. Saved conversations still work on this device.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="device-settings">
      <h3>On this device</h3>
      <div className="device-setting-row">
        <div>
          <strong>SWAN app</strong>
          <p>
            {pwa.installed
              ? "Installed and ready to open from your home screen."
              : "Open SWAN from your home screen in its own window."}
          </p>
        </div>
        {!pwa.installed && (
          <button className="secondary" onClick={() => void pwa.install()}>
            {pwa.canInstall ? "Install SWAN" : "How to install"}
          </button>
        )}
      </div>
      <div className="device-setting-row">
        <div>
          <strong>Saved conversations</strong>
          <p>
            Stored on this device, not synced across devices. Signing out clears
            SWAN’s conversation cache.
          </p>
        </div>
        {retained === true ? (
          <span className="muted">Protected from automatic cleanup</span>
        ) : (
          <button
            className="secondary"
            disabled={busy}
            onClick={() => void retain()}
          >
            {busy ? "Checking…" : "Protect saved data"}
          </button>
        )}
      </div>
      {storageMessage && <p role="status">{storageMessage}</p>}
      <details>
        <summary>Privacy &amp; storage</summary>
        <p>
          SWAN saves a small appearance cookie, local conversations and chart
          preferences, and temporary navigation state. Firebase manages your
          sign-in. The offline cache contains only public assets; it does not
          store API responses or queue trading requests.
        </p>
      </details>
    </div>
  );
}
