"use client";

import { useEffect, useState, type FormEvent } from "react";
import type { ApiRequest, Readiness } from "@/lib/readiness";

type ConfigDocument = { name: string; revision: string; document: Record<string, unknown> | null };
const labels: Record<string, string> = { passed: "Passed", failed: "Needs attention", not_checked: "Not checked", waiting_for_market: "Waiting for market", not_applicable: "Not applicable" };
const connectionNames: Record<string, string> = { broker: "Broker account", catalog: "Available contracts", stream: "Live market prices", ai: "AI research", ai_schema: "AI response check", news: "Market news" };
const configLabels: Record<string, string> = { execution: "Execution policy and fee schedules", calendar: "Exchange calendar", news: "Permitted news sources", agents: "Agent settings" };
const time = (value: string) => new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });

export default function SystemSetup({ report, request, onRefresh }: { report: Readiness; request: ApiRequest; onRefresh: () => void }) {
  const [documents, setDocuments] = useState<ConfigDocument[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    request("/api/settings/setup", "GET", controller.signal).then(value => {
      if (!controller.signal.aborted) setDocuments((value as { documents: ConfigDocument[] }).documents);
    }).catch(() => { if (!controller.signal.aborted) setError("Unable to load setup documents. Refresh to retry."); });
    return () => controller.abort();
  }, [request]);

  async function diagnose(name: string) {
    if (busy) return;
    setBusy(name); setError(null); setFeedback(null);
    try {
      const result = await request(`/api/diagnostics/${name}`, "POST") as { detail: string; models?: string[] };
      if (result.models) setModels(result.models);
      setFeedback(result.detail); onRefresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Connection test unavailable."); }
    finally { setBusy(null); }
  }

  async function save(name: string, value: unknown) {
    if (busy) return;
    const current = documents.find(item => item.name === name);
    if (!current) { setError("Configuration is unavailable. Refresh before saving."); return; }
    setBusy(name); setError(null); setFeedback(null);
    try {
      const updated = await request(`/api/settings/setup/${name}`, "POST", undefined, { expected_revision: current.revision, document: value }) as ConfigDocument;
      setDocuments(items => items.map(item => item.name === name ? updated : item));
      setFeedback(`${configLabels[name]} saved. Relevant connection checks need to be rerun.`); onRefresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Configuration could not be saved."); }
    finally { setBusy(null); }
  }

  function saveAgents(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    void save("agents", { model: values.get("model"), daily_token_budget: Number(values.get("budget")), max_output_tokens: Number(values.get("output")), timeout_seconds: Number(values.get("timeout")) });
  }

  const agent = documents.find(item => item.name === "agents")?.document;
  const affected = (fields: string[]) => [...new Set(fields.map(field => field.split(".").at(-1)!.replaceAll("_", " ").toLowerCase()))].join(", ");
  return <>
    <section className="panel"><div className="panelhead"><div><p className="eyebrow">CONNECTIONS</p><h2>Account connections</h2><p>Connect your broker, market data, and research services.</p></div><span className="status-pill">Market {report.market_state === "unknown" ? "schedule unknown" : report.market_state}</span></div>
      <p className="muted">Check each connection before trading. Results stay valid for 15 minutes. The AI response check uses a small amount of your token budget. These checks do not place orders.</p>
      {error && <p className="notice error" role="alert">{error}</p>}
      {feedback && <p className="notice" role="status">{feedback}</p>}
      {busy && <p className="muted" role="status">{["broker", "catalog", "stream", "ai", "ai_schema", "news"].includes(busy) ? "Testing connection; this can take up to 80 seconds." : "Saving configuration…"}</p>}
      <div className="checklist">{report.checks.filter(check => check.diagnostic).map(check => <article key={check.code}>
        <span className={`check-symbol ${check.status === "passed" ? "passed" : "pending"}`} aria-hidden="true">{check.status === "passed" ? "✓" : check.status === "failed" ? "!" : "·"}</span>
        <div><h3>{connectionNames[check.diagnostic!] ?? check.title}</h3><p>{check.status === "not_checked" ? "Ready to check your connection." : check.status === "passed" ? "Connected and verified." : check.detail}</p>{check.checked_at && <p className="muted">Checked {time(check.checked_at)} IST</p>}</div>
        <div className="check-result"><span className={check.status === "passed" ? "passed" : "pending"}>{labels[check.status]}</span>{check.diagnostic && <button className="secondary" disabled={busy !== null} onClick={() => diagnose(check.diagnostic!)}>{busy === check.diagnostic ? "Testing…" : check.diagnostic === "ai_schema" ? "Check (uses tokens)" : "Check connection"}<span className="sr-only"> for {check.title}</span></button>}</div>
      </article>)}</div>
    </section>
    <details className="panel advanced-settings"><summary>Advanced trading setup</summary><p>Review execution requirements and manage imported trading settings.</p><section className="panel"><h2>Trading requirements</h2><p>These requirements come from the current execution configuration and effective fee schedules. Existing reference links do not establish that an unresolved item is verified.</p>
      {report.paper_execution.requirements == null ? <p>Detailed evidence requirements are unavailable. Refresh after the API is updated.</p> : report.paper_execution.requirements.length === 0 ? <p>Execution configuration requirements are satisfied. Actual-market validation and explicit paper arming remain separate.</p> : report.paper_execution.requirements.map(item => <details key={item.code}><summary>{item.title}</summary><p>{item.detail}</p><p className="check-action">{item.action}</p><p className="muted" style={{ overflowWrap: "anywhere" }}>Affected: {affected(item.fields)}</p>{item.sources.length > 0 && <ul>{item.sources.map((url, index) => <li key={url}><a href={url} target="_blank" rel="noopener noreferrer">Existing reference {index + 1}<span className="sr-only"> for {item.title}</span></a></li>)}</ul>}</details>)}
    </section>
    <section className="panel"><h2>Agent settings</h2><p>Use your existing server-side API key. Test OpenAI access above to retrieve available model identifiers. Model access does not prove structured-output compatibility; that remains a validation check.</p>
      <form key={JSON.stringify(agent)} onSubmit={saveAgents}><fieldset disabled={busy !== null || !documents.length}><div className="riskform">
        <label>Research model<input name="model" list="accessible-models" required pattern="[a-zA-Z0-9._:\-]+" maxLength={150} defaultValue={String(agent?.model ?? "")} autoComplete="off" /><datalist id="accessible-models">{models.map(model => <option key={model} value={model} />)}</datalist></label>
        <label>Daily token budget<input name="budget" type="number" min="1" step="1" required defaultValue={agent ? Number(agent.daily_token_budget) : undefined} /></label>
        <label>Maximum output tokens<input name="output" type="number" min="256" max="8000" step="1" required defaultValue={agent ? Number(agent.max_output_tokens) : undefined} /></label>
        <label>Request timeout (seconds)<input name="timeout" type="number" min="5" max="45" step="1" required defaultValue={agent ? Number(agent.timeout_seconds) : undefined} /></label>
      </div><p className="muted">These are explicit operating limits. A token budget is not a currency spending cap. Saving does not start agents or enable entries.</p><button type="submit">Save agent settings</button></fieldset></form>
    </section>
    <section className="panel"><h2>Trading settings</h2><p>Review and import execution assumptions, source-backed fees, verified exchange sessions or closures, and permitted news sources. Imports are validated and version checked. Saving requires paused entries and no unresolved orders or positions.</p>
      {documents.filter(item => item.name !== "agents").map(item => <details key={item.name}><summary>{configLabels[item.name]}</summary><div className="config-tools"><button className="secondary" onClick={() => {
        const url = URL.createObjectURL(new Blob([JSON.stringify(item.document, null, 2)], { type: "application/json" }));
        const link = document.createElement("a"); link.href = url; link.download = `swan-${item.name}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      }}>Download current document</button><label className="file-label">Import reviewed JSON<input type="file" accept=".json,application/json" disabled={busy !== null} onChange={async event => {
        const file = event.target.files?.[0]; event.target.value = "";
        if (!file) return;
        if (file.size > 1000000) { setError("Configuration must be smaller than 1 MB."); return; }
        try { await save(item.name, JSON.parse(await file.text())); }
        catch { setError("Select a valid JSON configuration document."); }
      }} /></label></div></details>)}
    </section></details>
  </>;
}
