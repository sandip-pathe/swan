import OrderHistory from "./order-history";
import { PaperActionButton } from "./paper-action";
import type { ExecutionData, Instrument, Order, Position } from "@/lib/paper";
import { money, time, words } from "@/lib/paper";

const source = (value?: string) => value === "HUMAN" ? "Manual entry" : value === "AI" ? "Automated entry" : value === "LEGACY" ? "Earlier entry" : "Entry source unavailable";

function ContractLabel({ id, instruments }: { id: string; instruments?: Record<string, Instrument> }) {
  const item = instruments?.[id];
  return <span className="contract-label">{item ? <><strong>{item.underlying} {item.strike} {item.option_type}</strong><small>{item.expiry} · {item.exchange} · lot {item.lot_size}</small></> : <><strong>Contract details unavailable</strong><small>Refresh to load the contract name</small></>}</span>;
}

export function FundsPanel({ data }: { data: ExecutionData }) {
  const funds = data.funds;
  const cash = Number(funds?.cash);
  const available = Number(funds?.available_cash);
  const validSplit = Number.isFinite(cash) && cash > 0 && Number.isFinite(available) && available >= 0 && available <= cash;
  const availablePercent = validSplit ? Math.max(0, Math.min(100, available / cash * 100)) : 0;
  const held = validSplit ? Math.max(0, cash - available) : null;
  return <section className="panel funds-overview" aria-labelledby="funds-heading">
    <div className="funds-primary">
      <p className="eyebrow">YOUR CASH</p>
      <h2 id="funds-heading">Available to trade</h2>
      <p className="funds-amount">{money(funds?.available_cash)}</p>
      {validSplit ? <>
        <div className="funds-track" role="img" aria-label={`${availablePercent.toFixed(0)} percent of your paper cash is available to trade`}><span style={{ width: `${availablePercent}%` }} /></div>
        <p className="funds-caption">{availablePercent.toFixed(0)}% of your paper cash is available. {held! > 0 ? `${money(String(held))} is held or waiting for a release check.` : "No cash is currently held."}</p>
      </> : <p className="funds-caption">The latest cash breakdown is unavailable.</p>}
    </div>
    <details className="funds-details"><summary>See your cash breakdown</summary>
      <dl className="funds-grid">{([
        ["Total paper cash", funds?.cash], ["Held for open orders", funds?.reserved_cash], ["Sale money waiting for release", funds?.restricted_proceeds], ["Risk set aside for pending orders", funds?.reserved_pending_risk],
      ] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{money(value)}</dd></div>)}</dl>
      {data.funds_holds?.length ? <details><summary>Why is sale money held?</summary><ul className="funds-hold-list">{data.funds_holds.map(hold => <li key={hold.id}><strong>{money(hold.amount)}</strong><span>{hold.released_at ? `Released ${time(hold.released_at)} IST` : "Release not verified yet"}</span><small>{words(hold.reason)}</small></li>)}</ul></details> : null}
      <p className="muted">Money from a sale stays unavailable until its release is verified. Available cash is a balance, not permission to place an order.</p>
    </details>
  </section>;
}

export function ActiveOrders({ data }: { data: ExecutionData }) {
  return <section className="panel"><div className="panelhead"><div><p className="eyebrow">WAITING TO FILL</p><h2>Orders in progress</h2></div>{(data.order_summary?.active_count ?? 0) > 0 && <span className="status-pill">{data.order_summary!.active_count} waiting</span>}</div>
    <p className="muted">An order only becomes a trade when it fills. It can fill in parts, expire, or be cancelled.</p>
    {data.order_summary?.active_truncated && <p className="notice error" role="status">Showing the oldest 200 active orders. Additional pending orders exist; exit coverage cannot be fully assessed here.</p>}
    {data.active_orders == null ? <p className="empty-state">Orders in progress could not be loaded. Try refreshing your account.</p> : !data.active_orders.length ? <p className="empty-state">Nothing waiting to fill. New orders will show here while they’re being matched.</p> : <div className="order-list">{data.active_orders.map(order => <OrderCard key={order.id} order={order} instruments={data.instruments} />)}</div>}
  </section>;
}

