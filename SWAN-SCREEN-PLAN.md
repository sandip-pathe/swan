# SWAN: clear screens, familiar trading language

Design proposal, 25 November 2026. This is the copy and interaction plan for the
next implementation pass, not a claim that these screens have been implemented.
It extends [the design brief](./SWAN-UX-DESIGN.md). The local app remains connected
to its hosted backend; this pass changes no application or backend code.

## The direction

SWAN helps someone answer four questions: What is happening? What does it mean?
What can I do? What happened after that? A person who knows trading from videos
should be able to use familiar terms while learning the reasoning behind them.
Educational background is not a proxy for intelligence. Unfamiliar software and
unexplained trading mechanics are the problems to solve.

Keep Buy, Sell, P&L, stop-loss, target, lots, expiry, CE/PE, VWAP and RSI. Explain
unfamiliar meanings beside the relevant value. Remove implementation language such
as admission, provenance, arming, assignment, reconciliation and worker heartbeat
from everyday screens. Preserve the consequences those terms represent.

The personality is calm, curious and direct. A little warmth belongs in discovery
and learning. Money, losses, permissions and failures get precise language. Prefer
“No rush. Check the idea first.” over “Send it,” “Easy money,” or forced memes.
Replace the current “Chill mode” with the clearer “New trades paused.”

Learning should feel rewarding because something makes sense. Trade volume, wins,
losses and risk-taking do not earn streaks, XP, confetti or social approval. No fake
activity feeds, fabricated agent thoughts, leaderboards or urgency counts.

## What this is based on

- Owner direction: chat first; mobile PWA first; four primary tabs; familiar broker
  charts; learning-focused autonomy; original royal blue and logo; readable Inter;
  white/charcoal surfaces; fewer boxes; real data with honest loading and freshness.
- Product authority: current requirements and accepted decisions in `__workspace`,
  including autonomous paper operation, separate explanatory chat, persistent
  records, explicit trading authority and no routine agent reports pushed into chat.
- Capability inventory: current frontend components and authenticated API contracts.
  Existing code is a functionality inventory, not the required page layout.
- UX methods: task-first hierarchy, recognition over recall, progressive disclosure,
  contextual learning, visible outcomes and preserved state after interruption.
- This is a design hypothesis. No learner interviews, comprehension results or
  usability scores are claimed. Existing single-owner access is not expanded here.

## Navigation

### Primary navigation stays familiar

| Destination | Question it answers | Icon |
|---|---|---|
| Chat | What do I want to ask or understand? | `MessageSquare` |
| Dashboard | How is my account doing, and what has SWAN done? | `LayoutDashboard` |
| Trade | What am I watching, and how do I inspect or trade it? | `ChartCandlestick` |
| Account | What are my preferences and trading limits? | `UserRound` |

Keep the mobile bottom bar and desktop sidebar. Preserve selected screen, scroll,
chart, filters and draft when changing tabs. The logo stays static. Account entry
in the sidebar stays the user's name/email without extra labels or an avatar.

### Replace the dashboard strip

Owner clarification: this strip exists inside Dashboard only. Chat, Dashboard,
Trade and Account stay in the desktop sidebar/mobile bottom bar. The standalone
review board uses a labeled area picker to browse proposals; that picker is not
proposed application navigation. Shared states are examples, not an app destination.

| Current | Proposed | Lucide icon | Destination |
|---|---|---|---|
| Overview | Overview | `LayoutDashboard` | Money, current state, important updates |
| Positions & orders | Trades | `ArrowLeftRight` | Open trades and orders |
| Decisions | Decisions | `Lightbulb` | Ideas, reasoning and outcomes |
| History & reports | History | `History` | Closed trades and daily results |
| Activity | Remove from this strip | None | Meaningful events move into the relevant story |

Desktop: 18–20px icon beside the word, neutral inactive text, royal-blue active text
and a short underline. No individual rounded button backgrounds, permanent outlines
or ornamental full-width divider. One alignment baseline across all four items.

Mobile: four equal cells, icon above a single-word label, at least 44px touch targets.
At large text sizes, allow a clearly scrollable strip rather than clipping labels.
Keep labels visible; emoji are not navigation substitutes. Bottom navigation remains
the four primary destinations, not this dashboard subsection strip.

