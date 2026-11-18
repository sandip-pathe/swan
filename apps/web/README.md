# SWAN Trade frontend

Firebase browser sign-in foundation. No protected portfolio or trading API exists yet. Signing in does not grant trading authorization; the backend must verify Firebase tokens and enforce the configured UID allowlist before exposing protected data or commands.

## Local setup

The workspace provides Node.js 24 LTS; activate it using the root setup instructions. Dependencies are installed and locked. In this directory run `npm.cmd ci`, `npm.cmd run typecheck`, `npm.cmd run build`, then `npm.cmd run dev`. Production build and type checking passed during setup. Live Firebase sign-in remains to be checked in the browser.

Local Firebase web configuration has been extracted from the supplied root `firebase.config` into ignored `.env.local`. `.env.example` lists the expected names. These `NEXT_PUBLIC_` values are browser configuration, not backend service-account credentials; never place private keys here.

In Firebase Console, enable Authentication → Sign-in method → Google, configure the support email, and authorize the exact development/production domains in Authentication settings. Check `localhost` explicitly rather than assuming it is authorized. Run the app at `http://localhost:3000` for development and verify sign-in, refresh/session restoration and sign-out. Firebase web config alone does not confirm provider enablement.

Official references: [Google sign-in](https://firebase.google.com/docs/auth/web/google-signin), [backend ID-token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens).

## Email and password sign-in

The login page also accepts existing Firebase email/password accounts. Enable Authentication → Sign-in method → Email/Password in Firebase Console, then add your account under Authentication → Users → Add user. Do not send the password through chat or put it in project configuration. Public registration is not provided. Passwords are passed only to Firebase's sign-in SDK and the password field is cleared after each attempt. Backend UID authorization still applies when protected APIs are implemented.

Reference: [Firebase password authentication](https://firebase.google.com/docs/auth/web/password-auth).
