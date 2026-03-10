let allServers = [];
let selectedServers = new Set();
let lastFetchedData = null;
let myChart = null;
let fetchController = null; // for aborting in-flight requests

const COLORS = [
  "#ff6a00", "#4a9eff", "#33cc66", "#ce33ce", "#ff5050",
  "#e6b800", "#66cccc", "#ff66aa", "#99ccff", "#88dd44"
];

// Assign stable colors per server name so toggling doesn't shuffle colors
const serverColorMap = new Map();
let colorIndex = 0;
function getServerColor(name) {
  if (!serverColorMap.has(name)) {
    serverColorMap.set(name, COLORS[colorIndex % COLORS.length]);
    colorIndex++;
  }
  return serverColorMap.get(name);
}

// Elements
const chipsContainer = document.getElementById('serverChips');
const searchInput = document.getElementById('searchInput');
const rollingSlider = document.getElementById('rollingSlider');
const sliderValueSpan = document.getElementById('sliderValue');
const chartLoading = document.getElementById('chartLoading');

// === Date range state ===
let activePreset = 7; // days

function getTimeRange() {
  const now = Math.floor(Date.now() / 1000);
  const afterInput = document.getElementById('afterTime').value;
  const beforeInput = document.getElementById('beforeTime').value;

  if (activePreset) {
    return {
      after: now - activePreset * 86400,
      before: now
    };
  }

  // Custom range
  const after = afterInput ? Math.floor(new Date(afterInput).getTime() / 1000) : 0;
  const before = beforeInput ? Math.floor(new Date(beforeInput).getTime() / 1000) : now;
  return { after, before };
}

// === Preset buttons ===
document.querySelectorAll('.preset').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.preset').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activePreset = parseInt(btn.dataset.days, 10);
    fetchAndRender();
  });
});

// Custom range
document.getElementById('customRangeBtn').addEventListener('click', () => {
  document.querySelectorAll('.preset').forEach(b => b.classList.remove('active'));
  activePreset = null;
  fetchAndRender();
});

// Smoothness slider
rollingSlider.addEventListener('input', () => {
  sliderValueSpan.textContent = rollingSlider.value;
  if (lastFetchedData && myChart) {
    myChart.data.datasets = buildDatasets(lastFetchedData);
    myChart.update({ duration: 300, easing: 'easeInOutCubic' });
  }
});

// Server search filter
let searchFilter = '';
searchInput.addEventListener('input', () => {
  searchFilter = searchInput.value.trim().toLowerCase();
  renderChips();
});

// === Init ===
loadServerList();

async function loadServerList() {
  try {
    const resp = await fetch("https://relay.awesome.tf/server-scoreboard");
    const data = await resp.json();
    allServers = (data.servers || []).sort((a, b) => b.score - a.score);

    // Pre-select top 3
    allServers.slice(0, 3).forEach(s => selectedServers.add(s.name));

    renderChips();
    fetchAndRender();
  } catch (e) {
    console.error("Failed to load server list:", e);
    chipsContainer.innerHTML = '<span class="chips-loading">Failed to load servers</span>';
  }
}

function renderChips() {
  chipsContainer.innerHTML = '';

  // Show selected first, then unselected; filter by search
  const filtered = allServers.filter(s =>
    !searchFilter || s.name.toLowerCase().includes(searchFilter)
  );

  // Sort: selected first, then by score
  const sorted = [...filtered].sort((a, b) => {
    const aSelected = selectedServers.has(a.name) ? 0 : 1;
    const bSelected = selectedServers.has(b.name) ? 0 : 1;
    if (aSelected !== bSelected) return aSelected - bSelected;
    return b.score - a.score;
  });

  // Cap visible chips to avoid overwhelming the bar
  const maxVisible = searchFilter ? 50 : 30;
  const visible = sorted.slice(0, maxVisible);

  visible.forEach(server => {
    const chip = document.createElement('button');
    chip.classList.add('chip');
    if (selectedServers.has(server.name)) chip.classList.add('selected');

    const dot = document.createElement('span');
    dot.classList.add('chip-dot');
    dot.style.backgroundColor = getServerColor(server.name);

    const label = document.createTextNode(server.name);

    chip.appendChild(dot);
    chip.appendChild(label);

    chip.addEventListener('click', () => {
      if (selectedServers.has(server.name)) {
        selectedServers.delete(server.name);
        chip.classList.remove('selected');
      } else {
        if (selectedServers.size >= 10) return; // max 10
        selectedServers.add(server.name);
        chip.classList.add('selected');
      }
      fetchAndRender();
    });

    chipsContainer.appendChild(chip);
  });

  if (filtered.length > maxVisible) {
    const more = document.createElement('span');
    more.classList.add('chips-loading');
    more.textContent = `+${filtered.length - maxVisible} more (use filter)`;
    chipsContainer.appendChild(more);
  }

  if (filtered.length === 0) {
    const none = document.createElement('span');
    none.classList.add('chips-loading');
    none.textContent = 'No servers match filter';
    chipsContainer.appendChild(none);
  }
}

// === Data fetching (single batched request) ===
let fetchDebounce = null;

function fetchAndRender() {
  clearTimeout(fetchDebounce);
  fetchDebounce = setTimeout(doFetch, 150);
}