function OrderCard({ order, instruments }: { order: Order; instruments?: Record<string, Instrument> }) {
  return <article className="execution-card"><div className="execution-card-head"><ContractLabel id={order.instrument_id} instruments={instruments} /><span className="status-pill">{words(order.side)} · {words(order.status)}</span></div>
    <p className="order-progress"><strong>{order.filled_quantity} / {order.quantity}</strong> units filled · {order.quantity - order.filled_quantity} remaining</p>
    <p>{words(order.order_type)} · {words(order.reason)}</p><dl className="execution-values"><div><dt>Limit</dt><dd>{order.limit_price == null ? "Not set" : money(order.limit_price)}</dd></div><div><dt>Trigger</dt><dd>{order.trigger_price == null ? "Not set" : money(order.trigger_price)}</dd></div><div><dt>Reserved cash</dt><dd>{money(order.reserved_cash)}</dd></div><div><dt>Reserved risk</dt><dd>{money(order.reserved_risk)}</dd></div></dl>
    {order.can_amend && order.manual_terms && <PaperActionButton kind="amend" id={order.id} label={instruments?.[order.instrument_id] ? `${instruments[order.instrument_id].underlying} ${instruments[order.instrument_id].strike} ${instruments[order.instrument_id].option_type}` : "Selected entry"} quantity={order.quantity} entry={order.manual_terms.entry_limit} stop_loss={order.manual_terms.stop_loss} target={order.manual_terms.target} />}{order.can_cancel && <PaperActionButton kind="cancel" id={order.id} label={instruments?.[order.instrument_id] ? `${instruments[order.instrument_id].underlying} ${instruments[order.instrument_id].strike} ${instruments[order.instrument_id].option_type}` : "Selected entry"} quantity={order.quantity - order.filled_quantity} />}<details><summary>Order details</summary><dl className="execution-values"><div><dt>Submitted (IST)</dt><dd>{time(order.timestamp)}</dd></div><div><dt>Eligible from (IST)</dt><dd>{time(order.eligible_at)}</dd></div><div><dt>Expires (IST)</dt><dd>{time(order.expires_at)}</dd></div><div><dt>Entry source</dt><dd>{source(order.entry_source)}</dd></div></dl></details><OrderHistory orderId={order.id} /></article>;
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
      {item.can_exit && !item.closed_at && <PaperActionButton kind="exit" id={item.id} label={data.instruments?.[item.instrument_id] ? `${data.instruments[item.instrument_id].underlying} ${data.instruments[item.instrument_id].strike} ${data.instruments[item.instrument_id].option_type}` : "Selected position"} quantity={item.remaining_quantity ?? item.quantity} pending={!!item.pending_exit} />}<details><summary>Position details</summary><p>{source(item.entry_source)}</p><p>Opened {time(item.opened_at)} IST{item.closed_at ? ` · Closed ${time(item.closed_at)} IST` : ""}</p></details>{item.entry_order_id && <OrderHistory orderId={item.entry_order_id} label="Entry and exit history" />}</article>;
  })}</div>;
}

export default function ExecutionHistory({ data }: { data: ExecutionData }) {
  return <>
    <section className="panel"><details className="history-disclosure"><summary>Past orders <span>{data.orders?.length ?? "Unavailable"}</span></summary><p className="muted">Your latest orders. Orders still waiting to fill are listed above.</p>{data.orders == null ? <p>Past orders could not be loaded.</p> : !data.orders.length ? <p className="empty-state">No orders yet. Your first order will show up here.</p> : <div className="order-list">{data.orders.map(order => <OrderCard key={order.id} order={order} instruments={data.instruments} />)}</div>}</details></section>
    <section className="panel"><details className="history-disclosure"><summary>Filled trades and fees <span>{data.fills?.length ?? "Unavailable"}</span></summary><p className="muted">Only filled orders appear here. Costs are included with each fill.</p>{data.fills == null ? <p>Fill history could not be loaded.</p> : !data.fills.length ? <p className="empty-state">No filled trades yet.</p> : <div className="tablewrap" tabIndex={0} role="region" aria-label="Paper fills"><table><caption className="sr-only">Paper fills and itemized fees</caption><thead><tr><th>Time (IST)</th><th>Instrument</th><th>Side</th><th>Units</th><th>Fill price</th><th>Fees</th><th>Fee details</th></tr></thead><tbody>{data.fills.map(fill => <tr key={fill.id}><td>{time(fill.timestamp)}</td><td><ContractLabel id={fill.instrument_id} instruments={data.instruments} /></td><td>{fill.side}</td><td>{fill.quantity}</td><td>{money(fill.price)}</td><td>{money(fill.fees)}</td><td><details><summary>Fee breakdown</summary><dl>{Object.entries(fill.fee_breakdown).map(([code, amount]) => <div key={code}><dt>{words(code)}</dt><dd>{money(amount)}</dd></div>)}</dl></details></td></tr>)}</tbody></table></div>}</details></section>

  </>;
}
