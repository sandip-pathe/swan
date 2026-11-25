/* All records and responses are fictional and local. No service integrations. */
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const icons = {
  chat: '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>',
  dashboard:
    '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="11" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="18" width="7" height="3" rx="1"/>',
  chart: '<path d="M4 3v17h17M8 14l4-5 4 3 5-7"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  book: '<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1v15"/>',
  settings:
    '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="m9 3-1 3-3 1-2 4 2 2v4l4 3 3-1 3 1 4-3v-4l2-2-2-4-3-1-1-3Z"/>',
  panel:
    '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
  "arrow-up": '<path d="M12 19V5m-6 6 6-6 6 6"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  shield:
    '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
};
function paintIcons() {
  $$("[data-icon]").forEach((el) => {
    el.innerHTML = `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[el.dataset.icon] || icons.info}</svg>`;
  });
}
const state = {
  page: "chat",
  scenario: "normal",
  context: false,
  instrument: 0,
  order: "none",
  paused: false,
  side: "buy",
  preview: null,
  committed: null,
  period: "today",
  chatTimer: null,
  chatGeneration: 0,
};
const contracts = [
  {
    name: "NIFTY 25,400 CE",
    index: "NIFTY",
    price: 120,
    change: "+3.63%",
    lot: 60,
  },
  {
    name: "NIFTY 25,300 PE",
    index: "NIFTY",
    price: 94.5,
    change: "−1.82%",
    lot: 60,
  },
  {
    name: "SENSEX 82,600 CE",
    index: "SENSEX",
    price: 185,
    change: "+2.41%",
    lot: 20,
  },
];
const inr = (n) =>
  "₹" +
  Number(n).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
