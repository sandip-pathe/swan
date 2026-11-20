export const money = (value: string | null | undefined) => value == null || value.trim() === "" || !Number.isFinite(Number(value)) ? "Unavailable" : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(Number(value));
export const time = (value: string | null | undefined) => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour12: false }) : "Unavailable";
export const words = (value: string) => value.replaceAll("_", " ").toLowerCase();
export type Instrument = { underlying: string; expiry: string; strike: string; option_type: string; exchange: string; lot_size: number };
type EntrySource = { entry_source?: string; entry_order_id?: string | null; entry_manual_intent_id?: string | null; entry_decision_id?: string | null };
export type Position = EntrySource & { can_exit?: boolean; id: string; instrument_id: string; quantity: number; closed_quantity?: number; remaining_quantity?: number; average_price: string; stop_loss: string; target: string; opened_at: string; closed_at: string | null; realized_pnl: string | null; pending_exit: string | null };
export type Order = EntrySource & { can_cancel?: boolean; can_amend?: boolean; manual_terms?: { entry_limit: string; stop_loss: string; target: string } | null; id: string; instrument_id: string; position_id: string | null; side: string; status: string; order_type: string; quantity: number; filled_quantity: number; reason: string; timestamp: string; eligible_at: string | null; expires_at: string | null; limit_price: string | null; trigger_price: string | null; reserved_cash: string; reserved_risk: string; execution_version: string };
export type Fill = { id: string; order_id: string; instrument_id: string; side: string; quantity: number; price: string; fees: string; fee_breakdown: Record<string, string>; cost_version: string; timestamp: string | null };
export type Funds = { cash: string; available_cash: string; reserved_cash: string; reserved_pending_risk: string; restricted_proceeds: string };
export type ExecutionData = {
  funds?: Funds; instruments?: Record<string, Instrument>; orders?: Order[]; active_orders?: Order[];
  order_summary?: { active_count: number; active_truncated: boolean }; fills?: Fill[];
  order_events?: { id: string; order_id: string; kind: string; timestamp: string; payload: unknown }[];
  funds_holds?: { id: string; fill_id: string; amount: string; created_at: string; reason: string; released_at: string | null }[];
};
