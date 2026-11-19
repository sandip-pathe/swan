import type { ExecutionData, Instrument, Order, Position } from "@/lib/paper";
import { money, time, words } from "@/lib/paper";

function ContractLabel({ id, instruments }: { id: string; instruments?: Record<string, Instrument> }) {
  const item = instruments?.[id];
  return <span className="contract-label">{item ? <><strong>{item.underlying} {item.strike} {item.option_type}</strong><small>{item.expiry} · {item.exchange} · lot {item.lot_size}</small></> : <><strong>Contract details unavailable</strong><small>Refresh to load the contract name</small></>}</span>;
}

export function FundsPanel({ funds }: Pick<ExecutionData, "funds">) {
  return <section className="panel"><h2>Paper funds</h2><p className="muted">Reserved cash backs pending entries. Restricted sale proceeds stay unavailable until their release is verified.</p><dl className="funds-grid">{([
    ["Cash balance", funds?.cash], ["Reserved for entries", funds?.reserved_cash], ["Restricted proceeds", funds?.restricted_proceeds], ["Available to trade", funds?.available_cash], ["Pending risk allocation", funds?.reserved_pending_risk],
  ] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{money(value)}</dd></div>)}</dl></section>;
}

export function ActiveOrders({ data }: { data: ExecutionData }) {
  return <section className="panel"><div className="panelhead"><h2>Pending orders</h2><span className="status-pill">{data.order_summary ? `${data.order_summary.active_count} active` : "Count unavailable"}</span></div>
    <p className="muted">An accepted order is not a fill. Orders can wait for later depth, fill partially, expire or be cancelled.</p>
    {data.order_summary?.active_truncated && <p className="notice error" role="status">Showing the oldest 200 active orders. Additional pending orders exist; exit coverage cannot be fully assessed here.</p>}
    {data.active_orders == null ? <p>Pending order data is unavailable. Refresh the workspace.</p> : !data.active_orders.length ? <p className="empty-state">No pending paper orders.</p> : <div className="order-list">{data.active_orders.map(order => <OrderCard key={order.id} order={order} instruments={data.instruments} />)}</div>}
  </section>;
}

function OrderCard({ order, instruments }: { order: Order; instruments?: Record<string, Instrument> }) {
  return <article className="execution-card"><div className="execution-card-head"><ContractLabel id={order.instrument_id} instruments={instruments} /><span className="status-pill">{words(order.side)} · {words(order.status)}</span></div>
    <p className="order-progress"><strong>{order.filled_quantity} / {order.quantity}</strong> units filled · {order.quantity - order.filled_quantity} remaining</p>
    <p>{words(order.order_type)} · {words(order.reason)}</p><dl className="execution-values"><div><dt>Limit</dt><dd>{order.limit_price == null ? "Not set" : money(order.limit_price)}</dd></div><div><dt>Trigger</dt><dd>{order.trigger_price == null ? "Not set" : money(order.trigger_price)}</dd></div><div><dt>Reserved cash</dt><dd>{money(order.reserved_cash)}</dd></div><div><dt>Reserved risk</dt><dd>{money(order.reserved_risk)}</dd></div></dl>
    <details><summary>Order details</summary><dl className="execution-values"><div><dt>Submitted (IST)</dt><dd>{time(order.timestamp)}</dd></div><div><dt>Eligible from (IST)</dt><dd>{time(order.eligible_at)}</dd></div><div><dt>Expires (IST)</dt><dd>{time(order.expires_at)}</dd></div><div><dt>Execution policy</dt><dd>{order.execution_version}</dd></div></dl></details></article>;
}