Trades contains **Open** and **Orders**. Completed positions belong in History;
completed/cancelled order records remain available through Orders filters and the
linked trade story. No duplicate full logs on each destination.

## Shared appearance and visual vocabulary

- Original lightning logo, royal blue `#2455e6`, Inter, white and neutral charcoal.
  Dark mode separates surfaces by brightness, without blue-tinted backgrounds.
- Use spacing, alignment and typography to group content. A surface contains one
  related idea; not every label, row, explanation or error needs its own box.
- Choose one card inset per breakpoint: 28px desktop, 20px phone. Headings, body,
  disclosures and actions share the same left edge. Use natural height, not spacer
  blocks or hard-coded card heights. Dividers separate actual sibling records only.
- Body text normally 16px, supporting text 14px, financial figures 28–36px. Dense
  trade tables can be compact without tiny labels or unreadable secondary text.
- Use tabular figures, Indian digit grouping, currency units and readable dates.
  A current quote can show `10:42:08 IST`; older records show `25 Nov, 10:42 IST`.
- Keep one main action per task. Buy and Sell retain text labels; green/red alone
  never explains direction, performance or state. Blue is the product action accent.
- Lucide is the existing icon family. Primary tabs retain the agreed outline/filled
  selection treatment. Secondary tabs use the same family with colour/underline;
  do not fake filled versions of line drawings that become illegible when filled.

### Icon and emoji choices

| Meaning | UI icon | Optional editorial emoji |
|---|---|---|
| Idea / reasoning | `Lightbulb` | 💡 in a learning heading |
| Learning | `BookOpen` | 🧠 in a short lesson |
| News | `Newspaper` | 📰 in editorial content |
| Watching | `Star` / `Search` | 👀 in an optional empty-state illustration |
| Limits / checks | `ShieldCheck` | None on consequential controls |
| Time / saved data | `Clock3` | None |
| Refresh / retry | `RefreshCw` | None |
| Offline | `WifiOff` | None |
| Needs attention | `TriangleAlert` | None |
| Confirmed outcome | `CircleCheck` | None |
| Help / definition | `CircleHelp` | None |

Use emoji sparingly and decoratively, with equivalent text always present. Do not
use flames, rockets, cash showers or celebration around trading returns. Not every
heading needs an icon and an emoji together. The exact density is a visual choice
for the review board, not an accessibility substitute.

### Images

No stock photography, fake people, generic robot art or giant banners. Most of the
visual richness should come from meaningful charts, labelled prices and timelines.
Three small original SVG illustration ideas are enough: an empty watchlist with
a bookmark/star motif, an empty trade history with a simple path, and a compact
learning diagram. Use the SWAN lightning geometry as a subtle accent, not a mascot
that repeatedly interrupts the task. Illustrations appear mainly in empty states.

## Chat

### C1. New conversation

- Heading: **What do you want to understand?**
- Optional supporting line: **Ask about the market, a trade, or a term.**
- Composer: **Ask SWAN…**; accessible label **Message SWAN**; action **Send**.
- Three suggestions, shown only before the first message: **Why didn't SWAN trade?**
  (`Lightbulb`), **Explain this chart** (`ChartCandlestick`), **How is my account
  doing?** (`Wallet`, or a verified equivalent from the existing library).
- Selected contract chip shows name, strike, CE/PE and expiry with an accessible
  Remove action. It never silently changes which instrument a question concerns.
- New chat and saved conversations stay in the left drawer. No welcome dashboard,
  sessions table, provider checklist or warning footer under the composer.
- Empty-state illustration, if any, is small and disappears once conversation begins.

### C2. Conversation and answer

Answer shape when the question needs market/account evidence: a direct answer,
the relevant numbers or a small chart, then **Why?** and **Sources · {time}**.
Simple greetings do not need a chart, market lookup or a source drawer.

Keep one suggested next step when useful: **Open chart**, **View trade**, or
**Explain stop-loss**. These link to the same contract/trade while preserving chat.
Do not attach a grid of unrelated buttons to every answer. Chat remains usable
while a background account request fails.

Loading: **Working on your question…**. Only show **Checking your saved trades** or
similar phases when actual backend events support that statement. No fake thinking
trace, rotating invented work stages, model names or token counters.

Failure: **Couldn't finish this answer. Your question is saved.** Link: **Try again**.
Keep the user's message, draft and scroll position. Add **See latest reply** when
the user is reading older messages; do not pull the conversation to the bottom.

