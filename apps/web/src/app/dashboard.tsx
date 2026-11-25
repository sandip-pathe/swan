"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import type { User } from "firebase/auth";
import type { Readiness } from "@/lib/readiness";
import Icon from "./icons";
import { Plus } from "lucide-react";
import NavigationIcon, { type NavigationIconName } from "./navigation-icon";
import ContractChart from "./candles";
import InstrumentSearch, { type SelectedContract } from "./instrument-search";
import Watchlist, { useWatchlist } from "./watchlist";
import OptionChain, { type Chain, type ChainRow } from "./option-chain";
import SystemSetup from "./system-setup";
import ValidationPanel from "./validation";
import PaperControls from "./paper-controls";
import { PaperActionProvider, PaperActionStatus } from "./paper-action";
import DashboardIntelligence from "./dashboard-intelligence";
import DashboardSkeleton from "./dashboard-skeleton";
import AgentActivity from "./agent-activity";
import { readSnapshot, saveSnapshot, clearSnapshots } from "@/lib/display-snapshot";
import Chat from "./chat";
import DeviceSettings from "./device-settings";
import { useScreenMemory } from "@/lib/navigation-memory";
import { useOverlayBack } from "@/lib/overlay-back";
import { readAppearance, saveAppearance, validAppearance } from "@/lib/browser-preferences";
import { useChatSessions } from "./chat-sessions";
import Brand from "./brand";
import DailyReport from "./daily-report";
import ClosedJournal from "./closed-journal";
import PortfolioPanel from "./portfolio";
import ExecutionHistory, { ActiveOrders, FundsPanel, Positions } from "./execution";
import type { ExecutionData, Position } from "@/lib/paper";
import { money, time } from "@/lib/paper";

