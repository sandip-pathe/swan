export type MarketQuote = {
  timestamp: string; received_at?: string; source?: string;
  bid?: string | null; ask?: string | null; last_price?: string | null;
  session_open?: string | null; session_high?: string | null; session_low?: string | null;
  previous_close?: string | null; volume?: number | null; oi?: number | null;
  iv?: string | null; iv_unit?: string | null; metrics_timestamp?: string | null; metrics_source?: string | null;
};
export type QuoteStatistics = { change: string | null; change_pct: string | null; spread: string | null; spread_bps: string | null };