Chat is not an alternate unreviewed order-submit channel. Any future trade-intent
handoff opens the same explicit order review and existing server checks. The
existing stop-new-entries command, if surfaced, must say exactly that it stops new
entries and leaves existing trades subject to their current exit management.

### C3. Discover panel

Use **For you**, with sections **News**, **Worth a look**, and **Learn one thing**.
Retain the right-side Discover affordance; mobile opens a dismissible sheet.
News shows source, publication date and delay. Learning follows the selected topic
when evidence supports it. No fabricated personalization or automatic chat messages.
Missing live news should not occupy a permanent dead card on every screen; show
**No recent headlines available** in this panel and preserve the rest of the app.
Current data supports historical cited news; a current feed is D32.

## Dashboard

### D1. Overview

Title: **Your day at a glance.** Supporting copy only if it adds information.
The current experimental “Money. Moves. Lessons.” can remain a brand line elsewhere;
it should not consume three lines above the first useful number on a phone.

Order: **Your money** → **Right now** → **Needs attention** when relevant →
one latest decision → one contextual learning item. News is secondary. Urgent open
trade/exit issues move above learning and news. Do not make people scroll through
four empty blocks to see their current exposure.

Primary labels: **Account value**, **Today's P&L**, **Open trades**, **Available cash**.
Explain account value once as cash plus estimated open-trade value. Explain P&L as
profit/loss including the stated cost basis. If a current daily baseline is missing:
**Not available yet** / **Today's starting value hasn't been recorded.** Never zero it.
Account mode remains clear where a person acts or could mistake the money for real
funds; no repeated “Paper workspace / Virtual funds” badges.

Visuals: existing cash available/held bar with amounts; open-trade count; a concise
state row. A history-based P&L chart is a later capability, not an invented sparkline
made from arbitrary local cache samples.

State copy: **New trades paused**; **Automated trading is on** only with current
verified authority; **Waiting for a setup** only when a real reported process is
running; **Can't confirm trading status** when status is old or missing. Idle agents
must not be described as watching a live market. No worker/heartbeat table by default.

### D2. Trades: Open

Title: **Your trades**. Inner control: **Open · Orders**. Put open trades first when
there is exposure; otherwise Orders can show any pending entry without hiding Open.

Each open-trade row shows contract + expiry, remaining lots/units, entry price,
verified open P&L if available, stop-loss, target, and exit-monitoring status.
Actions: **View trade** and **Close trade** when permitted. If current valuation is
missing: **P&L needs a fresh price**. Do not compute it from unrelated last-price data.

Useful visual: an entry/stop/target price ladder, with current price only when fresh.
Levels can be offscreen; do not invent crossings or label a planned stop “guaranteed.”
Monitoring warning stays visible: **Automatic exits aren't being monitored** or
**Exit requested. Waiting for confirmation.** It is never hidden behind “Details.”

Empty: **No open trades.** / **You can explore a chart or review past trades.**
No encouragement to open a position just to fill the screen. Primary follow-up:
**Explore charts**; secondary **View history**.

### D3. Trades: Orders

Title: **Your orders**. Explain once: **An order is a request. A fill is a completed
part of that request.** Default to pending/recent orders; filters stay in a sheet.

Each row: Buy/Sell, contract + expiry, requested vs filled quantity, limit/average
fill price where available, state and time. Use **Waiting to fill**, **Partly filled**,
**Filled**, **Cancelled**, **Expired**, **Rejected**. Only map known backend states;
unknown states say **Status unavailable**, not “Waiting.”

Partial example (illustrative, not account data): **30 of 60 units filled** with a
labelled progress bar. Cancel action: **Cancel unfilled part**. Cancellation does
not undo already filled units. Amend action: **Edit order**, followed by a fresh
review. Show the effect on reserved cash/risk before confirmation.

Order acknowledgement says **Order received. Waiting to fill.**, never **Trade done**.
Uncertain result says **Checking this order… Don't submit it again yet.** Existing
command IDs/receipts determine retry behaviour; the UI must not create a second order.

### D4. Decisions

Title: **Why SWAN made that call.** Filters: **All**, **Waiting**, **Ideas**, **Checks**.
Only offer filters that map unambiguously to existing records. Keep dates available
through a Calendar control, not a full-width form above every screen.

