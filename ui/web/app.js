const statusEl = document.getElementById("status");
const updatedEl = document.getElementById("updated");
const refreshEl = document.getElementById("refresh");
const timezoneLabelEl = document.getElementById("timezone-label");
const timezoneToggleEl = document.getElementById("timezone-toggle");
const priceEl = document.getElementById("price");
const priceMetaEl = document.getElementById("price-meta");
const signalListEl = document.getElementById("latest-signals");
const signalTableEl = document.getElementById("signal-table");
const opsStartEl = document.getElementById("ops-start");
const opsSyncOnlyEl = document.getElementById("ops-sync-only");
const opsLoopOnlyEl = document.getElementById("ops-loop-only");
const opsStopEl = document.getElementById("ops-stop");
const opsMetaEl = document.getElementById("ops-meta");
const opsLogEl = document.getElementById("ops-log");
const opsStrategyListEl = document.getElementById("ops-strategy-list");
const opsProgressLabelEl = document.getElementById("ops-progress-label");
const opsProgressEtaEl = document.getElementById("ops-progress-eta");
const opsProgressFillEl = document.getElementById("ops-progress-fill");
const TIMEZONE_STORAGE_KEY = "signal_board_timezone_mode";

let refreshMs = 30000;
let latestPrice = null;
let opsRunning = false;
let selectedStrategyIds = new Set();
let refreshTimerId = null;
let timezoneMode = _loadTimezoneMode();

function _errorText(err) {
  if (err instanceof Error && err.message) return err.message;
  return String(err || "unknown error");
}

