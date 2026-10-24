// Renderer process for Stake Mirrors Ping GUI

let isScanning = false;
let scanGeneration = 0;

// Tab switching
document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach((p) => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.panel).classList.add('active');
  });
});

// Error display
function showError(message, persistent = false) {
  const container = document.getElementById('error-container');
  const div = document.createElement('div');
  div.className = 'error';
  div.textContent = message;
  container.replaceChildren(div);
  if (!persistent) setTimeout(() => { if (div.isConnected) div.remove(); }, 5000);
}

// ----------------------------------------------------------------- helpers
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatMs(ms) {
  if (ms === null || ms === undefined) return '—';
  return `${ms.toFixed(1)}ms`;
}

// Short token for the .lat bar color: good / warn / bad / muted
function latToken(ms) {
  if (ms === null || ms === undefined) return 'muted';
  if (ms < 100) return 'good';
  if (ms < 200) return 'warn';
  return 'bad';
}

// Legacy token kept for history uptime text color (CSS .latency-*)
function getLatencyClass(ms) {
  if (ms === null || ms === undefined) return '';
  if (ms < 100) return 'latency-good';
  if (ms < 200) return 'latency-warn';
  return 'latency-bad';
}

// Inline latency value + proportional bar
function latCell(ms) {
  const wrap = el('div', `lat ${latToken(ms)}`);
  wrap.appendChild(el('span', 'val', formatMs(ms)));
  const bar = el('span', 'bar');
  const fill = el('span');
  const pct = ms == null ? 0 : Math.max(4, Math.min(100, (ms / 300) * 100));
  fill.style.width = `${pct}%`;
  bar.appendChild(fill);
  wrap.appendChild(bar);
  return wrap;
}

function statusPill(isUp, reachability = 'legacy') {
  const pill = el('span', `pill ${isUp ? 'up' : 'down'}`, reachability.replaceAll('_', ' '));
  return pill;
}

// ----------------------------------------------------------------- Run scan
const scanStatus = document.getElementById('scan-status');

document.getElementById('run-scan-btn').addEventListener('click', async () => {
  if (isScanning) return;
  isScanning = true;
  const generation = ++scanGeneration;
  document.getElementById('run-scan-btn').disabled = true;
  document.getElementById('stop-scan-btn').disabled = false;
  scanStatus.hidden = false;
  scanStatus.classList.add('live');
  scanStatus.textContent = 'Scanning';

  try {
    const config = {
      rounds: parseInt(document.getElementById('rounds').value, 10) || 3,
      timeout: parseFloat(document.getElementById('timeout').value) || 10,
      skip_geoip: document.getElementById('skip-geoip').checked,
      skip_vpn: document.getElementById('skip-vpn').checked,
      api_tests: document.getElementById('api-tests').checked,
      save_history: true,
    };

    const result = await window.electronAPI.runScan(config);

    if (generation !== scanGeneration) return;
    if (result.success) {
      displayMirrors(result.mirrors);
      displayVPN(result.vpn_recommendations);
      updateDashboard(result);
      scanStatus.classList.remove('live');
      scanStatus.textContent = `Scan complete · ${result.scan_id}`;
    } else {
      showError(result.error);
      scanStatus.classList.remove('live');
      scanStatus.textContent = 'Scan failed';
    }
  } catch (error) {
    if (generation !== scanGeneration) return;
    showError(error.message);
    scanStatus.classList.remove('live');
    scanStatus.textContent = error.message.includes('cancelled') ? 'Scan cancelled' : 'Scan failed';
  } finally {
    if (generation !== scanGeneration) return;
    isScanning = false;
    document.getElementById('run-scan-btn').disabled = false;
    document.getElementById('stop-scan-btn').disabled = true;
  }
});