Use one idea/story as the unit, not one card per database table. A story contains
**What it noticed → The idea → What could go wrong → What happened**. Role names:
**Market reader**, **Trade planner**, **Second opinion**, **Risk checks**. Show roles
only for stages actually recorded; missing stages say **Not recorded**.

First view: contract/market, observed time, outcome and a short supported reason.
Tap **Why?** for reasoning, **Show on chart** for actual linked data, **Sources** for
attribution. Longer original reasoning remains available. Concise rewrites must be
grounded; a frontend must not guess why an agent waited.

Outcomes: **Waited**, **Idea proposed**, **Stopped by checks**, **Order received**,
**Partly filled**, **Filled**. They are distinct facts, not a guaranteed linear
progress bar. “Review passed” does not imply “trade allowed” or “filled.”

Existing logs and strategy records cannot always be linked into one story. Do not
join them merely because their timestamps are close; keep unlinked records clearly
separate until stable identifiers support the relationship.

Empty: **No decisions saved for this view.** / **Try another date or explore a chart.**
Technical assessment/version/artifact IDs move to an operator-only view.

### D5. History

Title: **Look back. Learn something.** Date picker with **Today**, **Yesterday**,
and **Choose date**. Default is a clear daily summary, then closed-trade rows.

Show **Closed-trade P&L**, **Trading costs**, **Closed trades**, and **Trades still
open at day end** when the record supports them. Today's partial report says
**Today so far**. Cash movement is not profit; put funding/withdrawal/hold records
under **Money movements** with their correct meanings.

Each closed trade: instrument, dates, actual net result if recorded, duration and
entry/exit reason where linked. Use **Review trade** to open its story. A lesson
can be **What did the original plan expect?**, rather than praising a win or blaming
a loss. Do not infer strategy quality from one or two outcomes.

Charts: daily bars only after an authoritative series exists; actual fills on a
chart only with linked instrument/time/candles. Never interpolate missing days as
zero or create an equity curve from cash movements. Export belongs in the overflow
menu as **Download CSV**, not a large main CTA.

Empty: **No completed trades for this date.** / **Your money and settings are still
available.** No simulated achievements for “first trade.”

### D6. Trade story (detail shared by Trades, History and Chat)

Title is the contract, not an order UUID. First show **Open / Closed / Partly filled**,
the most important result and the latest verified timestamp. Then the visual story:
**Idea → Order → Fills → Exit**, using actual linked events and explicit missing steps.

Primary action depends on state: **View chart**, **Close trade**, or **Review result**.
Source IDs, raw event payloads, fee code names and execution versions are not the
default narrative. Itemized financial fees remain available under **Costs**.

## Trade

### T1. Watchlist

Top-level Trade tabs: **Options** (`ChartCandlestick`), **Watchlist** (`Star`),
**Find** (`Search`). Keep the quiet text-and-underline selected state used elsewhere.

Title: **What you're watching.** Each row: contract name, expiry, last observed
price, valid change only if a matching baseline exists, and data age. A Star toggle
says **Add to watchlist** / **Remove from watchlist** accessibly. Opening a row opens
the chart; no nested Buy action beside a tiny delete target.

Empty: **Start with one contract.** / **Save something you want to follow.** Action:
**Find a contract**. Optional small bookmark/star illustration. No AI pick presented
as a personalized recommendation when none exists.

### T2. Options / option chain

Title: **Options around this price**. Main controls: **NIFTY / SENSEX**, **Expiry**,
and a simple sort. Keep Call · CE on the left, Strike in the centre, Put · PE on the
right. Last price, bid/ask, volume and OI remain visible because they support option
comparison and execution checks; source age stays labelled per quote.
At larger widths a **More data** control exposes the familiar broker table.

ATM highlight requires a valid reference; label **Near the saved index price** when
the reference is historical. Do not auto-centre on an invented index value. If ATM
or dates are uncertain, keep neutral ordering and explain the missing reference.

Help: **CE is a call option. PE is a put option.** A tap can explain strike, expiry,
lots, OI and premium without leaving the selection. Do not reduce an option's risk
to “CE = price up = profit.” Expiry, price paid and other factors matter.

