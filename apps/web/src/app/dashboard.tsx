"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { User } from "firebase/auth";
import type { Readiness } from "@/lib/readiness";
import Icon, { type IconName } from "./icons";
import ContractChart from "./candles";
import InstrumentSearch, { type SelectedContract } from "./instrument-search";
import Watchlist, { useWatchlist } from "./watchlist";
import OptionChain, { type Chain, type ChainRow } from "./option-chain";
import SystemSetup from "./system-setup";
import ValidationPanel from "./validation";
import PaperControls from "./paper-controls";
import ExecutionHistory, { ActiveOrders, FundsPanel, Positions } from "./execution";
import type { ExecutionData, Position } from "@/lib/paper";
import { money, time } from "@/lib/paper";

type Runtime = { status: string; problem: string | null; heartbeat: string | null; resume_requested: boolean; active_envelope: unknown };
type Workspace = ExecutionData & {
  as_of: string; mode: string;
  readiness?: Readiness;
  account: { cash: string; enabled: boolean; daily_blocked: boolean; revision: number; config: Record<string, unknown> };
  runtime: Runtime | null; positions: Position[]; journal: Position[];
  ledger: { id: string; timestamp: string; category: string; amount: string }[];
  evaluations: { id: string; slot_at: string; status: string; evidence_ids: string[] }[];
  events: { id: string; timestamp: string; kind: string; details: unknown }[];
};
const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const pages: Record<string, string> = { home: "Overview", markets: "Option chain", orders: "Execution", history: "Journal", account: "System setup", risk: "Risk settings", permissions: "Paper controls", trial: "Paper validation", activity: "Activity" };
const errors: Record<string, string> = {
  PAPER_PLAN_REQUEST_CONFLICT: "This save request was already used with different inputs. Preview again before saving.",
  PREVIEW_ACCOUNT_CHANGED: "Your account changed. Preview again before saving or placing this plan.",
  MANUAL_MARKET_CLOSED: "The market is closed or its session is unverified. You can still save a plan.",
  MANUAL_ADMISSION_CHANGED: "Order checks changed. Calculate a fresh preview before trying again.",
  MANUAL_QUOTE_UNAVAILABLE: "A current stored quote is required before placing a paper order.",
  MANUAL_REQUEST_CONFLICT: "This order request belongs to different inputs. Check Orders before trying again.",
  MANUAL_CONTRACT_CHANGED: "Contract details changed. Load the contract and make a new plan.",
  ENTRY_SOURCE_MISMATCH: "Another entry mode owns this session. Stop it before starting a manual session.",
  CONTROLLED_VALIDATION_REQUIRED: "Start a manual paper session before placing this order.",
  MANUAL_VALIDATION_REQUIRED: "Manual orders need an explicit manual paper session.",
  MANUAL_RISK_LIMIT: "This order exceeds the remaining risk budget. Review quantity and stop price.",
  INSUFFICIENT_EXECUTABLE_DEPTH: "Usable depth no longer covers this order. Preview again.",
  INSUFFICIENT_UNRESERVED_CASH: "Available cash no longer covers this order and its costs.",
  VALIDATION_ENTRY_LIMIT: "This session already has its one entry. Track it in Orders.",
  VALIDATION_SCOPE_EXCEEDED: "This session supports one lot of its selected contract.",
  VALIDATION_STOPPING: "The session is stopping. Existing exposure is still being managed.",
  PAPER_PLAN_LIMIT: "You have 50 saved paper plans. Archive an older plan before saving another.",
  PAPER_PLAN_NOT_FOUND: "This saved plan is unavailable for your account.",
  ORDER_PRICES_OFF_TICK: "Use prices that are multiples of the contract tick size shown in Details.",
  BROKER_LOGIN_REQUIRED: "Your broker session needs a new login. Prices were not refreshed; previously saved quotes are still shown.",
  HISTORY_REFRESH_BUSY: "A candle refresh is already running. Try again shortly.",
  HISTORY_REFRESH_RATE_LIMIT: "Please wait a few seconds before requesting candles again.",
  HISTORY_CURRENT_METADATA_REQUIRED: "Refresh market prices first to update this contract?s details.",
  HISTORY_UNSUPPORTED_INSTRUMENT_OR_RANGE: "Refresh market prices or choose another session. This contract?s history could not be requested.",
  HISTORY_PROVIDER_UNAVAILABLE: "The broker could not return candles. Check your broker login and try again.",
  HISTORY_RANGE_AFTER_EXPIRY: "Choose a session on or before this contract?s expiry.",
  WATCHLIST_FULL: "Your watchlist has 50 contracts. Remove one before saving another.",
  CATALOG_REFRESH_BUSY: "Another contract refresh is running. Try again shortly.",
  CATALOG_REFRESH_RATE_LIMIT: "Please wait a minute between contract refreshes.",
  CATALOG_UNAVAILABLE: "The contract list could not be retrieved. Try again shortly.",
  CATALOG_REFRESH_REQUIRED: "Refresh contracts to open a current listing.",
  INSTRUMENT_NOT_LISTED: "This contract is no longer in the current list. Refresh contracts.",
  INSTRUMENT_NOT_SAVED: "This contract is unavailable. Find it again in Search.",
  INSTRUMENT_EXPIRED: "This contract has expired. Choose a current expiry.",
  INSTRUMENT_IDENTITY_CHANGED: "The broker's contract details changed. This listing cannot be opened safely.",
  MARKET_PRICES_UNAVAILABLE: "Prices could not be retrieved. Check your broker login and try again.",
  QUOTE_REFRESH_BUSY: "A market refresh is already running. Try again shortly.",
  QUOTE_REFRESH_RATE_LIMIT: "Please wait 30 seconds between market refreshes.",
  AUTH_NOT_CONFIGURED: "Sign-in is not fully configured. Check your account connection in Settings.",
  ACCOUNT_NOT_AUTHORIZED: "This sign-in does not have access to this paper account.",
  PAPER_ACCOUNT_NOT_CONFIGURED: "Your paper account and risk policy need to be configured.",
  AUTH_VERIFICATION_UNAVAILABLE: "Identity verification is temporarily unavailable.",
  SESSION_INVALID: "Your session has expired or was revoked. Sign in again.",
  DATABASE_UNAVAILABLE: "The account database is unavailable.",
  WORKER_NOT_READY_OR_DAILY_BLOCKED: "Resume is unavailable: the worker is offline or the daily loss limit is active.",
  PAUSE_AND_CLOSE_POSITIONS_BEFORE_SETTINGS: "Pause new entries and close all positions before changing risk limits.",
  SETTINGS_CHANGED_REFRESH_REQUIRED: "The account changed. Refresh before saving your risk limits.",
  INVALID_RISK_LIMITS: "Trade risk must not exceed the daily loss limit. Check the values and try again.",
  USE_EXPLICIT_PAPER_ARMING: "Use Paper controls to review qualification and explicitly arm paper entries.",
  PAPER_QUALIFICATION_REQUIRED: "Current qualification is missing, expired or invalidated. Review the evidence checklist in Paper controls.",
  PAPER_ARM_PREFLIGHT_INCOMPLETE: "Complete setup and refresh connection tests before arming paper entries.",
  QUALIFICATION_EVIDENCE_INCOMPLETE: "The required actual-market evidence is incomplete. Review the qualification checklist.",
  QUALIFICATION_CONFIGURATION_INCOMPLETE: "Resolve execution configuration evidence before reviewing qualification.",
  WORKER_PREPARATION_REQUIRES_FLAT_PAUSED_ACCOUNT: "Pause entries, stop validation or disarm, then resolve all orders and positions before changing worker mode.",
  WORKER_PREPARATION_FAILED: "The worker could not be prepared. Inspect private local logs and refresh its status.",
  LOCAL_SINGLE_OWNER_REQUIRED: "Local worker control requires the enrolled single-owner account.",
  AUTONOMOUS_WORKER_REQUIRED: "Prepare an autonomous worker first. Preparing it does not arm entries.",
  PAPER_ENGINE_NOT_READY: "Paper validation has not been completed. Review the specific requirements in System setup.",
  VALIDATION_WORKER_REQUIRED: "Start the validation worker before requesting a bounded session.",
  VALIDATION_PREFLIGHT_INCOMPLETE: "Complete configuration and refresh the connection tests in System setup.",
  VALIDATION_FRESH_CONTRACT_REQUIRED: "Select a contract with a current stored quote from Option chain.",
  VALIDATION_FRESH_DEPTH_REQUIRED: "The selected contract needs fresh, verified market depth.",
  VALIDATION_OPEN_CURRENT_SESSION_REQUIRED: "Validation requires an open, verified market session and a current account baseline.",
  VALIDATION_ALREADY_ACTIVE_OR_ARMED: "Stop the existing session and resolve exposure before starting another.",
  VALIDATION_REQUIRES_FLAT_RECONCILED_ACCOUNT: "Resolve pending orders and positions and reconcile the account first.",
  VALIDATION_INELIGIBLE_CONTRACT: "Select a current eligible contract whose actual lot fits the approved quantity limit.",
  VALIDATION_WINDOW_TOO_SHORT: "Refresh connection tests and broker login; at least one minute must remain before the entry cutoff.",
  WORKER_OBSERVATION_ONLY: "The managed worker observes only. Entries remain disabled pending paper validation.",
  PAUSE_AND_RESOLVE_ORDERS_POSITIONS_BEFORE_SETTINGS: "Pause entries and resolve every pending order and position before changing settings.",
  INVALID_SETUP_CONFIGURATION: "The imported configuration is invalid. Check its schema, source evidence and required values.",
  COMPLETE_RISK_POLICY_REQUIRED: "Every risk-policy field must be supplied and reviewed.",
  CONFIGURATION_WRITE_UNAVAILABLE: "Configuration could not be saved. Check the local file permissions.",
  CONNECTION_CHECK_UNAVAILABLE: "Another connection check is running, or the account is unavailable. Retry shortly.",
  CAPITAL_CHANGE_REQUIRES_LEDGER_OPERATION: "Capital cannot be changed through risk settings. An audited funding operation is required.",
};

