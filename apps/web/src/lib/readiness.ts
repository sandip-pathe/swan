export type ReadinessCheck = {
  code: string; title: string;
  status: "passed" | "failed" | "not_checked" | "waiting_for_market" | "not_applicable";
  detail: string; action: string; checked_at: string | null; diagnostic: string | null;
};
export type Readiness = {
  checks: ReadinessCheck[]; configuration_complete: boolean; connections_verified: boolean;
  worker_online: boolean; market_state: "open" | "closed" | "unknown" | "partial";
  title: string; detail: string;
  paper_execution: { engine_ready: boolean; configuration_ready: boolean; blockers: string[];
    requirements?: { code: string; title: string; detail: string; action: string; fields: string[]; sources: string[] }[] };
};
export type ApiRequest = (path: string, method?: string, signal?: AbortSignal, body?: unknown) => Promise<unknown>;