Price state belongs in a small timestamp row, not repeated warnings on every cell.
Missing quotes stay **— / No quote**; never zero. Action **Update prices** is distinct
from ordinary background reads because it may request market observations.
Add a short optional **What do bid, ask and OI mean?** explanation; keep those
definitions close to the figures rather than sending a new trader to a glossary.

### T3. Search

Heading: **Find an option**. Input: **Try a strike, NIFTY or CE / PE**.
Start with search and the NIFTY / SENSEX picker. Keep call/put and expiry behind
**Filters** until needed; show the number selected and offer **Clear filters**.

Results show readable strike values (no trailing six decimal places), CE/PE, expiry,
exchange when relevant and a watchlist star. Show **1 lot = {units} units** on detail,
not four tiny metadata strings in every result row.

No results: **No contracts match.** Actions: **Clear filters**, **Try another search**.
Expired/unlisted result: **This contract is no longer available.** / **Find another
expiry.** Never invite a retry that cannot fix the condition.

### T4. Contract and chart

First visible: contract + expiry, lot size in units, observed premium and timestamp,
then the candle chart. Indicators start off; the supported VWAP and DEMA toggles are
under **Indicators** so the chart opens cleanly.
Use labelled **Price**, **Volume**, **Indicators**, and **Details** controls instead
of exposing a professional drawing-tool rail by default.

Keep familiar candles, timeframes, VWAP, moving averages and RSI where supported.
Indicator controls expose only implemented indicators; saved settings stay put.
Each indicator has **What does this show?** with a small labelled example rather
than a paragraph pasted beneath the chart. Offer **Ask SWAN about this chart**.

Action area: **Plan a buy** for supported long-option entries; **Close trade / Sell**
only against an existing eligible holding. No decorative Sell switch implying
unsupported naked-short execution. Chart, details and order ticket share contract
identity and date; changing either invalidates the old preview.

**Depth** remains accessible through Details, with bid/ask and source age. Greeks,
unimplemented indicators and broad equity/fundamental screens are omitted until
their data and product scope exist. Stale charts are viewable but do not establish
current prices or trading permission.

### T5. Plan and review an order

Mobile bottom sheet; desktop side panel. Title: **Plan a buy**. Contract name,
expiry and account mode stay visible. Controls: **Lots**, **Entry price**, **Stop-loss**,
**Target**; below lots: **{lots} lot(s) = {units} units**. Use decimal/numeric keyboards.

Primary action **Check costs & risk**. Secondary **Save plan** only after supported
checks. Preview first shows **Cash needed**, **Cash available**, **Planned loss if stop
is reached**, and **Usable at this price**. The full fee and gross/net breakdown stays
under **See the full cost breakdown**; do not relabel a gross target as net profit.

A labelled stop/entry/target ladder makes the plan understandable. Caption:
**A stop-loss is a plan, not a guaranteed exit price.** Keep uncertain depth and
failed checks visible. Do not substitute “maximum loss” for planned stop loss.

Final step **Review paper order** → **Place paper buy order**. It explicitly names
practice/paper execution without cluttering the rest of the app with repeated tags.
Current manual trading's one-entry, one-lot and time-window restrictions must stay
visible when applicable. Display **One-entry window · {time left}** with a simple
explanation, while hiding UUIDs and implementation vocabulary. Simplification does
not remove preparation, qualification or server permission requirements.

If blocked, show the specific next useful step: **Not enough available cash**,
**Price needs an update**, **Trading hasn't been enabled**, or **Market hours aren't
confirmed**. If preview expires: **Prices or checks may have changed. Check again.**
No false Buy/Sell activation to make the sheet look complete.

### T6. Order outcome

Use a small confirmation state, not a confetti screen. **Order received** is followed
by **Waiting to fill** or the actual returned state. Show quantities filled and what
remains. Actions: **View order**, **Back to chart**. A filled response can say **Filled**
only when that is verified.

If response is unknown: **We haven't confirmed the result yet.** / **Check this order
before trying again.** Action **Check order status** uses the same stored command,
not a fresh submission. Do not promise that no order exists after a network timeout.

## Account

### A1. Account home

Title: **Account**. Identity first, followed by grouped rows:

- **Trading:** Trading limits (`ShieldCheck`), Automated trading (`Pause`/`Play` state).
- **Your app:** Appearance, Install SWAN, Saved data, Help.
- **Sign out** as a quiet but discoverable action.