export default function Dashboard({ user, onSignOut }: { user: User; onSignOut: () => void }) {
  const [tab, setTab] = useState("Overview");
  const [settingsTab, setSettingsTab] = useState("System setup");
  const [data, setData] = useState<Workspace | null>(null);
  const [chain, setChain] = useState<Chain | null>(null);
  const [underlying, setUnderlying] = useState("NIFTY");
  const [chainExpiry, setChainExpiry] = useState("");
  const [offset, setOffset] = useState(0);
  const [marketView, setMarketView] = useState("chain");
  const [chartRecord, setChartRecord] = useState<SelectedContract | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);
  const [chartId, setChartId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [chainSort, setChainSort] = useState<"latest" | "strike">("latest");
  const [chainError, setChainError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => { setChainExpiry(""); setOffset(0); setChain(null); }, [underlying]);

  useEffect(() => {
    const restorePage = () => {
      const [section, query] = window.location.hash.slice(1).split("?");
      const params = new URLSearchParams(query);
      const page = pages[section] ?? "Overview";
      setMarketView(["search", "watchlist"].includes(params.get("view") ?? "") ? params.get("view")! : "chain");
      setChartId(section === "markets" ? params.get("instrument") : null);
      const market = params.get("underlying");
      if (market === "NIFTY" || market === "SENSEX") setUnderlying(market);
      setTab(page); setFeedback(null);
      if (["System setup", "Risk settings", "Paper controls", "Paper validation", "Activity"].includes(page)) setSettingsTab(page);
    };
    restorePage();
    window.addEventListener("hashchange", restorePage);
    return () => window.removeEventListener("hashchange", restorePage);
  }, []);

  const request = useCallback(async (path: string, method = "GET", signal?: AbortSignal, body?: unknown) => {
    const token = await user.getIdToken();
    const response = await fetch(base + path, { method, signal, cache: "no-store", headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
    const result = await response.json();
    if (!response.ok) {
      const code = typeof result.detail === "string" ? result.detail : result.detail?.code;
      const message = typeof code === "string" ? errors[code] : null;
      throw Object.assign(new Error(message ?? (response.status === 422 ? "Some fields are invalid or missing. Review your inputs." : "Unable to complete the request. Check the connection and settings.")), { status: response.status, code });
    }
    return result;
  }, [user]);

  const watchlist = useWatchlist(request, tab === "Option chain", tab === "Option chain" && marketView === "watchlist" && !chartId);

  useEffect(() => {
    if (!chartId || tab !== "Option chain") return;
    let active = true;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setChartRecord(current => current?.instrument.id === chartId ? current : null); setChartError(null);
    async function load() {
      try {
        if (!document.hidden) {
          const result = await request(`/api/market/instruments/selected?${new URLSearchParams({ instrument_id: chartId! })}`, "GET", controller.signal);
          if (active) { setChartRecord(result as SelectedContract); setChartError(null); }
        }
      } catch (cause) { if (active) setChartError(cause instanceof Error ? cause.message : "Contract unavailable."); }
      finally { if (active) timer = setTimeout(load, 5000); }
    }
    void load();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [chartId, request, tab, refresh]);

  useEffect(() => {
    if (!chartId || tab !== "Option chain") return;
    const controller = new AbortController();
    const retain = () => {
      if (!document.hidden) void request("/api/market/subscriptions/selected", "POST", controller.signal, { instrument_id: chartId }).catch(() => {});
    };
    retain();
    const timer = setInterval(retain, 30000);
    document.addEventListener("visibilitychange", retain);
    return () => { controller.abort(); clearInterval(timer); document.removeEventListener("visibilitychange", retain); };
  }, [chartId, request, tab]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const workspace: Workspace = await request("/api/workspace", "GET", controller.signal);
        if (active) { setData(workspace); setError(null); setNow(Date.now()); }
        if (tab === "Option chain" || tab === "Overview") {
          try {
            const options: Chain = await request(`/api/chain?underlying=${underlying}&offset=${offset}&sort=${chainSort}${chainExpiry ? `&expiry=${encodeURIComponent(chainExpiry)}` : ""}`, "GET", controller.signal);
            if (active) { setChain(options); setChainError(null); }
          } catch { if (active) { setChainError("Option observations could not be loaded. Account data is still available."); setChain(null); } }
        }
      } catch (cause) {
        if (active) { setError(cause instanceof Error ? cause.message : "Connection unavailable."); setChain(null); }
      } finally {
        if (active) timer = setTimeout(load, 5000);
      }
    }
    void load();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [request, tab, underlying, offset, chainExpiry, chainSort, refresh]);

  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);

  async function control(action: "pause" | "resume") {
    if (busy) return;
    setBusy(true); setActionError(null); setFeedback(null);
    try { await request(`/api/control/${action}`, "POST"); setFeedback(action === "pause" ? "New entries are paused." : "Resume requested. Entries wait for worker preflight and strategy approval."); setRefresh(value => value + 1); }
    catch (cause) { setActionError(cause instanceof Error ? cause.message : "Action unavailable."); }
    finally { setBusy(false); }
  }

  async function refreshPrices() {
    if (busy || stale) return;
    setBusy(true); setActionError(null); setFeedback(null);
    try {
      const result = await request("/api/market/quotes/refresh", "POST", undefined, { underlying }) as { quotes: number };
      setFeedback(result.quotes ? `Retrieved ${result.quotes} last available quotes for ${underlying}. Check their exchange timestamps below.` : "No quotes were returned for the selected contracts.");
      setRefresh(value => value + 1);
    } catch (cause) { setActionError(cause instanceof Error ? cause.message : "Prices are unavailable."); }
    finally { setBusy(false); }
  }

  async function refreshSelectedPrices(ids: string[]) {
    if (busy || !ids.length) return;
    setBusy(true); setActionError(null); setFeedback(null);
    try {
      const result = await request("/api/market/quotes/selected/refresh", "POST", undefined, { instrument_ids: ids }) as { quotes: number; fresh_quotes: number };
      setFeedback(result.quotes ? `Retrieved ${result.quotes} quotes.${result.fresh_quotes < result.quotes ? " Some prices are older; check their timestamps." : ""}` : "The broker returned no quotes for these contracts. Saved prices remain visible.");
      setRefresh(value => value + 1);
      await watchlist.retry();
    } catch (cause) { setActionError(cause instanceof Error ? cause.message : "Prices are unavailable."); }
    finally { setBusy(false); }
  }

  async function saveRisk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data || busy) return;
    const values = new FormData(event.currentTarget);
    setBusy(true); setActionError(null); setFeedback(null);
    try {
      const policy = { ...data.account.config };
      for (const key of ["max_positions", "quote_max_age_seconds", "entry_cutoff_minutes", "flatten_minutes", "max_fill_quantity", "min_volume", "min_oi", "max_spread_bps"]) policy[key] = key === "max_spread_bps" ? String(values.get(key)) : Number(values.get(key));
      policy.max_trade_risk_pct = String(Number(values.get("trade")) / 100);
      policy.max_daily_loss_pct = String(Number(values.get("daily")) / 100);
      policy.max_holding_seconds = Number(values.get("holding"));
      await request("/api/settings/risk-policy", "POST", undefined, {
        expected_revision: data.account.revision, policy, reviewed: values.get("reviewed") === "on",
      });
      setRefresh(value => value + 1);
      setFeedback("The complete risk policy is saved and reviewed. Entries remain paused.");
    } catch (cause) { setActionError(cause instanceof Error ? cause.message : "Unable to save risk policy."); }
    finally { setBusy(false); }
  }

  async function downloadJournal() {
    if (busy) return;
    setBusy(true); setActionError(null); setFeedback(null);
    try {
      const token = await user.getIdToken();
      const response = await fetch(base + "/api/reports/journal.csv", { cache: "no-store", headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("Export unavailable. Check your connection and try again.");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = url; link.download = "swan-paper-journal.csv";
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) { setActionError(cause instanceof Error ? cause.message : "Export unavailable."); }
    finally { setBusy(false); }
  }

  const heartbeat = data?.runtime?.heartbeat;
  const workerOnline = heartbeat != null && now - Date.parse(heartbeat) >= 0 && now - Date.parse(heartbeat) <= 10000;
  const stale = data != null && (error !== null || now - Date.parse(data.as_of) > 15000);
  const ready = data?.readiness;

  const marketLabel = ready?.market_state === "open" ? "Market open" : ready?.market_state === "closed" ? "Market closed" : ready?.market_state === "partial" ? "Limited trading hours" : "Market hours unavailable";
  const settingsPage = ["System setup", "Risk settings", "Paper controls", "Paper validation", "Activity"].includes(tab);
  const navigate = (name: string) => {
    setTab(name); setFeedback(null);
    const hash = Object.keys(pages).find(key => pages[key] === name) ?? "home";
    if (window.location.hash !== `#${hash}`) window.location.hash = hash;
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  const selectedContract = chartRecord?.instrument.id === chartId ? chartRecord : chain?.rows.find(row => row.instrument.id === chartId);
  const returnToMarket = () => { setChartId(null); window.location.hash = marketView === "chain" ? "markets" : `markets?view=${marketView}`; };
  const openChart = (item: ChainRow["instrument"]) => {
    setChartId(item.id);
    window.location.hash = `markets?${new URLSearchParams({ instrument: item.id, underlying: item.underlying, ...(marketView !== "chain" ? { view: marketView } : {}) })}`;
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  const nextStep = !workerOnline ? "Connect your trading service" : !ready?.configuration_complete ? "Finish setting up your paper account" : !ready.connections_verified ? "Check your market connections" : "Explore the market";
  const nextDetail = !workerOnline ? "Your account is available, but automatic position monitoring is offline." : !ready?.configuration_complete ? "A few trading and risk settings still need review before you can place paper trades." : !ready.connections_verified ? "Verify your broker and market data before starting a paper session." : "View option prices and available contracts. Paper trading stays paused until you choose to start.";

  return <main className="workspace">
    <header className="topbar"><div className="brand"><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M7 22 15 9l3 8 7-5-9 13-3-8Z" fill="currentColor"/></svg></span><div><p className="brand-name">swan<span className="brand-period">.</span></p></div></div><div className="header-actions"><button className="avatar-button" aria-label="Open account settings" onClick={() => navigate("System setup")}>{(user.displayName ?? user.email ?? "S").slice(0, 1).toUpperCase()}</button></div></header>
    <nav className="tabs" aria-label="Main navigation">{([["Overview", "Home", "home"], ["Option chain", "Markets", "markets"], ["Execution", "Orders", "orders"], ["Journal", "History", "history"], ["System setup", "Account", "account"]] as [string, string, IconName][]).map(([name, label, icon]) => <button key={name} aria-current={(name === "System setup" ? settingsPage : tab === name) ? "page" : undefined} onClick={() => navigate(name === "System setup" ? settingsTab : name)}><Icon name={icon} /><span>{label}</span></button>)}</nav>
    {settingsPage && <div className="account-heading"><div><h1>Account</h1><p>{user.email ?? user.displayName}</p></div><button className="text-button" onClick={onSignOut}><Icon name="logout" />Sign out</button></div>}
    {settingsPage && <nav className="settings-tabs" aria-label="Account settings">{[["System setup", "Connections & setup"], ["Risk settings", "Risk limits"], ["Paper controls", "Trading permissions"], ["Paper validation", "Trial sessions"], ["Activity", "Account activity"]].map(([name, label]) => <button className="secondary" key={name} aria-current={tab === name ? "page" : undefined} onClick={() => { setSettingsTab(name); navigate(name); }}>{label}</button>)}</nav>}
    {error && <div className="notice error" role="alert">{error}<button className="secondary" onClick={() => setRefresh(value => value + 1)}>Retry</button></div>}
    {actionError && <p className="notice error" role="alert">{actionError}</p>}
    {feedback && <p className="notice" role="status">{feedback}</p>}
    {!data ? <section className="panel"><h2>{error ? "Workspace unavailable" : "Loading your workspace…"}</h2><p>Your balances and positions will appear here once your account is connected.</p></section> : <>
      <div className="statusline"><span className={`dot ${workerOnline ? "online" : ""}`} /><span>{workerOnline ? "Monitoring connected" : "Monitoring offline"}</span><span className="status-pill">{data.account.enabled && workerOnline ? "Entries enabled" : "Entries paused"}</span><span className="updated">Updated {time(data.as_of)} IST</span><button className="text-button refresh-button" aria-label="Refresh account" onClick={() => setRefresh(value => value + 1)}><Icon name="refresh" /></button></div>
      {stale && <p className="notice error" role="status">Workspace data is stale. Controls are unavailable until it refreshes.</p>}
      {!workerOnline && data.positions.length > 0 && <p className="notice error" role="alert">Your open positions are not being monitored. Restore the trading connection to manage automatic exits.</p>}
      {tab === "Overview" && <>
        <div className="page-heading"><div><p className="eyebrow">YOUR PORTFOLIO</p><h1>Overview</h1></div><span className="market-badge">{marketLabel}</span></div>
        <div className="metrics"><article className="balance-card"><p><Icon name="wallet" /> Available to trade</p><strong>{money(data.funds?.available_cash)}</strong><span>Paper balance &middot; INR</span></article><article><p>Open positions</p><strong>{data.positions.length}</strong><span>{data.positions.length ? "Positions currently held" : "No market exposure"}</span></article><article><p>Pending orders</p><strong>{data.order_summary?.active_count ?? "Unavailable"}</strong><span>Awaiting a fill</span></article><article><p>Daily loss limit</p><strong>{Number(data.account.config.max_daily_loss_pct) * 100}%</strong><span>{data.account.daily_blocked ? "Limit reached - trading paused" : "Of your paper capital"}</span></article></div>
        <div className="overview-grid">
          <section className="panel getting-started"><p className="eyebrow">{data.account.enabled ? "TRADING STATUS" : "YOUR NEXT STEP"}</p><h2>{data.account.enabled ? "Paper trading is active" : nextStep}</h2><p>{data.account.enabled ? "New entries are enabled. You can pause them while existing positions continue to be monitored." : nextDetail}</p><div className="actions">{data.account.enabled ? <button disabled={busy || stale} onClick={() => control("pause")}>Pause new trades</button> : <button onClick={() => navigate(ready?.configuration_complete && ready.connections_verified ? "Option chain" : "System setup")}>{ready?.configuration_complete && ready.connections_verified ? "Explore markets" : "Continue setup"}<Icon name="arrow" /></button>}<button className="text-button" onClick={() => navigate("Risk settings")}>Review risk limits</button></div></section>
          <section className="panel market-summary"><div className="panelhead"><h2>Market watch</h2><button className="text-button" onClick={() => navigate("Option chain")}>View chain <Icon name="arrow" /></button></div><div className="market-switch" aria-label="Market watch underlying">{["NIFTY", "SENSEX"].map(name => <button key={name} aria-pressed={underlying === name} onClick={() => {setUnderlying(name);setChainExpiry("");setOffset(0);setChain(null);}}>{name}</button>)}</div>{chainError ? <p className="empty-state">Market prices are unavailable. Check your connection in Account.</p> : chain == null ? <p className="empty-state">Loading market prices...</p> : chain.rows.length ? <div className="watch-list">{chain.rows.slice(0,3).map(({instrument,quote}) => <div className="watch-row" key={instrument.id}><div><strong>{instrument.strike} {instrument.option_type === "CALL" ? "CE" : "PE"}</strong><small>{instrument.expiry}</small></div><div><span>Bid / Ask</span><strong>{quote.bid == null ? "Unavailable" : money(quote.bid)} / {quote.ask == null ? "Unavailable" : money(quote.ask)}</strong><small>{time(quote.timestamp)} IST</small></div></div>)}</div> : <div className="market-empty"><Icon name="markets" /><strong>No quotes yet</strong><p>{ready?.market_state === "closed" ? "The market is closed. Quotes appear here when your market connection receives prices." : "Check your market connection to receive option prices."}</p></div>}</section>
        </div>
        <section className="panel"><div className="panelhead"><div><h2>Open positions</h2><p>{data.positions.length ? "Your current paper holdings and exit levels." : "You have no open positions. Your funds are ready when you are."}</p></div><button className="text-button" onClick={() => navigate("Execution")}>View all</button></div>{data.positions.length > 0 && <Positions rows={data.positions} data={data} workerOnline={workerOnline} stale={stale} empty="No open positions." />}</section>
        {(data.order_summary?.active_count ?? 0) > 0 && <ActiveOrders data={data} />}
      </>}
      {tab === "Execution" && <><FundsPanel funds={data.funds} /><ActiveOrders data={data} /><section className="panel"><h2>Open positions</h2><Positions rows={data.positions} data={data} workerOnline={workerOnline} stale={stale} empty="No open paper positions." /></section><ExecutionHistory data={data} /></>}
      {tab === "Paper controls" && <PaperControls request={request} report={ready} />}
      {tab === "Paper validation" && <ValidationPanel request={request} report={ready} />}
      {tab === "System setup" && (ready ? <SystemSetup report={ready} request={request} onRefresh={() => setRefresh(value => value + 1)} /> : <section className="panel"><h2>Readiness checks unavailable</h2><p>Refresh to retrieve the backend setup report.</p></section>)}
      {tab === "Option chain" && chartId && selectedContract && <ContractChart key={`${user.uid}:${chartId}`} instrument={selectedContract.instrument} reference={"reference" in selectedContract ? selectedContract.reference : chain?.reference} quoteDate={selectedContract.quote?.timestamp} quote={selectedContract.quote} statistics={"statistics" in selectedContract ? selectedContract.statistics : undefined} quoteError={chartError} quoteMaxAge={Number(data.account.config.quote_max_age_seconds)} request={request} quoteBusy={busy} onRefreshQuote={() => void refreshSelectedPrices([chartId])} marketLabel={marketLabel} onBack={returnToMarket} backLabel={marketView === "watchlist" ? "Watchlist" : marketView === "search" ? "Search" : "Option chain"} />}
      {tab === "Option chain" && chartId && !selectedContract && <section className="panel"><p>{chartError ?? "Loading contract..."}</p><button className="secondary" onClick={returnToMarket}>Back to markets</button></section>}
      {tab === "Option chain" && !chartId && <div className="market-switch market-views" aria-label="Market view">{[["chain", "Option chain"], ["watchlist", "Watchlist"], ["search", "Search"]].map(([value, label]) => <button key={value} aria-pressed={marketView === value} onClick={() => { setMarketView(value); window.location.hash = value === "chain" ? "markets" : `markets?view=${value}`; }}>{label}</button>)}</div>}
      {tab === "Option chain" && marketView === "search" && <div hidden={chartId != null}><InstrumentSearch watchlist={watchlist} request={request} underlying={underlying} onMarket={value => { setUnderlying(value); setChainExpiry(""); setOffset(0); setChain(null); }} onOpen={result => { setChartRecord(result); openChart(result.instrument); }} /></div>}
      {tab === "Option chain" && !chartId && watchlist.feedback && <p className="chart-feedback" role="status">{watchlist.feedback}</p>}
      {tab === "Option chain" && !chartId && marketView === "watchlist" && <Watchlist refreshing={busy} onRefresh={() => void refreshSelectedPrices(watchlist.data?.rows.filter(row => row.status === "listed").map(row => row.instrument.id) ?? [])} state={watchlist} now={now} quoteAge={Number(data.account.config.quote_max_age_seconds)} onOpen={row => { setChartRecord(row); openChart(row.instrument); }} onSearch={() => { setMarketView("search"); window.location.hash = "markets?view=search"; }} />}
      {tab === "Option chain" && !chartId && marketView === "chain" && <OptionChain sort={chainSort} onSort={value => { setChainSort(value); setOffset(0); setChain(null); }} chain={chain} error={chainError} underlying={underlying} expiry={chainExpiry} busy={busy} stale={stale} offset={offset} now={now} maxAge={Number(data.account.config.quote_max_age_seconds)} onMarket={value => { setUnderlying(value); setChainExpiry(""); setOffset(0); setChain(null); }} onExpiry={value => { setChainExpiry(value); setOffset(0); setChain(null); }} onRefresh={() => { setChainExpiry(""); setOffset(0); void refreshPrices(); }} onPage={value => { setOffset(value); setChain(null); }} onOpen={openChart} />}
      {tab === "Journal" && <><section className="panel"><div className="panelhead"><h2>Closed positions</h2><button className="secondary" disabled={busy} onClick={downloadJournal}>Export CSV</button></div><p>Most recent 50 records. Realized P&amp;L includes recorded execution costs. CSV exports up to 10,000 closed positions.</p><Positions rows={data.journal} data={data} empty="No closed paper positions." /></section><section className="panel"><h2>Cash ledger</h2>{!data.ledger.length ? <p>No ledger entries recorded.</p> : <div className="tablewrap"><table><thead><tr><th>Time (IST)</th><th>Category</th><th>Amount</th></tr></thead><tbody>{data.ledger.map(item => <tr key={item.id}><td>{time(item.timestamp)}</td><td>{item.category}</td><td>{money(item.amount)}</td></tr>)}</tbody></table></div>}</section></>}
      {tab === "Activity" && <section className="panel"><h2>Account activity</h2><p>Recent changes to your account and trading activity.</p>{!data.events.length ? <p>No activity recorded.</p> : data.events.map(event => <details key={event.id}><summary>{time(event.timestamp)} · {event.kind.replaceAll("_", " ")}</summary><p className="muted">Recorded in your account history.</p></details>)}</section>}
      {tab === "Risk settings" && <section className="panel"><h2>Review your complete risk policy</h2><p>Pause entries and resolve pending orders and positions before saving. Capital is preserved in the ledger; changing it requires a separate funding operation.</p><form onSubmit={saveRisk} key={data.account.revision}><fieldset disabled={busy || stale || data.account.enabled || data.positions.length > 0 || (data.order_summary?.active_count ?? 1) > 0 || data.runtime?.resume_requested}><p>Configured paper capital: <strong>{money(String(data.account.config.capital))}</strong></p><div className="riskform">
        <label>Trade risk (% of capital)<input name="trade" type="number" required min="0.01" max="100" step="0.01" defaultValue={Number(data.account.config.max_trade_risk_pct) * 100} /></label>
        <label>Daily loss limit (% of capital)<input name="daily" type="number" required min="0.01" max="100" step="0.01" defaultValue={Number(data.account.config.max_daily_loss_pct) * 100} /></label>
        <label>Maximum holding (seconds)<input name="holding" type="number" required min="1" max="300" step="1" defaultValue={Number(data.account.config.max_holding_seconds)} /></label>
        {([ ["Maximum open positions", "max_positions", 1, undefined], ["Quote maximum age (seconds)", "quote_max_age_seconds", 1, 10], ["Stop new entries before close (minutes)", "entry_cutoff_minutes", 1, undefined], ["Request flatten before close (minutes)", "flatten_minutes", 1, undefined], ["Maximum fill quantity (units)", "max_fill_quantity", 1, undefined], ["Minimum observed volume", "min_volume", 0, undefined], ["Minimum open interest", "min_oi", 0, undefined], ["Maximum spread (basis points)", "max_spread_bps", 0.01, 10000] ] as const).map(([label, key, min, max]) => <label key={key}>{label}<input name={key} type="number" required min={min} max={max} step={key === "max_spread_bps" ? "0.01" : "1"} defaultValue={Number(data.account.config[key])} /></label>)}
        </div><p className="muted">Maximum quantity must accommodate an actual whole option lot. Entry cutoff must be earlier than flatten time. Execution policy and reviewed fees are configured separately.</p><label className="checkbox-label"><input name="reviewed" type="checkbox" required />I reviewed all limits, including quantity, liquidity and session cutoffs.</label><button type="submit">Save and review policy</button></fieldset></form></section>}
    </>}
    <footer>Paper execution only · NIFTY &amp; SENSEX · All times Asia/Kolkata</footer>
  </main>;
}