async function doFetch() {
  if (selectedServers.size === 0) {
    lastFetchedData = null;
    if (myChart) { myChart.destroy(); myChart = null; }
    return;
  }

  // Abort previous in-flight request
  if (fetchController) fetchController.abort();
  fetchController = new AbortController();

  chartLoading.classList.add('visible');

  const { after, before } = getTimeRange();
  const params = new URLSearchParams();
  params.set("filters", [...selectedServers].join(","));
  if (after) params.set("after", after);
  if (before) params.set("before", before);

  // hey devs! feel free to use this endpoint. you may be limited so join the discord to request a key
  const url = "https://relay.awesome.tf/server-history?" + params.toString();

  try {
    const resp = await fetch(url, { signal: fetchController.signal });
    if (!resp.ok) {
      const errTxt = await resp.text();
      console.warn("History fetch error:", errTxt);
      chartLoading.classList.remove('visible');
      return;
    }
    const data = await resp.json();
    lastFetchedData = data;
    renderChart(data);
  } catch (e) {
    if (e.name !== 'AbortError') {
      console.error("Failed to fetch history:", e);
    }
  } finally {
    chartLoading.classList.remove('visible');
  }
}

// === Chart rendering ===
function inferStepSeconds(points) {
  if (!points || points.length < 2) return 300;
  const diffs = [];
  for (let i = 1; i < points.length; i++) {
    const d = points[i].t - points[i - 1].t;
    if (Number.isFinite(d) && d > 0) diffs.push(d);
  }
  if (!diffs.length) return 300;
  const freq = new Map();
  for (const d of diffs) freq.set(d, (freq.get(d) || 0) + 1);
  let bestDiff = 300, bestCount = -1;
  for (const [d, c] of freq.entries()) {
    if (c > bestCount || (c === bestCount && d < bestDiff)) {
      bestDiff = d; bestCount = c;
    }
  }
  return (Number.isFinite(bestDiff) && bestDiff > 0) ? bestDiff : 300;
}

function fillMissingPointsWithZeros(points) {
  if (!points || points.length === 0) return [];
  const step = inferStepSeconds(points);
  const map = new Map();
  for (const pt of points) map.set(pt.t, pt.p);
  const minT = points[0].t;
  const maxT = points[points.length - 1].t;
  const filled = [];
  for (let t = minT; t <= maxT; t += step) {
    filled.push({ t, p: map.get(t) ?? 0 });
  }
  return filled;
}

function computeRollingAverage(points, windowSize) {
  const smoothed = [];
  for (let i = 0; i < points.length; i++) {
    const start = Math.max(0, i - windowSize + 1);
    let sum = 0;
    for (let j = start; j <= i; j++) sum += points[j].p;
    smoothed.push({ t: points[i].t, p: sum / (i - start + 1) });
  }
  return smoothed;
}

function buildDatasets(data) {
  const serverNames = Object.keys(data.servers);
  if (!serverNames.length) return [];
  const rollingWindow = parseInt(rollingSlider.value, 10);

  return serverNames.map(serverKey => {
    let points = Object.entries(data.servers[serverKey]).map(([ts, count]) => ({
      t: parseInt(ts, 10), p: count
    }));
    points.sort((a, b) => a.t - b.t);
    points = fillMissingPointsWithZeros(points);
    points = computeRollingAverage(points, rollingWindow);

    return {
      label: serverKey,
      data: points.map(pt => ({ x: pt.t * 1000, y: pt.p })),
      borderColor: getServerColor(serverKey),
      backgroundColor: 'rgba(0,0,0,0)',
      pointRadius: 0,
      borderWidth: 2,
      tension: 0.25
    };
  });
}

const gridColor = 'rgba(74, 158, 255, 0.08)';
const tickColor = '#565e68';

function renderChart(data) {
  if (!data || !data.servers || !Object.keys(data.servers).length) {
    if (myChart) { myChart.destroy(); myChart = null; }
    return;
  }

  const datasets = buildDatasets(data);

  if (myChart) {
    myChart.data.datasets = datasets;
    myChart.update({ duration: 400 });
    return;
  }

  const ctx = document.getElementById('historyChart').getContext('2d');

  myChart = new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      animation: { duration: 400 },
      interaction: { mode: 'index', intersect: false },
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day' },
          title: {
            display: true, text: 'Time',
            color: tickColor,
            font: { family: "'Rajdhani', sans-serif", weight: '600', size: 12 }
          },
          ticks: {
            color: tickColor,
            font: { family: "'IBM Plex Mono', monospace", size: 11 }
          },
          grid: { color: gridColor }
        },
        y: {
          title: {
            display: true, text: 'Players',
            color: tickColor,
            font: { family: "'Rajdhani', sans-serif", weight: '600', size: 12 }
          },
          ticks: {
            color: tickColor,
            font: { family: "'IBM Plex Mono', monospace", size: 11 }
          },
          grid: { color: gridColor },
          beginAtZero: true
        }
      },
      plugins: {
        tooltip: {
          backgroundColor: '#151b23',
          borderColor: 'rgba(74, 158, 255, 0.2)',
          borderWidth: 1,
          titleFont: { family: "'Rajdhani', sans-serif", weight: '600' },
          bodyFont: { family: "'IBM Plex Mono', monospace", size: 12 },
          padding: 10,
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${Math.round(ctx.parsed.y)} players`
          }
        },
        legend: {
          display: true,
          labels: {
            color: '#8b949e',
            font: { family: "'IBM Plex Mono', monospace", size: 12 },
            padding: 16,
            usePointStyle: true,
            pointStyle: 'rectRounded'
          }
        }
      }
    }
  });
}