export function Positions({ rows, empty, data = {}, workerOnline = false, stale = false }: { rows: Position[]; empty: string; data?: ExecutionData; workerOnline?: boolean; stale?: boolean }) {
  return !rows.length ? <p className="empty-state">{empty}</p> : <div className="position-list">{rows.map(item => {
    const exits = data.active_orders?.filter(order => order.position_id === item.id && order.side === "SELL") ?? [];
    const exitQuantity = exits.reduce((sum, order) => sum + order.quantity - order.filled_quantity, 0);
    const complete = data.active_orders != null && data.order_summary?.active_truncated === false;
    const exitRecorded = complete && item.remaining_quantity != null && item.remaining_quantity > 0 && exitQuantity >= item.remaining_quantity;
    return <article className="execution-card" key={item.id}><div className="execution-card-head"><ContractLabel id={item.instrument_id} instruments={data.instruments} /><span className="status-pill">{item.closed_at ? "Closed" : `${item.remaining_quantity ?? "Unknown"} units open`}</span></div>
      <dl className="execution-values"><div><dt>Entered units</dt><dd>{item.quantity}</dd></div><div><dt>Closed units</dt><dd>{item.closed_quantity ?? "Unavailable"}</dd></div><div><dt>Remaining units</dt><dd>{item.remaining_quantity ?? "Unavailable"}</dd></div><div><dt>Average entry</dt><dd>{money(item.average_price)}</dd></div><div><dt>Stop</dt><dd>{money(item.stop_loss)}</dd></div><div><dt>Target</dt><dd>{money(item.target)}</dd></div><div><dt>Realized P&amp;L</dt><dd>{money(item.realized_pnl)}</dd></div></dl>
      {!item.closed_at && <p className={`position-protection ${stale || !workerOnline || !exitRecorded || item.pending_exit ? "needs-attention" : ""}`}>{stale ? "Position data is stale · exit coverage unverified" : !workerOnline ? "Worker disconnected · exit monitoring unavailable" : item.pending_exit ? `Exit requested · ${words(item.pending_exit)}` : !complete ? "Exit order coverage unavailable" : exitRecorded ? "Exit order recorded · execution still requires fresh depth" : "No full-quantity exit order recorded"}</p>}
      <details><summary>Position details</summary><p>Opened {time(item.opened_at)} IST{item.closed_at ? ` · Closed ${time(item.closed_at)} IST` : ""}</p></details></article>;
  })}</div>;
}

export default function ExecutionHistory({ data }: { data: ExecutionData }) {
  return <>
    <section className="panel"><h2>Recent orders</h2><p className="muted">Most recent 50 orders. Pending orders are listed separately above.</p>{data.orders == null ? <p>Order history unavailable.</p> : !data.orders.length ? <p className="empty-state">No recorded paper orders.</p> : <details><summary>View recent order history</summary><div className="order-list">{data.orders.map(order => <OrderCard key={order.id} order={order} instruments={data.instruments} />)}</div></details>}</section>
    <section className="panel"><h2>Recent fills and fees</h2><p className="muted">Your latest completed paper trades, including fees.</p>{data.fills == null ? <p>Fill history unavailable.</p> : !data.fills.length ? <p className="empty-state">No recorded paper fills.</p> : <div className="tablewrap" tabIndex={0} role="region" aria-label="Paper fills"><table><caption className="sr-only">Paper fills and itemized fees</caption><thead><tr><th>Time (IST)</th><th>Instrument</th><th>Side</th><th>Units</th><th>Fill price</th><th>Fees</th><th>Fee details</th></tr></thead><tbody>{data.fills.map(fill => <tr key={fill.id}><td>{time(fill.timestamp)}</td><td><ContractLabel id={fill.instrument_id} instruments={data.instruments} /></td><td>{fill.side}</td><td>{fill.quantity}</td><td>{money(fill.price)}</td><td>{money(fill.fees)}</td><td><details><summary>Fee breakdown</summary><dl>{Object.entries(fill.fee_breakdown).map(([code, amount]) => <div key={code}><dt>{words(code)}</dt><dd>{money(amount)}</dd></div>)}</dl></details></td></tr>)}</tbody></table></div>}</section>
    <section className="panel"><h2>Sale proceeds holds</h2><p className="muted">Up to 100 holds, with unreleased holds first. The funds summary includes all current restrictions.</p>{data.funds_holds == null ? <p>Funds hold records unavailable.</p> : !data.funds_holds.length ? <p className="empty-state">No recorded sale proceeds holds.</p> : <div className="tablewrap" tabIndex={0} role="region" aria-label="Sale proceeds holds"><table><caption className="sr-only">Restricted sale proceeds and release status</caption><thead><tr><th>Created (IST)</th><th>Amount</th><th>Reason</th><th>Status</th></tr></thead><tbody>{data.funds_holds.map(hold => <tr key={hold.id}><td>{time(hold.created_at)}</td><td>{money(hold.amount)}</td><td>{words(hold.reason)}</td><td>{hold.released_at ? `Released ${time(hold.released_at)} IST` : "Restricted · release not verified"}</td></tr>)}</tbody></table></div>}</section>

  </>;
}
