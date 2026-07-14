// Renderer process for Stake Mirrors Ping GUI

let isScanning = false;

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.panel).classList.add('active');
  });
});

// Error display
function showError(message) {
  const container = document.getElementById('error-container');
  const div = document.createElement('div');
  div.className = 'error';
  div.textContent = message;
  container.replaceChildren(div);
  setTimeout(() => container.replaceChildren(), 5000);
}

// Run scan
document.getElementById('run-scan-btn').addEventListener('click', async () => {
  if (isScanning) return;

  isScanning = true;
  document.getElementById('run-scan-btn').disabled = true;
  document.getElementById('stop-scan-btn').disabled = false;
  document.getElementById('scan-status').textContent = 'Scanning...';
  document.getElementById('mirrors-body').innerHTML = '<tr><td colspan="8" class="loading">Scanning mirrors...</td></tr>';

  try {
    const config = {
      rounds: parseInt(document.getElementById('rounds').value) || 3,
      timeout: parseFloat(document.getElementById('timeout').value) || 10,
      skip_geoip: document.getElementById('skip-geoip').checked,
      skip_vpn: document.getElementById('skip-vpn').checked,
      api_tests: document.getElementById('api-tests').checked,
      save_history: true,
    };

    const result = await window.electronAPI.runScan(config);

    if (result.success) {
      displayMirrors(result.mirrors);
      displayVPN(result.vpn_recommendations);
      updateDashboard(result);
      document.getElementById('scan-status').textContent = `Scan complete: ${result.scan_id}`;
    } else {
      showError(result.error);
      document.getElementById('scan-status').textContent = 'Scan failed';
    }
  } catch (error) {
    showError(error.message);
    document.getElementById('scan-status').textContent = 'Scan failed';
  } finally {
    isScanning = false;
    document.getElementById('run-scan-btn').disabled = false;
    document.getElementById('stop-scan-btn').disabled = true;
  }
});

// Stop scan
document.getElementById('stop-scan-btn').addEventListener('click', async () => {
  try {
    await window.electronAPI.stopScan();
    isScanning = false;
    document.getElementById('run-scan-btn').disabled = false;
    document.getElementById('stop-scan-btn').disabled = true;
    document.getElementById('scan-status').textContent = 'Scan stopped';
  } catch (error) {
    showError(error.message);
  }
});

// Display mirrors table
function displayMirrors(mirrors) {
  const tbody = document.getElementById('mirrors-body');
  tbody.innerHTML = '';

  mirrors.sort((a, b) => (a.best_ms || 9999) - (b.best_ms || 9999));

  mirrors.forEach((mirror, index) => {
    const row = document.createElement('tr');
    row.appendChild(cell(mirror.domain));
    row.appendChild(cell(mirror.is_up ? '✓ UP' : '✗ DOWN', mirror.is_up ? 'status-up' : 'status-down'));
    row.appendChild(cell(mirror.ip_address || '—'));
    row.appendChild(cell(mirror.server_location || '—'));
    row.appendChild(cell(formatMs(mirror.tcp_ms), getLatencyClass(mirror.tcp_ms)));
    row.appendChild(cell(formatMs(mirror.https_ms), getLatencyClass(mirror.https_ms)));
    row.appendChild(cell(formatMs(mirror.api_ms), getLatencyClass(mirror.api_ms)));
    const best = document.createElement('td');
    best.className = getLatencyClass(mirror.best_ms);
    best.innerHTML = `<strong>${formatMs(mirror.best_ms)}</strong>`;
    row.appendChild(best);
    tbody.appendChild(row);
  });
}

// Build a <td> with optional class and text (no innerHTML interpolation).
function cell(text, className) {
  const td = document.createElement('td');
  if (className) td.className = className;
  td.textContent = text;
  return td;
}

// Display VPN recommendations
function displayVPN(recommendations) {
  const tbody = document.getElementById('vpn-body');
  tbody.innerHTML = '';

  const allRecs = [];
  for (const [domain, recs] of Object.entries(recommendations)) {
    if (recs && recs.length > 0) {
      allRecs.push({ domain, ...recs[0] });
    }
  }

  allRecs.sort((a, b) => a.estimated_total_ms - b.estimated_total_ms);

  if (allRecs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="loading">No VPN recommendations available</td></tr>';
    return;
  }

  allRecs.forEach(rec => {
    const row = document.createElement('tr');
    row.appendChild(cell(rec.domain));
    row.appendChild(cell(rec.vpn_city));
    row.appendChild(cell(rec.vpn_country));
    row.appendChild(cell(formatMs(rec.estimated_total_ms), getLatencyClass(rec.estimated_total_ms)));
    tbody.appendChild(row);
  });
}

// Update dashboard stats
function updateDashboard(result) {
  const mirrors = result.mirrors;
  const upMirrors = mirrors.filter(m => m.is_up);
  const latencies = upMirrors.map(m => m.best_ms).filter(Boolean);

  document.getElementById('stat-total').textContent = mirrors.length;
  document.getElementById('stat-online').textContent = upMirrors.length;

  if (latencies.length > 0) {
    const fastest = mirrors.find(m => m.is_up && m.best_ms);
    document.getElementById('stat-fastest').textContent = fastest ? formatMs(fastest.best_ms) : '—';

    const avg = latencies.reduce((a, b) => a + b, 0) / latencies.length;
    document.getElementById('stat-avg').textContent = formatMs(avg);
  }
}

// Load history stats
document.getElementById('load-history-btn').addEventListener('click', async () => {
  try {
    const result = await window.electronAPI.getHistoryStats({ hours: 24 });

    if (result.success) {
      displayHistory(result.stats);
    } else {
      showError(result.error);
    }
  } catch (error) {
    showError(error.message);
  }
});

// Display history table
function displayHistory(stats) {
  const tbody = document.getElementById('history-body');
  tbody.innerHTML = '';

  if (stats.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="loading">No history data available</td></tr>';
    return;
  }

  stats.forEach(stat => {
    const row = document.createElement('tr');
    row.appendChild(cell(stat.domain));
    const uptimeClass = stat.uptime_pct >= 99 ? 'latency-good' : stat.uptime_pct >= 90 ? 'latency-warn' : 'latency-bad';
    row.appendChild(cell(`${stat.uptime_pct}%`, uptimeClass));
    row.appendChild(cell(formatMs(stat.avg_best_ms)));
    row.appendChild(cell(formatMs(stat.min_best_ms)));
    row.appendChild(cell(formatMs(stat.max_best_ms)));
    row.appendChild(cell(String(stat.total_checks)));
    tbody.appendChild(row);
  });
}

// Save settings
document.getElementById('save-settings-btn').addEventListener('click', async () => {
  try {
    const config = {
      ping_rounds: parseInt(document.getElementById('rounds').value),
      timeout_seconds: parseFloat(document.getElementById('timeout').value),
    };

    const result = await window.electronAPI.updateConfig(config);

    if (result.success) {
      alert('Settings saved successfully');
    } else {
      showError(result.error);
    }
  } catch (error) {
    showError(error.message);
  }
});

// Utility functions
function formatMs(ms) {
  if (ms === null || ms === undefined) return '—';
  return `${ms.toFixed(1)}ms`;
}

function getLatencyClass(ms) {
  if (ms === null || ms === undefined) return '';
  if (ms < 100) return 'latency-good';
  if (ms < 200) return 'latency-warn';
  return 'latency-bad';
}