Drop the technical multi-tab strip: General / Risk settings / Trading permissions /
Trial sessions. Normal users do not need a setup dashboard, connection-test grid,
API names, broker PIN fields or runtime configuration editor.

Single-owner operator maintenance remains available separately. An actual market
connection issue produces a useful message and supported recovery/help path; it is
not hidden merely because diagnostics are hidden. Do not invent a “Reconnect” flow
that the existing product cannot complete.

### A2. Trading limits

Title: **Your trading limits**. Summary: **How much can one trade risk?** and
**When should trading stop for the day?** Keep percentages with a money illustration
only when the correct reviewed baseline is known. State which baseline it uses.

Other relevant choices: **Maximum open trades**, **Hold for at most**, and
**Stop new trades before close**. Friendly minute selectors translate to the actual
stored units without expanding allowed ranges. Show technical liquidity/fill rules
in a dedicated operator view, not a casual More slider that silently changes them.

Action **Review changes**, then a before/after summary and **Save limits**. Preserve
the existing requirement to pause and resolve orders/positions before changes.
No “Low / Medium / High” risk presets without defined reviewed meanings. Changing
limits is never an immediate side effect of dragging a slider.

### A3. Automated trading

Title: **Automated trading**. One current state, its consequence and the next useful
action. Show **New entries**, **Open trades**, and any expiry/stop state that matters.

Turning on uses **Review & enable** and existing checks. While on, expose
**Pause new trades**. Separate **Close open trades** only if that action is actually
supported and reviewed. Caption when pausing: **This stops new entries. It doesn't
close your open trades.** Never equate “paused” with “all positions closed.”

If not ready: **Automated trading isn't ready yet.** Show the user-relevant reason;
route system preparation to operator maintenance. Readiness is not represented by
a fake completion percentage. Known limits and current permissions remain visible.

Controlled validation is a maintenance/qualification journey, not a normal-user
“Trial sessions” tab. If the current manual flow requires a bounded window, reveal
its real constraints at the order step without exposing raw sessions history.

### A4. Appearance, install and saved data

Appearance: **Light · Dark · Match device** with a preview. Default Match device;
keep the agreed setting location inside Account / More settings.

Install: **Keep SWAN one tap away.** Action **Install SWAN** only when supported;
otherwise **How to install** with actual platform instructions. No repeated modal.

Saved data: **Your drafts and recent data stay on this device.** State that current
conversations are device-local, not synced across devices. **Protect saved data**
requests optional browser persistence and handles refusal normally. Any **Clear
saved data** action lists what it removes and keeps unresolved order-recovery state
separate. It must not abandon a pending command or imply deleting server history.

Help: definitions, important status explanations and a supported issue-report path.
Support reference IDs can be copyable here without taking over everyday screens.
Notification controls remain absent until opt-in delivery is implemented (D31).

## Shared states, exact copy and attention

| Situation | Icon | Copy | Action / behaviour |
|---|---|---|---|
| First account read | None | Accessible “Loading your account” | Immediate geometry-matched skeleton; no text-then-skeleton waterfall |
| Silent successful update | None | `Updated {time}` | Keep data, scroll and disclosure state; no animated Refresh button |
| Saved data, request pending | `Clock3` | `Saved at {time}. Checking for updates…` | Quiet local line; figures stay visible as historical |
| Failed account update with saved data | `RefreshCw` | `Couldn't update. Showing data saved at {time}.` | Blue Retry link and Close icon; one strip, not a second stale warning |
| Failed first read | `TriangleAlert` | `Couldn't load your account.` | Retry; keep app navigation and independent Chat usable |
| Offline with saved content | `WifiOff` | `You're offline. Saved data is still here.` | Local drafts usable; trading actions remain online-only |
| Offline without saved content | `WifiOff` | `You're offline. Reconnect to load this screen.` | Do not promise an available cache |
| Last observed price | `Clock3` | `Last price · {date/time}` | No live badge or green connection dot implied |
| Open trade lacks exit monitoring | `TriangleAlert` | `Automatic exits aren't being monitored.` | Persistent relevant warning + supported help/action; not casually dismissible |
| Routine save confirmed | `CircleCheck` | `Plan saved` / `Limits saved` | Small local acknowledgement, no page modal |
| Unknown order result | `Clock3` | `Checking whether this order went through…` | Preserve command ID; no new-submit retry |