async function _readApiResponse(res) {
  const contentType = String(res.headers.get("content-type") || "").toLowerCase();
  let payload = null;
  let rawText = "";

  if (contentType.includes("application/json")) {
    try {
      payload = await res.json();
    } catch (err) {
      payload = null;
    }
  } else {
    rawText = await res.text();
    const trimmed = rawText.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        payload = JSON.parse(trimmed);
      } catch (err) {
        payload = null;
      }
    }
  }

  if (!res.ok) {
    const detail =
      (payload && (payload.error || payload.reason || payload.message)) ||
      rawText ||
      `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return payload || {};
}

async function fetchJson(path) {
  const res = await fetch(path, { cache: "no-store" });
  return _readApiResponse(res);
}

async function postJson(path, payload = {}) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  return _readApiResponse(res);
}

function _loadTimezoneMode() {
  try {
    const stored = window.localStorage.getItem(TIMEZONE_STORAGE_KEY);
    if (stored === "utc" || stored === "local") return stored;
  } catch (err) {
    // ignore storage failures
  }
  return "local";
}

function _saveTimezoneMode(mode) {
  try {
    window.localStorage.setItem(TIMEZONE_STORAGE_KEY, mode);
  } catch (err) {
    // ignore storage failures
  }
}

function _formatUtc(date) {
  return date.toISOString().replace("T", " ").replace("Z", " UTC");
}

function renderTimezoneMode() {
  if (timezoneLabelEl) {
    timezoneLabelEl.textContent = timezoneMode === "utc" ? "UTC" : "Local";
  }
  if (timezoneToggleEl) {
    timezoneToggleEl.textContent = timezoneMode === "utc" ? "ローカル表示" : "UTC表示";
  }
}

function toggleTimezoneMode() {
  timezoneMode = timezoneMode === "utc" ? "local" : "utc";
  _saveTimezoneMode(timezoneMode);
  renderTimezoneMode();
  refresh();
}

function formatTs(ts) {
  if (!ts) return "-";
  const parsed = new Date(ts);
  if (Number.isNaN(parsed.getTime())) return String(ts);
  if (timezoneMode === "utc") return _formatUtc(parsed);
  return parsed.toLocaleString();
}

function formatDuration(sec) {
  const value = Number(sec);
  if (!Number.isFinite(value) || value < 0) return "-";
  if (value < 60) return `${Math.floor(value)}s`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60);
  if (minutes < 60) return `${minutes}m ${seconds}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
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
  const ts = payload.ts ? `(${formatTs(payload.ts)})` : "";
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

function _symbolBand(symbol) {
  const text = String(symbol || "").toUpperCase();
  if (/^[A-Z]{6}$/.test(text)) {
    if (text.endsWith("JPY")) return { low: 50, high: 300 };
    return { low: 0.2, high: 5 };
  }
  return { low: 0.01, high: 100000 };
}

function _normalizePrice(value, symbol) {
  if (value === null || value === undefined || value === "") return null;
  const raw = Number(value);
  if (!Number.isFinite(raw) || raw <= 0) return null;
  const band = _symbolBand(symbol);
  const target = Math.sqrt(band.low * band.high);
  const candidates = [0.0002, 0.001, 0.002, 0.01, 0.1, 1, 10, 100];
  let best = raw;
  let bestScore = Number.POSITIVE_INFINITY;
  candidates.forEach((factor) => {
    const scaled = raw * factor;
    if (!Number.isFinite(scaled) || scaled <= 0) return;
    let score = Math.abs(Math.log(scaled / target));
    if (scaled < band.low) score += Math.abs(Math.log(band.low / scaled)) + 5;
    if (scaled > band.high) score += Math.abs(Math.log(scaled / band.high)) + 5;
    if (score < bestScore) {
      bestScore = score;
      best = scaled;
    }
  });
  return best;
}

function fmtPrice(value, symbol) {
  const normalized = _normalizePrice(value, symbol);
  if (normalized === null) return "-";
  return normalized.toFixed(3);
}

function _signalExpireMs(signal) {
  if (!signal || !signal.expire_at) return null;
  const value = new Date(signal.expire_at).getTime();
  return Number.isFinite(value) ? value : null;
}

function _signalEntryPrice(signal) {
  const symbol = signal?.symbol;
  const entry = _normalizePrice(signal?.entry, symbol);
  if (entry !== null) return entry;
  return _normalizePrice(signal?.level, symbol);
}

function _isEntryFilled(signal, price) {
  if (price === null) return false;
  const entry = _signalEntryPrice(signal);
  if (entry === null) return false;
  const direction = (signal?.direction || "").toLowerCase();
  if (direction === "short") return price <= entry;
  return price >= entry;
}

function computeStatus(signal) {
  const tsMs = _signalTimestampMs(signal);
  const expireAt = _signalExpireMs(signal);
  const now = Date.now();
  const priceNow = _normalizePrice(latestPrice, signal?.symbol);
  const filled = _isEntryFilled(signal, priceNow);

  if (!expireAt && tsMs !== null && now - tsMs > 24 * 60 * 60 * 1000) {
    return filled ? "filled" : "historical";
  }

  if (latestPrice !== null && signal.target && signal.stop) {
    const target = _normalizePrice(signal.target, signal.symbol);
    const stop = _normalizePrice(signal.stop, signal.symbol);
    const direction = (signal.direction || "").toLowerCase();
    if (priceNow !== null && target !== null && stop !== null) {
      if (direction === "short") {
        if (priceNow <= target) return "tp_hit";
        if (priceNow >= stop) return "sl_hit";
      } else {
        if (priceNow >= target) return "tp_hit";
        if (priceNow <= stop) return "sl_hit";
      }
    }
  }

  if (expireAt && now >= expireAt) return filled ? "expired" : "missed";

  if (filled) return "filled";
  if (_signalEntryPrice(signal) !== null) return "pending";
  return "active";
}

function _signalTimestampMs(signal) {
  if (!signal || !signal.ts) return null;
  const value = new Date(signal.ts).getTime();
  return Number.isFinite(value) ? value : null;
}

function _renderNoSignalsMessage(opsPayload) {
  if (!opsPayload || opsPayload.status !== "ok") {
    return "シグナルなし（ops_runtimeが無効か未設定）";
  }
  if (!opsPayload.running) {
    return "シグナルなし（ループ未起動。まず「同期+ループ開始」を押してください）";
  }
  const warnings = opsPayload.last_loop?.signal_preview?.warnings || [];
  if (Array.isArray(warnings) && warnings.length > 0) {
    return `シグナルなし（${warnings[0]}）`;
  }
  return "シグナルなし（条件未一致または最新データ不足）";
}

function renderSignals(payload, opsPayload) {
  const signals = payload.signals || [];
  const nowMs = Date.now();
  const freshWindowMs = 24 * 60 * 60 * 1000;
  const freshSignals = signals.filter((signal) => {
    const ts = _signalTimestampMs(signal);
    if (ts === null) return false;
    return nowMs - ts <= freshWindowMs;
  });
  const latest = freshSignals.slice(-5).reverse();
  signalListEl.innerHTML = "";
  signalTableEl.innerHTML = "";

  if (signals.length === 0) {
    const empty = document.createElement("li");
    empty.className = "signal-item";
    empty.innerHTML = `<strong>NO SIGNAL</strong><span>${_renderNoSignalsMessage(opsPayload)}</span>`;
    signalListEl.appendChild(empty);

    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="11">${_renderNoSignalsMessage(opsPayload)}</td>`;
    signalTableEl.appendChild(tr);
    return;
  }

  if (latest.length === 0) {
    const empty = document.createElement("li");
    empty.className = "signal-item";
    empty.innerHTML = `<strong>NO FRESH SIGNAL</strong><span>直近24hのシグナルなし（履歴 ${signals.length} 件）</span>`;
    signalListEl.appendChild(empty);
  }

  latest.forEach((signal) => {
    const li = document.createElement("li");
    li.className = "signal-item";
    const title = `${signal.strategy_id || "-"} / ${signal.symbol || "-"}`;
    const direction = (signal.direction || "-").toUpperCase();
    const level = fmtPrice(signal.level, signal.symbol);
    const entry = fmtPrice(signal.entry, signal.symbol);
    const stop = fmtPrice(signal.stop, signal.symbol);
    const target = fmtPrice(signal.target, signal.symbol);
    const expire = signal.expire_at ? formatTs(signal.expire_at) : "-";
    const status = computeStatus(signal);
    li.innerHTML = `<strong>${title}</strong><span>${direction} / level ${level}</span><span>entry ${entry} / SL ${stop} / TP ${target}</span><span>期限(TTL) ${expire} / ${status}</span>`;
    signalListEl.appendChild(li);
  });

  signals.slice().reverse().forEach((signal) => {
    const status = computeStatus(signal);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatTs(signal.ts)}</td>
      <td>${signal.strategy_id || ""}</td>
      <td>${signal.symbol || ""}</td>
      <td>${(signal.direction || "").toUpperCase()}</td>
      <td>${fmtPrice(signal.level, signal.symbol)}</td>
      <td>${fmtPrice(signal.entry, signal.symbol)}</td>
      <td>${fmtPrice(signal.stop, signal.symbol)}</td>
      <td>${fmtPrice(signal.target, signal.symbol)}</td>
      <td>${signal.expire_at ? formatTs(signal.expire_at) : "-"}</td>
      <td>${status}</td>
      <td>${signal.reason || signal.rationale || ""}</td>
    `;
    signalTableEl.appendChild(tr);
  });
}

