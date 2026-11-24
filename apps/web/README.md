# SWAN Trade frontend

Next.js app for the single-user, paper-only SWAN workspace. Vercel serves this
frontend; the API, PostgreSQL and market worker run separately on the Oracle VM.
The API must be reachable over HTTPS and configured with the exact Vercel origin
before authenticated workspace data can load. Keep paper entries paused until the
backend's existing qualification and arm gates are satisfied.

## Deploy with Vercel's web UI

1. Import the `sandip-pathe/swan` GitHub repository in Vercel.
2. Set **Root Directory** to `apps/web` and keep **Include files outside the root
   directory** disabled. This app uses only its own package and lock files.
3. Confirm **Framework Preset** is Next.js. Use `npm run build` as the build
   command; leave the install command and output directory at their defaults.
   Vercel detects `package-lock.json` and runs the corresponding npm install.
4. Add the following variables under Project Settings → Environment Variables.
   Copy the Firebase browser configuration from Firebase Console → Project
   settings → Your apps → Web app. Set them for Production and Preview only when
   those deployments should connect to the same single-user backend.

   - `NEXT_PUBLIC_FIREBASE_API_KEY`
   - `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`
   - `NEXT_PUBLIC_FIREBASE_PROJECT_ID`
   - `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET`
   - `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`
   - `NEXT_PUBLIC_FIREBASE_APP_ID`
   - `NEXT_PUBLIC_API_BASE_URL` — the backend's HTTPS origin, such as
     `https://api.example.com`, with no path suffix.

5. Deploy, then add the assigned Vercel production domain under Firebase
   Authentication → Settings → Authorized domains. Enable only the sign-in
   providers you use and keep public account creation disabled.
6. Set `SWAN_WEB_ORIGINS` on the backend to a JSON array containing the exact
   production origin, such as `["https://swan.example.com"]`. Add the exact
   Vercel preview origin only if you intend to use previews with the live
   single-user backend. Keep backend owner bootstrap disabled and bind the
   authorized Firebase UID explicitly to the existing paper account.
7. Redeploy after changing environment variables. Check sign-in, API health,
   saved records and chat only after HTTPS, Firebase UID binding, database
   restore and API CORS settings are ready.

Do not add database URLs, broker credentials or sessions, Firebase Admin keys,
OpenAI keys, or other server secrets to Vercel. `NEXT_PUBLIC_*` values are
embedded in browser JavaScript and must contain only browser-safe configuration.
The Firebase web API key is not an authorization control; backend UID checks are.

## Local development

Copy `.env.example` to `.env.local`, fill in the Firebase web app values and leave
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`. The local file is ignored by
Git. Install with `npm ci`, then use `npm run dev`. `npm run typecheck` and
`npm run build` are available for local checks.

Firebase browser configuration can be copied from Firebase Console → Project
settings → Your apps → Web app. Do not copy service-account JSON into this app.
