// Display only. Cached records must never establish current trading permission.
const prefix = "swan.display.v1.";
export function readSnapshot<T>(owner: string, name: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(`${prefix}${owner}.${name}`);
    if (!raw || raw.length > 1_000_000) return null;
    const value = JSON.parse(raw);
    if (
      value.owner !== owner ||
      !Number.isFinite(value.saved) ||
      Date.now() - value.saved > 86_400_000 ||
      value.saved > Date.now()
    )
      return null;
    return value.data ?? null;
  } catch {
    return null;
  }
}
export function saveSnapshot(owner: string, name: string, data: unknown) {
  try {
    const raw = JSON.stringify({ owner, saved: Date.now(), data });
    if (raw.length <= 1_000_000)
      localStorage.setItem(`${prefix}${owner}.${name}`, raw);
  } catch {
    /* The online view still works when storage is unavailable. */
  }
}
export function clearSnapshots(owner: string) {
  try {
    for (const key of Object.keys(localStorage))
      if (key.startsWith(`${prefix}${owner}.`)) localStorage.removeItem(key);
  } catch {
    /* Continue sign-out. */
  }
}
