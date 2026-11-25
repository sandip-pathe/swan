# SWAN UI and UX design

Cross-screen proposal, 25 November 2026: [screen, copy and icon plan](./SWAN-SCREEN-PLAN.md)
and [interactive review board](./design-playground/screen-plan.html). This proposes
plain-language journeys across Dashboard, Trade, Chat and Account, including the
four-item Overview / Trades / Decisions / History dashboard strip. It is the
brainstorming artifact requested after the dashboard experiment, not an implemented
or usability-validated replacement for every screen. Proposed changes remain
distinguished from accepted product constraints and actual backend capabilities.

Native PWA behavior contract, 24 November 2026 (implemented locally; installed-
device acceptance remains D28):

- Chat owns its scroll region. Composer remains reachable above the keyboard; tabs
  yield space while editing. Restore reading position and drafts. An incoming reply
  must not pull the reader away from earlier content; provide Jump to latest.
- Tabs preserve screen context: scroll, filters, selected contract and chart view.
  Native Back dismisses a mobile drawer/sheet before leaving its underlying screen.
  Touch targets and safe areas remain; essential actions never depend on hover.
- Account > More settings provides installation, optional saved-data protection and
  privacy/storage information. Native browser form controls and progressive browser
  APIs are preferred where their behavior fits. Installation/persistence outcomes
  depend on the browser; denial leaves normal use available.
- Appearance cookie contains only the chosen theme; conversations remain owner-
  scoped device storage and temporary positions/filters use session storage. Broker
  secrets and API credentials are never placed in preference cookies. Existing
  authenticated command/recovery state is distinct from disposable UI state.
- Offline state preserves the open UI/draft and clearly marks stale data. Trading
  requests are not queued, current buying power is not inferred from old snapshots,
  and reconnect revalidates account data. Public offline launch is a fallback screen;
  authenticated HTML and API responses are not service-worker cached.
- Short drawer/sheet motion respects reduced motion. App/status-bar theme and launch
  shortcuts enhance supported browsers; physical installed-device checks remain
  necessary. Backend latency is D29; server sessions D30; planned push/private offline
  extensions D31. None is implied complete by the local native-feel implementation.