function _strategyLabel(strategy) {
  const name = strategy?.name || strategy?.id || "";
  const id = strategy?.id || "";
  if (!id || id === name) return name || id;
  return `${name} (${id})`;
}

function _collectCheckedStrategyIds() {
  if (!opsStrategyListEl) return [];
  return Array.from(opsStrategyListEl.querySelectorAll("input[type='checkbox']:checked"))
    .map((el) => el.value)
    .filter((value) => Boolean(value));
}

function _renderStrategyChecklist(payload) {
  if (!opsStrategyListEl) return;
  const strategies = Array.isArray(payload.available_strategies) ? payload.available_strategies : [];
  const selectedFromServer = Array.isArray(payload.selected_strategy_ids)
    ? payload.selected_strategy_ids
    : [];

  if (selectedStrategyIds.size === 0 || !opsRunning) {
    selectedStrategyIds = new Set(selectedFromServer);
  }
  if (selectedStrategyIds.size === 0 && strategies.length > 0) {
    selectedStrategyIds.add(strategies[0].id);
  }

  opsStrategyListEl.innerHTML = "";
  strategies.forEach((strategy) => {
    const id = strategy.id;
    if (!id) return;
    const item = document.createElement("label");
    item.className = "ops-strategy-item";
    const opsState = String(strategy.ops_state || "default").trim().toLowerCase();
    if (opsState) {
      item.classList.add(`is-${opsState}`);
    }
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = id;
    input.checked = selectedStrategyIds.has(id);
    input.disabled = opsRunning;
    input.addEventListener("change", () => {
      const checked = _collectCheckedStrategyIds();
      selectedStrategyIds = new Set(checked);
    });
    const textWrap = document.createElement("span");
    textWrap.className = "ops-strategy-text";
    const text = document.createElement("span");
    text.className = "ops-strategy-name";
    text.textContent = _strategyLabel(strategy);
    textWrap.appendChild(text);
    const badgeLabel = String(strategy.ops_state_label || "").trim();
    if (badgeLabel) {
      const badge = document.createElement("span");
      badge.className = "ops-strategy-badge";
      badge.textContent = badgeLabel;
      textWrap.appendChild(badge);
    }
    const note = String(strategy.ops_state_note || "").trim();
    if (note) {
      item.title = note;
    }
    item.appendChild(input);
    item.appendChild(textWrap);
    opsStrategyListEl.appendChild(item);
  });
}