A background refresh normally needs no top strip. Use it for an interruption that
affects the person's current task. The dismissible strip remains an overlay, with
space for a small leading icon, readable sentence, blue link and Close at the end.
Text wraps on phones; Retry and Close retain usable touch areas. No full-screen
red box for a recoverable read failure. Closing the strip does not make old data fresh.

Data states, trading permission and model interpretation remain distinct. A cached
snapshot can explain the past; it cannot authorize a trade, confirm monitoring or
claim a price is current. A live clock never makes old data fresh.

## What leaves normal screens

Move worker modes, heartbeats, raw logs, setup tests, model/provider names, token
usage, UUIDs, version hashes, artifact lists, admission matrices, recovery internals,
raw JSON and validation records to operator maintenance. In normal screens, preserve
their user-relevant effect: missing prices, incomplete order, paused entries, unsafe
monitoring, unavailable analysis or a specific step needed before trading.

Do not remove event records, auditability, financial fee detail, unresolved exits,
transaction history or important constraints. This is a presentation decision,
not deletion of records or relaxation of trading gates.

## Capability boundaries and implementation order

| Work | Existing basis | Boundary |
|---|---|---|
| Navigation, plain copy, icons and disclosure | Existing components and Lucide | Can implement locally without new market access |
| Trades, status, history and account data | Authenticated workspace/portfolio/orders/report APIs | Preserve verified timestamps, gross/net meaning and command recovery |
| Saved read views across important screens | Existing bounded display-snapshot helper | Extend per owner with schema/expiry handling; never cache trading authority |
| Concise reasons | Original agent rationale / explicit reason codes | Map known codes; grounded paraphrasing needs a defined contract, not guessed text |
| Unified decision/trade story | Existing linked evidence and order references | New cross-record joins need stable IDs; timestamp proximity is insufficient |
| Current index/news feed | Not supplied by the current cited-evidence feed | D32; keep historical labels until a real current feed exists |
| Multi-day P&L/learning charts | Daily reports and existing historical data | Aggregate API/defined metrics needed; no fabricated series or arbitrary cache curve |
| Rich contextual chat cards / action handoffs | Some selected-contract context exists | Any new result/action contract needs implementation; no fake clickable promises |
| Cross-device chat and push | Not implemented | D30/D31; don't advertise them |

Implementation sequence: (1) navigation/shared copy/status strip, (2) Trades and
order lifecycle, (3) chart/search/options/order ticket, (4) Decisions/History stories,
(5) Chat/Discover, (6) Account/limits/automation. Each slice includes loading,
saved/old, empty, failure, partial and unknown-result states as applicable. Data
effects matter more than a polished happy-path screenshot.

## Review before calling it done

Use synthetic scenarios first, then authorized real-device/user review. A learner
should be able to distinguish an idea, an order and a fill; identify CE/PE, expiry,
lots and fees; explain planned risk without believing the stop is guaranteed; find
why a trade did not happen; tell old data from current data; and predict what Pause
does to open trades. These are evaluation tasks, not results already achieved.

Visual acceptance includes 320/390px phones, landscape, desktop, large text,
light/dark, keyboard and native Back. No icon/text overlap, no orphaned Refresh
actions, no double alerts and no card with missing side insets. Inspect populated,
empty, stale, blocked and partial-fill states, not just screenshot dimensions.

## References and limits

- [GOV.UK content design](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/plan-manage-content/understand-content-design/): organise information around the person's task and reduce redundant content.
- [NN/g progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/): put secondary complexity behind meaningful requests for detail; this is not permission to hide consequences.
- [Apple tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars.md): stable destinations, visible labels and appropriate icon/label layouts. Adapt the principles for this PWA rather than pretending it is native UIKit.
- [Lucide](https://lucide.dev/icons/lightbulb): existing icon family; proposed export names were checked against the installed package. The current website redirects `History` to `rotate-ccw-clock`; the installed `History` export remains available.

The UI skill's automatic design-system results were not used: one suggested a
children's education style and the retry suggested a finance marketing page.
Neither fits this trading workspace. The approved SWAN brand and the task-specific
guidance above take precedence. Icons, imagery and exact tone remain proposals
for this review; no usability claim follows from a skill recommendation.
