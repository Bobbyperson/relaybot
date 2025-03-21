let allServers = [];
let selectedServers = [];
let lastFetchedData = null;
let myChart = null;

const COLORS = [
  "#33aa33", "#3388dd", "#d47d1f", "#ce33ce", "#ff5050",
  "#669999", "#66cc66", "#e6e600", "#ff66cc", "#99ccff"
];

document.getElementById('searchBtn').addEventListener('click', handleSearch);
document.getElementById('fetchDataBtn').addEventListener('click', fetchHistoryData);

const rollingSlider = document.getElementById('rollingSlider');
const sliderValueSpan = document.getElementById('sliderValue');

rollingSlider.addEventListener('input', () => {
  sliderValueSpan.textContent = rollingSlider.value;
  if (lastFetchedData && myChart) {
    updateChartData(lastFetchedData);
    myChart.update({ duration: 500, easing: 'easeInOutCubic' });
  }
});

loadServerList();

async function loadServerList() {
  try {
    const resp = await fetch("https://relay.awesome.tf/server-scoreboard");
    const data = await resp.json();
    allServers = data.servers || [];

    const topThree = [...allServers]
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);

    selectedServers = topThree.map(s => s.name);
    updateSelectedServersUI();

    fetchHistoryData();
  } catch(e) {
    console.error("Failed to load server list:", e);
  }
}

function handleSearch() {
  const query = document.getElementById('searchInput').value.trim().toLowerCase();
  const resultsDiv = document.getElementById('searchResults');
  resultsDiv.innerHTML = '';

  if (!query) {
    const topServers = [...allServers]
      .sort((a, b) => b.score - a.score)
      .slice(0, 10);

    if (topServers.length === 0) {
      resultsDiv.textContent = "No servers found.";
      return;
    }

    topServers.forEach(serverObj => {
      const div = document.createElement('div');
      div.style.marginBottom = "0.5rem";

      const textSpan = document.createElement('span');
      textSpan.textContent = `${serverObj.name} (Score: ${serverObj.score}) `;

      const addBtn = document.createElement('button');
      addBtn.textContent = "Add";
      addBtn.onclick = () => addServer(serverObj.name);

      div.appendChild(textSpan);
      div.appendChild(addBtn);
      resultsDiv.appendChild(div);
    });
    return;
  }

  let matches = allServers.filter(s => s.name.toLowerCase().includes(query));
  matches.sort((a, b) => b.score - a.score);

  if (matches.length === 0) {
    resultsDiv.textContent = "No servers found for that search.";
    return;
  }

  matches.forEach(serverObj => {
    const div = document.createElement('div');
    div.style.marginBottom = "0.5rem";

    const textSpan = document.createElement('span');
    textSpan.textContent = `${serverObj.name} (Score: ${serverObj.score}) `;

    const addBtn = document.createElement('button');
    addBtn.textContent = "Add";
    addBtn.onclick = () => addServer(serverObj.name);

    div.appendChild(textSpan);
    div.appendChild(addBtn);
    resultsDiv.appendChild(div);
  });
}

function addServer(name) {
  if (!selectedServers.includes(name)) {
    selectedServers.push(name);
    updateSelectedServersUI();
  }
}

function removeServer(name) {
  selectedServers = selectedServers.filter(s => s !== name);
  updateSelectedServersUI();
}

function updateSelectedServersUI() {
  const container = document.getElementById('selectedServers');
  container.innerHTML = '';

  if (selectedServers.length === 0) {
    container.textContent = "(No servers selected)";
    return;
  }

  selectedServers.forEach(sName => {
    const div = document.createElement('div');
    div.style.marginBottom = "0.5rem";

    const textSpan = document.createElement('span');
    textSpan.textContent = sName;

    const removeBtn = document.createElement('button');
    removeBtn.textContent = "Remove";
    removeBtn.style.marginLeft = "0.5rem";
    removeBtn.onclick = () => removeServer(sName);

    div.appendChild(textSpan);
    div.appendChild(removeBtn);
    container.appendChild(div);
  });
}

