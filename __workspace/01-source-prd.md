# SWAN Trade — MVP Product Requirements Document

## 1. Objective & Core Problem

Build **SWAN Trade**, an installable, mobile-first PWA that autonomously analyzes NIFTY and SENSEX options, makes AI-assisted decisions, and executes simulated trades. Reuse existing LLMs, market APIs, and open-source libraries without training models. Validate whether autonomous strategies produce positive returns after simulated trading costs while enforcing strict risk limits.

## 2. Strict Scope & Non-Goals

**MVP — BUILD:**
- Single-user PWA with authenticated access.
- Angel One market-data integration for NIFTY/SENSEX options.
- Option-chain analysis: OI, PCR, volume, IV, Greeks, and price trends.
- AI agents for market analysis, trade decisions, and trade reviews.
- Autonomous BUY CALL / BUY PUT / WAIT decisions.
- Virtual portfolio, order management, stop-loss, take-profit, and daily loss limit.
- Live activity dashboard, trade journal, and daily reports.

**DO NOT BUILD:**
- Real-money trading or broker order execution.
- Custom LLMs, training pipelines, or fine-tuning.
- TradingView-style drawing tools or custom chart engines.
- Multiuser accounts, subscriptions, or social features.
- Unrestricted AI access to account settings or risk limits.

## 3. Critical User Flow

1. User signs in, configures paper capital and risk limits, then enables autonomous paper trading.
2. At market open, the system validates exchange sessions and data availability.
3. Every three minutes, market tools retrieve prices, option-chain metrics, and available market context.
4. AI evaluates market conditions and returns BUY_CALL, BUY_PUT, or WAIT with supporting evidence.
5. Risk engine validates data freshness, liquidity, capital, stop-loss, and exposure.
6. Approved proposals become simulated orders using available bid/ask quotes.
7. System monitors positions, updates simulated P&L, and executes virtual exits.
8. Daily cutoff blocks new entries; user can pause trading anytime.
9. After market close, AI summarizes performance, decisions, and errors.

## 4. Technical & Data Specs

**Stack:** Next.js, TypeScript, Tailwind, shadcn/ui, Serwist, Lightweight Charts, FastAPI, Python, LangGraph, OpenAI API, Angel One SmartAPI, PostgreSQL, APScheduler, Docker.

**Hosting:** Vercel (PWA), AWS Lightsail (backend/agents), PostgreSQL on AWS initially.

**Authentication:** AWS Cognito OIDC, single-user email allowlist (provisional default).

**Core schemas:**
- `MarketSnapshot(id, symbol, expiry, strike, option_type, bid, ask, oi, volume, iv, greeks, timestamp)`
- `TradeDecision(id, snapshot_ids, action, rationale, entry, stop_loss, target, timestamp)`
- `PaperOrder(id, decision_id, instrument, side, quantity, fill_price, status, fees)`
- `PaperPosition(id, instrument, quantity, average_price, realized_pnl, unrealized_pnl)`
- `RiskConfig(capital, max_trade_risk_pct, max_daily_loss_pct, max_positions, enabled)`

**Interfaces:**
- `GET /market/snapshot`
- `POST /agents/evaluate` → `TradeDecision`
- `POST /paper/orders` → `PaperOrder`
- `GET /portfolio`
- `POST /trading/pause`
- `evaluate_risk(decision: TradeDecision, state: PortfolioState) -> RiskResult`

**Directory hints:** `/apps/web`, `/services/api`, `/services/agents`, `/services/paper`, `/services/risk`, `/shared/schemas`, `/tests`.

**MVP defaults:** ₹100,000 paper capital; 0.5% maximum planned trade risk; 2% daily loss cutoff; one simultaneous position. OpenAI API access is separately configured; ChatGPT credits are not assumed transferable.

## 5. Edge Cases & Error States

- Missing/invalid credentials → disable autonomous operation.
- Missing OI, Greeks, or required quotes → mark data unavailable; never fabricate metrics.
- Stale prices (over 10 seconds) → reject new trade proposals.
- Market closed or exchange holiday → no new orders.
- LLM timeout, invalid JSON, or conflicting decisions → WAIT.
- Insufficient paper capital or risk violation → reject order and record reason.
- Daily loss limit reached → block entries and apply configured exit policy.
- Network interruption → stop new entries; reconcile simulated positions after recovery.
- Duplicate signal → reject using unique decision ID.
- Missing required external API capabilities → disable dependent features.

## 6. Testable Acceptance Criteria

- [ ] PWA installs and opens on Android; unauthorized users cannot access portfolio data.
- [ ] Market snapshots show timestamped NIFTY/SENSEX data without fabricated fields.
- [ ] AI outputs parse into the defined decision schema; invalid outputs produce WAIT.
- [ ] Autonomous session executes simulated trades without user interaction.
- [ ] Every accepted order passes risk validation.
- [ ] Paper fills use bid/ask pricing, configured slippage, and transaction costs.
- [ ] Risk breaches block new entries and produce an auditable event.
- [ ] Pause prevents further entries within the next evaluation cycle.
- [ ] Duplicate decisions never create duplicate paper orders.
- [ ] Dashboard portfolio and journal reconcile with the simulated ledger.
- [ ] No application code invokes real-money order placement endpoints.
- [ ] Integration tests run successfully using recorded market fixtures without live credentials.