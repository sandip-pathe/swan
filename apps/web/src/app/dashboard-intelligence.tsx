"use client";

import { useEffect, useState } from "react";
import type { ApiRequest, Readiness } from "@/lib/readiness";
import { time, words, money } from "@/lib/paper";
import { readSnapshot, saveSnapshot } from "@/lib/display-snapshot";

type Activity = {
  id: string;
  timestamp: string;
  stage: string;
  state: string;
  title: string;
  summary: string;
  rationale: string | null;
  concerns: string[];
};
type Records = { as_of: string; mode: string; rows: Activity[] };
type Headline = {
  id: string;
  title: string;
  source: string;
  url: string | null;
  published_at: string;
  fetched_at: string;
  provider_delay_seconds: number;
  provider_name: string;
};
type Quote = {
  id: string;
  instrument: string;
  timestamp: string;
  source: string;
  last_price: string | null;
};
type Evidence = { available: boolean; headlines: Headline[]; quotes: Quote[] };
const safeUrl = (url: string | null) => {
  try {
    const value = new URL(url ?? "");
    return ["https:", "http:"].includes(value.protocol)
      ? value.href
      : undefined;
  } catch {
    return undefined;
  }
};

export default function DashboardIntelligence({
  request,
  readiness,
  runtime,
  enabled,
  blocked,
  stale,
  snapshot,
  onNavigate,
  ownerKey,
}: {
  request: ApiRequest;
  readiness?: Readiness;
  runtime: {
    status: string;
    heartbeat: string | null;
    problem: string | null;
  } | null;
  enabled: boolean;
  blocked: boolean;
  stale: boolean;
  snapshot: string;
  onNavigate: (page: string) => void;
  ownerKey: string;
}) {
  const [saved] = useState(() =>
    readSnapshot<{ records: Records; evidence: Evidence[] }>(
      ownerKey,
      "insights",
    ),
  );
  const [records, setRecords] = useState<Records | null>(
    saved?.records ?? null,
  );
  const [evidence, setEvidence] = useState<Evidence[]>(saved?.evidence ?? []);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState(false);
  const [evidenceError, setEvidenceError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true);
    setError(false);
    setEvidenceError(false);
    async function load() {
      try {
        const result = (await request(
          "/api/paper/agent-activity?category=all&limit=12",
          "GET",
          AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]),
        )) as Records;
        if (controller.signal.aborted) return;
        if (!Array.isArray(result.rows))
          throw new Error("Invalid activity response");
        setRecords(result);
        const linked = result.rows
          .filter((row) =>
            ["analysis", "proposal", "review"].includes(row.stage),
          )
          .slice(0, 3);
        const results = await Promise.allSettled(
          linked.map((row) =>
            request(
              `/api/paper/agent-activity/${encodeURIComponent(row.id)}/evidence`,
              "GET",
              AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
            ),
          ),
        );
        if (controller.signal.aborted) return;
        const linkedEvidence = results.flatMap((item) =>
          item.status === "fulfilled" && (item.value as Evidence).available
            ? [item.value as Evidence]
            : [],
        );
        if (results.every((item) => item.status === "fulfilled")) {
          setEvidence(linkedEvidence);
          saveSnapshot(ownerKey, "insights", {
            records: result,
            evidence: linkedEvidence,
          });
        }
        setEvidenceError(results.some((item) => item.status === "rejected"));
      } catch {
        if (!controller.signal.aborted) setError(true);
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [request, refresh, ownerKey]);
  const headlines = Array.from(
    new Map(
      evidence
        .flatMap((item) => item.headlines ?? [])
        .map((row) => [row.id, row]),
    ).values(),
  )
    .sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at))
    .slice(0, 5);
  const quotes = Array.from(
    new Map(
      evidence
        .flatMap((item) => item.quotes ?? [])
        .sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp))
        .map((row) => [row.id, row]),
    ).values(),
  ).slice(0, 3);
  const status = stale
    ? "Let’s update your account"
    : blocked
      ? "Taking a trading break"
      : !enabled
        ? "Chill mode. No new trades."
        : "Trading is switched on";
  const explanation = stale
    ? "The last update is old. Check a fresh balance before making a move."
    : blocked
      ? "The daily trading block is on. Check your limits before the next session."
      : !enabled
        ? "New trades are paused. You can still explore charts and learn from past decisions."
        : "Being switched on does not mean a trade is ready. Each trade still needs to pass its checks.";
  const stages: Record<string, string> = {
    analysis: "Market reader",
    proposal: "Trade planner",
    review: "Second opinion",
    evaluation: "Decision check",
    risk: "Risk guard",
    output: "Agent update",
  };
  const outcomes: Record<string, string> = {
    wait: "Waiting",
    blocked: "Stopped by checks",
    failed: "Could not finish",
    ready: "Checks passed",
    proposed: "Idea only",
    reviewed: "Reviewed",
    analysis: "Market view",
    pending: "Still pending",
    unavailable: "Not available",
  };
  return (
    <div className="dashboard-intelligence beginner-dashboard">
      <section
        className="panel dashboard-operation simple-status"
        aria-label="SWAN operation"
      >
        <div className="simple-status-icon" aria-hidden="true">
          {stale ? "⏳" : blocked ? "✋" : !enabled ? "🌿" : "👀"}
        </div>
        <div>
          <p className="eyebrow">RIGHT NOW</p>
          <h2>{status}</h2>
          <p>{explanation}</p>
          <button
            className="text-button"
            onClick={() => onNavigate("Paper controls")}
          >
            See trading settings →
          </button>
          <details className="quiet-details">
            <summary>Check the connection & details</summary>
            <p>
              {readiness?.detail || "Trading checks have not been reported."}
            </p>
            <dl className="dashboard-facts">
              <div>
                <dt>Background service</dt>
                <dd>{runtime ? words(runtime.status) : "Not reported"}</dd>
              </div>
              <div>
                <dt>Monitoring</dt>
                <dd>
                  {stale
                    ? "Needs updating"
                    : readiness?.worker_online
                      ? "Recently reported online"
                      : "Not confirmed"}
                </dd>
              </div>
              <div>
                <dt>Last check-in</dt>
                <dd>
                  {runtime?.heartbeat
                    ? `${time(runtime.heartbeat)} IST`
                    : "Not recorded"}
                </dd>
              </div>
            </dl>
            <p className="muted">Account updated {time(snapshot)} IST</p>
            {runtime?.problem && <p>{runtime.problem}</p>}
          </details>
        </div>
      </section>
      <section className="panel" aria-label="Latest agent decisions">
        <div className="panelhead">
          <div>
            <p className="eyebrow">BEHIND THE MOVES</p>
            <h2>
              What’s the thinking? <span aria-hidden="true">🧠</span>
            </h2>
            <p>What the agents said, and why.</p>
          </div>
          <button
            className="text-button"
            disabled={busy}
            onClick={() => setRefresh((value) => value + 1)}
          >
            {busy ? "Updating..." : "Refresh"}
          </button>
        </div>
        {error && !records ? (
          <p role="status">
            Couldn’t get the latest decisions.{" "}
            <button
              className="text-button"
              onClick={() => setRefresh((value) => value + 1)}
            >
              Try again
            </button>
          </p>
        ) : !records ? (
          <div role="status" aria-label="Loading decisions">
            <div className="skeleton-line" />
            <div className="skeleton-line skeleton-subtitle" />
          </div>
        ) : (
          <>
            {error && (
              <p className="saved-data-strip">
                Could not update. Showing saved decisions.
              </p>
            )}
            <p className="muted">
              {records.mode === "OBSERVATION"
                ? "Agents are idle. These are past decisions."
                : "Saved decisions. A trade idea is not a completed trade."}
            </p>
            {!records.rows.length ? (
              <div className="friendly-empty">
                <span aria-hidden="true">🔎</span>
                <h3>No decisions yet</h3>
                <p>
                  When an agent records a decision, you’ll see its reasoning
                  here.
                </p>
                <button
                  className="text-button"
                  onClick={() => onNavigate("Option chain")}
                >
                  Explore a chart meanwhile →
                </button>
              </div>
            ) : (
              <ol className="dashboard-records decision-story">
                {records.rows.slice(0, 3).map((row, index) => (
                  <li key={row.id}>
                    <div className="story-step" aria-hidden="true">
                      {index + 1}
                    </div>
                    <div>
                      <small>
                        {stages[row.stage] ?? "Agent update"} ?{" "}
                        {time(row.timestamp)} IST
                      </small>
                      <div className="dashboard-record-heading">
                        <h3>{row.title}</h3>
                        <span className="status-pill">
                          {outcomes[row.state] ?? "Saved update"}
                        </span>
                      </div>
                      <details className="decision-why">
                        <summary>Why this decision?</summary>
                        <p>{row.rationale || row.summary}</p>
                        {row.concerns?.length > 0 && (
                          <>
                            <strong>What could go wrong?</strong>
                            <ul>
                              {row.concerns.map((text, index) => (
                                <li key={index}>{text}</li>
                              ))}
                            </ul>
                          </>
                        )}
                      </details>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </>
        )}
        <button className="text-button" onClick={() => onNavigate("Activity")}>
          See the full story →
        </button>
      </section>
      <section
        className="panel learning-bite"
        aria-label="Quick trading lesson"
      >
        <div>
          <p className="eyebrow">ONE-MINUTE LEVEL UP</p>
          <h2>A good idea can still be a bad trade.</h2>
          <p>Think a price will rise? That’s only the start.</p>
        </div>
        <div className="lesson-steps">
          <div>
            <span aria-hidden="true">💡</span>
            <strong>The idea</strong>
            <p>Why might the price move?</p>
          </div>
          <div>
            <span aria-hidden="true">🛡️</span>
            <strong>The downside</strong>
            <p>What if you’re wrong?</p>
          </div>
          <div>
            <span aria-hidden="true">💸</span>
            <strong>The cost</strong>
            <p>Do fees eat the possible gain?</p>
          </div>
        </div>
        <details>
          <summary>How does SWAN use this?</summary>
          <p>
            Analysis, a trade plan, a second review and risk checks are separate
            steps. An agent can suggest a trade that later checks reject. Even a
            trade that passes can lose money.
          </p>
          <button
            className="text-button"
            onClick={() => onNavigate("Strategy intelligence")}
          >
            Explore saved research →
          </button>
        </details>
      </section>
      <div className="dashboard-context-grid">
        <section className="panel" aria-label="News evidence">
          <div className="panelhead">
            <div>
              <p className="eyebrow">THE CONTEXT</p>
              <h2>
                On the radar <span aria-hidden="true">📰</span>
              </h2>
            </div>
          </div>
          <p className="muted">
            News the agents used earlier. Check the dates.
          </p>
          {busy && !headlines.length ? (
            <div
              className="skeleton-line"
              role="status"
              aria-label="Loading headlines"
            />
          ) : error || evidenceError ? (
            <p>Some headlines didn’t load. Tap Refresh above to try again.</p>
          ) : !headlines.length ? (
            <p>No news was linked to these decisions.</p>
          ) : null}
          <ul className="dashboard-records">
            {headlines.slice(0, 3).map((row) => (
              <li key={row.id}>
                {safeUrl(row.url) ? (
                  <a
                    href={safeUrl(row.url)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {row.title} ↗
                  </a>
                ) : (
                  <strong>{row.title}</strong>
                )}
                <p className="muted">
                  {row.source} / {time(row.published_at)} IST
                </p>
                <details>
                  <summary>Source & timing</summary>
                  <small>
                    Saved {time(row.fetched_at)} IST
                    {row.provider_delay_seconds > 0
                      ? ` ? News provider delay: ${Math.round(row.provider_delay_seconds / 3600)}h`
                      : ""}
                  </small>
                  {row.provider_name === "NewsData.io" && (
                    <small>
                      Powered by{" "}
                      <a
                        href="https://newsdata.io"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        NewsData.io API
                      </a>
                    </small>
                  )}
                </details>
              </li>
            ))}
          </ul>
        </section>
        <section className="panel" aria-label="Market observations">
          <div className="panelhead">
            <div>
              <p className="eyebrow">TAKE A CLOSER LOOK</p>
              <h2>Prices behind the idea</h2>
            </div>
          </div>
          <p className="muted">
            Prices saved with the analysis. They may have changed.
          </p>
          {busy && !quotes.length ? (
            <div
              className="skeleton-line"
              role="status"
              aria-label="Loading saved prices"
            />
          ) : error || evidenceError ? (
            <p>Some saved prices didn’t load.</p>
          ) : !quotes.length ? (
            <p>No prices were linked to these decisions.</p>
          ) : null}
          <ul className="dashboard-records">
            {quotes.map((row) => (
              <li key={row.id}>
                <strong>{row.instrument}</strong>
                <p className="saved-price">{money(row.last_price)}</p>
                <small>
                  {row.source} / {time(row.timestamp)} IST
                </small>
              </li>
            ))}
          </ul>
          <button
            className="text-button"
            onClick={() => onNavigate("Option chain")}
          >
            Explore charts →
          </button>
        </section>
      </div>
    </div>
  );
}
