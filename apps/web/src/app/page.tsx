"use client";

import { useEffect, useState, type FormEvent } from "react";
import { GoogleAuthProvider, onAuthStateChanged, signInWithEmailAndPassword, signInWithPopup, signOut, type User } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import Dashboard from "./dashboard";

function errorMessage(error: unknown, method: "google" | "password" = "google"): string {
  const code = error && typeof error === "object" && "code" in error ? String(error.code) : "";
  switch (code) {
    case "auth/popup-closed-by-user": return "Sign-in was closed. You can try again.";
    case "auth/popup-blocked": return "Allow sign-in popups for this site and try again.";
    case "auth/unauthorized-domain": return "This domain must be authorized in Firebase Authentication.";
    case "auth/operation-not-allowed": return `${method === "password" ? "Email/Password" : "Google"} sign-in must be enabled in Firebase Authentication.`;
    case "auth/invalid-credential":
    case "auth/invalid-login-credentials":
    case "auth/user-not-found":
    case "auth/wrong-password": return "Unable to sign in with that email and password. Check your credentials and try again.";
    case "auth/invalid-email": return "Enter a valid email address.";
    case "auth/user-disabled": return "This account has been disabled. Contact the account administrator.";
    case "auth/too-many-requests": return "Too many attempts. Please wait before trying again.";
    case "auth/network-request-failed": return "Unable to connect. Check your connection and try again.";
    default: return "Authentication is unavailable. Check Firebase setup and try again.";
  }
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      return onAuthStateChanged(getFirebaseAuth(), (currentUser) => {
        setUser(currentUser);
        setLoading(false);
      }, () => {
        setError("Unable to restore your sign-in session.");
        setLoading(false);
      });
    } catch {
      setError("Firebase configuration is incomplete. Check the frontend environment configuration.");
      setLoading(false);
    }
  }, []);

  async function authenticate() {
    if (busy || loading) return;
    setBusy(true);
    setError(null);
    try {
      const auth = getFirebaseAuth();
      if (user) await signOut(auth);
      else {
        const provider = new GoogleAuthProvider();
        provider.setCustomParameters({ prompt: "select_account" });
        await signInWithPopup(auth, provider);
      }
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function authenticateWithPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || loading) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    const email = String(values.get("email") ?? "").trim();
    const password = String(values.get("password") ?? "");
    if (!email || !password) {
      setError("Enter your email address and password.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await signInWithEmailAndPassword(getFirebaseAuth(), email, password);
    } catch (cause) {
      setError(errorMessage(cause, "password"));
    } finally {
      const passwordInput = form.elements.namedItem("password");
      if (passwordInput instanceof HTMLInputElement) passwordInput.value = "";
      setBusy(false);
    }
  }

  if (user && !loading) return <Dashboard key={user.uid} user={user} onSignOut={authenticate} />;

  return (
    <main>
      <section aria-labelledby="title">
        <p className="eyebrow">SWAN TRADE</p>
        <h1 id="title">Sign in to SWAN</h1>
        <p>Follow NIFTY and SENSEX options. Practice with virtual funds.</p>
        {loading ? <p role="status">Checking your session…</p> : user ? (
          <div>
            <p role="status">Signed in as {user.email ?? user.displayName ?? "your account"}.</p>
            <p className="note">Your paper account is connected.</p>
          </div>
        ) : (
          <>
            <p>Sign in with your email and password or your Google account.</p>
            <form onSubmit={authenticateWithPassword} aria-label="Email and password sign-in" aria-busy={busy}>
              <fieldset disabled={loading || busy}>
                <legend className="sr-only">Account credentials</legend>
                <label htmlFor="email">Email address</label>
                <input id="email" name="email" type="email" autoComplete="username" autoCapitalize="none" spellCheck={false} required />
                <label htmlFor="password">Password</label>
                <input id="password" name="password" type="password" autoComplete="current-password" required />
                <button type="submit">{busy ? "Please wait…" : "Sign in with email"}</button>
              </fieldset>
            </form>
            <p className="divider">or</p>
          </>
        )}
        <button type="button" disabled={loading || busy} onClick={authenticate}>
          {busy ? "Please wait…" : user ? "Sign out" : "Continue with Google"}
        </button>
        {error && <p role="alert" className="error">{error}</p>}
      </section>
    </main>
  );
}