document.getElementById('stop-scan-btn').addEventListener('click', async () => {
  const generation = ++scanGeneration;
  document.getElementById('run-scan-btn').disabled = true;
  document.getElementById('stop-scan-btn').disabled = true;
  scanStatus.textContent = 'Stopping scan';
  try {
    await window.electronAPI.stopScan();
    scanStatus.textContent = 'Scan cancelled';
    scanStatus.classList.remove('live');
  } catch (error) { showError(error.message); }
  finally {
    if (generation === scanGeneration) {
      isScanning = false;
      document.getElementById('run-scan-btn').disabled = false;
    }
  }
});

// ----------------------------------------------------------------- Mirrors
function displayMirrors(mirrors) {
  const tbody = document.getElementById('mirrors-body');
  tbody.replaceChildren();

  const sorted = [...mirrors].sort(
    (a, b) => (a.is_up && a.best_ms != null ? a.best_ms : Infinity) - (b.is_up && b.best_ms != null ? b.best_ms : Infinity)
  );

  sorted.forEach((mirror, index) => {
    const row = el('tr', 'row-enter');
    row.style.animationDelay = `${Math.min(index, 10) * 20}ms`;
    row.appendChild(el('td', 'mono', mirror.domain));
    const statusTd = el('td');
    statusTd.appendChild(statusPill(mirror.is_up, mirror.reachability));
    row.appendChild(statusTd);
    row.appendChild(el('td', 'mono', mirror.ip_address || '—'));
    row.appendChild(el('td', null, mirror.server_location || '—'));
    row.appendChild(td(latCell(mirror.tcp_ms)));
    row.appendChild(td(latCell(mirror.https_ms)));
    row.appendChild(td(latCell(mirror.api_ms)));
    row.appendChild(td(latCell(mirror.best_ms)));
    tbody.appendChild(row);
  });
}

function td(child) {
  const cell = el('td');
  cell.appendChild(child);
  return cell;
}

// ----------------------------------------------------------------- VPN
function displayVPN(recommendations) {
  const tbody = document.getElementById('vpn-body');
  tbody.replaceChildren();

  const allRecs = [];
  for (const [domain, recs] of Object.entries(recommendations || {})) {
    if (recs && recs.length > 0) allRecs.push({ domain, ...recs[0] });
  }
  allRecs.sort((a, b) => a.estimated_total_ms - b.estimated_total_ms);

  if (allRecs.length === 0) {
    tbody.appendChild(el('tr')).appendChild(
      el('td', 'empty', 'No VPN recommendations available')
    ).setAttribute('colspan', '5');
    return;
  }

  allRecs.forEach((rec, i) => {
    const row = el('tr');
    const rankTd = el('td');
    const rank = el('span', `rank ${i < 3 ? 'r' + (i + 1) : ''}`, String(i + 1));
    rankTd.appendChild(rank);
    row.appendChild(rankTd);
    row.appendChild(el('td', 'mono', rec.domain));
    row.appendChild(el('td', null, rec.vpn_city || '—'));
    row.appendChild(el('td', null, rec.vpn_country || '—'));
    row.appendChild(td(latCell(rec.estimated_total_ms)));
    tbody.appendChild(row);
  });
}

// ----------------------------------------------------------------- Dashboard
function updateDashboard(result) {
  const mirrors = result.mirrors || [];
  const up = mirrors.filter((m) => m.is_up);
  const latencies = up.map((m) => m.best_ms).filter(value => value != null);

  document.getElementById('stat-total').textContent = mirrors.length;
  document.getElementById('stat-online').textContent = up.length;

  if (latencies.length > 0) {
    const fastest = [...up].filter(m => m.best_ms != null).sort((a, b) => a.best_ms - b.best_ms)[0];
    document.getElementById('stat-fastest').textContent = fastest
      ? formatMs(fastest.best_ms)
      : '—';
    const avg = latencies.reduce((a, b) => a + b, 0) / latencies.length;
    document.getElementById('stat-avg').textContent = formatMs(avg);

    const spread = [...latencies].sort((a, b) => a - b);
    drawSpark(document.getElementById('stat-spark'), spread);
  } else {
    document.getElementById('stat-fastest').textContent = '—';
    document.getElementById('stat-avg').textContent = '—';
    drawSpark(document.getElementById('stat-spark'), []);
  }
}

