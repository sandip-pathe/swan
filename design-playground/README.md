# SWAN design playground

An isolated, editable frontend concept based on [the UX brief](../SWAN-UX-DESIGN.md).
No build, framework, API keys or npm install required. Open `index.html` directly
in your browser, or serve this folder:

```powershell
cd D:\s\swan\design-playground
python -m http.server 4173 --bind 127.0.0.1
```

Then open http://127.0.0.1:4173. Stop the server with Ctrl+C.

- `index.html`: the three workspace layouts and shared panels.
- `styles.css`: tokens at the top; responsive layouts and light/dark themes.
- `app.js`: fictional fixtures, example answers and local interaction states.

## Try the journeys

1. Ask why SWAN is waiting; inspect its example evidence; open Trade.
2. Search the watchlist or switch between chart, depth and chain.
3. Review a manual paper order; submit the example; advance partial fill → full
   position → exit request → exit fill; review the result on Dashboard.
4. Change the scenario to holiday, stale prices, unavailable chat or exposure alert.
5. Stop new entries from Dashboard; attempt another preview.
6. Narrow the browser to phone size; open the full-height paper ticket.
7. Open profile preferences to compare light/dark appearance.

All instruments, prices, dates, financial results, decisions and responses are
fictional design fixtures. Nothing connects to the hosted app, AI, broker or ledger.
Refresh resets the simulation. No real credentials should be entered.

This is a visual/interaction exploration, not a full frontend or an accepted
trading workflow. The chart is schematic, not an interactive market chart engine.
Conversations are in memory, not persistent across reloads. Watchlist selection
changes labels and order inputs; the candle series is a shared schematic. News is
explicitly unavailable. Automatic task resumption and live mode are not depicted.

## Design direction

Original SWAN royal blue (#2455e6) and angular logo, on white/neutral-grey light
surfaces and charcoal dark surfaces. Native system sans typography, moderate
weights and tabular financial numerals keep it simple and readable. The original
font assets remain available with licenses in `assets/fonts` for comparison, but
the active interface now uses locally hosted Inter with native system fallbacks,
matching the real application's typography refinement. Green/editorial and blue-washed
surface treatments were rejected. This visual
correction leaves the existing layout intact; that layout is not yet approved.
Different densities support different tasks.
The skill's generic marketing-page recommendations were rejected as unsuitable.
No existing production page styles or components are imported.

Validation status and remaining owner/browser checks are recorded under D27 in
[DEFERRED-WORK.md](../DEFERRED-WORK.md). Production source remains unchanged.