type Runtime = { status: string; problem: string | null; heartbeat: string | null; resume_requested: boolean; active_envelope: unknown };
type Workspace = ExecutionData & {
  as_of: string; mode: string;
  readiness?: Readiness;
  account: { cash: string; enabled: boolean; daily_blocked: boolean; revision: number; config: Record<string, unknown> };
  runtime: Runtime | null; positions: Position[];
  ledger: { id: string; timestamp: string; category: string; amount: string }[];
  evaluations: { id: string; slot_at: string; status: string; evidence_ids: string[] }[];
  events: { id: string; timestamp: string; kind: string; details: unknown }[];
};
const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
const pages: Record<string, string> = { home: "Overview", markets: "Option chain", orders: "Trades", history: "History", strategies: "Decisions", chat: "Chat", account: "Account & workspace", diagnostics: "System setup", risk: "Risk settings", permissions: "Paper controls", trial: "Paper validation" };
const errors: Record<string, string> = {
  PAPER_PLAN_REQUEST_CONFLICT: "This save request was already used with different inputs. Preview again before saving.",
  PREVIEW_ACCOUNT_CHANGED: "Your account changed. Preview again before saving or placing this plan.",
  MANUAL_MARKET_CLOSED: "The market is closed or today's hours aren't confirmed. You can still save a plan.",
  MANUAL_ADMISSION_CHANGED: "Order checks changed. Calculate a fresh preview before trying again.",
  MANUAL_QUOTE_UNAVAILABLE: "A current stored quote is required before placing a paper order.",
  MANUAL_REQUEST_CONFLICT: "This order request belongs to different inputs. Check Orders before trying again.",
  MANUAL_CONTRACT_CHANGED: "Contract details changed. Load the contract and make a new plan.",
  ENTRY_SOURCE_MISMATCH: "Another paper trading mode is active. Turn it off before placing this order.",
  CONTROLLED_VALIDATION_REQUIRED: "Turn on paper buying in the order window before placing this order.",
  MANUAL_VALIDATION_REQUIRED: "Turn on paper buying in the order window before placing this order.",
  MANUAL_RISK_LIMIT: "This order exceeds the remaining risk budget. Review quantity and stop price.",
  INSUFFICIENT_EXECUTABLE_DEPTH: "Usable depth no longer covers this order. Preview again.",
  INSUFFICIENT_UNRESERVED_CASH: "Available cash no longer covers this order and its costs.",
  VALIDATION_ENTRY_LIMIT: "This paper-buying window has used its one order. Track it in Trades.",
  VALIDATION_SCOPE_EXCEEDED: "This paper-buying window is for one option and one lot. Finish or turn it off before switching.",
  VALIDATION_STOPPING: "Paper buying is turning off. Any open trade will still be managed.",
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
  const [tab, setTab] = useState("Chat");
  const internalNavigation = useRef(false);
  const pageRestored = useRef(false);
  const contextTrigger = useRef<HTMLButtonElement>(null);
  const sidebarTrigger = useRef<HTMLButtonElement>(null);
  const sidebarElement = useRef<HTMLElement>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileSidebar, setMobileSidebar] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 760px)");
    const sync = () => { setMobileSidebar(media.matches); setSidebarOpen(!media.matches); };
    sync(); media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);
  useEffect(() => {
    if (!mobileSidebar || !sidebarOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sidebarElement.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const keys = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); setSidebarOpen(false); }
      if (event.key !== "Tab") return;
      const nodes = Array.from(sidebarElement.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],select,input,textarea,[tabindex="0"]') ?? []).filter(node => node.getClientRects().length);
      const first = nodes[0], last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", keys);
    return () => { document.body.style.overflow = previous; document.removeEventListener("keydown", keys); requestAnimationFrame(() => sidebarTrigger.current?.focus()); };
  }, [mobileSidebar, sidebarOpen]);
  const chats = useChatSessions(user.uid);
  const [contextOpen, setContextOpen] = useState(false);
  const [theme, setTheme] = useState("system");
  const [settingsTab, setSettingsTab] = useState("System setup");
  const [data, setData] = useState<Workspace | null>(() => readSnapshot<Workspace>(user.uid, "workspace"));
  const [confirmed, setConfirmed] = useState(false);
  const [workerNow, setWorkerNow] = useState(Date.now);
  const [chain, setChain] = useState<Chain | null>(null);
  const [underlying, setUnderlying] = useState("NIFTY");
  const [chainExpiry, setChainExpiry] = useState("");
  const [offset, setOffset] = useState(0);
  const [marketView, setMarketView] = useState("search");
  const [chartRecord, setChartRecord] = useState<SelectedContract | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);
  const [chartId, setChartId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadErrorDismissed, setLoadErrorDismissed] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [chainSort, setChainSort] = useState<"latest" | "strike">("latest");
  const [chainError, setChainError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [feedback, setFeedback] = useState<string | null>(null);
  const rememberScreen = useScreenMemory(user.uid, tab, data !== null);
  const dashboardDestination = useRef("Overview");
  const accountDestination = useRef("Account & workspace");
  useOverlayBack(mobileSidebar && sidebarOpen, () => setSidebarOpen(false));
  useOverlayBack(mobileSidebar && contextOpen, () => setContextOpen(false));
  useEffect(() => {
    if (["Overview", "Trades", "History", "Decisions"].includes(tab)) dashboardDestination.current = tab;
    if (["Account & workspace", "System setup", "Risk settings", "Paper controls", "Paper validation"].includes(tab)) accountDestination.current = tab;
  }, [tab]);


  useEffect(() => { setChainExpiry(""); setOffset(0); setChain(null); }, [underlying]);

  useEffect(() => {
    const restorePage = () => {
      const [section, query] = window.location.hash.slice(1).split("?");
      const params = new URLSearchParams(query);
      const page = pages[section] ?? "Chat";
      if (section === "markets") setMarketView(["search", "watchlist", "chain"].includes(params.get("view") ?? "") ? params.get("view")! : "search");
      if (section === "markets") setChartId(params.get("instrument"));
      const market = params.get("underlying");
      if (market === "NIFTY" || market === "SENSEX") setUnderlying(market);
      if (pageRestored.current && !internalNavigation.current) rememberScreen();
      pageRestored.current = true; internalNavigation.current = false;
      setTab(page); setFeedback(null);
      if (["Account & workspace", "System setup", "Risk settings", "Paper controls", "Paper validation"].includes(page)) setSettingsTab(page);
    };
    restorePage();
    window.addEventListener("hashchange", restorePage);
    return () => window.removeEventListener("hashchange", restorePage);
  }, []);

  const request = useCallback(async (path: string, method = "GET", signal?: AbortSignal, body?: unknown) => {
    if (!navigator.onLine) throw new Error("You are offline. Reconnect before sending requests.");
    const token = await user.getIdToken();
    const boundedSignal = signal ? AbortSignal.any([signal, AbortSignal.timeout(30000)]) : AbortSignal.timeout(30000);
    const response = await fetch(base + path, { method, signal: boundedSignal, cache: "no-store", headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
    const result = await response.json();
    if (!response.ok) {
      const code = typeof result.detail === "string" ? result.detail : result.detail?.code;
      const message = typeof code === "string" ? errors[code] : null;
      throw Object.assign(new Error(message ?? (response.status === 422 ? "Some fields are invalid or missing. Review your inputs." : "Unable to complete the request. Check the connection and settings.")), { status: response.status, code });
    }
    return result;
  }, [user]);

  useEffect(() => {
    const refreshAfterReconnect = () => setRefresh(value => value + 1);
    window.addEventListener("swan:refresh", refreshAfterReconnect);
    return () => window.removeEventListener("swan:refresh", refreshAfterReconnect);
  }, []);

  const watchlist = useWatchlist(request, tab === "Option chain", tab === "Option chain");

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
    let active = true, pending = false, failures = 0;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      clearTimeout(timer);
      if (!active || pending) return;
      if (document.hidden || !navigator.onLine) { timer = setTimeout(load, 5000); return; }
      pending = true;
      try {
        const workspace = await request("/api/workspace", "GET", controller.signal) as Workspace;
        if (active) {
          setData(workspace); setConfirmed(true); setError(null); setLoadErrorDismissed(false); setNow(Date.now());
          saveSnapshot(user.uid, "workspace", workspace); failures = 0;
        }
      } catch (cause) {
        if (active) { failures++; setError(cause instanceof Error ? cause.message : "Connection unavailable."); }
      } finally {
        pending = false;
        if (active) timer = setTimeout(load, failures ? Math.min(60000, 5000 * 2 ** failures) : 5000);
      }
    }
    const resume = () => { if (!document.hidden) void load(); };
    void load(); document.addEventListener("visibilitychange", resume);
    return () => { active = false; controller.abort(); clearTimeout(timer); document.removeEventListener("visibilitychange", resume); };
  }, [request, user.uid, refresh]);

  useEffect(() => {
    if (tab !== "Option chain" || marketView !== "chain") return;
    const controller = new AbortController();
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        if (document.hidden || !navigator.onLine) return;
        const options = await request(`/api/chain?underlying=${underlying}&offset=${offset}&sort=${chainSort}${chainExpiry ? `&expiry=${encodeURIComponent(chainExpiry)}` : ""}`, "GET", controller.signal) as Chain;
        if (active) { setChain(options); setChainError(null); }
      } catch { if (active) setChainError("Option observations could not be updated. Previous observations are still shown."); }
      finally { if (active) timer = setTimeout(load, 5000); }
    }
    void load();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [request, tab, marketView, underlying, offset, chainExpiry, chainSort, refresh]);

  useEffect(() => { const timer = setInterval(() => setWorkerNow(Date.now()), 5000); return () => clearInterval(timer); }, []);

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
  const workerOnline = confirmed && heartbeat != null && workerNow - Date.parse(heartbeat) >= 0 && workerNow - Date.parse(heartbeat) <= 15000;
  const stale = data != null && (!confirmed || error !== null || workerNow - Date.parse(data.as_of) > 20000);
  const ready = confirmed && !stale ? data?.readiness : undefined;

  const marketLabel = ready?.market_state === "open" ? "Market open" : ready?.market_state === "closed" ? "Market closed" : ready?.market_state === "partial" ? "Limited trading hours" : "Market hours unavailable";
  const settingsPage = ["Account & workspace", "System setup", "Risk settings", "Paper controls", "Paper validation"].includes(tab);
  const navigate = (name: string) => {
    rememberScreen();
    setTab(name); setFeedback(null);
    if (mobileSidebar) setSidebarOpen(false);
    const hash = name === "Option chain" ? `markets?${new URLSearchParams({ view: marketView, ...(chartId ? { instrument: chartId, underlying } : {}) })}` : Object.keys(pages).find(key => pages[key] === name) ?? "chat";
    if (window.location.hash !== `#${hash}`) { internalNavigation.current = true; window.location.hash = hash; }
  };
  const selectedContract = chartRecord?.instrument.id === chartId ? chartRecord : chain?.rows.find(row => row.instrument.id === chartId);
  const returnToMarket = () => { setChartId(null); window.location.hash = `markets?view=${marketView}`; };
  const openChart = (item: ChainRow["instrument"]) => {
    setChartId(item.id);
    window.location.hash = `markets?${new URLSearchParams({ instrument: item.id, underlying: item.underlying, ...(marketView !== "chain" ? { view: marketView } : {}) })}`;
    window.scrollTo({ top: 0, behavior: "instant" });
  };

  const dashboardPage = ["Overview", "Trades", "History", "Decisions"].includes(tab);
  useEffect(() => {
    const stored = readAppearance();
    setTheme(stored);
    if (stored === "dark" || stored === "light") document.documentElement.dataset.theme = stored;
    else delete document.documentElement.dataset.theme;
  }, []);
  useEffect(() => {
    if (!contextOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") { setContextOpen(false); contextTrigger.current?.focus(); } };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [contextOpen]);
  function changeTheme(value: string) {
    setTheme(value); if (value === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = value;
    if (validAppearance(value)) saveAppearance(value);
  }
  function signOut() {
    clearSnapshots(user.uid);
    try { for (const key of Object.keys(localStorage)) { if (key === `swan.chat.sessions.v1.${user.uid}` || key.startsWith(`swan.chat.history.v2.${user.uid}.`) || key.startsWith(`swan.chat.draft.v1.${user.uid}.`)) localStorage.removeItem(key); } localStorage.removeItem(`swan.chat.history.v2.${user.uid}`); localStorage.removeItem(`swan.chat.draft.v1.${user.uid}`); localStorage.removeItem("swan.chat.history.v1"); } catch { /* Continue sign-out. */ }
    try { for (const key of Object.keys(sessionStorage)) { if (key === `swan.navigation.v1.${user.uid}` || key.startsWith(`swan.market.filters.v1.${user.uid}.`) || key.startsWith(`swan.chat.scroll.v1.${user.uid}.`)) sessionStorage.removeItem(key); } } catch { /* Continue sign-out. */ }
    onSignOut();
  }
  const primaryNavigation = <>{([ ["Chat", "Chat", "chat"], ["Overview", "Dashboard", "dashboard"], ["Option chain", "Trade", "trade"] ] as [string, string, NavigationIconName][]).map(([name, label, icon]) => { const active = name === "Overview" ? dashboardPage : tab === name; return <button key={name} aria-current={active ? "page" : undefined} onClick={() => navigate(name === "Overview" ? dashboardDestination.current : name)}><NavigationIcon name={icon} active={active} /><span>{label}</span></button>; })}</>;
  return <main className={`workspace swan-app ${sidebarOpen ? "sidebar-is-open" : "sidebar-is-closed"}`}><PaperActionProvider key={user.uid} ownerKey={user.uid} revision={data?.account.revision} request={request} onRefresh={() => setRefresh(value => value + 1)}>
    {mobileSidebar && sidebarOpen && <button className="sidebar-backdrop text-button" aria-label="Close navigation overlay" onClick={() => setSidebarOpen(false)} />}
    <aside id="swan-navigation" ref={sidebarElement} className="app-sidebar" role={mobileSidebar && sidebarOpen ? "dialog" : undefined} aria-modal={mobileSidebar && sidebarOpen ? true : undefined} aria-label="Navigation"><button className="sidebar-close text-button" aria-label="Close sidebar" onClick={() => { setSidebarOpen(false); requestAnimationFrame(() => sidebarTrigger.current?.focus()); }}>&times;</button><div className="app-brand-label" aria-label="SWAN"><Brand /></div><button className="app-new-chat secondary" onClick={() => { chats.create(); navigate("Chat"); }}><Plus className="icon nav-icon-dashboard" size={21} strokeWidth={1.65} aria-hidden="true" /><span className="nav-label">New conversation</span></button><nav className="app-navigation" aria-label="Main navigation">{primaryNavigation}</nav><nav className="chat-session-list" aria-label="Conversations"><p className="eyebrow">CHATS</p>{[...chats.sessions].sort((a, b) => b.updated - a.updated).map(session => <button key={session.id} className="text-button" title={session.title} aria-current={tab === "Chat" && chats.activeId === session.id ? "page" : undefined} onClick={() => { chats.select(session.id); navigate("Chat"); }}><span>{session.title}</span></button>)}</nav><div className="app-sidebar-bottom"><button className="app-profile" aria-label="Open account and workspace settings" title={user.displayName?.trim() || user.email || "Account"} onClick={() => navigate("Account & workspace")}><span>{user.displayName?.trim() || user.email || "Account"}</span></button></div></aside>
    <div inert={mobileSidebar && sidebarOpen} className={`app-frame ${contextOpen ? "context-open" : ""}`}>
    {error && !loadErrorDismissed && <div className="workspace-load-strip" role="alert"><span>{data ? `Could not update. Showing saved account from ${time(data.as_of)} IST.` : "Could not load your account."}</span><button className="text-button retry-link" onClick={() => { setRefresh(value => value + 1); }}>Retry</button><button className="text-button dismiss-load-error" aria-label="Dismiss workspace error" onClick={() => setLoadErrorDismissed(true)}>&times;</button></div>}
    {contextOpen && <aside className="app-context" aria-label="Workspace context"><div className="panelhead"><h2>Discover</h2><button className="text-button" aria-label="Close workspace context" onClick={() => { setContextOpen(false); contextTrigger.current?.focus(); }}>&times;</button></div><section><p className="eyebrow">NEWS</p><h3>Market headlines</h3><p>Headlines are not available in this panel yet.</p><button className="text-button" onClick={() => { setContextOpen(false); navigate("Chat"); }}>Ask SWAN about market news <Icon name="arrow" /></button></section><section><p className="eyebrow">INSIGHTS</p><h3>{data ? data.account.enabled ? "Following your mandate" : "New entries are paused" : "Account insights unavailable"}</h3><p>Review the evidence behind recorded decisions.</p><button className="text-button" onClick={() => { setContextOpen(false); navigate("Decisions"); }}>Explore decisions <Icon name="arrow" /></button></section><section><p className="eyebrow">LEARNING</p><h3>Learn through the market</h3><p>Open a contract to explore its chart, indicators and risk with SWAN.</p><button className="text-button" onClick={() => { setContextOpen(false); navigate("Option chain"); }}>Explore Trade <Icon name="arrow" /></button></section></aside>}
    <div className={`app-content ${tab === "Chat" ? "app-content-chat" : tab === "Option chain" ? "app-content-trade" : ""}`}>
    <header className="app-topbar"><button ref={sidebarTrigger} className="sidebar-open text-button" aria-label="Open sidebar" aria-controls="swan-navigation" aria-expanded={sidebarOpen} onClick={() => { setContextOpen(false); setSidebarOpen(true); }}><Icon name="panel" /></button><button ref={contextTrigger} className="app-context-button text-button" aria-label={contextOpen ? "Close workspace context" : "Open workspace context"} aria-expanded={contextOpen} onClick={() => setContextOpen(value => !value)}><Icon name="panel" /></button></header>
    {dashboardPage && <nav className="workspace-subnav" aria-label="Dashboard views">{[ ["Overview", "Overview"], ["Trades", "Trades"], ["Decisions", "Decisions"], ["History", "History"] ].map(([name,label]) => <button key={name} className="text-button" aria-current={tab === name ? "page" : undefined} onClick={() => navigate(name)}>{label}</button>)}</nav>}
    {settingsPage && <div className="account-heading"><div><h1>Account &amp; workspace</h1><p>{user.email ?? user.displayName}</p></div><button className="text-button" onClick={signOut}><Icon name="logout" />Sign out</button></div>}
    {settingsPage && <nav className="settings-tabs" aria-label="Account settings">{[["Account & workspace", "General"], ["Risk settings", "Risk limits"], ["Paper controls", "Trading permissions"], ["Paper validation", "Paper order access"]].map(([name, label]) => <button className="secondary" key={name} aria-current={tab === name ? "page" : undefined} onClick={() => { setSettingsTab(name); navigate(name); }}>{label}</button>)}</nav>}
    {tab === "Account & workspace" && <section className="panel account-preferences"><h2>Your account</h2><p>{user.displayName?.trim() || user.email || "Account"}</p>{user.displayName && user.email && <p className="muted">{user.email}</p>}<details className="more-settings"><summary>More settings</summary><div className="appearance-settings"><h3>Appearance</h3><p>Choose how SWAN looks on this device.</p><div className="theme-options" role="group" aria-label="Appearance">{["system", "light", "dark"].map(value => <button key={value} className="secondary" aria-pressed={theme === value} onClick={() => changeTheme(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div></div><DeviceSettings /></details></section>}

    {actionError && <p className="notice error" role="alert">{actionError}</p>}
    {feedback && <p className="notice" role="status">{feedback}</p>}
    <PaperActionStatus />
    <div hidden={tab !== "Chat"} className="chat-mount">{chats.ready && chats.sessions.map(session => <div key={session.id} hidden={chats.activeId !== session.id}><Chat request={request} ownerKey={user.uid} sessionId={session.id} active={tab === "Chat" && chats.activeId === session.id} onTitle={text => chats.title(session.id, text)} onMarket={() => navigate("Option chain")} /></div>)}</div>
      {tab === "Overview" && <>
        {confirmed && !workerOnline && data && data.positions.length > 0 && <p className="notice error" role="alert">Open trades are not being monitored. Check the background service before relying on automatic exits.</p>}
        {stale && !error && data && <p className="saved-data-strip" role="status">Saved values from {time(data.as_of)} IST · Checking for updates.</p>}
        <div className="page-heading beginner-heading"><div><p className="eyebrow">YOUR DAILY CHECK-IN</p><h1>Money. Moves. Lessons.</h1><p>See where you stand. Understand the why.</p></div><span className="market-badge">{marketLabel}</span></div>
        <PortfolioPanel ownerKey={user.uid} revision={data?.account.revision ?? 0} />
        {data ? <><DashboardIntelligence ownerKey={user.uid} request={request} readiness={ready} runtime={data.runtime} enabled={data.account.enabled} blocked={data.account.daily_blocked} stale={stale} snapshot={data.as_of} onNavigate={navigate} />
        <section className="panel"><div className="panelhead"><div><h2>Your open trades</h2><p>{data.positions.length ? "Trades still running, with their exit levels." : "No trades running right now. Take your time."}</p></div><button className="text-button" onClick={() => navigate("Trades")}>View all</button></div>{data.positions.length > 0 && <Positions rows={data.positions} data={data} workerOnline={workerOnline} stale={stale} empty="No open positions." />}</section>
        {(data.order_summary?.active_count ?? 0) > 0 && <ActiveOrders data={data} />}
        </> : <DashboardSkeleton />}
      </>}
    {tab !== "Chat" && tab !== "Account & workspace" && tab !== "Overview" && (!data ? <DashboardSkeleton /> : <>
      {stale && !error && <p className="saved-data-strip" role="status">Saved values from {time(data.as_of)} IST · {confirmed ? "Waiting for an update." : "Checking for updates."}</p>}
      {confirmed && !workerOnline && data.positions.length > 0 && <p className="notice error" role="alert">Your open positions are not being monitored. Restore the trading connection to manage automatic exits.</p>}
      {tab === "Trades" && <><FundsPanel data={data} /><ActiveOrders data={data} /><section className="panel"><div className="panelhead"><div><p className="eyebrow">YOUR OPEN TRADES</p><h2>Open trades</h2></div>{data.positions.length > 0 && <span className="status-pill">{data.positions.length} open</span>}</div><Positions rows={data.positions} data={data} workerOnline={workerOnline} stale={stale} empty="No open trades. When an order fills, you’ll see the position and its exit levels here." /></section><ExecutionHistory data={data} /></>}
      {tab === "Decisions" && <><DashboardIntelligence ownerKey={user.uid} request={request} readiness={ready} runtime={data.runtime} enabled={data.account.enabled} blocked={data.account.daily_blocked} stale={stale} snapshot={data.as_of} onNavigate={navigate} /><AgentActivity /></>}
      {tab === "Paper controls" && <PaperControls request={request} report={ready} />}
      {tab === "Paper validation" && <ValidationPanel request={request} report={ready} />}
      {tab === "System setup" && (ready ? <SystemSetup report={ready} request={request} onRefresh={() => setRefresh(value => value + 1)} /> : <section className="panel"><h2>Readiness checks unavailable</h2><p>Refresh to retrieve the backend setup report.</p></section>)}
      {tab === "Option chain" && <div className="live-market-content">
      {tab === "Option chain" && chartId && selectedContract && <ContractChart key={`${user.uid}:${chartId}`} instrument={selectedContract.instrument} reference={"reference" in selectedContract ? selectedContract.reference : chain?.reference} quoteDate={selectedContract.quote?.timestamp} quote={selectedContract.quote} statistics={"statistics" in selectedContract ? selectedContract.statistics : undefined} quoteError={chartError} quoteMaxAge={Number(data.account.config.quote_max_age_seconds)} request={request} quoteBusy={busy} onRefreshQuote={() => void refreshSelectedPrices([chartId])} marketLabel={marketLabel} onBack={returnToMarket} backLabel={marketView === "watchlist" ? "Watchlist" : marketView === "search" ? "Search" : "Option chain"} />}
      {tab === "Option chain" && chartId && !selectedContract && <section className="panel"><p>{chartError ?? "Loading contract..."}</p><button className="secondary" onClick={returnToMarket}>Back to markets</button></section>}
      {tab === "Option chain" && !chartId && <div className="market-switch market-views" aria-label="Market view">{[["chain", "Options"], ["watchlist", "Watchlist"], ["search", "Find"]].map(([value, label]) => <button key={value} aria-pressed={marketView === value} onClick={() => { setMarketView(value); window.location.hash = `markets?view=${value}`; }}>{label}</button>)}</div>}
      {tab === "Option chain" && marketView === "search" && <div hidden={chartId != null}><InstrumentSearch key={underlying} ownerKey={user.uid} watchlist={watchlist} request={request} underlying={underlying} onMarket={value => { setUnderlying(value); setChainExpiry(""); setOffset(0); setChain(null); }} onOpen={result => { setChartRecord(result); openChart(result.instrument); }} /></div>}
      {tab === "Option chain" && !chartId && watchlist.feedback && <p className="chart-feedback" role="status">{watchlist.feedback}</p>}
      {tab === "Option chain" && !chartId && marketView === "watchlist" && <Watchlist refreshing={busy} onRefresh={() => void refreshSelectedPrices(watchlist.data?.rows.filter(row => row.status === "listed").map(row => row.instrument.id) ?? [])} state={watchlist} now={now} quoteAge={Number(data.account.config.quote_max_age_seconds)} onOpen={row => { setChartRecord(row); openChart(row.instrument); }} onSearch={() => { setMarketView("search"); window.location.hash = "markets?view=search"; }} />}
      {tab === "Option chain" && !chartId && marketView === "chain" && <OptionChain sort={chainSort} onSort={value => { setChainSort(value); setOffset(0); setChain(null); }} chain={chain} error={chainError} underlying={underlying} expiry={chainExpiry} busy={busy} stale={stale} offset={offset} now={now} maxAge={Number(data.account.config.quote_max_age_seconds)} onMarket={value => { setUnderlying(value); setChainExpiry(""); setOffset(0); setChain(null); }} onExpiry={value => { setChainExpiry(value); setOffset(0); setChain(null); }} onRefresh={() => { setChainExpiry(""); setOffset(0); void refreshPrices(); }} onPage={value => { setOffset(value); setChain(null); }} onOpen={openChart} />}
      </div>}
      {tab === "History" && <><DailyReport /><section className="panel"><div className="panelhead"><h2>Closed trades</h2><button className="secondary" disabled={busy} onClick={downloadJournal}>Export CSV</button></div><p>See how each trade ended, including recorded costs.</p><ClosedJournal /></section><section className="panel"><details><summary>Cash movements</summary><p className="muted">Deposits, adjustments and other recorded account movements.</p>{!data.ledger.length ? <p>No cash movements recorded.</p> : <div className="tablewrap"><table><thead><tr><th>Time (IST)</th><th>Type</th><th>Amount</th></tr></thead><tbody>{data.ledger.map(item => <tr key={item.id}><td>{time(item.timestamp)}</td><td>{item.category}</td><td>{money(item.amount)}</td></tr>)}</tbody></table></div>}</details></section></>}
      {tab === "Risk settings" && <section className="panel"><h2>Review your complete risk policy</h2><p>Pause entries and resolve pending orders and positions before saving. Capital is preserved in the ledger; changing it requires a separate funding operation.</p><form onSubmit={saveRisk} key={data.account.revision}><fieldset disabled={busy || stale || data.account.enabled || data.positions.length > 0 || (data.order_summary?.active_count ?? 1) > 0 || data.runtime?.resume_requested}><p>Configured paper capital: <strong>{money(String(data.account.config.capital))}</strong></p><div className="riskform">
        <label>Trade risk (% of capital)<input name="trade" type="number" required min="0.01" max="100" step="0.01" defaultValue={Number(data.account.config.max_trade_risk_pct) * 100} /></label>
        <label>Daily loss limit (% of capital)<input name="daily" type="number" required min="0.01" max="100" step="0.01" defaultValue={Number(data.account.config.max_daily_loss_pct) * 100} /></label>
        <label>Maximum holding (seconds)<input name="holding" type="number" required min="1" max="300" step="1" defaultValue={Number(data.account.config.max_holding_seconds)} /></label>
        {([ ["Maximum open positions", "max_positions", 1, undefined], ["Quote maximum age (seconds)", "quote_max_age_seconds", 1, 10], ["Stop new entries before close (minutes)", "entry_cutoff_minutes", 1, undefined], ["Request flatten before close (minutes)", "flatten_minutes", 1, undefined], ["Maximum fill quantity (units)", "max_fill_quantity", 1, undefined], ["Minimum observed volume", "min_volume", 0, undefined], ["Minimum open interest", "min_oi", 0, undefined], ["Maximum spread (basis points)", "max_spread_bps", 0.01, 10000] ] as const).map(([label, key, min, max]) => <label key={key}>{label}<input name={key} type="number" required min={min} max={max} step={key === "max_spread_bps" ? "0.01" : "1"} defaultValue={Number(data.account.config[key])} /></label>)}
        </div><p className="muted">Maximum quantity must accommodate an actual whole option lot. Entry cutoff must be earlier than flatten time. Execution policy and reviewed fees are configured separately.</p><label className="checkbox-label"><input name="reviewed" type="checkbox" required />I reviewed all limits, including quantity, liquidity and session cutoffs.</label><button type="submit">Save and review policy</button></fieldset></form></section>}
    </>)}
    {settingsPage && <details className="operator-tools"><summary>Advanced operator tools</summary><p>Configuration diagnostics are intended for maintenance, not routine trading.</p><button className="secondary" onClick={() => navigate("System setup")}>Open diagnostics</button></details>}

    </div></div><nav inert={mobileSidebar && sidebarOpen} className="app-mobile-nav" aria-label="Mobile navigation">{primaryNavigation}<button aria-label="Open account and workspace settings" aria-current={["Account & workspace", "Risk settings", "Paper controls", "Paper validation", "System setup"].includes(tab) ? "page" : undefined} onClick={() => navigate(accountDestination.current)}><NavigationIcon name="account" active={["Account & workspace", "Risk settings", "Paper controls", "Paper validation", "System setup"].includes(tab)} /><span>Account</span></button></nav>
  </PaperActionProvider></main>;
}