function parseDateTimeLocal(value) {
  if (!value) return null;
  const dateObj = new Date(value);
  if (isNaN(dateObj.getTime())) {
    return null;
  }
  return Math.floor(dateObj.getTime() / 1000);
}

async function fetchHistoryData() {
  if (selectedServers.length === 0) {
    alert("Please add at least one server first.");
    return;
  }

  const afterVal = document.getElementById('afterTime').value;
  const beforeVal = document.getElementById('beforeTime').value;
  const afterTime = parseDateTimeLocal(afterVal);
  const beforeTime = parseDateTimeLocal(beforeVal);

  let combined = { servers: {} };

  for (let sName of selectedServers) {
    const params = new URLSearchParams();
    params.set("filter", sName);
    if (afterTime !== null)  params.set("after", afterTime);
    if (beforeTime !== null) params.set("before", beforeTime);

    // hey devs! feel free to use this endpoint. you may be limited so join the discord to request a key
    const url = "https://relay.awesome.tf/server-history?" + params.toString();
    try {
      const resp = await fetch(url);
      if (!resp.ok) {
        const errTxt = await resp.text();
        console.warn(`Error fetching ${sName}: `, errTxt);
        continue;
      }
      const data = await resp.json();
      Object.assign(combined.servers, data.servers);
    } catch(e) {
      console.error(`Failed to fetch ${sName}: `, e);
    }
  }

  lastFetchedData = combined;
  renderChartJs(combined);
}

function computeRollingAverage(points, windowSize) {
  const smoothed = [];
  for (let i = 0; i < points.length; i++) {
    const start = Math.max(0, i - windowSize + 1);
    let sum = 0;
    for (let j = start; j <= i; j++) {
      sum += points[j].p;
    }
    const count = (i - start + 1);
    smoothed.push({ t: points[i].t, p: sum / count });
  }
  return smoothed;
}

function updateChartData(data) {
  if (!myChart) return;
  myChart.data.datasets = buildDatasets(data);
}

function buildDatasets(data) {
  const serverNames = Object.keys(data.servers);
  if (serverNames.length === 0) return [];

  const rollingWindow = parseInt(rollingSlider.value, 10);

  return serverNames.map((serverKey, i) => {
    let points = Object.entries(data.servers[serverKey]).map(([tsStr, count]) => ({
      t: parseInt(tsStr, 10),
      p: count
    }));

    points.sort((a, b) => a.t - b.t);
    points = computeRollingAverage(points, rollingWindow);

    const chartPoints = points.map(pt => ({
      x: pt.t * 1000,
      y: pt.p
    }));

    return {
      label: serverKey,
      data: chartPoints,
      borderColor: COLORS[i % COLORS.length],
      backgroundColor: 'rgba(0,0,0,0)',
      pointRadius: 0,
      tension: 0.2
    };
  });
}

function renderChartJs(data) {
  const canvas = document.getElementById('historyChart');
  const ctx = canvas.getContext('2d');

  if (!data || !data.servers) {
    alert("No data returned.");
    return;
  }
  const serverNames = Object.keys(data.servers);
  if (!serverNames.length) {
    alert("No data points to display.");
    return;
  }

  const datasets = buildDatasets(data);

  if (myChart) {
    myChart.destroy();
  }

  myChart = new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      animation: {
        duration: 0
      },
      interaction: {
        mode: 'index',
        intersect: false
      },
      responsive: false,
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'day'
          },
          title: {
            display: true,
            text: 'Time (UTC)'
          }
        },
        y: {
          title: {
            display: true,
            text: 'Players'
          },
          beginAtZero: true
        }
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: function (ctx) {
              const floatVal = ctx.parsed.y; 
              const roundedVal = Math.round(floatVal);
              return `${ctx.dataset.label}: ${roundedVal} players`;
            }
          }
        },
        legend: {
          display: true
        }
      }
    }
  });
}
