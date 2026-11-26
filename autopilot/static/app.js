const state = { data: null, size: Number(localStorage.getItem("autopilot.size")) || 10000 };

const $ = (sel) => document.querySelector(sel);

function fmtUsd(v) {
  const abs = Math.abs(v);
  let s;
  if (abs >= 1e9) s = "$" + (v / 1e9).toFixed(2) + "B";
  else if (abs >= 1e6) s = "$" + (v / 1e6).toFixed(1) + "M";
  else if (abs >= 1e3) s = "$" + (v / 1e3).toFixed(0) + "K";
  else s = "$" + v.toFixed(0);
  return s.replace("$-", "-$");
}

function label(entry) {
  let html = entry.issuer;
  if (entry.ticker) html += `<span class="tkr">${entry.ticker}</span>`;
  return html;
}

function sizeInput() {
  const el = $("#size");
  el.addEventListener("change", () => {
    state.size = Number(el.value) || 10000;
    localStorage.setItem("autopilot.size", String(state.size));
    render();
  });
}

function setStatus(msg, isError) {
  const el = $("#status");
  el.textContent = msg;
  el.className = isError ? "statusbar error" : "statusbar";
}

function consensusRow(entry, kind) {
  const div = document.createElement("div");
  div.className = "move " + (kind === "buy" ? "pos" : "neg");
  const weight = kind === "buy" ? entry.weight : entry.prev_weight;
  const copy = weight * state.size;
  const managers = kind === "buy"
    ? `${entry.managers_now} manager${entry.managers_now === 1 ? "" : "s"} holding`
    : `${entry.managers_prev} manager${entry.managers_prev === 1 ? "" : "s"} held it`;
  div.innerHTML = `
    <div class="left">
      <div class="name">${label(entry)}</div>
      <div class="meta">${managers} &middot; weight ${(weight * 100).toFixed(1)}%</div>
    </div>
    <div class="right">
      <div class="net">${kind === "buy" ? "+" : ""}${fmtUsd(entry.net)}</div>
      <div class="copy">your copy: $${copy.toFixed(0)}</div>
    </div>`;
  return div;
}

function renderConsensus(data) {
  const buys = $("#buys");
  const sells = $("#sells");
  buys.innerHTML = "";
  sells.innerHTML = "";
  const c = data.consensus || { buys: [], sells: [] };
  if (!c.buys.length) buys.innerHTML = "<p class='meta'>No data yet.</p>";
  c.buys.forEach((e) => buys.appendChild(consensusRow(e, "buy")));
  c.sells.forEach((e) => sells.appendChild(consensusRow(e, "sell")));
}

function signalLine(s) {
  const t = s.ticker ? ` (${s.ticker})` : "";
  let detail;
  if (s.action === "NEW") detail = `opened, ${fmtUsd(s.cur_value)}`;
  else if (s.action === "EXIT") detail = `sold out, was ${fmtUsd(s.prev_value)}`;
  else {
    const pctTxt = (s.pct > 0 ? "+" : "") + (s.pct * 100).toFixed(0) + "%";
    detail = `${pctTxt} shares, now ${fmtUsd(s.cur_value)}`;
  }
  const cls = { NEW: "new", EXIT: "exit", INCREASED: "inc", REDUCED: "red" }[s.action];
  return `<div class="sig"><span class="badge ${cls}">${s.action}</span><span class="sig-name">${s.issuer}${t}</span><span class="sig-detail">${detail}</span></div>`;
}

function managerCard(m) {
  const card = document.createElement("div");
  card.className = "card";
  const topRows = (m.top || [])
    .map(
      (h) => `<tr><td>${h.issuer}${h.ticker ? ` <span class="tkr">${h.ticker}</span>` : ""}</td>
        <td class="num">${(h.weight * 100).toFixed(1)}%</td>
        <td class="num">${fmtUsd(h.value)}</td></tr>`
    )
    .join("");
  const shown = (m.signals || []).slice(0, 12);
  const signalRows = shown.length
    ? `<div class="signals">${shown.map(signalLine).join("")}</div>`
    : "<p class='mperiod'>No significant changes vs the previous filing.</p>";
  card.innerHTML = `
    <h3>${m.name}${m.stale ? ` <span class="badge exit">STALE</span>` : ""}</h3>
    <div class="mperiod">Quarter ${m.period} &middot; filed ${m.filed}${m.stale ? " &middot; no recent filing, excluded from consensus" : ""}</div>
    <div class="mval">Reported value: <b>${fmtUsd(m.total_value)}</b> across ${m.holdings_count} positions</div>
    <table><thead><tr><th>Top holdings</th><th class="num">Weight</th><th class="num">Value</th></tr></thead>
    <tbody>${topRows}</tbody></table>
    ${signalRows}`;
  return card;
}

function renderManagers(data) {
  const wrap = $("#managers");
  wrap.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "mgrid";
  (data.managers || []).forEach((m) => grid.appendChild(managerCard(m)));
  wrap.appendChild(grid);
  (data.errors || []).forEach((e) => {
    const p = document.createElement("p");
    p.className = "statusbar error";
    p.textContent = `Could not load ${e.name}: ${e.error}`;
    wrap.appendChild(p);
  });
}

function render() {
  if (!state.data) return;
  renderConsensus(state.data);
  renderManagers(state.data);
  const fetched = state.data.fetched_at_iso
    ? new Date(state.data.fetched_at_iso).toLocaleString()
    : "unknown";
  const stale = state.data.stale ? " (stale — hit Refresh)" : "";
  setStatus(`Last updated ${fetched}${stale} · auto-refreshes every 12h`);
}

let progressTimer = null;

function stopProgressPolling() {
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
}

function startProgressPolling() {
  stopProgressPolling();
  progressTimer = setInterval(async () => {
    try {
      const resp = await fetch("/api/progress");
      const p = await resp.json();
      if (p.active && p.total) {
        const now = p.current ? ` — now loading ${p.current}` : "";
        setStatus(`First run: fetched ${p.done} of ${p.total} portfolios${now} · takes about a minute`);
      }
    } catch (err) {}
  }, 1500);
}

async function load(force) {
  const btn = $("#refresh");
  btn.disabled = true;
  setStatus("Loading…");
  startProgressPolling();
  try {
    const resp = await fetch(force ? "/api/refresh" : "/api/summary", force ? { method: "POST" } : {});
    const data = await resp.json();
    if (data.error) {
      setStatus("Error: " + data.error, true);
    } else {
      state.data = data;
      render();
    }
  } catch (err) {
    setStatus("Could not reach the local server: " + err, true);
  } finally {
    stopProgressPolling();
    btn.disabled = false;
  }
}

function initTabs() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tabpane").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $("#tab-" + btn.dataset.tab).classList.add("active");
    });
  });
}

$("#refresh").addEventListener("click", () => load(true));
sizeInput();
initTabs();
load(false);