function renderOpsProgress(payload) {
  if (!opsProgressLabelEl || !opsProgressEtaEl || !opsProgressFillEl) return;
  const syncProgress = payload && typeof payload.sync_progress === "object" ? payload.sync_progress : null;
  const phase = payload?.phase || "idle";

  if (!syncProgress) {
    if (phase === "sync") {
      opsProgressLabelEl.textContent = "同期進捗: 準備中";
      opsProgressEtaEl.textContent = "ETA: 算出中";
      opsProgressFillEl.style.width = "1%";
      return;
    }
    opsProgressLabelEl.textContent = "同期進捗: -";
    opsProgressEtaEl.textContent = "ETA: -";
    opsProgressFillEl.style.width = "0%";
    return;
  }

  const pct = Math.max(0, Math.min(100, Number(syncProgress.progress_pct || 0)));
  const stageLabel = syncProgress.stage_label || syncProgress.stage || "同期中";
  const step = Number(syncProgress.step || 0);
  const totalSteps = Number(syncProgress.total_steps || 0);
  const stepLabel = totalSteps > 0 ? ` (${Math.max(0, step)}/${Math.max(1, totalSteps)})` : "";

  opsProgressFillEl.style.width = `${pct}%`;
  opsProgressLabelEl.textContent = `同期進捗: ${Math.round(pct)}% - ${stageLabel}${stepLabel}`;

  if (syncProgress.state === "error") {
    opsProgressEtaEl.textContent = "ETA: エラー";
    return;
  }
  if (syncProgress.state === "stopped") {
    opsProgressEtaEl.textContent = "ETA: 停止";
    return;
  }
  if (syncProgress.state === "done" || pct >= 100) {
    opsProgressEtaEl.textContent = `完了: ${formatDuration(syncProgress.elapsed_sec || 0)}`;
    return;
  }

  const etaSec = syncProgress.eta_sec;
  if (etaSec === null || etaSec === undefined) {
    opsProgressEtaEl.textContent = "ETA: 算出中";
    return;
  }
  opsProgressEtaEl.textContent = `ETA: ${formatDuration(etaSec)}`;
}

function renderOps(payload) {
  if (!opsMetaEl || !opsLogEl) return;
  if (payload.status === "disabled") {
    opsMetaEl.textContent = "状態: disabled";
    opsLogEl.textContent = "GUI側のops_runtime設定が無効です。";
    if (opsStrategyListEl) opsStrategyListEl.innerHTML = "";
    if (opsStartEl) opsStartEl.disabled = true;
    if (opsSyncOnlyEl) opsSyncOnlyEl.disabled = true;
    if (opsLoopOnlyEl) opsLoopOnlyEl.disabled = true;
    if (opsStopEl) opsStopEl.disabled = true;
    renderOpsProgress(null);
    return;
  }

  opsRunning = Boolean(payload.running);
  _renderStrategyChecklist(payload);
  renderOpsProgress(payload);

  const phase = payload.phase || "-";
  const loopCount = payload.loop_iterations ?? 0;
  const strategyManifest = payload.strategy_manifest || "-";
  const dataManifest = payload.data_manifest || "-";
  const sourceDir = payload.source_dir || "-";
  const symbols = Array.isArray(payload.symbols) ? payload.symbols.join(",") : payload.symbol || "-";
  const runSync = Boolean(payload.run_sync);
  const runLoop = Boolean(payload.run_loop);
  let runMode = "loop";
  if (runSync && runLoop) runMode = "sync+loop";
  else if (runSync && !runLoop) runMode = "sync-only";
  else if (!runSync && runLoop) runMode = "loop-only";
  const error = payload.last_error ? ` / error: ${payload.last_error}` : "";
  const syncProgress = payload.sync_progress || {};
  const syncPct = Number(syncProgress.progress_pct || 0);
  const syncText =
    phase === "sync" || syncPct > 0
      ? ` / sync=${Math.max(0, Math.min(100, Math.round(syncPct)))}%`
      : "";
  opsMetaEl.textContent = `状態: ${phase} / mode=${runMode} / running=${opsRunning} / loop=${loopCount}${syncText}${error}`;
  const logs = Array.isArray(payload.recent_logs) ? payload.recent_logs : [];
  const warnings = payload.last_loop?.signal_preview?.warnings || [];
  const allocationPayload =
    payload && typeof payload.recent_allocation_decisions === "object"
      ? payload.recent_allocation_decisions
      : null;
  const allocationSummary = allocationPayload && typeof allocationPayload.summary === "object"
    ? allocationPayload.summary
    : null;
  const allocationDecisions = allocationPayload && Array.isArray(allocationPayload.decisions)
    ? allocationPayload.decisions.slice(-3)
    : [];
  const warningLine =
    Array.isArray(warnings) && warnings.length > 0 ? [`signal_warning: ${warnings[0]}`] : [];
  const allocationLine = allocationSummary
    ? [
        `allocation: accept=${allocationSummary.accept || 0} / reject=${allocationSummary.reject || 0} / defer=${allocationSummary.defer || 0}`,
      ]
    : [];
  const allocationRecentLines = allocationDecisions.map((entry) => {
    const decision = entry.allocation_decision || {};
    const reason = decision.reason_code || entry.reason || "-";
    return `allocation_recent: ${entry.strategy_id || "-"} ${entry.status || "-"} ${reason}`;
  });
  const header = [
    `symbols: ${symbols}`,
    `provider/timeframe: ${payload.provider || "-"} / ${payload.timeframe || "-"}`,
    `strategy_manifest: ${strategyManifest}`,
    `selected_strategies: ${(payload.selected_strategy_ids || []).join(", ") || "-"}`,
    `data_manifest: ${dataManifest}`,
    `source_dir: ${sourceDir}`,
  ];
  opsLogEl.textContent = [
    ...header,
    ...allocationLine,
    ...allocationRecentLines,
    ...warningLine,
    ...(logs.length ? logs : ["ログなし"]),
  ].join("\n");
  if (opsStartEl) opsStartEl.disabled = opsRunning;
  if (opsSyncOnlyEl) opsSyncOnlyEl.disabled = opsRunning;
  if (opsLoopOnlyEl) opsLoopOnlyEl.disabled = opsRunning;
  if (opsStopEl) opsStopEl.disabled = !opsRunning;
}

