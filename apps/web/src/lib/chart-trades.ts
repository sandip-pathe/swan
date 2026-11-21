import type { Candles, Timeframe } from "./chart-data";

export type TradeFill = { id: string; order_id: string; side: string; quantity: number; price: string; timestamp: string };
export type PendingTradeOrder = { id: string; position_id: string | null; side: string; status: string; order_type: string; quantity_remaining: number; timestamp: string; trigger_price: string | null; limit_price: string | null };
export type TradePosition = { id: string; entry_order_id: string; remaining_quantity: number; average_price: string; stop_loss: string; target: string; pending_exit: string | null; opened_at: string };
export type ChartTrades = { as_of: string; day: string; instrument_id: string; current_day: boolean; fills_truncated: boolean; positions_truncated: boolean; exits_truncated: boolean; pending_orders_truncated: boolean; pending_orders: PendingTradeOrder[]; fills: TradeFill[]; positions: TradePosition[]; exit_orders: { id: string; position_id: string; remaining_quantity: number; status: string; order_type: string; trigger_price: string | null; limit_price: string | null }[] };

/** Never snap a trade across a gap or outside verified candle/session coverage. */
export function tradeMarkers(data: Candles, minutes: Timeframe, fills: TradeFill[]) {
  return fills.flatMap(fill => {
    const at = Date.parse(fill.timestamp), price = Number(fill.price);
    if (!Number.isFinite(at) || !Number.isFinite(price) || price <= 0 || !["BUY", "SELL"].includes(fill.side) || at > Date.parse(data.as_of)) return [];
    const session = data.sessions.find(row => row.verified && at >= Date.parse(row.opens_at) && at < Date.parse(row.closes_at));
    if (!session) return [];
    const bar = data.bars.find(row => Date.parse(row.opens_at) >= Date.parse(session.opens_at) && at >= Date.parse(row.opens_at) && at < Math.min(Date.parse(row.opens_at) + minutes * 60000, Date.parse(session.closes_at)));
    return bar ? [{ ...fill, time: Math.floor(Date.parse(bar.opens_at) / 1000), priceValue: price }] : [];
  }).sort((a, b) => a.time - b.time || a.timestamp.localeCompare(b.timestamp) || a.id.localeCompare(b.id));
}

/** Pending orders stay visually distinct from executed fills and are plotted only in verified candle coverage. */
export function pendingOrderMarkers(data: Candles, minutes: Timeframe, orders: PendingTradeOrder[]) {
  return orders.flatMap(order => {
    const at = Date.parse(order.timestamp);
    const price = Number(order.limit_price ?? order.trigger_price);
    if (!Number.isFinite(at) || !Number.isFinite(price) || price <= 0 || !["BUY", "SELL"].includes(order.side)) return [];
    const session = data.sessions.find(row => row.verified && at >= Date.parse(row.opens_at) && at < Date.parse(row.closes_at));
    if (!session) return [];
    const bar = data.bars.find(row => Date.parse(row.opens_at) >= Date.parse(session.opens_at) && at >= Date.parse(row.opens_at) && at < Math.min(Date.parse(row.opens_at) + minutes * 60000, Date.parse(session.closes_at)));
    return bar ? [{ ...order, time: Math.floor(Date.parse(bar.opens_at) / 1000), priceValue: price }] : [];
  }).sort((a, b) => a.time - b.time || a.timestamp.localeCompare(b.timestamp) || a.id.localeCompare(b.id));
}
