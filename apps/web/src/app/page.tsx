"use client";

import { useEffect, useState, type FormEvent } from "react";
import { browserLocalPersistence, onAuthStateChanged, setPersistence, signInWithEmailAndPassword, signOut, type User } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import BotHome from "./bot-home";
import Brand from "./brand";

const accountEmail = process.env.NEXT_PUBLIC_BOT_LOGIN_EMAIL ?? "jit4xxxx@gmail.com";

function errorMessage(error: unknown): string {
  const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
  if (code === "auth/too-many-requests") return "Too many attempts. Try again later.";
  if (code === "auth/network-request-failed") return "Connect to the internet to log in.";
  if (["auth/invalid-credential", "auth/invalid-login-credentials", "auth/wrong-password", "auth/user-not-found"].includes(code)) return "Incorrect code.";
  return "Unable to log in. Try again.";
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      return onAuthStateChanged(getFirebaseAuth(), current => {
        // A restored session opens the owner's local archive without a network request.
        if (current?.email?.toLowerCase() === accountEmail.toLowerCase()) setUser(current);
        else { setUser(null); if (current) void signOut(getFirebaseAuth()); }
        setLoading(false);
      }, () => { setError("Unable to restore your session."); setLoading(false); });
    } catch { setError("Login is unavailable."); setLoading(false); }
  }, []);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || loading || !/^\d{6}$/.test(code)) return;
    setBusy(true); setError("");
    try {
      const auth = getFirebaseAuth();
      await setPersistence(auth, browserLocalPersistence);
      await signInWithEmailAndPassword(auth, accountEmail, code);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setCode(""); setBusy(false); }
  }

  if (user) return <BotHome key={user.uid} user={user} onSignOut={() => { void signOut(getFirebaseAuth()); }} />;

  return <main className="bot-login" aria-busy={loading || busy}>
    <form className="bot-login-form" onSubmit={login} aria-label="SWAN login">
      <div className="bot-login-brand" aria-label="swan"><Brand /></div>
      <div className="bot-login-entry">
        <label htmlFor="code" className="sr-only">Six-digit password</label>
        <input id="code" name="password" type="password" inputMode="numeric" autoComplete="current-password"
          enterKeyHint="go" pattern="[0-9]{6}" minLength={6} maxLength={6} required
          aria-label="Six-digit password" aria-describedby={error ? "login-error" : undefined}
          value={code} onChange={event => setCode(event.target.value.replace(/[^0-9]/g, ""))}
          disabled={loading || busy} placeholder="••••••" />
        {error && <p id="login-error" role="alert" className="error">{error}</p>}
      </div>
      <button type="submit" disabled={loading || busy || code.length !== 6} aria-label={loading ? "Restoring session" : busy ? "Logging in" : "Login"}>
        {loading || busy ? <span className="login-spinner" aria-hidden="true" /> : "Login"}
      </button>
    </form>
  </main>;
}