async function startOpsWithMode(runSync, runLoop, buttonEl) {
  if (!opsStartEl) return;
  if (buttonEl) buttonEl.disabled = true;
  try {
    const strategyIds = _collectCheckedStrategyIds();
    if (strategyIds.length === 0) {
      opsMetaEl.textContent = "状態: start error（戦略を1つ以上選択してください）";
      if (buttonEl) buttonEl.disabled = false;
      return;
    }
    selectedStrategyIds = new Set(strategyIds);
    const startPayload = {
      strategy_ids: strategyIds,
      run_sync: Boolean(runSync),
      run_loop: Boolean(runLoop),
    };
    const payload = await postJson("/api/ops/start", startPayload);
    renderOps(payload);
  } catch (err) {
    opsMetaEl.textContent = `状態: start error（${_errorText(err)}）`;
    if (buttonEl) buttonEl.disabled = false;
  }
}

async function startOps() {
  return startOpsWithMode(true, true, opsStartEl);
}

async function startSyncOnly() {
  return startOpsWithMode(true, false, opsSyncOnlyEl);
}

async function startLoopOnly() {
  return startOpsWithMode(false, true, opsLoopOnlyEl);
}

async function stopOps() {
  if (!opsStopEl) return;
  opsStopEl.disabled = true;
  try {
    const payload = await postJson("/api/ops/stop");
    renderOps(payload);
  } catch (err) {
    opsMetaEl.textContent = `状態: stop error（${_errorText(err)}）`;
    opsStopEl.disabled = false;
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
    renderOps(ops);
    renderSignals(signals, ops);
  } catch (err) {
    statusEl.textContent = "error";
    if (opsMetaEl) {
      opsMetaEl.textContent = `状態: refresh error（${_errorText(err)}）`;
    }
  }
}

function scheduleNextRefresh() {
  if (refreshTimerId !== null) {
    clearTimeout(refreshTimerId);
  }
  refreshTimerId = window.setTimeout(async () => {
    await refresh();
    scheduleNextRefresh();
  }, refreshMs);
}

if (opsStartEl) opsStartEl.addEventListener("click", startOps);
if (opsSyncOnlyEl) opsSyncOnlyEl.addEventListener("click", startSyncOnly);
if (opsLoopOnlyEl) opsLoopOnlyEl.addEventListener("click", startLoopOnly);
if (opsStopEl) opsStopEl.addEventListener("click", stopOps);
if (timezoneToggleEl) timezoneToggleEl.addEventListener("click", toggleTimezoneMode);

renderTimezoneMode();
refresh().finally(scheduleNextRefresh);