let toastTimer;
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("#toast").hidden = true), 4500);
}
function navigate() {
  const name = location.hash.slice(1);
  state.page = ["chat", "dashboard", "trade"].includes(name) ? name : "chat";
  $$(".page").forEach((p) => (p.hidden = p.id !== `page-${state.page}`));
  $$("[data-page]").forEach((a) => {
    a.classList.toggle("active", a.dataset.page === state.page);
    if (a.dataset.page === state.page) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  $("#page-title").textContent = {
    chat: "Your conversation",
    dashboard: "Account overview",
    trade: "Trading workspace",
  }[state.page];
  $("#mobile-ticket").hidden = state.page !== "trade";
  $("#order-panel").classList.remove("open");
}
function go(page) {
  location.hash = page;
  navigate();
}
function closeContext() {
  state.context = false;
  $("#context-drawer").hidden = true;
  $("#context-toggle").setAttribute("aria-expanded", "false");
}
function showDialog(title, html) {
  $("#dialog-title").textContent = title;
  $("#dialog-body").innerHTML = html;
  $("#detail-dialog").showModal();
}
function watchlist() {
  const term = $("#instrument-search").value.trim().toLowerCase();
  const visible = contracts
    .map((c, i) => ({ ...c, i }))
    .filter((c) => c.name.toLowerCase().includes(term));
  $("#watch-items").innerHTML = visible
    .map(
      (c) =>
        `<button class="watch-item ${c.i === state.instrument ? "active" : ""}" data-contract="${c.i}" aria-pressed="${c.i === state.instrument}"><div class="row"><b>${c.name}</b><span>${inr(c.price)}</span></div><small>Example expiry <span class="positive"> · ${c.change}</span></small></button>`,
    )
    .join("");
  $("#search-empty").hidden = visible.length !== 0;
}
function drawChart() {
  const values = [
    104, 105, 103, 108, 107, 109, 106, 111, 114, 112, 117, 116, 118, 115, 119,
    118, 120, 123, 121, 124, 122, 120, 123, 121, 120, 122, 120, 121,
  ];
  let bars = "",
    line = "";
  const height = 270,
    low = 98,
    scale = 7.5;
  values.forEach((v, i) => {
    const open = i ? values[i - 1] : 102,
      close = v,
      x = 15 + i * 14,
      y = height - (Math.max(open, close) - low) * scale,
      bh = Math.max(2, Math.abs(open - close) * scale),
      color = close >= open ? "var(--positive)" : "var(--negative)";
    bars += `<g><line x1="${x + 4}" y1="${y - 9}" x2="${x + 4}" y2="${y + bh + 12}" stroke="${color}"/><rect x="${x}" y="${y}" width="8" height="${bh}" fill="${color}"/><rect x="${x}" y="${300 - ((i % 5) + 1) * 5}" width="8" height="${((i % 5) + 1) * 5}" fill="${color}" opacity=".18"/></g>`;
    line +=
      (i ? " L" : "M") + (x + 4) + " " + (height - (v - low - 1.5) * scale);
  });
  const grid = [100, 110, 120, 130]
    .map((v) => {
      const y = height - (v - low) * scale;
      return `<line x1="0" y1="${y}" x2="410" y2="${y}" stroke="var(--line)"/><text x="421" y="${y + 4}" fill="var(--muted)" font-size="10">${v}</text>`;
    })
    .join("");
  $("#price-chart").innerHTML =
    `<svg viewBox="0 0 455 310" preserveAspectRatio="none" role="img" aria-label="Fictional option-premium candles from 100 to 130 rupees with volume and DEMA line. Illustrative only.">${grid}${bars}<path d="${line}" stroke="#6583db" stroke-width="1.8" fill="none"/><line x1="0" y1="105" x2="410" y2="105" stroke="var(--accent)" stroke-dasharray="3 4" opacity=".5"/><rect x="415" y="96" width="38" height="18" rx="3" fill="var(--accent)"/><text x="420" y="109" fill="var(--on-accent)" font-size="10">120.00</text></svg>`;
}
function selectContract(i) {
  if (
    state.order !== "none" &&
    state.committed &&
    state.committed.instrument !== i
  ) {
    toast("Existing order stays attached to its original contract.");
  }
  state.instrument = i;
  state.preview = null;
  const c = contracts[i];
  $("#instrument-name").textContent = c.name;
  $("#instrument-price").textContent = inr(c.price);
  $(".instrument-heading p").textContent =
    `Example expiry · ${c.lot} units / lot · tick ₹0.05`;
  $("#limit").value = c.price;
  $("#stop").value = c.price - 5;
  $("#target").value = c.price + 10;
  $("#lots").value = 1;
  $("#attached-context span:nth-child(2)").textContent = c.name + " · 5 min";
  invalidatePreview();
  watchlist();
  updateUnits();
}
function updateUnits() {
  const n = Number($("#lots").value) || 0;
  $("#units-line").textContent =
    `${n} lot${n === 1 ? "" : "s"} = ${n * contracts[state.instrument].lot} units`;
}
function invalidatePreview() {
  state.preview = null;
  $("#order-preview").hidden = true;
  $("#order-edit").hidden = false;
  $("#preview-order").hidden = false;
  $("#submit-order").hidden = true;
  $("#edit-order").hidden = true;
  $("#order-error").textContent = "";
}
function entryBlock() {
  if (state.scenario === "holiday")
    return "The example market is closed. You can explore saved information.";
  if (state.scenario === "stale")
    return "Prices are stale. Refresh evidence before preparing a new order.";
  if (state.scenario === "exposure")
    return "Resolve the unverified exposure before considering another entry.";
  if (state.paused) return "New entries are stopped for this sample session.";
  if (state.order !== "none" && state.order !== "closed")
    return "An example order or position is already active.";
  if (state.side === "sell")
    return "Use the existing position’s exit action. This example does not open short positions.";
  return "";
}
function preview() {
  const blocked = entryBlock();
  if (blocked) {
    $("#order-error").textContent = blocked;
    return;
  }
  const lots = Number($("#lots").value),
    limit = Number($("#limit").value),
    stop = Number($("#stop").value),
    target = Number($("#target").value);
  if (
    !Number.isInteger(lots) ||
    lots < 1 ||
    lots > 2 ||
    limit <= 0 ||
    stop <= 0 ||
    stop >= limit ||
    target <= limit
  ) {
    $("#order-error").textContent =
      "Use 1–2 whole lots, a positive stop below entry, and a target above entry.";
    return;
  }
  const c = contracts[state.instrument],
    units = lots * c.lot;
  state.preview = {
    lots,
    limit,
    stop,
    target,
    units,
    instrument: state.instrument,
  };
  $("#order-preview").innerHTML =
    `<div class="preview-summary"><h3>Review your paper buy</h3><p class="small">${c.name}</p><dl><dt>Quantity</dt><dd>${lots} lot · ${units} units</dd><dt>Limit premium</dt><dd>${inr(limit)}</dd><dt>Premium required</dt><dd>${inr(limit * units)}</dd><dt>Planned stop risk</dt><dd>${inr((limit - stop) * units)}</dd><dt>Modeled round-trip costs</dt><dd>${inr(40 * lots)}</dd></dl><p class="small muted">Planned risk excludes stop slippage. This is a fictional preview, not a fill.</p></div>`;
  $("#order-preview").hidden = false;
  $("#order-edit").hidden = true;
  $("#preview-order").hidden = true;
  $("#submit-order").hidden = false;
  $("#edit-order").hidden = false;
  $("#order-error").textContent = "";
}
function submit() {
  const blocked = entryBlock();
  if (blocked) {
    invalidatePreview();
    $("#order-error").textContent = blocked;
    return;
  }
  if (!state.preview) return;
  state.committed = { ...state.preview };
  state.order = "working";
  invalidatePreview();
  renderRecords();
  toast("Example order accepted. It has not filled.");
}
function orderMarkup() {
  const p = state.committed,
    c = p ? contracts[p.instrument] : contracts[0],
    units = p?.units || 60;
  const text = {
    working: [
      "Order accepted. Awaiting a fill.",
      "Acceptance is not execution. The paper order remains working.",
      "Preview partial fill",
      "partial",
    ],
    partial: [
      `${units / 2} of ${units} units filled.`,
      "Filled units are exposure. The remaining entry quantity is still working.",
      "Preview remaining fill",
      "filled",
    ],
    filled: [
      `${units} units open · ${c.name}`,
      "Example protection active. Production must verify monitoring separately from the saved stop.",
      "Request example exit",
      "exit",
    ],
    exit: [
      "Exit requested. Exposure remains open.",
      "The exit request is recorded; its fill has not been confirmed.",
      "Preview exit fill",
      "close",
    ],
    closed: [
      "Paper position closed.",
      "Exit fills are confirmed in this fictional example. Review the original intent, price move and costs.",
      "Review this result",
      "review",
    ],
  };
  const a = text[state.order];
  if (!a) return "";
  return `<div class="record-card"><div class="row between"><b>${a[0]}</b><span class="tag">Manual · example</span></div><p>${a[1]}</p><button class="secondary" data-order-action="${a[3]}">${a[2]} →</button></div>`;
}
function renderRecords() {
  const active = ["partial", "filled", "exit"].includes(state.order),
    p = state.committed;
  const pnl =
    state.order === "closed" ? (p.target - p.limit) * p.units - 40 * p.lots : 0;
  $("#equity-value").textContent = active ? "Unavailable" : inr(100000 + pnl);
  $("#available-funds").textContent = inr(
    p && ["working", "partial", "filled", "exit"].includes(state.order)
      ? 100000 - p.limit * p.units
      : 100000 + pnl,
  );
  $("#pnl-value").textContent = active
    ? "Unavailable"
    : (pnl > 0 ? "+" : "") + inr(pnl);
  $("#exposure-value").textContent = active
    ? `${state.order === "partial" ? p.units / 2 : p.units} units`
    : "No positions";
  $("#exposure-note").textContent = active
    ? "Fresh valuation not supplied in this example"
    : "No capital currently at market risk";
  if (state.order === "none") {
    $("#account-records").innerHTML =
      '<span data-icon="layers"></span><h3>A clear desk.</h3><p>No open positions or working orders.</p>';
    $("#trade-records").innerHTML =
      '<div class="quiet-empty">Your next paper order will appear here, followed by its actual fill state.</div>';
  } else {
    $("#account-records").innerHTML = orderMarkup();
    $("#trade-records").innerHTML = orderMarkup();
  }
  $("#account-records").classList.toggle(
    "empty-record",
    state.order === "none",
  );
  paintIcons();
}
function updateScenario() {
  const s = state.scenario;
  if (!state.preview) $("#order-error").textContent = "";
  $("#session-label").innerHTML =
    `<span class="status-dot"></span> ${s === "holiday" ? "Market closed" : "Market open"} <span class="muted">· sample session</span>`;
  const alerts = {
    holiday:
      "Market holiday in this fictional session. Saved charts, reports and learning remain available.",
    stale:
      "Prices are stale. New entries are unavailable. Saved records retain their original observation times.",
    exposure:
      "Open paper exposure: position monitoring could not be verified. Inspect the position and resolve the monitoring issue.",
  };
  $("#global-alert").hidden = !alerts[s];
  $("#global-alert").textContent = alerts[s] || "";
  $("#quote-age").textContent =
    s === "stale"
      ? "Stale · last sample 09:45 IST"
      : "Sample observation · 10:05:02 IST";
  $("#entry-state").textContent = state.paused
    ? "Entries stopped"
    : s === "holiday"
      ? "Market closed"
      : s === "stale"
        ? "Data unavailable"
        : "Observing";
  $("#activity-title").textContent = state.paused
    ? "No new entries today."
    : s === "holiday"
      ? "A day away from the market."
      : s === "stale"
        ? "Waiting for usable evidence."
        : "Waiting is a decision, too.";
  $("#activity-copy").textContent = state.paused
    ? "The session stop does not liquidate positions. Position monitoring and protection need their own verified state."
    : s === "holiday"
      ? "No session in this example. Review earlier decisions or explore a concept."
      : s === "stale"
        ? "An old quote cannot support a current entry. This is missing evidence, not a strategy decision to wait."
        : "Watching NIFTY for an eligible opening-range setup. No qualifying entry has been recorded.";
  $("#stop-entries").disabled = state.paused;
  $("#stop-entries").innerHTML = state.paused
    ? "New entries stopped"
    : '<span data-icon="pause"></span>Stop new entries today';
  if (state.preview) {
    invalidatePreview();
    $("#order-error").textContent =
      "The scenario changed. Review a fresh preview before submitting.";
  }
  if (s === "exposure" && state.order === "none") {
    $("#account-records").innerHTML =
      '<div class="record-card"><b>Example exposure · 60 units</b><p>Position monitoring is unverified. This incident must remain visible across screens.</p><button class="secondary" data-action="inspect">Inspect position →</button></div>';
    $("#account-records").classList.remove("empty-record");
    $("#exposure-value").textContent = "60 units";
    $("#exposure-note").textContent = "Monitoring could not be verified";
    $("#pnl-value").textContent = "Unavailable";
    $("#equity-value").textContent = "Unavailable";
  }
  paintIcons();
}
function ask(question) {
  if (state.chatTimer) {
    toast("One sample response is already pending. Your draft is preserved.");
    return;
  }
  closeContext();
  go("chat");
  $("#welcome").hidden = true;
  const user = document.createElement("div");
  user.className = "message user-message";
  user.textContent = question;
  $("#messages").append(user);
  const reply = document.createElement("div");
  reply.className = "message assistant-message";
  reply.innerHTML =
    '<div class="assistant-label"><svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M7 22 15 9l3 8 7-5-9 13-3-8Z" fill="currentColor"/></svg> SWAN</div><div class="pending-answer">Preparing a local example response…</div>';
  $("#messages").append(reply);
  $("#chat-input").value = "";
  const generation = state.chatGeneration;
  state.chatTimer = setTimeout(() => {
    state.chatTimer = null;
    if (generation !== state.chatGeneration) return;
    const s = state.scenario;
    let title, copy, source, action;
    if (s === "failure") {
      title = "This answer couldn’t complete.";
      copy =
        "Your question is preserved below. Your charts and account records are still available. This failure does not change trading permissions or stop position management.";
      source = "Example failure state. No provider or AI request was made.";
      action =
        '<button data-action="retry-answer">Retry answer</button><button data-action="account">View account</button>';
      $("#chat-input").value = question;
    } else if (/vwap|spread|explain|understand/i.test(question)) {
      title = /spread/i.test(question)
        ? "The cost hiding between two prices."
        : "A price with a little more context.";
      copy = /spread/i.test(question)
        ? "The bid is what someone currently offers to pay; the ask is what someone offers to sell for. Buying at the ask and selling at the bid can create a loss even when the market hasn’t moved. A tighter spread reduces that friction, but depth and freshness still matter."
        : "VWAP is the volume-weighted average price over a session. It gives more weight to prices where more units traded. It can help describe context, but it is not a prediction or an automatic entry instruction. Where valid volume is missing, SWAN must show VWAP as unavailable.";
      source =
        "Educational example · no current market claim. Selected chart context stays attached.";
      action = '<button data-action="inspect">Open the chart ↗</button>';
    } else if (/review|last|result/i.test(question)) {
      title = "A good review follows the whole trade.";
      copy =
        "In our fictional example, a call bought at ₹120 exited at ₹130. For 60 units that is ₹600 before ₹40 of modeled costs, or ₹560 net. It was a manual paper trade. A favorable result does not establish that the decision or strategy is repeatable.";
      source =
        "Illustrative review · original intent, execution and retrospective explanation are different records.";
      action = '<button data-action="account">View account review ↗</button>';
    } else if (/why|watch|trad|wait/i.test(question)) {
      title =
        s === "holiday"
          ? "There is no market session today."
          : s === "stale"
            ? "We don’t have usable evidence for an entry."
            : "No qualifying setup. No forced trade.";
      copy =
        s === "holiday"
          ? "This fictional session is a market holiday. SWAN can still help you inspect saved charts, review earlier decisions or learn a concept."
          : s === "stale"
            ? "The last quote is too old to justify a new entry. That is a data limitation, not a model deciding to wait. Saved records remain available with their original timestamps."
            : "SWAN is watching for an eligible opening-range setup. In this example, the recorded conditions have not produced one. Waiting is different from a failed evaluation, missing data or a rejected trade.";
      source =
        "Illustrative decision record · last example check 10:05 IST · no autonomous order submitted.";
      action =
        '<button data-action="evidence">View decision evidence</button><button data-action="inspect">Inspect the contract ↗</button>';
    } else {
      title = "Let’s make the question useful.";
      copy =
        "This playground uses a few local example answers. Try asking why SWAN is waiting, how VWAP works, what a bid–ask spread means, or how to review a paper trade. It does not call an AI service.";
      source = "Design example · supported interactions are illustrative.";
      action = '<button data-action="inspect">Explore Trade ↗</button>';
    }
    reply.innerHTML = `<div class="assistant-label"><svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M7 22 15 9l3 8 7-5-9 13-3-8Z" fill="currentColor"/></svg> SWAN</div><h2>${title}</h2><p>${copy}</p><div class="source">${source}</div><div class="answer-actions">${action}</div>`;
    reply.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, 650);
}
function reset() {
  clearTimeout(state.chatTimer);
  state.chatTimer = null;
  state.chatGeneration++;
  state.order = "none";
  state.committed = null;
  state.paused = false;
  state.scenario = "normal";
  state.period = "today";
  $("#scenario").value = "normal";
  $("#messages").replaceChildren();
  $("#welcome").hidden = false;
  $("#chat-input").value = "";
  $("#attached-context").hidden = true;
  closeContext();
  selectContract(0);
  renderRecords();
  updateScenario();
  go("chat");
  toast("Playground reset. No production state was changed.");
}
function drawDataViews() {
  $("#depth-view").innerHTML =
    "<h3>Example market depth</h3><table><thead><tr><th>Bid units</th><th>Bid ₹</th><th>Ask ₹</th><th>Ask units</th></tr></thead><tbody>" +
    [0, 1, 2, 3, 4]
      .map(
        (i) =>
          `<tr><td>${120 + i * 60}</td><td>${(119.5 - i * 0.5).toFixed(2)}</td><td>${(120 + i * 0.5).toFixed(2)}</td><td>${180 + i * 60}</td></tr>`,
      )
      .join("") +
    '</tbody></table><p class="small muted">Illustrative levels. Visible depth is not the full exchange book or a fill guarantee.</p>';
  $("#chain-view").innerHTML =
    "<h3>Example option chain</h3><table><thead><tr><th>Call ₹</th><th>Strike</th><th>Put ₹</th></tr></thead><tbody>" +
    [25200, 25300, 25400, 25500, 25600]
      .map(
        (v, i) =>
          `<tr><td>${(210 - i * 45).toFixed(2)}</td><td>${v.toLocaleString("en-IN")}</td><td>${(60 + i * 35).toFixed(2)}</td></tr>`,
      )
      .join("") +
    '</tbody></table><p class="small muted">Layout example only. No actual listed contracts or option analytics.</p>';
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.prompt) ask(b.dataset.prompt);
  if (b.dataset.contract !== undefined)
    selectContract(Number(b.dataset.contract));
  if (b.dataset.step) {
    $("#lots").value = Math.max(
      1,
      Math.min(2, Number($("#lots").value) + Number(b.dataset.step)),
    );
    invalidatePreview();
    updateUnits();
  }
  if (b.dataset.period) {
    state.period = b.dataset.period;
    $$("[data-period]").forEach((x) =>
      x.setAttribute("aria-pressed", String(x === b)),
    );
    $("#pnl-label").textContent =
      state.period === "all" ? "Net P&L since start" : "Session net P&L";
    toast(
      "This fictional dataset contains one session; both periods use those same records.",
    );
  }
  if (b.dataset.side) {
    state.side = b.dataset.side;
    $$("[data-side]").forEach((x) =>
      x.setAttribute("aria-pressed", String(x === b)),
    );
    invalidatePreview();
    if (state.side === "sell")
      $("#order-error").textContent =
        "Exit an existing position from its record; short selling is outside this example.";
  }
  if (b.dataset.view) {
    $$("[data-view]").forEach((x) =>
      x.setAttribute("aria-pressed", String(x === b)),
    );
    ["chart", "depth", "chain"].forEach(
      (v) => ($(`#${v}-view`).hidden = v !== b.dataset.view),
    );
  }
  switch (b.dataset.action) {
    case "inspect":
      go("trade");
      break;
    case "account":
      go("dashboard");
      break;
    case "ask-contract":
      $("#attached-context").hidden = false;
      ask("Explain this contract and its bid-ask spread.");
      break;
    case "evidence":
      showDialog(
        "Why the example waited",
        '<p>No qualifying trigger was recorded. This is not a provider failure or an expired opportunity.</p><dl><dt>Assessment</dt><dd>No setup</dd><dt>Example check</dt><dd>10:05 IST</dd><dt>Order submitted</dt><dd>No</dd></dl><p class="small muted">Fictional evidence for layout review only.</p>',
      );
      break;
    case "retry-answer":
      ask($("#chat-input").value || "Why is SWAN waiting?");
      break;
  }
  switch (b.dataset.orderAction) {
    case "partial":
      state.order = "partial";
      renderRecords();
      break;
    case "filled":
      state.order = "filled";
      renderRecords();
      break;
    case "exit":
      state.order = "exit";
      renderRecords();
      toast("Example exit requested. Position remains open until the fill.");
      break;
    case "close":
      state.order = "closed";
      renderRecords();
      toast("Example exit filled. Review the result on Dashboard.");
      break;
    case "review":
      go("dashboard");
      showDialog(
        "The example result",
        `<p>${contracts[state.committed.instrument].name} · manual paper trade</p><dl><dt>Entry / exit</dt><dd>${inr(state.committed.limit)} / ${inr(state.committed.target)}</dd><dt>Units</dt><dd>${state.committed.units}</dd><dt>Modeled costs</dt><dd>${inr(40 * state.committed.lots)}</dd></dl><p>Review the original rationale separately from the outcome. This example proves no strategy performance.</p>`,
      );
      break;
  }
});
$("#chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const question = $("#chat-input").value.trim();
  if (question) ask(question);
});
$("#chat-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("#chat-form").requestSubmit();
  }
});
$("#new-chat").addEventListener("click", () => {
  clearTimeout(state.chatTimer);
  state.chatTimer = null;
  state.chatGeneration++;
  $("#messages").replaceChildren();
  $("#welcome").hidden = false;
  $("#chat-input").value = "";
  $("#attached-context").hidden = true;
  go("chat");
  $("#chat-input").focus();
});
$("#remove-context").addEventListener(
  "click",
  () => ($("#attached-context").hidden = true),
);
$("#context-toggle").addEventListener("click", () => {
  state.context = !state.context;
  $("#context-drawer").hidden = !state.context;
  $("#context-toggle").setAttribute("aria-expanded", String(state.context));
  if (state.context) $("#close-context").focus();
});
$("#close-context").addEventListener("click", () => {
  closeContext();
  $("#context-toggle").focus();
});
$("#scenario").addEventListener("change", (e) => {
  state.scenario = e.target.value;
  renderRecords();
  updateScenario();
});
$("#reset").addEventListener("click", reset);
$("#instrument-search").addEventListener("input", watchlist);
["lots", "limit", "stop", "target"].forEach((id) =>
  $("#" + id).addEventListener("input", () => {
    invalidatePreview();
    updateUnits();
  }),
);
$("#preview-order").addEventListener("click", preview);
$("#submit-order").addEventListener("click", submit);
$("#edit-order").addEventListener("click", invalidatePreview);
$("#stop-entries").addEventListener("click", () => {
  state.paused = true;
  invalidatePreview();
  updateScenario();
  toast("Example session stop recorded. Existing positions are not closed.");
});
$("#mobile-ticket").addEventListener("click", () => {
  $("#order-panel").classList.add("open");
  $("#order-panel").setAttribute("role", "dialog");
  $("#order-panel").setAttribute("aria-modal", "true");
  $("#order-panel").setAttribute("aria-label", "Paper order ticket");
  $("#close-ticket").focus();
});
function closeTicket() {
  $("#order-panel").classList.remove("open");
  $("#order-panel").removeAttribute("role");
  $("#order-panel").removeAttribute("aria-modal");
  $("#mobile-ticket").focus();
}
$("#close-ticket").addEventListener("click", closeTicket);
$("#close-dialog").addEventListener("click", () => $("#detail-dialog").close());
$("#profile").addEventListener("click", () =>
  showDialog(
    "Workspace preferences",
    '<p>Appearance follows your system by default. This playground stores no credentials or account data.</p><label>Appearance <select id="theme-select"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label><p class="small muted">Account configuration and provider diagnostics are outside this design playground.</p>',
  ),
);
document.addEventListener("change", (e) => {
  if (e.target.id === "theme-select") {
    const v = e.target.value;
    if (v === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = v;
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if ($("#order-panel").classList.contains("open")) closeTicket();
    if (state.context) {
      closeContext();
      $("#context-toggle").focus();
    }
  }
  if (e.key === "Tab" && $("#order-panel").classList.contains("open")) {
    const items = [
      ...$("#order-panel").querySelectorAll(
        "button:not([disabled]),input:not([disabled])",
      ),
    ].filter((x) => x.getClientRects().length);
    const first = items[0],
      last = items.at(-1);
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
});
window.addEventListener("hashchange", navigate);
paintIcons();
watchlist();
drawChart();
drawDataViews();
navigate();
renderRecords();
updateScenario();
