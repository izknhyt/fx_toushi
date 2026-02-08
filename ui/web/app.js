const statusEl = document.getElementById("status");
const updatedEl = document.getElementById("updated");
const refreshEl = document.getElementById("refresh");
const priceEl = document.getElementById("price");
const priceMetaEl = document.getElementById("price-meta");
const signalListEl = document.getElementById("latest-signals");
const signalTableEl = document.getElementById("signal-table");
const opsStartEl = document.getElementById("ops-start");
const opsStopEl = document.getElementById("ops-stop");
const opsMetaEl = document.getElementById("ops-meta");
const opsLogEl = document.getElementById("ops-log");

let refreshMs = 30000;
let latestPrice = null;
let opsRunning = false;

async function fetchJson(path) {
  const res = await fetch(path, { cache: "no-store" });
  return await res.json();
}

async function postJson(path, payload = {}) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  return await res.json();
}

function formatTs(ts) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString();
}

function renderStatus(payload) {
  statusEl.textContent = payload.status || "unknown";
  updatedEl.textContent = formatTs(payload.server_time);
  refreshEl.textContent = `${payload.refresh_sec}s`;
  refreshMs = (payload.refresh_sec || 30) * 1000;
}

function renderPrice(payload) {
  if (payload.status !== "ok") {
    priceEl.textContent = "--";
    priceMetaEl.textContent = "取得元: 未設定";
    latestPrice = null;
    return;
  }
  const price = payload.price ?? "--";
  const ts = payload.ts ? `(${payload.ts})` : "";
  priceEl.textContent = price;
  priceMetaEl.textContent = `取得元: ${payload.source} ${ts}`;
  latestPrice = payload.price ?? null;
}

function fmtNum(value) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return value;
  return num.toFixed(3);
}

function computeStatus(signal) {
  const expireAt = signal.expire_at ? new Date(signal.expire_at).getTime() : null;
  const now = Date.now();
  if (expireAt && now >= expireAt) return "expired";
  if (latestPrice !== null && signal.target && signal.stop) {
    const price = Number(latestPrice);
    const target = Number(signal.target);
    const stop = Number(signal.stop);
    const direction = (signal.direction || "").toLowerCase();
    if (!Number.isNaN(price)) {
      if (direction === "short") {
        if (price <= target) return "tp_hit";
        if (price >= stop) return "sl_hit";
      } else {
        if (price >= target) return "tp_hit";
        if (price <= stop) return "sl_hit";
      }
    }
  }
  return "active";
}

function renderSignals(payload) {
  const signals = payload.signals || [];
  const latest = signals.slice(-5).reverse();
  signalListEl.innerHTML = "";
  latest.forEach((signal) => {
    const li = document.createElement("li");
    li.className = "signal-item";
    const title = `${signal.strategy_id || "-"} / ${signal.symbol || "-"}`;
    const direction = (signal.direction || "-").toUpperCase();
    const level = fmtNum(signal.level);
    const entry = fmtNum(signal.entry);
    const stop = fmtNum(signal.stop);
    const target = fmtNum(signal.target);
    const expire = signal.expire_at ? formatTs(signal.expire_at) : "-";
    const status = computeStatus(signal);
    li.innerHTML = `<strong>${title}</strong><span>${direction} / level ${level}</span><span>entry ${entry} / SL ${stop} / TP ${target}</span><span>期限 ${expire} / ${status}</span>`;
    signalListEl.appendChild(li);
  });

  signalTableEl.innerHTML = "";
  signals.slice().reverse().forEach((signal) => {
    const status = computeStatus(signal);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${signal.ts || ""}</td>
      <td>${signal.strategy_id || ""}</td>
      <td>${signal.symbol || ""}</td>
      <td>${(signal.direction || "").toUpperCase()}</td>
      <td>${fmtNum(signal.level)}</td>
      <td>${fmtNum(signal.entry)}</td>
      <td>${fmtNum(signal.stop)}</td>
      <td>${fmtNum(signal.target)}</td>
      <td>${signal.expire_at ? formatTs(signal.expire_at) : ""}</td>
      <td>${status}</td>
      <td>${signal.reason || signal.rationale || ""}</td>
    `;
    signalTableEl.appendChild(tr);
  });
}

function renderOps(payload) {
  if (!opsMetaEl || !opsLogEl) return;
  if (payload.status === "disabled") {
    opsMetaEl.textContent = "状態: disabled";
    opsLogEl.textContent = "GUI側のops_runtime設定が無効です。";
    if (opsStartEl) opsStartEl.disabled = true;
    if (opsStopEl) opsStopEl.disabled = true;
    return;
  }
  opsRunning = Boolean(payload.running);
  const phase = payload.phase || "-";
  const loopCount = payload.loop_iterations ?? 0;
  const error = payload.last_error ? ` / error: ${payload.last_error}` : "";
  opsMetaEl.textContent = `状態: ${phase} / running=${opsRunning} / loop=${loopCount}${error}`;
  const logs = Array.isArray(payload.recent_logs) ? payload.recent_logs : [];
  opsLogEl.textContent = logs.length ? logs.join("\n") : "ログなし";
  if (opsStartEl) opsStartEl.disabled = opsRunning;
  if (opsStopEl) opsStopEl.disabled = !opsRunning;
}

async function startOps() {
  if (!opsStartEl) return;
  opsStartEl.disabled = true;
  try {
    const payload = await postJson("/api/ops/start");
    renderOps(payload);
  } catch (err) {
    opsMetaEl.textContent = "状態: start error";
  }
}

async function stopOps() {
  if (!opsStopEl) return;
  opsStopEl.disabled = true;
  try {
    const payload = await postJson("/api/ops/stop");
    renderOps(payload);
  } catch (err) {
    opsMetaEl.textContent = "状態: stop error";
  }
}

async function refresh() {
  try {
    const [status, price, signals, ops] = await Promise.all([
      fetchJson("/api/status"),
      fetchJson("/api/price"),
      fetchJson("/api/signals?limit=100"),
      fetchJson("/api/ops/status"),
    ]);
    renderStatus(status);
    renderPrice(price);
    renderSignals(signals);
    renderOps(ops);
  } catch (err) {
    statusEl.textContent = "error";
  }
}

if (opsStartEl) opsStartEl.addEventListener("click", startOps);
if (opsStopEl) opsStopEl.addEventListener("click", stopOps);

refresh();
setInterval(refresh, refreshMs);