Browser references: [VisualViewport](https://developer.mozilla.org/en-US/docs/Web/API/VisualViewport),
[optional persistent storage](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/persist),
[History API](https://developer.mozilla.org/en-US/docs/Web/API/History/pushState).

Mobile PWA tab contract: exactly four equal-width bottom tabs, Chat, Dashboard,
Trade and Account. Stable labels and icons remain visible, with account settings
under Account. Icon accents are purple/royal-blue/teal/amber respectively, adapted
for light/dark contrast; text remains neutral and selection is also indicated without
relying only on color. Bottom safe-area spacing stays part of the fixed bar.

Mobile-first PWA navigation, 24 November 2026: prioritize touch screens. The left
sidebar becomes a dismissible navigation/history drawer on mobile, with a visible
44px close target, backdrop, focus containment and safe-area spacing. Desktop close
is a quiet cross at top-right above the wordmark, visible on hover/keyboard focus;
a collapsed sidebar has an explicit reopen control. Conversation selection is an
edge-to-edge square tint, not an outlined/rounded action button. Keep text inset for
readability; remove outer row inset and gaps. No essential touch action depends on
hover. Physical installed-PWA acceptance remains required.

Conversation-session correction, 24 November 2026: Chat supports multiple
conversations listed in the left sidebar. New conversation preserves existing
threads; each has its own draft, history and pending reply. A first-message title
identifies it. Mobile provides a conversation picker. Current local implementation
stores these on the device under the signed-in owner and clears them at sign-out;
server persistence/cross-device restoration remains D30. Backend greeting latency
and failure recovery are tracked separately as D29 and are not solved by UI states.

Account and context refinement, 24 November 2026: bottom-left account entry shows
only the signed-in name or email, with no generic workspace subtitle or account
icon. It opens Account & workspace. Theme buttons belong under More settings there.
The right panel is Discover: news, insights, learning and relevant platform features;
account settings and appearance controls do not belong there. Remove redundant
Paper workspace / Virtual funds tags; preserve explicit paper-order semantics at
action points. Wide layouts reserve space for the panel; compact layouts use a
dismissible overlay. Unavailable headlines stay explicit until their source is wired.

Agreed direction: 24 November 2026. Paper design only; no application implementation is claimed.

Implementation checkpoint, 24 November 2026: user approved the refined playground
and requested migration into the real app. Local frontend now implements the three
workspaces with existing authenticated services and permission controls. Body and
support text use self-hosted Inter, chosen for readability and its leading use in
[this bounded top-site body-font study](https://www.markstudios.com/research/website-fonts-study),
not a universal most-used-font claim. Neutral white/charcoal and original royal-blue
branding remain. See D28 and RESUME for local evidence and remaining hosted acceptance.
Earlier design-only statements describe that phase, not current implementation status.

**Review status: behavioral design brief v1 complete, 24 November 2026.** Product
decisions from the user are distinguished from recommended defaults. Visual
exploration, owner usability validation and deployed acceptance remain unverified.
This document specifies design intent; it does not authorize implementation or
trading. The old application pages are not the baseline.

**Layout exploration:** [design-playground](./design-playground/README.md) is a
separate editable HTML/CSS/JS concept created after this brief review. It has
fictional records, no service connections and no production app changes. Its
bounded local Chrome layout/interaction verification is recorded under D27;
owner usability acceptance and deployed integration remain open.

Read in this order:

1. [Product, scope and principles](#product-and-scope).
2. [Information architecture](#agreed-information-architecture) and the three surface descriptions.
3. [Resolved design defaults](#resolved-design-defaults).
4. [Behavior contracts and recovery](#behavior-contracts-and-recovery).
5. [Source traceability](#source-map-and-precedence), [backend blueprint](#backend-to-experience-blueprint) and [implementation gates](#handoff-gates-by-implementation-slice).
6. [Acceptance criteria](#observable-acceptance-contracts) and [verification plan](#verification-plan-and-remaining-boundaries).

This revision supersedes the earlier Assistant / Markets / Trading / Journal navigation proposal. The agreed primary destinations are **Chat, Dashboard, Trade**. The direction comes from the product discussion and supplied Claude/Angel One screenshots; it is not governed by a generic skill-generated layout.

## Product and scope

### Visual identity correction: original SWAN branding

Latest refinement supersedes the tinted-surface and font direction below: use the
original royal blue `#2455e6` selectively on white backgrounds, with neutral grey
support surfaces. Dark mode uses charcoal surfaces with luminance separation,
off-white text and readable secondary text; avoid navy/blue-washed backgrounds.
Use a clean native system sans stack (SF on Apple platforms, Segoe UI on Windows),
moderate heading weights and tabular numerals rather than pervasive monospace.
Original logo retained. This is an appearance refinement only; no layout approval.

Explicit user direction, 24 November 2026: reuse the main application's blue
visual identity and original angular SWAN logo. The green/editorial playground
direction is rejected. Use the original IBM Plex Sans interface typography and
IBM Plex Mono for appropriate financial figures; remove serif display headings.
Core light-theme tokens: accent `#2455e6`, background `#f5f6fa`, ink `#172033`,
muted `#627086`, border `#e3e7ef`, soft blue `#edf2ff`, white surfaces.
Dark appearance uses corresponding blue/navy tokens rather than green surfaces.

This is an explicit exception to the clean-slate styling instruction below:
retain the existing brand assets, not the existing page layouts. The playground
layout has not been approved, and this correction changes colours, fonts and logo
only. Layout evaluation remains a separate next step.

### Clean-slate design instruction

Ignore all current application pages as design constraints. Do not inherit their
navigation, page boundaries, component arrangement, card styles, typography,
wording or information hierarchy. Design from the accepted vision, user tasks,
authoritative backend capabilities and state contracts. Existing pages may be
consulted later only to inventory functionality and plan migration; they are not
the visual or interaction baseline. This does not authorize deleting code.

Chat / Dashboard / Trade remains the agreed starting architecture because it was
chosen in product discussion, not because it matches the current pages. Existing
illustrative prototypes are disposable hypotheses, not approved final designs.

### Practical design rules and review criteria

Use principles as decision tools, not a requirement to apply every named UX law.
Prioritize task success, evidence clarity and safe action over aesthetic trends.

| Principle | SWAN design rule | Review question |
|---|---|---|
| Task-first hierarchy | One clear next action for the current task; supporting actions have lower emphasis | Can the user identify what to do without scanning every panel? |
| Recognition over recall | Display selected contract, side, lots, account mode and relevant context at the point of action | Does the user need to remember information from another screen? |
| Choice and cognitive load | Group related controls; disclose advanced settings on demand; avoid redundant navigation | Is every visible control useful at this moment? |
| Target acquisition and thumb reach | Put frequent mobile actions within comfortable reach; make touch areas generous; separate opposing actions | Can the task be completed one-handed without accidental activation? |
| Spatial consistency | Keep navigation, composer, selected instrument and contextual action placement predictable | Does the user have to relearn the same action across destinations? |
| Gestalt grouping and visual hierarchy | Use proximity, alignment, spacing and typographic emphasis before adding containers | Do grouping and reading order explain relationships without excessive cards? |
| System visibility | Give prompt local acknowledgement and real progress; resolve waits into outcomes | Is the user waiting for a known task or staring at an unexplained spinner? |
| User control and recovery | Preserve drafts and context; provide Back, dismiss and supported cancellation; distinguish their effects | Can the user recover without repeating work or duplicating an order? |
| Error prevention | Validate lots/units, mode and current authority; revalidate expired previews | Could a plausible interaction submit the wrong intent? |
| Progressive disclosure | Lead with consequence and concise reason; make supporting evidence accessible | Are we hiding essential exposure information or exposing irrelevant machinery? |
| Honest data presentation | Distinguish observed, derived, estimated, stale, missing and illustrative values | Can the user tell what a number means and when it was observed? |
| Attention management | Reserve persistent global alerts for consequential conditions; keep routine feedback local | Does the alert compete with something more urgent? |
| Accessibility | Keyboard operation, visible focus, semantic labels, readable contrast, zoom/reflow and non-colour status cues | Can someone complete the same journey without a pointer or colour perception? |
| Motion and stability | Reserve space during loading; avoid shifting prices, news and buttons while reading; honor reduced motion | Does feedback clarify change without interrupting the task? |

Mobile targets should normally provide at least 44 × 44 CSS pixels of touch area.
This is a SWAN ergonomic target, not the WCAG AA minimum: WCAG 2.2 target-size
minimum uses 24 × 24 CSS pixels with defined exceptions. Review actual spacing,
reach and device behavior rather than treating one dimension as proof of usability.
See [W3C target-size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum).

Keep focused controls visible above sticky navigation, composers, sheets and the
software keyboard; restore focus after dismissing overlays. See
[W3C focus-not-obscured guidance](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum).

Use a deliberate spacing/type system, comfortable chat reading width, tabular
financial figures and explicit semantic colour. Trade may be dense without using
tiny text or tiny hit areas. Avoid fixed-height assumptions that break with larger
text. Charts and dense data tables need their own accessible navigation and readable
alternatives rather than being squeezed into a phone viewport.

Latency is part of UX: acknowledge input locally, avoid unrelated work for simple
requests, and show genuine progress for longer operations. Feedback does not excuse
slow execution. Measure actual hosted latency before setting service promises;
[NN/g response-time guidance](https://www.nngroup.com/articles/website-response-times/)
provides perceptual context, not an SLA for SWAN.

Apply these checks to complete journeys across desktop/mobile and normal, empty,
loading, partial, stale, offline, failed and active-exposure states. Compliance and
visual polish do not replace owner task walkthroughs.

SWAN is a learning-focused autonomous trading application for personal use. Chat is its main home. A familiar dashboard and trading workspace let the user inspect evidence, understand performance, and trade manually. Agents, workers and APIs support the experience without becoming its navigation structure.

Current execution is paper-only. The conversational assistant and autonomous trading system remain distinct. A conversation, research task, trade proposal, order submission and fill are different events. User-facing simplicity must preserve these distinctions and existing permission gates.

Do not expand trading instruments or add strategy cards merely to fill the new design. Angel One is a spatial and interaction reference; its screenshots are not evidence that every displayed feature or data field is available through our integration.

## Agreed information architecture

| Destination | User intent | Contents |
|---|---|---|
| Chat - index/home | Ask, learn, research, request work | Conversations, contextual answers, meaningful task feedback; optional wide-screen context |
| Dashboard | Understand my money and what SWAN is doing | Account performance, positions needing attention, autonomous activity, recent trades/decisions, deeper history |
| Trade | Inspect markets and trade manually | Watchlist/search, charts, instrument overview, option chain, depth, contextual order ticket, orders/positions |

Orders, positions, strategies, history and performance are contextual tabs or views rather than seven equal top-level destinations. Dashboard and Trade may show the same position for different purposes: portfolio consequence versus instrument/action. Both open the same underlying record and timeline.

Account preferences belong under the profile menu. Remove Account Connections/provider diagnostics from the everyday user application. API keys, provider tests, model checks, worker heartbeats and implementation IDs belong in operational tooling, not the normal navigation.

Desktop navigation should remain compact. Chat additionally has a collapsible conversation sidebar with New chat and history. Trade gives screen space to the chart and supporting panes. On mobile, use the same three destinations in bottom navigation and show supporting panes as tabs or sheets.

## Chat: a modern conversational home

Use the conversational proportions and behavior of ChatGPT/Claude: a readable central message column, persistent composer at the bottom, conversation history in a collapsible sidebar. Avoid a chat form inside an oversized dashboard card, a full-width Send bar, or permanent paragraphs explaining internal capabilities.

New chat starts quietly: a short invitation, the composer and a few useful optional suggestions. Do not force a daily briefing or account dashboard into the message column. Returning users can resume a conversation or start another explicitly. Account preferences and history controls should not crowd the composer.

Composer: multiline input, compact Send control, Enter to send, Shift+Enter for a new line, preserved drafts, visible busy/cancel state, and accessible keyboard controls. Do not add attachments, voice or tools unless implemented and useful.

On sufficiently wide screens, offer a collapsible contextual side panel:

- Indian market brief: index summary and session state, with actual observation times.
- Worth reading: a small relevant selection of news with publication times and delay/source information.
- Learn next: material tied to questions, instruments and recent decisions rather than generic articles.
- SWAN activity: real work in progress or a meaningful waiting state.

The panel is optional, stable while reading and absent when space is limited. News does not continually shift the conversation or masquerade as fresh when delayed. At narrower desktop widths, offer a drawer instead of squeezing the message column.

Messages support readable prose, instrument links, compact tables and contextual result cards. Relevant evidence appears behind Sources or Details, with market-data time separate from answer-generation time. Generic educational answers do not need invented market citations. No fabricated agent activity or model chain-of-thought.

### Request feedback and speed

A greeting should not trigger account, news and market research. Route work according to the request. Streaming helps perception but does not excuse unnecessary processing or a two-minute greeting.

| Situation | Experience |
|---|---|
| Message submitted | Show it immediately and acknowledge receipt |
| Simple conversation | Respond without unrelated tool work |
| Account question | Actual phase such as Reading your paper account |
| Research request | Task card with genuine phases, progress, cancellation and eventual result |
| Longer task | Conversation stays usable; task continues separately when the runtime supports it |
| Timeout/failure | Error attached to the message, preserved input and Retry |
| Partial result | Clearly identify what completed and what is unavailable |

Feedback must reflect actual state; never run a decorative sequence of fake research steps. Distinguish canceling generation from canceling a submitted task or order. Do not promise background continuation if the backend cannot resume it.

### Learning within the task

A concept on a chart, a rejected plan or a completed trade can lead directly to an explanation. Examples: Explain this indicator; Why was this entry rejected?; What did this trade teach us? Offer depth progressively. Do not turn every short answer into a lesson.

An explanation should distinguish observations, interpretation and uncertainty. A plausible-sounding explanation must not replace the recorded reason for an agent action. Learning should help the user develop judgment rather than imply predictable daily profits.

### Requests to act

The intended chat can request research, analysis and permitted trading workflows. It is not limited to questions. Current chat execution capability must be represented truthfully: link to an existing action when direct execution is unavailable. Proposed future execution uses a structured plan and the applicable permissions, not hidden side effects behind conversational wording.

Actions that move money or alter exposure must remain explicit. Do not require a separate manual confirmation for every autonomous action already authorized by the account mandate, and do not let chat silently widen that mandate.

## Dashboard: how are we doing?

Prioritize:

1. Paper equity and P&L for the selected period.
2. Open positions and anything needing attention.
3. What the autonomous system is actually doing, waiting for or unable to do.
4. Recent trades and decisions with readable explanations.
5. Deeper history, strategy performance and reports on demand.

Equity, cash and available buying power are different. Explain restrictions contextually rather than making available funds the headline account value. Never replace unavailable figures with zeros. Charts and comparisons require real dated evidence.

Today / selected period / all-time labels must be unambiguous. Empty states explain the situation: no trades because of a holiday, no entries authorized, no qualifying setup, or failed evaluation are different outcomes.

Activity shows meaningful milestones, not heartbeats. Identify whether an action came from the user or autonomous system. A trade detail timeline joins its decision, order, fills, exit and net result. Fee assumptions remain accessible beside net P&L instead of dominating every page.

Strategies show only what exists: what the strategy looks for, when it can operate, its last actual evaluation, and why it is waiting. The present ORB window must not appear as active afternoon scanning. Human/agent comparison appears only when actual comparable sessions exist.

## Trade: familiar spatial relationships

Use Angel One's useful layout relationships while keeping SWAN's own identity:

    Watchlist / search | Chart / instrument overview | Context tools
                       |                             | Depth / option chain
                       |                             | Positions / orders

The chart is the main surface. Watchlist/search can collapse. Context tools open the relevant pane rather than duplicating entire screens. Instrument selection, chart timeframe and watchlist survive navigation.

Selecting a watchlist item opens its instrument; selecting an option-chain row opens that contract; selecting a position opens the corresponding chart and actions. Orders and positions use the same records as Dashboard.

Order tickets open next to or over the instrument context and preserve the chart. Distinguish instrument, side, quantity/lots, order type, price, protection, estimated costs/risk and resulting submission status. Use paper-specific action labels and keep Paper mode visible.

For an agent-generated plan, display its existing supported levels and rationale. Do not force the user to invent stops and targets to make an autonomous proposal usable. Manual trading can intentionally expose editable values. Missing required levels are an actionable failure, not an invitation to invent AI defaults.

Do not reproduce unsupported SIP, GTT, delivery products, equity execution, multi-leg baskets or strategy catalogs simply because the reference broker offers them. Avoid duplicated navigation, excessive icon rails and repeated tab stacks.

VWAP and DEMA belong in chart overlays with readable legends. Explain the instrument and data used. Indicators do not inherently establish an exit or guarantee a good trade. Show unavailable volume/history honestly. Use readable formatting such as SENSEX 64,600 CE, Lot 20 and Tick ₹0.05 rather than raw decimal precision.

## Connect the experiences

The three destinations share objects and selections:

- Ask SWAN about this from a contract, chart, position, news item or trade opens a conversation with that context visibly attached.
- Open chart / View trade / View position in chat opens the same object in Trade or Dashboard.
- Context survives switching and can be removed from the composer explicitly.
- Attaching an object should retrieve bounded current evidence; do not silently send an entire account history or stale transcript.
- Switching destinations does not lose drafts, active tasks or instrument selections.

This continuity matters more than adding more pages. A docked conversation in Trade is a candidate interaction, not a mandatory permanent third pane.

## What to abstract, and what to disclose

Hide provider configuration and routine machinery during normal operation. Surface consequences at the point of use:

| Internal condition | User-facing consequence |
|---|---|
| Backend unavailable | Couldn't refresh; show last saved time, or unavailable if no saved result |
| Broker authentication failure | Current prices unavailable; automatic reconnect/login state when known |
| Market holiday | Market closed for the named verified holiday; saved charts and learning remain usable |
| Old quotes | Last-session prices, with actual observation time |
| Entry permission missing | Paper trading paused, with a route to the relevant setup decision |
| Agent task failure | Task could not complete; clear recovery and any partial result |

Remove the generic Monitoring connected banner and the provider-test checklist. Do not replace them with another permanent diagnostics strip. A small market/data label is enough in normal use; relevant failures become specific contextual notices. Paper mode remains visible.

Backend connection, broker sign-in, fresh data, autonomous task state and execution permission are separate facts. Never infer one from another. A successful fetch does not update the apparent age of the underlying quote. A successful provider smoke test is not proof that chat or a live feed works.

State-dependent actions need honest semantics: Pause new entries does not close positions; preview is not submission; acceptance is not a fill; stop generating is not cancel order. Keep operational IDs behind details/support references.

## Shared interaction and presentation rules

Loading is local to the affected component. Keep existing usable content and navigation interactive. Use stable skeletons for initial content, restrained refresh indicators for existing data, and informative progress for long tasks. Deadlines must resolve to results, partial results, cancellation or recoverable errors.

Empty, loading, stale, disconnected and failed are separate states. No infinite spinner, no silent fixture fallback and no zero balance replacing a failed request. Use actual error evidence before naming a provider as the cause.

Chat is calm and spacious; Trade is deliberately denser; Dashboard balances summary and detail. One uniform card layout is unsuitable for all three. Readable labels, tabular money values, Indian number grouping, consistent dates and explicit IST time labels. Maintain keyboard access, visible focus, accessible status feedback and touch targets. Use green/red with signs and text, never colour alone.

Exact palette, typography and decorative treatment remain for visual design. The v1 default follows system appearance with an override (DD-07). Do not mistake a theme change for UX repair. The immediate design priority is structure, continuity and truthful feedback.

## Current screen disposition

| Current surface | Proposed disposition |
|---|---|
| Home overview / portfolio | Dashboard account summary and performance |
| Chat form | Replaced by conversational Chat home |
| Markets search/watchlist/chain | Integrated Trade workspace |
| Orders / positions | Trade tabs and Dashboard summaries; shared detail views |
| History / daily report | Dashboard history/performance drill-down |
| Strategy intelligence / agent activity | Dashboard activity and strategy detail; contextual chat cards |
| Account Connections / provider checks | Removed from normal product navigation; operational tools |
| Qualification / validation / permission forms | Consolidated relevant paper setup; gates preserved |
| Unimplemented capabilities | No empty top-level screens or pretend controls; retain as future product scope |

This is a proposed consolidation, not authorization to delete underlying functionality or evidence.

## Resolved design defaults

These are the designer's selected v1 defaults, not claims of owner preference or
observed usability. They settle routine decisions for the next visual pass and
supersede earlier exploratory wording wherever it differs.

| ID | Selected behavior | Alternative / tradeoff | Evidence and revisit condition |
|---|---|---|---|
| DD-01 | Context panel closed on first Chat visit; visible Context action opens it; remember the choice locally | Default-open briefing improves discovery but crowds the requested quiet conversation | User's chat-first direction; revisit if relevant context cannot be found |
| DD-02 | Dashboard leads with paper equity, selected-session net P&L and open exposure; critical exposure incidents appear above metrics | Leading with buying power emphasizes order entry while obscuring overall account result | Existing reconciled accounting and supervision job; revisit in owner task review |
| DD-03 | Trade assistant opens in a contextual drawer; optional dock only when chart and controls remain usable | Permanent split view offers comparison but consumes chart space | Chart-first workspace and occasional explanation; revisit if frequent back-and-forth loses context |
| DD-04 | Mobile order ticket uses a dismissible full-height sheet with persistent contract/mode summary and reachable review action; desktop uses a side panel | Stacked ticket is simple but separates action from chart; short bottom sheet struggles with keyboard and errors | One active mobile task with generous targets; verify on phone and with larger text |
| DD-05 | Current chat answers and links to evidence; separate explicit session-stop control; no conversational order/risk/arm mutation | Broader conversational execution is future capability requiring new contracts | Current product permissions and actual endpoint boundary; revisit only after separately specified capability |
| DD-06 | Trade shows search/watchlist, chart/studies, overview, depth/chain and supported paper actions; no parity catalog | Copying every broker tab gives familiarity but creates unsupported promises | Backend field/capability inventory; add only for an accepted task with real data |
| DD-07 | Theme follows system preference with profile override; restrained neutral surfaces and semantic accent | Fixed dark or light theme imposes one viewing preference | Recommended reversible default; final typeface/palette require visual exploration |
| DD-08 | A contextual action opens shared object detail with a stable identity and a return path; browser Back restores prior context | Separate duplicate screens are easy to build but drift in status and meaning | Shared-record requirement; verify direct-link, missing-object and back behavior |

Do not reopen these defaults merely to begin visual work. Change them when owner
feedback, task failure, accessibility findings or implementation evidence warrants it.

## Behavior contracts and recovery

### Roles, objects and entry paths

Only the authenticated owner can view private account records or invoke permitted
paper controls. Operator setup is outside ordinary product navigation. The worker
is an independent actor, not a chat participant. No public/multi-user onboarding
or real-money authority is introduced by the design.

| Object | Entry and relationship | Missing, stale or denied behavior |
|---|---|---|
| Instrument | Search/watchlist/chain → Trade; linked by stable identity, not display name alone | Explain expired/unavailable contract; offer eligible search; never silently replace it |
| Decision / strategy assessment | Dashboard activity or chat citation → shared detail → source instrument/records | Preserve recorded version/time; distinguish no decision from inaccessible evidence |
| Order / fill | Trade list, Dashboard or chat link → shared timeline → related position | Show only confirmed quantities/events; unknown outcome remains unresolved |
| Position | Dashboard exposure or Trade → detail/chart → permitted exit | Show remaining units and current verification; deleted/not-owned records reveal no private content |
| Session report | Dashboard date/period → reconciled report → decisions/trades | Differentiate no records, missing baseline and failed fetch; never render a zero-result substitute |
| Conversation | Chat history or contextual Ask SWAN → bounded local conversation | Label history as this-device storage; reload does not promise a resumable AI task |
| Account mandate | Dashboard entry-state action or profile preferences → saved limits and setup status | Read current policy/authority; editing is separate and uses existing restrictions |

Direct links authenticate before showing private content, retain only the intended
object destination and recheck ownership. Sign-out removes sensitive content and
account-scoped local state. A missing/deleted object offers a return route rather
than a blank page. No new cross-device conversation storage is assumed.

### Interface contracts

All controls must have visible or accessible names, correct role/state, keyboard
operation and visible focus. Open a modal sheet with focus inside it; provide a
named Close action and return focus to its trigger. Nonmodal panes do not trap
focus. Announce meaningful status changes without reading every price tick.

| Contract | Trigger, controls and validation | State, persistence and completion | Failure / recovery / responsive rule |
|---|---|---|---|
| IC-01 Chat | Owner enters nonempty message; Send submits once; context chips removable before send | Show submitted message immediately; pending then complete/failed; no financial side effect; retain per-conversation draft and bounded history on this device | Attach failure to request; preserve input; explicit Retry. New draft stays editable while pending; no parallel generation promised. Composer stays reachable above keyboard |
| IC-02 Context and sources | Ask SWAN visibly attaches object identity and timeframe; Sources opens relevant records | Retrieve only authorized bounded evidence; source observation time separate from answer time; return to same selection | Missing evidence stays explicit; source link is not proof of claim correctness. Manual clarification can remove/change attachment |
| IC-03 Search/chart | Search and supported filters; selecting result updates shared contract/timeframe | Loading local to chart; preserve last selected contract across navigation; ignore superseded responses | Clear no-results state and reset-filter action; gaps stay gaps; chart has readable OHLC/value alternative and supported non-drag controls |
| IC-04 Paper ticket | Side/contract/lots, supported type, protection, costs and mode visible before preview; validation beside fields | Editing material intent invalidates preview; review summarizes actual units, risk estimates and resulting intent; explicit Submit paper order | Preserve intent after rejection; no auto-submit after reconnect; sheet grows/reflows with text and keyboard; chart context returns on close |
| IC-05 Order/position | Open persisted timeline; only supported cancel/amend/exit controls under current authority | Submission pending → known order state → actual fills → remaining position; no optimistic filled/closed state | Unknown outcome resolves by persisted identity before retry. Cancel/exit acknowledgments are not fills; show rejected/partial outcomes individually |
| IC-06 Stop new entries | Explicit Stop new entries today action with concise scope explanation; audited command | Pending until server confirms session stop and effective scope; existing position monitoring remains separate | Failure retains previous confirmed state. No one-click resume/arm invented; changed authority follows existing preflight. Don't bury this control in provider setup |
| IC-07 Dashboard/review | Choose session/period; inspect metric breakdown, activity or trade | Numbers reconcile to saved records; valuations carry separate age; result links preserve period and return position | Component-level retry; unavailable partial total cannot masquerade as complete. On narrow widths show priority measures sequentially, not a shrinking metric grid |
| IC-08 Preferences/access | Profile contains appearance and relevant account/risk settings; sign-in/out has explicit progress/result | Theme local; saved account policy server-owned. Risk editing respects paused/flat and revision constraints of existing endpoints | Sign-in failure retains safe destination; expired identity requires reauth; no offline mutation queue or retained preview authority |

Browser-local state is not authoritative trading state. Drafts and selections may
survive navigation and reload on the same device; clear them on sign-out. Do not
store credentials, tokens, full account snapshots or complete raw tool evidence in
these preferences. Treat migration of existing local conversation history as an
explicit frontend compatibility check, not an implicit promise.

### State and transition contract

| Flow | Allowed user-visible transitions | Completion and exception boundary |
|---|---|---|
| Read / account refresh | Initial → loading → available / partial / empty / failed; available → refreshing → fresh or saved-stale | Saved content retains actual age. If safely retaining data is not supported, show unavailable; never invent an offline cache |
| Chat | Draft → submitted/pending → answer / incomplete / failed; explicit retry creates a known new attempt | No streaming indicator or cancel-generation promise without backend support. A local abort stops waiting; it does not prove server cancellation |
| Manual entry | Editable intent → preview → submitting → accepted/working → partial/full fill, rejection, cancellation or expiry | Server decides valid transitions. A partial fill creates exposure even if the remainder cancels; plan/order/position are separate objects |
| Exit / amendment | Requested → acknowledged or rejected → tracked execution / unresolved outcome | Do not remove position on request. Amendments follow existing replacement/race contract; unsupported editing has no control |
| Session stop | Confirmed prior state → stop pending → confirmed scoped stop or failure | Repeat safely through existing audited identity; do not equate pause with liquidation or qualification with arming |
| Autonomous work | Observing, evaluating, waiting, rejected, expired or failed, overlapping with position management | Only real persisted jobs yield job progress. Strategy setup is not an order; unknown data is not a valid WAIT conclusion |

No special undo for a fill exists. Canceling a working order, exiting exposure and
editing an unsubmitted draft have different consequences and labels. Critical
exposure alerts remain visible when switching screens; acknowledgment may record
that they were seen but cannot turn an unresolved risk into a resolved state.

### AI interaction contract

AI assists with interpretation and learning using authorized market/account/news
records. It cannot expand its mandate through a prompt. Routine autonomy never
depends on keeping Chat open. An already authorized autonomous action does not
gain an extra per-trade confirmation requirement from this brief.

- Observations, original agent interpretation and retrospective explanations have
  distinct labels. No invented confidence score or retrospective rationale posed
  as the original reason. Contradictory evidence is disclosed and cited separately.
- For ambiguous questions, ask the smallest relevant clarification or answer with
  an explicit bounded assumption. For unsupported actions, explain the boundary
  and open a supported workflow; do not say Done.
- On unavailable account/market tools, explain which portion could not be read;
  general education remains possible only when clearly independent of that data.
- Routine agent output stays in Activity until requested. Only consequential
  safety states produce cross-screen alerts. No agent persona/avatar theater.
- Correction consists of editing context, asking a follow-up or retrying a read.
  It does not rewrite historical evidence. No external human-support handoff,
  saved lesson feature or rating/feedback collection is assumed implemented.
- News shows permitted attribution, publication time and relevant delay; receipt
  time alone never makes a headline current. Disabling a context pane stops its
  unnecessary display-driven work; it does not stop autonomous monitoring.
- Model/prompt/tool changes must repeat UX-10 checks. No conversational content
  telemetry is enabled by this design review.

### Dependency and verification ownership

| Dependency | Responsible role / evidence | Failure and resolution gate |
|---|---|---|
| Identity and account ownership | Backend implementer; current auth/account contracts | Deny private reads/actions on lost authority; validate account switch/sign-out cleanup before release |
| Quote/calendar/history semantics | Market backend implementer; actual timestamped records and reviewed calendar | Explain stale, unknown session and missing history; current broker access never inferred from a healthy API |
| Order/command identity and outcome lookup | Paper/backend implementer; actual operation IDs, ledger and reconciliation | If uncertain-outcome lookup is missing, expose unresolved state and hold retry capability until contract exists |
| Portfolio values and reports | Accounting/backend implementer; formula, baseline and reconciliation contracts | Missing/failed value stays unavailable; no frontend-derived authoritative equity |
| AI progress and cancellation | Chat/backend implementer; current endpoint capabilities | Request/response loading only until actual events/cancel semantics exist; no fake task service |
| Responsive accessibility | Frontend implementer and reviewer; browser/input/zoom observations | Blocking defects in reachability, focus or essential content must resolve before affected surface acceptance |

## Verification plan and remaining boundaries

This review is a document and contract review. It is not an observed user study,
WCAG conformance audit, rendered prototype review or connected-market acceptance.
The earlier local DOM prototype checks remain the only prototype execution evidence.

For the next owner walkthrough, use fictional records and goal-based tasks without
revealing the required clicks: understand why no trade occurred; inspect the
instrument and return to the conversation; follow a partially filled order; stop
new entries without closing exposure; recover from a failed answer. Record only
supplied feedback and observed actions, separately from designer inference. No
participant recruitment, recording or data collection is part of this review.

Before implementation release, capture browser/version, viewport/zoom, input mode,
scenario, expected observation, actual result and evidence for UX-01–UX-10. Include
keyboard focus/return, text expansion, narrow reflow, software keyboard, reduced
motion, stale instrument responses and ambiguous order outcomes. Actual market
acceptance remains under its existing separate work items.

Remaining bounded decisions:

- **Visual specification:** designer owns typography, exact palette, spacing,
  density and polished component states. Gate: reviewed desktop/mobile examples
  before styling implementation; behavior work need not reopen the product model.
- **Backend integration gaps:** backend implementer verifies current field and
  operation contracts before each slice. Gate: no invented consequential behavior.
- **Owner usability evidence:** owner walkthrough and reviewer notes before
  declaring task usability accepted; until then the defaults are hypotheses.
- **Browser/accessibility evidence:** implementation reviewer owns actual checks;
  no prototype or documentation claim substitutes for them.

The behavioral brief is complete for visual design and implementation planning.
Final appearance and verified task usability are separate deliverables.

No application code, deployment settings or trading permissions changed as part of this document.

## Integrated product direction: PRD, vision and implementation

Synthesis dated 24 November 2026. The sections above record the agreed interaction direction. This section supplies the product rationale, source precedence and designer handoff. Recommendations below are design proposals unless already identified as agreed; they do not activate functionality.

### Source map and precedence

| Source | How the designer should use it |
|---|---|
| [Original PRD](./__workspace/01-source-prd.md) | Historical starting point: genuine quotes, simulated execution, strict risk, measurable outcomes. Its hosting/auth choices and permanent product exclusions are superseded where later decisions differ. |
| [Current product requirements](./__workspace/11-current-product-requirements.md) | Chat-first access, independently operating autonomy, persisted evidence, explicit controls and account boundaries. |
| [Autonomous product direction](./__workspace/21-autonomous-product-direction.md) | Longer-term broker execution and possible multiple users; future ambitions, not current release capability. |
| [Autonomous trading discussion](./AUTONOMOUS-TRADING-DISCUSSION.md) | Product reasoning: bounded sessions, mandates, explainable abstention, reliable management, learning from outcomes. Brainstorming is not implementation authorization. |
| [Strategy intelligence handoff](./STRATEGY-INTELLIGENCE-HANDOFF.md) | Personal trading desk, continuous observation with selective reasoning, predefined strategies first, evidence-led future research. |
| [Workspace plan](./__workspace/37-complete-system-and-broker-workspace-plan.md) and [feature inventory](./__workspace/39-broker-feature-data-inventory.md) | Detailed workflows and field contracts. Dated capability statements need reconciliation with later checkpoint notes. |
| [RESUME](./RESUME.md), [deferred work](./DEFERRED-WORK.md), current API modules | Latest implementation and acceptance boundaries. Passing tests or a successful login does not establish autonomous trading acceptance. |
| This brief and latest user discussion | Current UX decisions: Chat / Dashboard / Trade, learning emphasis, broker-familiar workspace, no everyday provider-diagnostics screens. |

Resolve by topic and explicit decision, not by treating the newest file as authority for everything. Preserve the immutable source PRD. This synthesis does not silently rewrite trading requirements.

Important reconciliations:

- Design for the present personal, single-owner paper release. Keep future broker execution conceptually possible without exposing a nonfunctional Live switch, broker marketplace or user administration.
- The original three-minute AI cycle is not a promise to show perpetual AI thinking. The current model is continuous observation and selective bounded reasoning. The latest checkpoint describes an ORB watcher once per minute at second 5 IST; cadence is operational detail, not primary UI.
- Broad strategy development and comparisons are vision/research scope. A strategy library full of invented active strategies would misrepresent the current narrow ORB path.
- Learning is now a first-class experience goal. It complements the original goal of measuring outcomes after costs; engagement, lesson completion and profitable trading are different measures.
- Remove routine developer/provider checklists from normal use. Retain user-owned risk decisions and actionable account recovery. A future multi-user broker-consent flow would be legitimate onboarding, distinct from today's developer diagnostics.
- Chat as a place to request anything is an interaction ambition. Current free-text chat reads evidence; the separate audited session-stop control blocks new entries. Order placement, risk editing and session arming must not be implied by a friendly chat response.

### The product promise and user jobs

**Designer brief:** Design a personal trading companion that lets its user ask and learn naturally, inspect the market directly, and understand what an autonomous paper-trading system did, why, and with what result. Its work continues independently of the conversation. Every actionable result links to the same underlying instrument, decision, order or position across the three destinations.

| Situation / user job | Essential answer | Primary surface |
|---|---|---|
| I open SWAN | Let me continue asking or learning immediately | Chat |
| I wonder why nothing happened | Was there no setup, a rejected opportunity, missing evidence, or a failure? | Chat answer linked to Dashboard activity |
| I inspect a possible trade | Which contract, what evidence, what price age, what costs and constraints? | Trade with contextual explanation |
| SWAN is holding exposure | What is open, what protection is actually active, and what requires me? | Dashboard / Trade with persistent critical alert |
| I stop new entries | Confirm the effective scope and that this does not itself close positions | Audited control with resulting state |
| I review a session | What happened after costs, why, and what can I learn? | Dashboard review linked to Chat |
| A dependency fails | What remains usable, what is affected, and what can I do? | Local failure state; critical exposure consequences global |

These are design hypotheses grounded in this user's discussions, not findings from external user interviews.

### Design frameworks and concrete application

Use a small number of methods to make decisions rather than accumulating aesthetic frameworks.

| Method / source | Application in SWAN | Required design evidence |
|---|---|---|
| [Design Council Double Diamond](https://www.designcouncil.org.uk/resources/framework-for-innovation) | Discover requirements and failure examples; define the jobs above; develop alternative flows; test and refine them before implementation | Source map, chosen journeys, alternative wireframes, task walkthrough results |
| [Nielsen usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/) | Visible request state, familiar trading language, explicit cancel/pause semantics, error prevention, preserved drafts and recovery | For every action: visible response, result, failure and recovery |
| [Progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/) | Show consequence and concise reason first; reveal evidence, accounting and version details on request | Summary → one useful detail view; avoid nested drawers inside drawers |
| [Microsoft Human–AI Interaction guidelines](https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/) | State supported capabilities, uncertainty and limitations; permit correction/dismissal; make recorded reasons accessible when AI is wrong | Unsupported-request, incorrect interpretation, partial evidence and failed-analysis flows |
| Job and journey mapping, applied here | Organize by what the user wants to accomplish and the sequence of decisions | Complete ask → inspect → act → track → review journey |
| Service blueprint, applied here | Map visible user states to actual service records, events and ownership | State/evidence matrix below; no invented backend progress |

UI/UX Pro Max was used for targeted loading/recovery guidance: preserve layout/focus, use accessible busy feedback, match feedback to the wait, and supply a recovery action. Its navigation/disclosure searches did not return a relevant disclosure rule after a narrower retry; use the primary NN/g source above instead. No generic skill-generated product template determines this layout.

### Backend-to-experience blueprint

This is a repository/checkpoint review, not a new live integration audit. Existing capability does not imply current operational availability.

| Backend responsibility and evidence | User-facing object / interaction | Current boundary |
|---|---|---|
| Authenticated account identity and ownership | Sign-in; one paper account context; sign-out | Current fixed owner; no multi-account switcher |
| `services/api/chat.py`, `chat_control.py` | Grounded answer, source links, explicit stop-new-entries outcome | Current request/response endpoint; no verified streaming, cross-device history or resumable background-chat contract |
| Instruments, watchlists, chain, candles, indicators, market APIs | Search → selected contract → chart/depth/chain; explain selected study | Show sourced fields only; missing history/volume is not zero; analytics coverage varies |
| Strategy records, assignments, agent evidence/activity | Opportunity or decision detail with reason, evidence and validity | ORB path exists; broad strategy research is not a delivered catalog; actual autonomous qualification remains open |
| Manual plans, order preview/actions/history | Paper ticket → preview → submission status → fills/position | Existing bounded manual permission/risk path; no broker order submission |
| Portfolio, journal and daily report | Reconciled account summary, exposure, history and session review | Saved values, fresh valuations and unavailable baselines remain distinct |
| Paper controls and qualification | Saved mandate, entry state, permitted setup/recovery action | Eligibility, qualification and explicit arm stay server-owned; no frontend toggle bypass |
| Worker, reconciliation and protection | Relevant activity and position protection state | Worker presence alone does not prove fresh data or working protection |
| Calendar-aware isolated broker login | Quiet automatic maintenance; actionable price-access failure if relevant | Daily 08:55 IST job is separate from app; renewal and next-open-session stream acceptance remain unverified |
| Hosted API/database and bounded VM resources | Independent pane loading, lightweight refresh, retained readable results | 1 GB experiment, not a latency SLA; idle health does not establish sustained session performance |

Before implementation, each UI field/action needs a contract: authoritative record, units/formula, observation time, response time, missing/stale semantics, allowed action, expiry, terminal outcome and retry behavior. Do not add these internal fields as visible labels everywhere; use them to make the interface truthful.

### Three surfaces, one coherent experience

**Chat:** begin with a quiet composer and optional relevant prompts. Once the conversation starts, prioritize reading and writing. Context attachments identify the selected instrument/trade and can be removed. Rich answers offer Open chart, View decision or View position. A narrow optional side panel adds relevant context on wide screens; it never becomes a second dashboard competing with the conversation. No unsolicited routine agent reports in the transcript.

**Dashboard:** lead with the selected session/period, paper equity and net result, current exposure, and anything requiring attention. Then show what SWAN did or is waiting for, with concise reasons. Deeper tabs can hold Positions, Activity and History/Review. Equity history and statistics need real, sufficient records; do not draw a plausible curve from two trades. Expand costs and risk calculations only when useful.

**Trade:** watchlist/search at left, selected contract/chart centrally, contextual depth/chain or ticket alongside, orders/positions below or in a drawer. Keep context tools mutually manageable so five panels do not crowd the chart. On mobile use one active task surface, with sheets/tabs for secondary details. Ask SWAN opens a contextual assistant drawer; docking it is optional for large screens. The chart remains usable if chat fails.

**Shared details:** one order timeline, one position detail and one decision explanation, reached from any surface. Preserve the instrument, timeframe, draft and navigation return point. A manual order's origin must never appear as an agent decision.

### State design: autonomy is often quiet

Use this as a semantic map, not a single exclusive state machine: observation, research and management can overlap. Market session, account entry permission, feed freshness and active work are independent dimensions.

| Actual condition | Suggested concise copy | Available next step |
|---|---|---|
| Observing, no qualifying setup | Watching NIFTY. No qualifying setup yet. | See conditions / ask why |
| Setup rejected by a recorded rule | Entry skipped: spread exceeded the saved limit. | View evidence |
| Agent job running | Reviewing the observed breakout. | View actual task status; cancellation only if supported |
| Evidence absent | Cannot assess this setup: opening bars are missing. | Inspect coverage; retry when allowed |
| Opportunity expired | Opportunity expired before review completed. | Review timing; do not silently renew it |
| Entries paused | New paper entries paused. | Review pause reason and allowed recovery |
| Open position, verified management | Position open; show current verified protection details. | Inspect / permitted exit action |
| Worker/protection uncertain with exposure | Position monitoring could not be verified. | Prominent actionable exposure alert |
| Exchange holiday | Market closed for the verified holiday. | Saved charts, learning and reports remain usable |
| Chat unavailable | This answer could not complete. | Retry; keep other surfaces usable |

Never synthesize comforting protection copy from a heartbeat. Do not call provider failure WAIT or imply that successful sign-in makes old observations current. Critical alerts persist across destinations until resolved or explicitly acknowledged under their real semantics. Routine statuses stay near the affected object.

### Priority journeys for the next prototype

1. **Orient and ask:** open Chat → greeting → ask why no trade → concise sourced explanation → inspect the recorded decision.
2. **Inspect and learn:** search contract → chart → explain indicator with visible instrument/timeframe context → return to the same chart.
3. **Manual paper trade:** ticket → valid preview → explicit paper submission → pending/partial fill → position → exit outcome. Include rejection and uncertain response recovery without automatic duplicate submission.
4. **Supervise autonomy:** saved mandate → current eligibility/entry state → meaningful activity → stop new entries → verify effect while existing protection remains independently visible.
5. **Review and improve:** session result → costs and decisions → one trade/abstention → grounded explanation and optional learning note. Saved notes are a proposal until storage exists.
6. **Recover:** stale feed, interrupted chat, changed instrument during fetch, daily loss block, restart with exposure and a missing valuation. Preserve what is trustworthy and disable only actions that lack required evidence.

### Additional ideas worth testing

- A compact Today summary on demand: what happened, why no trades if applicable, what remains open. It must reflect records, not manufacture an AI narrative on every page load.
- A useful no-trade review: differentiate disciplined abstention from outages and expired opportunities. This makes quiet autonomous operation understandable.
- A per-trade explanation combining original hypothesis, observed execution and outcome. Separate original rationale from retrospective interpretation.
- Saved learning notes attached to decisions/indicators, and later comparison of the user's hypothesis with the actual outcome. New storage/workflow scope, not assumed implemented.
- A single contextual command/search entry for instruments and navigation, distinct from conversational order execution. Test discoverability before adding another persistent control.

Avoid agent avatars with decorative progress, arbitrary confidence gauges, automatic lessons after every message, unsupported strategy galleries, a permanently scrolling news feed and performance claims from tiny samples.

### Designer deliverables and evaluation

Deliver a flow map and low-fidelity mobile/desktop alternatives before polished screenshots. For the chosen flow, include component states, content examples, keyboard behavior, focus recovery, data-age presentation and responsive pane rules. Use clearly marked illustrative values in prototypes; never connect them to production records or trading permissions.

Validate with the owner on the priority journeys. Record success/failure, confusion, retries, context loss and ability to identify paper mode, exposure, freshness and order outcome. Ask the user to explain what Pause does and what an accepted order means. A visually attractive screen that fails these questions needs revision.

Candidate performance goals for later measurement: immediate local acknowledgement of input; a simple greeting without unrelated tools; progress for long requests backed by real events; independently usable navigation during chat/research failure. Set numeric latency budgets from hosted measurements rather than inventing a guarantee.

Open design work is tracked under D27 in [DEFERRED-WORK.md](./DEFERRED-WORK.md). Existing illustrative mockups are exploratory, not a tested final design. No broker login, market acceptance, code change or deployment was performed for this synthesis.

## Linked journey prototype: 24 November 2026

The next prototype is `.local/design/swan-journeys.html`, displayed in conversation.
It is an isolated design example, not application source or a production feature.
Its hypothetical contract, lot size, prices, costs and session are explicitly
illustrative. No network requests, AI calls or trading actions are made.

Implemented prototype interactions:

- Chat explanation → same contract in Trade → contextual learning → return to chart.
- Editable whole-lot paper preview → explicit submission example → accepted order
  → partial fill → full position → exit requested → exit filled → Dashboard review.
- Desktop and narrow mobile preview, preserving the active journey.
- Holiday, stale-price, unavailable-chat and unverified-monitoring exposure scenarios.
- Pause-new-entries example, distinct from liquidation. A restriction activated
  after preview also blocks the stale submit action.

Local DOM interaction checks passed for these transitions, repeat submission,
illustrative arithmetic, preview invalidation and preserved failed-chat input.
These checks are not visual browser inspection, real backend acceptance or owner
usability validation. The prototype stacks the mobile chart and ticket; it predates
the selected full-height sheet default (DD-04) and is not the final layout contract.

### Owner walkthrough prompts

| Task | What we need to observe | Status |
|---|---|---|
| Explain why there was no trade | Can the owner distinguish no setup from failure? | Awaiting owner walkthrough |
| Open chart, ask a question, return | Is the selected instrument/context clear and preserved? | Awaiting owner walkthrough |
| Preview and follow an order | Can the owner distinguish preview, acceptance, partial fill and exposure? | Awaiting owner walkthrough |
| Request an exit | Is it clear that exposure remains until the fill? | Awaiting owner walkthrough |
| Pause entries with a position open | Does the owner understand that this does not liquidate? | Awaiting owner walkthrough |
| Switch to a failure scenario | Is the consequence understandable and usable content still reachable? | Awaiting owner walkthrough |
| Use the mobile preview | Is task priority clear without crowded simultaneous panes? | Awaiting owner walkthrough |

Do not label these tasks passed until the owner actually walks through them.
Next refinement should follow observed confusion, especially mobile tickets,
dashboard information priority and the visibility of current trading authority.

## Implementation handoff hardening with Product Design and UX

Installed 24 November 2026 from
[magnus919/agent-skills](https://github.com/magnus919/agent-skills/tree/cb581ffec17d3bb0aee2cf605716d107c6e378ad/product-design-and-ux),
pinned to commit `cb581ffec17d3bb0aee2cf605716d107c6e378ad`.
Local skill: `C:/Users/HP/.codex/skills/product-design-and-ux/SKILL.md`.
Reviewed its main instructions, collaborative decision guidance, state modeling,
interface contracts, AI uncertainty and engineering handoff references. This adds
behavioral rigor to the existing brief; it does not replace its product decisions
or prescribe a visual template. Adjacent named skills are optional specialist
routes, not dependencies installed or invoked by this action.

### Handoff gates by implementation slice

Before starting a slice, link its user outcome, authoritative records, allowed
actions, relevant states, recovery and observable criteria below. Do not wait for
every decorative choice to resolve, but do not invent consequential behavior.

| Slice | Existing capability to reuse | UI work / contract gap | Entry gate |
|---|---|---|---|
| Navigation and shell | Authenticated owner context | New task-first layout, focus/return behavior, responsive panes | Agreed three destinations; no inheritance from old pages |
| Chat home | Grounded request/response and separate session-stop control | Modern composer, context links, failure recovery; streaming and durable tasks need separate backend contracts | Do not fake token streaming, background completion or unsupported mutations |
| Trade exploration | Instruments, saved watchlist, candles, indicators, chain/depth | Shared selection, readable fields, contextual panes and evidence age | Map real schemas and per-field missing/freshness rules before binding |
| Paper order journey | Existing preview/manual execution/ledger paths | Ticket, preview invalidation, pending/partial/exit timelines | Bind actual permissions, revisions and deduplication; no prototype execution logic |
| Dashboard and review | Portfolio, journal, reports, activity/evidence | Reconciled hierarchy and shared details | Specify valuation/baseline availability; distinguish manual from autonomous origin |
| Alerts and recovery | Runtime/account/session facts where available | Consequence-first severity, persistence and recovery | Missing status evidence cannot become a positive protection claim |

### Observable acceptance contracts

These are planned criteria, not passed implementation tests.

| ID | Given / when | Required observable outcome and recovery | Verification boundary |
|---|---|---|---|
| UX-01 | Authenticated owner opens the app | Chat home appears; unrelated market/research loads do not block the composer or navigation | Authenticated browser, slow/failing dependency conditions |
| UX-02 | Chat request fails after submission | Original input/context remain recoverable; Retry is explicit; no order or permission change is implied | Actual API error/timeout and UI state, not only prototype |
| UX-03 | Selected contract changes while an older read is pending | Old response cannot replace the newly selected contract's chart or ticket | Delayed out-of-order responses; assert instrument identity |
| UX-04 | Prices, policy or authority change after preview | Submission revalidates the actual contract; blocked outcome explains the consequence and preserves editable intent | Existing server path plus UI; altered/revoked permission and expired evidence |
| UX-05 | Submission response is lost or uncertain | Resolve persisted operation/order identity before any repeat side effect; show uncertainty until known | API/ledger integration with interrupted response; no blind duplicate POST |
| UX-06 | Order partially fills or exit is requested | Remaining order quantity and actual exposure stay distinct; exit request does not show Closed before confirmation | Persisted order/fill/position records, followed across destinations |
| UX-07 | Owner stops new entries | Show confirmed effective scope; failure is not success; open positions are not described as liquidated | Audited server result, UI state and separately evidenced protection |
| UX-08 | Viewport, zoom, orientation or keyboard changes | Preserve draft, selection and task; controls remain reachable, focused controls visible, dense data has usable alternatives | Real browser keyboard/reflow/touch checks; phone checks recorded separately |
| UX-09 | Account valuation or session baseline is unavailable | Show unavailable with consequence; never render zero or a fabricated curve | Real schema missing-data cases and ledger reconciliation |
| UX-10 | Chat/model source or prompt changes | Recheck normal, unsupported, stale/conflicting, permission and failure behavior | Versioned authorized fixtures; model quality remains separate from UX success |

### Ownership and unresolved decisions

- Owner: user reviews visual direction and the recommended mobile sheet (DD-04)
  through concrete examples. The selected behavior is a recommendation, not a
  recorded owner usability result.
- Frontend implementer: specify focus, draft/selection persistence, reflow and
  request lifecycle for each slice before building it. Cross-device chat history
  remains future scope unless separately accepted.
- Backend implementer: verify existing schemas, commit/retry identities and
  permission rechecks. Report any missing capability as a dependency, not a
  simulated frontend success. No runtime/trading authority changes follow here.
- Verification: record browser/version, scenario, expected and observed result,
  evidence, and failed/blocked/not-run status. Prototype DOM checks do not close
  browser accessibility, usability, hosted integration or actual-market acceptance.
- Privacy: measure only needed task/lifecycle events if telemetry is authorized;
  do not default to recording chat bodies, financial details, tokens or secrets.

The current plan is ready to guide slice specification. It is not yet a fully
approved visual design or permission to implement/deploy the application.