// Dependency-free SVG sparkline (no external libs / network)
function drawSpark(svg, values) {
  if (!values.length) {
    svg.replaceChildren();
    return;
  }
  const W = 200;
  const H = 34;
  const pad = 3;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1 || 1)) * (W - 2 * pad);
    const y = H - pad - ((v - min) / range) * (H - 2 * pad);
    return [x, y];
  });
  const d = 'M' + pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' L');
  const last = pts[pts.length - 1];
  svg.innerHTML =
    `<path class="line" d="${d}"></path>` +
    `<circle class="dot" cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="2.6"></circle>`;
}

// ----------------------------------------------------------------- History
document.getElementById('load-history-btn').addEventListener('click', async () => {
  try {
    const result = await window.electronAPI.getHistoryStats({ hours: 24 });
    if (result.success) displayHistory(result.stats);
    else showError(result.error);
  } catch (error) {
    showError(error.message);
  }
});

function displayHistory(stats) {
  const tbody = document.getElementById('history-body');
  tbody.replaceChildren();

  if (!stats || stats.length === 0) {
    tbody.appendChild(el('tr')).appendChild(
      el('td', 'empty', 'No history data available')
    ).setAttribute('colspan', '6');
    return;
  }

  stats.forEach((stat) => {
    const row = el('tr');
    row.appendChild(el('td', 'mono', stat.domain));

    const upTd = el('td');
    const up = el('div', 'uptime');
    const txt = el('span', getLatencyClass(stat.uptime_pct), `${stat.uptime_pct}%`);
    const track = el('span', 'track');
    const fill = el('span');
    fill.style.width = `${Math.max(2, Math.min(100, stat.uptime_pct))}%`;
    track.appendChild(fill);
    up.append(txt, track);
    upTd.appendChild(up);
    row.appendChild(upTd);

    row.appendChild(el('td', 'mono', formatMs(stat.avg_best_ms)));
    row.appendChild(el('td', 'mono', formatMs(stat.min_best_ms)));
    row.appendChild(el('td', 'mono', formatMs(stat.max_best_ms)));
    row.appendChild(el('td', 'mono', String(stat.total_checks)));
    tbody.appendChild(row);
  });
}

// ----------------------------------------------------------------- Settings
document.getElementById('save-settings-btn').addEventListener('click', async () => {
  try {
    const config = {
      ping_rounds: parseInt(document.getElementById('rounds').value, 10),
      timeout_seconds: parseFloat(document.getElementById('timeout').value),
    };
    const result = await window.electronAPI.updateConfig(config);
    if (result.success) {
      const btn = document.getElementById('save-settings-btn');
      const original = btn.textContent;
      btn.textContent = '✓ Saved';
      setTimeout(() => (btn.textContent = original), 1500);
    } else {
      showError(result.error);
    }
  } catch (error) {
    showError(error.message);
  }
});

// Range slider value readouts
function bindRange(id) {
  const input = document.getElementById(id);
  const out = document.getElementById(`${id}-val`);
  const update = () => (out.textContent = input.value);
  input.addEventListener('input', update);
  update();
}
bindRange('rounds');
bindRange('timeout');

// Load canonical configuration and surface runtime prerequisites before enabling scans.
document.getElementById('run-scan-btn').disabled = true;
window.electronAPI.getConfig().then(result => {
  if (!result.success) throw new Error(result.error || 'Configuration could not load');
  document.getElementById('inventory-count').textContent = `${result.config.mirrors.length} configured destinations · application identity unverified`;
  document.getElementById('stat-total').textContent = result.config.mirrors.length;
  for (const [id, key] of [['rounds', 'ping_rounds'], ['timeout', 'timeout_seconds']]) {
    const value = result.config.settings?.[key];
    if (value != null) {
      const input = document.getElementById(id);
      input.value = value;
      input.dispatchEvent(new Event('input'));
    }
  }
  document.getElementById('run-scan-btn').disabled = false;
}).catch(error => {
  document.getElementById('inventory-count').textContent = 'Python runtime configuration required';
  showError(error.message, true);
});
